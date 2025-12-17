# Design Validation Command

## Purpose

Validate a design by walking through concrete scenarios before implementation begins. This catches architectural gaps, state machine inconsistencies, and integration issues *before* code is written.

**When to use:** After design and architecture docs are "complete" but before writing the implementation plan.

**What it produces:**
- Validated scenarios with traced execution paths
- Identified gaps and open questions requiring resolution
- Interface contracts (signatures, data shapes, state transitions)
- Vertical milestone structure for implementation

---

## This is a Conversation, Not a Report

**The command produces scaffolding. The value comes from the conversation.**

Claude will systematically enumerate scenarios and trace through them, but:

- **Claude will miss scenarios.** The most insidious bugs come from scenarios Claude doesn't think of — infrastructure failures, race conditions, recovery flows. Karl adds these.
- **Claude will miss context.** Karl knows what failed before, what's flaky in the codebase, what "feels wrong." This context is essential.
- **Gaps require decisions.** Claude identifies options and trade-offs. Karl decides.

The command pauses for conversation at each step. Claude asks questions, proposes scenarios, and waits for feedback before proceeding. This back-and-forth is how the validation works.

---

## How We Work Together

This is a collaborative validation, not a rubber stamp. Karl brings domain knowledge and intuition about what matters. Claude brings systematic scenario analysis and fresh eyes on gaps. Together we stress-test the design before committing to implementation.

**On finding gaps:** These are valuable discoveries, not failures. Every gap found now is hours saved later.

**On ambiguity:** When the design is ambiguous, Claude surfaces the ambiguity with options. Karl decides.

**On scope:** We validate what's in scope for the current implementation, not the full north star vision.

**On pushing back:** If Claude's scenarios seem shallow or miss the point, say so. The best gaps often come from "what about when X happens?" questions that Claude didn't consider.

---

## Command Usage

```
/kdesign-validate design: <design-doc.md> arch: <architecture-doc.md> [scope: <scope-description>]
```

**Required:**
- `design:` — The design/spec document
- `arch:` — The architecture document

**Optional:**
- `scope:` — What subset of the design to validate (e.g., "MVP Phase 1-2" or "checkpoint save/restore only")
- Additional reference docs can be included

---

## Validation Process

### Step 1: Scenario Enumeration

Claude reads the design and architecture docs, then proposes 8-12 concrete scenarios covering:

**Happy paths (3-4 scenarios):**
- The primary use case working end-to-end
- Key variations (different inputs, configurations)

**Error paths (2-3 scenarios):**
- Expected failures (validation errors, gate failures)
- Recovery flows (retry, resume, rollback)

**Edge cases (2-3 scenarios):**
- Cancellation at various points
- Concurrent operations
- State transitions that might be ambiguous

**Integration boundaries (1-2 scenarios):**
- Cross-component communication
- External system interactions

**Output format:**
```markdown
## Proposed Scenarios

### Happy Paths
1. **[Scenario Name]**: [One sentence description]
2. ...

### Error Paths
3. **[Scenario Name]**: [One sentence description]
4. ...

### Edge Cases
5. **[Scenario Name]**: [One sentence description]
6. ...

### Integration Boundaries
7. **[Scenario Name]**: [One sentence description]
8. ...
```

---

**Pause: Scenario Review**

After proposing scenarios, Claude pauses and asks:

> "These are my proposed scenarios. Before I trace through them:
> 
> 1. **What's missing?** What failure modes have you seen before? What keeps you up at night about this design?
> 2. **What's not worth tracing?** Any scenarios here that are obvious or low-risk?
> 3. **What's the scary scenario?** The one that feels like it could bite us — even if you can't articulate exactly why?
>
> I'd rather trace 5 scenarios that matter than 12 that don't."

The scenarios Karl adds here are often the most valuable ones — they come from lived experience with the codebase and past failures. This is where Claude's systematic approach meets Karl's institutional knowledge.

---

### Step 2: Scenario Walk-Through

For each approved scenario, Claude traces through the architecture step-by-step:

**For each step:**
- Which component handles this?
- What is the input (data shape, state)?
- What processing occurs?
- What is the output (data shape, state change)?
- What could go wrong?

