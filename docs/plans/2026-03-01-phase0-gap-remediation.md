# Phase 0 Gap Remediation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix 4 spec deviations found during post-ship gap analysis of Phase 0 DCE Orchestration (v1.2.0).

**Architecture:** All changes are additive — no architecture modifications. G1 adds a CLI confirm prompt, G2 adds a conditional card to the GUI export page, G3 wraps the download in a retry loop, G4 replaces an external link with an inline dialog.

**Tech Stack:** Click (CLI), NiceGUI (GUI), aiohttp (download retry), pytest + aioresponses (tests)

---

### Task 1: CLI ToS Disclaimer (G1)

**Files:**
- Modify: `src/discord_ferry/cli.py:203-240` (add `--yes` option)
- Modify: `src/discord_ferry/cli.py:314-340` (add confirm prompt in `migrate`)
- Test: `tests/test_cli.py`

**Step 1: Write the failing tests**

Add three tests to `tests/test_cli.py`:

```python
def test_migrate_orchestrated_prompts_tos(runner: CliRunner) -> None:
    """Orchestrated mode prompts for ToS confirmation."""
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--discord-token", "dt",
                "--discord-server", "12345",
                "--stoat-url", "http://localhost",
                "--token", "t",
            ],
            input="n\n",  # decline ToS
        )
    assert result.exit_code == 1
    assert "Terms of Service" in result.output


def test_migrate_orchestrated_yes_flag_skips_tos(runner: CliRunner) -> None:
    """--yes flag bypasses ToS prompt in orchestrated mode."""
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--discord-token", "dt",
                "--discord-server", "12345",
                "--stoat-url", "http://localhost",
                "--token", "t",
                "--yes",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0


def test_migrate_offline_no_tos_prompt(runner: CliRunner) -> None:
    """Offline mode (--export-dir) does not prompt for ToS."""
    mock_engine = _make_mock_engine()
    with patch("discord_ferry.cli.run_migration", mock_engine):
        result = runner.invoke(
            main,
            [
                "migrate",
                "--export-dir", FIXTURES_DIR,
                "--stoat-url", "http://localhost",
                "--token", "t",
            ],
            catch_exceptions=False,
        )
    assert result.exit_code == 0
    assert "Terms of Service" not in result.output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py::test_migrate_orchestrated_prompts_tos tests/test_cli.py::test_migrate_orchestrated_yes_flag_skips_tos tests/test_cli.py::test_migrate_offline_no_tos_prompt -v`
Expected: FAIL — no ToS prompt exists, `--yes` is not a recognized option

**Step 3: Implement**

In `src/discord_ferry/cli.py`, add `--yes` to `_common_options` (after `--max-emoji`):

```python
    click.option("--yes", "-y", is_flag=True, default=False, help="Skip ToS confirmation prompt"),
```

In the `migrate` command function, after `config = _build_config(kwargs)` succeeds (around line 333), add:

```python
    if not config.skip_export and not kwargs.get("yes"):
        click.confirm(
            "Using a user token may violate Discord's Terms of Service. Continue?",
            abort=True,
        )
```

Wrap the entire `try: config = _build_config(...)` block to also catch `click.exceptions.Abort`:

```python
    try:
        config = _build_config(kwargs)
    except click.UsageError as exc:
        console.print(f"[bold red]Error:[/] {exc}")
        sys.exit(1)

    if not config.skip_export and not kwargs.get("yes"):
        try:
            click.confirm(
                "Using a user token may violate Discord's Terms of Service. Continue?",
                abort=True,
            )
        except click.exceptions.Abort:
            sys.exit(1)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All tests pass including the 3 new ones

**Step 5: Run full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest`
Expected: All green

---

### Task 2: GUI Smart Resume Dialog (G2)

**Files:**
- Modify: `src/discord_ferry/gui.py:488-495` (top of `export_page()`)
- Test: `tests/test_gui.py`

**Step 1: Write the failing tests**

