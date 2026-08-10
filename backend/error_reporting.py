"""Sentry error reporting (Phase 6.6, see docs/ROADMAP.md) -- captures
unhandled exceptions in production so they surface as an alert instead of
requiring someone to go read Render's logs. Entirely optional: init_sentry()
no-ops when SENTRY_DSN isn't set, the same "optional feature degrades
gracefully" pattern as OPENAI_API_KEY/RESEND_API_KEY elsewhere in this app
-- local dev and tests never talk to Sentry.

send_default_pii stays at the SDK's own default (False) rather than being
turned on -- this app handles real personal data (student profile text,
resume uploads, session cookies), and an error report is the last place
that should end up. scrub_event() is a second layer on top of that
default, not a replacement for it: it strips any Authorization/Cookie
header that made it into an event's request context regardless of
send_default_pii, so the guarantee doesn't depend on that flag never
getting flipped on by accident later.
"""

import os

SENTRY_DSN = os.environ.get("SENTRY_DSN")

_SENSITIVE_HEADERS = {"authorization", "cookie", "set-cookie"}


def scrub_event(event, hint):
    """Pure event transform, passed as Sentry's before_send hook -- testable
    without a network call or a real DSN, same "split for testability"
    pattern as build_search_query()/build_flag_notification_email().
    Mutates and returns `event`; returning None would drop the event
    entirely, which isn't what a header scrub should do."""
    headers = event.get("request", {}).get("headers")
    if headers:
        event["request"]["headers"] = {
            key: ("[Filtered]" if key.lower() in _SENSITIVE_HEADERS else value) for key, value in headers.items()
        }
    return event


def init_sentry():
    if not SENTRY_DSN:
        return

    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        # No performance tracing -- this is error capture only, and a 0
        # sample rate keeps this comfortably inside Sentry's free tier
        # regardless of traffic.
        traces_sample_rate=0,
        send_default_pii=False,
        before_send=scrub_event,
    )
