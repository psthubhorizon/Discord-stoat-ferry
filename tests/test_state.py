"""Tests for migration state persistence."""

from pathlib import Path

import pytest

from discord_ferry.errors import StateError
from discord_ferry.state import MigrationState, load_state, save_state


def test_save_and_load_roundtrip(tmp_path: Path) -> None:
    """State survives a save/load round-trip."""
    state = MigrationState(
        stoat_server_id="01ABC",
        current_phase="messages",
        started_at="2024-01-01T00:00:00+00:00",
    )
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded.stoat_server_id == "01ABC"
    assert loaded.current_phase == "messages"
    assert loaded.started_at == "2024-01-01T00:00:00+00:00"


def test_save_creates_output_dir(tmp_path: Path) -> None:
    """save_state creates the output directory if it doesn't exist."""
    nested = tmp_path / "deep" / "nested" / "dir"
    save_state(MigrationState(), nested)
    assert (nested / "state.json").exists()


def test_load_missing_file(tmp_path: Path) -> None:
    """load_state raises StateError for missing file."""
    with pytest.raises(StateError, match="not found"):
        load_state(tmp_path)


def test_load_corrupt_json(tmp_path: Path) -> None:
    """load_state raises StateError for corrupt JSON."""
    (tmp_path / "state.json").write_text("not valid json {{{", encoding="utf-8")
    with pytest.raises(StateError, match="Corrupt"):
        load_state(tmp_path)


def test_pending_pins_tuple_roundtrip(tmp_path: Path) -> None:
    """Pending pins tuples survive JSON serialization."""
    state = MigrationState(
        pending_pins=[("ch1", "msg1"), ("ch2", "msg2")],
    )
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded.pending_pins == [("ch1", "msg1"), ("ch2", "msg2")]
    assert isinstance(loaded.pending_pins[0], tuple)


def test_state_with_populated_maps(tmp_path: Path) -> None:
    """State with data in all maps round-trips correctly."""
    state = MigrationState(
        role_map={"d_role1": "s_role1"},
        channel_map={"d_ch1": "s_ch1", "d_ch2": "s_ch2"},
        category_map={"d_cat1": "s_cat1"},
        message_map={"d_msg1": "s_msg1"},
        emoji_map={"d_emoji1": "s_emoji1"},
        avatar_cache={"author1": "autumn_av1"},
        upload_cache={"/path/to/file.png": "autumn_file1"},
        author_names={"12345": "Alice"},
        pending_reactions=[{"channel_id": "ch1", "message_id": "msg1", "emoji": "👍"}],
        errors=[{"phase": "messages", "error": "timeout"}],
        warnings=[{"type": "http_attachment", "message": "missing media"}],
        stoat_server_id="01STOAT",
        current_phase="reactions",
        last_completed_channel="general",
        last_completed_message="msg999",
        started_at="2024-06-01T10:00:00+00:00",
        completed_at="2024-06-01T14:00:00+00:00",
    )
    save_state(state, tmp_path)
    loaded = load_state(tmp_path)
    assert loaded.role_map == {"d_role1": "s_role1"}
    assert loaded.channel_map == {"d_ch1": "s_ch1", "d_ch2": "s_ch2"}
    assert loaded.emoji_map == {"d_emoji1": "s_emoji1"}
    assert loaded.author_names == {"12345": "Alice"}
    assert loaded.upload_cache == {"/path/to/file.png": "autumn_file1"}
    assert loaded.last_completed_channel == "general"
    assert loaded.completed_at == "2024-06-01T14:00:00+00:00"
    assert len(loaded.errors) == 1
    assert len(loaded.warnings) == 1


def test_atomic_write_no_tmp_leftover(tmp_path: Path) -> None:
    """After save, the .tmp file should not remain."""
    save_state(MigrationState(), tmp_path)
    assert not (tmp_path / "state.json.tmp").exists()
    assert (tmp_path / "state.json").exists()
