---
name: critique
description: "REQUIRED for medium+ tasks: stress-test a design document before writing an implementation plan. Must run between /brainstorm and writing-plans. Skipping this is a workflow violation."
user_invocable: true
allowed-tools: Read, Grep, Glob
---

# /critique — 7-Dimension Design Review

Reviews a design document and produces a structured critique. Use after `/brainstorm` produces a design doc, before `writing-plans`.

**The agent that designs cannot validate the design.** This skill creates a fresh-context review.

## Phase 0: Prerequisite Check (MANDATORY)

Before doing anything else, verify a design doc exists:

1. Glob `docs/plans/designs/*.md` for files
2. If no design files exist: **STOP. Tell the user: "No design doc found in `docs/plans/designs/`. Run `/brainstorm` first to produce a design document."**
3. If design files exist but the user didn't specify which one, list them and ask

Do NOT proceed without a design document. Do NOT critique from memory or from a spec alone.

## Input

The user provides a path to a design document (e.g., `docs/plans/designs/my-feature.md`). Read it fully before proceeding.

If no path is given, check `docs/plans/designs/` for the most recently modified file and confirm with the user.

## Step 1: Read the Design

Read the design document completely. Note:
- The stated problem and context
- Scope (in/out)
- Technical approach
- Files to create/modify
- Acceptance criteria
- Number of tasks

## Step 2: Read Referenced Code

For every file listed in the "Files" section:
- If it exists: read it to understand current state
- If it's new: read similar existing files to understand expected patterns
- Read any components or hooks the design says to reuse

## Step 3: Critique Against Seven Dimensions

Evaluate the design against each dimension. Note findings only if there are actual issues. Don't force findings where none exist.

### 1. Feasibility

Can this actually be built within Stoat's constraints?

Check against:
- **Rate limits**: `/servers` bucket = 5/10s (shared for channels, roles, emoji), messages = 10/10s. Will the design exceed these?
- **Autumn upload limits**: attachments 20MB, avatars 4MB, icons 2.5MB, banners 6MB, emojis 500KB
- **Server limits**: 200 channels, 200 roles, 100 emoji per server
- **Message limits**: 2,000 chars, 5 attachments, 5 embeds, 20 reactions per message
- **No ADMINISTRATOR permission**: Does the design assume a blanket admin permission?
- **Two-step categories**: Does the design correctly account for create-then-patch?

### 2. Pattern Alignment

Does the design follow established project conventions?

Check against:
- `python-conventions.md`: async-first, dataclasses, pathlib, type hints, ruff/mypy
- `stoat-api.md`: British spelling, nonce deduplication, masquerade rules
- **Engine/shell separation**: Does engine.py remain independent of GUI/CLI? Event emitter pattern?
- **Existing phase patterns**: Does a new phase follow the same structure as existing ones in `migrator/`?
- **Error handling**: Custom exceptions in `errors.py`, errors logged to `MigrationState.errors`

### 3. Over-Engineering

Is the design doing more than necessary?

Watch for:
- Abstractions for single-use cases
- Configurability nobody asked for
- "Future-proofing" for hypothetical requirements
- Complex retry/fallback logic where simple would suffice
- New dependencies when stdlib/existing deps cover it

**YAGNI is the default.** The burden of proof is on complexity, not simplicity.

### 4. Missing Edge Cases

What could go wrong that the design doesn't address?

Common Discord Ferry edge cases:
- **Empty exports**: No messages, no channels, no members in DCE JSON
- **Malformed DCE JSON**: Missing fields, unexpected types, DCE version differences
- **Network failures mid-migration**: Connection drops during message upload, Autumn timeout
- **Resume-after-crash**: Can the migration resume cleanly from `MigrationState`? Are nonces correct?
- **Forwarded messages**: Empty content + empty attachments (DCE bug #1322)
- **System messages**: Empty `content` but non-empty `type`
- **Exceeding server limits**: What happens at channel 201 or emoji 101?
- **Rate limit exhaustion**: Sustained 429s, not just occasional ones

### 5. Type Safety

Will this pass mypy strict?

Check for:
- Dataclass field types — are they precise or overly broad (`Any`, `dict`)?
- Union types using `X | Y` syntax (not `Optional[X]` or `Union[X, Y]`)
- Return types on all public functions
- `pathlib.Path` for file paths (not `str`)
- Generic types using lowercase (`dict[str, str]` not `Dict[str, str]`)

### 6. Scope Creep

Does the design stay within what was requested?

- Compare against the spec (if one exists in `docs/plans/specs/`)
- Flag any requirements that appeared in the design but weren't in the spec
- Flag any "while we're at it" additions
- Is there a simpler version that solves the core problem?

### 7. Better Alternatives

Is there a fundamentally better approach?

- Could an existing pattern be extended instead of creating something new?
- Is there a library that already does this?
- Could the problem be solved at a different layer (parser vs transform vs migrator)?
- Would a different data model make the code simpler?

## Output Format

```markdown
# Critique: <Design Document Name>

## Summary
[1-2 sentence overall assessment — is this design sound?]

## Findings

### Critical (must fix before planning)
- **[Finding]**: [Explanation].
  **Suggestion**: [Specific fix or alternative]

### Important (should fix)
- **[Finding]**: [Explanation].
  **Suggestion**: [Fix]

### Minor (consider)
- **[Finding]**: [Explanation].
  **Suggestion**: [Fix]

## Strengths
- [What the design does well — be specific]

## Verdict
**[PASS / ITERATE / RETHINK]**
```

## Verdict Rules

- **PASS**: 0 BLOCKs/Critical, <=2 Important. Proceed to implementation planning.
- **ITERATE**: 0 Critical, 3+ Important, or 1 Critical that's easy to fix. Revise the design and re-critique.
- **RETHINK**: 2+ Critical, or 1 Critical that requires fundamental redesign. Go back to brainstorming.

## Handoff

Based on verdict:

- **ITERATE**: "Design needs changes. Address the findings above, update the design doc, then re-run `/critique`."
- **RETHINK**: "Fundamental issues. Go back to `/brainstorm` with these critique findings as input."

<WORKFLOW-GATE>
On PASS verdict only:

COMPLETED: /critique (PASS)
NEXT MANDATORY STEP: /test-scenarios (optional, recommended for Large) OR writing-plans

If the task is Large: recommend invoking /test-scenarios first, then writing-plans.
If the task is Medium: invoke writing-plans directly (superpowers:writing-plans).

You MUST invoke the next step now. Do NOT:
- Implement any code
- Skip to building
- Take any action other than invoking the next workflow step

If the user says "go ahead", "do that", "OK", or similar — they mean "invoke the next step",
NOT "start implementing". The workflow chain is:
/brief -> /spec -> /brainstorm -> /critique -> [/test-scenarios] -> writing-plans -> build -> /ship
</WORKFLOW-GATE>

## NEVERs

- **Never** skip the prerequisite check — a design doc must exist before critiquing
- **Never** critique without reading the full design document and referenced code first
- **Never** rubber-stamp — if everything is genuinely PASS, say so, but earn it with specific observations
- **Never** force findings — if a dimension has no issues, skip it. Fabricated findings waste time.
- **Never** propose implementation details — this is design review, not implementation planning
- **Never** expand scope — critique what's written, don't add requirements
- **Never** modify the design doc — this skill is read-only. The user decides what to change.
- **Never** skip the Scope Creep check — the most common source of wasted work
- **Never** skip the WORKFLOW GATE — after PASS, the next step is /test-scenarios or writing-plans
