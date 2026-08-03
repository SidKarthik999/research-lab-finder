from src.ingestion.emails import pick_best_orcid_email


def test_no_emails_returns_none():
    assert pick_best_orcid_email([]) is None


def test_unverified_email_is_rejected():
    emails = [{"email": "fake@example.com", "verified": False, "primary": True}]
    assert pick_best_orcid_email(emails) is None


def test_verified_primary_email_is_chosen():
    emails = [
        {"email": "secondary@example.edu", "verified": True, "primary": False},
        {"email": "primary@example.edu", "verified": True, "primary": True},
    ]
    assert pick_best_orcid_email(emails) == "primary@example.edu"


def test_falls_back_to_first_verified_when_none_is_primary():
    emails = [
        {"email": "first@example.edu", "verified": True, "primary": False},
        {"email": "second@example.edu", "verified": True, "primary": False},
    ]
    assert pick_best_orcid_email(emails) == "first@example.edu"


def test_ignores_unverified_even_if_primary_and_picks_verified_secondary():
    emails = [
        {"email": "unverified@example.com", "verified": False, "primary": True},
        {"email": "verified@example.edu", "verified": True, "primary": False},
    ]
    assert pick_best_orcid_email(emails) == "verified@example.edu"


def test_all_unverified_returns_none_even_with_multiple_entries():
    emails = [
        {"email": "a@example.com", "verified": False, "primary": True},
        {"email": "b@example.com", "verified": False, "primary": False},
    ]
    assert pick_best_orcid_email(emails) is None
