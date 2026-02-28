"""Tests for CLI entry point."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from discord_ferry.cli import main
from discord_ferry.errors import MigrationError
from discord_ferry.state import MigrationState

if TYPE_CHECKING:
    from discord_ferry.config import FerryConfig

FIXTURES_DIR = str(Path(__file__).parent / "fixtures")


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------


def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Migrate a Discord server" in result.output


def test_migrate_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["migrate", "--help"])
    assert result.exit_code == 0
    assert "--stoat-url" in result.output


def test_validate_help(runner: CliRunner) -> None:
    result = runner.invoke(main, ["validate", "--help"])
    assert result.exit_code == 0
    assert "EXPORT_DIR" in result.output


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def test_validate_basic(runner: CliRunner) -> None:
    # Fixtures include markdown_rendered.json which triggers a critical warning,
    # so exit code is 1.  We still verify the table and warnings render.
    result = runner.invoke(main, ["validate", FIXTURES_DIR])
    assert result.exit_code == 1
    assert "Export Summary" in result.output
    assert "Messages" in result.output
    assert "Critical warnings found" in result.output


def test_validate_empty_dir(runner: CliRunner, tmp_path: Path) -> None:
    result = runner.invoke(main, ["validate", str(tmp_path)])
    assert result.exit_code == 1
    assert "No valid DCE JSON files" in result.output


# ---------------------------------------------------------------------------
# Migrate — argument validation
# ---------------------------------------------------------------------------


def test_migrate_missing_url(runner: CliRunner) -> None:
    result = runner.invoke(
        main,
        ["migrate", "--export-dir", FIXTURES_DIR, "--token", "test-token"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "--stoat-url is required" in result.output


def test_migrate_missing_token(runner: CliRunner) -> None:
    result = runner.invoke(
        main,
        ["migrate", "--export-dir", FIXTURES_DIR, "--stoat-url", "http://localhost"],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "--token is required" in result.output


# ---------------------------------------------------------------------------
# Migrate — engine integration
# ---------------------------------------------------------------------------


def _make_mock_engine() -> AsyncMock:
    """Create a mock run_migration that returns a minimal MigrationState."""
    mock = AsyncMock(return_value=MigrationState())
    return mock


def test_migrate_calls_engine(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "test-token",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    mock_engine.assert_called_once()
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.stoat_url == "http://localhost"
    assert config.token == "test-token"
    assert config.export_dir == Path(FIXTURES_DIR)
    assert config.skip_export is True


def test_migrate_resume_flag(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
                "--resume",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.resume is True


def test_migrate_skip_flags(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
                "--skip-messages",
                "--skip-emoji",
                "--skip-reactions",
                "--skip-threads",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.skip_messages is True
    assert config.skip_emoji is True
    assert config.skip_reactions is True
    assert config.skip_threads is True


def test_migrate_rate_limit(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
                "--rate-limit",
                "2.0",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.message_rate_limit == 2.0


def test_migrate_env_vars(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    env = {"STOAT_URL": "http://env-url", "STOAT_TOKEN": "env-token"}
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            ["migrate", "--export-dir", FIXTURES_DIR],
            env=env,
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.stoat_url == "http://env-url"
    assert config.token == "env-token"


def test_migrate_engine_error(runner: CliRunner) -> None:
    mock_engine = AsyncMock(side_effect=MigrationError("Phase connect failed: boom"))
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
            ],
        )
    assert result.exit_code == 1
    assert "Migration failed" in result.output


def test_verbose_flag(runner: CliRunner) -> None:
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir",
                FIXTURES_DIR,
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
                "-v",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.verbose is True


# ---------------------------------------------------------------------------
# Migrate — orchestrated mode
# ---------------------------------------------------------------------------


def test_migrate_orchestrated_mode(runner: CliRunner) -> None:
    """Orchestrated mode: --discord-token + --discord-server sets skip_export=False."""
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--discord-token",
                "dt",
                "--discord-server",
                "12345",
                "--stoat-url",
                "http://localhost",
                "--token",
                "t",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    config: FerryConfig = mock_engine.call_args[0][0]
    assert config.discord_token == "dt"
    assert config.discord_server_id == "12345"
    assert config.skip_export is False


def test_migrate_mutual_exclusion(runner: CliRunner) -> None:
    """Cannot use both --export-dir and --discord-token."""
    result = runner.invoke(
        main,
        [
            "migrate",
            "--export-dir",
            FIXTURES_DIR,
            "--discord-token",
            "dt",
            "--discord-server",
            "12345",
            "--stoat-url",
            "http://localhost",
            "--token",
            "t",
        ],
    )
    assert result.exit_code == 1
    assert "Cannot use both" in result.output


def test_migrate_neither_mode(runner: CliRunner) -> None:
    """Must provide either --export-dir or --discord-token."""
    result = runner.invoke(
        main,
        [
            "migrate",
            "--stoat-url",
            "http://localhost",
            "--token",
            "t",
        ],
    )
    assert result.exit_code == 1
    assert "Provide either" in result.output
