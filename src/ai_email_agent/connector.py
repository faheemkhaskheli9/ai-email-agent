"""Mailbox polling: fetch new messages, normalize them, skip ones already seen.

``MailboxClient`` is the swappable boundary — ``ImapMailboxClient`` talks to a
real IMAP server; ``FixtureMailboxClient`` (used by the CLI demo and tests)
reads from local ``.eml`` files so the pipeline runs with no live mailbox.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from ai_email_agent.mime_parsing import parse_email_message
from ai_email_agent.models import IngestedEmail, MalformedMessageError
from ai_email_agent.seen_store import SeenIdStore

logger = logging.getLogger("ai_email_agent.connector")


class MailboxClient(Protocol):
    def list_new_uids(self) -> list[str]: ...
    def fetch_raw(self, uid: str) -> bytes: ...


@dataclass
class IngestionResult:
    ingested: list[IngestedEmail] = field(default_factory=list)
    failed: list[tuple[str, str]] = field(default_factory=list)  # (uid, reason)
    skipped_already_seen: int = 0


def poll_mailbox(client: MailboxClient, seen_store: SeenIdStore) -> IngestionResult:
    """Pull every new message from ``client``, normalize it, and skip dupes.

    A single malformed message is logged and skipped rather than raised, so one
    bad email never crashes the poller — the acceptance criterion this exists
    to satisfy.
    """
    result = IngestionResult()
    for uid in client.list_new_uids():
        try:
            raw = client.fetch_raw(uid)
            email = parse_email_message(uid, raw)
        except MalformedMessageError as exc:
            logger.warning("skipping malformed message uid=%s: %s", uid, exc.reason)
            result.failed.append((uid, exc.reason))
            continue
        except Exception as exc:  # auth/network errors from a real client, etc.
            logger.warning("skipping message uid=%s after ingestion error: %s", uid, exc)
            result.failed.append((uid, str(exc)))
            continue

        if seen_store.is_seen(email.message_id):
            result.skipped_already_seen += 1
            continue

        seen_store.mark_seen(email.message_id)
        result.ingested.append(email)

    return result


class ImapMailboxClient:
    """Real IMAP connector (Phase 1 acceptance criterion: "authenticates
    against IMAP ... using credentials from .env/configs").

    Not exercised by the test suite — it needs a live mailbox — but every piece
    of logic downstream of ``list_new_uids``/``fetch_raw`` (parsing, dedup,
    error handling) is fully covered via :class:`FixtureMailboxClient`.
    """

    def __init__(self, host: str, username: str, password: str, *, mailbox: str = "INBOX") -> None:
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self._conn = None

    def _connect(self):
        import imaplib

        if self._conn is None:
            conn = imaplib.IMAP4_SSL(self.host)
            conn.login(self.username, self.password)
            conn.select(self.mailbox)
            self._conn = conn
        return self._conn

    def list_new_uids(self) -> list[str]:
        conn = self._connect()
        status, data = conn.uid("search", None, "UNSEEN")
        if status != "OK":
            raise ConnectionError(f"IMAP search failed: {status}")
        return data[0].split() if data and data[0] else []

    def fetch_raw(self, uid: str) -> bytes:
        conn = self._connect()
        status, data = conn.uid("fetch", uid, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            raise ConnectionError(f"IMAP fetch failed for uid={uid!r}: {status}")
        return data[0][1]


class FixtureMailboxClient:
    """Reads ``.eml`` files from a directory — the demo/test stand-in for IMAP."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def list_new_uids(self) -> list[str]:
        return sorted(p.stem for p in self.directory.glob("*.eml"))

    def fetch_raw(self, uid: str) -> bytes:
        return (self.directory / f"{uid}.eml").read_bytes()
