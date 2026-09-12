#!/usr/bin/env python
"""Create/verify the `emails` table for the configured database.

    python scripts/init_db.py                       # uses $DATABASE_URL
    python scripts/init_db.py --database-url sqlite:///dev.db

Safe to re-run: schema creation is idempotent (`CREATE TABLE IF NOT EXISTS`
plus its unique constraint and indexes).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_email_agent.db import EmailStoreError, PostgresEmailStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy URL, e.g. postgresql://user:pass@host/db or sqlite:///dev.db",
    )
    args = parser.parse_args(argv)

    if not args.database_url:
        print("error: no --database-url given and $DATABASE_URL is not set", file=sys.stderr)
        return 2

    try:
        PostgresEmailStore(args.database_url)
    except EmailStoreError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"emails table ready at {args.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
