"""Tests for Discord metadata persistence."""

from pathlib import Path

import aiohttp

from discord_ferry.discord import fetch_and_translate_guild_metadata
from discord_ferry.discord.metadata import (
    ChannelMeta,
    DiscordMetadata,
    PermissionPair,
    RoleOverride,
    load_discord_metadata,
    save_discord_metadata,
)


def test_save_load_roundtrip(tmp_path: Path) -> None:
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="2026-03-01T00:00:00Z",
        server_default_permissions=1_048_576,
        role_permissions={
            "role1": PermissionPair(allow=4_194_304, deny=0),
        },
        channel_metadata={
            "ch1": ChannelMeta(
                nsfw=True,
                default_override=PermissionPair(allow=4_194_304, deny=8_388_608),
                role_overrides=[
                    RoleOverride(discord_role_id="role1", allow=4_194_304, deny=0),
                ],
            ),
        },
    )
    save_discord_metadata(meta, tmp_path)
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert loaded.guild_id == "111"
    assert loaded.server_default_permissions == 1_048_576
    assert loaded.role_permissions["role1"].allow == 4_194_304
    assert loaded.channel_metadata["ch1"].nsfw is True
    assert loaded.channel_metadata["ch1"].default_override is not None
    assert loaded.channel_metadata["ch1"].default_override.deny == 8_388_608
    assert len(loaded.channel_metadata["ch1"].role_overrides) == 1
    assert loaded.channel_metadata["ch1"].role_overrides[0].discord_role_id == "role1"


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_discord_metadata(tmp_path) is None


def test_save_creates_directory(tmp_path: Path) -> None:
    nested = tmp_path / "deep" / "dir"
    meta = DiscordMetadata(
        guild_id="x",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
    )
    save_discord_metadata(meta, nested)
    assert (nested / "discord_metadata.json").exists()


def test_empty_metadata_roundtrip(tmp_path: Path) -> None:
    meta = DiscordMetadata(
        guild_id="empty",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
    )
    save_discord_metadata(meta, tmp_path)
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert loaded.role_permissions == {}
    assert loaded.channel_metadata == {}


def test_channel_without_overrides(tmp_path: Path) -> None:
    meta = DiscordMetadata(
        guild_id="g",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={
            "ch1": ChannelMeta(nsfw=False),
        },
    )
    save_discord_metadata(meta, tmp_path)
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert loaded.channel_metadata["ch1"].default_override is None
    assert loaded.channel_metadata["ch1"].role_overrides == []


_DISCORD_API = "https://discord.com/api/v10"
_GUILD_ID = "999000000000000001"


async def test_everyone_deny_view_channel_produces_stoat_deny_bit() -> None:
    """Discord @everyone VIEW_CHANNEL deny -> Stoat ViewChannel deny bit."""
    from aioresponses import aioresponses

    discord_view_channel = 1 << 10  # Discord VIEW_CHANNEL bit
    stoat_view_channel = 1 << 20  # Stoat ViewChannel bit

    channel_id = "555000000000000001"

    mock_roles = [
        {
            "id": _GUILD_ID,  # @everyone role id == guild_id
            "name": "@everyone",
            "permissions": "0",
            "position": 0,
            "color": 0,
            "hoist": False,
            "managed": False,
        },
    ]

    mock_channels = [
        {
            "id": channel_id,
            "name": "private-channel",
            "type": 0,
            "nsfw": False,
            "permission_overwrites": [
                {
                    "id": _GUILD_ID,  # @everyone override
                    "type": 0,  # role type
                    "allow": "0",
                    "deny": str(discord_view_channel),
                },
            ],
        },
    ]

    with aioresponses() as m:
        m.get(f"{_DISCORD_API}/guilds/{_GUILD_ID}/roles", payload=mock_roles)
        m.get(f"{_DISCORD_API}/guilds/{_GUILD_ID}/channels", payload=mock_channels)

        async with aiohttp.ClientSession() as session:
            meta = await fetch_and_translate_guild_metadata(session, "test-token", _GUILD_ID)

    ch_meta = meta.channel_metadata[channel_id]
    assert ch_meta.default_override is not None, "Expected default_override for @everyone deny"
    assert ch_meta.default_override.deny & stoat_view_channel, (
        f"Expected Stoat ViewChannel deny bit (1<<20), got {ch_meta.default_override.deny}"
    )


def test_user_override_channels_roundtrip(tmp_path: Path) -> None:
    """user_override_channels persists through save/load cycle."""
    overrides = [
        {"channel_id": "ch1", "channel_name": "general", "override_count": 3},
        {"channel_id": "ch2", "channel_name": "mods", "override_count": 1},
    ]
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="2026-03-01T00:00:00Z",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
        user_override_channels=overrides,
    )
    save_discord_metadata(meta, tmp_path)
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert len(loaded.user_override_channels) == 2
    assert loaded.user_override_channels[0]["channel_id"] == "ch1"
    assert loaded.user_override_channels[0]["override_count"] == 3
    assert loaded.user_override_channels[1]["channel_name"] == "mods"


def test_user_override_channels_empty_by_default(tmp_path: Path) -> None:
    """user_override_channels defaults to empty list."""
    meta = DiscordMetadata(
        guild_id="g",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
    )
    assert meta.user_override_channels == []
    save_discord_metadata(meta, tmp_path)
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert loaded.user_override_channels == []


def test_user_override_channels_backward_compat(tmp_path: Path) -> None:
    """Loading old metadata without user_override_channels field returns empty list."""
    import json

    old_data = {
        "guild_id": "111",
        "fetched_at": "t",
        "server_default_permissions": 0,
        "role_permissions": {},
        "channel_metadata": {},
        # No user_override_channels key — old format
    }
    (tmp_path / "discord_metadata.json").write_text(json.dumps(old_data), encoding="utf-8")
    loaded = load_discord_metadata(tmp_path)
    assert loaded is not None
    assert loaded.user_override_channels == []


async def test_user_overrides_counted_in_fetch() -> None:
    """fetch_and_translate_guild_metadata counts user overrides per channel."""
    from aioresponses import aioresponses

    guild_id = "999000000000000001"

    mock_roles = [
        {
            "id": guild_id,
            "name": "@everyone",
            "permissions": "0",
            "position": 0,
            "color": 0,
            "hoist": False,
            "managed": False,
        },
    ]

    mock_channels = [
        {
            "id": "ch1",
            "name": "general",
            "type": 0,
            "nsfw": False,
            "permission_overwrites": [
                {"id": "user1", "type": 1, "allow": "0", "deny": "1024"},
                {"id": "user2", "type": 1, "allow": "0", "deny": "1024"},
                {"id": guild_id, "type": 0, "allow": "0", "deny": "0"},
            ],
        },
        {
            "id": "ch2",
            "name": "no-overrides",
            "type": 0,
            "nsfw": False,
            "permission_overwrites": [],
        },
    ]

    with aioresponses() as m:
        m.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/roles",
            payload=mock_roles,
        )
        m.get(
            f"https://discord.com/api/v10/guilds/{guild_id}/channels",
            payload=mock_channels,
        )

        async with aiohttp.ClientSession() as session:
            meta = await fetch_and_translate_guild_metadata(session, "test-token", guild_id)

    assert len(meta.user_override_channels) == 1
    assert meta.user_override_channels[0]["channel_id"] == "ch1"
    assert meta.user_override_channels[0]["channel_name"] == "general"
    assert meta.user_override_channels[0]["override_count"] == 2
