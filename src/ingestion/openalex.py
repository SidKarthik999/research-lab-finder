from dotenv import load_dotenv
from functools import lru_cache
import os
import re
import pyalex
import src.ingestion.openalex_client  # noqa: F401 -- import for its config/session-hardening side effects
from src.database import (
    insert_institution,
    insert_professor,
    get_professors_by_institution,
    close_connection,
)

load_dotenv()

# CJK, Hangul, Cyrillic, Arabic, Hebrew, Thai, Greek -- display names in these
# scripts are excluded so professor names in the DB are consistently English.
NON_LATIN_SCRIPT = re.compile(
    "["
    "一-鿿"  # CJK
    "぀-ヿ"  # Hiragana/Katakana
    "가-힣"  # Hangul
    "Ѐ-ӿ"  # Cyrillic
    "؀-ۿ"  # Arabic
    "֐-׿"  # Hebrew
    "฀-๿"  # Thai
    "Ͱ-Ͽ"  # Greek
    "]"
)

# A token that's just an initial or a run of initials, e.g. "A", "A.",
# "K.-Y.", "M.P.", "R.D" -- but not a real (if short) name like "Kim" or "Li".
INITIAL_TOKEN = re.compile(r"^[A-Z](?:[.\-]+[A-Z])*\.?$")

# OpenAlex occasionally creates an "Author" entity for something that isn't a
# person at all -- e.g. "The Auk" (an ornithology journal misattributed as an
# author via a citation-parsing error upstream). Only "The " is safe to filter
# this way: "A"/"An" collide too often with real initials ("A Boyle") and real
# given names ("An" is a common Vietnamese/Korean first name), but no real
# person's name starts with "The ". A telltale companion signal (not checked
# here, but worth knowing) is an implausibly large works_count with no ORCID
# and an incoherent last_known_institutions list.
NON_PERSON_NAME = re.compile(r"^the\s", re.IGNORECASE)


def is_non_latin_name(name):
    return bool(NON_LATIN_SCRIPT.search(name))


def is_non_person_name(name):
    return bool(NON_PERSON_NAME.match(name))


def prefer_full_name(display_name, alternatives):
    """If display_name is mostly initials, look for a fuller form in
    display_name_alternatives -- but only accept one that shares the same
    surname and whose other tokens start with the same initials, since
    OpenAlex's alternative-name lists for common surnames are often a
    disambiguation cluster of unrelated people, not spelling variants of
    one person.
    """
    tokens = display_name.split()
    if len(tokens) < 2 or not any(INITIAL_TOKEN.match(t) for t in tokens[:-1]):
        return display_name

    surname = tokens[-1].lower()
    lead_tokens = tokens[:-1]
    candidates = []

    for alt in alternatives or []:
        alt_tokens = alt.split()
        if len(alt_tokens) < len(tokens) or alt_tokens[-1].lower() != surname:
            continue

        matches = True
        for i, orig in enumerate(lead_tokens):
            candidate = alt_tokens[i]
            if INITIAL_TOKEN.match(orig):
                if not candidate.lower().startswith(orig[0].lower()):
                    matches = False
                    break
            elif candidate.lower() != orig.lower():
                matches = False
                break
        if not matches:
            continue

        if any(INITIAL_TOKEN.match(t) for t in alt_tokens):
            continue  # still has initials itself, not a full expansion

        candidates.append(alt)

    if not candidates:
        return display_name

    # Prefer properly-cased forms (e.g. "Aaron Roodman") over ALL-CAPS or
    # all-lowercase variants of the same length, then prefer the shortest.
    def sort_key(alt):
        badly_cased = alt.isupper() or alt.islower()
        return (badly_cased, len(alt))

    return min(candidates, key=sort_key)


def search_institution(institution_name):
    results = pyalex.Institutions().search(institution_name).get()
    if results:
        return results[0]
    return None

def get_top_us_institutions(limit=100):
    institutions = (
        pyalex.Institutions()
        .filter(country_code="US", type="education")
        .sort(works_count="desc")
        .get(per_page=limit)
    )
    return [institution["display_name"] for institution in institutions]

