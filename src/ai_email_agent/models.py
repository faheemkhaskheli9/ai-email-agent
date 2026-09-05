"""Common internal schema every mailbox source is normalized into."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Attachment:
    filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class IngestedEmail:
    """One normalized email, independent of which provider it came from."""

    message_id: str
    thread_id: str
    subject: str
    body: str
    sender: str
    timestamp: str  # ISO-8601; kept as str so the schema has no timezone-lib dependency
    attachments: tuple[Attachment, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.message_id:
            raise ValueError("message_id must be non-empty (needed for idempotent ingestion)")


class MalformedMessageError(ValueError):
    """Raised when a raw message can't be parsed into an IngestedEmail."""

    def __init__(self, uid: str, reason: str) -> None:
        super().__init__(f"message {uid!r} is malformed: {reason}")
        self.uid = uid
        self.reason = reason
