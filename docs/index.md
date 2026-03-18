# Discord Ferry

**Migrate your Discord server to Stoat (formerly Revolt) — messages, channels, roles, emoji, attachments, and all.**

One-click app for Windows and Mac. Command-line interface for Linux. No coding required.

<!-- screenshot: ferry-gui-validate-and-migrate-screens-side-by-side -->

---

## Get Started in 3 Steps

1. **[Install Ferry](getting-started/install.md)** — download the app for Windows, macOS, or Linux
2. **[Set up Stoat](getting-started/setup-stoat.md)** — find your Stoat API URL (the address Ferry uses to connect) and user token (a secret key your browser saves when you log in — no bot or app creation needed). New to Stoat? [Create a free account](https://app.stoat.chat).
3. **[Run your first migration](getting-started/first-migration.md)** — enter your Discord and Stoat credentials, click Migrate

Already have DiscordChatExporter (DCE) exports? See [Offline Migration](getting-started/export-discord.md) to skip the export step.

---

## How Long Does It Take?

About **1 message per second**. Stoat limits how fast data can be sent to protect the service, which sets this pace:

| Server size | Estimated time |
|-------------|---------------|
| 1,000 messages | ~17 minutes |
| 10,000 messages | ~3 hours |
| 100,000 messages | ~28 hours |

Ferry can **pause and resume** — close it anytime and pick up where you left off.

---

## What Gets Migrated?

| Feature | Status |
|---------|--------|
| Text channels | Supported |
| Categories | Supported |
| Roles (with colours and permissions) | Supported — Discord permissions translated to Stoat equivalents |
| Channel permissions | Supported — per-role and @everyone overrides migrated |
| NSFW channels | Supported — NSFW flag set during channel creation |
| Messages + author names | Supported (each message shows the original author's name and avatar) |
| File attachments | Supported |
| Custom emoji | Supported (up to 100) |
| Pinned messages | Supported |
| Replies | Supported |
| Reactions | Supported (without per-user attribution) |
| Embeds (with media) | Supported (thumbnails and images uploaded) |
| Polls | Supported (rendered as formatted text) |
| Threads | Supported (converted to text channels) |
| Forum posts | Supported (grouped into dedicated categories) |
| Voice channels | Partial (created but do not work yet — known Stoat bug) |
| Stickers | Image upload with text fallback for animated or unavailable stickers |
| Original timestamps | Shown in message text, not metadata |
| Pre-creation review | Supported — summary and confirmation before anything is created on Stoat |
| Server blueprints | Supported — export your server's channel and role structure as a reusable template file |
| Avatar pre-flight | Supported — uploads author avatars before migration, with CDN fallback for missing files |
| Dead-letter queue | Supported — failed messages tracked and retryable without re-running the full migration |
| Configurable reactions | Supported — text summary (default), native API calls, or skip entirely |
| Discord link rewriting | Supported — jump links and invite URLs annotated for Stoat context |
| Circuit breaker | Supported — exponential backoff prevents indefinite blocking on Stoat API failures |
| Thread filtering | Supported — exclude low-activity threads by minimum message count |
| Post-migration validation | Supported — verifies Stoat server structure matches the source |
| Markdown report | Supported — human-readable `migration_report.md` generated after migration |
| Server banner migration | Supported |
| Forum post index channels | Supported — index channel created per forum category listing all posts |
| CDN URL validation | Supported — detects expired Discord attachment URLs before migration starts |

---

## Guides

- [GUI Walkthrough](guides/gui-walkthrough.md) — every screen explained
- [CLI Reference](guides/cli-reference.md) — all command-line options and configuration settings
- [Large Servers](guides/large-servers.md) — tips for 100k+ message migrations
- [Self-Hosted Tips](guides/self-hosted-tips.md) — raising limits, custom configuration
- [Troubleshooting](guides/troubleshooting.md) — common issues and solutions
- [Pre-Flight Checklist](guides/pre-flight-checklist.md) — verify your setup before migrating
- [Known Limitations](guides/known-limitations.md) — platform constraints and unsupported features

## Reference

- [Architecture](reference/architecture.md) — how the engine works
- [Stoat API Notes](reference/stoat-api-notes.md) — speed limits, permission mapping, and known quirks
- [DiscordChatExporter Format](reference/dce-format.md) — export file structure and field reference