**Output format:**
```markdown
## Scenario: [Name]

**Trigger:** [What initiates this scenario]
**Expected Outcome:** [What success looks like]

### Execution Trace

| Step | Component | Action | Input | Output | State Change |
|------|-----------|--------|-------|--------|--------------|
| 1 | CLI | User runs command | `ktrdr agent trigger` | HTTP POST | - |
| 2 | API | Receives request | POST /agent/trigger | operation_id | Operation: PENDING |
| 3 | AgentService | Creates session | trigger_reason | session_id | Session: DESIGNING |
| ... | ... | ... | ... | ... | ... |

### Questions / Gaps Identified

- **[Q1]**: [Question about ambiguity or missing detail]
- **[GAP]**: [Something the design doesn't cover]
```

**Key questions Claude asks during walk-through:**
- "What happens if this fails?" (for each step)
- "What state is the system in if we stop here?"
- "How does component A know about state change in component B?"
- "Is this synchronous or async? What are the implications?"

---

### Step 3: Gap Analysis

After all scenarios are traced, Claude consolidates findings:

**Gap Categories:**

1. **State Machine Gaps** — Transitions not covered
   - "What state is the session in after training completes but before backtest starts?"
   - "Can a session be cancelled while in QUEUED state?"

2. **Error Handling Gaps** — Failures without defined behavior
   - "What happens if artifact write succeeds but DB insert fails?"
   - "How does the system recover from a partial checkpoint?"

3. **Data Shape Gaps** — Undefined or ambiguous data
   - "What fields are in the checkpoint metadata JSON?"
   - "What's the format of the operation result summary?"

4. **Integration Gaps** — Unclear component boundaries
   - "Who owns the decision to retry vs. fail?"
   - "How does the worker know which checkpoint to load?"

5. **Concurrency Gaps** — Race conditions or ordering issues
   - "What if two triggers fire simultaneously?"
   - "Can a cancel arrive while a checkpoint is being written?"

6. **Infrastructure Gaps** — Deployment, restart, recovery issues
   - "What happens on backend restart mid-operation?"
   - "How are orphaned child operations cleaned up?"

**Output format:**
```markdown
## Gap Analysis

### Critical (Must Resolve Before Implementation)

**[GAP-1]: [Title]**
- **Category:** State Machine
- **Scenario:** [Which scenario exposed this]
- **Issue:** [Description]
- **Options:**
  - A) [Option with trade-offs]
  - B) [Option with trade-offs]
- **Recommendation:** [Claude's suggestion]

### Important (Should Resolve, May Defer)

**[GAP-2]: [Title]**
...

### Minor (Note for Implementation)

**[GAP-3]: [Title]**
...
```

---

**Pause: Gap Resolution**

After presenting gaps, Claude works through each critical gap with Karl:

> "I found [N] critical gaps that need decisions before we proceed.
>
> Let's work through them one at a time:
>
> **[GAP-1]: [Title]**
> [Explanation of the issue]
>
> Options:
> - A) [Option] — [Trade-offs]
> - B) [Option] — [Trade-offs]
>
> I'm leaning toward [X] because [reasoning]. What's your take?
>
> Also — does this gap remind you of anything that's bitten you before?"

**For each critical gap:**
- Claude presents options and trade-offs
- Claude gives a recommendation with reasoning
- Karl decides (or asks for more analysis)
- Decision is recorded

This is where the real value happens. The gap analysis is just setup for the conversation. Karl's decisions ("I'm comfortable losing sessions on restart, I just don't want inconsistencies") turn vague gaps into concrete constraints.

---

### Step 4: Interface Contracts

Based on the scenario traces and gap resolutions, Claude produces concrete interface specifications:

**API Endpoints:**
```markdown
### POST /agent/trigger

**Request:**
```json
{
  "trigger_reason": "start_new_cycle" | "training_completed" | "backtest_completed"
}
```

**Response (202 Accepted):**
```json
{
  "operation_id": "op_agent_...",
  "session_id": 123,
  "status": "started"
}
```

**Error Responses:**
- 409 Conflict: Active session exists
- 503 Service Unavailable: Budget exhausted
```

**State Transitions:**
```markdown
### Session State Machine

```
IDLE
  ├─[trigger: start_new_cycle]─→ DESIGNING
  
DESIGNING
  ├─[event: design_complete]─→ TRAINING
  ├─[event: design_failed]─→ IDLE (outcome: FAILED_DESIGN)
  ├─[event: cancelled]─→ IDLE (outcome: CANCELLED)

TRAINING
  ├─[event: training_complete, gate: PASS]─→ BACKTESTING
  ├─[event: training_complete, gate: FAIL]─→ IDLE (outcome: FAILED_TRAINING_GATE)
  ├─[event: training_error]─→ IDLE (outcome: FAILED_TRAINING)
  ├─[event: cancelled]─→ IDLE (outcome: CANCELLED)
  
