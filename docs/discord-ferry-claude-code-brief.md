# discord-ferry: Definitive Claude Code Implementation Brief

> **This is the single source of truth for implementing discord-ferry.** Read this entire document before writing any code. Every section contains implementation-critical details.

---

## 1. Project Overview

**Goal:** Open-source Python app that migrates a Discord server (exported via DiscordChatExporter) to a self-hosted Stoat (formerly Revolt) instance.

**Primary interface:** Local web GUI — user double-clicks `Ferry.exe` (Windows) or `Ferry.app` (Mac), a browser-based UI opens locally. No Python install needed, no terminal required.
**Secondary interface:** CLI (`ferry` command) for Linux/power users and scripting.
**Both are thin wrappers** around the same migration engine + event system.

**Input:** DiscordChatExporter JSON export directory (exported with `--media --reuse-media --markdown false --format Json --include-threads All`)
**Output:** Fully populated Stoat server with structure, roles, channels, messages, attachments, emoji, and pins.

**No existing Python tool does this.** The only prior art is `discord-terminator` (JavaScript, web UI, uses Discord API directly — not DCE exports) and `revcord` (TypeScript bridge, not a migration tool). discord-ferry fills a genuine gap.

**Hardest unsolvable constraint:** Stoat's API does not accept custom message timestamps. All migrated messages will show their migration time, not the original Discord timestamp. The ULID-based message ID encodes creation time. **Mitigation:** Prepend original timestamp to message content (see §8).

**Throughput expectation:** The message API rate limit (10/10s) means ~3,600 messages/hour sustained. A server with 100,000 messages takes ~28 hours. Communicate this clearly in docs and CLI output.

---

## 2. DiscordChatExporter (DCE) — Source Data

### 2.1 Required Export Command

```bash
DiscordChatExporter.Cli exportguild \
  --token DISCORD_USER_TOKEN \
  -g SERVER_ID \
  --media \
  --reuse-media \
  --markdown false \
  --format Json \
  --include-threads All \
  --output ./export/
```

- **Must use user token** (not bot token) — bot tokens cannot reliably export threads.
- `--media` downloads all attachments locally; `--reuse-media` avoids re-downloading.
- **`--markdown false` is CRITICAL** — without it, DCE replaces raw mention syntax (`<@123>`) with rendered text (`@Username`), destroying data needed for mention remapping. The VALIDATE phase must detect and warn if exports appear to have rendered markdown.
- `--include-threads All` exports both active and archived threads as separate JSON files.
- **Discord CDN URLs expire within ~24 hours** (signed URL parameters). The `--media` flag is mandatory — if any `attachment.url` starts with `http`, the file was NOT downloaded and cannot be migrated.

**Current DCE version:** 2.46.1 (Feb 16, 2026). JSON schema is stable.

### 2.2 Output File Naming Convention

| Channel Type | File Name Pattern |
|---|---|
| Text channel | `{Guild} - {Channel} [{channel_id}].json` |
| Forum thread | `{Guild} - {Forum Name} - {Thread Name} [{thread_id}].json` |
| Thread | `{Guild} - {Channel} - {Thread Name} [{thread_id}].json` |

**Important:** The thread-to-parent-channel relationship is NOT stored in the JSON metadata. Reconstruct it from the filesystem naming convention: a file with three dash-separated segments (Guild - Parent - Thread) indicates a thread/forum post. Use the `channel.categoryId` and `channel.id` fields plus filename parsing to rebuild the hierarchy.

### 2.3 Top-Level JSON Schema

```json
{
  "guild": {
    "id": "string",
    "name": "string",
    "iconUrl": "string (local path if --media used)"
  },
  "channel": {
    "id": "string",
    "type": 0,
    "categoryId": "string",
    "category": "string",
    "name": "string",
    "topic": "string"
  },
  "dateRange": { "after": null, "before": null },
  "exportedAt": "ISO8601",
  "messages": [],
  "messageCount": 123
}
```

### 2.4 Discord Channel Types Relevant for Migration

| Type ID | Name | Stoat Target | Notes |
|---|---|---|---|
| 0 | GUILD_TEXT | TextChannel | Direct mapping |
| 2 | GUILD_VOICE | VoiceChannel | Bug #194: may create as text on self-hosted |
| 4 | GUILD_CATEGORY | Category | Categories are server-level, not channel types in Stoat |
| 5 | GUILD_ANNOUNCEMENT | TextChannel | Map to text channel |
| 11 | PUBLIC_THREAD | TextChannel | **No thread support in Stoat** — flatten to channel |
| 12 | PRIVATE_THREAD | TextChannel | Same — flatten to channel |
| 15 | GUILD_FORUM | TextChannel(s) | **No forum support in Stoat** — each forum thread becomes a separate text channel |
| 16 | GUILD_MEDIA | TextChannel(s) | Same as forum |

**Critical: Stoat has exactly 5 channel types:** SavedMessages, DirectMessage, Group, TextChannel, VoiceChannel. There are NO thread or forum channel types. All Discord threads and forum posts must be flattened into text channels.

### 2.5 Message Object Schema

```json
{
  "id": "string",
  "type": "Default",
  "timestamp": "2024-01-01T12:00:00+00:00",
  "timestampEdited": null,
  "callEndedTimestamp": null,
  "isPinned": false,
  "content": "string (raw markdown)",
  "author": {
    "id": "string",
    "name": "string",
    "discriminator": "0000",
    "nickname": "string",
    "color": "#RRGGBB",
    "isBot": false,
    "roles": [],
    "avatarUrl": "string (local path)"
  },
  "attachments": [
    {
      "id": "string",
      "url": "string (local path if --media)",
      "fileName": "string",
      "fileSizeBytes": 12345
    }
  ],
  "embeds": [],
  "stickers": [],
  "reactions": [
    {
      "emoji": { "id": "string", "name": "string", "isAnimated": false },
      "count": 5
    }
  ],
  "mentions": [
    { "id": "string", "name": "string", "discriminator": "0000", "nickname": "string" }
  ],
  "reference": {
    "messageId": "string",
    "channelId": "string",
    "guildId": "string"
  },
  "interaction": null,
  "poll": null
}
```

**DCE `type` field uses string names** (e.g. "Default", "Reply", "GuildMemberJoin"), not numeric IDs. Handle these:

| DCE Type String | Numeric | Action |
|---|---|---|
| "Default" | 0 | Import normally |
| "Reply" | 19 | Import with reply reference |
| "RecipientAdd" | 1 | Skip |
| "RecipientRemove" | 2 | Skip |
| "ChannelNameChange" | 4 | Skip |
| "ChannelPinnedMessage" | 6 | Import, mark for re-pinning |
| "GuildMemberJoin" | 7 | Import as system note or skip (configurable) |
| "UserPremiumGuildSubscription" | 8 | Skip (boost) |
| "ThreadCreated" | 18 | Import as first message in thread channel |
| "ThreadStarterMessage" | 19 | Import as first message in thread |

