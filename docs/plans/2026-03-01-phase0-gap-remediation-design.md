# Design: Phase 0 Gap Remediation

**Brief**: Gap analysis comparing original design doc, brief, and approved design against shipped v1.2.0.
**Status**: Approved
**Complexity**: Medium (4 small fixes across 3 files, no architecture changes)

## Context

Phase 0 DCE Orchestration shipped in `68e3b59` (v1.2.0). A post-ship gap analysis found 4 spec deviations:

| Gap | Severity | Source |
|-----|----------|--------|
| G1: CLI ToS disclaimer missing | Medium | Design §7.1, Brief #12 |
| G2: GUI smart resume dialog missing | Medium | Design doc §5 |
| G3: DCE download retry missing | Low | Design doc §7 error matrix |
| G4: Token help is external link, not built-in modal | Low | Design §5.1 |

## G1: CLI ToS Disclaimer

**Problem**: Users running `--discord-token` on the CLI get no Discord ToS warning. The GUI has a checkbox; the CLI has nothing.

**Design**: Add `click.confirm()` prompt when `--discord-token` is provided.

```python
# In migrate command, after _build_config but before run_migration
if not config.skip_export:
    if not kwargs.get("yes"):
        click.confirm(
            "Using a user token may violate Discord's Terms of Service. Continue?",
            abort=True,
        )
```

- `--yes` / `-y` flag bypasses the prompt for scripted usage
- Only triggered in orchestrated mode (not offline)
- `abort=True` means declining exits immediately

**Files**: `src/discord_ferry/cli.py`

---

## G2: GUI Smart Resume Dialog

**Problem**: If the user re-runs Ferry after a successful export (or crash), the export page always runs a fresh export. No detection of existing cached exports.

**Design**: At the top of `export_page()`, check for existing JSON files in the export directory. If found, show a card with summary and two buttons.

```
┌─────────────────────────────────────────────┐
│  📦 Found cached exports                    │
│  X channels · Y files · Z MB               │
│                                             │
│  [Use Cached]          [Re-export]          │
└─────────────────────────────────────────────┘
```

- [Use Cached] → `ui.navigate.to("/validate")`
- [Re-export] → hide card, show normal export progress UI
- Detection: `list(export_dir.glob("*.json"))` — count files, sum sizes
- Export dir derived from storage: `output_dir / "dce_cache" / server_id`

**Files**: `src/discord_ferry/gui.py`

---

## G3: DCE Download Retry

**Problem**: `download_dce()` fails immediately on any network error. The design doc specifies "retry once, then error."

**Design**: Wrap the download section in a retry loop (max 1 retry, 3s delay). Only retry on transient errors.

```python
async def download_dce(on_event) -> Path:
    ...
    for attempt in range(2):  # 0 = first try, 1 = retry
        try:
            # existing download logic
            ...
            break
        except (aiohttp.ClientError, DCENotFoundError) as e:
            if attempt == 0:
                on_event(MigrationEvent(
                    phase="export", status="progress",
                    message="Download failed, retrying in 3s..."
                ))
                await asyncio.sleep(3)
            else:
                raise
```

- Only retry on `aiohttp.ClientError` (network) and `DCENotFoundError` (HTTP status)
- Do NOT retry on `zipfile.BadZipFile` (corrupt download won't fix itself)
- Emit progress event on retry so GUI/CLI show what's happening

**Files**: `src/discord_ferry/exporter/manager.py`

---

## G4: Built-in Token Help Modal

**Problem**: "How to find these?" is an external link to DCE wiki. Design specified a built-in NiceGUI modal with step-by-step instructions.

**Design**: Replace `ui.link` with a clickable element that opens `ui.dialog()`.

Dialog content (5 steps):
1. Open Discord in your **browser** (not desktop app)
2. Press **F12** → open the **Network** tab
3. Type `/api` in the network filter bar
4. Click any channel in Discord, then find a request in the Network tab
5. Click the request → **Headers** tab → copy the `Authorization` value

For server ID:
1. Enable **Developer Mode** in Discord Settings → App Settings → Advanced
2. Right-click your server name → **Copy Server ID**

- Uses `ui.dialog()` with `ui.card()` inside — standard NiceGUI pattern
- Replaces the external link entirely
- Self-contained: works offline, doesn't depend on DCE wiki

**Files**: `src/discord_ferry/gui.py`

---

## Testing

| Gap | Test approach | Count |
|-----|--------------|-------|
| G1 | Click test runner: orchestrated without `--yes` prompts, with `--yes` skips | ~3 |
| G2 | Check export page shows cached card when JSONs exist, hides when empty | ~2 |
| G3 | Mock aiohttp to fail once then succeed; mock to fail twice and raise | ~2 |
| G4 | No test needed (UI-only, no logic) | 0 |
| **Total** | | **~7** |

## Files Changed

- `src/discord_ferry/cli.py` — G1: `--yes` flag, confirm prompt
- `src/discord_ferry/gui.py` — G2: cached export card, G4: help dialog
- `src/discord_ferry/exporter/manager.py` — G3: download retry
- `tests/test_cli.py` — G1 tests
- `tests/test_gui.py` — G2 tests
- `tests/test_exporter_manager.py` — G3 tests

## Version

Patch bump: 1.2.0 → 1.2.1 (bugfix/polish, no new features)
