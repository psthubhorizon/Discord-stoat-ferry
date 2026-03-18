"""Pre-creation review summary for blocking confirmation before migration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from discord_ferry.discord.metadata import DiscordMetadata
    from discord_ferry.parser.models import DCEExport


@dataclass
class ReviewSummary:
    """Summary of what will be created during migration."""

    server_name: str
    role_count: int
    category_count: int
    channel_count: int
    emoji_count: int
    message_count: int
    thread_count: int
    has_permissions: bool
    nsfw_channel_count: int
    threads_filtered: int = 0
    user_override_count: int = 0
    warnings: list[str] = field(default_factory=list)


def build_review_summary(
    exports: list[DCEExport],
    discord_metadata: DiscordMetadata | None = None,
) -> ReviewSummary:
    """Build a review summary from parsed exports and optional Discord metadata.

    Args:
        exports: Parsed DCE exports.
        discord_metadata: Optional Discord metadata (for permission/NSFW info).

    Returns:
        ReviewSummary with counts and metadata availability info.
    """
    if not exports:
        return ReviewSummary(
            server_name="(empty)",
            role_count=0,
            category_count=0,
            channel_count=0,
            emoji_count=0,
            message_count=0,
            thread_count=0,
            has_permissions=False,
            nsfw_channel_count=0,
            warnings=["No exports found"],
        )

    server_name = exports[0].guild.name

    # Count unique roles, categories, channels
    role_ids: set[str] = set()
    category_ids: set[str] = set()
    channel_ids: set[str] = set()
    emoji_ids: set[str] = set()
    thread_count = 0
    total_messages = 0

    for export in exports:
        if export.channel.type != 4 and export.channel.id not in channel_ids:  # Skip categories
            channel_ids.add(export.channel.id)
        if export.channel.category_id:
            category_ids.add(export.channel.category_id)
        if export.is_thread:
            thread_count += 1
        total_messages += export.message_count
        for msg in export.messages:
            for role in msg.author.roles:
                role_ids.add(role.id)
            for reaction in msg.reactions:
                if reaction.emoji.id:
                    emoji_ids.add(reaction.emoji.id)

    # NSFW info and user override count from metadata
    nsfw_count = 0
    user_override_count = 0
    has_permissions = discord_metadata is not None
    if discord_metadata:
        for ch_meta in discord_metadata.channel_metadata.values():
            if ch_meta.nsfw:
                nsfw_count += 1
        user_override_count = len(discord_metadata.user_override_channels)

    # Build warnings
    warnings: list[str] = []
    if not has_permissions:
        warnings.append("No Discord token — permissions will not be migrated")
    if len(channel_ids) > 200:
        warnings.append(f"Channel count ({len(channel_ids)}) exceeds Stoat limit of 200")
    if len(emoji_ids) > 100:
        warnings.append(f"Emoji count ({len(emoji_ids)}) exceeds Stoat limit of 100")

    # Filter out @everyone role (id == guild_id)
    guild_id = exports[0].guild.id
    role_ids.discard(guild_id)

    return ReviewSummary(
        server_name=server_name,
        role_count=len(role_ids),
        category_count=len(category_ids),
        channel_count=len(channel_ids),
        emoji_count=len(emoji_ids),
        message_count=total_messages,
        thread_count=thread_count,
        has_permissions=has_permissions,
        nsfw_channel_count=nsfw_count,
        user_override_count=user_override_count,
        warnings=warnings,
    )
