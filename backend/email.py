"""send_email() seam: the dev backend prints to the console, so signup
verification and password reset work end-to-end without picking a
transactional email provider. Production sets EMAIL_BACKEND to swap one
in; nothing else in the codebase needs to know which is active. This was
the one decision Phase 5A's plan deliberately left open -- resolved
2026-08-08 (see docs/ROADMAP.md Phase 6.2) in favor of Resend: its free
tier (3,000 emails/month) is permanent rather than a time-limited trial
like SendGrid's, and its plain REST API needs nothing beyond the
`requests` library already pulled in for backend/google_auth.py.
"""

import os

import requests

RESEND_API_URL = "https://api.resend.com/emails"


def send_email(to, subject, body):
    backend = os.environ.get("EMAIL_BACKEND", "console")
    if backend == "console":
        _send_console(to, subject, body)
    elif backend == "resend":
        _send_resend(to, subject, body)
    else:
        raise NotImplementedError(
            f"EMAIL_BACKEND={backend!r} isn't implemented yet -- see "
            "docs/ROADMAP.md Phase 6.2 for the production email provider choice."
        )


def _send_console(to, subject, body):
    print(f"\n--- email to {to} ---\nSubject: {subject}\n\n{body}\n--- end email ---\n")


def build_resend_payload(to, subject, body, from_address):
    """Pure request-body builder, kept apart from the actual HTTP call so it's
    testable without a network connection or a real API key -- same
    "split for testability" pattern as build_search_query() in
    backend/main.py. Resend's API takes `to` as a list even for a single
    recipient."""
    return {
        "from": from_address,
        "to": [to],
        "subject": subject,
        "text": body,
    }


def _send_resend(to, subject, body):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise RuntimeError("EMAIL_BACKEND=resend but RESEND_API_KEY is unset")

    # research-finder.com is verified in Resend (SPF/DKIM published), so the
    # default is a real address on it rather than Resend's shared
    # onboarding@resend.dev domain -- that shared domain was only ever meant
    # for testing and a real signup's verification email sent from it can be
    # spam-filtered. Production still sets EMAIL_FROM explicitly (render.yaml);
    # this default just keeps the fallback safe if that env var goes missing.
    from_address = os.environ.get("EMAIL_FROM", "Research Finder <noreply@research-finder.com>")

    response = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json=build_resend_payload(to, subject, body, from_address),
        timeout=10,
    )
    response.raise_for_status()
