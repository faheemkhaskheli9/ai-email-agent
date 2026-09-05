from pathlib import Path

from ai_email_agent.connector import poll_mailbox
from ai_email_agent.seen_store import InMemorySeenIdStore, JsonFileSeenIdStore

VALID = (
    b"From: alice@example.com\r\n"
    b"Subject: hi\r\n"
    b"Message-ID: <m1@example.com>\r\n"
    b"\r\n"
    b"body one\r\n"
)
VALID_2 = (
    b"From: bob@example.com\r\n"
    b"Subject: hi2\r\n"
    b"Message-ID: <m2@example.com>\r\n"
    b"\r\n"
    b"body two\r\n"
)
MALFORMED = b"\xff\xfe\x00garbage\x00\xff"


class FakeMailboxClient:
    def __init__(self, messages: dict[str, bytes]) -> None:
        self.messages = messages

    def list_new_uids(self) -> list[str]:
        return sorted(self.messages)

    def fetch_raw(self, uid: str) -> bytes:
        return self.messages[uid]


def test_valid_messages_are_ingested_and_normalized():
    client = FakeMailboxClient({"1": VALID, "2": VALID_2})
    result = poll_mailbox(client, InMemorySeenIdStore())
    assert {e.message_id for e in result.ingested} == {"<m1@example.com>", "<m2@example.com>"}
    assert result.failed == []


def test_malformed_message_is_logged_and_skipped_not_raised():
    client = FakeMailboxClient({"1": VALID, "2": MALFORMED})
    result = poll_mailbox(client, InMemorySeenIdStore())
    assert len(result.ingested) == 1
    assert len(result.failed) == 1
    assert result.failed[0][0] == "2"


def test_second_poll_does_not_reingest_same_message_id():
    seen_store = InMemorySeenIdStore()
    client = FakeMailboxClient({"1": VALID})
    first = poll_mailbox(client, seen_store)
    second = poll_mailbox(client, seen_store)
    assert len(first.ingested) == 1
    assert len(second.ingested) == 0
    assert second.skipped_already_seen == 1


def test_idempotency_persists_across_store_instances(tmp_path: Path):
    store_path = tmp_path / "seen.json"
    client = FakeMailboxClient({"1": VALID})

    first = poll_mailbox(client, JsonFileSeenIdStore(store_path))
    # Simulate the process restarting: a brand new store instance reads the same file.
    second = poll_mailbox(client, JsonFileSeenIdStore(store_path))

    assert len(first.ingested) == 1
    assert len(second.ingested) == 0
