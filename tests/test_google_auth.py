import pytest

from backend.google_auth import UnverifiedGoogleEmail, extract_google_identity


class TestExtractGoogleIdentity:
    def test_extracts_identity_from_verified_claims(self):
        identity = extract_google_identity(
            {
                "sub": "1234567890",
                "email": "student@example.com",
                "email_verified": True,
                "name": "Ada Lovelace",
                "picture": "https://example.com/photo.jpg",
            }
        )
        assert identity.sub == "1234567890"
        assert identity.email == "student@example.com"
        assert identity.name == "Ada Lovelace"
        assert identity.avatar_url == "https://example.com/photo.jpg"

    def test_missing_email_verified_claim_raises(self):
        # Absent, not just False -- a malformed or older-style claims dict
        # must not be treated as verified by default. This is the gate
        # that makes it safe to auto-link a Google sign-in to an existing
        # AppUser by email; see CLAUDE.md / docs/ROADMAP.md Phase 5A.
        with pytest.raises(UnverifiedGoogleEmail):
            extract_google_identity({"sub": "1", "email": "x@example.com"})

    def test_email_verified_false_raises(self):
        with pytest.raises(UnverifiedGoogleEmail):
            extract_google_identity(
                {"sub": "1", "email": "x@example.com", "email_verified": False}
            )

    def test_missing_name_and_picture_are_optional(self):
        identity = extract_google_identity(
            {"sub": "1", "email": "x@example.com", "email_verified": True}
        )
        assert identity.name is None
        assert identity.avatar_url is None
