"""Backfill ResearchTopic/ProfessorTopic for professors already ingested via
openalex.py.

Fetches each professor's own OpenAlex Author record and reads its `topics`
field directly (`pyalex.Authors()[openalex_author_id]`), rather than
inferring subject matter from Works affiliated with an institution -- see
CLAUDE.md for why that approach was replaced. Author.topics is derived from
that author's own works, so there's no attribution risk here, the same
safe pattern publications.py already uses.

Author.topics doesn't include a normalized score; each topic instead carries
a `count` (how many of the author's own works are tagged with it), already
ordered most-relevant-first. That count is stored as ProfessorTopic.works_count.

Run from the repo root: python -m src.ingestion.topics
"""

import pyalex

import src.ingestion.openalex_client  # noqa: F401 -- import for its config/session-hardening side effects
from src.database import (
    close_connection,
    get_professors_without_topics,
    insert_professor_topic,
    insert_research_topic,
)


def get_author_topics(openalex_author_id):
    author = pyalex.Authors()[openalex_author_id]
    return author.get("topics") or []


def insert_openalex_topic(topic):
    subfield = (topic.get("subfield") or {}).get("display_name")
    field = (topic.get("field") or {}).get("display_name")
    domain = (topic.get("domain") or {}).get("display_name")
    return insert_research_topic(
        openalex_id=topic["id"],
        name=topic["display_name"],
        subfield=subfield,
        field=field,
        domain=domain,
        source="OpenAlex",
    )


def insert_topics_for_professor(professor_id, openalex_author_id):
    topics = get_author_topics(openalex_author_id)
    for topic in topics:
        topic_id = insert_openalex_topic(topic)
        insert_professor_topic(professor_id, topic_id, works_count=topic.get("count"))
    return len(topics)


def insert_topics_from_professors(professors, max_consecutive_failures=5):
    """Stops early after max_consecutive_failures in a row, on the assumption
    the daily budget/prepaid balance just ran out -- see the same guard in
    publications.py's ingest_all_publications() for the full reasoning.
    A real success anywhere resets the counter.
    """
    professors_processed = 0
    consecutive_failures = 0
    for professor_id, name, openalex_id in professors:
        try:
            topic_count = insert_topics_for_professor(professor_id, openalex_id)
            print(f"Inserted {topic_count} topics for {name}")
            professors_processed += 1
            consecutive_failures = 0

        except Exception as e:
            print(f"Failed {name}: {e}")
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                print(
                    f"Stopping after {consecutive_failures} consecutive failures "
                    "-- likely out of budget for today. Re-run tomorrow to pick up "
                    "where this left off."
                )
                break

    return professors_processed


if __name__ == "__main__":
    # get_professors_without_topics() skips anyone with an existing
    # ProfessorTopic row so a resumed/rerun call doesn't redo work -- these
    # are free single-record OpenAlex views (not paid filtered-list
    # requests like publications.py), but still no reason to waste the
    # request/time budget re-fetching professors already done.
    professors = get_professors_without_topics()

    insert_topics_from_professors(professors)

    close_connection()
