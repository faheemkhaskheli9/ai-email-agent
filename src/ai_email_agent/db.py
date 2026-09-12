"""PostgreSQL persistence for ingested + classified emails (Phase 1).

Schema/migration: :func:`create_schema` issues an idempotent
``CREATE TABLE IF NOT EXISTS emails (...)`` (plus its unique constraint and
indexes) via SQLAlchemy Core, so it's Phase 1's single migration step -- see
``scripts/init_db.py`` and README §9 for how to run it. The table definition
is plain SQLAlchemy Core (no Postgres-only types), so the exact same schema
and store logic run against ``sqlite:///...`` for local dev/tests with no
Postgres server required, and against a real ``postgresql://...`` URL in
production -- this repo's CPU-only dev/CI convention.

Re-ingesting the same ``message_id`` never creates a duplicate row: a unique
constraint on ``message_id`` is the source of truth for "already ingested",
and :meth:`PostgresEmailStore.upsert_email` reacts to the constraint
violation by updating the existing row instead of pre-checking existence
(which would race under concurrent ingestion).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    update,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ai_email_agent.models import IngestedEmail

__all__ = [
    "EmailRecord",
    "EmailStoreError",
    "PostgresEmailStore",
    "create_schema",
    "emails_table",
    "metadata",
]

metadata = MetaData()

emails_table = Table(
    "emails",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("message_id", String(512), nullable=False),
    Column("thread_id", String(512), nullable=False),
    Column("sender", String(320), nullable=False),
    Column("subject", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("category", String(128), nullable=True),
    Column("confidence", Float, nullable=True),
    Column("status", String(32), nullable=False, server_default="ingested"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("message_id", name="uq_emails_message_id"),
    Index("ix_emails_thread_id", "thread_id"),
    Index("ix_emails_sender", "sender"),
)


@dataclass(frozen=True)
class EmailRecord:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    category: str | None
    confidence: float | None
    status: str
    created_at: datetime
    updated_at: datetime


class EmailStoreError(RuntimeError):
    """The email store's database is unreachable or misconfigured.

    Covers: a ``postgresql://`` URL with no driver installed (``psycopg2``
    isn't in this repo's CPU-only base install), or any other connection
    failure -- raised with an actionable message instead of a bare
    ``ModuleNotFoundError``/driver traceback.
    """


def create_schema(engine: Engine) -> None:
    """Create the ``emails`` table (with its unique constraint and indexes) if missing.

    Idempotent -- safe to call on every startup/migration run.
    """
    metadata.create_all(engine, checkfirst=True)


def _row_to_record(row) -> EmailRecord:
    return EmailRecord(
        message_id=row.message_id,
        thread_id=row.thread_id,
        sender=row.sender,
        subject=row.subject,
        body=row.body,
        category=row.category,
        confidence=row.confidence,
        status=row.status,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class PostgresEmailStore:
    """Persists ingested/classified emails, keyed uniquely by ``message_id``."""

    def __init__(self, database_url: str, *, echo: bool = False) -> None:
        try:
            self._engine = create_engine(database_url, echo=echo, future=True)
            create_schema(self._engine)
        except EmailStoreError:
            raise
        except Exception as exc:  # missing driver (e.g. psycopg2), bad URL, unreachable host
            raise EmailStoreError(
                f"could not connect to the email store at {database_url!r}: {exc}. "
                "For PostgreSQL, install `psycopg2-binary`; for local dev/tests, "
                "a `sqlite:///path/to.db` URL needs no extra driver."
            ) from exc

    def upsert_email(
        self,
        email: IngestedEmail,
        *,
        category: str | None = None,
        confidence: float | None = None,
        status: str = "ingested",
    ) -> None:
        """Insert ``email``, or update it in place if ``message_id`` already exists."""
        now = datetime.now(timezone.utc)
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    insert(emails_table).values(
                        message_id=email.message_id,
                        thread_id=email.thread_id,
                        sender=email.sender,
                        subject=email.subject,
                        body=email.body,
                        category=category,
                        confidence=confidence,
                        status=status,
                        created_at=now,
                        updated_at=now,
                    )
                )
            return
        except IntegrityError:
            pass  # message_id already present -- fall through to an update

        with self._engine.begin() as conn:
            result = conn.execute(
                update(emails_table)
                .where(emails_table.c.message_id == email.message_id)
                .values(
                    thread_id=email.thread_id,
                    sender=email.sender,
                    subject=email.subject,
                    body=email.body,
                    category=category,
                    confidence=confidence,
                    status=status,
                    updated_at=now,
                )
            )
            if result.rowcount == 0:
                raise EmailStoreError(
                    f"upsert of {email.message_id!r} hit a unique-constraint conflict "
                    "but no row was found to update"
                )

    def get_by_message_id(self, message_id: str) -> EmailRecord | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                select(emails_table).where(emails_table.c.message_id == message_id)
            ).first()
        return _row_to_record(row) if row is not None else None

    def list_by_thread(self, thread_id: str) -> list[EmailRecord]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(emails_table)
                .where(emails_table.c.thread_id == thread_id)
                .order_by(emails_table.c.created_at)
            ).all()
        return [_row_to_record(r) for r in rows]

    def list_by_sender(self, sender: str) -> list[EmailRecord]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(emails_table)
                .where(emails_table.c.sender == sender)
                .order_by(emails_table.c.created_at)
            ).all()
        return [_row_to_record(r) for r in rows]

    def list_by_status(self, status: str) -> list[EmailRecord]:
        """Fetch every email currently in `status` (e.g. `needs_review`) --
        the manual-review queue this backs (issue #6)."""
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(emails_table)
                .where(emails_table.c.status == status)
                .order_by(emails_table.c.created_at)
            ).all()
        return [_row_to_record(r) for r in rows]
