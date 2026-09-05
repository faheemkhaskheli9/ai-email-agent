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

from ai_email_agent.connector import FixtureMailboxClient, ImapMailboxClient, poll_mailbox
from ai_email_agent.seen_store import JsonFileSeenIdStore


def _run_poll(mailbox_dir: str, seen_store_path: str) -> int:
    seen_store = JsonFileSeenIdStore(Path(seen_store_path))

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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)
    if args.command == "poll":
        return _run_poll(args.mailbox, args.seen_store)
    return 2


if __name__ == "__main__":
    sys.exit(main())
