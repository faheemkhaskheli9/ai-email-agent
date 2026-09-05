"""Parse a raw RFC 822 message into the common :class:`IngestedEmail` schema."""

from __future__ import annotations

from email import message_from_bytes, policy
from email.message import EmailMessage

from ai_email_agent.models import Attachment, IngestedEmail, MalformedMessageError


def parse_email_message(uid: str, raw: bytes) -> IngestedEmail:
    """Parse raw message bytes for ``uid`` into an :class:`IngestedEmail`.

    Raises :class:`MalformedMessageError` (never a bare parser exception) so
    callers can log-and-skip a single bad message instead of crashing the poll.
    """
    try:
        msg = message_from_bytes(raw, policy=policy.default)
    except Exception as exc:  # the stdlib parser raises assorted Exception subtypes
        raise MalformedMessageError(uid, f"could not parse MIME: {exc}") from exc

    if not isinstance(msg, EmailMessage):  # pragma: no cover - defensive, policy.default guarantees this
        raise MalformedMessageError(uid, "unexpected message type")

    if msg.defects:
        # email.policy.default parses very leniently and rarely raises outright;
        # RFC822 structural problems (missing header/body separator, unterminated
        # MIME boundary, ...) surface here instead. Treat any of them as malformed
        # rather than silently ingesting a message we half-parsed.
        reasons = ", ".join(type(d).__name__ for d in msg.defects)
        raise MalformedMessageError(uid, f"structural defects: {reasons}")

    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        # Fall back to the mailbox uid so ingestion is still possible, but this
        # is a real data-quality problem worth surfacing rather than hiding.
        message_id = f"uid:{uid}"

    sender = (msg.get("From") or "").strip()
    subject = (msg.get("Subject") or "").strip()
    thread_id = (msg.get("References") or msg.get("In-Reply-To") or message_id).split()[0]
    timestamp = (msg.get("Date") or "").strip()

    try:
        body_part = msg.get_body(preferencelist=("plain", "html"))
        body = body_part.get_content() if body_part is not None else ""
    except Exception as exc:
        raise MalformedMessageError(uid, f"could not extract body: {exc}") from exc

    attachments = []
    for part in msg.iter_attachments():
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            Attachment(
                filename=part.get_filename() or "unnamed",
                content_type=part.get_content_type(),
                size_bytes=len(payload),
            )
        )

    return IngestedEmail(
        message_id=message_id,
        thread_id=thread_id,
        subject=subject,
        body=body.strip(),
        sender=sender,
        timestamp=timestamp,
        attachments=tuple(attachments),
    )
