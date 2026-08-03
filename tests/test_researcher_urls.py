from src.ingestion.researcher_urls import pick_best_researcher_url


def test_no_urls_returns_none():
    assert pick_best_researcher_url([]) is None


def test_only_social_media_returns_none():
    urls = [("Linkedin", "https://linkedin.com/in/someone"), ("Twitter", "https://twitter.com/someone")]
    assert pick_best_researcher_url(urls) is None


def test_prefers_personal_website_over_social_media():
    urls = [
        ("Linkedin", "https://linkedin.com/in/someone"),
        ("Personal website", "https://someone.edu"),
    ]
    assert pick_best_researcher_url(urls) == "https://someone.edu"


def test_prefers_lab_page_over_google_scholar():
    urls = [
        ("Google Scholar", "https://scholar.google.com/citations?user=abc"),
        ("Lab website", "https://smithlab.university.edu"),
    ]
    assert pick_best_researcher_url(urls) == "https://smithlab.university.edu"


def test_falls_back_to_first_non_excluded_when_nothing_preferred():
    urls = [
        ("Google Scholar", "https://scholar.google.com/citations?user=abc"),
        ("List of publications", "https://example.org/pubs"),
    ]
    assert pick_best_researcher_url(urls) == "https://scholar.google.com/citations?user=abc"


def test_untitled_url_still_usable_as_fallback():
    # Real ORCID data: url-name is sometimes blank even though the URL is a
    # legitimate lab group site.
    urls = [("", "https://gmwgroup.harvard.edu/")]
    assert pick_best_researcher_url(urls) == "https://gmwgroup.harvard.edu/"


def test_faculty_link_counts_as_preferred():
    urls = [
        ("Twitter", "https://twitter.com/someone"),
        ("Harvard faculty link", "https://hsph.harvard.edu/profile/someone"),
    ]
    assert pick_best_researcher_url(urls) == "https://hsph.harvard.edu/profile/someone"


def test_keyword_matching_is_case_insensitive():
    urls = [("PERSONAL WEBSITE", "https://someone.edu")]
    assert pick_best_researcher_url(urls) == "https://someone.edu"
