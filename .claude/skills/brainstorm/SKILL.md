---
name: brainstorm
description: "Explore technical approaches for a feature after spec is complete. Produces a design document. Use after /spec, before /critique. This is the project-local brainstorming skill — use this instead of superpowers:brainstorming."
user_invocable: true
allowed-tools: Read, Grep, Glob, Write, AskUserQuestion
---

# Brainstorming — Design from Spec

Turn a spec's requirements into a concrete technical design through collaborative dialogue. Explore approaches, present trade-offs, and produce a design document.

**Output is a design document, not code.** The design captures *how* to build what the spec requires. Implementation happens after critique passes.

<HARD-GATE>
Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it. This applies regardless of perceived simplicity.
</HARD-GATE>

## When to Use

- After `/spec` produces a spec document in `docs/plans/specs/`
- Before `/critique` reviews the design
- When a task needs technical approach exploration (2-3 alternatives)
- Medium and Large tasks (per CLAUDE.md classification)

## When NOT to Use

- Trivial tasks (<5 lines) — just do it
- Bug fixes — use `superpowers:systematic-debugging`
- Requirements not yet specced — run `/spec` first

## Process

### Phase 0: Prerequisite Check (MANDATORY)

Before doing anything else, verify a spec exists:

1. Glob `docs/plans/specs/*.md` for files
2. If no spec files exist: **STOP. Tell the user: "No spec found in `docs/plans/specs/`. Run `/spec` first."**
3. If spec files exist, read the most recent one (or the one the user specifies)

Do NOT proceed without a spec. Do NOT brainstorm from a brief alone — the brief must go through `/spec` first.

### Phase 1: Absorb the Spec

Read the spec document completely. Extract:
- P0 requirements (these MUST be addressed by the design)
- P1 requirements (address if the approach naturally supports them)
- Success metrics (the design should make these achievable)
- Non-goals (the design must NOT include these)
- Pre-mortem Tigers (the design should mitigate these)

Also read the linked brief for full context.

### Phase 2: Explore Project Context

Check the codebase for:
- **Migration phase patterns** — How are existing phases structured in `migrator/`? What's the standard function signature, error handling, and event emission pattern?
- **Engine/shell separation** — `engine.py` NEVER imports from GUI or CLI. All progress uses the event emitter in `core/events.py`.
- **Data models** — What dataclasses exist in `parser/models.py`, `config.py`, `state.py`?
- **Stoat API constraints** — Rate limits (5/10s for structure, 10/10s for messages), British spelling, two-step categories, nonce deduplication
- **Existing transforms** — What does `transforms.py` already handle?
- **Test patterns** — How are similar features tested? What fixtures exist?

Report findings: "I found X, Y, Z that are relevant to the design."

### Phase 3: Ask Clarifying Questions (one at a time)

If the spec + codebase scan leave any technical ambiguity, ask questions one at a time. Focus on:
- Phase boundaries — where does new code live in the migration pipeline?
- Data flow — which existing models feed this? What new fields are needed?
- Shell impact — does this need GUI changes, CLI changes, or both?

Prefer AskUserQuestion with multiple-choice options when possible. Only ask questions the spec didn't already answer.

### Phase 4: Propose 2-3 Approaches

Present approaches with trade-offs:

```
## Approach A: [Name] (Recommended)
[2-3 sentences on how it works]
- Pros: ...
- Cons: ...
- Reuses: [existing modules/patterns]

## Approach B: [Name]
[2-3 sentences]
- Pros: ...
- Cons: ...

## Approach C: [Name] (if meaningfully different)
[2-3 sentences]
- Pros: ...
- Cons: ...
```

Lead with your recommendation and explain why. For Medium tasks, 1 alternative is sufficient. For Large tasks, propose 2 alternatives minimum.

### Phase 5: Present Design (section by section)

Once the user approves an approach, present the design in sections. Ask for approval after each section before moving to the next:

1. **Architecture** — Where in the migration pipeline, data flow, engine event hooks
2. **Data Models** — New dataclass fields in models.py, state.py, config.py
3. **API Integration** — Stoat API calls, rate limit handling, Autumn uploads, error recovery
4. **Error Handling** — Custom exceptions, state error logging, resume/checkpoint behaviour
5. **Files** — Specific files to create/modify/test (matching the design doc template)

Scale each section to its complexity — a few sentences if straightforward, up to 200-300 words if nuanced.

### Phase 6: Write Design Document

After all sections are approved, write the design to `docs/plans/designs/YYYY-MM-DD-<kebab-name>.md`:

```markdown
# Design: [Feature Name]

## Problem & Context
[From the brief/spec — why are we doing this?]

## Scope
- **In scope**: [From spec P0 + P1]
- **Out of scope**: [From spec Non-Goals]

## Technical Approach
[Chosen approach — architecture, data flow, error handling]

### Alternatives Considered
1. **[Name]**: [What it is]. Rejected because: [Why].

## Files
- Create: `path/to/new.py`
- Modify: `path/to/existing.py`
- Test: `tests/test_something.py`

## Acceptance Criteria
[Carried forward from spec P0 stories]

## Tasks
1. Step one (specific files to create/modify)
2. Step two (specific files to create/modify)
```

### Phase 7: Handoff

After saving the design document:

<WORKFLOW-GATE>
COMPLETED: /brainstorm
NEXT MANDATORY STEP: /critique

You MUST invoke /critique now. Do NOT:
- Invoke writing-plans
- Implement any code
- Skip to building
- Take any action other than invoking /critique

The Superpowers brainstorming skill says "terminal state is writing-plans".
That is WRONG for this project. /critique MUST run before writing-plans.

If the user says "go ahead", "do that", "OK", or similar — they mean "invoke /critique",
NOT "start implementing" or "write the plan". The workflow chain is:
/brief -> /spec -> /brainstorm -> /critique -> [/test-scenarios] -> writing-plans -> build -> /ship
</WORKFLOW-GATE>

## NEVER

- **Never** skip the prerequisite check — a spec must exist before brainstorming
- **Never** produce code in the design — the design captures approach and architecture, not implementation
- **Never** skip the approach alternatives — always propose at least 2 options for Medium, 3 for Large
- **Never** include non-goals in the design — respect the spec's boundaries
- **Never** assume Stoat API capabilities — verify via Context7 or stoat-api.md rule
- **Never** save the design without user seeing it — present each section and get approval
- **Never** invoke writing-plans after this skill — the next step is /critique, always
- **Never** invoke `superpowers:brainstorming` — this IS the brainstorming skill for this project
- **Never** skip the WORKFLOW GATE — after this skill completes, the next step is /critique, period
