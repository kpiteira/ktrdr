# Implementation Plan Command

## Purpose

Generate a vertical implementation plan from validated design and architecture documents. Each milestone delivers an E2E-testable capability, ensuring design problems surface early.

**When to use:** After design validation is complete (via `/kdesign-validate`), when you're ready to break the work into implementable tasks.

**What it produces:**
- Vertical milestones (each E2E-testable)
- Detailed tasks with specific files and changes
- E2E test scenarios for each milestone
- Acceptance criteria per task

---

## This is a Conversation, Not a Generator

The command produces a draft plan. The value comes from refining it together.

Claude will propose milestones based on the design, but:

- **Claude may miss dependencies.** Karl knows what's flaky, what takes longer than expected, what has hidden complexity.
- **Claude may over-split or under-split.** Karl knows team capacity and what makes sense as a unit of work.
- **Milestone boundaries are judgment calls.** Claude proposes, Karl adjusts.

The command pauses for feedback at key points. This back-and-forth is how good plans emerge.

---

## Command Usage

```
/kdesign-impl-plan design: <design-doc.md> arch: <architecture-doc.md> [validation: <validation-output.md>]
```

**Required:**
- `design:` — The design/spec document
- `arch:` — The architecture document

**Optional:**
- `validation:` — Output from `/kdesign-validate` (contains scenarios, decisions, milestone structure)
- Additional reference docs

If validation output is provided, Claude uses the scenarios and milestone structure from validation as the starting point.

---

## Plan Generation Process

### Step 0: Architecture Alignment Check

Before planning tasks, Claude must understand and commit to the architecture's core decisions. This prevents implementation drift.

Claude reads the architecture document and extracts:

```markdown
## Architecture Alignment

### Core Patterns (from ARCHITECTURE.md)

| Pattern | Description | Implementation Approach |
|---------|-------------|------------------------|
| [e.g., State Machine] | [What the arch doc says] | [How we'll implement it] |
| [e.g., Event-Driven] | [What the arch doc says] | [How we'll implement it] |
| [e.g., Worker Model] | [What the arch doc says] | [How we'll implement it] |

### Key Architectural Decisions

1. **[Decision 1]**: [What the arch says]
   - Implementation: [How tasks will reflect this]

2. **[Decision 2]**: [What the arch says]
   - Implementation: [How tasks will reflect this]

### What We Will NOT Do

Based on the architecture, these approaches are explicitly ruled out:
- [Anti-pattern 1 that would violate the architecture]
- [Anti-pattern 2 that would violate the architecture]
```

---

**Pause: Architecture Alignment**

Claude asks:

> "I've extracted these core patterns and decisions from the architecture:
>
> **Patterns:** [list]
> **Key Decisions:** [list]
> **Ruled Out:** [list]
>
> Before I proceed:
> 1. **Did I understand the architecture correctly?**
> 2. **Are there patterns I missed?**
> 3. **Anything in 'ruled out' that's actually acceptable?"

This alignment check is critical. If the architecture says "state machine with explicit transitions," the implementation plan cannot use a "continuous polling loop." Every task must be traceable to an architectural decision.

---

### Step 1: Extract Capabilities

Claude reads the design docs and lists what the user can DO when this feature is complete:

```markdown
## User Capabilities (when complete)

1. User can trigger an automated research cycle
2. User can see current status and progress  
3. User can cancel a running cycle
4. User can see results when complete
5. User can configure research parameters
```

---

**Pause: Capability Review**

Claude asks:

> "These are the capabilities I extracted from the design. Before I structure milestones:
>
> 1. **Is anything missing?** Capabilities you expect that I didn't list?
> 2. **What's the priority order?** Which capability is most important to prove first?
> 3. **Any dependencies I should know about?** Things that must exist before others can work?"

---

### Step 2: Define Milestone 1 (The Foundation)

Milestone 1 is special — it's the smallest thing that proves the architecture works end-to-end. It doesn't need to be useful, just testable.

Claude proposes M1:

```markdown
## Milestone 1: [Smallest E2E-testable slice]

**Capability:** User can [minimal action]
**Why this is M1:** [Why this proves the architecture]

**E2E Test Scenario:**
```bash
# [Concrete commands that prove it works]
```

**Layers Touched:**
- Model: [What's needed]
- Service: [What's needed]
- API: [What's needed]
- CLI: [What's needed, if any]
```

