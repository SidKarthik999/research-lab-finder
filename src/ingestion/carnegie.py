"""Backfills Institution.carnegie_classification from the real Carnegie
Classification of Institutions of Higher Education (ACE / Indiana
University) -- not a heuristic derived from our own works_count data, which
was the other option considered (see CLAUDE.md Phase 3 for why the real
dataset was chosen once it turned out to actually be fetchable and usable).

Run from the repo root: python -m src.ingestion.carnegie

Why this needed real investigation before writing any matching code: there
is no shared ID between our Institution rows (keyed by OpenAlex/ROR id) and
Carnegie's data (keyed by IPEDS UnitID) -- matching has to go by name, city,
and state, and a live test against our actual ~1,768 institutions surfaced
two real problems worth recording here:

1. Plain string-similarity scoring (difflib.SequenceMatcher on the whole
   normalized name) produces confident-looking wrong answers -- e.g. it
   matched "University of Cincinnati" to "ATA College-Cincinnati" at 0.83
   and "Stony Brook School" (an unrelated K-12 school) to "Stony Brook
   University" at 0.76. Scoring on token *sets* (Jaccard over words, so word
   order and repeated generic words like "University"/"College" matter
   less) instead of the raw string was verified against a random 200-row
   sample to be far more reliable, but still isn't perfect -- see the
   threshold discussion below.

2. Carnegie's data turns out to already track institutions at roughly the
   same granularity OpenAlex does -- separate entries per campus for
   multi-campus systems (Rutgers-Newark/New Brunswick/Camden are three rows,
   not one "Rutgers University" row), and separate entries for medical
   schools that are their own accredited institutions (e.g. "Icahn School
   of Medicine at Mount Sinai" has its own Carnegie row, distinct from
   "Mount Sinai Health System" -- which isn't even a Carnegie-classifiable
   educational institution). This means matching each Institution row
   *directly* against Carnegie -- scoped to the same city, not walked up to
   a resolved "parent" institution first -- works better than trying to
   resolve institutional hierarchy first. A city-scoped candidate pool also
   keeps token-Jaccard scoring meaningful (it isn't compared against
   thousands of irrelevant candidates nationwide).

Two-tier matching, verified against that same 200-row sample:
- >=AUTO_ACCEPT_THRESHOLD (0.6) token-Jaccard, same city: auto-accepted.
  Every example at or above this threshold in the sample was correct.
- Below that but still >0 (i.e. there's a real, if weak, shortlist of
  same-city candidates): handed to a bounded LLM pass (see
  ask_llm_to_pick_match) rather than auto-accepted, since this band was a
  genuine mix of correct and wrong matches by score alone (e.g. "University
  of Minnesota" -> "University of Minnesota-Twin Cities" at 0.5 is correct;
  "St. Francis College" -> "ASA College" at 0.25 is not).
- No candidates in that city at all: left NULL. Some of these are real
  Carnegie coverage gaps; others are OpenAlex data artifacts that aren't
  actually degree-granting institutions (a few Institution rows turned out
  to be things like a high school or a professional association that
  OpenAlex tagged type="education") -- either way, absent beats wrong.

The LLM pass is deliberately narrow: given an institution's name/city/state
and the *shortlist* of same-city Carnegie candidates only (never the full
~6,257-row dataset, never asked to invent a match), it picks the single
correct unitid or says none of them are a real match. The response is
validated against the exact shortlist of unitids handed in -- anything else
returned is treated as "no match", not trusted. Same principle as everywhere
else in this project: a wrong classification is worse than a missing one.
"""

import io
import os
import re

import openpyxl
import openai
import requests
from dotenv import load_dotenv

from src.database import (
    close_connection,
    get_institutions_without_carnegie_classification,
    update_institution_carnegie_classification,
)

load_dotenv()

CARNEGIE_DATA_URL = (
    "https://carnegieclassifications.acenet.edu/wp-content/uploads/2023/03/CCIHE2021-PublicData.xlsx"
)

