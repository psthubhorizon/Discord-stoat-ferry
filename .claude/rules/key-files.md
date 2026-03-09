---
description: "Critical file pointers for navigating the codebase"
---

# Key Files

## Engine (Shared Core)

| File | Purpose |
|------|---------|
| `src/discord_ferry/core/engine.py` | Migration orchestrator (12 phases). NEVER imports GUI or CLI. |
| `src/discord_ferry/core/events.py` | Event emitter pattern for progress reporting |
| `src/discord_ferry/config.py` | FerryConfig dataclass (all migration parameters) |
| `src/discord_ferry/state.py` | MigrationState (ID maps, checkpoints, resume support) |
| `src/discord_ferry/errors.py` | Custom exception hierarchy (FerryError base) |

## Shells (Thin Wrappers)

| File | Purpose |
|------|---------|
| `src/discord_ferry/gui.py` | NiceGUI web interface (subscribes to engine events) |
| `src/discord_ferry/cli.py` | Click + Rich CLI (subscribes to engine events) |

## Migration Phases

| File | Purpose |
|------|---------|
| `src/discord_ferry/migrator/` | All migration phase implementations |
| `src/discord_ferry/migrator/api.py` | Stoat API client (aiohttp, retry, rate limits) |
| `src/discord_ferry/migrator/messages.py` | Message migration (content, masquerade, replies) |
| `src/discord_ferry/migrator/structure.py` | Server/channels/roles/categories creation |

## Parsing & Transform

| File | Purpose |
|------|---------|
| `src/discord_ferry/parser/` | DCE JSON parsing and data models |
| `src/discord_ferry/parser/models.py` | Dataclass models for parsed exports |
| `src/discord_ferry/parser/transforms.py` | Content transformation (mentions, embeds, formatting) |

## Data Pipeline

| File | Purpose |
|------|---------|
| `src/discord_ferry/uploader/` | Autumn file upload client |
| `src/discord_ferry/discord/` | Discord REST API client (permissions, metadata) |
| `src/discord_ferry/review.py` | Pre-creation review summary |
| `src/discord_ferry/blueprint.py` | Server blueprint export/import |
| `src/discord_ferry/templates/` | Preset server templates (gaming, community, education) |

## Config & Build

| File | Purpose |
|------|---------|
| `src/discord_ferry/__init__.py` | Version string (PyInstaller reads this) |
| `pyproject.toml` | Version, deps, tool config |
| `ferry.spec` | PyInstaller build spec (includes template JSON data) |

## Design Documents (local-only — gitignored)

All `docs/plans/` content is gitignored. These files exist locally for the design workflow but must never be committed to the public repo.

| Path | Purpose |
|------|---------|
| `docs/plans/briefs/` | Brief documents from /brief |
| `docs/plans/specs/` | Spec documents from /spec |
| `docs/plans/designs/` | Design documents from /brainstorm |
| `docs/plans/` | Implementation plans |
