"""General site contact form -- POST /api/contact in main.py. Distinct from
backend/flags.py's per-professor "Flag an issue" report: a flag always
names one Professor row and is reached from that professor's own detail
page. This is the catch-all for anything that doesn't fit that shape -- a
professor asking to have their listing corrected or removed entirely, or
a general privacy/data question -- and it's the contact path the privacy
policy (frontend/views/legal.js) points at. See docs/ROADMAP.md Phase 6.5.

No account required and nothing is stored in the database -- unlike a
flag (which the admin dashboard lists and lets an admin resolve over
time, see backend/flags.py), a contact message is a one-off that only
needs to reach ADMIN_EMAIL once.
"""


def build_contact_notification_email(name, email, message, app_base_url):
    """Pure email content builder -- same split as
    build_flag_notification_email() and build_resend_payload(), testable
    without a network call or a real ADMIN_EMAIL/RESEND_API_KEY."""
    lines = [
        f"From: {name or '(no name given)'} <{email or 'no reply address given'}>",
        f"Site: {app_base_url}",
        "",
        message,
    ]
    subject = "Research Finder contact form"
    return subject, "\n".join(lines)
