"""Tests for migration report generator."""

import json
from pathlib import Path

from discord_ferry.config import FerryConfig
from discord_ferry.discord.metadata import (
    DiscordMetadata,
    PermissionPair,
    save_discord_metadata,
)
from discord_ferry.parser.models import DCEChannel, DCEExport, DCEGuild
from discord_ferry.reporter import generate_report
from discord_ferry.state import MigrationState


def _make_config(tmp_path: Path) -> FerryConfig:
    return FerryConfig(
        export_dir=tmp_path,
        stoat_url="https://api.test",
        token="test-token",
        output_dir=tmp_path,
    )


def _make_export(
    guild_id: str = "111",
    guild_name: str = "Test Guild",
    channel_id: str = "222",
    channel_name: str = "general",
    message_count: int = 0,
    is_thread: bool = False,
) -> DCEExport:
    guild = DCEGuild(id=guild_id, name=guild_name)
    channel = DCEChannel(id=channel_id, type=0, name=channel_name)
    return DCEExport(
        guild=guild,
        channel=channel,
        messages=[],
        message_count=message_count,
        is_thread=is_thread,
    )


def test_generate_report_structure(tmp_path: Path) -> None:
    """Report contains all required top-level keys."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert "started_at" in report
    assert "completed_at" in report
    assert "duration_seconds" in report
    assert "source_guild" in report
    assert "target_server_id" in report
    assert "summary" in report
    assert "warnings" in report
    assert "errors" in report
    assert "maps" in report


def test_generate_report_summary_keys(tmp_path: Path) -> None:
    """Summary dict contains all required keys."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [_make_export()]

    report = generate_report(config, state, exports)
    summary = report["summary"]

    assert isinstance(summary, dict)
    assert "channels_created" in summary
    assert "roles_created" in summary
    assert "categories_created" in summary
    assert "messages_imported" in summary
    assert "messages_skipped" in summary
    assert "attachments_uploaded" in summary
    assert "attachments_skipped" in summary
    assert "emoji_created" in summary
    assert "reactions_added" in summary
    assert "pins_restored" in summary
    assert "threads_flattened" in summary
    assert "errors" in summary
    assert "warnings" in summary


def test_generate_report_counts(tmp_path: Path) -> None:
    """Summary counts match state data."""
    config = _make_config(tmp_path)
    state = MigrationState(
        channel_map={"d1": "s1", "d2": "s2"},
        role_map={"r1": "sr1"},
        category_map={"c1": "sc1", "c2": "sc2", "c3": "sc3"},
        message_map={"m1": "sm1", "m2": "sm2", "m3": "sm3"},
        upload_cache={"file1": "autumn1"},
        attachments_uploaded=1,
        emoji_map={"e1": "se1"},
        pending_pins=[("ch1", "msg1"), ("ch2", "msg2")],
        reactions_applied=5,
        pins_applied=2,
        errors=[{"phase": "messages", "context": "x", "message": "err"}],
        warnings=[{"phase": "structure", "context": "y", "message": "warn"}],
    )
    # total messages = 10, imported = 3, so skipped = 7
    exports = [_make_export(message_count=10)]

    report = generate_report(config, state, exports)
    summary = report["summary"]

    assert summary["channels_created"] == 2
    assert summary["roles_created"] == 1
    assert summary["categories_created"] == 3
    assert summary["messages_imported"] == 3
    assert summary["messages_skipped"] == 7
    assert summary["attachments_uploaded"] == 1
    assert summary["emoji_created"] == 1
    assert summary["reactions_added"] == 5
    assert summary["pins_restored"] == 2
    assert summary["errors"] == 1
    assert summary["warnings"] == 1


def test_generate_report_writes_file(tmp_path: Path) -> None:
    """Report file is written to output_dir."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    report_path = tmp_path / "migration_report.json"
    assert report_path.exists()

    with report_path.open(encoding="utf-8") as f:
        on_disk = json.load(f)

    assert on_disk["started_at"] == report["started_at"]
    assert on_disk["completed_at"] == report["completed_at"]
    assert on_disk["summary"] == report["summary"]


def test_generate_report_duration(tmp_path: Path) -> None:
    """Duration calculated from started_at and completed_at."""
    config = _make_config(tmp_path)
    state = MigrationState(
        started_at="2024-01-01T10:00:00",
        completed_at="2024-01-01T10:01:00",
    )
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["duration_seconds"] == 60


def test_generate_report_duration_zero_when_missing(tmp_path: Path) -> None:
    """Duration is 0 when started_at or completed_at is empty."""
    config = _make_config(tmp_path)
    state = MigrationState(started_at="", completed_at="")
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["duration_seconds"] == 0


def test_generate_report_duration_zero_when_only_started(tmp_path: Path) -> None:
    """Duration is 0 when only started_at is set."""
    config = _make_config(tmp_path)
    state = MigrationState(started_at="2024-01-01T10:00:00", completed_at="")
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["duration_seconds"] == 0


def test_generate_report_empty_exports(tmp_path: Path) -> None:
    """Report handles empty exports list gracefully."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports: list[DCEExport] = []

    report = generate_report(config, state, exports)

    assert report["source_guild"] == {"id": "", "name": ""}


def test_generate_report_source_guild_from_first_export(tmp_path: Path) -> None:
    """source_guild reflects the first export's guild metadata."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [
        _make_export(guild_id="999", guild_name="My Server"),
        _make_export(guild_id="888", guild_name="Other Server"),
    ]

    report = generate_report(config, state, exports)

    assert report["source_guild"] == {"id": "999", "name": "My Server"}


def test_generate_report_threads_counted(tmp_path: Path) -> None:
    """threads_flattened counts exports with is_thread=True."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [
        _make_export(channel_id="1", is_thread=False),
        _make_export(channel_id="2", is_thread=True),
        _make_export(channel_id="3", is_thread=False),
    ]

    report = generate_report(config, state, exports)

    assert report["summary"]["threads_flattened"] == 1