def get_us_institutions(min_works_count=500):
    """All US educational institutions above a works-count floor, not just a
    fixed top-N -- OpenAlex's own works_count filter, paginated (per_page
    caps at 200, so this can return well over 1000 results). Returns full
    institution records, not just names, so callers can ingest directly
    without a second (fuzzy, name-based) search_institution() lookup.
    """
    query = (
        pyalex.Institutions()
        .filter(country_code="US", type="education", works_count=f">{min_works_count}")
        .sort(works_count="desc")
    )
    institutions = []
    for page in query.paginate(per_page=200):
        institutions.extend(page)
    return institutions

def insert_openalex_institution(institution):
    institution_id = insert_institution(
        name = institution['display_name'],
        website = institution.get('homepage_url'),
        city = institution['geo'].get('city'),
        state = institution['geo'].get('region'),
        country_code = institution['geo'].get('country_code'),
        openalex_id = institution['id'],
        ror_id = institution['ids'].get('ror'),
        source = "OpenAlex"
    )
    return institution_id

def get_professors_at_institution(openalex_institution_id, limit=50):
    # Filtering by last_known_institutions.id asks OpenAlex "who currently
    # works at this institution" directly, rather than inferring affiliation
    # from co-authorship on works affiliated with the institution (which
    # mislabels co-authors from other universities entirely -- the bug this
    # replaces). Sorting by works_count favors established researchers over
    # one-off/incidental author records.
    authors = (
        pyalex.Authors()
        .filter(last_known_institutions={"id": openalex_institution_id})
        .sort(works_count="desc")
        .get(per_page=limit)
    )
    return authors

@lru_cache(maxsize=1)
def get_fields():
    """All ~26 OpenAlex top-level fields (id + display_name) -- the same
    fixed taxonomy topics.py stores as ResearchTopic.field. Fetched
    dynamically, like get_top_us_institutions/get_us_institutions, rather
    than hardcoded, so a taxonomy update doesn't silently go stale.
    Cached: this doesn't depend on the institution being ingested, so a
    full-run loop over institutions should only ever fetch it once.
    """
    fields = pyalex.Fields().get(per_page=200)
    return tuple({"id": field["id"], "display_name": field["display_name"]} for field in fields)

@lru_cache(maxsize=32)
def get_field_topic_ids(field_id, limit=100):
    """The field's own most-published-in topics, sorted by each topic's
    works_count. Authors can't be filtered by field directly (the API's
    valid-fields list for /authors has topics.id but no topics.field.id) --
    so this is the building block for field-scoped breadth: an OR-able list
    of topic ids standing in for "this field", capped at 100 because the API
    rejects more than 100 OR'd values for a single filter.
    Cached per field_id for the same reason as get_fields(): independent of
    the institution, so it should only be fetched once per field per run.
    """
    topics = (
        pyalex.Topics()
        .filter(field={"id": field_id})
        .sort(works_count="desc")
        .get(per_page=limit)
    )
    return tuple(topic["id"] for topic in topics)