---

**Pause: M1 Review**

Claude asks:

> "This is my proposed Milestone 1. It touches [N] layers and should be completable in [estimate].
>
> 1. **Is this too big?** Should I find a smaller first proof?
> 2. **Is this too small?** Is there a natural grouping that makes more sense?
> 3. **Is the E2E test realistic?** Can we actually run this against the system?"

---

### Step 3: Build Remaining Milestones

For each subsequent milestone, Claude proposes:

```markdown
## Milestone N: [User can X]

**Builds on:** Milestone N-1
**Capability Added:** [What's new]

**E2E Test Scenario:**
```bash
# [Commands that prove this works]
# [Should also verify previous milestones still work]
```

**Layers Touched:**
- [Only what changes from previous milestone]
```

Claude continues until all capabilities are covered, then presents the full milestone structure.

---

**Pause: Milestone Structure Review**

Claude asks:

> "Here's the full milestone structure:
>
> - M1: [capability] (~X tasks)
> - M2: [capability] (~Y tasks)  
> - M3: [capability] (~Z tasks)
> ...
>
> 1. **Does the order make sense?** Any milestones that should be reordered?
> 2. **Are the boundaries right?** Any milestones that should be split or merged?
> 3. **Anything missing?** Capabilities we discussed that aren't covered?"

---

### Step 4: Expand Tasks

For each approved milestone, Claude generates detailed tasks. Each task must trace back to the architecture.

```markdown
# Milestone N: [User can X]

**Branch:** `feature/[branch-name]`
**Builds on:** Milestone N-1
**E2E Test:** [Scenario from above]

---

## Task N.1: [Specific action]

**File:** `path/to/file.py`
**Action:** Create | Modify | Delete
**Architectural Pattern:** [Which pattern from Step 0 this implements]

**What to do:**
[Specific description of the change]

**Code sketch:** (if helpful)
```python
# Key parts of what this looks like
# NOTE: Must align with [architectural pattern]
```

**Tests:**
- Unit: `tests/unit/path/test_file.py`
- What to test: [Specific behaviors]

**Acceptance Criteria:**
- [ ] [Specific, verifiable criterion]
- [ ] [Specific, verifiable criterion]
- [ ] Implements [pattern] as specified in architecture

---

## Task N.2: [Next task]
...

---

## Milestone N Verification

### E2E Test Scenario

**Purpose:** [What this test proves]
**Duration:** ~[N] seconds
**Prerequisites:** [What must be running/available]

**Test Steps:**

```bash
# 1. Setup (if needed)
[commands]

# 2. Trigger the feature
[commands with expected output comments]

# 3. Verify the result
[commands to check state/logs/response]

# 4. Cleanup (if needed)
[commands]
```

**Success Criteria:**
- [ ] [Observable outcome 1]
- [ ] [Observable outcome 2]
- [ ] No errors in logs: `docker compose logs backend --since 5m | grep -i error`

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
```

---

### Step 5: Review and Refine

After generating all tasks, Claude presents summary:

```markdown
## Implementation Plan Summary

**Total Milestones:** N
**Total Tasks:** M
**Estimated Effort:** [rough estimate]

### Milestone Overview

| Milestone | Capability | Tasks | Key Risk |
|-----------|------------|-------|----------|
| M1 | [capability] | X | [risk] |
| M2 | [capability] | Y | [risk] |
| ... | ... | ... | ... |

### Architecture Consistency Check

| Pattern (from Step 0) | Implemented In | Verified |
|-----------------------|----------------|----------|
| [Pattern 1] | Tasks X.Y, X.Z | ✅ |
| [Pattern 2] | Tasks A.B | ✅ |

### Dependencies

[Any cross-milestone dependencies or external dependencies]

### Open Questions

[Questions that came up during planning]
```

---

**Pause: Final Review**

Claude asks:

> "The plan is ready for review. Before we finalize:
>
> 1. **Architecture alignment:** Does the implementation approach match the architecture?
>    - Patterns identified: [list]
>    - All patterns have implementing tasks: [yes/no]
> 2. **Task granularity:** Are tasks the right size? (Target: 1-4 hours each)
> 3. **Missing tasks:** Anything I forgot? (Tests, migrations, documentation)
> 4. **Risk areas:** Which milestones feel risky? Should we add spike tasks?"

