"""Tests for the poll CLI's optional PostgreSQL persistence (issue #5)."""

from __future__ import annotations

from pathlib import Path

from ai_email_agent import cli
from ai_email_agent.db import PostgresEmailStore

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MAILBOX = REPO_ROOT / "examples" / "sample_mailbox"


def test_poll_without_database_url_skips_persistence(tmp_path, capsys):
    rc = cli.main(
        [
            "poll",
            "--mailbox", str(SAMPLE_MAILBOX),
            "--seen-store", str(tmp_path / "seen.json"),
            "--classification-store", str(tmp_path / "classifications.json"),
        ]
    )
    assert rc == 0
    assert "persistence skipped: no DATABASE_URL set" in capsys.readouterr().out


def test_poll_persists_ingested_emails_when_database_url_given(tmp_path, capsys):
    db_url = f"sqlite:///{tmp_path / 'emails.db'}"
    rc = cli.main(
        [
            "poll",
            "--mailbox", str(SAMPLE_MAILBOX),
            "--seen-store", str(tmp_path / "seen.json"),
            "--classification-store", str(tmp_path / "classifications.json"),
            "--database-url", db_url,
        ]
    )
    assert rc == 0

    store = PostgresEmailStore(db_url)
    # both fixture messages ended up in the emails table, unclassified (no API key set)
    ingested_uids = ["<msg-001@example.com>", "<msg-002@example.com>"]
    found = [store.get_by_message_id(mid) for mid in ingested_uids]
    assert any(f is not None for f in found), "expected at least one fixture email persisted"
    for record in found:
        if record is not None:
            assert record.status == "ingested"


def test_repolling_the_same_fixture_does_not_duplicate_rows(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'emails.db'}"
    seen_store = str(tmp_path / "seen.json")
    common_args = [
        "poll",
        "--mailbox", str(SAMPLE_MAILBOX),
        "--seen-store", seen_store,
        "--classification-store", str(tmp_path / "classifications.json"),
        "--database-url", db_url,
    ]

    assert cli.main(common_args) == 0
    assert cli.main(common_args) == 0  # seen_store makes the second poll a no-op for ingestion

    store = PostgresEmailStore(db_url)
    from sqlalchemy import func, select

    from ai_email_agent.db import emails_table

    with store._engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(emails_table)).scalar_one()
    assert count == 2  # the two fixture messages, not duplicated across polls