def get_professors_in_field(openalex_institution_id, field_id, topic_ids, per_field_limit=10, candidate_pool=None):
    """Top-cited professors at an institution whose own PRIMARY topic (the
    highest-`count` entry in their Author.topics, which OpenAlex already
    returns most-relevant-first) falls under field_id.

    Candidates are fetched via an OR filter over the field's topic ids
    (topics.id, since topics.field.id isn't filterable) sorted by each
    author's overall works_count, then narrowed to authors whose own
    topics[0] actually IS this field. Skipping that narrowing step would
    rank by unrelated overall citation volume -- e.g. a highly-cited
    chemist can turn up as a candidate for "Arts and Humanities" through one
    tangential paper. Within the narrowed set, ranking is by the primary
    topic's own `count` (how much of *that author's* own work is in this
    field) rather than overall works_count, since that's the actual
    per-field relevance signal -- Author.topics has no separate normalized
    score, same reasoning as ProfessorTopic.works_count in topics.py.

    candidate_pool defaults to 6x per_field_limit (capped at the API's
    per_page max of 200) since roughly 40-60% of candidates survive the
    primary-field narrowing in practice -- verified live at per_field_limit
    10 (candidate_pool 60) and 20 (candidate_pool 120), both reliably
    returning full field counts except in genuinely thin fields at a small
    institution (e.g. Chemical Engineering at a school with only 3
    matching authors total), which is real scarcity, not a pool-size
    artifact.
    """
    if not topic_ids:
        return []

    if candidate_pool is None:
        candidate_pool = min(200, per_field_limit * 6)

    candidates = (
        pyalex.Authors()
        .filter(
            last_known_institutions={"id": openalex_institution_id},
            topics={"id": "|".join(topic_ids)},
        )
        .sort(works_count="desc")
        .get(per_page=candidate_pool)
    )

    field_id_suffix = field_id.rsplit("/", 1)[-1]
    matches = [
        author for author in candidates
        if author.get("topics")
        and author["topics"][0]["field"]["id"].rsplit("/", 1)[-1] == field_id_suffix
    ]
    matches.sort(key=lambda author: author["topics"][0]["count"], reverse=True)
    return matches[:per_field_limit]

def get_professors_at_institution_by_field(openalex_institution_id, per_field_limit=10):
    """Breadth-first alternative to get_professors_at_institution(): instead
    of one flat top-N-by-works_count query (which Phase 3 found to be
    dominated by a handful of prolific fields -- e.g. a real 200-author
    sample from a large university was 63 Medicine/54 Physics and zero
    Arts and Humanities, Business, Dentistry, etc.), this pulls up to
    per_field_limit top-cited professors from EACH of the ~26 fields
    separately and merges them. Institutions naturally get fewer total
    professors if they have fewer active fields (a small college won't hit
    26 fields) -- that's real coverage, not a bug.

    Costs one Authors request per field (~26 per institution, vs. 1 for the
    flat version) -- get_fields()/get_field_topic_ids() are lru_cache'd so
    that cost is only the per-institution Authors calls, not re-fetching the
    field/topic-id lookups on every institution in a full run.

    Each field is wrapped in its own try/except: an exhausted-retries
    failure on one field (a persistent 429, a dropped connection) skips just
    that field rather than aborting the whole institution -- a first full
    run without this per-item isolation lost ALL professors for ~1,450
    institutions because one field's exception aborted the other 25 that
    would otherwise have succeeded.
    """
    authors = []
    seen_ids = set()
    for field in get_fields():
        try:
            field_authors = get_professors_in_field(
                openalex_institution_id,
                field["id"],
                get_field_topic_ids(field["id"]),
                per_field_limit=per_field_limit,
            )
        except Exception as e:
            print(f"Failed field {field['display_name']}: {e}")
            continue

        for author in field_authors:
            if author["id"] in seen_ids:
                continue
            seen_ids.add(author["id"])
            authors.append(author)
    return authors

def insert_openalex_professor(author, institution_id=None):
    if is_non_latin_name(author['display_name']) or is_non_person_name(author['display_name']):
        return None

    name = prefer_full_name(author['display_name'], author.get('display_name_alternatives'))
    professor_id = insert_professor(
        name=name,
        orcid=author.get('orcid'),
        openalex_id=author['id'],
        institution_id=institution_id,
        source="OpenAlex"
    )
    return professor_id

def insert_professors_from_institution(authors, institution_id):
    professors_inserted = 0
    for author in authors:
        try:
            professor_id = insert_openalex_professor(author, institution_id)
            if professor_id is None:
                print(f"Skipped {author['display_name']}: non-Latin script or non-person name")
                continue
            print(f"Inserted {author['display_name']}")
            professors_inserted += 1

        except Exception as e:
            print(f"Failed {author['display_name']}: {e}")

    return professors_inserted