Add two tests to `tests/test_gui.py`:

```python
def test_export_page_detects_cached_exports(tmp_path: Path) -> None:
    """_detect_cached_exports returns summary when JSON files exist."""
    from discord_ferry.gui import _detect_cached_exports

    # Create fake export files
    (tmp_path / "guild - general [123].json").write_text('{"messageCount": 50}')
    (tmp_path / "guild - memes [456].json").write_text('{"messageCount": 100}')

    result = _detect_cached_exports(tmp_path)
    assert result is not None
    assert result["file_count"] == 2
    assert result["total_size"] > 0


def test_export_page_no_cached_exports(tmp_path: Path) -> None:
    """_detect_cached_exports returns None when no JSON files exist."""
    from discord_ferry.gui import _detect_cached_exports

    result = _detect_cached_exports(tmp_path)
    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gui.py::test_export_page_detects_cached_exports tests/test_gui.py::test_export_page_no_cached_exports -v`
Expected: FAIL — `_detect_cached_exports` does not exist

**Step 3: Implement the helper function**

Add a helper function in `gui.py` (near the top, after the imports, around line 30):

```python
def _detect_cached_exports(export_dir: Path) -> dict[str, int] | None:
    """Check for existing DCE JSON exports in a directory.

    Returns:
        Dict with 'file_count' and 'total_size' (bytes), or None if no exports found.
    """
    json_files = list(export_dir.glob("*.json"))
    if not json_files:
        return None
    total_size = sum(f.stat().st_size for f in json_files)
    return {"file_count": len(json_files), "total_size": total_size}
```

**Step 4: Run helper tests to verify they pass**

Run: `uv run pytest tests/test_gui.py::test_export_page_detects_cached_exports tests/test_gui.py::test_export_page_no_cached_exports -v`
Expected: PASS

**Step 5: Add the cached export card to export_page**

In `export_page()` (around line 495), after the mode check and before the main card, add:

```python
    # Check for cached exports
    discord_server = str(storage.get("discord_server_id", ""))
    output_dir = Path(str(storage.get("output_dir", "./ferry-output")))
    export_dir = output_dir / "dce_cache" / discord_server
    cached = _detect_cached_exports(export_dir) if export_dir.exists() else None

    if cached is not None:
        size_mb = cached["total_size"] / 1_000_000
        with ui.card().classes("w-full max-w-2xl shadow-md fade-in bg-blue-50"):
            ui.label("Found cached exports").classes("text-lg font-bold")
            ui.label(
                f"{cached['file_count']} files · {size_mb:.1f} MB"
            ).classes("text-sm text-gray-600")
            with ui.row().classes("w-full justify-end gap-2 mt-2"):
                ui.button(
                    "Use Cached", on_click=lambda: ui.navigate.to("/validate")
                ).classes("bg-green-600 text-white")
                ui.button(
                    "Re-export", on_click=lambda: cached_card.set_visibility(False)
                ).classes("bg-gray-500 text-white")
        cached_card = ui.element("div")  # placeholder for visibility binding
```

**Important**: The cached card and the main export card must be siblings. When "Re-export" is clicked, hide the cached card and let the normal export flow proceed. The simplest approach: wrap the cached card in a container and toggle its visibility.

Refined approach — wrap both in a container:

```python
    cached = _detect_cached_exports(export_dir) if export_dir.exists() else None
    show_export = ui.state(cached is None)  # True = show export UI, False = show cached card
```

Actually, keep it simple. Use a `ref` pattern:

At the top of `export_page()`, after the mode check:

