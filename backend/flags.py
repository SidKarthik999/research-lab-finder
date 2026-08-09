"""Professor issue-flagging: lets any visitor report a data-quality problem
(wrong person, dead link, ...) on a professor's page without needing an
account -- ingestion is automated (OpenAlex + ORCID enrichment, see
CLAUDE.md), so mistakes are expected, and there was previously no way to
report one short of emailing the site owner directly.

FLAG_REASONS is served via GET /api/flag-reasons (same "fetched, not
hardcoded" pattern as INSTITUTION_TYPES in backend/institution_types.py and
METRO_AREA_LABELS in backend/metro_areas.py) so the frontend checkboxes can
never drift out of sync with what the backend actually records.
"""

FLAG_REASONS = {
    "wrong_person": "This doesn't look like the right person",
    "wrong_institution": "Wrong institution listed",
    "outdated_contact": "Contact info (email/website) is wrong or outdated",
    "broken_link": "A link on this page is broken",
    "topics_mismatch": "Research topics or publications don't match this person",
    "duplicate": "Duplicate listing for the same person",
}


def valid_reason_ids(reason_ids):
    """Filters a submitted reason-id list down to the ones FLAG_REASONS
    actually recognizes, preserving order and dropping duplicates -- an
    unrecognized id (stale client, tampered request) is silently dropped
    rather than raising, the same "match nothing extra, don't error" handling
    already used for an unrecognized institution_type/metro id."""
    seen = set()
    valid = []
    for reason_id in reason_ids:
        if reason_id in FLAG_REASONS and reason_id not in seen:
            seen.add(reason_id)
            valid.append(reason_id)
    return valid


def build_flag_notification_email(professor_id, professor_name, reason_ids, details, app_base_url):
    """Pure email content builder, kept apart from the actual send_email()
    call so it's testable without network access -- same split as
    build_resend_payload() in backend/email.py and build_summary_prompt() in
    backend/llm.py. reason_ids is assumed already filtered by
    valid_reason_ids() -- this just renders whatever it's given."""
    reason_lines = [f"- {FLAG_REASONS[reason_id]}" for reason_id in reason_ids if reason_id in FLAG_REASONS]
    if not reason_lines:
        reason_lines = ["- (no checkbox reason selected -- see details below)"]

    lines = [
        f"Professor: {professor_name or '(no name on file)'} (id {professor_id})",
        f"Link: {app_base_url}/#/professor/{professor_id}",
        "",
        "Reported issues:",
        *reason_lines,
    ]
    if details:
        lines += ["", "Additional details:", details]

    subject = f"Professor flag: {professor_name or f'professor #{professor_id}'}"
    return subject, "\n".join(lines)
