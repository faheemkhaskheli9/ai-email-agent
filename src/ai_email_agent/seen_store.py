"""Tracks which message ids have already been ingested, so a poll is idempotent.

A JSON file is enough for Phase 1; Phase 1's later PostgreSQL-persistence issue
replaces the storage backend behind this same interface without touching the
poller.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol


class SeenIdStore(Protocol):
    def is_seen(self, message_id: str) -> bool: ...
    def mark_seen(self, message_id: str) -> None: ...


class InMemorySeenIdStore:
    """Non-persistent store — useful for tests and one-shot demo runs."""

    def __init__(self) -> None:
        self._seen: set[str] = set()

    def is_seen(self, message_id: str) -> bool:
        return message_id in self._seen

    def mark_seen(self, message_id: str) -> None:
        self._seen.add(message_id)


class JsonFileSeenIdStore:
    """Persists seen message ids to a JSON file, atomically on every write."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._seen: set[str] = set()
        if self.path.exists():
            self._seen = set(json.loads(self.path.read_text() or "[]"))

    def is_seen(self, message_id: str) -> bool:
        return message_id in self._seen

    def mark_seen(self, message_id: str) -> None:
        if message_id in self._seen:
            return
        self._seen.add(message_id)
        # Atomic write: a poll interrupted mid-save must never leave a
        # truncated/corrupt seen-ids file that forgets or duplicates entries.
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(sorted(self._seen)))
        tmp_path.replace(self.path)
