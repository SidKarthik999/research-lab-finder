import backend.admin
from backend.admin import is_admin_email, is_admin_user


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


# is_admin_user() -- the current_user tuple form used to exempt the operator
# from the per-user LLM daily caps. user[1] is the email.

def _user(email):
    return (1, email, True, "Name", None)


def test_is_admin_user_true_for_the_configured_admin(monkeypatch):
    monkeypatch.setattr(backend.admin, "ADMIN_EMAIL", "owner@example.com")
    assert is_admin_user(_user("Owner@example.com")) is True


def test_is_admin_user_false_for_anyone_else(monkeypatch):
    monkeypatch.setattr(backend.admin, "ADMIN_EMAIL", "owner@example.com")
    assert is_admin_user(_user("student@example.com")) is False


def test_is_admin_user_false_when_admin_email_unset(monkeypatch):
    monkeypatch.setattr(backend.admin, "ADMIN_EMAIL", None)
    assert is_admin_user(_user("owner@example.com")) is False
