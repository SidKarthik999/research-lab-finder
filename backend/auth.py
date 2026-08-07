"""Authentication routes: Google sign-in and email/password (signup,
login, email verification, password reset), plus the session-derived
/api/me. Mounted in main.py.

Multi-provider from the start -- AppUser is the account, AuthIdentity is
one row per login method -- see CLAUDE.md / docs/ROADMAP.md Phase 5A for
why, and for the account-linking rule this file implements: a new
identity only auto-links to an existing AppUser when the *incoming*
assertion of that email is provider-verified. Auto-linking on an
unverified email is a known account-takeover path.

The signup flow follows the same rule from the other direction: the
hashed password lives only in a signed token (backend/tokens.py) until
whoever clicks the verification link proves they control that inbox, so
a signup request can't touch -- and can't take over -- an account that
already exists under that email.
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from backend.email import send_email
from backend.google_auth import GoogleSignInNotConfigured, UnverifiedGoogleEmail, verify_google_id_token
from backend.security import hash_password, verify_password
from backend.sessions import current_user, log_in, log_out
from backend.tokens import (
    make_email_verification_token,
    make_password_reset_token,
    read_email_verification_token,
    read_password_reset_token,
)
from src import database as db

router = APIRouter()

GENERIC_AUTH_ERROR = "Invalid email or password."
# Identical response whether or not the email is already registered --
# distinguishing them would let a caller enumerate which of a list of
# addresses have accounts here.
GENERIC_CHECK_EMAIL = "If that email can receive mail, check it for a link."


class GoogleSignInRequest(BaseModel):
    id_token: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class VerifyEmailRequest(BaseModel):
    token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


def _user_public(user):
    user_id, email, email_verified, name, avatar_url = user
    return {
        "id": user_id,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "avatar_url": avatar_url,
    }


@router.get("/api/auth/google/client-id")
def google_client_id():
    # Public value -- Google client IDs are meant to be embedded in
    # frontend JS. Returned as null (not a 503) when unset, so the sign-in
    # view can render its own "not configured" state instead of treating a
    # config gap as a request failure.
    return {"client_id": os.environ.get("GOOGLE_CLIENT_ID")}


@router.post("/api/auth/google")
def google_sign_in(body: GoogleSignInRequest, request: Request):
    try:
        identity = verify_google_id_token(body.id_token)
    except GoogleSignInNotConfigured:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured yet.")
    except UnverifiedGoogleEmail:
        raise HTTPException(status_code=400, detail="Google account email is not verified.")
    except ValueError:
        # google-auth raises plain ValueError for a malformed, expired, or
        # wrong-audience token.
        raise HTTPException(status_code=401, detail="Invalid Google sign-in token.")

    existing = db.get_auth_identity("google", identity.sub)
    if existing is not None:
        user_id = existing[1]
    else:
        # First time this Google account has signed in here. identity's
        # email is provider-verified (extract_google_identity already
        # enforced that), so it's safe to link to -- or create -- the
        # AppUser with this email. insert_user only ever upgrades
        # email_verified, never downgrades it.
        user_id = db.insert_user(
            identity.email,
            name=identity.name,
            avatar_url=identity.avatar_url,
            email_verified=True,
        )
        db.insert_auth_identity(user_id, "google", identity.sub)

    log_in(request, user_id)
    return _user_public(db.get_user_by_id(user_id))


@router.post("/api/auth/signup")
def signup(body: SignupRequest):
    password_hash = hash_password(body.password)
    token = make_email_verification_token(body.email, password_hash)
    verify_url = f"/#/verify-email?token={token}"
    send_email(
        body.email,
        "Verify your Research Lab Finder account",
        "Click to verify your email and finish creating your account:\n"
        f"{verify_url}\n\nIf you didn't request this, you can ignore this email.",
    )
    return {"message": GENERIC_CHECK_EMAIL}


@router.post("/api/auth/verify-email")
def verify_email(body: VerifyEmailRequest, request: Request):
    payload = read_email_verification_token(body.token)
    if payload is None:
        raise HTTPException(status_code=400, detail="That verification link is invalid or has expired.")

    user_id = db.insert_user(payload["email"], email_verified=True)
    # A stale or repeated click of the same link re-runs both upserts
    # harmlessly, but must not overwrite a password set since the link was
    # issued (e.g. by a later reset) -- insert_auth_identity's ON CONFLICT
    # branch only touches updated_at, never password_hash.
    db.insert_auth_identity(user_id, "password", payload["email"], password_hash=payload["password_hash"])
    log_in(request, user_id)
    return _user_public(db.get_user_by_id(user_id))


@router.post("/api/auth/login")
def login(body: LoginRequest, request: Request):
    identity = db.get_auth_identity("password", body.email)
    if identity is None or identity[4] is None or not verify_password(body.password, identity[4]):
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)

    user_id = identity[1]
    log_in(request, user_id)
    return _user_public(db.get_user_by_id(user_id))


@router.post("/api/auth/forgot")
def forgot_password(body: ForgotPasswordRequest):
    user = db.get_user_by_email(body.email)
    if user is not None:
        token = make_password_reset_token(user[0])
        reset_url = f"/#/reset-password?token={token}"
        send_email(
            body.email,
            "Reset your Research Lab Finder password",
            f"Click to set a new password:\n{reset_url}\n\n"
            "If you didn't request this, you can ignore this email.",
        )
    return {"message": GENERIC_CHECK_EMAIL}


@router.post("/api/auth/reset")
def reset_password(body: ResetPasswordRequest, request: Request):
    payload = read_password_reset_token(body.token)
    if payload is None:
        raise HTTPException(status_code=400, detail="That reset link is invalid or has expired.")

    user = db.get_user_by_id(payload["user_id"])
    if user is None:
        raise HTTPException(status_code=400, detail="That reset link is invalid or has expired.")

    email = user[1]
    password_hash = hash_password(body.password)
    identity = db.get_auth_identity("password", email)
    if identity is None:
        # First password this account has ever had (e.g. it started as
        # Google-only) -- a fresh insert is allowed to carry the hash
        # directly; only the ON CONFLICT branch is forbidden from writing
        # password_hash.
        db.insert_auth_identity(user[0], "password", email, password_hash=password_hash)
    else:
        db.update_identity_password(identity[0], password_hash)

    log_in(request, user[0])
    return _user_public(user)


@router.post("/api/auth/logout")
def logout(request: Request):
    log_out(request)
    return {"message": "Signed out."}


@router.get("/api/me")
def me(user=Depends(current_user)):
    return _user_public(user)


class StudentProfileRequest(BaseModel):
    level: str | None = None
    school: str | None = None
    graduation_year: int | None = None
    coursework: str | None = None
    skills: str | None = None
    prior_experience: str | None = None
    looking_for: str | None = None


def _profile_public(row):
    if row is None:
        return {}
    _user_id, level, school, graduation_year, coursework, skills, prior_experience, looking_for = row
    return {
        "level": level,
        "school": school,
        "graduation_year": graduation_year,
        "coursework": coursework,
        "skills": skills,
        "prior_experience": prior_experience,
        "looking_for": looking_for,
    }


@router.get("/api/me/profile")
def get_profile(user=Depends(current_user)):
    return _profile_public(db.get_student_profile(user[0]))


@router.put("/api/me/profile")
def update_profile(body: StudentProfileRequest, user=Depends(current_user)):
    user_id = user[0]
    # Full replace (EXCLUDED, not COALESCE) inside upsert_student_profile --
    # this is the student directly editing their own form, so leaving a
    # field blank must actually clear it. See CLAUDE.md Phase 5A.
    db.upsert_student_profile(
        user_id,
        level=body.level,
        school=body.school,
        graduation_year=body.graduation_year,
        coursework=body.coursework,
        skills=body.skills,
        prior_experience=body.prior_experience,
        looking_for=body.looking_for,
    )
    return _profile_public(db.get_student_profile(user_id))