---

### Step 6: Consistency Self-Check

Before saving the plan, Claude performs a final consistency check:

```markdown
## Consistency Verification

### Design → Plan Traceability

For each major design decision, verify it appears in the plan:

| Design Decision | Plan Reference | Status |
|-----------------|----------------|--------|
| [From DESIGN.md] | Task X.Y | ✅ |
| [From DESIGN.md] | Task A.B | ✅ |

### Architecture → Plan Traceability

For each architectural pattern, verify implementation matches:

| Architecture Says | Plan Implements | Match? |
|-------------------|-----------------|--------|
| "State machine with explicit transitions" | Task 1.3: Create state machine | ✅ |
| "Events trigger transitions" | Task 1.4: Event handlers | ✅ |

### Anti-Pattern Check

Verify the plan does NOT include approaches ruled out in Step 0:

- [ ] No [anti-pattern 1]
- [ ] No [anti-pattern 2]
```

If any row shows a mismatch, Claude must fix the plan before proceeding.

---

## Task Structure

Each task follows this structure for compatibility with `/ktask`:

```markdown
## Task [M.N]: [Title]

**File(s):** [Specific files to create/modify]
**Type:** CODING | RESEARCH | MIXED
**Estimated time:** [1-4 hours]

**Description:**
[What this task accomplishes — be specific about behavior, not just "implement X"]

**Implementation Notes:**
[Specific guidance, patterns to follow, gotchas to avoid]

**Testing Requirements:**

*Unit Tests:*
- [ ] [Specific test case 1]
- [ ] [Specific test case 2]
- [ ] Edge case: [description]
- [ ] Error case: [description]

*Integration Test (if applicable):*
- [ ] [How to verify this works with connected components]

**Acceptance Criteria:**
- [ ] [Functional criterion 1]
- [ ] [Functional criterion 2]
- [ ] Unit tests written and passing
- [ ] Code follows existing patterns in [reference file]

**Branch Strategy:** [If different from milestone branch]
```

---

## Task Quality Requirements

Every task must be **implementable by someone who only reads that task**. Check each task against:

### Specificity Checklist

| Requirement | Bad Example | Good Example |
|-------------|-------------|--------------|
| **Files named** | "Update the service" | "Modify `ktrdr/services/training.py`" |
| **Behavior described** | "Add validation" | "Validate symbol exists in cache before starting download" |
| **Tests specified** | "Add tests" | "Test: returns 404 if symbol not found" |
| **Patterns referenced** | "Follow existing patterns" | "Follow pattern in `OperationsService.create()`" |

### Testing Requirement by Task Type

| Task Type | Required Tests |
|-----------|----------------|
| New endpoint | Unit test for handler, integration test for request/response |
| New service method | Unit test with mocked dependencies, happy path + error cases |
| New model/schema | Unit test for validation, serialization |
| Bug fix | Regression test that fails before fix, passes after |
| Refactor | Existing tests still pass, no new tests needed |

### Red Flags in Tasks

- ❌ "Implement X" with no file specified
- ❌ "Add appropriate tests" with no specifics
- ❌ Acceptance criteria that can't be verified programmatically
- ❌ Task depends on decisions not yet made
- ❌ Task estimated at >4 hours (split it)

---

## Patterns for Common Features

### Pattern: Async Operation

```
M1: User can trigger operation (returns ID immediately)
    - Operation model (id, status, created_at)
    - Service.create() 
    - POST endpoint
    - E2E: trigger returns ID

M2: User can check status
    - Add progress fields
    - Service.get_status()
    - GET endpoint
    - E2E: status returns progress

M3: User can cancel
    - Add cancelled state
    - Service.cancel()
    - DELETE endpoint
    - Background task checks cancellation
    - E2E: cancel stops operation

M4: User sees results
    - Add result fields
    - Result storage
    - E2E: completed operation has results
```

### Pattern: State Machine

```
M1: Entity in initial state
    - Model with state field
    - Service.create()
    - E2E: create returns entity in initial state

M2: Happy path transition
    - State transition logic
    - Service.transition()
    - E2E: entity moves through states

M3: Validation
    - Invalid transition handling
    - E2E: invalid transitions rejected

M4: Failure states
    - Error state handling
    - Recovery logic
    - E2E: failures handled gracefully
```

