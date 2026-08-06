"""Google Sign-In.

Split into two layers on purpose: verify_google_id_token() is a
network+crypto operation (fetches Google's signing keys, checks
signature/audience/expiry) and isn't unit tested, the same way this
project's OpenAlex fetch functions aren't. extract_google_identity()
operates on an already-verified claims dict, is pure, and is where a
subtle bug would actually hide -- e.g. trusting an unverified email for
account linking -- so it's the part with test coverage.
"""

import os
from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token


class UnverifiedGoogleEmail(Exception):
    """Google asserted this account's email is not verified."""


class GoogleSignInNotConfigured(Exception):
    """GOOGLE_CLIENT_ID isn't set -- distinct from a bad token so the route
    handler can return a clean "not configured" response instead of a raw
    500 traceback."""


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str | None
    avatar_url: str | None


def extract_google_identity(claims):
    # This flag is what makes it safe to auto-link this sign-in to an
    # existing AppUser by email (see CLAUDE.md / docs/ROADMAP.md Phase 5A
    # on the account-linking rule) -- raise rather than silently treating
    # an unverified email as safe to link.
    if not claims.get("email_verified"):
        raise UnverifiedGoogleEmail(claims.get("email"))
    return GoogleIdentity(
        sub=claims["sub"],
        email=claims["email"],
        name=claims.get("name"),
        avatar_url=claims.get("picture"),
    )


def verify_google_id_token(token):
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    if not client_id:
        raise GoogleSignInNotConfigured()
    claims = google_id_token.verify_oauth2_token(token, google_requests.Request(), client_id)
    return extract_google_identity(claims)
