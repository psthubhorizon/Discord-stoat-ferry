---
name: spec
description: "Transform a brief into structured, prioritised requirements with acceptance criteria. Use after /brief produces a brief document, before /brainstorm explores technical approaches."
user_invocable: true
allowed-tools: Read, Grep, Glob, Write, AskUserQuestion
---

# Spec — Structured Requirements from Brief

Transform a brief document into prioritised user stories with acceptance criteria, success metrics, and risk analysis. This skill produces the *requirements layer* — what must be true when we're done, before brainstorming explores how to build it.

**Output is requirements, not design.** The spec captures *what must be delivered and verified*. Technical approach (the *how*) happens in brainstorming.

## When to Use

- After `/brief` produces a brief document in `docs/plans/briefs/`
- Before invoking `/brainstorm` to explore technical approaches
- When a task needs structured acceptance criteria and priority tiers
- Medium and Large tasks (per CLAUDE.md classification)

## When NOT to Use

- Trivial tasks (<5 lines, config, doc-only) — just do it
- Requirements are already crystal clear with testable acceptance criteria
- Bug fixes — use `superpowers:systematic-debugging` instead

## Invocation

```
/spec docs/plans/briefs/2026-03-01-feature-name.md
```

If no path is provided, scan `docs/plans/briefs/` for the most recently modified file and confirm: **"I found `docs/plans/briefs/<name>.md`. Is this the brief to spec?"**

## Process

### Phase 0: Prerequisite Check (MANDATORY)

Before doing anything else, verify a brief exists:

1. Glob `docs/plans/briefs/*.md` for files
2. If no brief files exist: **STOP. Tell the user: "No brief found in `docs/plans/briefs/`. Run `/brief` first."**
3. If brief files exist but none match the current task, ask the user to confirm which brief to use

Do NOT proceed without a brief. Do NOT create a spec from scratch without a brief document.

### Phase 1: Read and Absorb the Brief

Read the brief document completely. Extract:
- **What**: The feature being built
- **Why**: The problem it solves
- **Scope**: Tier classification (Medium/Large)
- **Non-Goals**: What's explicitly out of scope
- **Technical Context**: Migration phases touched, Stoat API calls, DCE format details
- **Constraints**: Rate limits, server limits, existing patterns to follow
- **Open Questions**: Anything flagged for investigation

If critical information is missing from the brief, stop and tell the user: **"This brief is missing [X]. Run `/brief` to fill the gap, or tell me the answer now."**

### Phase 2: Codebase Verification (automated)

Before writing requirements, verify what already exists:

1. **Existing capabilities** — Grep for modules, functions, or patterns that already deliver part of what the brief describes
2. **Migration phase patterns** — Check if the required phase exists in `migrator/`, or if a new one is needed
3. **Parser models** — Check if required DCE format fields are already modelled in `parser/models.py`
4. **Stoat API coverage** — Check if required API calls exist in `migrator/api.py`
5. **State management** — Check if `state.py` already has fields for resume support of this feature
6. **Test fixtures** — Check if sample DCE JSON exists in `tests/fixtures/` for this scenario

Report findings briefly: "I verified: [X exists, Y doesn't, Z needs extension]."

### Phase 3: Extract Requirements

For each distinct capability described in the brief, write a requirement using **WWA format** (Why-What-Acceptance):

- **Why**: Strategic context — 1-2 sentences on why this matters. Connects to the brief's "Problem & Context".
- **What**: What to deliver — specific, observable outcome. Reference existing components/patterns where relevant.
- **Acceptance Criteria**: Numbered list of testable, observable conditions. Each criterion must be verifiable without subjective judgment.

**Writing good acceptance criteria:**
- Start with a verb: "Migrates...", "Parses...", "Emits event when...", "Shows error when..."
- Be specific: "Uploads avatar via Autumn with 0.5s delay" not "Handles avatars"
- Include boundaries: "Supports messages up to 2,000 chars" not "Supports messages"
- Cover error states: "Logs warning and skips when attachment exceeds 20MB"
- Cover resume: "Resumes from last checkpoint using nonce-based deduplication"
- Reference existing patterns: "Follows masquerade pattern from messages.py"

### Phase 4: Prioritise

Assign each requirement a priority tier:

| Tier | Meaning | Constraint |
|------|---------|------------|
| **P0 — Must Have** | Required for this change to ship. Without these, the feature is broken or useless. | **Maximum 5 stories.** If you have more, you're not prioritising — split into phases. |
| **P1 — Should Have** | Important but the feature works without them. Fast-follow items. | No limit, but be honest — most "P1s" are actually P2s. |
| **P2 — Nice to Have** | Enhancements, polish, edge cases that can wait. Backlog candidates. | No limit. |

