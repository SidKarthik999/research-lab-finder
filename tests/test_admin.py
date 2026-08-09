from backend.admin import is_admin_email


def test_is_admin_email_matches_exactly():
    assert is_admin_email("owner@example.com", "owner@example.com") is True


def test_is_admin_email_case_insensitive():
    # Google/ORCID-verified emails aren't guaranteed to come back in
    # whatever casing ADMIN_EMAIL happens to be typed in.
    assert is_admin_email("Owner@Example.com", "owner@example.com") is True


def test_is_admin_email_mismatch_returns_false():
    assert is_admin_email("someone-else@example.com", "owner@example.com") is False


def test_is_admin_email_admin_email_unset_returns_false():
    # ADMIN_EMAIL unset in the environment means nobody is admin, not
    # "everybody is admin" -- absent beats wrong, same principle used
    # everywhere else in this project.
    assert is_admin_email("owner@example.com", None) is False
    assert is_admin_email("owner@example.com", "") is False


def test_is_admin_email_user_email_missing_returns_false():
    assert is_admin_email(None, "owner@example.com") is False
    assert is_admin_email("", "owner@example.com") is False
