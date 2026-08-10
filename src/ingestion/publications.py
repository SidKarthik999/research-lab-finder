"""Backfill Publications for professors already ingested via openalex.py.

Fetches each professor's own works directly by their OpenAlex author id
(`pyalex.Works().filter(author={"id": ...})`), rather than pulling works by
institution the way the original (buggy) pipeline did -- see CLAUDE.md for
why that approach was replaced. Because this hangs off a Professor row whose
institution attribution is already verified, there's no attribution risk
here: a publication is only ever linked to the professor whose own author id
was queried for it.

Run from the repo root: python -m src.ingestion.publications
"""

import re

import pyalex

import src.ingestion.openalex_client  # noqa: F401 -- import for its config/session-hardening side effects
from src.database import (
    backoff_sleep,
    close_connection,
    get_professors_without_publications,
    init_pool,
    insert_professor_publication,
    insert_publication,
    is_connection_error,
)


TAG_PATTERN = re.compile(r"<[^>]+>")


def strip_markup(text):
    """OpenAlex titles for math/physics papers sometimes embed raw
    <mml:math> MathML markup (e.g. for an equation in the title) instead of
    plain text. Strip tags so titles render as text, not broken markup.
    """
    if not text:
        return text
    return re.sub(r"\s+", " ", TAG_PATTERN.sub("", text)).strip()


def reconstruct_abstract(abstract_inverted_index):
    max_position = max(
        position
        for positions in abstract_inverted_index.values()
        for position in positions
    )
    abstract_words = [""] * (max_position + 1)
    for word, positions in abstract_inverted_index.items():
        for position in positions:
            abstract_words[position] = word

    return " ".join(abstract_words)


def get_works_for_professor(openalex_author_id, limit=10):
    return (
        pyalex.Works()
        .filter(author={"id": openalex_author_id})
        .sort(cited_by_count="desc")
        .get(per_page=limit)
    )


def insert_openalex_publication(work):
    primary_location = work.get('primary_location') or {}
    source_info = primary_location.get('source') or {}
    abstract_inverted_index = work.get('abstract_inverted_index')
    publication_id = insert_publication(
        title=strip_markup(work.get('display_name')),
        abstract=reconstruct_abstract(abstract_inverted_index) if abstract_inverted_index else None,
        publication_date=work.get('publication_date'),
        journal=source_info.get('display_name'),
        doi=work['ids'].get('doi'),
        url=primary_location.get('landing_page_url'),
        openalex_id=work['id'],
        source="OpenAlex"
    )
    return publication_id


def ingest_publications_for_professor(professor_id, openalex_author_id, limit=10):
    works = get_works_for_professor(openalex_author_id, limit=limit)
    inserted = 0
    for work in works:
        try:
            publication_id = insert_openalex_publication(work)
            insert_professor_publication(professor_id, publication_id)
            inserted += 1
        except Exception as e:
            # A connection failure (pool exhaustion, Neon waking from
            # autosuspend -- found 2026-08-10) is let through rather than
            # swallowed here: ingest_all_publications()'s circuit breaker
            # below only ever sees exceptions raised out of *this*
            # function, so catching this one silently, the same as a
            # genuinely bad OpenAlex record, made it invisible to that
            # breaker -- a sustained outage could burn through the entire
            # remaining professor list, one 90-second pool timeout at a
            # time, with nothing ever tripping the "stop early" path.
            if is_connection_error(e):
                raise
            print(f"Failed {work.get('display_name')}: {e}")

    return inserted


def ingest_all_publications(limit_per_professor=10, max_consecutive_failures=5):
    """Only pulls professors with zero ProfessorPublication rows so far --
    each professor here costs one paid, filtered-list OpenAlex request (not
    a free single-record view), so a resumed/rerun call must not re-spend
    that on professors already done. See the institution-ingestion skip
    logic in openalex.py (get_professors_by_institution check) for the same
    reasoning applied there after a real run wasted quota re-walking
    already-finished institutions.

    Each professor is one atomic request (get_works_for_professor fetches
    all of that professor's works in a single call), so professors are
    naturally finished one at a time in order -- never interleaved.

    Stops early after max_consecutive_failures in a row, on the assumption
    the daily budget/prepaid balance just ran out (the same 429 signal
    covers both -- OpenAlex gives no separate "which one" indicator).
    Without this, a budget-exhausted run would otherwise burn through
    every remaining professor one by one, each paying the full bounded
    retry+backoff delay before failing, for no benefit -- intended to be
    re-run daily (e.g. via a scheduled job) against whatever's left,
    letting each day's free budget pick up where the last one stopped.
    A real success anywhere resets the counter, so an isolated one-off
    failure (a single professor's data issue, not sustained throttling)
    doesn't prematurely abort a run that still has budget left.
    """
    professors = get_professors_without_publications()
    total = 0
    consecutive_failures = 0

    for professor_id, name, openalex_id in professors:
        try:
            count = ingest_publications_for_professor(professor_id, openalex_id, limit=limit_per_professor)
            print(f"{name}: {count} publication(s)")
            total += count
            consecutive_failures = 0
        except Exception as e:
            print(f"Failed {name}: {e}")
            consecutive_failures += 1
            # A connection failure gets a backoff pause before the next
            # attempt (see backoff_sleep()'s docstring) -- an OpenAlex
            # budget failure doesn't, since there's no reason to believe
            # waiting a few seconds changes whether today's budget is
            # exhausted, and the circuit breaker below already handles
            # that case by stopping outright.
            if is_connection_error(e):
                backoff_sleep(consecutive_failures)
            if consecutive_failures >= max_consecutive_failures:
                print(
                    f"Stopping after {consecutive_failures} consecutive failures "
                    "-- likely out of budget for today. Re-run tomorrow to pick up "
                    "where this left off."
                )
                break

    return total


if __name__ == "__main__":
    # A much larger pool timeout than the web app's default 30s -- see
    # init_pool()'s docstring in src/database.py. Must run before the
    # first get_connection() call (inside ingest_all_publications())
    # lazily creates the pool with the default instead.
    init_pool(timeout=90)
    total = ingest_all_publications()
    print(f"Inserted {total} publication(s)")
    close_connection()
    close_connection()
