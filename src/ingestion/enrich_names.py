"""Verify ORCID links against the attributed institution, and backfill
Professor.name from ORCID's own record where the link checks out.

Two separate problems showed up in testing:

1. A professor's stored ORCID id can belong to a *different* real person who
   happens to share a name -- e.g. an "Alex Jen" attributed to University of
   Washington whose ORCID id actually belongs to an Alex Jen at City
   University of Hong Kong. This is an upstream OpenAlex author-disambiguation
   error, not something ingestion can prevent, but it's verifiable: ORCID's
   own employment history says where that ORCID's person actually works. If
   it never overlaps with the institution we attributed, the ORCID is wrong
   and gets cleared -- a wrong link is worse than no link, since it points a
   user at a stranger's profile.

2. For professors whose ORCID *does* check out, ORCID's given-names /
   family-name / credit-name fields are a more reliable "full name" source
   than OpenAlex's display_name_alternatives (which, for common surnames, is
   often a disambiguation cluster of unrelated people -- see
   prefer_full_name() in src/ingestion/openalex.py). E.g. "A. M. Litke" ->
   "Alan M. Litke": OpenAlex had no matching alternative for this person at
   all, but ORCID knows the "A." is "Alan".

Run from the repo root: python -m src.ingestion.enrich_names
"""

import os
import re
import threading
import time

import requests
from dotenv import load_dotenv

from src.database import (
    clear_professor_orcid,
    close_connection,
    get_professors_with_orcid,
    update_professor_name,
)
from src.ingestion.openalex import INITIAL_TOKEN

load_dotenv()

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
ORCID_TOKEN_URL = "https://orcid.org/oauth/token"
ORCID_CLIENT_ID = os.getenv("ORCID_CLIENT_ID")
ORCID_CLIENT_SECRET = os.getenv("ORCID_CLIENT_SECRET")
USER_AGENT = "researchlabfinder-bot (contact: sanjanakarthik789@gmail.com)"

_orcid_token_lock = threading.Lock()
_orcid_token = [None]

def _get_orcid_token():
    if not ORCID_CLIENT_ID or not ORCID_CLIENT_SECRET:
        return None

    with _orcid_token_lock:
        if _orcid_token[0] is None:
            response = requests.post(
                ORCID_TOKEN_URL,
                headers={"Accept": "application/json"},
                data={
                    "client_id": ORCID_CLIENT_ID,
                    "client_secret": ORCID_CLIENT_SECRET,
                    "grant_type": "client_credentials",
                    "scope": "/read-public",
                },
                timeout=10,
            )
            response.raise_for_status()
            _orcid_token[0] = response.json()["access_token"]
        return _orcid_token[0]

ORCID_MIN_INTERVAL = 0.1 if (ORCID_CLIENT_ID and ORCID_CLIENT_SECRET) else 1.0
ORCID_MAX_RETRIES = 3
_orcid_lock = threading.Lock()
_orcid_next_allowed_at = [0.0]

def _throttle_orcid():
    with _orcid_lock:
        now = time.monotonic()
        wait_seconds = _orcid_next_allowed_at[0] - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
            now = time.monotonic()
        _orcid_next_allowed_at[0] = now + ORCID_MIN_INTERVAL


def normalize_orcid(orcid):
    return orcid.rstrip("/").rsplit("/", 1)[-1]


def _get_orcid(path):
    url = f"{ORCID_API_BASE}/{path}"
    headers = {"Accept": "application/json", "User-Agent": USER_AGENT}

    token = _get_orcid_token()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    for attempt in range(ORCID_MAX_RETRIES):
        _throttle_orcid()
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 10 * (attempt + 1)
            time.sleep(wait_seconds)
            continue

        response.raise_for_status()
        return response.json()

    response.raise_for_status()


def get_orcid_name(orcid):
    data = _get_orcid(f"{normalize_orcid(orcid)}/person")
    name = data.get("name") or {}
    given = (name.get("given-names") or {}).get("value")
    family = (name.get("family-name") or {}).get("value")
    credit = (name.get("credit-name") or {}).get("value")
    return best_orcid_name(given, family, credit)


def get_orcid_employers(orcid):
    """(organization name, country code) for every employment ORCID has on
    file for this id (current and past), for cross-checking against our own
    attribution.
    """
    data = _get_orcid(f"{normalize_orcid(orcid)}/employments")
    employers = []
    for group in data.get("affiliation-group", []):
        for summary in group.get("summaries", []):
            org = (summary.get("employment-summary") or {}).get("organization") or {}
            if org.get("name"):
                country = (org.get("address") or {}).get("country")
                employers.append((org["name"], country))
    return employers


# Generic academic-institution words that don't help distinguish one
# institution from another.
INSTITUTION_STOPWORDS = {
    "university", "college", "institute", "institution", "school",
    "of", "the", "at", "and", "state", "system", "technology",
}


