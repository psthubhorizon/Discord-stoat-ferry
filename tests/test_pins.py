"""Tests for the pins migration phase (Phase 10)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

from discord_ferry.config import FerryConfig
from discord_ferry.migrator.pins import run_pins
from discord_ferry.state import MigrationState

BASE_URL = "https://api.test"
TOKEN = "test-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config() -> FerryConfig:
    from pathlib import Path

    return FerryConfig(export_dir=Path("/tmp"), stoat_url=BASE_URL, token=TOKEN)


def _make_state(pending: list[tuple[str, str]] | None = None) -> MigrationState:
    state = MigrationState()
    state.stoat_server_id = "srv1"
    if pending is not None:
        state.pending_pins = pending
    return state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_run_pins_empty_pending() -> None:
    """Emits 'completed' immediately when there are no pending pins."""
    events: list[Any] = []
    config = _make_config()
    state = _make_state(pending=[])

    await run_pins(config, state, [], events.append)

    statuses = [e.status for e in events]
    assert "completed" in statuses
    assert state.pins_applied == 0


async def test_run_pins_successful_pin() -> None:
    """Pins a message successfully and increments the counter."""
    events: list[Any] = []
    config = _make_config()
    state = _make_state(pending=[("ch1", "msg1")])

    mock_pin = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.pins.api_pin_message", new=mock_pin),
        patch("discord_ferry.migrator.pins.asyncio.sleep", new=AsyncMock()),
    ):
        await run_pins(config, state, [], events.append)

    mock_pin.assert_awaited_once_with(
        mock_pin.call_args[0][0],  # session
        BASE_URL,
        TOKEN,
        "ch1",
        "msg1",
    )
    assert state.pins_applied == 1


async def test_run_pins_error_handling() -> None:
    """Logs error for a failed pin but continues processing remaining pins."""
    events: list[Any] = []
    config = _make_config()
    pending = [
        ("ch1", "msg1"),  # will fail
        ("ch1", "msg2"),  # should succeed
    ]
    state = _make_state(pending=pending)

    call_count = 0

    async def side_effect(*args: Any, **kwargs: Any) -> dict[str, object]:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("pin failed")
        return {}

    with (
        patch("discord_ferry.migrator.pins.api_pin_message", new=side_effect),
        patch("discord_ferry.migrator.pins.asyncio.sleep", new=AsyncMock()),
    ):
        await run_pins(config, state, [], events.append)

    assert len(state.errors) == 1
    assert "pin failed" in state.errors[0]["message"]
    assert state.pins_applied == 1


async def test_run_pins_counter_increment() -> None:
    """pins_applied increments correctly for each successful pin."""
    events: list[Any] = []
    config = _make_config()
    pending = [("ch1", f"msg{i}") for i in range(4)]
    state = _make_state(pending=pending)

    mock_pin = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.pins.api_pin_message", new=mock_pin),
        patch("discord_ferry.migrator.pins.asyncio.sleep", new=AsyncMock()),
    ):
        await run_pins(config, state, [], events.append)

    assert state.pins_applied == 4
    completed = [e for e in events if e.status == "completed"]
    assert completed
    assert "4" in completed[0].message


async def test_run_pins_emits_progress_events() -> None:
    """Progress events are emitted with correct current/total values."""
    events: list[Any] = []
    config = _make_config()
    pending = [("ch1", "msgA"), ("ch2", "msgB"), ("ch3", "msgC")]
    state = _make_state(pending=pending)

    mock_pin = AsyncMock(return_value={})
    with (
        patch("discord_ferry.migrator.pins.api_pin_message", new=mock_pin),
        patch("discord_ferry.migrator.pins.asyncio.sleep", new=AsyncMock()),
    ):
        await run_pins(config, state, [], events.append)

    progress_events = [e for e in events if e.status == "progress"]
    assert len(progress_events) == 3
    assert progress_events[0].current == 1
    assert progress_events[0].total == 3
    assert progress_events[2].current == 3