### Pattern: External Integration

```
M1: Connection health
    - Client class
    - Health check method
    - E2E: health returns OK

M2: Fetch data
    - Fetch method
    - Response parsing
    - E2E: data retrieved correctly

M3: Error handling
    - Retry logic
    - Error mapping
    - E2E: errors handled gracefully

M4: Caching
    - Cache layer
    - Invalidation
    - E2E: cache works correctly
```

---

## Red Flags

Watch for these during planning:

### Structure Issues

| Red Flag | Problem | Fix |
|----------|---------|-----|
| M1 has 10+ tasks | Foundation too big | Find smaller first proof |
| No E2E test in milestone | Can't verify | Every milestone needs E2E |
| "Implement X" without file | Too vague | Specify exact files |
| Task depends on unwritten task | Order wrong | Reorder or merge |
| All model tasks, then all service tasks | Horizontal! | Restructure vertically |

### Architecture Drift (Critical!)

| Red Flag | Problem | Fix |
|----------|---------|-----|
| Architecture says "state machine" but plan uses "polling loop" | Implementation won't match design | Re-read architecture, fix task descriptions |
| Architecture says "event-driven" but plan uses "request/response" | Wrong pattern | Redesign task to use correct pattern |
| Code sketch doesn't match architectural diagram | Visual mismatch = real mismatch | Align code with architecture |
| Task introduces pattern not in architecture | Scope creep or drift | Either update architecture or remove from plan |
| "Similar to X" without checking X matches architecture | Copying wrong patterns | Verify X follows architecture before referencing |

### Common Architecture Drift Examples

**State Machine Drift:**
- Architecture: "Explicit state transitions triggered by events"
- Wrong: `while True: poll_status(); advance_if_ready()` 
- Right: `on_event(event): transition_to(next_state)`

**Worker Pattern Drift:**
- Architecture: "Workers are independent, communicate via messages"
- Wrong: `worker.run()` returns result directly to caller
- Right: `worker.run()` posts result to queue/event system

**Async Pattern Drift:**
- Architecture: "Non-blocking operations with callbacks"
- Wrong: `result = await blocking_operation(); process(result)`
- Right: `start_operation(); # later: on_complete(result)`

---

## Output Files

**One file per milestone.** This keeps context manageable — when implementing Milestone 3, you don't need Milestones 1-2 in context.

```
docs/implementation/[feature-name]/
  OVERVIEW.md           # Summary, dependency graph, milestone index
  M1_[name].md          # Milestone 1: tasks, E2E test, checklist
  M2_[name].md          # Milestone 2: tasks, E2E test, checklist
  M3_[name].md          # Milestone 3: ...
  ...
```

### OVERVIEW.md Contents

```markdown
# [Feature] Implementation Plan

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [name] | N | [brief description] | ⏳ |
| M2 | [name] | N | [brief description] | ⏳ |

## Dependency Graph

M1 → M2 → M3
       ↘ M4

## Reference Documents

- Design: [link]
- Architecture: [link]
- Validation: [link]
```

### Per-Milestone File Contents

Each `M[N]_[name].md` file contains:

1. **Frontmatter** — References to design/architecture docs (from command params)
2. **Milestone goal** — One sentence
3. **E2E test scenario** — Full test script/commands
4. **Tasks** — Detailed task specs
5. **Completion checklist** — All gates that must pass

**Frontmatter format:**

```markdown
---
design: <path from design: param>
architecture: <path from arch: param>
---

# Milestone 1: [Name]
...
```

The frontmatter embeds the same paths provided to this command, enabling `/ktask` to automatically discover context documents. This makes milestone files self-contained.

This structure means `/ktask` only loads the milestone file it needs.

---

## Integration with Other Commands

**Flow:**
1. `/kdesign-validate` → Validates design, produces scenarios and milestone structure
2. `/kdesign-impl-plan` → Expands milestones into detailed tasks (this command)
3. `/ktask` → Executes individual tasks with TDD

The validation output (scenarios, decisions, milestone structure) feeds directly into implementation planning. If validation was done, reference it to maintain consistency.
