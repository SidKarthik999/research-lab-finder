import re
import time
import requests
from src.database import get_all_professors, insert_professor, update_lab_contact, close_connection

ORCID_API_BASE = "https://pub.orcid.org/v3.0"
USER_AGENT = "researchlabfinder-bot (contact: sanjanakarthik789@gmail.com)"

WEBSITE_KEYWORDS = ("lab", "website", "homepage", "personal")

MAILTO_PATTERN = re.compile(r'mailto:([^"\'?\s]+)', re.IGNORECASE)
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
META_DESCRIPTION_PATTERN = re.compile(
    r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']', re.IGNORECASE
)
TITLE_PATTERN = re.compile(r'<title[^>]*>([^<]+)</title>', re.IGNORECASE)


def normalize_orcid(orcid):
    return orcid.rstrip("/").rsplit("/", 1)[-1]


def get_orcid_researcher_urls(orcid):
    response = requests.get(
        f"{ORCID_API_BASE}/{normalize_orcid(orcid)}/researcher-urls",
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    urls = []
    for entry in data.get("researcher-url", []):
        name = (entry.get("url-name") or "")
        url = (entry.get("url") or {}).get("value")
        if url:
            urls.append({"name": name, "url": url})
    return urls


def normalize_url(url):
    if not re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*://', url):
        return f"https://{url}"
    return url


def pick_candidate_website(urls):
    if not urls:
        return None
    for entry in urls:
        if any(keyword in entry["name"].lower() for keyword in WEBSITE_KEYWORDS):
            return normalize_url(entry["url"])
    return normalize_url(urls[0]["url"])


def scrape_contact_page(url):
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=10)
    response.raise_for_status()
    html = response.text

    email_match = MAILTO_PATTERN.search(html) or EMAIL_PATTERN.search(html)
    email = email_match.group(1) if email_match and email_match.lastindex else (
        email_match.group(0) if email_match else None
    )

    description_match = META_DESCRIPTION_PATTERN.search(html)
    description = description_match.group(1)[:500] if description_match else None

    title_match = TITLE_PATTERN.search(html)
    title = re.sub(r'\s+', ' ', title_match.group(1)).strip()[:255] if title_match else None

    return {"email": email, "description": description, "title": title}


def enrich_professor(professor_id, name, orcid, openalex_id):
    urls = get_orcid_researcher_urls(orcid)
    website = pick_candidate_website(urls)
    if not website:
        return None

    contact = scrape_contact_page(website)

    insert_professor(
        name=name,
        email=contact.get("email"),
        website=website,
        openalex_id=openalex_id,
        source="OpenAlex-derived",
    )

    update_lab_contact(
        pi_professor_id=professor_id,
        name=contact.get("title"),
        website=website,
        description=contact.get("description"),
    )

    return website


def enrich_all_professors():
    professors = get_all_professors()
    enriched = 0
    for professor in professors:
        professor_id, name, email, orcid, website, source, created_at, updated_at, openalex_id = professor
        if not orcid:
            continue

        try:
            result = enrich_professor(professor_id, name, orcid, openalex_id)
            print(f"Enriched {name}: {result}")
            if result:
                enriched += 1

        except Exception as e:
            print(f"Failed {name}: {e}")

        time.sleep(0.75)

    return enriched


if __name__ == "__main__":
    enrich_all_professors()
    close_connection()
