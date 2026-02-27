"""Tests for the reactions migration phase (Phase 9)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from discord_ferry.config import FerryConfig
from discord_ferry.migrator.reactions import run_reactions
from discord_ferry.state import MigrationState

BASE_URL = "https://api.test"
TOKEN = "test-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> FerryConfig:
    from pathlib import Path

    return FerryConfig(export_dir=Path("/tmp"), stoat_url=BASE_URL, token=TOKEN)


def _make_state(pending: list[dict[str, object]] | None = None) -> MigrationState:
    state = MigrationState()
    state.stoat_server_id = "srv1"
    if pending is not None:
        state.pending_reactions = pending
    return state


def _reaction(
    channel_id: str = "ch1",
    message_id: str = "msg1",
    emoji: str = "\U0001f44d",
) -> dict[str, object]:
    return {"channel_id": channel_id, "message_id": message_id, "emoji": emoji}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_reactions_empty_pending() -> None:
    """Emits 'completed' immediately when there are no pending reactions."""
    events: list[Any] = []
    config = _make_config()
    state = _make_state(pending=[])

    await run_reactions(config, state, [], events.append)

    statuses = [e.status for e in events]
    assert "completed" in statuses
    assert state.reactions_applied == 0


async def test_run_reactions_unicode_emoji() -> None:
    """Applies a Unicode emoji reaction successfully."""
    events: list[Any] = []
    config = _make_config()
    state = _make_state(pending=[_reaction(emoji="\U0001f44d")])

    mock_add = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.reactions.api_add_reaction", new=mock_add),
        patch("discord_ferry.migrator.reactions.asyncio.sleep", new=AsyncMock()),
    ):
        await run_reactions(config, state, [], events.append)

    mock_add.assert_awaited_once()
    assert state.reactions_applied == 1


async def test_run_reactions_custom_emoji() -> None:
    """Applies a custom emoji ID reaction successfully."""
    events: list[Any] = []
    config = _make_config()
    state = _make_state(pending=[_reaction(emoji="customEmojiId")])

    mock_add = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.reactions.api_add_reaction", new=mock_add),
        patch("discord_ferry.migrator.reactions.asyncio.sleep", new=AsyncMock()),
    ):
        await run_reactions(config, state, [], events.append)

    mock_add.assert_awaited_once()
    assert state.reactions_applied == 1


async def test_run_reactions_per_message_limit() -> None:
    """Stops adding reactions once a message reaches 20 (Stoat hard limit)."""
    events: list[Any] = []
    config = _make_config()
    # 25 reactions all on the same message.
    pending = [_reaction(message_id="msg1", emoji=f"e{i}") for i in range(25)]
    state = _make_state(pending=pending)

    mock_add = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.reactions.api_add_reaction", new=mock_add),
        patch("discord_ferry.migrator.reactions.asyncio.sleep", new=AsyncMock()),
    ):
        await run_reactions(config, state, [], events.append)

    # Only 20 should be applied.
    assert state.reactions_applied == 20
    assert mock_add.await_count == 20


async def test_run_reactions_error_handling() -> None:
    """Logs error for a failed reaction but continues processing remaining reactions."""
    events: list[Any] = []
    config = _make_config()
    pending = [
        _reaction(message_id="msg1"),  # will fail
        _reaction(message_id="msg2"),  # should succeed
    ]
    state = _make_state(pending=pending)

    call_count = 0

    async def side_effect(*args: Any, **kwargs: Any) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("network error")
        return {}

    with (
        patch("discord_ferry.migrator.reactions.api_add_reaction", new=side_effect),
        patch("discord_ferry.migrator.reactions.asyncio.sleep", new=AsyncMock()),
    ):
        await run_reactions(config, state, [], events.append)

    assert len(state.errors) == 1
    assert "network error" in state.errors[0]["message"]
    assert state.reactions_applied == 1


async def test_run_reactions_counter_increment() -> None:
    """reactions_applied increments correctly for each successful reaction."""
    events: list[Any] = []
    config = _make_config()
    pending = [_reaction(message_id=f"msg{i}") for i in range(5)]
    state = _make_state(pending=pending)

    mock_add = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.reactions.api_add_reaction", new=mock_add),
        patch("discord_ferry.migrator.reactions.asyncio.sleep", new=AsyncMock()),
    ):
        await run_reactions(config, state, [], events.append)

    assert state.reactions_applied == 5
    completed = [e for e in events if e.status == "completed"]
    assert completed
    assert "5" in completed[0].message