...
```
```

**Data Shapes:**
```markdown
### CheckpointData (Training)

```python
@dataclass
class TrainingCheckpointData:
    # Metadata (always present)
    operation_id: str
    checkpoint_type: Literal["periodic", "cancellation", "failure"]
    created_at: datetime
    
    # Training state
    epoch: int
    batch_index: int  # 0 if starting fresh epoch
    training_loss: float
    validation_loss: float
    learning_rate: float
    
    # Artifact paths (relative to artifacts_dir)
    model_path: str  # e.g., "model.pt"
    optimizer_path: str  # e.g., "optimizer.pt"
    best_model_path: Optional[str]  # e.g., "best_model.pt"
```
```

---

### Step 5: Vertical Milestone Structure

Finally, Claude proposes an implementation structure organized as vertical slices, not horizontal layers.

**Principles:**
- Each milestone is E2E testable
- Each milestone builds on the previous
- Each milestone delivers user-visible value (or proves a critical path)

**Output format:**
```markdown
## Implementation Milestones

### Milestone 1: [Name] — [What's E2E Testable]

**User Story:** As a [user], I can [action] and see [result].

**Scope:**
- [Component A]: [What's built]
- [Component B]: [What's built]
- [Component C]: [Minimal/stub if needed]

**E2E Test:**
```
Given: [Initial state]
When: [User action]
Then: [Observable result]
```

**Estimated Effort:** [X days]

**Depends On:** [Previous milestone or nothing]

---

### Milestone 2: [Name] — [What's E2E Testable]

...
```

**Example transformation (from horizontal to vertical):**

❌ **Horizontal (problematic):**
```
Phase 1: All database tables
Phase 2: All service layer code  
Phase 3: All API endpoints
Phase 4: All CLI commands
Phase 5: Integration testing
```

✅ **Vertical (better):**
```
Milestone 1: "User can trigger agent and see a strategy saved"
  - DB: agent_sessions table only
  - Service: TriggerService (minimal), StrategyService
  - API: POST /agent/trigger, GET /agent/status
  - CLI: ktrdr agent trigger, ktrdr agent status
  - E2E: Trigger → design completes → strategy file exists

Milestone 2: "User can see agent start training after design"
  - DB: Add training columns to sessions
  - Service: Training integration in TriggerService
  - API: No changes (status already shows phase)
  - CLI: No changes
  - E2E: Trigger → design → training starts → progress visible

Milestone 3: "User can see full cycle complete"
  - DB: Add backtest/assessment columns
  - Service: Backtest integration, quality gates
  - API: No changes
  - CLI: No changes  
  - E2E: Trigger → design → train → backtest → assessment
```

---

## Final Output

At the end of validation, Claude produces a summary document:

```markdown
# Design Validation: [Project Name]

**Date:** [Date]
**Documents Validated:**
- Design: [filename]
- Architecture: [filename]
- Scope: [what was validated]

## Validation Summary

**Scenarios Validated:** X/Y passed
**Critical Gaps Found:** N (all resolved)
**Interface Contracts:** Defined for [list]

## Key Decisions Made

These decisions came from our conversation and should inform implementation:

1. **[Decision]**: [What was decided and why]
   - Context: [What gap or question prompted this]
   - Trade-off accepted: [What we're giving up]
   
2. ...

## Scenarios Added by Karl

These scenarios weren't in the initial enumeration but proved important:

1. **[Scenario]**: [Why it mattered]
2. ...

## Remaining Open Questions

To be resolved during implementation:

1. **[Question]**: [Context]
2. ...

## Recommended Milestone Structure

[Summary of milestones with effort estimates]

## Appendix

- Full scenario traces (for reference)
- Complete interface contracts
- Gap analysis details
```

### What Gets Saved