def ingest_institution_object(institution, per_field_limit=10, skip_if_populated=True):
    """Same as ingest_institution(), but takes an already-fetched OpenAlex
    institution record directly instead of re-searching by name -- avoids a
    second, fuzzy text search for institutions fetched in bulk via
    get_us_institutions(), where a name-based re-search could occasionally
    resolve to a different institution than the one actually intended.

    Uses get_professors_at_institution_by_field() (top-cited-per-field, not
    a flat top-N) so professor coverage spans a variety of fields instead of
    skewing toward whichever field happens to be most-cited overall -- see
    Phase 3 in docs/ROADMAP.md.

    skip_if_populated (default True) skips the ~26-request field-breadth
    pull entirely for an institution that already has at least one
    Professor row -- a resumed full run would otherwise re-spend its whole
    OpenAlex request budget re-fetching institutions it already finished
    before ever reaching new ones (this is exactly what happened resuming
    after a quota reset: the run re-walked the same ~200 already-done
    institutions, in the same works_count-sorted order every time, burning
    quota with zero new rows). The institution row itself is still
    upserted either way (a cheap DB call, no API cost) so name/website/etc
    stay fresh. Pass False to force a genuine re-pull for one institution
    (e.g. topping up an institution that only partially completed).
    """
    institution_id = insert_openalex_institution(institution)

    if skip_if_populated and get_professors_by_institution(institution_id):
        print(f"Skipped {institution['display_name']}: already has professors")
        return institution_id

    print(f"Inserted {institution['display_name']}: {institution_id}")

    authors = get_professors_at_institution_by_field(institution["id"], per_field_limit=per_field_limit)
    insert_professors_from_institution(authors, institution_id)

    return institution_id

def ingest_institution(institution_name, per_field_limit=10, skip_if_populated=True):
    institution = search_institution(institution_name)
    if institution is None:
        print(f"Failed {institution_name}: not found in OpenAlex")
        return None

    return ingest_institution_object(institution, per_field_limit=per_field_limit, skip_if_populated=skip_if_populated)

# Institutions ranked in the top LARGE_INSTITUTION_RANK by works_count get a
# deeper per-field pull (large research universities plausibly have 20
# genuinely distinct top-cited professors in most fields, and are also the
# schools students searching from a major hub like NYC are most likely to
# actually query). Below that rank, per_field_limit drops to 5 -- smaller/
# regional schools often don't have 20 (or even 10) real matches in a given
# field (a spot-check of the University of Nebraska Omaha, works_count
# ~22,700, topped out at 3-8 for several fields even when asked for 10), so
# asking for more there just spends API calls without adding real rows.
# 100 was chosen because it's the same cutoff the pre-Phase-3 pipeline used
# for its "top US institutions" slice (get_top_us_institutions) -- i.e. the
# boundary between "large, broadly recognizable research university" and
# everything else. works_count at rank 100 is roughly 90,000 vs. ~500 at the
# tail of the full ~1,764-institution set, so the two tiers are genuinely
# different populations, not an arbitrary split.
LARGE_INSTITUTION_RANK = 100

if __name__  == "__main__":
    # Full run -- attribution accuracy was verified against an 8-institution
    # test batch first (see CLAUDE.md). Phase 3 widened this from a fixed
    # top-100 to every US institution above a works-count floor, and from a
    # flat top-50-by-citations per institution to top-cited-per-field (see
    # get_professors_at_institution_by_field) so coverage isn't dominated by
    # whichever field is most-cited overall -- see docs/ROADMAP.md. This
    # costs ~26x the Authors requests per institution, so a full run over
    # ~1,700+ institutions is expected to take hours.
    #
    # get_us_institutions() already sorts by works_count desc, so the first
    # LARGE_INSTITUTION_RANK entries are the large-institution tier.
    institutions = get_us_institutions(min_works_count=500)

    for rank, institution in enumerate(institutions):
        per_field_limit = 20 if rank < LARGE_INSTITUTION_RANK else 5
        try:
            ingest_institution_object(institution, per_field_limit=per_field_limit)

        except Exception as e:
            print(f"Failed {institution['display_name']}: {e}")

    close_connection()
