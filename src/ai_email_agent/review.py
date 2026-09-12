"""Manual-review routing for low-confidence classifications (issue #6).

A classification below the configured confidence threshold must not
silently auto-proceed with the wrong draft/routing treatment -- it's routed
to a ``needs_review`` status instead of ``classified`` so a human sees it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# src/ai_email_agent/review.py -> src/ai_email_agent -> src -> project root
_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "configs" / "review.yaml"

STATUS_CLASSIFIED = "classified"
STATUS_NEEDS_REVIEW = "needs_review"


class ReviewConfigError(ValueError):
    """Raised when the review config file is missing or malformed."""


@dataclass(frozen=True)
class ReviewConfig:
    confidence_threshold: float = 0.6

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence_threshold <= 1.0):
            raise ReviewConfigError(
                f"confidence_threshold must be in [0, 1], got {self.confidence_threshold!r}"
            )


def load_review_config(path: Path | str | None = None) -> ReviewConfig:
    """Load a :class:`ReviewConfig` from a YAML file.

    ``path`` defaults to ``configs/review.yaml``. A missing or malformed
    file is a hard error regardless of whether ``path`` was explicit or the
    default (same contract as ``taxonomy.load_categories``) -- a silently
    default threshold would mean review routing doesn't actually reflect
    the configured policy.
    """
    target = Path(path) if path is not None else _DEFAULT_PATH
    if not target.exists():
        raise ReviewConfigError(f"review config file not found: {target}")

    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ReviewConfigError(f"review config file is not valid YAML: {target}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ReviewConfigError(f"review config file must contain a YAML mapping: {target}")

    try:
        return ReviewConfig(**raw)
    except TypeError as exc:
        raise ReviewConfigError(f"review config file has an unexpected field: {target}: {exc}") from exc


def classification_status(confidence: float, config: ReviewConfig) -> str:
    """Return ``STATUS_NEEDS_REVIEW`` if ``confidence`` is below the
    configured threshold, else ``STATUS_CLASSIFIED``."""
    return STATUS_NEEDS_REVIEW if confidence < config.confidence_threshold else STATUS_CLASSIFIED
