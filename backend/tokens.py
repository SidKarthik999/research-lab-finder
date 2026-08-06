"""Signed, time-limited tokens for email verification and password reset.

Pure aside from reading SESSION_SECRET from the environment -- no database
or network access -- so token construction and parsing are directly
testable. Uses itsdangerous rather than a database-backed pending-signup
row: the token *is* the pending state, so signup doesn't touch the
database at all until the recipient proves they control the inbox by
clicking the link. See backend/auth.py's module docstring for why that
matters for account takeover.

Verification and reset tokens use different itsdangerous salts so a token
of one kind can't be replayed as the other, even though both currently
carry similar-looking payloads.
"""

import os

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

EMAIL_VERIFY_SALT = "email-verify"
PASSWORD_RESET_SALT = "password-reset"

EMAIL_VERIFY_MAX_AGE_SECONDS = 60 * 60 * 24
PASSWORD_RESET_MAX_AGE_SECONDS = 60 * 60


def _serializer():
    return URLSafeTimedSerializer(os.environ["SESSION_SECRET"])


def make_email_verification_token(email, password_hash):
    return _serializer().dumps(
        {"email": email, "password_hash": password_hash}, salt=EMAIL_VERIFY_SALT
    )


def read_email_verification_token(token, max_age_seconds=EMAIL_VERIFY_MAX_AGE_SECONDS):
    try:
        return _serializer().loads(token, salt=EMAIL_VERIFY_SALT, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def make_password_reset_token(user_id):
    return _serializer().dumps({"user_id": user_id}, salt=PASSWORD_RESET_SALT)


def read_password_reset_token(token, max_age_seconds=PASSWORD_RESET_MAX_AGE_SECONDS):
    try:
        return _serializer().loads(token, salt=PASSWORD_RESET_SALT, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
