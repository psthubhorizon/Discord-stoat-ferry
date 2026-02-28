"""Tests for exporter binary manager."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from discord_ferry.exporter.manager import (
    DCE_VERSION,
    _get_asset_name,
    _get_dce_dir,
    detect_dotnet,
    get_dce_path,
)


def test_dce_version_is_pinned():
    assert DCE_VERSION == "2.46.1"


def test_get_dce_dir():
    """DCE binary directory is under ~/.discord-ferry/bin/dce/{version}/."""
    dce_dir = _get_dce_dir()
    assert dce_dir == Path.home() / ".discord-ferry" / "bin" / "dce" / DCE_VERSION


class TestGetAssetName:
    def test_windows_x64(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch("platform.machine", return_value="AMD64"),
        ):
            assert "win-x64" in _get_asset_name()

    def test_linux_x64(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="x86_64"),
        ):
            assert "linux-x64" in _get_asset_name()

    def test_macos_arm64(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="arm64"),
        ):
            assert "osx-arm64" in _get_asset_name()

    def test_linux_arm64(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("platform.machine", return_value="aarch64"),
        ):
            assert "linux-arm64" in _get_asset_name()

    def test_macos_x64(self):
        with (
            patch("platform.system", return_value="Darwin"),
            patch("platform.machine", return_value="x86_64"),
        ):
            assert "osx-x64" in _get_asset_name()

    def test_unsupported_os_raises(self):
        with (
            patch("platform.system", return_value="FreeBSD"),
            pytest.raises(ValueError, match="Unsupported"),
        ):
            _get_asset_name()

    def test_windows_x86_raises(self):
        with (
            patch("platform.system", return_value="Windows"),
            patch("platform.machine", return_value="x86"),
            pytest.raises(ValueError, match="Unsupported"),
        ):
            _get_asset_name()


class TestDetectDotnet:
    def test_windows_always_true(self):
        with patch("platform.system", return_value="Windows"):
            assert detect_dotnet() is True

    def test_linux_with_dotnet_8(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="8.0.100\n"),
            ),
        ):
            assert detect_dotnet() is True

    def test_linux_without_dotnet(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            assert detect_dotnet() is False

    def test_linux_with_old_dotnet(self):
        with (
            patch("platform.system", return_value="Linux"),
            patch(
                "subprocess.run",
                return_value=subprocess.CompletedProcess(args=[], returncode=0, stdout="6.0.400\n"),
            ),
        ):
            assert detect_dotnet() is False


class TestGetDcePath:
    def test_returns_path_when_binary_exists(self, tmp_path):
        dce_dir = tmp_path / "dce"
        dce_dir.mkdir()
        exe = dce_dir / "DiscordChatExporter.Cli"
        exe.touch()
        exe.chmod(0o755)

        with patch("discord_ferry.exporter.manager._get_dce_dir", return_value=dce_dir):
            result = get_dce_path()
            assert result is not None
            assert result.exists()

    def test_returns_exe_path_on_windows(self, tmp_path):
        dce_dir = tmp_path / "dce"
        dce_dir.mkdir()
        exe = dce_dir / "DiscordChatExporter.Cli.exe"
        exe.touch()

        with (
            patch("discord_ferry.exporter.manager._get_dce_dir", return_value=dce_dir),
            patch("platform.system", return_value="Windows"),
        ):
            result = get_dce_path()
            assert result is not None
            assert result.name == "DiscordChatExporter.Cli.exe"

    def test_returns_none_when_not_found(self, tmp_path):
        with patch(
            "discord_ferry.exporter.manager._get_dce_dir", return_value=tmp_path / "nonexistent"
        ):
            result = get_dce_path()
            assert result is None