**Save to repo (scenarios.md):**
- Final scenario list (including Karl's additions)
- Key decisions with rationale
- Interface contracts
- Milestone structure

**Don't save (conversation artifacts):**
- Gap analysis details (gaps are resolved, decisions captured above)
- Walk-through traces (working material)
- Back-and-forth discussion

The saved artifact should be useful for:
- Future Claude sessions ("why did we decide X?")
- Onboarding ("what is this system supposed to do?")
- Testing ("what scenarios should we cover?")

---

## When Validation Fails

Sometimes validation reveals that the design needs significant rework. Signs of this:

- **More than 5 critical gaps** — The design is underspecified
- **Scenarios can't be traced** — The architecture is too vague
- **Circular dependencies** — Components depend on each other in ways that can't be resolved
- **Missing core capability** — A fundamental piece isn't designed

In these cases, Claude should say:

> "This design has [N] critical gaps that suggest it needs another iteration before implementation planning. The main issues are [X, Y, Z]. I recommend we [specific action] before proceeding."

This is valuable! It's much better to discover this now than after writing code.

---

## Conversation Patterns That Work

Based on experience, these conversation patterns produce the best results:

### Pattern 1: "What keeps you up at night?"

After proposing scenarios, ask what feels risky even if it's hard to articulate. The answer often reveals scenarios Claude would never think of.

**Example:**
> Claude: "These are my proposed scenarios..."
> Karl: "The one thing that tripped v1 was backend restart mid-operation"
> Claude: [Adds infrastructure recovery scenarios that expose critical gaps]

### Pattern 2: "What's the constraint?"

When a gap has multiple options, ask Karl for the real constraint. The answer often simplifies the decision dramatically.

**Example:**
> Claude: "We could persist operations to DB, or add startup cleanup, or..."
> Karl: "I'm comfortable losing cycles on restart. I just don't want inconsistencies."
> Claude: [Now knows the constraint is consistency, not durability — changes the analysis]

### Pattern 3: "Does this remind you of anything?"

Past failures are the best predictor of future failures. When a gap surfaces, ask if it's familiar.

**Example:**
> Claude: "There's a gap where operation state and session state could desync..."
> Karl: "That's exactly what broke v1 — two sources of truth"
> Claude: [Understands this isn't a theoretical gap, it's a known failure mode]

### Pattern 4: "Let me trace that"

When Karl adds a scenario, trace it immediately even if it seems simple. The act of tracing often reveals surprises.

**Example:**
> Karl: "What about backend restart during training?"
> Claude: [Traces step by step, discovers OperationsService is in-memory]
> Claude: "Wait — if OperationsService is in-memory, we can't even detect orphans after restart"

### Pattern 5: "What would you need to see?"

When Karl is uncertain about a decision, ask what information would help.

**Example:**
> Karl: "I'm not sure if we need operation persistence..."
> Claude: "What would you need to see to decide? Should I trace what happens without it?"
> Karl: "Yes, show me the failure mode"
> Claude: [Traces, shows concrete problem, Karl decides]

---

## Integration with ktask

After validation completes, the milestone structure becomes the input to implementation planning. Each milestone can be expanded into tasks following the ktask pattern:

```
Milestone 1 → Phase 1 tasks (with TDD, acceptance criteria, etc.)
Milestone 2 → Phase 2 tasks
...
```

The key difference: tasks within a milestone are all working toward one E2E-testable outcome, not building horizontal layers.

---

## Why This Works (And What Doesn't)

### What makes validation effective:

1. **Concrete scenarios, not abstract review** — "What happens when X" is testable. "Is the design good" is not.

2. **Conversation, not checklist** — Claude's initial scenarios are scaffolding. The real value comes from Karl's additions and decisions.

3. **Traced execution, not hand-waving** — Writing out "Step 1: Component A does X, Step 2: Component B receives Y" forces precision. Gaps become obvious.

4. **Decisions recorded** — "I'm comfortable losing cycles on restart" is a constraint that shapes everything. Without recording it, the next session won't know.

### What doesn't work:

1. **Running it without engagement** — If Karl just says "looks good" to every checkpoint, the validation is useless. The value is in the pushback.

2. **Skipping scenarios to save time** — The "boring" scenarios (happy path) are quick to trace. The interesting ones (infrastructure failure) take time but find real bugs.

3. **Treating gaps as failures** — Finding gaps is the point. A validation that finds nothing is suspicious.

4. **Over-documenting** — The conversation matters more than the artifact. Save decisions and scenarios, not every trace.

---

## Example: Applying to Checkpoint System

If we had run this validation on the checkpoint system before v1:

**Scenario that would have caught the gap:**
> "User cancels training at epoch 5. System saves checkpoint. User resumes. Training continues from epoch 5."

**Walk-through would have asked:**
- "What data is saved in the checkpoint?" → Forces enumeration
- "Where are artifacts written?" → Forces storage decision
- "How does the worker load the checkpoint on resume?" → Forces distributed access design
- "What if epoch 5 was partially complete?" → Forces restart-partial-unit decision

**Gap that would have been found:**
- "The design says 'save training state' but doesn't specify what fields. Need to analyze ModelTrainer to determine necessary and sufficient data."

This would have led to Phase 0's research tasks being done *before* the architecture was finalized, not after.