# From the source file's own "Values" sheet (BASIC2021 variable) -- Carnegie's
# current (2021 release) Basic Classification scheme. Hardcoded rather than
# re-parsed from the "Values" sheet every run since it's a fixed, versioned
# taxonomy that only changes on Carnegie's multi-year release cycle, same
# reasoning as any other fixed lookup table in this codebase.
BASIC2021_LABELS = {
    -2: "Not classified",
    1: "Associate's Colleges: High Transfer-High Traditional",
    2: "Associate's Colleges: High Transfer-Mixed Traditional/Nontraditional",
    3: "Associate's Colleges: High Transfer-High Nontraditional",
    4: "Associate's Colleges: Mixed Transfer/Career & Technical-High Traditional",
    5: "Associate's Colleges: Mixed Transfer/Career & Technical-Mixed Traditional/Nontraditional",
    6: "Associate's Colleges: Mixed Transfer/Career & Technical-High Nontraditional",
    7: "Associate's Colleges: High Career & Technical-High Traditional",
    8: "Associate's Colleges: High Career & Technical-Mixed Traditional/Nontraditional",
    9: "Associate's Colleges: High Career & Technical-High Nontraditional",
    10: "Special Focus Two-Year: Health Professions",
    11: "Special Focus Two-Year: Technical Professions",
    12: "Special Focus Two-Year: Arts & Design",
    13: "Special Focus Two-Year: Other Fields",
    14: "Baccalaureate/Associate's Colleges: Associate's Dominant",
    15: "Doctoral Universities: Very High Research Activity",
    16: "Doctoral Universities: High Research Activity",
    17: "Doctoral/Professional Universities",
    18: "Master's Colleges & Universities: Larger Programs",
    19: "Master's Colleges & Universities: Medium Programs",
    20: "Master's Colleges & Universities: Small Programs",
    21: "Baccalaureate Colleges: Arts & Sciences Focus",
    22: "Baccalaureate Colleges: Diverse Fields",
    23: "Baccalaureate/Associate's Colleges: Mixed Baccalaureate/Associate's",
    24: "Special Focus Four-Year: Faith-Related Institutions",
    25: "Special Focus Four-Year: Medical Schools & Centers",
    26: "Special Focus Four-Year: Other Health Professions Schools",
    27: "Special Focus Four-Year: Research Institution",
    28: "Special Focus Four-Year: Engineering and Other Technology-Related Schools",
    29: "Special Focus Four-Year: Business & Management Schools",
    30: "Special Focus Four-Year: Arts, Music & Design Schools",
    31: "Special Focus Four-Year: Law Schools",
    32: "Special Focus Four-Year: Other Special Focus Institutions",
    33: "Tribal Colleges and Universities",
}

AUTO_ACCEPT_THRESHOLD = 0.6
LLM_SHORTLIST_LIMIT = 10
LLM_MODEL = "gpt-5.4-nano"

STOPWORDS = {"the", "of", "at", "a", "an", "and", "in"}


# --- Pure matching logic (no network, no DB -- see tests/test_carnegie.py) ---


def normalize_city(city):
    return re.sub(r"[^a-z0-9]", "", (city or "").lower())


def name_tokens(name):
    name = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower())
    return {token for token in name.split() if token not in STOPWORDS}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build_city_index(carnegie_records):
    """carnegie_records: list of dicts with at least name/city/unitid/basic2021.
    Returns {normalized_city: [record, ...]}."""
    index = {}
    for record in carnegie_records:
        index.setdefault(normalize_city(record["city"]), []).append(record)
    return index


def match_candidates(name, city, city_index):
    """All same-city Carnegie candidates for (name, city), scored by name
    token-Jaccard and sorted best-first. Empty list if the city has no
    Carnegie institutions on file at all."""
    candidates = city_index.get(normalize_city(city), [])
    if not candidates:
        return []

    ntok = name_tokens(name)
    scored = [(record, jaccard(ntok, name_tokens(record["name"]))) for record in candidates]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def best_deterministic_match(name, city, city_index, threshold=AUTO_ACCEPT_THRESHOLD):
    """Returns (record, score) for the top same-city candidate if it clears
    the auto-accept threshold, else None."""
    scored = match_candidates(name, city, city_index)
    if scored and scored[0][1] >= threshold:
        return scored[0]
    return None


def build_llm_match_prompt(name, city, state, shortlist):
    """shortlist: list of (record, score) tuples, already limited to the
    candidates actually worth asking about (see classify_institution)."""
    lines = [f"- {record['unitid']}: {record['name']}" for record, _score in shortlist]
    return (
        f"Institution to classify: {name}\n"
        f"Location: {city or '(unknown city)'}, {state or '(unknown state)'}\n\n"
        "Candidate institutions from the same city in the Carnegie Classification "
        "dataset (id: name):\n"
        f"{chr(10).join(lines)}\n\n"
        "Which candidate, if any, is actually the same real institution as the one "
        "above (accounting for abbreviations, punctuation, or a rename -- not just a "
        "similar-sounding name)? Answer with only that candidate's id number, or the "
        "single word NONE if none of them are actually the same institution."
    )


