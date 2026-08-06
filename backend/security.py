"""Password hashing (argon2id), kept separate from route handlers so it's
testable without a request or database connection.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password):
    return _hasher.hash(password)


def verify_password(password, password_hash):
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
