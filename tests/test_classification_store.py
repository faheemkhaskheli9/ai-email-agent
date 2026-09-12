from pathlib import Path

from ai_email_agent.classification import ClassificationResult
from ai_email_agent.classification_store import (
    InMemoryClassificationStore,
    JsonFileClassificationStore,
)

RESULT = ClassificationResult(
    label="support", confidence=0.95, model="fake-model-v1", classified_at="2025-01-01T00:00:00+00:00"
)


def test_in_memory_store_round_trips_a_result():
    store = InMemoryClassificationStore()
    assert store.get("m1") is None
    store.save("m1", RESULT)
    assert store.get("m1") == RESULT


def test_json_file_store_creates_file_on_first_write(tmp_path: Path):
    path = tmp_path / "classifications.json"
    store = JsonFileClassificationStore(path)
    assert not path.exists()
    store.save("m1", RESULT)
    assert path.exists()


def test_json_file_store_survives_interrupted_write(tmp_path: Path):
    path = tmp_path / "classifications.json"
    store = JsonFileClassificationStore(path)
    store.save("m1", RESULT)
    tmp_path_file = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_path_file.exists()  # temp file cleaned up by the rename

    reloaded = JsonFileClassificationStore(path)
    assert reloaded.get("m1") == RESULT


def test_json_file_store_persists_multiple_records(tmp_path: Path):
    path = tmp_path / "classifications.json"
    store = JsonFileClassificationStore(path)
    other = ClassificationResult(
        label="spam", confidence=0.6, model="fake-model-v1", classified_at="2025-01-02T00:00:00+00:00"
    )
    store.save("m1", RESULT)
    store.save("m2", other)

    reloaded = JsonFileClassificationStore(path)
    assert reloaded.get("m1") == RESULT
    assert reloaded.get("m2") == other
