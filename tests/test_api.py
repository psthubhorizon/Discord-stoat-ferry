"""Tests for the Stoat REST API wrapper."""

from __future__ import annotations

import aiohttp
import pytest
from aioresponses import aioresponses

from discord_ferry.errors import MigrationError
from discord_ferry.migrator.api import (
    api_add_reaction,
    api_create_category,
    api_create_channel,
    api_create_emoji,
    api_create_role,
    api_create_server,
    api_edit_category,
    api_edit_role,
    api_edit_server,
    api_fetch_server,
    api_pin_message,
    api_send_message,
    api_set_channel_default_permissions,
    api_set_channel_role_permissions,
    api_set_role_permissions,
    api_set_server_default_permissions,
)

BASE_URL = "https://api.test"
TOKEN = "test-session-token"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_aiohttp() -> aioresponses:
    with aioresponses() as m:
        yield m


# ---------------------------------------------------------------------------
# api_create_server
# ---------------------------------------------------------------------------


async def test_api_create_server(mock_aiohttp: aioresponses) -> None:
    """POST /servers/create returns the new server dict including _id."""
    mock_aiohttp.post(f"{BASE_URL}/servers/create", payload={"_id": "srv123", "name": "Test"})
    async with aiohttp.ClientSession() as session:
        result = await api_create_server(session, BASE_URL, TOKEN, "Test")
    assert result["_id"] == "srv123"
    assert result["name"] == "Test"


# ---------------------------------------------------------------------------
# api_fetch_server
# ---------------------------------------------------------------------------


