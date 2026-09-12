"""Integration tests for issue #6: low-confidence classifications are routed
to `needs_review` instead of auto-proceeding as `classified`.

A fake classifier client is injected in place of `OpenAIClassifierClient`
(the same swappable-client convention `classification.py` documents) so
these run with no network access or API key -- only `OPENAI_API_KEY` being
*set* (to a dummy value) is needed to take the classify-and-route path at
all.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_email_agent import cli
from ai_email_agent.db import PostgresEmailStore

REPO_ROOT = Path(__file__).resolve().parents[1]
SAMPLE_MAILBOX = REPO_ROOT / "examples" / "sample_mailbox"


class _FixedConfidenceClassifierClient:
    """Returns the same (label, confidence) for every email."""

    def __init__(self, api_key: str, *, model: str = "fake-model", client: object | None = None) -> None:
        del api_key, client

    @property
    def model_name(self) -> str:
        return "fake-model"

    confidence: float = 0.5  # overridden per-test via a subclass

    def classify(self, subject, body, categories):
        return "support", self.confidence


def _classifier_factory(confidence: float):
    class _Client(_FixedConfidenceClassifierClient):
        pass

    _Client.confidence = confidence
    return _Client


@pytest.fixture
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'emails.db'}"


def _run_poll_with_fake_classifier(monkeypatch, tmp_path, db_url, confidence):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-key-not-real")
    monkeypatch.setattr(cli, "OpenAIClassifierClient", _classifier_factory(confidence))

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


def test_low_confidence_classification_is_flagged_needs_review(monkeypatch, tmp_path, db_url):
    _run_poll_with_fake_classifier(monkeypatch, tmp_path, db_url, confidence=0.2)

    store = PostgresEmailStore(db_url)
    record = store.get_by_message_id("<msg-001@example.com>")
    assert record is not None
    assert record.status == "needs_review"


def test_high_confidence_classification_auto_proceeds(monkeypatch, tmp_path, db_url):
    _run_poll_with_fake_classifier(monkeypatch, tmp_path, db_url, confidence=0.95)

    store = PostgresEmailStore(db_url)
    record = store.get_by_message_id("<msg-001@example.com>")
    assert record is not None
    assert record.status == "classified"


def test_review_queue_command_lists_needs_review_emails(monkeypatch, tmp_path, db_url, capsys):
    _run_poll_with_fake_classifier(monkeypatch, tmp_path, db_url, confidence=0.2)
    capsys.readouterr()  # discard poll output

    rc = cli.main(["review-queue", "--database-url", db_url])

    assert rc == 0
    out = capsys.readouterr().out
    assert "needs_review: 2" in out
    assert "<msg-001@example.com>" in out


def test_review_queue_command_without_database_url_errors(capsys):
    rc = cli.main(["review-queue"])
    assert rc == 1
    assert "persistence skipped" in capsys.readouterr().out
