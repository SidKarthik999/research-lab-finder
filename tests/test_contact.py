from backend.contact import build_contact_notification_email


def test_build_contact_notification_email_includes_name_email_and_message():
    subject, body = build_contact_notification_email(
        "Ada Lovelace", "ada@example.com", "Please remove my listing.", "https://research-finder.com"
    )
    assert "contact form" in subject.lower()
    assert "Ada Lovelace" in body
    assert "ada@example.com" in body
    assert "https://research-finder.com" in body
    assert "Please remove my listing." in body


def test_build_contact_notification_email_missing_name_and_email_falls_back_to_placeholders():
    _, body = build_contact_notification_email(None, None, "Just a question.", "https://x.test")
    assert "(no name given)" in body
    assert "no reply address given" in body
    assert "Just a question." in body