**IVT check** — Every story must be:
- **Independent**: Can be implemented and tested without other stories
- **Valuable**: Delivers observable value to the user or system
- **Testable**: Acceptance criteria can be verified in a test or manual check

If a story fails IVT, split or rewrite it.

### Phase 5: Success Metrics

Define 2-4 measurable outcomes that indicate the feature worked:
- Functional: "Users can [do X] in [context Y]"
- Quality: "[Error rate / message loss / upload failures] meets [threshold]"
- Completeness: "[Migration phase] handles [N]% of exported data"

These are NOT acceptance criteria (those are per-story). These are feature-level "was this worth building?" signals.

### Phase 6: Pre-Mortem (Large tasks only)

For tasks classified as **Large** in the brief (5+ files, architecture changes, cross-cutting):

**Tigers** — Real risks that could derail the implementation:
- Technical: Stoat API rate limits (5/10s for structure), Autumn upload limits, server limits (200 channels, 100 emoji)
- Scope: Requirements that sound simple but hide DCE format complexity
- Integration: Changes that affect both GUI and CLI shells, or engine/shell separation
- For each: state the risk and a concrete mitigation

**Paper Tigers** — Concerns that feel scary but aren't real risks:
- For each: name the concern and explain why it's manageable

**Elephants** — Unspoken worries nobody has raised yet:
- For each: name the worry and what investigation is needed

Skip this phase entirely for Medium tasks.

### Phase 7: Produce Spec Document

Show the user the complete spec before saving. Write to `docs/plans/specs/YYYY-MM-DD-<kebab-name>.md`:

```markdown
# Spec: [Feature Name]
**Brief**: `docs/plans/briefs/YYYY-MM-DD-<name>.md`
**Date**: YYYY-MM-DD | **Size**: Medium/Large

## Success Metrics
- [Measurable outcome 1]
- [Measurable outcome 2]

## Requirements

### P0 — Must Have
| ID | Title | Why | What | Acceptance Criteria |
|----|-------|-----|------|---------------------|
| S1 | [Title] | [Strategic context] | [Deliverable + pattern ref] | 1. ... 2. ... 3. ... |

### P1 — Should Have
| ID | Title | Why | What | Acceptance Criteria |
|----|-------|-----|------|---------------------|
| S3 | ... | ... | ... | ... |

### P2 — Nice to Have
| ID | Title | Why | What | Acceptance Criteria |
|----|-------|-----|------|---------------------|
| S4 | ... | ... | ... | ... |

## Pre-Mortem (Large tasks only)

### Tigers (Real Risks)
- **[Risk]**: [Mitigation]

### Paper Tigers (Overblown Concerns)
- **[Concern]**: [Why it's manageable]

### Elephants (Unspoken Worries)
- **[Worry]**: [Investigation needed]

## Non-Goals
- [Carried forward from brief]
```

### Phase 8: Handoff

After saving the spec, report the summary, then enforce the workflow gate.

If the brief had a **Large** classification, remind: "Pre-mortem included — review Tigers before brainstorming commits to an approach."

<WORKFLOW-GATE>
COMPLETED: /spec
NEXT MANDATORY STEP: /brainstorm

You MUST invoke /brainstorm now. Do NOT:
- Implement any code
- Skip to writing-plans
- Start designing without the brainstorming skill
- Invoke superpowers:brainstorming (use the project-local /brainstorm instead)
- Take any action other than invoking /brainstorm

If the user says "go ahead", "do that", "OK", or similar — they mean "invoke /brainstorm",
NOT "start implementing". The workflow chain is:
/brief -> /spec -> /brainstorm -> /critique -> [/test-scenarios] -> writing-plans -> build -> /ship
</WORKFLOW-GATE>

## NEVER

- **Never** design solutions in the spec — requirements say *what* must be true, not *how* to build it
- **Never** skip the prerequisite check — a brief must exist before speccing
- **Never** skip codebase verification — existing capabilities change what requirements are needed
- **Never** exceed 5 P0 stories — if you need more, the scope is too large. Split into phases.
- **Never** write untestable acceptance criteria — "Works well", "Is fast" are not testable. Be specific.
- **Never** assume Stoat API capabilities — verify via Context7 or stoat-api.md rule
- **Never** save the spec without showing the user first — present the complete spec for review
- **Never** skip the IVT check — every story must be Independent, Valuable, and Testable
- **Never** run pre-mortem for Medium tasks — overhead without proportional value
- **Never** skip the WORKFLOW GATE — after this skill completes, the next step is /brainstorm, period
