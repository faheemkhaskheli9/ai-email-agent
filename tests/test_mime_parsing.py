import pytest

from ai_email_agent.mime_parsing import parse_email_message
from ai_email_agent.models import MalformedMessageError

VALID_RAW = (
    b"From: alice@example.com\r\n"
    b"To: support@example.com\r\n"
    b"Subject: Trouble logging in\r\n"
    b"Message-ID: <msg-001@example.com>\r\n"
    b"Date: Mon, 01 Sep 2025 09:00:00 +0000\r\n"
    b"Content-Type: text/plain; charset=\"utf-8\"\r\n"
    b"\r\n"
    b"Hi, I can't log in.\r\n"
)


def test_parses_valid_message_into_common_schema():
    email = parse_email_message("uid-1", VALID_RAW)
    assert email.message_id == "<msg-001@example.com>"
    assert email.subject == "Trouble logging in"
    assert email.sender == "alice@example.com"
    assert "can't log in" in email.body
    assert email.attachments == ()


def test_missing_message_id_falls_back_to_uid():
    raw = b"From: a@example.com\r\nSubject: hi\r\n\r\nbody\r\n"
    email = parse_email_message("uid-42", raw)
    assert email.message_id == "uid:uid-42"


def test_malformed_bytes_raise_typed_error_not_a_crash():
    with pytest.raises(MalformedMessageError):
        parse_email_message("uid-bad", b"\xff\xfe\x00not an email at all\x00\xff")


def test_malformed_error_carries_the_uid():
    try:
        parse_email_message("uid-bad", b"\xff\xfe\x00\x00\xff")
    except MalformedMessageError as exc:
        assert exc.uid == "uid-bad"
    else:
        pytest.fail("expected MalformedMessageError")
