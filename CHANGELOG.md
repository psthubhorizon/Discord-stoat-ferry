# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [0.3.0] — 2026-02-26

### Added

- **Migration engine** (`core/engine.py`): 11-phase orchestrator with phase injection for testing, resume support (skip completed phases), and config-based skip flags for emoji/messages/reactions
- **State persistence** (`state.py`): atomic save/load with JSON round-tripping, crash recovery (state saved on error), author name tracking, counter fields for reactions/pins/attachments
- **Report generator** (`reporter.py`): produces `migration_report.json` per brief §12 with summary counts, ID maps, timing, warnings, and errors
- **Event callback** (`core/events.py`): `EventCallback` type alias and `"skipped"` status for phase events
- **40 new tests** across engine (18), reporter (15), and state (7) — 111 total passing

## [0.2.0] — 2026-02-26

### Added

- **DCE parser** (`parser/dce_parser.py`): parse DiscordChatExporter JSON exports into typed models, with thread/forum inference from filename patterns and export validation (rendered markdown detection, missing media, channel/emoji limits)
- **Content transforms** (`parser/transforms.py`): spoiler conversion, mention/emoji/underline remapping, embed flattening (Discord→Stoat), timestamp formatting, sticker placeholders — all code-block-aware
- **Typed data models** (`parser/models.py`): 10 dataclasses (DCEGuild, DCEChannel, DCEAuthor, DCERole, DCEAttachment, DCEEmoji, DCEReaction, DCEReference, DCEMessage, DCEExport)
- **Test fixtures**: 5 realistic DCE JSON files covering text channels, threads, forums, edge cases, and rendered markdown detection
- **71 passing tests** across parser (27) and transforms (42) with full coverage of edge cases

## [0.1.0] — 2026-02-26

### Added

- Project scaffolding and Claude Code configuration
- Migration engine skeleton (11-phase architecture)
- CLI skeleton (Click)
- GUI skeleton (NiceGUI)
- DCE parser data models (stubs)
- Migration state management dataclass
- Custom `/ship` skill for commit discipline