**Edge cases discovered in research:**
- **Webhook messages and bot messages are indistinguishable** — both have `author.isBot = true`. No `webhook_id` field in DCE export.
- **Forwarded messages export as empty** (DCE bug #1322, PR #1451 pending). Detect empty content + empty attachments + non-null `reference` and log as "forwarded message skipped".
- **System messages may have empty `content`** — always check `type` field, not just `content`.
- **Reply references contain only IDs**, not the referenced message content. Cross-reference within exported messages to build reply chains.

---

## 3. Stoat API — Confirmed Behavior

### 3.1 Background

Stoat is the renamed Revolt platform (rebrand October 1, 2025, triggered by cease-and-desist). GitHub org moved from `revoltchat` to `stoatchat`. The API protocol is unchanged; endpoints auto-redirect.

### 3.2 API Endpoints

All API calls go to `{STOAT_API_URL}` (e.g. `https://api.stoat.chat`).

| Method | Path | Purpose | Rate Bucket |
|---|---|---|---|
| GET | `/` | Config: returns `features.autumn.url`, `features.january.url` | `/*` 20/10s |
| POST | `/servers` | Create server (**user accounts only**) | `/servers` **5/10s** |
| GET/PATCH | `/servers/:id` | Edit server (name, icon, banner, description, **categories**) | `/servers` **5/10s** |
| POST | `/servers/:id/channels` | Create channel | `/servers` **5/10s** ⚠️ |
| PATCH | `/channels/:id` | Edit channel | `/channels` 15/10s |
| POST | `/servers/:id/roles` | Create role | `/servers` **5/10s** |
| PATCH | `/servers/:id/roles/:role_id` | Edit role | `/servers` **5/10s** |
| POST | `/channels/:id/messages` | Send message | **10/10s** (dedicated bucket) |
| PUT | `/channels/:id/messages/:msg_id/pin` | Pin message | `/channels` 15/10s |
| PUT | `/channels/:id/messages/:msg_id/reactions/:emoji` | Add reaction | `/channels` 15/10s |
| POST | `/servers/:id/emojis` | Create emoji | `/servers` **5/10s** |
| Any | `/*` | Catch-all | 20/10s |

> ⚠️ **Rate bucket clarification:** The official docs define buckets by path prefix. `POST /servers/:id/channels` starts with `/servers`, so it likely shares the 5/10s server bucket — NOT the 15/10s `/channels` bucket. This means **all structure creation (server, channels, roles, emoji) shares a single 5-per-10-second budget.** This significantly impacts structure creation phase speed. Plan accordingly: 5 operations per 10s for all server-related endpoints combined.

### 3.3 Rate Limits

**Algorithm:** Fixed window, 10-second reset.
**Headers:** `X-RateLimit-Remaining`, `X-RateLimit-Reset-After` (milliseconds), `X-RateLimit-Limit`, `X-RateLimit-Bucket`.
**429 body:** `{ "retry_after": <ms> }` — use this value for backoff.

**The message endpoint (10/10s) is the primary bottleneck.** stoat.py handles rate limits internally ("sane rate limit handling that prevents 429s"). Let the library manage limits, but add a configurable inter-message delay (default 1.0s) as additional safety margin for bulk operations.

### 3.4 Server & Account Limits (from Revolt.toml — yes, still called Revolt.toml)

**The config file is genuinely still named `Revolt.toml`** even in the stoatchat/stoatchat repo. The rebrand was cosmetic (domains, org name, UI) — the internal codebase still uses Revolt naming. Binaries are still `revolt-delta`, `revolt-bonfire`, `revolt-autumn`, `revolt-january`. The Endpoints docs page literally says: *"We are moving stuff around currently following the rebrand, guidance will follow soon!"*

**Global limits (apply to all accounts):**

| Resource | Limit | Source |
|---|---|---|
| Group size | 100 | `features.limits.global.group_size` |
| Embeds per message | **5** | `features.limits.global.message_embeds` |
| Replies per message | **5** | `features.limits.global.message_replies` |
| Reactions per message | **20** | `features.limits.global.message_reactions` |
| Custom emoji per server | **100** | `features.limits.global.server_emoji` |
| Roles per server | **200** | `features.limits.global.server_roles` |
| Channels per server | **200** | `features.limits.global.server_channels` |
| New user window | 72 hours | `features.limits.global.new_user_hours` |
| Max upload body size | **20 MB** | `features.limits.global.body_limit_size` |

**Default user limits (apply to established accounts):**

| Resource | Limit | Source |
|---|---|---|
| Message length | **2,000 chars** | `features.limits.default.message_length` |
| Attachments per message | **5** | `features.limits.default.message_attachments` |
| Servers per user | 100 | `features.limits.default.servers` |
| Bots per user | 5 | `features.limits.default.bots` |
| Outgoing friend requests | 10 | `features.limits.default.outgoing_friend_requests` |

**File size limits by Autumn tag:**

| Tag | Max Size | Bytes | Source |
|---|---|---|---|
| `attachments` | **20 MB** | 20,000,000 | `features.limits.default.attachment_size` |
| `avatars` | **4 MB** | 4,000,000 | `features.limits.default.avatar_size` |
| `backgrounds` | **6 MB** | 6,000,000 | `features.limits.default.background_size` |
| `icons` | **2.5 MB** | 2,500,000 | `features.limits.default.icon_size` |
| `banners` | **6 MB** | 6,000,000 | `features.limits.default.banner_size` |
| `emojis` | **500 KB** | 500,000 | `features.limits.default.emoji_size` |

**New users (accounts < 72 hours old) may have stricter limits** — the config has a `[features.limits.new_user]` section. For migration, ensure the Stoat account used is older than 72 hours.

**Self-hosted instances can override all of these** via `Revolt.overrides.toml`. Document this in README as a tip for large migrations (e.g. raise `server_channels` if > 200 channels needed).

### 3.5 Category Assignment — Two-Step Process (CRITICAL)

**Categories are NOT a channel property in Stoat.** They live on the Server object as an array of `{ id, title, channels[] }`. There is NO `category_id` parameter on channel creation.

The correct workflow is:
1. Create the channel via `POST /servers/:id/channels`
2. PATCH the server's `categories` array to include the new channel ID in the appropriate category

In stoat.py, this is:
1. `channel = await client.http.create_server_channel(server, name=..., type=...)`
2. `await client.http.edit_category(server, category_id, channels=[...existing_ids, channel.id])`

Or use `create_category()` for new categories, then `edit_category()` to assign channels to them.

### 3.6 Masquerade

Masquerade is the critical feature enabling attributed message migration. The `masquerade` object on message send accepts:
- `name` — displayed username (string)
- `avatar` — URL string (can be an Autumn CDN URL after uploading the avatar)
- `colour` — hex color string (**British spelling in API; stoat.py may accept either**)

**Required permissions on the sending account's role:**
- `Masquerade` (bit 28) — required for masquerade (name, avatar)
- `ManageRole` (bit 3) — **required specifically for `colour` in masquerade** (confirmed via OpenAPI.json: *"Must have ManageRole permission to use"* on the colour field)

This means the ferry bot permission bitfield needs updating if colour is used (add `1 << 3`).

### 3.7 Reactions

Reactions ARE supported via `PUT /channels/{channel}/messages/{msg}/reactions/{emoji}`. Both Unicode emoji and custom server emoji work. **However, per-user reaction attribution is lost** — Stoat reactions don't record who reacted, only that the reaction exists. Custom emoji must be uploaded to the server first, then referenced by their Stoat ID.

---

## 4. Stoat File Storage — Autumn

### 4.1 Architecture

- **Autumn** = file upload server (now integrated into main `stoatchat/stoatchat` backend; the standalone `revoltchat/autumn` repo was archived Dec 19, 2024)
- **January** = image proxy for external URLs
- Files are AES-256-GCM encrypted before storage
- EXIF stripping enabled by default for JPEGs and videos

### 4.2 Discovering Autumn URL

```python
resp = await http.get(f"{STOAT_API_URL}/")
config = await resp.json()
autumn_url = config["features"]["autumn"]["url"]
# Example: "https://autumn.stoat.chat"
```

### 4.3 Upload Pattern

```
POST {autumn_url}/{tag}
Content-Type: multipart/form-data
Authorization: x-session-token: {token}

file=<binary>
```

**Available tags and confirmed size limits (from Revolt.toml `features.limits.default`):**

| Tag | Use for | Max Size |
|---|---|---|
| `attachments` | Message file attachments | **20 MB** |
| `avatars` | User/member avatars | **4 MB** |
| `backgrounds` | Profile backgrounds | **6 MB** |
| `icons` | Server and channel icons | **2.5 MB** |
| `banners` | Server banners | **6 MB** |
| `emojis` | Custom server emoji | **500 KB** |

**Response:** `{ "id": "<file_id>" }` — use this ID in subsequent API calls.

**Autumn CANNOT accept URLs** — files must be downloaded locally first, then uploaded as multipart form data. This is fine for discord-ferry since DCE `--media` already downloads everything locally.

**Response metadata types:** `{ type: "File" }`, `{ type: "Image", width, height }`, `{ type: "Video", width, height }`, `{ type: "Audio" }`.

### 4.4 Python Upload Implementation

```python
async def upload_to_autumn(session, autumn_url, tag, file_path, token):
    with open(file_path, 'rb') as f:
        data = aiohttp.FormData()
        data.add_field('file', f, filename=Path(file_path).name)
        async with session.post(
            f"{autumn_url}/{tag}",
            data=data,
            headers={"x-session-token": token}
        ) as resp:
            if resp.status != 200:
                raise AutumnUploadError(f"Upload failed: {resp.status}")
            result = await resp.json()
            return result["id"]
```

**Attachment in message:** After upload, pass the Autumn file ID in the attachments list:
```python
await channel.send(content="...", attachments=["<autumn_file_id>"])
```

### 4.5 Autumn Rate Limits

No documented per-tag limits. Likely shares the catch-all 20-per-10-second bucket. Use conservative sleep:
- `0.5s` between file uploads
- Backoff on 429 using `retry_after` header
- Implement upload cache to avoid re-uploading the same file (DCE `--reuse-media` means the same local path can appear in multiple messages)

---

## 5. stoat.py Library API

**Version:** 1.2.1 (stable, Nov 26, 2025) / 1.3.0a (alpha master)
**Install (stable):** `pip install -U stoat-py` (PyPI package name is `stoat-py`, imports as `stoat`)
**Install (master):** `pip install -U git+https://github.com/MCausc78/stoat.py@master`
**Docs:** https://stoatpy.readthedocs.io/en/latest/
**Requires:** Python 3.10+
**License:** MIT (consistent with predecessor)
**Status:** Listed on stoatchat/awesome-stoat as the recommended Python library. 0 open issues, 6 open PRs. Beta software.

**Key feature:** Built-in rate limit handling ("sane rate limit handling that prevents 429s"). This means discord-ferry should generally let stoat.py manage HTTP-level rate limits rather than implementing its own, but should add configurable inter-message delay as additional safety margin.

### 5.1 Client Bootstrap

```python
import stoat

class FerryClient(stoat.Client):
    async def on_ready(self, _, /):
        await self.run_migration()

# bot=False required for user account (server creation needs user account)
client = FerryClient(token='user_token', bot=False)
client.run()
```

### 5.2 Server Creation

```python
# Only available to user (non-bot) accounts — bot tokens get 403
server = await client.http.create_server(name="My Server")
# Returns: stoat.Server object
```

### 5.3 Channel Creation

```python
# TextChannel (type=None defaults to text)
channel = await client.http.create_server_channel(
    server,
    name="general",
    description="Channel topic here",
    type=None,  # text
    nsfw=False
)

# Voice channel — MAY FAIL on self-hosted (Bug #194)
voice_ch = await client.http.create_server_channel(
    server,
    name="General Voice",
    type=stoat.ChannelType.VOICE  # or the string "Voice" — test both
)
```

### 5.4 Category Creation & Channel Assignment

```python
# Create category
category = await client.http.create_category(server, title="Category Name")
# Returns category object with .id

# After creating channels, assign them to the category
await client.http.edit_category(
    server,
    category.id,
    channels=[channel1.id, channel2.id, channel3.id]
)
```

**v1.2 breaking change:** The old `categories` parameter on `server.edit()` was deprecated in favor of dedicated `create_category()`, `edit_category()`, and `delete_category()` methods, reflecting Stoat API v0.8.5's categories rework.

### 5.5 Role Creation & Edit

```python
role = await client.http.create_role(server, name="Member")

await role.edit(
    name="Senior Member",
    colour=0xFF5733,  # int RGB
    hoist=True,       # show separately in sidebar
    rank=5            # NOTE: rank on role.edit() deprecated in v1.2
)

# For rank ordering, use:
await server.bulk_edit_role_ranks({role1.id: 1, role2.id: 2, role3.id: 3})

# Permissions via Permissions object (keyword-based)
# Use official bit values from §5.11 — NOT the incorrect values from early research
# stoat.py may use snake_case keywords — verify exact names at implementation time
await role.set_permissions(
    allow=stoat.Permissions(
        manage_server=True,       # 1 << 1
        manage_channel=True,      # 1 << 0
        manage_role=True,         # 1 << 3  — needed for masquerade colour
        manage_messages=True,     # 1 << 23
        masquerade=True,          # 1 << 28 — CRITICAL for ferry bot
        upload_files=True,        # 1 << 27
        send_message=True,        # 1 << 22
        view_channel=True,        # 1 << 20
        read_message_history=True, # 1 << 21
        send_embeds=True,         # 1 << 26
        react=True,               # 1 << 29
    ),
    deny=stoat.Permissions()  # empty = deny nothing
)
```

**There is NO single ADMINISTRATOR permission in Stoat.** Unlike Discord, you must grant individual permissions explicitly. For the ferry bot, grant all needed permissions individually.

### 5.6 Emoji Upload

```python
# First upload image to Autumn with "emojis" tag
emoji_file_id = await upload_to_autumn(session, autumn_url, "emojis", local_path, token)

# Then create the emoji on the server
emoji = await client.http.create_emoji(
    server,
    name="custom_emoji",
    parent=emoji_file_id  # ResolvableResource — test if raw string works
)
```

**Server emoji limit: 100.** If the Discord server has more than 100 custom emoji, prioritize by usage frequency or prompt the user to choose.

### 5.7 Sending Messages with Masquerade

```python
masquerade = stoat.MessageMasquerade(
    name="DiscordUsername",         # shown instead of bot name
    avatar="https://...",           # avatar URL (can be Autumn URL)
    colour="#FF5733"                # optional role colour (British spelling)
)

message = await channel.send(
    content="The original message text",
    masquerade=masquerade,
    attachments=["<autumn_file_id>"],  # list of Autumn file IDs
    nonce="unique-nonce-string",       # prevent duplicates on retry
    silent=True                         # don't trigger notifications
)
```

**`send()` parameters:** `content`, `attachments`, `embeds`, `masquerade`, `replies`, `nonce`, `silent`, `mention_everyone`, `mention_online`.

### 5.8 Pinning Messages

```python
await client.http.pin_message(channel, message)
```

### 5.9 Editing Server

```python
await server.edit(
    name="New Name",
    description="Server description",
    icon=icon_file_id,    # Autumn file ID from "icons" tag
    banner=banner_file_id # Autumn file ID from "banners" tag
)
```

### 5.10 ResolvableResource

This type appears throughout the API for file parameters. Based on the library's architecture, it likely accepts raw string file IDs from Autumn. **Test at implementation time** — if raw strings don't work, try wrapping in the library's resource type.

### 5.11 Permission Reference (OFFICIAL — from developers.stoat.chat)

**These are the authoritative permission bit values.** The original research had completely wrong bit positions. These come directly from https://developers.stoat.chat/developers/api/permissions/

Stoat's permission system works by sequentially applying allows then denies.

| Name | Value | Bitwise | Notes |
|---|---|---|---|
| `ManageChannel` | 1 | `1 << 0` | Create/edit/delete channels |
| `ManageServer` | 2 | `1 << 1` | Edit server settings |
| `ManagePermissions` | 4 | `1 << 2` | Manage permissions on servers/channels |
| `ManageRole` | 8 | `1 << 3` | Manage roles on server |
| `ManageCustomisation` | 16 | `1 << 4` | Manage emoji on servers |
| *(gap at bit 5)* | | | |
| `KickMembers` | 64 | `1 << 6` | Kick members below their ranking |
| `BanMembers` | 128 | `1 << 7` | Ban members below their ranking |
| `TimeoutMembers` | 256 | `1 << 8` | Timeout members below their ranking |
| `AssignRoles` | 512 | `1 << 9` | Assign roles to members below their ranking |
| `ChangeNickname` | 1024 | `1 << 10` | Change own nickname |
| `ManageNicknames` | 2048 | `1 << 11` | Change/remove other's nicknames |
| `ChangeAvatar` | 4096 | `1 << 12` | Change own avatar |
| `RemoveAvatars` | 8192 | `1 << 13` | Remove other's avatars |
| *(gap bits 14–19)* | | | |
| `ViewChannel` | 1048576 | `1 << 20` | **Required for ferry bot** |
| `ReadMessageHistory` | 2097152 | `1 << 21` | Read past message history |
| `SendMessage` | 4194304 | `1 << 22` | **Required for ferry bot** |
| `ManageMessages` | 8388608 | `1 << 23` | Delete/pin messages — **Required for pins** |
| `ManageWebhooks` | 16777216 | `1 << 24` | Manage webhook entries |
| `InviteOthers` | 33554432 | `1 << 25` | Create invites |
| `SendEmbeds` | 67108864 | `1 << 26` | Send embedded content |
| `UploadFiles` | 134217728 | `1 << 27` | **Required for ferry bot** — attachments |
| `Masquerade` | 268435456 | `1 << 28` | **Required for ferry bot** — masquerade |
| `React` | 536870912 | `1 << 29` | React to messages — **Required for reactions** |
| `Connect` | 1073741824 | `1 << 30` | Connect to voice channel |
| `Speak` | 2147483648 | `1 << 31` | Speak in voice call |
| `Video` | 4294967296 | `1 << 32` | Share video in voice call |
| `MuteMembers` | 8589934592 | `1 << 33` | Mute others in voice |
| `DeafenMembers` | 17179869184 | `1 << 34` | Deafen others in voice |
| `MoveMembers` | 34359738368 | `1 << 35` | Move members between voice channels |

**Minimum permissions the ferry bot needs (bitfield OR):**
```python
FERRY_BOT_PERMISSIONS = (
    (1 << 3)   # ManageRole (required for colour in masquerade)
    | (1 << 20)  # ViewChannel
    | (1 << 21)  # ReadMessageHistory
    | (1 << 22)  # SendMessage
    | (1 << 23)  # ManageMessages (for pins)
    | (1 << 26)  # SendEmbeds
    | (1 << 27)  # UploadFiles
    | (1 << 28)  # Masquerade
    | (1 << 29)  # React
)
# = 1,071,644,680
```

**Note:** There is NO single ADMINISTRATOR permission in Stoat (unlike Discord). The ferry bot must be granted individual permissions. If the user creating the server is the owner, they already have all permissions. For `--server-id` flows, the bot/user must have these permissions pre-granted.

**How stoat.py exposes these:** Confirm the exact keyword names in the `Permissions` class — they may use snake_case versions of the above (e.g. `manage_channel`, `send_message`, `masquerade`, `upload_files`). Run `from stoat import Permissions; help(Permissions)` at implementation time.

---

## 6. Migration Architecture

### 6.1 Directory Structure

```
discord-ferry/
├── pyproject.toml
├── LICENSE                       # MIT — full text
├── README.md                     # Primary landing page (see §18)
├── CONTRIBUTING.md               # How to contribute (see §18)
├── CODE_OF_CONDUCT.md            # Contributor Covenant v2.1
├── CHANGELOG.md                  # Keep-a-changelog format
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml        # Structured bug report form
│   │   ├── feature_request.yml   # Feature request form
│   │   └── config.yml            # Template chooser config
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── FUNDING.yml               # GitHub Sponsors / Ko-fi (optional)
│   └── workflows/
│       ├── ci.yml                # Lint + test on PR
│       ├── release.yml           # Build executables + publish on tag
│       └── docs.yml              # Build + deploy docs to GitHub Pages
├── docs/
│   ├── index.md                  # Docs home (mirrors/extends README)
│   ├── getting-started/
│   │   ├── install.md            # Step-by-step install for each platform
│   │   ├── export-discord.md     # How to run DiscordChatExporter (with screenshots)
│   │   ├── setup-stoat.md        # Getting your Stoat URL + token
│   │   └── first-migration.md    # End-to-end walkthrough with screenshots
│   ├── guides/
│   │   ├── gui-walkthrough.md    # Every screen of the GUI explained
│   │   ├── cli-reference.md      # Full CLI flags and env vars
│   │   ├── large-servers.md      # Tips for 100k+ message servers
│   │   ├── self-hosted-tips.md   # Revolt.toml overrides for large migrations
│   │   └── troubleshooting.md    # Common errors + solutions
│   ├── reference/
│   │   ├── architecture.md       # How the engine works internally
│   │   ├── stoat-api-notes.md    # Everything we learned about the Stoat API
│   │   └── dce-format.md         # DCE JSON schema reference
│   └── assets/
│       └── screenshots/          # GUI screenshots for docs
├── assets/
│   ├── ferry.ico                 # Windows icon
│   ├── ferry.icns                # macOS icon
│   ├── ferry-banner.png          # README / social preview banner
│   └── ferry-logo.svg            # Logo source
├── src/
│   └── discord_ferry/
│       ├── __init__.py
│       ├── cli.py                # Click CLI entry point (power users / Linux)
│       ├── gui.py                # NiceGUI local web UI entry point (primary UX)
│       ├── config.py             # FerryConfig dataclass
│       ├── core/
│       │   ├── __init__.py
│       │   ├── engine.py         # Migration orchestrator (shared by CLI + GUI)
│       │   └── events.py         # Event emitter for progress (GUI subscribes, CLI prints)
│       ├── parser/
│       │   ├── __init__.py
│       │   ├── dce_parser.py     # Parse DCE JSON exports
│       │   ├── models.py         # Dataclasses for parsed data
│       │   └── transforms.py     # Markdown/mention/emoji conversions
│       ├── uploader/
│       │   ├── __init__.py
│       │   ├── autumn.py         # Autumn file upload with retry
│       │   └── cache.py          # Upload cache (avoid re-uploading)
│       ├── migrator/
│       │   ├── __init__.py
│       │   ├── structure.py      # Server, categories, channels, roles
│       │   ├── messages.py       # Message import with masquerade
│       │   ├── emoji.py          # Custom emoji upload
│       │   ├── reactions.py      # Reaction migration
│       │   └── pins.py           # Re-pin messages
│       ├── state.py              # Migration state / ID mapping / resume
│       ├── reporter.py           # Migration report generator
│       └── errors.py             # Custom exceptions
└── tests/
    ├── conftest.py
    ├── fixtures/                 # Sample DCE JSON files for testing
    ├── test_parser.py
    ├── test_transforms.py
    ├── test_migrator.py
    └── test_cli.py
```

**Key architectural principle:** The `core/engine.py` migration orchestrator contains ALL migration logic. Both `cli.py` and `gui.py` are thin wrappers that create a `FerryConfig`, call the engine, and subscribe to progress events. The engine must NEVER import from `cli` or `gui` — all progress reporting happens through the event emitter pattern in `core/events.py`.

### 6.2 Migration Phases (in order)

```
Phase 1:  VALIDATE       Parse all DCE JSON files, verify media files exist,
                          detect --markdown false, warn on expired CDN URLs,
                          count totals, estimate migration time
Phase 2:  CONNECT        Test Stoat API connectivity, get Autumn URL from
                          GET /, verify auth token, check permissions
Phase 3:  SERVER         Create server (or use --server-id), upload and set
                          icon/banner via Autumn
Phase 4:  ROLES          Create all roles with colours, hoist, rank;
                          grant ferry bot all needed permissions
Phase 5:  CATEGORIES     Create category structure
Phase 6:  CHANNELS       Create channels, assign to categories via
                          edit_category(), set topics/descriptions
                          (threads/forums → text channels)
Phase 7:  EMOJI          Upload custom emoji to Autumn → create on server
                          (max 100, warn if over limit)
Phase 8:  MESSAGES       Import messages oldest-first per channel with:
                          - Masquerade (author name, colour)
                          - Attachment upload via Autumn (with cache)
                          - Original timestamp prepended to content
                          - Mention/emoji/spoiler syntax conversion
                          - Embed flattening
                          - Nonce for deduplication
                          - Reply references (where target already migrated)
Phase 9:  REACTIONS      Add reactions to migrated messages (no user attribution)
Phase 10: PINS           Re-pin messages that had isPinned=true
Phase 11: REPORT         Write migration_report.json and state.json for resume
```

### 6.3 State / ID Mapping & Resume

```python
@dataclass
class MigrationState:
    # Discord ID → Stoat ID mappings
    role_map: dict[str, str] = field(default_factory=dict)
    channel_map: dict[str, str] = field(default_factory=dict)
    category_map: dict[str, str] = field(default_factory=dict)
    message_map: dict[str, str] = field(default_factory=dict)
    emoji_map: dict[str, str] = field(default_factory=dict)

    # Author ID → uploaded Autumn avatar ID (avoid re-uploading per author)
    avatar_cache: dict[str, str] = field(default_factory=dict)

    # Autumn upload cache: local_path → autumn_file_id
    upload_cache: dict[str, str] = field(default_factory=dict)

    # Pending pins: list of (stoat_channel_id, stoat_message_id)
    pending_pins: list[tuple[str, str]] = field(default_factory=list)

    # Error log
    errors: list[dict] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)

    # Stoat server ID
    stoat_server_id: str = ""

    # Current phase + channel for resume
    current_phase: str = ""
    last_completed_channel: str = ""
    last_completed_message: str = ""
```

**State must be saved to `state.json` after each channel completes** to support `--resume`. Use atomic writes (write to `.tmp` then rename) to avoid corruption on interrupt.

---

## 7. Content Transformation Rules

### 7.1 Markdown Syntax Conversion

| Feature | Discord | Stoat | Action |
|---|---|---|---|
| Bold | `**text**` | `**text**` | No change |
| Italic | `*text*` or `_text_` | `*text*` or `_text_` | No change |
| Strikethrough | `~~text~~` | `~~text~~` | No change |
| **Spoiler** | `\|\|text\|\|` | `!!text!!` | **CONVERT** |
| **Underline** | `__text__` | *(no equivalent)* | **Strip markers or convert to bold** |
| Code inline | `` `code` `` | `` `code` `` | No change |
| Code block | ` ```lang ``` ` | ` ```lang ``` ` | No change |
| Blockquote | `> text` | `> text` | No change |
| Heading | `# text` | `# text` | No change |
| Link | `[text](url)` | `[text](url)` | No change |

### 7.2 Mention Remapping

Discord uses numeric Snowflake IDs; Stoat uses 26-character ULIDs. All mentions in message content must be remapped.

```python
import re

def remap_mentions(content: str, state: MigrationState, author_names: dict) -> str:
    """Remap Discord mention syntax to Stoat IDs or fallback to plain text."""

    # User mentions: <@123456> or <@!123456> (with nickname)
    def replace_user(m):
        discord_id = m.group(1)
        name = author_names.get(discord_id, f"Unknown#{discord_id[:4]}")
        return f"@{name}"  # Stoat doesn't have user mention syntax in the same way

    # Channel mentions: <#123456>
    def replace_channel(m):
        discord_id = m.group(1)
        stoat_id = state.channel_map.get(discord_id)
        if stoat_id:
            return f"<#{stoat_id}>"
        return f"#deleted-channel"

    # Role mentions: <@&123456>
    def replace_role(m):
        discord_id = m.group(1)
        stoat_id = state.role_map.get(discord_id)
        if stoat_id:
            return f"<@&{stoat_id}>"
        return f"@deleted-role"

    content = re.sub(r'<@!?(\d+)>', replace_user, content)
    content = re.sub(r'<#(\d+)>', replace_channel, content)
    content = re.sub(r'<@&(\d+)>', replace_role, content)

    return content
```

### 7.3 Custom Emoji Remapping

Discord: `<:name:id>` and `<a:name:id>` (animated)
Stoat: `:emoji_id:` (by Stoat emoji ID, not name)

```python
def remap_emoji(content: str, state: MigrationState) -> str:
    """Remap Discord custom emoji to Stoat emoji IDs."""
    def replace_emoji(m):
        discord_id = m.group(2)
        stoat_id = state.emoji_map.get(discord_id)
        if stoat_id:
            return f":{stoat_id}:"
        return f"[:{m.group(1)}:]"  # fallback: show name in brackets

    return re.sub(r'<a?:([^:]+):(\d+)>', replace_emoji, content)
```

**Note:** Animated Discord emoji become static in Stoat. Log this as a warning.

### 7.4 Spoiler Conversion

```python
def convert_spoilers(content: str) -> str:
    return content.replace("||", "!!")
```

**Careful:** This is a naive replacement. It works because `||` always appears in pairs in Discord markdown. However, if someone uses `||` in a code block, it would be incorrectly converted. To be safe, skip conversion inside code blocks and inline code.

### 7.5 Embed Flattening

Stoat's `SendableEmbed` supports only: `title`, `description`, `url`, `icon_url`, `media` (Autumn file ID), and `colour` (**British spelling**).

Discord embeds with `fields[]`, `footer`, `author`, `timestamp` must be flattened:

```python
def flatten_embed(embed: dict) -> dict:
    """Convert Discord embed to Stoat-compatible SendableEmbed."""
    parts = []

    if embed.get("author", {}).get("name"):
        parts.append(f"**{embed['author']['name']}**")

    if embed.get("description"):
        parts.append(embed["description"])

    for field in embed.get("fields", []):
        parts.append(f"**{field['name']}:** {field['value']}")

    if embed.get("footer", {}).get("text"):
        parts.append(f"_{embed['footer']['text']}_")

    return {
        "title": embed.get("title"),
        "description": "\n\n".join(parts) if parts else None,
        "url": embed.get("url"),
        "colour": embed.get("color"),  # Discord uses "color", Stoat wants "colour"
        "icon_url": embed.get("author", {}).get("iconUrl"),
        # media: upload thumbnail/image to Autumn if present
    }
```

### 7.6 Timestamp Embedding

Since Stoat cannot accept custom timestamps, prepend the original time:

```python
from datetime import datetime

def format_original_timestamp(iso_timestamp: str) -> str:
    """Format Discord timestamp for embedding in message content."""
    dt = datetime.fromisoformat(iso_timestamp)
    return dt.strftime("*[%Y-%m-%d %H:%M UTC]*")

# Usage in message content:
content = f"{format_original_timestamp(msg['timestamp'])} {content}"
```

### 7.7 Sticker Handling

Stickers have no Stoat equivalent. Convert to text placeholder:
```python
for sticker in msg.get("stickers", []):
    content += f"\n[Sticker: {sticker.get('name', 'unknown')}]"
```

If the sticker has a downloadable image (check `sticker.sourceUrl`), upload as an attachment instead.

---

## 8. Message Import Loop (Complete)

```python
async def import_messages(channel, dce_messages, state, autumn_url, session, token, config):
    for msg in sorted(dce_messages, key=lambda m: m["timestamp"]):
        # Skip non-importable message types
        msg_type = msg.get("type", "Default")
        if msg_type in ("RecipientAdd", "RecipientRemove", "ChannelNameChange",
                         "UserPremiumGuildSubscription"):
            continue

        # 1. Upload attachments to Autumn (with cache)
        autumn_ids = []
        for att in msg.get("attachments", []):
            local_path = resolve_local_path(config.export_dir, att["url"])
            if local_path is None:
                state.warnings.append({
                    "phase": "messages", "msg_id": msg["id"],
                    "warning": f"Attachment URL not local: {att['url']}"
                })
                continue

            if not local_path.exists():
                state.warnings.append({
                    "phase": "messages", "msg_id": msg["id"],
                    "warning": f"Attachment file missing: {local_path}"
                })
                continue

            # Check file size against Autumn limits (20 MB for attachments)
            if local_path.stat().st_size > 20 * 1024 * 1024:
                state.warnings.append({
                    "phase": "messages", "msg_id": msg["id"],
                    "warning": f"Attachment too large (>20MB): {att['fileName']}"
                })
                continue

            cache_key = str(local_path)
            if cache_key in state.upload_cache:
                autumn_ids.append(state.upload_cache[cache_key])
            else:
                fid = await upload_to_autumn(session, autumn_url, "attachments", local_path, token)
                state.upload_cache[cache_key] = fid
                autumn_ids.append(fid)
                await asyncio.sleep(0.5)  # conservative Autumn rate limit

            # Respect 5-attachment-per-message limit
            if len(autumn_ids) >= 5:
                break

        # 2. Build content with transformations
        content = msg.get("content", "") or ""
        content = convert_spoilers(content)
        content = remap_mentions(content, state, author_names)
        content = remap_emoji(content, state)

        # Prepend original timestamp
        content = f"{format_original_timestamp(msg['timestamp'])} {content}"

        # Handle stickers
        for sticker in msg.get("stickers", []):
            content += f"\n[Sticker: {sticker.get('name', 'unknown')}]"

        # 3. Build masquerade
        author = msg["author"]
        masquerade = stoat.MessageMasquerade(
            name=author.get("nickname") or author["name"],
            colour=author.get("color")  # stoat.py may accept either spelling
        )

        # 4. Handle embeds (flatten Discord embeds to Stoat format)
        stoat_embeds = []
        for embed in msg.get("embeds", [])[:5]:  # max 5 per message
            flat = flatten_embed(embed)
            if flat.get("description") or flat.get("title"):
                stoat_embeds.append(flat)

        # 5. Build reply references
        replies = []
        if msg.get("reference", {}).get("messageId"):
            ref_discord_id = msg["reference"]["messageId"]
            ref_stoat_id = state.message_map.get(ref_discord_id)
            if ref_stoat_id:
                replies.append(stoat.Reply(id=ref_stoat_id, mention=False))

        # 6. Handle empty messages
        if not content.strip() and not autumn_ids and not stoat_embeds:
            content = f"{format_original_timestamp(msg['timestamp'])} [empty message]"

        # 7. Truncate to character limit
        if len(content) > 2000:
            content = content[:1997] + "..."

        # 8. Send message
        try:
            nonce = f"ferry-{msg['id']}"  # unique nonce for dedup on retry
            sent = await channel.send(
                content=content,
                attachments=autumn_ids if autumn_ids else None,
                embeds=stoat_embeds if stoat_embeds else None,
                masquerade=masquerade,
                replies=replies if replies else None,
                nonce=nonce,
                silent=True
            )
            state.message_map[msg["id"]] = sent.id

            if msg.get("isPinned"):
                state.pending_pins.append((channel.id, sent.id))

            # Collect reactions for later phase
            for reaction in msg.get("reactions", []):
                state.pending_reactions.append({
                    "channel_id": channel.id,
                    "message_id": sent.id,
                    "emoji": reaction["emoji"],
                    "count": reaction.get("count", 1)
                })

        except Exception as e:
            state.errors.append({
                "phase": "messages",
                "msg_id": msg["id"],
                "channel": channel.name if hasattr(channel, 'name') else str(channel.id),
                "error": str(e)
            })

        # 9. Rate limit delay
        await asyncio.sleep(config.message_rate_limit)
```

---

## 9. Thread & Forum Flattening Strategy

Since Stoat has no thread or forum channel types, these must be converted:

### 9.1 Threads → Text Channels

For each Discord thread (types 11, 12):
1. Create a text channel named `{parent_channel}-{thread_name}` (or a configurable naming pattern)
2. Place it in the same category as its parent channel
3. Import all thread messages into the new channel
4. Add a system message at the top: `"[Thread migrated from #{parent_channel}]"`

### 9.2 Forum Channels → Category with Text Channels

For each Discord forum (type 15, 16):
1. Create a new Stoat **category** named after the forum
2. For each forum post/thread, create a text channel within that category
3. Channel name = thread/post title
4. Import all messages from each thread into its respective channel
5. Add a system message at the top: `"[Forum post migrated from #{forum_name}]"`

### 9.3 Naming Collision Prevention

```python
def make_unique_channel_name(name: str, existing_names: set) -> str:
    """Ensure channel name is unique within the server."""
    base = name[:64]  # Stoat channel name length limit (verify)
    if base not in existing_names:
        existing_names.add(base)
        return base
    counter = 1
    while f"{base}-{counter}" in existing_names:
        counter += 1
    unique = f"{base}-{counter}"
    existing_names.add(unique)
    return unique
```

**Respect the 200-channel server limit.** If thread flattening would exceed 200 channels, warn the user and offer to skip threads or merge small threads.

---

## 10. User Interfaces — GUI (Primary) + CLI (Secondary)

### 10.1 Architecture: Two Thin Shells, One Engine

discord-ferry has two entry points — a **local web GUI** (primary, for Windows/Mac users) and a **CLI** (secondary, for Linux/power users). Both are thin wrappers around the same migration engine.

```
┌─────────────┐     ┌─────────────┐
│   gui.py    │     │   cli.py    │
│  (NiceGUI)  │     │  (Click)    │
└──────┬──────┘     └──────┬──────┘
       │                   │
       └───────┬───────────┘
               │
        ┌──────▼──────┐
        │  engine.py  │  ← all migration logic lives here
        │  events.py  │  ← progress events emitted here
        └─────────────┘
```

**The engine NEVER imports from gui or cli.** It emits progress events via a simple callback/event pattern:

```python
# core/events.py
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class MigrationEvent:
    phase: str                    # "validate", "connect", "roles", "channels", "messages", etc.
    status: str                   # "started", "progress", "completed", "error", "warning"
    message: str                  # human-readable description
    current: int = 0             # current item number
    total: int = 0               # total items in this phase
    channel_name: str = ""       # current channel (during message phase)
    detail: dict | None = None   # extra data (error info, warning details)

# Engine accepts a callback
async def run_migration(config: FerryConfig, on_event: Callable[[MigrationEvent], Any]):
    on_event(MigrationEvent(phase="validate", status="started", message="Parsing export..."))
    # ...
```

### 10.2 GUI — Local Web UI (Primary Interface)

**The user double-clicks `Ferry.exe` (Windows) or `Ferry.app` (Mac).** A local Python HTTP server starts, a browser tab opens to `http://localhost:8765`. Everything runs locally — no data leaves the machine except API calls to the user's own Stoat instance.

**Framework: NiceGUI** (https://nicegui.io)
- Pure Python — no JS/HTML to write manually, but renders as a real web UI
- Built on FastAPI + Vue.js under the hood
- Supports native window mode (`nicegui.ui.run(native=True)`) using pywebview — looks like a desktop app, no visible browser chrome
- File dialogs, progress bars, tables, logs all available as Python objects
- PyInstaller-compatible for single-binary distribution
- MIT license, actively maintained, 12k+ GitHub stars

**Three-screen flow:**

#### Screen 1: Setup

```python
# gui.py (simplified — NiceGUI declarative style)
from nicegui import ui

with ui.card().classes('w-96 mx-auto mt-8'):
    ui.label('Discord Ferry').classes('text-2xl font-bold')
    ui.label('Migrate your Discord server to Stoat').classes('text-gray-500')

    export_dir = ui.input('Export folder path', placeholder='/path/to/dce-export/')
    # NiceGUI has a native folder picker:
    ui.button('Browse...', on_click=lambda: pick_folder(export_dir))

    stoat_url = ui.input('Stoat API URL', placeholder='https://api.my-stoat.com')
    token = ui.input('Stoat Token', password=True, password_toggle_button=True)

    # Optional: expandable advanced settings
    with ui.expansion('Advanced Options', icon='settings'):
        server_id = ui.input('Existing Server ID (optional)')
        rate_limit = ui.slider(min=0.5, max=3.0, value=1.0, step=0.1)
        ui.label().bind_text_from(rate_limit, 'value',
                                  backward=lambda v: f'Message delay: {v}s (~{int(3600/v)}/hr)')
        skip_messages = ui.checkbox('Structure only (skip messages)')
        skip_emoji = ui.checkbox('Skip emoji')
        skip_reactions = ui.checkbox('Skip reactions')

    ui.button('Validate Export', on_click=go_to_validate).classes('w-full mt-4')
```

#### Screen 2: Validate (Dry Run)

After clicking Validate, the app parses all DCE JSON files locally (no API calls). Displays:

- **Source server name** and export date
- **Counts table:** channels, categories, roles, messages, attachments, custom emoji
- **Warnings** with amber indicators: missing media files, expired CDN URLs, `--markdown false` not detected, channel count vs 200 limit, emoji count vs 100 limit
- **ETA estimate** based on message count and configured rate limit (e.g. "~12,483 messages at 1.0s/msg ≈ 3h 28m")
- **Green/amber/red overall status** indicator

Two buttons: `← Back` and `Start Migration →` (disabled if red status)

#### Screen 3: Migrate (Live Progress)

- **Phase indicator** showing which of the 11 phases is active (with checkmarks for completed ones)
- **Per-channel progress bar** during the message phase — the longest phase by far
- **Running totals:** messages sent, attachments uploaded, errors, warnings
- **Live log stream** (scrollable, auto-scrolls to bottom)
- **ETA countdown** (recalculated live based on actual throughput)
- **Pause / Resume button** — sets a flag the engine checks between messages
- **Cancel button** — saves state cleanly, shows resume instructions
- On completion: summary card with stats + "Open Report" button that opens `ferry-output/report.json` in the OS file explorer

```python
# Progress subscription in GUI
async def run_with_progress():
    progress_bar = ui.linear_progress(value=0, show_value=False)
    log_area = ui.log(max_lines=500)
    stats_label = ui.label('Starting...')

    def on_event(event: MigrationEvent):
        if event.status == "progress" and event.total > 0:
            progress_bar.set_value(event.current / event.total)
        log_area.push(f"[{event.phase}] {event.message}")
        if event.status == "error":
            log_area.push(f"  ⚠ ERROR: {event.detail}")
        stats_label.set_text(
            f"{event.current}/{event.total} — {event.channel_name}"
        )

    await run_migration(config, on_event=on_event)
```

### 10.3 CLI (Secondary Interface — Power Users / Linux)

The CLI remains for power users, scripting, and headless Linux servers. Same engine, different presentation.

```
Usage: ferry [OPTIONS] EXPORT_DIR

Arguments:
  EXPORT_DIR  Path to DiscordChatExporter output directory

Commands:
  migrate      Run the full migration (default)
  validate     Parse and validate only, no API calls

Options:
  --stoat-url TEXT        Stoat API base URL [required]
  --token TEXT            Stoat user/bot token [required]
  --server-id TEXT        Use existing Stoat server (skip creation)
  --server-name TEXT      Name for new server [default: source guild name]
  --skip-messages        Import structure only (no message history)
  --skip-emoji           Skip emoji upload
  --skip-reactions       Skip reaction migration
  --skip-threads         Skip thread/forum channel migration
  --rate-limit FLOAT     Seconds between message sends [default: 1.0]
  --upload-delay FLOAT   Seconds between Autumn uploads [default: 0.5]
  --output-dir TEXT      Where to write reports [default: ./ferry-output]
  --resume               Resume from state file (ferry-output/state.json)
  --verbose / -v         Debug output
  --help                 Show help

Environment variables (alternative to flags):
  STOAT_URL              Stoat API base URL
  STOAT_TOKEN            Stoat user/bot token
```

CLI uses **Rich** for progress display: progress bar per channel, live stats panel, structured log output.

**The `validate` subcommand is distinct from `migrate --dry-run`:**
- `ferry validate ./export/` — purely local parsing, zero network. "Is my export good?"
- `ferry migrate ./export/ --dry-run` — also tests API connection, auth, and permissions. "Is everything ready?"

### 10.4 Distribution — Single Executable per Platform

Users should NOT need Python installed. Distribute as a self-contained executable.

| Platform | Format | Build Tool | Notes |
|---|---|---|---|
| **Windows** | `Ferry.exe` (portable) | PyInstaller `--onefile` | Also offer `.msi` installer via NSIS/Inno |
| **macOS** | `Ferry.app` in `.dmg` | PyInstaller + `create-dmg` | Code-sign if possible (Apple Developer ID) |
| **Linux** | `ferry` CLI via `pipx` | PyPI package | Linux users expect CLI, not a GUI |

**Build pipeline (GitHub Actions):**

```yaml
# .github/workflows/release.yml (simplified)
on:
  push:
    tags: ['v*']

jobs:
  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pyinstaller nicegui
      - run: pyinstaller --onefile --windowed --name Ferry --icon assets/ferry.ico src/discord_ferry/gui.py
      - uses: actions/upload-artifact@v4
        with: { name: Ferry-Windows, path: dist/Ferry.exe }

  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - run: pip install pyinstaller nicegui create-dmg
      - run: pyinstaller --onefile --windowed --name Ferry --icon assets/ferry.icns src/discord_ferry/gui.py
      - run: create-dmg dist/Ferry.app dist/Ferry.dmg
      - uses: actions/upload-artifact@v4
        with: { name: Ferry-macOS, path: dist/Ferry.dmg }

  publish-pypi:
    runs-on: ubuntu-latest
    steps:
      - uses: pypa/gh-action-pypi-publish@release/v1
```

**GitHub Releases** hosts the `.exe` and `.dmg`. README links directly to the latest release for each platform. PyPI package available for `pip install` / `pipx install` users.

**NiceGUI native mode consideration:** NiceGUI supports `ui.run(native=True)` which wraps the web UI in a pywebview desktop window — no visible browser chrome, looks like a real desktop app. This is the recommended mode for the packaged executables. Falls back to browser tab if pywebview is unavailable.

---

## 11. Configuration

```python
@dataclass
class FerryConfig:
    export_dir: Path
    stoat_url: str                    # e.g. "https://api.stoat.chat"
    token: str
    server_id: str | None = None      # pre-existing server
    server_name: str | None = None    # name for new server
    dry_run: bool = False
    skip_messages: bool = False
    skip_emoji: bool = False
    skip_reactions: bool = False
    skip_threads: bool = False
    message_rate_limit: float = 1.0   # seconds between message sends
    upload_delay: float = 0.5         # seconds between Autumn uploads
    output_dir: Path = Path("./ferry-output")
    resume: bool = False
    verbose: bool = False
```

---

## 12. Migration Report Format

```json
{
  "started_at": "ISO8601",
  "completed_at": "ISO8601",
  "duration_seconds": 3600,
  "source_guild": { "id": "...", "name": "..." },
  "target_server_id": "...",
  "summary": {
    "channels_created": 42,
    "roles_created": 8,
    "categories_created": 5,
    "messages_imported": 12483,
    "messages_skipped": 45,
    "attachments_uploaded": 341,
    "attachments_skipped": 3,
    "emoji_created": 24,
    "reactions_added": 156,
    "pins_restored": 17,
    "threads_flattened": 12,
    "errors": 3,
    "warnings": 5
  },
  "warnings": [
    { "type": "voice_channel_bug", "channel": "General Voice", "note": "Created as text (Bug #194)" },
    { "type": "emoji_limit", "note": "Server has 150 emoji, only 100 migrated" },
    { "type": "channel_limit", "note": "Approaching 200-channel limit, some threads skipped" },
    { "type": "animated_emoji", "emoji": "dance", "note": "Animated emoji imported as static" }
  ],
  "errors": [
    { "phase": "messages", "msg_id": "...", "channel": "general", "error": "..." }
  ],
  "maps": {
    "channels": { "<discord_id>": "<stoat_id>" },
    "roles": { "<discord_id>": "<stoat_id>" },
    "emoji": { "<discord_id>": "<stoat_id>" }
  }
}
```

---

## 13. Known Issues & Mitigations

### Voice Channel Bug (Issue #194 / #176)

**Status:** Open, closed as duplicate of #176, unresolved. Self-hosted voice requires Vortex/LiveKit service.
**Symptom:** `POST /servers/{id}/channels` with voice type succeeds (200 OK) but creates a text channel.
**Mitigation:** Create the channel, verify type after creation, log warning in report.

### Server Creation (User Account Only)

`create_server()` requires user token (`bot=False`). Bot tokens get 403.
**Mitigation:** Strongly recommend `--server-id` flow where user pre-creates an empty server. Document in README.

### Category Two-Step (§3.5)

Cannot assign categories during channel creation.
**Mitigation:** Create all channels first, then batch-assign to categories via `edit_category()`.

### Masquerade Permission Bootstrap

The bot/user needs `Masquerade` (bit 28), `ManageRole` (bit 3, for colour), `SendMessage` (bit 22), `UploadFiles` (bit 27), and `ViewChannel` (bit 20) permissions BEFORE sending messages. If creating a new server, the creating user has owner permissions automatically. If using `--server-id`, the user must have appropriate permissions already.

### Message Nonce for Deduplication

Always pass a unique `nonce` per message (e.g. `f"ferry-{discord_msg_id}"`). This prevents duplicate sends if the tool is interrupted and resumed, as stoat.py / the API will reject duplicate nonces.

### The `colour` vs `color` Spelling

The Stoat API uses British `colour`. stoat.py may accept either via keyword arguments. When sending raw HTTP (e.g. for embeds), always use `colour`. Test both in stoat.py wrapper methods.

---

## 14. Dependencies & Packaging

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "discord-ferry"
version = "0.1.0"
description = "Migrate Discord servers to self-hosted Stoat (formerly Revolt)"
readme = "README.md"
license = "MIT"
requires-python = ">=3.10"
authors = [{ name = "Peter", email = "..." }]
keywords = ["discord", "stoat", "revolt", "migration", "gui"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Environment :: Console",
    "Environment :: Web Environment",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Communications :: Chat",
]

dependencies = [
    "stoat-py>=1.2.1",
    "aiohttp>=3.9",
    "aiofiles>=23.0",
    "nicegui>=2.0",       # local web UI (primary interface)
    "click>=8.0",          # CLI (secondary interface)
    "rich>=13.0",          # CLI progress display
    "python-dotenv",       # .env config
]

[project.scripts]
ferry = "discord_ferry.cli:main"
ferry-gui = "discord_ferry.gui:main"

[project.gui-scripts]
ferry-desktop = "discord_ferry.gui:main"

[project.urls]
Homepage = "https://github.com/.../discord-ferry"
Issues = "https://github.com/.../discord-ferry/issues"

[project.optional-dependencies]
native = [
    "pywebview>=5.0",     # desktop window mode (no visible browser chrome)
]
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "aioresponses>=0.7",
    "ruff",
    "mypy",
    "pyinstaller>=6.0",   # for building platform executables
]
```

**License compatibility:** Click (BSD-3), Rich (MIT), aiohttp (Apache-2.0), stoat.py (MIT), NiceGUI (MIT), pywebview (BSD-3) — all compatible with MIT.

**Entry points explained:**
- `ferry` → CLI for Linux/power users
- `ferry-gui` → launches local web UI in default browser
- `ferry-desktop` (gui-scripts) → same as ferry-gui but marked as GUI app (no console window on Windows)

**For PyInstaller builds**, the entry point is `gui.py` with `--windowed` flag so no terminal window appears. The packaged app runs in NiceGUI native mode (pywebview) if available, otherwise falls back to launching the browser.

---

## 15. What to Verify at Implementation Time

These are acceptable unknowns — discover them during development:

1. **Exact `create_server()` signature** — inspect stoat.py `HTTPClient` source
2. **`Permissions` class keyword names** — may be snake_case of official names. Run `from stoat import Permissions; help(Permissions)` and compare against official bit values (§5.11)
3. **stoat.py keyword for ManageRole** — confirmed needed for masquerade colour; check if it's `manage_role` or `manage_roles` in the Permissions class
4. **`ResolvableResource` for Autumn IDs** — test if raw string ID works or needs a wrapper
5. **Voice channel type constant** — `stoat.ChannelType.VOICE` or string `"Voice"` — check Enum
6. **Channel name max length** — likely 64 chars but verify
7. **`edit_category()` exact signature** — how to pass the channels list
8. **stoat.py `colour` vs `color` in MessageMasquerade** — test both
9. **`Reply` object constructor** — `stoat.Reply(id=..., mention=False)` or different
10. **`SendableEmbed` constructor** — how stoat.py wraps `colour` and `media`
11. **`nonce` parameter** — verify it's a string, check max length
12. **Reaction API via stoat.py** — check if there's a high-level method or use HTTP directly
13. **New user limits** — `[features.limits.new_user]` may impose stricter limits; ensure the migration account is >72h old
14. **`ManageCustomisation` (bit 4) vs `ManageRole` (bit 3)** — which is needed for emoji upload?
15. **Stoat Endpoints docs status** — currently says "moving stuff around following rebrand"; check for updates before finalizing

**Now confirmed (removed from unknowns):**
- ✅ Message char limit: **2,000** (from `features.limits.default.message_length`)
- ✅ Attachment limit per message: **5** (from `features.limits.default.message_attachments`)
- ✅ Emoji size limit: **500 KB** (from `features.limits.default.emoji_size`)
- ✅ Permission bit values: **Official table at developers.stoat.chat** (see §5.11)
- ✅ Config file name: **Still `Revolt.toml`** even post-rebrand
- ✅ Rate limits: **Fixed-window, 10s reset, 10 msg/10s confirmed** (from developers.stoat.chat)
- ✅ Masquerade colour needs **ManageRole** (bit 3) — confirmed via OpenAPI.json
- ✅ Minio storage uses single bucket `revolt-uploads` (not per-tag buckets) in newer deployments

---

## 16. Reference Links

| Resource | URL | Status |
|---|---|---|
| **Stoat OpenAPI Spec (GOLD)** | https://github.com/revoltchat/api/blob/main/OpenAPI.json | ✅ Machine-readable full API |
| **Stoat Developer Docs** | https://developers.stoat.chat | ✅ Live |
| Stoat Permissions (OFFICIAL) | https://developers.stoat.chat/developers/api/permissions/ | ✅ Authoritative |
| Stoat Rate Limits (OFFICIAL) | https://developers.stoat.chat/developers/api/ratelimits/ | ✅ Authoritative |
| Stoat Authentication | https://developers.stoat.chat/developers/api/authentication/ | ✅ Live |
| Stoat Uploading Files | https://developers.stoat.chat/developers/api/uploading-files/ | ⚠️ Page exists, may be sparse |
| Stoat Endpoints | https://developers.stoat.chat/developers/endpoints | ⚠️ "Moving stuff around following rebrand" |
| Stoat API Reference | https://developers.stoat.chat/api-reference/ | ⚠️ Empty shell — OpenAPI not yet published |
| Stoat Migration Guide | https://developers.stoat.chat/developers/stoat-migration-guide | Revolt→Stoat API migration (not Discord→Stoat) |
| stoat.py GitHub | https://github.com/MCausc78/stoat.py | ✅ Active |
| stoat.py PyPI | https://pypi.org/project/stoat-py/ | ✅ |
| stoat.py Docs | https://stoatpy.readthedocs.io/en/latest/ | ✅ |
| Stoat Backend Source | https://github.com/stoatchat/stoatchat | ✅ Config reference |
| Revolt.toml (reference config) | https://github.com/stoatchat/stoatchat/blob/main/crates/core/config/Revolt.toml | ✅ Authoritative limits |
| Stoat Self-Hosted | https://github.com/stoatchat/self-hosted | ✅ |
| awesome-stoat | https://github.com/stoatchat/awesome-stoat | ✅ |
| DiscordChatExporter | https://github.com/Tyrrrz/DiscordChatExporter | ✅ |
| DCE Frontend (schema ref) | https://github.com/slatinsky/DiscordChatExporter-frontend | ✅ |
| Voice Channel Bug #194 | https://github.com/stoatchat/self-hosted/issues/194 | Open |
| Forwarded Msg Bug #1322 | https://github.com/Tyrrrz/DiscordChatExporter/issues/1322 | Open |
| Discord Import Request #358 | https://github.com/orgs/stoatchat/discussions/358 | Open (31 upvotes) |
| revcord (bridge, reference) | https://github.com/mayudev/revcord | Reference only |
| discord-terminator (JS tool) | https://github.com/rambros3d/discord-terminator | Reference only |

---

## 17. Open Source Release & Documentation

This project will go from private to public. All documentation must be written for **community admins who are NOT developers** — people who can follow step-by-step instructions but don't know what Python or pip is. They managed a Discord server. They set up self-hosted Stoat (so they're not afraid of a terminal, but they followed a guide). Meet them where they are.

### ⚠️ DOCUMENTATION PHILOSOPHY — READ THIS FIRST

**Every doc page must pass the "my friend who runs a gaming Discord" test.** If that person couldn't follow the instructions without asking you for help, the doc has failed.

Rules for ALL documentation:
1. **No unexplained jargon.** If you must use a technical term, explain it in parentheses the first time: "your token (a long string of letters and numbers that proves who you are)"
2. **Every action gets a screenshot.** "Click the gear icon" is not enough — show them where the gear icon is.
3. **Copy-paste ready commands.** Never say "run the export command with the appropriate flags." Instead, give them the exact command with placeholders clearly marked: `DiscordChatExporter.Cli export --token YOUR_TOKEN_HERE --guild YOUR_SERVER_ID ...`
4. **Numbered steps, not paragraphs.** Instructions are always 1, 2, 3 — never buried in prose.
5. **Warning boxes before mistakes, not after.** If they need `--markdown false` or they'll waste hours, put a big warning BEFORE the step, not in a troubleshooting page.
6. **State the obvious.** "Open your web browser." "Click the Download button." What's obvious to you isn't obvious to everyone.
7. **Test on fresh eyes.** Before publishing, have someone who wasn't involved in development try to follow the guide. Fix every place they hesitated.
8. **Platform-specific instructions use tabs or clear headers.** Never mix Windows/Mac/Linux instructions in one paragraph.

### 17.1 README.md — The Single Most Important File

The README is the landing page. Most users will never click past it. Structure it exactly like this:

```markdown
# 🚢 Discord Ferry

**Migrate your Discord server to Stoat (formerly Revolt) — messages, channels,
roles, emoji, attachments, and all.**

> One-click app for Windows and Mac. CLI for Linux.
> No coding required. Your data stays on your machine.

[screenshot/gif of the GUI in action — validate screen + migrate screen]

---

## ⬇️ Download

| Platform | Download | Size |
|----------|----------|------|
| **Windows** | [Ferry.exe (v0.1.0)](link) | ~XX MB |
| **macOS** | [Ferry.dmg (v0.1.0)](link) | ~XX MB |
| **Linux / pip** | `pipx install discord-ferry` | — |

---

## How It Works (3 Steps)

### Step 1: Export your Discord server
[Brief explanation + link to detailed guide]

### Step 2: Open Ferry and connect to your Stoat instance
[Brief explanation + screenshot]

### Step 3: Click Migrate
[Brief explanation + screenshot]

Your messages, channels, roles, emoji and attachments migrate to Stoat.
Original authors show up via masquerade. Pins are preserved.

---

## ⏱ How long does it take?

About **1 message per second** due to Stoat API rate limits. That means:
- 1,000 messages → ~17 minutes
- 10,000 messages → ~3 hours
- 100,000 messages → ~28 hours (run overnight!)

Ferry can **pause and resume** — close it anytime, pick up where you left off.

---

## What gets migrated?

| Feature | Status |
|---------|--------|
| Text channels | ✅ |
| Categories | ✅ |
| Roles (with colours) | ✅ |
| Messages + author names | ✅ (via masquerade) |
| File attachments | ✅ |
| Custom emoji | ✅ (up to 100) |
| Pinned messages | ✅ |
| Replies | ✅ |
| Reactions | ✅ (without per-user attribution) |
| Threads | ✅ (as text channels) |
| Forum posts | ✅ (as text channels) |
| Voice channels | ⚠️ (created but may not work — Stoat bug) |
| Stickers | ℹ️ (shown as text placeholder) |
| Original timestamps | ℹ️ (shown in message text, not metadata) |

---

## Detailed Guides

- [Exporting from Discord (step-by-step)](docs/getting-started/export-discord.md)
- [Setting up your Stoat instance](docs/getting-started/setup-stoat.md)
- [Your first migration (full walkthrough)](docs/getting-started/first-migration.md)
- [GUI guide (every screen explained)](docs/guides/gui-walkthrough.md)
- [CLI reference](docs/guides/cli-reference.md)
- [Migrating large servers (100k+ messages)](docs/guides/large-servers.md)
- [Troubleshooting](docs/guides/troubleshooting.md)

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT — do whatever you want with it.
```

**Key README rules:**
- Download links ABOVE the fold — first thing a visitor sees after the tagline
- Zero jargon: no "pip", no "Python", no "async" in the main README
- Screenshots are mandatory — at minimum the validate screen and migrate screen
- "How long does it take?" section is critical — sets realistic expectations upfront
- Feature table shows exactly what migrates and what doesn't
- Every guide link goes to a dedicated page, not an anchor in a giant doc

### 17.2 docs/ — The Full Documentation Site

Build with **MkDocs Material** (https://squidfunk.github.io/mkdocs-material/). Deploys to GitHub Pages via `docs.yml` action. This gives a searchable, mobile-friendly docs site at `https://your-username.github.io/discord-ferry/`.

```yaml
# mkdocs.yml
site_name: Discord Ferry
site_description: Migrate Discord servers to Stoat
theme:
  name: material
  palette:
    primary: indigo
  features:
    - navigation.sections
    - navigation.expand
    - search.suggest
    - content.code.copy
nav:
  - Home: index.md
  - Getting Started:
    - Installation: getting-started/install.md
    - Exporting from Discord: getting-started/export-discord.md
    - Setting up Stoat: getting-started/setup-stoat.md
    - Your First Migration: getting-started/first-migration.md
  - Guides:
    - GUI Walkthrough: guides/gui-walkthrough.md
    - CLI Reference: guides/cli-reference.md
    - Large Servers: guides/large-servers.md
    - Self-Hosted Tips: guides/self-hosted-tips.md
    - Troubleshooting: guides/troubleshooting.md
  - Reference:
    - Architecture: reference/architecture.md
    - Stoat API Notes: reference/stoat-api-notes.md
    - DCE Format: reference/dce-format.md
  - Contributing: contributing.md
  - Changelog: changelog.md
```

### 17.3 Key Documentation Pages — Content Briefs

Each of these must be written **for someone who has never used a command line tool before** unless explicitly noted otherwise.

**`getting-started/install.md`**
- Platform tabs: Windows | macOS | Linux
- Windows: "Download Ferry.exe → double-click → done." Screenshot of Windows SmartScreen warning and how to click through it.
- macOS: "Download Ferry.dmg → drag to Applications → first launch right-click → Open." Screenshot of Gatekeeper warning.
- Linux: `pipx install discord-ferry` then `ferry --help`. Assumes terminal familiarity.
- Troubleshooting: antivirus false positives (PyInstaller binaries trigger them), macOS quarantine attribute (`xattr -d com.apple.quarantine Ferry.app`)

**`getting-started/export-discord.md`**
- This is the **most important guide** — if the export is wrong, nothing works.
- Step-by-step with numbered screenshots:
  1. Download DiscordChatExporter (link, platform instructions)
  2. Get your Discord user token (with screenshots of browser DevTools — this is the hardest part for non-technical users)
  3. Run the export command (copy-paste ready, with placeholders highlighted)
  4. Verify the export looks right (what the folder should contain)
- **Big warning box:** "You MUST use `--markdown false` and `--media`. Without these flags, your migration will have problems."
- **Big warning box:** "Use a user token, NOT a bot token. Bot tokens cannot export threads."
- FAQ: "How long does the export take?" / "Can I export just some channels?" / "What about DMs?"

**`getting-started/setup-stoat.md`**
- How to find your Stoat API URL (with screenshots of the Stoat web UI)
- How to get your Stoat user token (with screenshots)
- "Should I create the server first?" — explain the --server-id option
- Permissions: what the migration account needs (link to §5.11 in reference docs)
- **Tip box for self-hosted admins:** "You can raise limits in Revolt.overrides.toml for large migrations"

**`getting-started/first-migration.md`**
- Complete end-to-end walkthrough: export → open Ferry → configure → validate → migrate → done
- Every step has a screenshot
- Expected output: what the Stoat server looks like after migration
- "What if something goes wrong?" → link to troubleshooting

**`guides/gui-walkthrough.md`**
- Screenshot + explanation of every screen element
- Setup screen: what each field means, what "Advanced Options" do
- Validate screen: what green/amber/red means, common warnings and what to do
- Migrate screen: what the progress bar shows, how pause/resume works, what to do on errors
- Report: how to read the migration report, what the maps mean

**`guides/troubleshooting.md`**
- Table format: Symptom → Cause → Fix
- Common issues:
  - "401 Unauthorized" → wrong token or token expired
  - "403 Forbidden on server create" → using bot token, need user token
  - "429 Too Many Requests" → rate limited, increase --rate-limit
  - "Attachment file missing" → DCE export didn't download media, re-export with --media
  - "Channel limit exceeded" → too many threads, use --skip-threads or raise limit in Revolt.overrides.toml
  - Ferry.exe blocked by antivirus → false positive, how to whitelist
  - macOS "app is damaged" → quarantine attribute, how to fix

### 17.4 Community Files

**`CONTRIBUTING.md`**
```markdown
# Contributing to Discord Ferry

Thank you for your interest in contributing! 🎉

## Ways to contribute

- **Report bugs** — [open an issue](link) with the bug report template
- **Suggest features** — [open an issue](link) with the feature request template
- **Improve docs** — fix typos, add screenshots, improve guides
- **Write code** — see below

## Development setup

1. Clone the repo: `git clone ...`
2. Install uv: `pip install uv`
3. Install dependencies: `uv sync --all-extras`
4. Run tests: `uv run pytest`
5. Run the GUI in dev mode: `uv run ferry-gui`

## Code style

- We use `ruff` for linting and formatting: `uv run ruff check . && uv run ruff format .`
- Type hints on all public functions
- Docstrings on all public functions (Google style)

## Pull request process

1. Fork the repo and create a branch from `main`
2. Make your changes
3. Run `ruff check . && ruff format . && pytest`
4. Open a PR with a clear description of what and why
5. Wait for review — we aim to respond within a few days

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md).
Be kind, be respectful, be helpful.
```

**`CODE_OF_CONDUCT.md`**
Use the standard Contributor Covenant v2.1: https://www.contributor-covenant.org/version/2/1/code_of_conduct/

**`CHANGELOG.md`**
Follow Keep a Changelog format (https://keepachangelog.com/):
```markdown
# Changelog

## [Unreleased]

### Added
- Initial release
- GUI with NiceGUI local web UI
- CLI with Click
- Full Discord → Stoat migration (channels, roles, messages, emoji, pins)
- Masquerade for author attribution
- Attachment upload via Autumn
- Pause/resume support
- Migration reports
```

**`.github/ISSUE_TEMPLATE/bug_report.yml`** (structured form, not freetext)
```yaml
name: Bug Report
description: Something isn't working
labels: [bug]
body:
  - type: dropdown
    id: interface
    attributes:
      label: Which interface?
      options:
        - GUI (Ferry.exe / Ferry.app)
        - CLI (ferry command)
    validations:
      required: true
  - type: dropdown
    id: platform
    attributes:
      label: Operating system
      options:
        - Windows
        - macOS
        - Linux
    validations:
      required: true
  - type: input
    id: version
    attributes:
      label: Ferry version
      placeholder: "e.g. 0.1.0"
    validations:
      required: true
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      placeholder: Tell us what you were doing and what went wrong
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: What did you expect to happen?
    validations:
      required: true
  - type: textarea
    id: logs
    attributes:
      label: Error messages or logs
      description: Paste any error messages, or attach ferry-output/report.json
      render: shell
  - type: textarea
    id: export-info
    attributes:
      label: Export details
      description: "Approximate server size: channels, messages, attachments"
```

**`.github/PULL_REQUEST_TEMPLATE.md`**
```markdown
## What does this PR do?

<!-- Brief description -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Documentation
- [ ] Refactor

## Checklist

- [ ] I've run `ruff check . && ruff format .`
- [ ] I've run `pytest` and all tests pass
- [ ] I've updated docs if this changes user-facing behavior
- [ ] I've updated CHANGELOG.md
```

### 17.5 GitHub Repository Settings (When Going Public)

Configure these on the GitHub repo before making it public:

- **Description:** "Migrate your Discord server to Stoat (formerly Revolt) — GUI app for Windows/Mac, CLI for Linux"
- **Website:** link to GitHub Pages docs
- **Topics:** `discord`, `stoat`, `revolt`, `migration`, `python`, `gui`, `open-source`, `discord-chat-exporter`
- **Social preview image:** Use `assets/ferry-banner.png` (1280×640px recommended)
- **Releases:** Create a v0.1.0 release with `.exe`, `.dmg` and release notes before going public
- **Discussions:** Enable GitHub Discussions for Q&A (redirect support questions out of Issues)
- **Branch protection:** Require PR reviews on `main`, require CI to pass
- **Pages:** Enable GitHub Pages from the `gh-pages` branch (built by `docs.yml` action)
- **Issue labels:** Create these labels:
  - `bug`, `enhancement`, `documentation`, `good first issue`, `help wanted`
  - `gui`, `cli`, `stoat-api`, `dce-parser`, `packaging`

### 17.6 Launch Checklist

Before flipping the repo to public:

- [ ] README has download links pointing to a real release
- [ ] At least 3 screenshots in docs (validate screen, migrate screen, completed screen)
- [ ] `getting-started/export-discord.md` is complete with screenshots
- [ ] `getting-started/first-migration.md` is complete with screenshots
- [ ] `guides/troubleshooting.md` has at least 5 common issues
- [ ] CONTRIBUTING.md is filled in with real repo URLs
- [ ] LICENSE file contains full MIT text
- [ ] v0.1.0 release exists with `.exe` and `.dmg` attached
- [ ] GitHub Pages docs site is live and navigable
- [ ] No secrets, tokens, or personal data in commit history
- [ ] pyproject.toml has correct author info and repo URLs
- [ ] Social preview image is set
- [ ] Announce on: Stoat community server, r/stoatchat, relevant Discord migration discussions, stoatchat/discussions #358

---

## 18. Implementation Priority Matrix

**Build the engine first, then the GUI, then the docs.** Phase 1 delivers a working CLI migration. Phase 2 adds content transforms and the GUI. Phase 3 polishes edge cases, platform packaging, and creates all public-facing documentation.

| Task | Impact | Difficulty | Phase |
|---|---|---|---|
| **Engine + CLI foundation** | | | |
| Migration engine + event emitter pattern | Foundation | Medium | 1 |
| FerryConfig dataclass | Foundation | Easy | 1 |
| CLI skeleton (Click) | Foundation | Easy | 1 |
| DCE JSON parser + models | Foundation | Easy | 1 |
| Stoat API connection + auth check | Foundation | Easy | 1 |
| Autumn URL discovery | Foundation | Trivial | 1 |
| Server creation / --server-id | Critical | Easy | 1 |
| Role creation + permissions | High | Medium | 1 |
| Category creation | Critical | Medium | 1 |
| Channel creation + category assignment | Critical | Medium | 1 |
| Masquerade message sending | Critical | Easy | 1 |
| Rate limit handling (10 msg/10s) | Critical | Medium | 1 |
| Attachment upload via Autumn + cache | Critical | Medium | 1 |
| `colour` not `color` spelling | Medium | Trivial | 1 |
| `--markdown false` validation | High | Easy | 1 |
| CDN URL expiry detection | Medium | Easy | 1 |
| State persistence + `--resume` | High | Medium | 1 |
| Migration report generation | High | Easy | 1 |
| Rich CLI progress display | Medium | Easy | 1 |
| ——— | ——— | ——— | ——— |
| **GUI + content transforms** | | | |
| NiceGUI local web UI (3 screens) | Critical | Medium | 2 |
| Validate/dry-run screen | High | Easy | 2 |
| Live progress screen with pause/resume | High | Medium | 2 |
| Spoiler syntax conversion | High | Easy | 2 |
| Mention ID remapping | High | Medium | 2 |
| Custom emoji upload + remap | Medium | Medium | 2 |
| Emoji syntax conversion in messages | Medium | Medium | 2 |
| Original timestamp embedding | High | Easy | 2 |
| Embed flattening (fields→description) | Medium | Medium | 2 |
| Reply reference mapping | Medium | Medium | 2 |
| Forum→category+channels flattening | High | Medium | 2 |
| Thread→channel conversion | High | Medium | 2 |
| Pin preservation | Medium | Easy | 2 |
| ——— | ——— | ——— | ——— |
| **Polish, packaging + open-source release** | | | |
| PyInstaller Windows `.exe` build | Critical | Medium | 3 |
| PyInstaller macOS `.app` + `.dmg` build | Critical | Medium | 3 |
| GitHub Actions CI pipeline (lint + test) | High | Easy | 3 |
| GitHub Actions release pipeline (build + publish) | High | Medium | 3 |
| NiceGUI native mode (pywebview) | Medium | Easy | 3 |
| Reaction migration | Medium | Medium | 3 |
| Sticker→text/attachment conversion | Low | Easy | 3 |
| Voice channel creation (with bug warning) | Low | Easy | 3 |
| System message handling (join, etc.) | Low | Easy | 3 |
| Avatar upload to Autumn for masquerade | Medium | Medium | 3 |
| Animated emoji → static warning | Low | Trivial | 3 |
| Channel limit (200) protection | Medium | Easy | 3 |
| Emoji limit (100) protection | Medium | Easy | 3 |
| Underline markup stripping | Low | Trivial | 3 |
| ——— | ——— | ——— | ——— |
| **Documentation — ALL "for dummies" (§17)** | | | |
| README.md (per §17.1 template — download links, 3-step flow, screenshots) | Critical | Medium | 3 |
| Logo, banner, social preview image (`assets/`) | High | Easy | 3 |
| `export-discord.md` — step-by-step DCE guide with screenshots | Critical | Medium | 3 |
| `install.md` — per-platform install with SmartScreen/Gatekeeper screenshots | Critical | Easy | 3 |
| `first-migration.md` — end-to-end walkthrough with screenshots | Critical | Medium | 3 |
| `setup-stoat.md` — finding API URL + token with screenshots | High | Easy | 3 |
| `gui-walkthrough.md` — every screen explained with screenshots | High | Medium | 3 |
| `cli-reference.md` — all flags, env vars, examples | Medium | Easy | 3 |
| `troubleshooting.md` — symptom→cause→fix table (min 5 issues) | High | Easy | 3 |
| `large-servers.md` — 100k+ message tips, Revolt.toml overrides | Medium | Easy | 3 |
| MkDocs Material site (`mkdocs.yml` + GitHub Pages deploy) | High | Easy | 3 |
| CONTRIBUTING.md, CODE_OF_CONDUCT.md, CHANGELOG.md | High | Easy | 3 |
| Issue templates (bug_report.yml, feature_request.yml) | Medium | Easy | 3 |
| PR template | Medium | Trivial | 3 |
| GitHub repo settings (topics, description, Discussions, labels) | Medium | Trivial | 3 |
| Complete §17.6 launch checklist before flipping to public | Critical | — | 3 |
