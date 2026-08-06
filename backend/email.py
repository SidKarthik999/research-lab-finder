"""send_email() seam: the dev backend prints to the console, so signup
verification and password reset work end-to-end without picking a
transactional email provider. Production sets EMAIL_BACKEND to swap one
in; nothing else in the codebase needs to know which is active. This is
the one decision Phase 5A's plan deliberately left open -- see
docs/ROADMAP.md Phase 6.2.
"""

import os


def send_email(to, subject, body):
    backend = os.environ.get("EMAIL_BACKEND", "console")
    if backend == "console":
        _send_console(to, subject, body)
    else:
        raise NotImplementedError(
            f"EMAIL_BACKEND={backend!r} isn't implemented yet -- see "
            "docs/ROADMAP.md Phase 6.2 for the production email provider choice."
        )


def _send_console(to, subject, body):
    print(f"\n--- email to {to} ---\nSubject: {subject}\n\n{body}\n--- end email ---\n")
