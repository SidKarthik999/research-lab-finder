"""Admin access gate for the flag/metrics dashboard (GET /api/admin/flags,
GET /api/admin/metrics in backend/main.py).

Reuses ADMIN_EMAIL (already set in production to receive flag notification
emails -- see backend/flags.py) as the single admin identity, rather than
adding a roles/permissions table: this app has exactly one operator, so a
real roles system would be solving a problem that doesn't exist yet. If a
second admin is ever needed, this is the one place that assumption lives.

is_admin_email() takes both emails as arguments rather than reading
ADMIN_EMAIL from the environment itself, so it's a pure function testable
without monkeypatching os.environ -- same "split for testability" pattern as
build_search_query()/build_flag_notification_email().
"""

import os

from fastapi import Depends, HTTPException

from backend.sessions import current_user

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")


def is_admin_email(user_email, admin_email):
    # Case-insensitive: Google/ORCID-verified emails aren't guaranteed to
    # come back in whatever casing ADMIN_EMAIL happens to be typed in.
    if not admin_email or not user_email:
        return False
    return user_email.strip().lower() == admin_email.strip().lower()


def require_admin(user=Depends(current_user)):
    if not is_admin_email(user[1], ADMIN_EMAIL):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
