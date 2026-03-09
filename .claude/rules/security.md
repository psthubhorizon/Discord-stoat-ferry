---
description: "Security rules for token handling, credential safety, and sensitive data"
globs:
  - "src/discord_ferry/config.py"
  - "src/discord_ferry/cli.py"
  - "src/discord_ferry/gui.py"
  - "src/discord_ferry/discord/**"
---

# Security Rules (Mandatory)

## Token & Credential Handling

| Rule | Why |
|------|-----|
| **Never log tokens** | Stoat tokens and Discord tokens must never appear in log output, error messages, or state files. `FerryConfig.discord_token` is `repr=False`. |
| **Never persist Discord tokens to disk** | NiceGUI `app.storage.user` writes to `.nicegui/storage-user.json` — clear after use: `storage.pop("discord_token", None)`. |
| **Never commit .env files** | `.env` contains `STOAT_TOKEN` and `DISCORD_TOKEN`. Must remain in `.gitignore`. |
| **Never embed tokens in URLs** | Use request headers or body parameters. |

## CLI Token Safety

- Click options for tokens should use `hide_input=True` where possible
- The `--yes` flag bypasses ToS confirmation — acceptable for automation but must not bypass token validation

## State File Safety

- `state.json` contains ID mappings only (Discord IDs → Stoat IDs). No tokens, no message content.
- `discord_metadata.json` contains server structure data. No tokens.
- Both files live in the output directory, not the project root.

## Export Safety

- DCE exports may contain private message content. The `ferry-output/` directory should be treated as sensitive.
- Never commit export data or ferry output to git.

## GUI Storage

- NiceGUI storage persists to `.nicegui/storage-user.json`. This file is gitignored but exists on disk.
- Clear all token-like values from storage when migration completes or errors.