LLM_SYSTEM_PROMPT = """\
You match a research institution's name to the correct entry, if any, in a \
shortlist of candidates from the official Carnegie Classification of \
Institutions of Higher Education. The shortlist is already filtered to \
institutions in the same city -- your job is picking the right one among \
those, not searching more broadly.

Multiple candidates can look superficially similar (shared words like \
"University", "College", "Medical", or the city name itself) without being \
the same institution -- e.g. "University of Cincinnati" and an unrelated \
for-profit college that also happens to be in Cincinnati. Only match when \
you're confident it's genuinely the same institution, allowing for \
abbreviations, punctuation differences, or an official rename.

Rules:
- Answer with only the candidate's id number, exactly as given, or the \
single word NONE.
- Never invent an id that wasn't in the candidate list.
- If you are not confident any candidate is a real match, answer NONE \
rather than guessing.\
"""


class CarnegieMatchNotConfigured(Exception):
    """OPENAI_API_KEY isn't set."""


def ask_llm_to_pick_match(name, city, state, shortlist):
    """shortlist: list of (record, score) tuples. Returns the matched record,
    or None if the model declined, errored, or returned something outside
    the given shortlist -- that last case is treated as a decline, not
    trusted, since the whole point of this pass is never accepting a
    fabricated answer."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise CarnegieMatchNotConfigured()

    valid_unitids = {str(record["unitid"]) for record, _score in shortlist}
    prompt = build_llm_match_prompt(name, city, state, shortlist)

    client = openai.OpenAI()
    response = client.responses.create(
        model=LLM_MODEL,
        instructions=LLM_SYSTEM_PROMPT,
        input=prompt,
        max_output_tokens=20,
        reasoning={"effort": "none"},
    )

    if response.status == "incomplete" or not response.output_text:
        return None

    answer = response.output_text.strip()
    if answer not in valid_unitids:
        return None

    return next(record for record, _score in shortlist if str(record["unitid"]) == answer)


# --- I/O: fetching the source data and running the backfill ---


def fetch_carnegie_records():
    response = requests.get(CARNEGIE_DATA_URL, timeout=60)
    response.raise_for_status()

    workbook = openpyxl.load_workbook(io.BytesIO(response.content), read_only=True, data_only=True)
    sheet = workbook["Data"]
    rows = sheet.iter_rows(values_only=True)
    header = next(rows)
    column_index = {name: i for i, name in enumerate(header)}

    records = []
    for row in rows:
        name = row[column_index["name"]]
        if not name:
            continue
        basic_code = row[column_index["basic2021"]]
        records.append(
            {
                "unitid": row[column_index["unitid"]],
                "name": name,
                "city": row[column_index["city"]],
                "state": row[column_index["stabbr"]],
                "classification": BASIC2021_LABELS.get(basic_code, "Not classified"),
            }
        )
    return records


def classify_institution(institution_id, name, city, state, city_index, llm_available):
    deterministic = best_deterministic_match(name, city, city_index)
    if deterministic is not None:
        record, _score = deterministic
        update_institution_carnegie_classification(
            institution_id, record["classification"], str(record["unitid"]), "token_match"
        )
        return "matched"

    shortlist = match_candidates(name, city, city_index)[:LLM_SHORTLIST_LIMIT]
    if not shortlist:
        return "no_candidates"

    if not llm_available:
        return "needs_review"

    matched = ask_llm_to_pick_match(name, city, state, shortlist)
    if matched is None:
        return "llm_declined"

    update_institution_carnegie_classification(
        institution_id, matched["classification"], str(matched["unitid"]), "llm"
    )
    return "llm_matched"


def classify_all_institutions():
    print("Fetching Carnegie Classification data...")
    records = fetch_carnegie_records()
    print(f"Loaded {len(records)} Carnegie institution records")
    city_index = build_city_index(records)

    llm_available = bool(os.environ.get("OPENAI_API_KEY"))
    if not llm_available:
        print("OPENAI_API_KEY not set -- skipping the LLM-assisted tier, deterministic matches only")

    institutions = get_institutions_without_carnegie_classification()
    counts = {"matched": 0, "llm_matched": 0, "llm_declined": 0, "no_candidates": 0, "needs_review": 0}

    for institution_id, name, city, state in institutions:
        try:
            outcome = classify_institution(institution_id, name, city, state, city_index, llm_available)
            counts[outcome] += 1
        except Exception as e:
            print(f"Failed {name}: {e}")

    return counts


if __name__ == "__main__":
    counts = classify_all_institutions()
    print(
        f"Deterministic matches: {counts['matched']} | "
        f"LLM matches: {counts['llm_matched']} | "
        f"LLM declined: {counts['llm_declined']} | "
        f"No same-city candidates: {counts['no_candidates']} | "
        f"Needs review (LLM unavailable): {counts['needs_review']}"
    )
    close_connection()
