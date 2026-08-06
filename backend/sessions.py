"""Session helpers built on Starlette's cookie-based SessionMiddleware
(added in main.py). request.session is a signed, HTTP-only cookie dict --
no server-side session store, consistent with this project's
no-extra-infra-unless-needed approach. Good enough for now; see
docs/ROADMAP.md Phase 6 for when this would need to become a real store
(e.g. to support "log out everywhere").
"""

from fastapi import HTTPException, Request

from src import database as db


def log_in(request, user_id):
    request.session["user_id"] = user_id


def log_out(request):
    request.session.clear()


def current_user(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not signed in")
    user = db.get_user_by_id(user_id)
    if user is None:
        # The session cookie outlived the account it pointed to -- clear it
        # rather than leaving a dangling reference in place.
        request.session.clear()
        raise HTTPException(status_code=401, detail="Not signed in")
    return user


def optional_current_user(request: Request):
    user_id = request.session.get("user_id")
    if user_id is None:
        return None
    return db.get_user_by_id(user_id)