```python
    discord_server = str(storage.get("discord_server_id", ""))
    output_dir = Path(str(storage.get("output_dir", "./ferry-output")))
    export_dir = output_dir / "dce_cache" / discord_server
    cached = _detect_cached_exports(export_dir) if export_dir.exists() else None

    if cached is not None:
        size_mb = cached["total_size"] / 1_000_000
        with ui.column().classes("w-full items-center min-h-screen bg-gray-50 py-10") as cached_view:
            with ui.element("div").classes("w-full max-w-2xl fade-in"):
                _render_step_indicator(active_step=2)
            with ui.card().classes("w-full max-w-2xl shadow-md fade-in"):
                ui.label("Found cached exports").classes("text-xl font-bold text-center mt-2")
                ui.label(
                    f"{cached['file_count']} files · {size_mb:.1f} MB"
                ).classes("text-sm text-gray-500 text-center mb-4")
                with ui.row().classes("w-full justify-center gap-4 mt-2"):
                    ui.button(
                        "Use Cached", on_click=lambda: ui.navigate.to("/validate")
                    ).props("color=green")
                    def _re_export():
                        cached_view.set_visibility(False)
                        export_view.set_visibility(True)
                    ui.button("Re-export", on_click=_re_export).props("color=grey")
        # The normal export UI follows, initially hidden
        export_view_visible = False
    else:
        export_view_visible = True
```

Then wrap the existing export UI column in:

```python
    with ui.column().classes("w-full items-center min-h-screen bg-gray-50 py-10") as export_view:
        export_view.set_visibility(export_view_visible)
        # ... existing export page content ...
```

This is the cleanest approach — two sibling views, one visible at a time.

**Step 6: Run full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest`
Expected: All green

---

### Task 3: DCE Download Retry (G3)

**Files:**
- Modify: `src/discord_ferry/exporter/manager.py:89-177` (`download_dce` function)
- Test: `tests/test_exporter_manager.py`

**Step 1: Write the failing tests**

Add to `tests/test_exporter_manager.py`:

```python
import asyncio
import io
import zipfile
from unittest.mock import AsyncMock

import pytest
from aioresponses import aioresponses

from discord_ferry.exporter.manager import DCE_VERSION, download_dce


