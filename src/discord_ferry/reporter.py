"""Migration report generator."""

import json
from datetime import datetime
from pathlib import Path

from discord_ferry.config import FerryConfig
from discord_ferry.parser.models import DCEExport
from discord_ferry.state import MigrationState


def generate_report(
    config: FerryConfig,
    state: MigrationState,
    exports: list[DCEExport],
) -> dict[str, object]:
    """Generate a migration report and write it to output_dir/migration_report.json.

    Args:
        config: Ferry configuration, used for output_dir.
        state: Current migration state with all ID maps and logs.
        exports: List of parsed DCE exports, used for guild info and message counts.

    Returns:
        The report dict that was serialised to disk.
    """
    duration_seconds = _calculate_duration(state.started_at, state.completed_at)

    source_guild: dict[str, str]
    if exports:
        guild = exports[0].guild
        source_guild = {"id": guild.id, "name": guild.name}
    else:
        source_guild = {"id": "", "name": ""}

    total_messages = sum(e.message_count for e in exports)
    messages_imported = len(state.message_map)
    messages_skipped = max(0, total_messages - messages_imported)

    threads_flattened = sum(1 for e in exports if e.is_thread)

    report: dict[str, object] = {
        "started_at": state.started_at,
        "completed_at": state.completed_at,
        "duration_seconds": duration_seconds,
        "source_guild": source_guild,
        "target_server_id": state.stoat_server_id,
        "summary": {
            "channels_created": len(state.channel_map),
            "roles_created": len(state.role_map),
            "categories_created": len(state.category_map),
            "messages_imported": messages_imported,
            "messages_skipped": messages_skipped,
            "attachments_uploaded": state.attachments_uploaded,
            "attachments_skipped": state.attachments_skipped,
            "emoji_created": len(state.emoji_map),
            "reactions_added": state.reactions_applied,
            "pins_restored": state.pins_applied,
            "threads_flattened": threads_flattened,
            "errors": len(state.errors),
            "warnings": len(state.warnings),
        },
        "warnings": state.warnings,
        "errors": state.errors,
        "maps": {
            "channels": state.channel_map,
            "roles": state.role_map,
            "emoji": state.emoji_map,
        },
    }

    _write_report(config.output_dir, report)

    return report


def _calculate_duration(started_at: str, completed_at: str) -> float:
    if not started_at or not completed_at:
        return 0
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(completed_at)
        return (end - start).total_seconds()
    except ValueError:
        return 0


def _write_report(output_dir: Path, report: dict[str, object]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "migration_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
