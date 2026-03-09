---
globs: []
---

# Workflow Gates

This rule is not auto-triggered. It is referenced by the `/ship` skill and design gate skills.

## Pipeline

```
/brief -> /spec -> /brainstorm -> /critique -> [/test-scenarios] -> writing-plans -> build -> /ship
```

## Verification Command

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest
```

## Code Review Gate

Mandatory for changes >20 lines of non-docs code. Dispatch chain:
1. `superpowers:code-reviewer` — primary reviewer
2. Fallback: `octo:personas:code-reviewer`
3. Fallback: `octo:skills:octopus-code-review`

Skip only for: <=20 lines OR docs-only changes.

## Commit Discipline

- Stage specific files only (NEVER `git add -A` or `git add .`)
- Commit message with Co-Authored-By trailer
- Run verification command before every commit
- One logical change per commit

## Version Bump Logic

| Bump | When |
|------|------|
| Major | Breaking change, architecture overhaul |
| Minor | New feature, new migration phase |
| Patch | Bugfix, small tweak |
| No bump | Docs-only, CLAUDE.md/rules, CI config (use `content:` commit prefix) |
