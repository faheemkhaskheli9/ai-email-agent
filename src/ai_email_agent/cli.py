"""CLI entry point.

    python -m ai_email_agent.cli poll --mailbox examples/sample_mailbox --seen-store .seen_ids.json

Polls a mailbox (a fixture directory of .eml files by default, or a real IMAP
server if IMAP_HOST/IMAP_USER/IMAP_PASSWORD are set) once and reports what was
ingested, skipped as a duplicate, or failed to parse.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from ai_email_agent.classification import OpenAIClassifierClient, classify_email
from ai_email_agent.classification_store import JsonFileClassificationStore
from ai_email_agent.connector import FixtureMailboxClient, ImapMailboxClient, poll_mailbox
from ai_email_agent.db import EmailStoreError, PostgresEmailStore
from ai_email_agent.models import IngestedEmail
from ai_email_agent.seen_store import JsonFileSeenIdStore
from ai_email_agent.taxonomy import TaxonomyError, load_categories

logger = logging.getLogger("ai_email_agent.cli")


def _open_email_store(database_url: str | None) -> PostgresEmailStore | None:
    """Open the PostgreSQL email store, or None if persistence isn't configured.

    Mirrors the OPENAI_API_KEY convention below: no `$DATABASE_URL` (nothing
    provisioned in this demo environment) skips persistence explicitly rather
    than crashing the poll.
    """
    if not database_url:
        print("  persistence skipped: no DATABASE_URL set")
        return None
    try:
        return PostgresEmailStore(database_url)
    except EmailStoreError as exc:
        print(f"  persistence skipped: {exc}")
        return None


def _classify_ingested(
    ingested: list[IngestedEmail],
    classification_store_path: str,
    email_store: PostgresEmailStore | None,
) -> None:
    """Classify each newly-ingested email and persist the result.

    Requires ``OPENAI_API_KEY``; with no key set (no paid API in this demo
    environment) classification is skipped with an explicit message rather
    than silently doing nothing. Ingestion into ``email_store`` (if
    configured) happens either way, so history/queue features have a record
    even for emails that failed or were skipped for classification.
    """
    for email in ingested:
        if email_store is not None:
            email_store.upsert_email(email, status="ingested")

    if not ingested:
        return

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  classification skipped: no OPENAI_API_KEY set")
        return

    try:
        categories = load_categories()
    except TaxonomyError as exc:
        print(f"  classification skipped: {exc}")
        return

    classifier = OpenAIClassifierClient(api_key)
    store = JsonFileClassificationStore(Path(classification_store_path))
    print("  classifications:")
    for email in ingested:
        try:
            result = classify_email(classifier, email.subject, email.body, categories)
        except Exception as exc:  # one bad classification must not crash the poll
            logger.warning("classification failed for %s: %s", email.message_id, exc)
            print(f"    - {email.message_id}: classification failed: {exc}")
            continue
        store.save(email.message_id, result)
        if email_store is not None:
            email_store.upsert_email(
                email, category=result.label, confidence=result.confidence, status="classified"
            )
        print(f"    - {email.message_id}: {result.label} ({result.confidence:.2f})")


def _run_poll(
    mailbox_dir: str,
    seen_store_path: str,
    classification_store_path: str,
    database_url: str | None,
) -> int:
    seen_store = JsonFileSeenIdStore(Path(seen_store_path))
    email_store = _open_email_store(database_url)

    host, user, password = (
        os.environ.get("IMAP_HOST"),
        os.environ.get("IMAP_USER"),
        os.environ.get("IMAP_PASSWORD"),
    )
    if host and user and password:
        client = ImapMailboxClient(host, user, password)
        source = f"IMAP:{host}"
    else:
        client = FixtureMailboxClient(Path(mailbox_dir))
        source = f"fixture:{mailbox_dir}"

    result = poll_mailbox(client, seen_store)

    print(f"polled {source}")
    print(f"  ingested: {len(result.ingested)}")
    for email in result.ingested:
        print(f"    - {email.message_id}: {email.subject!r} from {email.sender}")
    print(f"  skipped (already seen): {result.skipped_already_seen}")
    print(f"  failed: {len(result.failed)}")
    for uid, reason in result.failed:
        print(f"    - {uid}: {reason}")

    _classify_ingested(result.ingested, classification_store_path, email_store)
    return 0


def build_parser() -> argparse.ArgumentParser:
    # Shared parent so -v/--verbose works both before and after the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-v", "--verbose", action="store_true")

    parser = argparse.ArgumentParser(
        prog="ai_email_agent", description=__doc__, parents=[common]
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("poll", parents=[common], help="poll the mailbox once")
    p.add_argument(
        "--mailbox",
        default="examples/sample_mailbox",
        help="fixture directory of .eml files (used when no IMAP_* env vars are set)",
    )
    p.add_argument(
        "--seen-store",
        default=".seen_ids.json",
        help="path to the JSON file tracking already-ingested message ids",
    )
    p.add_argument(
        "--classification-store",
        default=".classifications.json",
        help="path to the JSON file tracking classification results",
    )
    p.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy URL for the emails table (e.g. postgresql://... or sqlite:///...); "
        "defaults to $DATABASE_URL, and persistence is skipped if neither is set",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    if args.command == "poll":
        return _run_poll(
            args.mailbox, args.seen_store, args.classification_store, args.database_url
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
