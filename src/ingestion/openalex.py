from dotenv import load_dotenv
import os
import re
import pyalex
from src.database import (
    insert_institution,
    insert_professor,
    close_connection,
)

load_dotenv()

pyalex.config.api_key = os.getenv("OPENALEX_API_KEY")

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

def ingest_institution(institution_name, limit=50):
    institution = search_institution(institution_name)
    if institution is None:
        print(f"Failed {institution_name}: not found in OpenAlex")
        return None

    institution_id = insert_openalex_institution(institution)
    print(f"Inserted {institution_name}: {institution_id}")

    authors = get_professors_at_institution(institution["id"], limit=limit)
    insert_professors_from_institution(authors, institution_id)

    return institution_id

if __name__  == "__main__":
    # Full run -- attribution accuracy was verified against an 8-institution
    # test batch first (see CLAUDE.md).
    institution_names = get_top_us_institutions(100)

    for institution_name in institution_names:
        try:
            ingest_institution(institution_name)

        except Exception as e:
            print(f"Failed {institution_name}: {e}")

    close_connection()
