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

import re

from src.database import (
    clear_professor_orcid,
    close_connection,
    get_professors_with_orcid,
    mark_professor_name_checked,
    update_professor_name,
)
from src.ingestion.openalex import INITIAL_TOKEN
from src.ingestion.orcid_client import get_orcid as _get_orcid
from src.ingestion.orcid_client import normalize_orcid


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
            else:
                new_name = enrich_professor_name(professor_id, current_name, orcid)
                if new_name:
                    print(f"{current_name} -> {new_name}")
                    updated += 1

            mark_professor_name_checked(professor_id)
        except Exception as e:
            print(f"Failed {current_name}: {e}")

    return updated, cleared


if __name__ == "__main__":
    updated, cleared = enrich_all_professor_names()
    print(f"Updated {updated} professor name(s), cleared {cleared} mismatched ORCID(s)")
    close_connection()
