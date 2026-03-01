"""Migration report generator."""

import json
from datetime import datetime
from pathlib import Path

from discord_ferry.config import FerryConfig
from discord_ferry.discord.metadata import load_discord_metadata
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

    # Build post-migration checklist
    discord_meta = load_discord_metadata(config.output_dir)
    checklist = _build_checklist(state, has_permissions=discord_meta is not None)
    report["checklist"] = checklist

    _write_report(config.output_dir, report)

    return report


def _build_checklist(
    state: MigrationState,
    has_permissions: bool,
) -> list[dict[str, str]]:
    """Build a dynamic post-migration checklist of manual steps.

    Args:
        state: Migration state with maps and counters.
        has_permissions: Whether Discord permissions were migrated.

    Returns:
        List of checklist items with 'task' and 'status' keys.
    """
    items: list[dict[str, str]] = []

    # Always present items
    items.append(
        {
            "task": "Verify channel order and category assignments in Stoat",
            "status": "todo",
        }
    )
    items.append(
        {
            "task": "Check message formatting in a few channels",
            "status": "todo",
        }
    )

    # Permission-dependent items
    if has_permissions:
        items.append(
            {
                "task": "Review migrated role permissions in Stoat server settings",
                "status": "todo",
            }
        )
        items.append(
            {
                "task": "Verify channel permission overrides are correct",
                "status": "todo",
            }
        )
    else:
        items.append(
            {
                "task": "Set up role permissions manually (not migrated — no Discord token)",
                "status": "todo",
            }
        )

    # Conditional items based on state
    if state.emoji_map:
        items.append(
            {
                "task": "Verify custom emoji are rendering correctly",
                "status": "todo",
            }
        )

    if state.warnings:
        items.append(
            {
                "task": f"Review {len(state.warnings)} warning(s) in the report",
                "status": "todo",
            }
        )

    if state.errors:
        items.append(
            {
                "task": (
                    f"Investigate {len(state.errors)} error(s) — some content may not have migrated"
                ),
                "status": "todo",
            }
        )

    # Final items
    items.append(
        {
            "task": "Invite members to the new Stoat server",
            "status": "todo",
        }
    )

    return items


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
