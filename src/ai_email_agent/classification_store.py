"""Persists classification results alongside their email records.

A JSON file is enough for Phase 1 (mirrors ``seen_store.py``); the Phase 1
PostgreSQL-persistence issue replaces the storage backend behind this same
interface without touching the classification pipeline.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from ai_email_agent.classification import ClassificationResult


class ClassificationStore(Protocol):
    def save(self, message_id: str, result: ClassificationResult) -> None: ...
    def get(self, message_id: str) -> ClassificationResult | None: ...


class InMemoryClassificationStore:
    """Non-persistent store — useful for tests and one-shot demo runs."""

    def __init__(self) -> None:
        self._results: dict[str, ClassificationResult] = {}

    def save(self, message_id: str, result: ClassificationResult) -> None:
        self._results[message_id] = result

    def get(self, message_id: str) -> ClassificationResult | None:
        return self._results.get(message_id)


class JsonFileClassificationStore:
    """Persists classification results to a JSON file, atomically on every write."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._results: dict[str, ClassificationResult] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text() or "{}")
            for message_id, fields in raw.items():
                self._results[message_id] = ClassificationResult(**fields)

    def save(self, message_id: str, result: ClassificationResult) -> None:
        self._results[message_id] = result
        # Atomic write: a poll interrupted mid-save must never leave a
        # truncated/corrupt classifications file that drops other records.
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {mid: asdict(r) for mid, r in self._results.items()}
        tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True))
        tmp_path.replace(self.path)

    def get(self, message_id: str) -> ClassificationResult | None:
        return self._results.get(message_id)
