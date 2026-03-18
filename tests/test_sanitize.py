"""Tests for string sanitization helpers."""

from discord_ferry.migrator.sanitize import sanitize_emoji_name, truncate_name

# ---------------------------------------------------------------------------
# truncate_name
# ---------------------------------------------------------------------------


def test_truncate_name_under_limit() -> None:
    """Short names are returned unchanged."""
    assert truncate_name("general") == "general"


def test_truncate_name_at_limit() -> None:
    """Names at exactly 32 chars are returned unchanged."""
    name = "a" * 32
    assert truncate_name(name) == name


def test_truncate_name_over_limit() -> None:
    """Names over 32 chars are truncated."""
    name = "a" * 50
    assert truncate_name(name) == "a" * 32


def test_truncate_name_custom_limit() -> None:
    """Custom max_length is respected."""
    assert truncate_name("abcdefgh", max_length=5) == "abcde"


def test_truncate_name_empty() -> None:
    """Empty string stays empty."""
    assert truncate_name("") == ""


# ---------------------------------------------------------------------------
# sanitize_emoji_name
# ---------------------------------------------------------------------------


def test_sanitize_emoji_name_lowercase() -> None:
    """Uppercase is lowercased."""
    assert sanitize_emoji_name("PartyTime") == "partytime"


def test_sanitize_emoji_name_replaces_invalid_chars() -> None:
    """Non-alphanumeric non-underscore chars become underscores."""
    assert sanitize_emoji_name("my-emoji!") == "my_emoji"


def test_sanitize_emoji_name_strips_edge_underscores() -> None:
    """Leading/trailing underscores from replacements are stripped."""
    assert sanitize_emoji_name("-hello-") == "hello"


def test_sanitize_emoji_name_truncates() -> None:
    """Names over 32 chars are truncated after sanitization."""
    name = "a" * 50
    result = sanitize_emoji_name(name)
    assert len(result) == 32


def test_sanitize_emoji_name_empty_fallback() -> None:
    """Entirely invalid names fall back to 'emoji'."""
    assert sanitize_emoji_name("!!!") == "emoji"


def test_sanitize_emoji_name_already_valid() -> None:
    """Already valid names pass through unchanged."""
    assert sanitize_emoji_name("cool_emoji_42") == "cool_emoji_42"


def test_sanitize_emoji_name_spaces() -> None:
    """Spaces are replaced with underscores."""
    assert sanitize_emoji_name("my emoji") == "my_emoji"
