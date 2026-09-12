"""Tests for the PostgreSQL email store (issue #5).

A real Postgres server isn't available on this repo's CPU-only dev/CI host,
so tests exercise the exact same schema/store logic against a file-backed
SQLite database (the CPU-only convention documented in `db.py`) -- the
table definition is plain SQLAlchemy Core with no Postgres-only types, so
nothing about the schema or the store's SQL differs between the two.
"""

from __future__ import annotations

import pytest

from ai_email_agent.db import EmailStoreError, PostgresEmailStore, create_schema, emails_table
from ai_email_agent.models import IngestedEmail
from sqlalchemy import create_engine, func, inspect, select


def _email(**overrides) -> IngestedEmail:
    defaults = dict(
        message_id="msg-1",
        thread_id="thread-1",
        subject="Order question",
        body="Where is my order?",
        sender="customer@example.com",
        timestamp="2025-01-01T00:00:00+00:00",
    )
    defaults.update(overrides)
    return IngestedEmail(**defaults)


@pytest.fixture
def store(tmp_path):
    return PostgresEmailStore(f"sqlite:///{tmp_path / 'emails.db'}")


def test_schema_has_unique_constraint_and_indexes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}", future=True)
    create_schema(engine)

    inspector = inspect(engine)
    assert "emails" in inspector.get_table_names()

    unique_columns = {
        tuple(uc["column_names"]) for uc in inspector.get_unique_constraints("emails")
    }
    assert ("message_id",) in unique_columns

    indexed_columns = {tuple(ix["column_names"]) for ix in inspector.get_indexes("emails")}
    assert ("thread_id",) in indexed_columns
    assert ("sender",) in indexed_columns


def test_schema_creation_is_idempotent(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}", future=True)
    create_schema(engine)
    create_schema(engine)  # must not raise on a second call


def test_upsert_then_get_round_trips(store):
    store.upsert_email(_email(), status="ingested")

    record = store.get_by_message_id("msg-1")
    assert record is not None
    assert record.thread_id == "thread-1"
    assert record.sender == "customer@example.com"
    assert record.status == "ingested"
    assert record.category is None


def test_missing_message_id_returns_none(store):
    assert store.get_by_message_id("does-not-exist") is None


def test_reingesting_same_message_id_does_not_duplicate(store):
    store.upsert_email(_email(subject="v1"), status="ingested")
    store.upsert_email(_email(subject="v2"), status="ingested")

    record = store.get_by_message_id("msg-1")
    assert record.subject == "v2"  # updated in place, not appended

    with store._engine.connect() as conn:
        count = conn.execute(select(func.count()).select_from(emails_table)).scalar_one()
    assert count == 1


def test_classification_update_sets_category_and_confidence(store):
    store.upsert_email(_email(), status="ingested")
    store.upsert_email(_email(), category="billing", confidence=0.91, status="classified")

    record = store.get_by_message_id("msg-1")
    assert record.category == "billing"
    assert record.confidence == pytest.approx(0.91)
    assert record.status == "classified"


def test_list_by_thread_returns_matching_emails_in_order(store):
    store.upsert_email(_email(message_id="m1", thread_id="t1"))
    store.upsert_email(_email(message_id="m2", thread_id="t1"))
    store.upsert_email(_email(message_id="m3", thread_id="t2"))

    records = store.list_by_thread("t1")
    assert [r.message_id for r in records] == ["m1", "m2"]


def test_list_by_sender_returns_matching_emails(store):
    store.upsert_email(_email(message_id="m1", sender="a@example.com"))
    store.upsert_email(_email(message_id="m2", sender="b@example.com"))

    records = store.list_by_sender("a@example.com")
    assert [r.message_id for r in records] == ["m1"]


def test_list_by_status_returns_matching_emails(store):
    store.upsert_email(_email(message_id="m1"), status="needs_review")
    store.upsert_email(_email(message_id="m2"), status="classified")
    store.upsert_email(_email(message_id="m3"), status="needs_review")

    records = store.list_by_status("needs_review")
    assert [r.message_id for r in records] == ["m1", "m3"]


def test_list_by_status_empty_when_none_match(store):
    store.upsert_email(_email(message_id="m1"), status="classified")
    assert store.list_by_status("needs_review") == []


def test_unreachable_database_raises_clear_error():
    with pytest.raises(EmailStoreError, match="could not connect"):
        PostgresEmailStore("postgresql://user:pass@nonexistent-host-xyz/db")
