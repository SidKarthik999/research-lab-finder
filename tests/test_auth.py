"""Route-level test for the rate-limit wiring in backend/auth.py.

Scoped to /api/auth/signup specifically: it's the one auth route with no
@db.with_connection (a fresh signup never touches AppUser/AuthIdentity
until the verification link is redeemed -- see the module docstring), so
it's the only one testable end-to-end here without a real database
connection. login/forgot's rate limiting reuses the exact same
_enforce_rate_limit() helper, covered directly in tests/test_rate_limit.py.
"""

from fastapi.testclient import TestClient

from backend.auth import SIGNUP_EMAIL_LIMIT
from backend.main import app

client = TestClient(app)


def _signup(email):
    return client.post(
        "/api/auth/signup",
        json={"email": email, "password": "at-least-8-chars", "name": "Test Student"},
    )


def test_signup_succeeds_up_to_the_email_limit():
    limit, _window = SIGNUP_EMAIL_LIMIT
    email = "ratelimit-under@example.com"
    for _ in range(limit):
        response = _signup(email)
        assert response.status_code == 200


def test_signup_refuses_past_the_email_limit():
    limit, _window = SIGNUP_EMAIL_LIMIT
    email = "ratelimit-over@example.com"
    for _ in range(limit):
        _signup(email)
    response = _signup(email)
    assert response.status_code == 429


def test_signup_rate_limit_is_scoped_per_email():
    limit, _window = SIGNUP_EMAIL_LIMIT
    for _ in range(limit):
        _signup("ratelimit-scoped-a@example.com")
    # A different email must not be blocked by another address's attempts.
    response = _signup("ratelimit-scoped-b@example.com")
    assert response.status_code == 200
