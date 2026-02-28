"""Custom exceptions for Discord Ferry."""


class FerryError(Exception):
    """Base exception for all ferry errors."""


class ValidationError(FerryError):
    """Export validation failed."""


class StoatConnectionError(FerryError):
    """Stoat API connection failed."""


class AutumnUploadError(FerryError):
    """File upload to Autumn failed."""


class MigrationError(FerryError):
    """Error during migration phase."""


class StateError(FerryError):
    """State file read/write error."""
