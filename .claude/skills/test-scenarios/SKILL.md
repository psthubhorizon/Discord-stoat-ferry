---
name: test-scenarios
description: "Generate structured test scenarios from spec acceptance criteria. Optional for Medium tasks, recommended for Large. Use after /critique passes, before writing-plans."
user_invocable: true
allowed-tools: Read, Grep, Glob, Write, AskUserQuestion
---

# Test Scenarios — Acceptance Criteria to Test Cases

Generate structured test scenarios from a spec's acceptance criteria. Ensures that every P0 requirement has clear, implementable test coverage before writing the implementation plan.

## When to Use

- After `/critique` passes a design document
- Recommended for Large tasks (5+ files, architecture changes)
- Optional for Medium tasks (skip if acceptance criteria are already highly specific)

## When NOT to Use

- Trivial tasks — no spec means no test scenarios
- Requirements not yet specced — run `/spec` first
- Design not yet critiqued — run `/critique` first

## Process

### Phase 0: Prerequisite Check (MANDATORY)

1. Glob `docs/plans/specs/*.md` for spec files
2. If no spec exists: **STOP. Tell the user: "No spec found. Run `/spec` first."**
3. Read the spec and extract all acceptance criteria from P0 and P1 stories

### Step 1: Read Related Test Files

Search `tests/` for existing test patterns related to this feature:
- Test naming convention: `tests/test_{module}.py`
- Fixture patterns in `tests/fixtures/`
- Async test setup with `pytest-asyncio`
- HTTP mocking with `aioresponses`

### Step 2: Generate Test Scenarios

For each P0 acceptance criterion, generate a test scenario:

```markdown
### SC-{id}: {descriptive name}
**Requirement**: S{n} — {acceptance criterion text}
**Type**: Happy path / Edge case / Error state / Resume
**Setup**: {What fixtures or mocks are needed}
**Action**: {What the test does}
**Expected**: {Observable outcome}
**Test file**: `tests/test_{module}.py`
```

### Step 3: Add Domain-Specific Edge Cases

For Discord Ferry, always consider these edge case categories:

| Category | Examples |
|----------|---------|
| Empty data | No messages in export, no channels, no members |
| Malformed input | Missing DCE fields, unexpected types, DCE version differences |
| Network failures | Connection drop during upload, Autumn timeout, sustained 429s |
| Resume/checkpoint | Migration resumes from crash, nonce deduplication works |
| Server limits | Channel 201, emoji 101, message >2,000 chars |
| Format edge cases | Forwarded messages (DCE bug #1322), system messages with empty content |
| Cross-shell | Scenario works in both GUI and CLI |

### Step 4: Produce Scenario Document

Write scenarios to the spec file as an appendix, or to a companion file:

```markdown
## Test Scenarios

### Happy Path
- SC-1: ...
- SC-2: ...

### Edge Cases
- SC-3: ...

### Error States
- SC-4: ...

### Resume
- SC-5: ...
```

### Step 5: Handoff

<WORKFLOW-GATE>
COMPLETED: /test-scenarios
NEXT MANDATORY STEP: writing-plans (superpowers:writing-plans)

You MUST invoke superpowers:writing-plans now with the design document as input. Do NOT:
- Implement any code
- Skip to building
- Take any action other than creating the implementation plan

If the user says "go ahead" — they mean "invoke writing-plans".
The workflow chain is:
/brief -> /spec -> /brainstorm -> /critique -> [/test-scenarios] -> writing-plans -> build -> /ship
</WORKFLOW-GATE>

## NEVER

- **Never** skip the prerequisite check — a spec must exist
- **Never** generate scenarios without reading existing test patterns first
- **Never** skip the domain-specific edge cases — they catch the bugs that matter most
- **Never** skip the WORKFLOW GATE — after this skill, the next step is writing-plans
