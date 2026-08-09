import time

import pytest

from backend.tokens import (
    make_email_verification_token,
    make_password_reset_token,
    read_email_verification_token,
    read_password_reset_token,
)


@pytest.fixture(autouse=True)
def session_secret(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "test-secret-do-not-use-in-production")


class TestEmailVerificationToken:
    def test_round_trips_email_and_password_hash(self):
        token = make_email_verification_token("student@example.com", "hashed-value")
        payload = read_email_verification_token(token)
        assert payload == {"email": "student@example.com", "password_hash": "hashed-value", "name": None}

    def test_round_trips_name_when_given(self):
        token = make_email_verification_token("student@example.com", "hashed-value", name="Jamie Lee")
        payload = read_email_verification_token(token)
        assert payload["name"] == "Jamie Lee"

    def test_rejects_garbage_token(self):
        assert read_email_verification_token("not-a-real-token") is None

    def test_rejects_token_past_max_age(self):
        # -1 rather than 0: itsdangerous's timestamp has one-second
        # resolution, so max_age=0 can still pass within the same second
        # the token was minted -- flaky, not a deterministic expiry check.
        token = make_email_verification_token("student@example.com", "hashed-value")
        assert read_email_verification_token(token, max_age_seconds=-1) is None

    def test_accepts_token_within_max_age(self):
        token = make_email_verification_token("student@example.com", "hashed-value")
        time.sleep(1)
        assert read_email_verification_token(token, max_age_seconds=10) is not None

    def test_rejects_token_signed_with_a_different_secret(self, monkeypatch):
        token = make_email_verification_token("student@example.com", "hashed-value")
        monkeypatch.setenv("SESSION_SECRET", "a-different-secret")
        assert read_email_verification_token(token) is None

    def test_reset_token_is_rejected_by_the_verification_reader(self):
        # Different itsdangerous salts -- a reset token replayed against
        # the verification endpoint must not be accepted as one, even
        # though both payloads are small dicts that could otherwise look
        # alike.
        reset_token = make_password_reset_token(user_id=1)
        assert read_email_verification_token(reset_token) is None


class TestPasswordResetToken:
    def test_round_trips_user_id(self):
        token = make_password_reset_token(user_id=42)
        assert read_password_reset_token(token) == {"user_id": 42}

    def test_rejects_garbage_token(self):
        assert read_password_reset_token("not-a-real-token") is None

    def test_rejects_token_past_max_age(self):
        token = make_password_reset_token(user_id=42)
        assert read_password_reset_token(token, max_age_seconds=-1) is None

    def test_verification_token_is_rejected_by_the_reset_reader(self):
        verify_token = make_email_verification_token("student@example.com", "hashed-value")
        assert read_password_reset_token(verify_token) is None
