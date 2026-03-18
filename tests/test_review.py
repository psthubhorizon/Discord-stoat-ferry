"""Tests for pre-creation review summary."""

from __future__ import annotations

from discord_ferry.discord.metadata import ChannelMeta, DiscordMetadata, PermissionPair
from discord_ferry.parser.models import (
    DCEAuthor,
    DCEChannel,
    DCEExport,
    DCEGuild,
    DCEMessage,
    DCERole,
)
from discord_ferry.review import ReviewSummary, build_review_summary


def _make_export(
    guild_id: str = "111",
    guild_name: str = "Test",
    channel_id: str = "ch1",
    channel_name: str = "general",
    channel_type: int = 0,
    category_id: str = "cat1",
    is_thread: bool = False,
    message_count: int = 10,
    messages: list[DCEMessage] | None = None,
) -> DCEExport:
    guild = DCEGuild(id=guild_id, name=guild_name, icon_url="")
    channel = DCEChannel(
        id=channel_id,
        type=channel_type,
        name=channel_name,
        category_id=category_id,
        category="General",
    )
    return DCEExport(
        guild=guild,
        channel=channel,
        messages=messages or [],
        message_count=message_count,
        is_thread=is_thread,
    )


def test_basic_summary() -> None:
    exports = [
        _make_export(channel_id="ch1", message_count=100),
        _make_export(channel_id="ch2", message_count=50),
    ]
    summary = build_review_summary(exports)
    assert summary.server_name == "Test"
    assert summary.channel_count == 2
    assert summary.message_count == 150
    assert summary.has_permissions is False
    assert "permissions" in summary.warnings[0].lower()


def test_with_metadata() -> None:
    exports = [_make_export()]
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={"r1": PermissionPair(allow=1, deny=0)},
        channel_metadata={
            "ch1": ChannelMeta(nsfw=True),
            "ch2": ChannelMeta(nsfw=False),
        },
    )
    summary = build_review_summary(exports, discord_metadata=meta)
    assert summary.has_permissions is True
    assert summary.nsfw_channel_count == 1
    assert not any("permissions" in w.lower() for w in summary.warnings)


def test_empty_exports() -> None:
    summary = build_review_summary([])
    assert summary.server_name == "(empty)"
    assert summary.channel_count == 0
    assert "No exports found" in summary.warnings


def test_thread_counting() -> None:
    exports = [
        _make_export(channel_id="ch1", is_thread=False),
        _make_export(channel_id="th1", is_thread=True),
        _make_export(channel_id="th2", is_thread=True),
    ]
    summary = build_review_summary(exports)
    assert summary.thread_count == 2
    assert summary.channel_count == 3


def test_role_counting_excludes_everyone() -> None:
    role = DCERole(id="r1", name="Admin")
    everyone = DCERole(id="111", name="@everyone")
    msg = DCEMessage(
        id="m1",
        type="Default",
        timestamp="t",
        content="hi",
        author=DCEAuthor(id="u1", name="User", roles=[role, everyone]),
    )
    exports = [_make_export(guild_id="111", messages=[msg])]
    summary = build_review_summary(exports)
    assert summary.role_count == 1  # @everyone excluded


def test_returns_review_summary_type() -> None:
    exports = [_make_export()]
    summary = build_review_summary(exports)
    assert isinstance(summary, ReviewSummary)


def test_category_counting() -> None:
    exports = [
        _make_export(channel_id="ch1", category_id="cat1"),
        _make_export(channel_id="ch2", category_id="cat1"),  # same category
        _make_export(channel_id="ch3", category_id="cat2"),  # different category
    ]
    summary = build_review_summary(exports)
    assert summary.category_count == 2
    assert summary.channel_count == 3


def test_category_type_channel_excluded_from_channel_count() -> None:
    exports = [
        _make_export(channel_id="ch1", channel_type=0),  # text channel
        _make_export(channel_id="cat1", channel_type=4),  # category — should NOT count
    ]
    summary = build_review_summary(exports)
    assert summary.channel_count == 1


def test_channel_count_warning_at_limit() -> None:
    # Create 201 unique channels
    exports = [_make_export(channel_id=f"ch{i}", category_id="") for i in range(201)]
    summary = build_review_summary(exports)
    assert any("200" in w for w in summary.warnings)


def test_no_warnings_when_metadata_provided() -> None:
    exports = [_make_export()]
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
    )
    summary = build_review_summary(exports, discord_metadata=meta)
    assert summary.has_permissions is True
    # No "No Discord token" warning
    assert not any("permissions" in w.lower() for w in summary.warnings)


def test_user_override_count_from_metadata() -> None:
    """ReviewSummary.user_override_count populated from metadata."""
    exports = [_make_export()]
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
        user_override_channels=[
            {"channel_id": "ch1", "channel_name": "general", "override_count": 3},
            {"channel_id": "ch2", "channel_name": "mods", "override_count": 1},
        ],
    )
    summary = build_review_summary(exports, discord_metadata=meta)
    assert summary.user_override_count == 2


def test_user_override_count_zero_without_metadata() -> None:
    """ReviewSummary.user_override_count is 0 when no metadata provided."""
    exports = [_make_export()]
    summary = build_review_summary(exports)
    assert summary.user_override_count == 0


def test_user_override_count_zero_when_no_overrides() -> None:
    """ReviewSummary.user_override_count is 0 when metadata has no user overrides."""
    exports = [_make_export()]
    meta = DiscordMetadata(
        guild_id="111",
        fetched_at="t",
        server_default_permissions=0,
        role_permissions={},
        channel_metadata={},
    )
    summary = build_review_summary(exports, discord_metadata=meta)
    assert summary.user_override_count == 0
