"""Backfill Professor.website from ORCID's researcher-urls -- links
researchers add to their own ORCID record (personal site, lab page, etc.).

Run after enrich_names.py (not required, but that script clears ORCID ids
that don't check out against the attributed institution, so running after
it avoids fetching researcher-urls for a wrong-person ORCID). Reuses the
shared ORCID client in orcid_client.py.

No scraping, no guessing: every URL stored here was entered by the
researcher into their own public ORCID profile. If ORCID has nothing on
file, Professor.website is simply left as-is (absent beats wrong -- see
CLAUDE.md).

Run from the repo root: python -m src.ingestion.researcher_urls
"""

from src.database import (
    close_connection,
    get_professors_with_orcid,
    update_professor_website,
)
from src.ingestion.orcid_client import get_orcid, normalize_orcid

# Not useful as a professor's "website" -- social/networking profiles, not a
# personal or lab site. Matched against the free-text url-name ORCID users
# themselves typed in, so this is a best-effort filter, not exhaustive.
EXCLUDE_KEYWORDS = ("linkedin", "twitter", "x.com", "facebook", "instagram", "youtube", "orcid")

# Prefer a URL whose name signals it's actually a personal/lab/faculty page
# over other candidates (Google Scholar, a publications list, etc.), but
# still fall back to those rather than return nothing.
PREFERRED_KEYWORDS = ("personal", "lab", "home", "faculty", "profile", "website", "webpage", "group")


def get_orcid_researcher_urls(orcid):
    data = get_orcid(f"{normalize_orcid(orcid)}/researcher-urls")
    urls = []
    for entry in data.get("researcher-url", []):
        url = (entry.get("url") or {}).get("value")
        if url:
            urls.append((entry.get("url-name") or "", url))
    return urls


def pick_best_researcher_url(urls):
    """urls: list of (url-name, url) tuples, as returned by
    get_orcid_researcher_urls(). Returns the single best URL to store as
    Professor.website, or None if nothing usable is present.
    """
    candidates = [
        (name, url) for name, url in urls
        if not any(kw in name.lower() for kw in EXCLUDE_KEYWORDS)
    ]
    if not candidates:
        return None

    for name, url in candidates:
        if any(kw in name.lower() for kw in PREFERRED_KEYWORDS):
            return url

    return candidates[0][1]


def enrich_professor_website(professor_id, orcid):
    urls = get_orcid_researcher_urls(orcid)
    website = pick_best_researcher_url(urls)
    if not website:
        return None

    update_professor_website(professor_id, website)
    return website


def enrich_all_professor_websites():
    professors = get_professors_with_orcid()
    updated = 0

    for professor_id, name, orcid, _institution_name, _institution_country in professors:
        try:
            website = enrich_professor_website(professor_id, orcid)
            if website:
                print(f"{name} -> {website}")
                updated += 1
        except Exception as e:
            print(f"Failed {name}: {e}")

    return updated


if __name__ == "__main__":
    updated = enrich_all_professor_websites()
    print(f"Updated {updated} professor website(s)")
    close_connection()
