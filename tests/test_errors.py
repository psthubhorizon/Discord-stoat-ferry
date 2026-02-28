"""Tests for custom exception hierarchy."""

from discord_ferry.errors import (
    DCENotFoundError,
    DiscordAuthError,
    DotNetMissingError,
    ExportError,
    FerryError,
    MigrationError,
)


def test_export_error_hierarchy():
    """ExportError inherits from MigrationError -> FerryError."""
    err = ExportError("test")
    assert isinstance(err, MigrationError)
    assert isinstance(err, FerryError)


def test_dce_not_found_is_export_error():
    assert isinstance(DCENotFoundError("msg"), ExportError)


def test_dotnet_missing_is_export_error():
    assert isinstance(DotNetMissingError("msg"), ExportError)


def test_discord_auth_is_export_error():
    assert isinstance(DiscordAuthError("msg"), ExportError)
