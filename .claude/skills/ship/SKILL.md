---
name: ship
description: The ONLY way to commit code. Runs verification, audit, code review, second opinion, documentation, and commit in sequence. Adapted from HubSpot Health Hero's shipping gate for Python.
user_invocable: true
allowed-tools: Bash, Read, Edit, Write, Grep, Glob
---

# /ship — The Only Way to Commit

Eight mandatory sequential steps. Do NOT skip any step. If a step fails, fix the issue and restart from Step 1.

## Step 1: Verify (conditional)

If ALL of the following are true, skip to Step 2:
- Build phase already ran `uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest` with no errors
- No code has been modified since the last successful build

Otherwise, run the full verification suite — stop on first failure:
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest
```

If anything fails: fix it, then restart from Step 1.

**Always re-run after code review or second opinion fixes** — fixes in Steps 3-4 invalidate prior verification.

Report: "Verify: skipped (build phase passed, no changes since)" or "Verify: running full suite..."

## Step 2: Audit

**If `.claude/change-manifest.md` exists** (preferred path):
- Read the manifest's "Audit Targets" section
- Run ONLY the grep patterns specified there
- Report results against the manifest — do NOT re-explore files or re-read changed code
- "Audit: verified against manifest — all N targets pass" or "Audit: manifest target failed in [file]"

**If no manifest exists** (fallback):
- Grep the entire codebase for the pattern(s) just changed. Report any unaddressed instances.
- Examples:
  - Changed how masquerade colour is set? Grep for all masquerade usage.
  - Changed error handling in one migrator? Check all migrators follow the same pattern.
  - Changed a dataclass field? Check all usages.

If unaddressed instances found: fix them, then restart from Step 1.

## Step 3: Code Review Gate

**This is the historically skipped step. NEVER skip for >20 lines.**

Check the diff size:
```bash
git diff --stat HEAD
```

| Condition | Action |
|-----------|--------|
| >20 lines of non-docs code | **MANDATORY**: Run code review (see dispatch chain below). Fix Critical and Important issues. Re-run Step 1 after fixes. |
| <=20 lines or docs-only | Skip: "Code review: skipped (<=20 lines / docs-only)." |

**Code review dispatch chain** (use Task tool directly — do NOT invoke skills):
1. `superpowers:code-reviewer` — primary reviewer
2. If agent error → `octo:personas:code-reviewer` — fallback
3. If agent error → `octo:skills:octopus-code-review` — last resort

**Manifest context**: If `.claude/change-manifest.md` exists, include its Summary and Pattern Applied sections in the code review prompt so the reviewer understands the intent without re-exploring.

## Step 4: Second Opinion

Same >20 line threshold as Step 3.

Categorize changed files using this table to determine the review focus:

| Files changed | Review focus |
|---|---|
| `config.py`, `cli.py` args, token handling, `.env` | **Security**: token handling, credential exposure, injection |
| `migrator/api.py`, rate limit logic, retry logic | **Performance**: rate limiting, async patterns, retry storms |
| `migrator/` (non-API), `core/engine.py`, `state.py` | **Migration Logic**: state management, phase ordering, edge cases |
| `parser/`, `transforms.py` | **Parser**: DCE format handling, data integrity, edge cases |
| `gui.py`, `uploader/` | **General**: bugs, architecture, naming |

Use `mcp__second-opinion__get_mistral_opinion` with:
- **model**: `mistral-large-latest`
- **personality**: `honest`
- **temperature**: `0.3`
- Include the categorized diff and the matching review focus from the table above
- If `.claude/change-manifest.md` exists, prepend its Summary and Pattern Applied sections

**Edge case**: If Second Opinion MCP is unavailable (connection error, timeout), log "Second Opinion: skipped (MCP unavailable)" and continue — do not block shipping.

Fix **Critical** issues. Re-run Step 1 after fixes.

**Skip if:** <=20 lines changed OR docs-only changes.

## Step 5: Documentation

Update these files as applicable:

| File | When |
|------|------|
| `CHANGELOG.md` | **Always** (Keep a Changelog format) |
| `docs/` pages | If user-facing behavior changed |
| `README.md` | If feature table or download links need updating |
| `pyproject.toml` version | If version bump needed (see below) |

**Version bump logic:**
- **Patch**: bugfix, small tweak
- **Minor**: new feature, new migration phase
- **Major**: breaking change, architecture overhaul
- **No bump**: docs-only, CLAUDE.md/rules, CI config (use `content:` commit prefix)

## Step 6: Commit and Push

1. Stage specific files only — **NEVER** use `git add -A` or `git add .`
2. Write a clear commit message (imperative mood, explain the *why*)
3. Include Co-Authored-By trailer:
   ```
   Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
   ```
4. Push to remote (if on a branch with upstream)

## Step 7: Harvest (CogniLayer)

Save session knowledge to CogniLayer memory. Review the session and call `memory_write` for:
- Decisions, patterns, gotchas, error fixes discovered during this work
- Architectural facts about files created/modified (what they do, how they relate)
- Procedures or commands that were non-obvious

Skip facts already saved proactively during the session (check via `memory_search`).
Then call `session_bridge(action="save")` with progress summary.

Report: "Harvest: saved N new facts, bridge updated" or "Harvest: no new facts (all captured proactively)"

If CogniLayer MCP is unavailable, log "Harvest: skipped (MCP unavailable)" and continue.

## Step 8: Report

Display:
- Commit hash
- Version (if bumped)
- Verification results (all green)
- Files changed count
- Brief summary of what shipped

## NEVERs

- **Never** skip code review for >20 lines of non-docs code
- **Never** skip Second Opinion for >20 lines of non-docs code
- **Never** use `git add -A` or `git add .`
- **Never** skip CHANGELOG update
- **Never** commit without passing Step 1 verification
- **Never** push without Co-Authored-By trailer
- **Never** bump version without checking previous version first
- **Never** amend a previous commit — always create a new one
- **Never** skip the Harvest step — session knowledge may be lost
- **Never** write releaseNotes for internal-only changes (N/A for this project, but keep discipline)

## Edge Cases

| Situation | Action |
|-----------|--------|
| Only docs changed (no code) | Still run verify — stale build state is possible |
| Git status is clean | Nothing to ship — report "no changes to commit" |
| Multiple logical changes | Split into separate commits by staging specific files per commit |
| Code review finds issues | Fix issues, re-run Step 1, then continue from Step 5 |
| Second Opinion MCP unavailable | Log skip and continue — don't block shipping |
| Second Opinion finds critical issues | Fix them, re-run Step 1, then continue from Step 5 |
| Change manifest exists | Use for audit (Step 2), include in review context (Steps 3-4), then delete after successful ship |
