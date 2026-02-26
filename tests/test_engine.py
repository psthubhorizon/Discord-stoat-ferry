"""Tests for the migration engine orchestrator."""

from pathlib import Path

import pytest

from discord_ferry.config import FerryConfig
from discord_ferry.core.engine import PHASE_ORDER, run_migration
from discord_ferry.core.events import EventCallback, MigrationEvent
from discord_ferry.state import MigrationState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _make_config(tmp_path: Path, **overrides: object) -> FerryConfig:
    defaults: dict[str, object] = {
        "export_dir": FIXTURES_DIR,
        "stoat_url": "https://api.test",
        "token": "test-token",
        "output_dir": tmp_path,
    }
    defaults.update(overrides)
    return FerryConfig(**defaults)  # type: ignore[arg-type]


async def test_run_migration_validates_exports(tmp_path: Path) -> None:
    """Engine parses exports and emits validate events."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path)
    state = await run_migration(config, events.append)
    validate_events = [e for e in events if e.phase == "validate"]
    assert any(e.status == "started" for e in validate_events)
    assert any(e.status == "completed" for e in validate_events)
    # Validation warnings should be stored in state for the report
    warning_events = [e for e in validate_events if e.status == "warning"]
    assert len(state.warnings) == len(warning_events)
    # Author names should be populated from the fixture exports
    assert len(state.author_names) > 0


async def test_run_migration_emits_phase_events(tmp_path: Path) -> None:
    """Engine emits started/completed for each injected phase."""
    events: list[MigrationEvent] = []
    called: list[str] = []

    async def mock_phase(
        config: FerryConfig,
        state: MigrationState,
        exports: list,
        emit: EventCallback,
    ) -> None:
        called.append("connect")

    config = _make_config(tmp_path)
    await run_migration(config, events.append, phase_overrides={"connect": mock_phase})
    assert "connect" in called
    connect_events = [e for e in events if e.phase == "connect"]
    assert any(e.status == "started" for e in connect_events)
    assert any(e.status == "completed" for e in connect_events)


async def test_run_migration_phases_called_in_order(tmp_path: Path) -> None:
    """Mock phases are called in the correct order."""
    call_order: list[str] = []

    def make_phase(name: str):
        async def fn(
            config: FerryConfig,
            state: MigrationState,
            exports: list,
            emit: EventCallback,
        ) -> None:
            call_order.append(name)

        return fn

    phase_names = ["connect", "server", "roles", "categories", "channels"]
    overrides = {name: make_phase(name) for name in phase_names}

    config = _make_config(tmp_path)
    await run_migration(config, lambda e: None, phase_overrides=overrides)
    assert call_order == phase_names


async def test_run_migration_skip_messages(tmp_path: Path) -> None:
    """skip_messages config flag skips the messages phase."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path, skip_messages=True)
    await run_migration(config, events.append)
    msg_events = [e for e in events if e.phase == "messages"]
    assert any(e.status == "skipped" for e in msg_events)


async def test_run_migration_skip_emoji(tmp_path: Path) -> None:
    """skip_emoji config flag skips the emoji phase."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path, skip_emoji=True)
    await run_migration(config, events.append)
    emoji_events = [e for e in events if e.phase == "emoji"]
    assert any(e.status == "skipped" for e in emoji_events)


async def test_run_migration_skip_reactions(tmp_path: Path) -> None:
    """skip_reactions config flag skips the reactions phase."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path, skip_reactions=True)
    await run_migration(config, events.append)
    reaction_events = [e for e in events if e.phase == "reactions"]
    assert any(e.status == "skipped" for e in reaction_events)


async def test_run_migration_saves_state(tmp_path: Path) -> None:
    """State file exists after migration completes."""
    config = _make_config(tmp_path)
    await run_migration(config, lambda e: None)
    assert (tmp_path / "state.json").exists()


async def test_run_migration_resume_skips_completed(tmp_path: Path) -> None:
    """On resume, phases before current_phase are skipped."""
    from discord_ferry.state import save_state

    # Save state with current_phase = "channels"
    prior_state = MigrationState(current_phase="channels", started_at="2024-01-01T00:00:00+00:00")
    save_state(prior_state, tmp_path)

    events: list[MigrationEvent] = []
    config = _make_config(tmp_path, resume=True)
    await run_migration(config, events.append)

    # connect, server, roles, categories should all be skipped
    for phase in ["connect", "server", "roles", "categories"]:
        phase_events = [e for e in events if e.phase == phase]
        assert any(e.status == "skipped" for e in phase_events), f"{phase} should be skipped"


