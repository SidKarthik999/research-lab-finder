from backend.flags import FLAG_REASONS, build_flag_notification_email, valid_reason_ids


def test_valid_reason_ids_keeps_only_known_ids():
    assert valid_reason_ids(["wrong_person", "not_a_real_reason", "broken_link"]) == [
        "wrong_person",
        "broken_link",
    ]


def test_valid_reason_ids_drops_duplicates_preserving_first_occurrence_order():
    assert valid_reason_ids(["broken_link", "wrong_person", "broken_link"]) == ["broken_link", "wrong_person"]


def test_valid_reason_ids_empty_list_returns_empty_list():
    assert valid_reason_ids([]) == []


def test_valid_reason_ids_all_unrecognized_returns_empty_list():
    # Same "match nothing extra, don't error" handling as an unrecognized
    # institution_type/metro id -- a stale client or tampered request
    # shouldn't be able to inject an arbitrary reason string.
    assert valid_reason_ids(["not_real", "also_not_real"]) == []


def test_build_flag_notification_email_includes_professor_link_and_reasons():
    subject, body = build_flag_notification_email(
        42, "Ada Lovelace", ["wrong_person", "broken_link"], None, "https://research-finder.com"
    )
    assert "Ada Lovelace" in subject
    assert "https://research-finder.com/#/professor/42" in body
    assert FLAG_REASONS["wrong_person"] in body
    assert FLAG_REASONS["broken_link"] in body


def test_build_flag_notification_email_includes_details_when_present():
    _, body = build_flag_notification_email(1, "Some Professor", [], "This is actually two different people.", "https://x.test")
    assert "This is actually two different people." in body


def test_build_flag_notification_email_no_reasons_still_produces_readable_body():
    # A submission can be details-only (no checkboxes ticked) -- the email
    # shouldn't render an empty "Reported issues:" section.
    _, body = build_flag_notification_email(1, "Some Professor", [], "Something is off.", "https://x.test")
    assert "Reported issues:" in body
    assert "no checkbox reason selected" in body


def test_build_flag_notification_email_missing_name_falls_back_to_id():
    subject, body = build_flag_notification_email(7, None, ["wrong_person"], None, "https://x.test")
    assert "7" in subject
    assert "(no name on file)" in body