def distinctive_words(name):
    words = re.findall(r"[a-z]+", name.lower())
    return {w for w in words if w not in INSTITUTION_STOPWORDS}


def orcid_institution_matches(orcid, institution_name, institution_country):
    """True if ORCID's employment history is consistent with the institution
    we attributed this professor to; None if ORCID has no employment history
    to check against (can't confirm or refute); False if ORCID lists
    employer(s) and none of them are consistent -- i.e. the ORCID likely
    belongs to a different person than the one OpenAlex attributed it to.

    Deliberately checks *country*, not institution-name text: a professor's
    real ORCID employer is very often a differently-named but
    same-country/region affiliate of their university (e.g. Aaron Roodman's
    ORCID employer is "SLAC National Accelerator Laboratory", not "Stanford
    University" -- SLAC is a Stanford-operated national lab). Country-level
    mismatches (e.g. a Seattle-attributed professor whose only ORCID
    employer is in Hong Kong) are a much stronger and rarer signal of an
    actual wrong-person link than institution-name text ever is.
    """
    employers = get_orcid_employers(orcid)
    if not employers:
        return None

    target_words = distinctive_words(institution_name)
    target_country = (institution_country or "").upper()

    for employer_name, employer_country in employers:
        if distinctive_words(employer_name) & target_words:
            return True
        if target_country and (employer_country or "").upper() == target_country:
            return True

    return False


def best_orcid_name(given, family, credit):
    if not family:
        return None  # can't verify a name without at least a surname

    # credit-name is the person's own preferred display form, but only trust
    # it if it actually contains their surname -- guards against a stale or
    # malformed credit-name field.
    if credit and family.lower() in credit.lower():
        return credit

    if given:
        return f"{given} {family}"

    return None


# Name particles that are conventionally lowercase even in a well-formed name.
LOWERCASE_PARTICLES = {"de", "der", "van", "von", "la", "le", "du", "da", "dos", "das", "di", "el", "al"}


def normalize_casing(name):
    """ORCID's given-names/family-name fields are free text some people type
    in ALL CAPS or all lowercase (e.g. "ANNA" / "GOUSSIOU") -- that's still a
    correct, useful name, just badly formatted. Title-case any token that's
    uniformly one case rather than discarding the whole candidate over it.
    """
    normalized = []
    for token in name.split():
        if token.lower() in LOWERCASE_PARTICLES:
            normalized.append(token.lower())
            continue
        core = token.strip(".,'-‐‑")
        if core and len(core) > 1 and (core.isupper() or core.islower()):
            normalized.append(token.title())
        else:
            normalized.append(token)
    return " ".join(normalized)


def is_safe_replacement(current_name, candidate_name):
    """Guard against replacing a good name with a worse one.

    Some ORCID records list only an initial where OpenAlex already had the
    full given name -- that would be a regression, so never trade a fuller
    name for one with more bare-initial tokens. (Wrong-person ORCID links are
    caught separately by orcid_institution_matches(), before this is even
    called. Casing is handled separately by normalize_casing().)
    """
    current_tokens = current_name.split()
    candidate_tokens = candidate_name.split()
    if not current_tokens or not candidate_tokens:
        return False

    if current_tokens[-1].lower() != candidate_tokens[-1].lower():
        return False

    if current_tokens[0][:1].lower() != candidate_tokens[0][:1].lower():
        return False

    current_initials = sum(1 for t in current_tokens if INITIAL_TOKEN.match(t))
    candidate_initials = sum(1 for t in candidate_tokens if INITIAL_TOKEN.match(t))
    if candidate_initials > current_initials:
        return False

    return True


def enrich_professor_name(professor_id, current_name, orcid):
    raw_name = get_orcid_name(orcid)
    if not raw_name:
        return None

    name = normalize_casing(raw_name)
    if name == current_name or not is_safe_replacement(current_name, name):
        return None

    update_professor_name(professor_id, name)
    return name


def enrich_all_professor_names():
    professors = get_professors_with_orcid()
    updated = 0
    cleared = 0

    for professor_id, current_name, orcid, institution_name, institution_country in professors:
        try:
            match = orcid_institution_matches(orcid, institution_name, institution_country)
            if match is False:
                clear_professor_orcid(professor_id)
                print(f"Cleared mismatched ORCID for {current_name} ({institution_name})")
                cleared += 1
                continue

            new_name = enrich_professor_name(professor_id, current_name, orcid)
            if new_name:
                print(f"{current_name} -> {new_name}")
                updated += 1
        except Exception as e:
            print(f"Failed {current_name}: {e}")

    return updated, cleared


if __name__ == "__main__":
    updated, cleared = enrich_all_professor_names()
    print(f"Updated {updated} professor name(s), cleared {cleared} mismatched ORCID(s)")
    close_connection()