async def test_api_fetch_server(mock_aiohttp: aioresponses) -> None:
    """GET /servers/abc123 returns the server info dict."""
    mock_aiohttp.get(
        f"{BASE_URL}/servers/abc123",
        payload={"_id": "abc123", "name": "My Server"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_fetch_server(session, BASE_URL, TOKEN, "abc123")
    assert result["_id"] == "abc123"
    assert result["name"] == "My Server"


# ---------------------------------------------------------------------------
# api_create_role
# ---------------------------------------------------------------------------


async def test_api_create_role(mock_aiohttp: aioresponses) -> None:
    """POST /servers/srv1/roles returns the new role dict including id."""
    mock_aiohttp.post(
        f"{BASE_URL}/servers/srv1/roles",
        payload={"id": "role99", "name": "Moderator"},
        status=200,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_create_role(session, BASE_URL, TOKEN, "srv1", "Moderator")
    assert result["id"] == "role99"
    assert result["name"] == "Moderator"


# ---------------------------------------------------------------------------
# api_edit_role
# ---------------------------------------------------------------------------


async def test_api_edit_role(mock_aiohttp: aioresponses) -> None:
    """PATCH /servers/srv1/roles/role1 sends colour in the JSON body."""
    mock_aiohttp.patch(
        f"{BASE_URL}/servers/srv1/roles/role1",
        payload={"id": "role1", "colour": "#FF0000"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_edit_role(
            session, BASE_URL, TOKEN, "srv1", "role1", colour="#FF0000", hoist=True
        )
    assert result["colour"] == "#FF0000"


# ---------------------------------------------------------------------------
# api_create_category
# ---------------------------------------------------------------------------


async def test_api_create_category(mock_aiohttp: aioresponses) -> None:
    """POST /servers/srv1/categories returns the new category dict including id."""
    mock_aiohttp.post(
        f"{BASE_URL}/servers/srv1/categories",
        payload={"id": "cat42", "title": "General"},
        status=201,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_create_category(session, BASE_URL, TOKEN, "srv1", "General")
    assert result["id"] == "cat42"
    assert result["title"] == "General"


# ---------------------------------------------------------------------------
# api_edit_category
# ---------------------------------------------------------------------------


async def test_api_edit_category(mock_aiohttp: aioresponses) -> None:
    """PATCH /servers/srv1/categories/cat1 sends the channels list in the body."""
    channels = ["ch1", "ch2", "ch3"]
    mock_aiohttp.patch(
        f"{BASE_URL}/servers/srv1/categories/cat1",
        payload={"id": "cat1", "channels": channels},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_edit_category(session, BASE_URL, TOKEN, "srv1", "cat1", channels)
    assert result["channels"] == channels


# ---------------------------------------------------------------------------
# api_create_channel
# ---------------------------------------------------------------------------


async def test_api_create_channel(mock_aiohttp: aioresponses) -> None:
    """POST /servers/srv1/channels sends name and type and returns the channel dict."""
    mock_aiohttp.post(
        f"{BASE_URL}/servers/srv1/channels",
        payload={"_id": "ch99", "name": "general", "channel_type": "Text"},
        status=201,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_create_channel(
            session, BASE_URL, TOKEN, "srv1", name="general", channel_type="Text"
        )
    assert result["_id"] == "ch99"
    assert result["name"] == "general"


# ---------------------------------------------------------------------------
# api_edit_server
# ---------------------------------------------------------------------------


async def test_api_edit_server(mock_aiohttp: aioresponses) -> None:
    """PATCH /servers/srv1 passes kwargs as the JSON body."""
    mock_aiohttp.patch(
        f"{BASE_URL}/servers/srv1",
        payload={"_id": "srv1", "name": "Renamed Server"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_edit_server(session, BASE_URL, TOKEN, "srv1", name="Renamed Server")
    assert result["name"] == "Renamed Server"


# ---------------------------------------------------------------------------
# Error and retry tests
# ---------------------------------------------------------------------------


async def test_api_error_403(mock_aiohttp: aioresponses) -> None:
    """A 403 response raises MigrationError immediately (not retried)."""
    mock_aiohttp.get(f"{BASE_URL}/servers/srv1", status=403, body="Forbidden")
    async with aiohttp.ClientSession() as session:
        with pytest.raises(MigrationError, match="API error 403"):
            await api_fetch_server(session, BASE_URL, TOKEN, "srv1")


# ---------------------------------------------------------------------------
# api_create_emoji
# ---------------------------------------------------------------------------


async def test_api_create_emoji(mock_aiohttp: aioresponses) -> None:
    """POST /servers/srv1/emojis sends name and parent (Autumn ID) in the body."""
    mock_aiohttp.post(
        f"{BASE_URL}/servers/srv1/emojis",
        payload={"_id": "emoji42", "name": "party", "parent": "autumn123"},
        status=200,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_create_emoji(session, BASE_URL, TOKEN, "srv1", "party", "autumn123")
    assert result["_id"] == "emoji42"
    assert result["name"] == "party"
    assert result["parent"] == "autumn123"


# ---------------------------------------------------------------------------
# api_send_message
# ---------------------------------------------------------------------------


async def test_api_send_message(mock_aiohttp: aioresponses) -> None:
    """POST /channels/ch1/messages sends content, nonce, and excludes None fields."""
    mock_aiohttp.post(
        f"{BASE_URL}/channels/ch1/messages",
        payload={"_id": "msg99", "content": "Hello"},
        status=200,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_send_message(
            session,
            BASE_URL,
            TOKEN,
            "ch1",
            content="Hello",
            nonce="ferry-discord123",
        )
    assert result["_id"] == "msg99"
    assert result["content"] == "Hello"


async def test_api_send_message_excludes_none_fields(mock_aiohttp: aioresponses) -> None:
    """api_send_message does not include None-valued optional fields in the request body."""
    captured_body: dict[str, object] = {}

    def capture_callback(url: object, **kwargs: object) -> None:
        body = kwargs.get("json") or {}
        captured_body.update(body)  # type: ignore[arg-type]

    mock_aiohttp.post(
        f"{BASE_URL}/channels/ch1/messages",
        payload={"_id": "msg1"},
        callback=capture_callback,
    )
    async with aiohttp.ClientSession() as session:
        await api_send_message(session, BASE_URL, TOKEN, "ch1", content="Hi")

    assert "content" in captured_body
    assert "attachments" not in captured_body
    assert "embeds" not in captured_body
    assert "masquerade" not in captured_body
    assert "replies" not in captured_body


async def test_api_send_message_includes_silent_by_default(mock_aiohttp: aioresponses) -> None:
    """api_send_message includes silent=true in the payload by default."""
    captured_body: dict[str, object] = {}

    def capture_callback(url: object, **kwargs: object) -> None:
        body = kwargs.get("json") or {}
        captured_body.update(body)  # type: ignore[arg-type]

    mock_aiohttp.post(
        f"{BASE_URL}/channels/ch1/messages",
        payload={"_id": "msg1"},
        callback=capture_callback,
    )
    async with aiohttp.ClientSession() as session:
        await api_send_message(session, BASE_URL, TOKEN, "ch1", content="Hello")

    assert captured_body.get("silent") is True


async def test_api_send_message_silent_false_omits_field(mock_aiohttp: aioresponses) -> None:
    """api_send_message with silent=False omits the silent field from payload."""
    captured_body: dict[str, object] = {}

    def capture_callback(url: object, **kwargs: object) -> None:
        body = kwargs.get("json") or {}
        captured_body.update(body)  # type: ignore[arg-type]

    mock_aiohttp.post(
        f"{BASE_URL}/channels/ch1/messages",
        payload={"_id": "msg1"},
        callback=capture_callback,
    )
    async with aiohttp.ClientSession() as session:
        await api_send_message(session, BASE_URL, TOKEN, "ch1", content="Hello", silent=False)

    assert "silent" not in captured_body


# ---------------------------------------------------------------------------
# api_add_reaction
# ---------------------------------------------------------------------------


async def test_api_add_reaction(mock_aiohttp: aioresponses) -> None:
    """PUT /channels/ch1/messages/msg1/reactions/:emoji returns empty dict on 204."""
    mock_aiohttp.put(
        f"{BASE_URL}/channels/ch1/messages/msg1/reactions/%F0%9F%91%8D",
        status=204,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_add_reaction(session, BASE_URL, TOKEN, "ch1", "msg1", "\U0001f44d")
    assert result == {}


async def test_api_add_reaction_custom_emoji(mock_aiohttp: aioresponses) -> None:
    """PUT with a custom emoji ID (no URL encoding needed for plain ASCII)."""
    mock_aiohttp.put(
        f"{BASE_URL}/channels/ch1/messages/msg1/reactions/customEmojiId",
        status=204,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_add_reaction(session, BASE_URL, TOKEN, "ch1", "msg1", "customEmojiId")
    assert result == {}


# ---------------------------------------------------------------------------
# api_pin_message
# ---------------------------------------------------------------------------


async def test_api_pin_message(mock_aiohttp: aioresponses) -> None:
    """PUT /channels/ch1/messages/msg1/pin returns empty dict on 204."""
    mock_aiohttp.put(
        f"{BASE_URL}/channels/ch1/messages/msg1/pin",
        status=204,
    )
    async with aiohttp.ClientSession() as session:
        result = await api_pin_message(session, BASE_URL, TOKEN, "ch1", "msg1")
    assert result == {}


# ---------------------------------------------------------------------------
# Error and retry tests
# ---------------------------------------------------------------------------


async def test_api_429_retry(mock_aiohttp: aioresponses) -> None:
    """A 429 response triggers a retry; the subsequent 200 returns the result."""
    # First response: 429 with 100 ms retry_after
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        status=429,
        payload={"retry_after": 100},
    )
    # Second response: success
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        payload={"_id": "srv1", "name": "Recovered"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_fetch_server(session, BASE_URL, TOKEN, "srv1")
    assert result["_id"] == "srv1"


async def test_api_network_error_retry_recovers(mock_aiohttp: aioresponses) -> None:
    """A transient ClientError on attempt 1 is retried; success on attempt 2."""
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        exception=aiohttp.ClientError("Connection reset"),
    )
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        payload={"_id": "srv1", "name": "Recovered"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_fetch_server(session, BASE_URL, TOKEN, "srv1")
    assert result["_id"] == "srv1"


async def test_api_network_error_exhausted(mock_aiohttp: aioresponses) -> None:
    """Three consecutive ClientErrors exhaust retries and raise MigrationError."""
    for _ in range(3):
        mock_aiohttp.get(
            f"{BASE_URL}/servers/srv1",
            exception=aiohttp.ClientError("Connection refused"),
        )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(MigrationError, match="Network error after 3 retries"):
            await api_fetch_server(session, BASE_URL, TOKEN, "srv1")


async def test_api_502_retry_exhaustion(mock_aiohttp: aioresponses) -> None:
    """Three consecutive 502 responses exhaust retries and raise MigrationError."""
    for _ in range(3):
        mock_aiohttp.get(
            f"{BASE_URL}/servers/srv1",
            status=502,
            body="Bad Gateway",
        )
    async with aiohttp.ClientSession() as session:
        with pytest.raises(MigrationError, match="API request failed after 3 retries"):
            await api_fetch_server(session, BASE_URL, TOKEN, "srv1")


async def test_api_503_retry_success(mock_aiohttp: aioresponses) -> None:
    """A 503 on attempt 1 is retried; success on attempt 2."""
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        status=503,
        body="Service Unavailable",
    )
    mock_aiohttp.get(
        f"{BASE_URL}/servers/srv1",
        payload={"_id": "srv1", "name": "Recovered"},
    )
    async with aiohttp.ClientSession() as session:
        result = await api_fetch_server(session, BASE_URL, TOKEN, "srv1")
    assert result["_id"] == "srv1"


# ---------------------------------------------------------------------------
# api_set_role_permissions
# ---------------------------------------------------------------------------


async def test_api_set_role_permissions(mock_aiohttp: aioresponses) -> None:
    """PUT /servers/srv1/permissions/role1 sends allow/deny permission pair."""
    mock_aiohttp.put(f"{BASE_URL}/servers/srv1/permissions/role1", payload={})
    async with aiohttp.ClientSession() as session:
        await api_set_role_permissions(
            session, BASE_URL, TOKEN, "srv1", "role1", allow=4194304, deny=0
        )


# ---------------------------------------------------------------------------
# api_set_server_default_permissions
# ---------------------------------------------------------------------------


async def test_api_set_server_default_permissions(mock_aiohttp: aioresponses) -> None:
    """PUT /servers/srv1/permissions/default sends a single permissions integer."""
    mock_aiohttp.put(f"{BASE_URL}/servers/srv1/permissions/default", payload={})
    async with aiohttp.ClientSession() as session:
        await api_set_server_default_permissions(
            session, BASE_URL, TOKEN, "srv1", permissions=1048576
        )


# ---------------------------------------------------------------------------
# api_set_channel_role_permissions
# ---------------------------------------------------------------------------


async def test_api_set_channel_role_permissions(mock_aiohttp: aioresponses) -> None:
    """PUT /channels/ch1/permissions/role1 sends allow/deny permission pair."""
    mock_aiohttp.put(f"{BASE_URL}/channels/ch1/permissions/role1", payload={})
    async with aiohttp.ClientSession() as session:
        await api_set_channel_role_permissions(
            session, BASE_URL, TOKEN, "ch1", "role1", allow=4194304, deny=8388608
        )


# ---------------------------------------------------------------------------
# api_set_channel_default_permissions
# ---------------------------------------------------------------------------


async def test_api_set_channel_default_permissions(mock_aiohttp: aioresponses) -> None:
    """PUT /channels/ch1/permissions/default sends allow/deny permission pair."""
    mock_aiohttp.put(f"{BASE_URL}/channels/ch1/permissions/default", payload={})
    async with aiohttp.ClientSession() as session:
        await api_set_channel_default_permissions(
            session, BASE_URL, TOKEN, "ch1", allow=4194304, deny=0
        )
