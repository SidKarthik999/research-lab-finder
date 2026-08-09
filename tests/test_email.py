import pytest

from backend.email import build_resend_payload, send_email


def test_build_resend_payload_wraps_recipient_in_a_list():
    payload = build_resend_payload("student@example.com", "Subject", "Body", "from@example.com")
    assert payload["to"] == ["student@example.com"]


def test_build_resend_payload_passes_through_fields_unchanged():
    payload = build_resend_payload("a@b.com", "My subject", "My body", "Sender <s@example.com>")
    assert payload["from"] == "Sender <s@example.com>"
    assert payload["subject"] == "My subject"
    assert payload["text"] == "My body"


def test_unconfigured_backend_still_raises_not_implemented(monkeypatch):
    monkeypatch.setenv("EMAIL_BACKEND", "some-other-provider")
    with pytest.raises(NotImplementedError):
        send_email("a@b.com", "Subject", "Body")


def test_resend_backend_without_api_key_raises_clear_error(monkeypatch):
    monkeypatch.setenv("EMAIL_BACKEND", "resend")
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="RESEND_API_KEY"):
        send_email("a@b.com", "Subject", "Body")


def test_console_backend_is_default(monkeypatch, capsys):
    monkeypatch.delenv("EMAIL_BACKEND", raising=False)
    send_email("a@b.com", "Hello", "World")
    captured = capsys.readouterr()
    assert "a@b.com" in captured.out
    assert "Hello" in captured.out
    assert "World" in captured.out