def test_generate_report_messages_skipped_multiple_exports(tmp_path: Path) -> None:
    """messages_skipped sums message_count across all exports."""
    config = _make_config(tmp_path)
    state = MigrationState(
        message_map={"m1": "sm1", "m2": "sm2"},
    )
    exports = [
        _make_export(channel_id="1", message_count=5),
        _make_export(channel_id="2", message_count=8),
    ]

    report = generate_report(config, state, exports)

    # total = 13, imported = 2, skipped = 11
    assert report["summary"]["messages_skipped"] == 11


def test_generate_report_maps_structure(tmp_path: Path) -> None:
    """maps dict contains channels, roles, and emoji keys."""
    config = _make_config(tmp_path)
    state = MigrationState(
        channel_map={"d1": "s1"},
        role_map={"r1": "sr1"},
        emoji_map={"e1": "se1"},
    )
    exports = [_make_export()]

    report = generate_report(config, state, exports)
    maps = report["maps"]

    assert isinstance(maps, dict)
    assert maps["channels"] == {"d1": "s1"}
    assert maps["roles"] == {"r1": "sr1"}
    assert maps["emoji"] == {"e1": "se1"}


def test_generate_report_target_server_id(tmp_path: Path) -> None:
    """target_server_id comes from state.stoat_server_id."""
    config = _make_config(tmp_path)
    state = MigrationState(stoat_server_id="stoat-abc-123")
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["target_server_id"] == "stoat-abc-123"


def test_generate_report_creates_output_dir(tmp_path: Path) -> None:
    """output_dir is created if it does not exist."""
    nested = tmp_path / "nested" / "output"
    config = FerryConfig(
        export_dir=tmp_path,
        stoat_url="https://api.test",
        token="test-token",
        output_dir=nested,
    )
    state = MigrationState()
    exports = [_make_export()]

    generate_report(config, state, exports)

    assert (nested / "migration_report.json").exists()


def test_generate_report_reactions_added(tmp_path: Path) -> None:
    """reactions_added equals state.reactions_applied counter."""
    config = _make_config(tmp_path)
    state = MigrationState(reactions_applied=3)
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["summary"]["reactions_added"] == 3


def test_generate_report_attachments_uploaded_uses_counter(tmp_path: Path) -> None:
    """attachments_uploaded uses state.attachments_uploaded counter, not upload_cache length."""
    config = _make_config(tmp_path)
    state = MigrationState(
        attachments_uploaded=10,
        upload_cache={"file1": "autumn1", "file2": "autumn2"},
    )
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    # Should use the counter, not len(upload_cache)
    assert report["summary"]["attachments_uploaded"] == 10


def test_generate_report_has_nonzero_duration(tmp_path: Path) -> None:
    """Report has positive duration when completed_at is set before generate_report."""
    config = _make_config(tmp_path)
    state = MigrationState(
        started_at="2024-01-01T10:00:00+00:00",
        completed_at="2024-01-01T10:05:00+00:00",
    )
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    assert report["completed_at"] != ""
    assert report["duration_seconds"] == 300


def test_checklist_with_permissions(tmp_path: Path) -> None:
    """Checklist includes permission review items when discord_metadata.json is present."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [_make_export()]

    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="2024-01-01T00:00:00",
        server_default_permissions=0,
        role_permissions={"r1": PermissionPair(allow=0, deny=0)},
        channel_metadata={},
    )
    save_discord_metadata(meta, tmp_path)

    report = generate_report(config, state, exports)

    checklist = report["checklist"]
    assert isinstance(checklist, list)
    tasks = [item["task"] for item in checklist]  # type: ignore[index]
    assert any("Review migrated role permissions" in t for t in tasks)
    assert any("Verify channel permission overrides" in t for t in tasks)
    assert not any("Set up role permissions manually" in t for t in tasks)


def test_checklist_without_permissions(tmp_path: Path) -> None:
    """Checklist includes manual permission setup item when discord_metadata.json is absent."""
    config = _make_config(tmp_path)
    state = MigrationState()
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    checklist = report["checklist"]
    assert isinstance(checklist, list)
    tasks = [item["task"] for item in checklist]  # type: ignore[index]
    assert any("Set up role permissions manually" in t for t in tasks)
    assert not any("Review migrated role permissions" in t for t in tasks)


def test_checklist_with_warnings(tmp_path: Path) -> None:
    """Checklist includes a warnings review item when state.warnings is non-empty."""
    config = _make_config(tmp_path)
    state = MigrationState(
        warnings=[
            {"phase": "messages", "context": "ch1", "message": "warn1"},
            {"phase": "messages", "context": "ch2", "message": "warn2"},
        ]
    )
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    checklist = report["checklist"]
    assert isinstance(checklist, list)
    tasks = [item["task"] for item in checklist]  # type: ignore[index]
    assert any("Review 2 warning(s)" in t for t in tasks)


def test_checklist_with_emoji(tmp_path: Path) -> None:
    """Checklist includes an emoji verification item when state.emoji_map is non-empty."""
    config = _make_config(tmp_path)
    state = MigrationState(emoji_map={"e1": "se1", "e2": "se2"})
    exports = [_make_export()]

    report = generate_report(config, state, exports)

    checklist = report["checklist"]
    assert isinstance(checklist, list)
    tasks = [item["task"] for item in checklist]  # type: ignore[index]
    assert any("Verify custom emoji" in t for t in tasks)