async def test_run_migration_phase_error(tmp_path: Path) -> None:
    """Engine catches phase exceptions and raises MigrationError."""
    from discord_ferry.errors import MigrationError

    async def failing_phase(
        config: FerryConfig,
        state: MigrationState,
        exports: list,
        emit: EventCallback,
    ) -> None:
        raise RuntimeError("Something broke")

    config = _make_config(tmp_path)
    with pytest.raises(MigrationError, match="connect"):
        await run_migration(config, lambda e: None, phase_overrides={"connect": failing_phase})


async def test_run_migration_phase_error_recorded_in_state(tmp_path: Path) -> None:
    """Phase errors are recorded in state.errors before raising."""
    from discord_ferry.errors import MigrationError

    captured_state: list[MigrationState] = []

    async def failing_phase(
        config: FerryConfig,
        state: MigrationState,
        exports: list,
        emit: EventCallback,
    ) -> None:
        captured_state.append(state)
        raise RuntimeError("boom")

    config = _make_config(tmp_path)
    with pytest.raises(MigrationError):
        await run_migration(config, lambda e: None, phase_overrides={"connect": failing_phase})

    assert len(captured_state) == 1
    state = captured_state[0]
    assert any(e["phase"] == "connect" for e in state.errors)


async def test_run_migration_builds_author_names(tmp_path: Path) -> None:
    """Author names are populated from export data, preferring nickname."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path)
    state = await run_migration(config, events.append)
    # simple_channel.json has alice (id 400000000000000001) with nickname "Alice"
    assert "400000000000000001" in state.author_names
    assert state.author_names["400000000000000001"] == "Alice"


async def test_run_migration_report_generated(tmp_path: Path) -> None:
    """Report file exists after migration."""
    config = _make_config(tmp_path)
    await run_migration(config, lambda e: None)
    assert (tmp_path / "migration_report.json").exists()


async def test_run_migration_report_events_emitted(tmp_path: Path) -> None:
    """Engine emits started and completed events for the report phase."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path)
    await run_migration(config, events.append)
    report_events = [e for e in events if e.phase == "report"]
    assert any(e.status == "started" for e in report_events)
    assert any(e.status == "completed" for e in report_events)


async def test_run_migration_returns_migration_state(tmp_path: Path) -> None:
    """run_migration returns a MigrationState instance."""
    config = _make_config(tmp_path)
    result = await run_migration(config, lambda e: None)
    assert isinstance(result, MigrationState)


async def test_run_migration_creates_output_dir(tmp_path: Path) -> None:
    """Engine creates the output directory if it doesn't exist."""
    nested_output = tmp_path / "deep" / "nested" / "output"
    config = _make_config(tmp_path, output_dir=nested_output)
    await run_migration(config, lambda e: None)
    assert nested_output.exists()


async def test_run_migration_state_has_timestamps(tmp_path: Path) -> None:
    """Completed state has non-empty started_at and completed_at."""
    config = _make_config(tmp_path)
    state = await run_migration(config, lambda e: None)
    assert state.started_at != ""
    assert state.completed_at != ""


async def test_run_migration_unimplemented_phases_skipped(tmp_path: Path) -> None:
    """Phases without implementations emit a 'Not yet implemented' skipped event."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path)
    # No phase_overrides — all phases default to no-op skipped
    await run_migration(config, events.append)
    skipped_events = [e for e in events if e.status == "skipped"]
    # All of the runnable phases (2-10) should be skipped
    skipped_phases = {e.phase for e in skipped_events}
    for phase in PHASE_ORDER[1:-1]:
        assert phase in skipped_phases, f"{phase} should be skipped when unimplemented"


async def test_run_migration_validate_total_in_event(tmp_path: Path) -> None:
    """The validate completed event carries the total message count."""
    events: list[MigrationEvent] = []
    config = _make_config(tmp_path)
    await run_migration(config, events.append)
    completed = next((e for e in events if e.phase == "validate" and e.status == "completed"), None)
    assert completed is not None
    assert completed.total > 0
