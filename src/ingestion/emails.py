"""Backfill Professor.email from ORCID's public email field -- an email the
researcher deliberately chose to make public on their ORCID profile, and
that ORCID itself has verified belongs to that address (a confirmation link
sent to it). This is not scraping and not guessing: both the exposure
decision and the correctness check were made by the person themselves or by
ORCID, not by us.

Only ~10% of ORCID holders have a public email at all (checked against a
100-professor sample before building this) -- that's expected, not a bug.
Most people leave it private. Unverified entries are skipped outright:
ORCID lets a person type any email into their profile, but only a verified
one has actually been confirmed to work and belong to them -- an unverified
entry carries the same "might be wrong" risk this project avoids elsewhere
(see clear_professor_orcid in enrich_names.py). Absent beats wrong.

Run from the repo root: python -m src.ingestion.emails
"""

from src.database import (
    close_connection,
    get_professors_with_orcid,
    update_professor_email,
)
from src.ingestion.orcid_client import get_orcid, normalize_orcid


def get_orcid_emails(orcid):
    data = get_orcid(f"{normalize_orcid(orcid)}/person")
    return (data.get("emails") or {}).get("email") or []


def pick_best_orcid_email(emails):
    """emails: list of ORCID email dicts (email/verified/primary). Returns
    the best address to store as Professor.email, or None if nothing is
    both public (already true of anything the public API returns) and
    verified.
    """
    verified = [e for e in emails if e.get("verified") and e.get("email")]
    if not verified:
        return None

    for entry in verified:
        if entry.get("primary"):
            return entry["email"]

    return verified[0]["email"]


def enrich_professor_email(professor_id, orcid):
    emails = get_orcid_emails(orcid)
    email = pick_best_orcid_email(emails)
    if not email:
        return None

    update_professor_email(professor_id, email)
    return email


def enrich_all_professor_emails():
    professors = get_professors_with_orcid()
    updated = 0

    for professor_id, name, orcid, _institution_name, _institution_country in professors:
        try:
            email = enrich_professor_email(professor_id, orcid)
            if email:
                print(f"{name} -> {email}")
                updated += 1
        except Exception as e:
            print(f"Failed {name}: {e}")

    return updated


if __name__ == "__main__":
    updated = enrich_all_professor_emails()
    print(f"Updated {updated} professor email(s)")
    close_connection()
