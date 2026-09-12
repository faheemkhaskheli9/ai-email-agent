"""Tests for issue #6: manual-review routing for low-confidence classifications."""

from __future__ import annotations

import pytest

from ai_email_agent.review import (
    STATUS_CLASSIFIED,
    STATUS_NEEDS_REVIEW,
    ReviewConfig,
    ReviewConfigError,
    classification_status,
    load_review_config,
)


def test_above_threshold_auto_proceeds():
    config = ReviewConfig(confidence_threshold=0.6)
    assert classification_status(0.9, config) == STATUS_CLASSIFIED


def test_below_threshold_is_flagged_needs_review():
    config = ReviewConfig(confidence_threshold=0.6)
    assert classification_status(0.4, config) == STATUS_NEEDS_REVIEW


def test_exactly_at_threshold_auto_proceeds():
    # Threshold is a floor for auto-proceeding, not an exclusive bound.
    config = ReviewConfig(confidence_threshold=0.6)
    assert classification_status(0.6, config) == STATUS_CLASSIFIED


def test_invalid_threshold_raises():
    with pytest.raises(ReviewConfigError):
        ReviewConfig(confidence_threshold=1.5)
    with pytest.raises(ReviewConfigError):
        ReviewConfig(confidence_threshold=-0.1)


def test_load_review_config_reads_shipped_default():
    config = load_review_config()
    assert 0.0 <= config.confidence_threshold <= 1.0


def test_load_review_config_missing_path_raises():
    with pytest.raises(ReviewConfigError):
        load_review_config("configs/does-not-exist.yaml")


def test_load_review_config_custom_threshold(tmp_path):
    path = tmp_path / "review.yaml"
    path.write_text("confidence_threshold: 0.8\n", encoding="utf-8")
    config = load_review_config(path)
    assert config.confidence_threshold == 0.8


def test_load_review_config_malformed_yaml_raises(tmp_path):
    path = tmp_path / "review.yaml"
    path.write_text("confidence_threshold: [this is not a number\n", encoding="utf-8")
    with pytest.raises(ReviewConfigError):
        load_review_config(path)


def test_load_review_config_not_a_mapping_raises(tmp_path):
    path = tmp_path / "review.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(ReviewConfigError):
        load_review_config(path)
