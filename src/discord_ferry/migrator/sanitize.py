"""String sanitization helpers for Stoat API field limits."""

from __future__ import annotations

import re

# Stoat API enforces maxLength: 32 on most name fields.
_DEFAULT_MAX_LENGTH = 32

# Emoji names must match ^[a-z0-9_]+$ per OpenAPI spec.
_EMOJI_NAME_RE = re.compile(r"[^a-z0-9_]")


def truncate_name(name: str, max_length: int = _DEFAULT_MAX_LENGTH) -> str:
    """Truncate a name to fit Stoat's field length limits.

    Args:
        name: The string to truncate.
        max_length: Maximum allowed length (default 32).

    Returns:
        The name, truncated if it exceeds max_length.
    """
    return name[:max_length]


def sanitize_emoji_name(name: str) -> str:
    """Sanitize an emoji name to match Stoat's ``^[a-z0-9_]+$`` pattern.

    Lowercases, replaces invalid characters with underscores, strips
    leading/trailing underscores, truncates to 32 chars, and falls back
    to ``"emoji"`` if the result is empty.

    Args:
        name: Raw emoji name string.

    Returns:
        A sanitized emoji name safe for the Stoat API.
    """
    sanitized = _EMOJI_NAME_RE.sub("_", name.lower())
    sanitized = sanitized.strip("_")
    sanitized = sanitized[:_DEFAULT_MAX_LENGTH]
    return sanitized if sanitized else "emoji"
