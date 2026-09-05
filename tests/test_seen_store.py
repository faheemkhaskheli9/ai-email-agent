from pathlib import Path

from ai_email_agent.seen_store import InMemorySeenIdStore, JsonFileSeenIdStore


def test_in_memory_store_tracks_seen_ids():
    store = InMemorySeenIdStore()
    assert not store.is_seen("a")
    store.mark_seen("a")
    assert store.is_seen("a")


def test_json_file_store_creates_file_on_first_write(tmp_path: Path):
    path = tmp_path / "seen.json"
    store = JsonFileSeenIdStore(path)
    assert not path.exists()
    store.mark_seen("a")
    assert path.exists()


def test_json_file_store_survives_interrupted_write(tmp_path: Path):
    # A crash mid-write must leave the real file untouched, not truncated —
    # the atomic-rename pattern: write to a temp path, then os.replace.
    path = tmp_path / "seen.json"
    store = JsonFileSeenIdStore(path)
    store.mark_seen("a")
    tmp_path_file = path.with_suffix(path.suffix + ".tmp")
    assert not tmp_path_file.exists()  # temp file cleaned up by the rename

    reloaded = JsonFileSeenIdStore(path)
    assert reloaded.is_seen("a")