def _make_dce_zip() -> bytes:
    """Create a minimal valid DCE zip in memory."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("DiscordChatExporter.Cli", "#!/bin/sh\necho ok\n")
    return buf.getvalue()


class TestDownloadDceRetry:
    @pytest.mark.asyncio
    async def test_retries_once_on_network_error(self, tmp_path):
        """download_dce retries once on network error then succeeds."""
        events = []
        dce_zip = _make_dce_zip()
        release_url = f"https://api.github.com/repos/Tyrrrz/DiscordChatExporter/releases/tags/v{DCE_VERSION}"

        with (
            aioresponses() as m,
            patch("discord_ferry.exporter.manager._get_dce_dir", return_value=tmp_path),
            patch("discord_ferry.exporter.manager._get_asset_name", return_value="test.zip"),
            patch("discord_ferry.exporter.manager.get_dce_path", return_value=tmp_path / "DiscordChatExporter.Cli"),
            patch("discord_ferry.exporter.manager.asyncio.sleep", new_callable=AsyncMock),
        ):
            # First call fails, second succeeds
            m.get(release_url, exception=Exception("network error"))
            m.get(release_url, status=200, payload={
                "assets": [{"name": "test.zip", "browser_download_url": "https://example.com/test.zip"}]
            })
            m.get("https://example.com/test.zip", status=200, body=dce_zip)
            (tmp_path / "DiscordChatExporter.Cli").touch()

            result = await download_dce(events.append)
            assert result is not None
            retry_msgs = [e.message for e in events if "retry" in e.message.lower() or "Retrying" in e.message]
            assert len(retry_msgs) >= 1

    @pytest.mark.asyncio
    async def test_fails_after_two_attempts(self, tmp_path):
        """download_dce raises after both attempts fail."""
        from discord_ferry.errors import DCENotFoundError

        events = []
        release_url = f"https://api.github.com/repos/Tyrrrz/DiscordChatExporter/releases/tags/v{DCE_VERSION}"

        with (
            aioresponses() as m,
            patch("discord_ferry.exporter.manager._get_dce_dir", return_value=tmp_path),
            patch("discord_ferry.exporter.manager._get_asset_name", return_value="test.zip"),
            patch("discord_ferry.exporter.manager.asyncio.sleep", new_callable=AsyncMock),
        ):
            m.get(release_url, exception=Exception("network error"))
            m.get(release_url, exception=Exception("network error again"))

            with pytest.raises(DCENotFoundError, match="Network error"):
                await download_dce(events.append)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_exporter_manager.py::TestDownloadDceRetry -v`
Expected: FAIL — no retry logic exists

**Step 3: Implement retry in download_dce**

In `src/discord_ferry/exporter/manager.py`, modify `download_dce()`. Add `import asyncio` at the top if not already present. Wrap the `try/except aiohttp.ClientError` block in a retry loop:

```python
async def download_dce(on_event: EventCallback) -> Path:
    from discord_ferry.core.events import MigrationEvent

    asset_name = _get_asset_name()
    release_url = _GITHUB_RELEASE_URL.format(version=DCE_VERSION)
    dce_dir = _get_dce_dir()

    on_event(
        MigrationEvent(
            phase="export",
            status="progress",
            message=f"Downloading DiscordChatExporter v{DCE_VERSION}...",
        )
    )

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    release_url, headers={"Accept": "application/vnd.github.v3+json"}
                ) as resp:
                    if resp.status != 200:
                        raise DCENotFoundError(
                            f"GitHub API returned {resp.status} for DCE v{DCE_VERSION}"
                        )
                    release_data = await resp.json()

                download_url: str | None = None
                for asset in release_data.get("assets", []):
                    if asset["name"] == asset_name:
                        download_url = asset["browser_download_url"]
                        break

                if download_url is None:
                    raise DCENotFoundError(
                        f"Asset {asset_name} not found in DCE v{DCE_VERSION} release"
                    )

                async with session.get(download_url) as resp:
                    if resp.status != 200:
                        raise DCENotFoundError(
                            f"Failed to download {asset_name}: HTTP {resp.status}"
                        )
                    data = await resp.read()
                    if len(data) > _MAX_DCE_BYTES:
                        raise DCENotFoundError(
                            f"DCE download unexpectedly large ({len(data)} bytes); aborting"
                        )

            break  # success — exit retry loop

        except (aiohttp.ClientError, DCENotFoundError) as e:
            last_error = e
            if attempt == 0:
                on_event(
                    MigrationEvent(
                        phase="export",
                        status="progress",
                        message="Download failed, retrying in 3s...",
                    )
                )
                await asyncio.sleep(3)
            else:
                raise DCENotFoundError(f"Network error downloading DCE: {e}") from e

    # Extract zip (unchanged from current code)
    dce_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for member in zf.infolist():
                member_path = (dce_dir / member.filename).resolve()
                if not str(member_path).startswith(str(dce_dir.resolve())):
                    raise DCENotFoundError(
                        f"Zip entry {member.filename!r} would extract outside target directory"
                    )
            zf.extractall(dce_dir)
    except zipfile.BadZipFile as e:
        raise DCENotFoundError(f"Downloaded file is not a valid zip: {e}") from e

    exe_path = get_dce_path()
    if exe_path is None:
        raise DCENotFoundError(f"Extraction succeeded but executable not found in {dce_dir}")

    if platform.system() != "Windows":
        exe_path.chmod(0o755)

    on_event(
        MigrationEvent(
            phase="export",
            status="progress",
            message=f"DiscordChatExporter v{DCE_VERSION} ready.",
        )
    )

    return exe_path
```

**Key change**: The `try/except` now wraps the entire HTTP section. On first failure (`attempt == 0`), emit a "retrying" event, sleep 3s, and loop. On second failure (`attempt == 1`), raise.

**Do NOT retry** `zipfile.BadZipFile` — that happens after download succeeds and won't fix itself.

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_exporter_manager.py -v`
Expected: All tests pass including the 2 new retry tests

**Step 5: Run full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest`
Expected: All green

---

### Task 4: Built-in Token Help Dialog (G4)

**Files:**
- Modify: `src/discord_ferry/gui.py:293-299` (replace external link with dialog trigger)

**No tests needed** — this is purely UI content with no logic.

**Step 1: Replace external link with dialog**

In `src/discord_ferry/gui.py`, find the block at lines 293-299:

```python
                    with ui.row().classes("items-center gap-1 -mt-2"):
                        ui.icon("help_outline", size="16px").classes("text-gray-400")
                        ui.link(
                            "How to find your Discord token and server ID",
                            "https://github.com/Tyrrrz/DiscordChatExporter/wiki",
                            new_tab=True,
                        ).classes("text-xs text-blue-600")
```

Replace with:

```python
                    with ui.dialog() as help_dialog, ui.card().classes("max-w-lg"):
                        ui.label("How to find your Discord credentials").classes(
                            "text-lg font-bold mb-2"
                        )
                        ui.label("Discord Token").classes("text-sm font-bold mt-2")
                        with ui.element("ol").classes("text-sm text-gray-700 pl-4"):
                            ui.element("li").text(
                                "Open Discord in your browser (not the desktop app)"
                            )
                            ui.element("li").text("Press F12 to open Developer Tools")
                            ui.element("li").text(
                                'Go to the Network tab and type "/api" in the filter'
                            )
                            ui.element("li").text(
                                "Click any channel in Discord, then find a request"
                            )
                            ui.element("li").text(
                                'Click the request → Headers → copy the "Authorization" value'
                            )
                        ui.label("Server ID").classes("text-sm font-bold mt-3")
                        with ui.element("ol").classes("text-sm text-gray-700 pl-4"):
                            ui.element("li").text(
                                "In Discord, go to Settings → App Settings → Advanced"
                            )
                            ui.element("li").text("Enable Developer Mode")
                            ui.element("li").text(
                                "Right-click your server name → Copy Server ID"
                            )
                        with ui.row().classes("w-full justify-end mt-4"):
                            ui.button("Got it", on_click=help_dialog.close).props("flat")

                    with ui.row().classes("items-center gap-1 -mt-2"):
                        ui.icon("help_outline", size="16px").classes("text-gray-400")
                        ui.link(
                            "How to find your Discord token and server ID",
                            target=help_dialog,
                        ).classes("text-xs text-blue-600 cursor-pointer")
```

**NiceGUI note**: `ui.link` with `target=` pointing to a dialog will open it on click. If that doesn't work in the current NiceGUI version, fall back to:

```python
                        ui.label(
                            "How to find your Discord token and server ID"
                        ).classes("text-xs text-blue-600 cursor-pointer").on(
                            "click", lambda: help_dialog.open()
                        )
```

**Step 2: Run full verification**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest`
Expected: All green

---

### Task 5: Version bump and docs

**Files:**
- Modify: `src/discord_ferry/__init__.py` — bump `1.2.0` → `1.2.1`
- Modify: `pyproject.toml` — bump `1.2.0` → `1.2.1`
- Modify: `CHANGELOG.md` — add `[1.2.1]` entry

**Step 1: Bump version in both files**

`src/discord_ferry/__init__.py`:
```python
__version__ = "1.2.1"
```

`pyproject.toml`:
```toml
version = "1.2.1"
```

**Step 2: Add CHANGELOG entry**

Under `## [Unreleased]`, add:

```markdown
## [1.2.1] — 2026-03-01

### Added

- **CLI ToS disclaimer**: Orchestrated mode now prompts for Discord ToS acknowledgment. Use `--yes` / `-y` to skip in scripts.
- **GUI smart resume**: Export page detects cached exports and offers [Use Cached] or [Re-export] choice.
- **DCE download retry**: `download_dce()` retries once on network error before failing.
- **Built-in token help**: "How to find these?" opens an inline dialog with step-by-step instructions instead of linking to external wiki.
```

**Step 3: Run full verification and ship**

Run: `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest`
Then: `/ship`
