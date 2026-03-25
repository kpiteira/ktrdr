---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# M2: Autonomous Loop

## Goal
The squad runs N cycles unattended using the Ralph loop pattern: fresh context per iteration, all state on disk, backpressure from real backtests. The Director controls cadence (full squad vs quick iteration).

## Dependencies
- M1 complete (Coordinator + Executor + knowledge base proven in one manual cycle)

## Tasks

### Task 2.1: Loop Runner

**File(s):** `.squad/loop_runner.py`
**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Build the Ralph loop that wraps the Coordinator and Executor into an autonomous cycle. The loop runner:
1. Reads current state from `.squad/` files
2. Calls the Coordinator for the squad discussion phase
3. Calls the Executor for the experiment phase
4. Calls the Coordinator for the evaluation phase (resume Critic + Quant)
5. Calls the Scribe for state updates
6. Writes all state to disk
7. Checks should_continue() and loops

**Implementation Notes:**
- Each iteration starts a fresh Claude session (no carried-over context — Ralph pattern)
- State is read from and written to `.squad/` files only
- `should_continue()` checks: iteration count < max, no fatal errors, Director hasn't paused
- Configurable: max_iterations (default 10), train_start/end dates, backtest_start/end dates
- Crash recovery: if interrupted between steps, the loop reads disk state and determines where to resume (check for `current-experiment.md` presence)
- Log each iteration: cycle number, experiment name, duration, result summary

**Testing Requirements:**
- [ ] Loop executes 2 iterations sequentially without error
- [ ] State files are updated between iterations (experiment count increments)
- [ ] Loop stops when max_iterations reached
- [ ] Crash recovery: manually interrupt, restart, loop picks up from last completed state

**Acceptance Criteria:**
- [ ] Loop runner executes N cycles unattended
- [ ] Each cycle is a fresh context (no conversation carryover)
- [ ] All state persists to `.squad/` files between cycles
- [ ] Loop terminates cleanly on max_iterations or Director pause

---

### Task 2.2: Director Cadence Control

**File(s):** `.squad/agents/director/charter.md` (update), `.squad/loop/cadence.md`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement the Director's ability to control squad cadence. After each cycle, the Director can signal:
- **full_squad**: convene all agents (default for first few cycles and after significant results)
- **quick_iteration**: skip STRATEGIZE, just DESIGN → EXECUTE → EVALUATE → LEARN (when exploring within a frontier)
- **synthesis**: trigger a synthesis session (every N experiments or when Director detects diminishing returns)
- **pause**: stop the loop (when human review is needed)

**Implementation Notes:**
- Director's output includes a `cadence` field: `full_squad | quick_iteration | synthesis | pause`
- Loop runner reads cadence from Director's output and adjusts the next cycle
- Quick iteration skips: Scout, Director strategic proposal, Inventor novel proposal — only Engineer (next variant), Executor, Critic evaluation, Scribe recording
- Synthesis triggers Scribe to produce `synthesis.md` update
- Cadence decision written to `cadence.md` with reasoning

**Testing Requirements:**
- [ ] Director outputs a valid cadence signal
- [ ] Quick iteration cycle is shorter (fewer agents spawned)
- [ ] Synthesis cycle produces updated synthesis.md
- [ ] Pause signal stops the loop

**Acceptance Criteria:**
- [ ] Director can switch between full_squad, quick_iteration, synthesis, and pause
- [ ] Loop runner respects the cadence signal
- [ ] Quick iterations are measurably leaner (fewer agent calls)

---

### Task 2.3: State Update Automation

**File(s):** `.squad/loop_runner.py` (update), `.squad/knowledge/*.md` (automated writes)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Automate the Scribe's state updates. After each cycle, the loop runner parses the Scribe's output and writes:
- New experiment entry to `experiments.md`
- Hypothesis status updates to `hypotheses.md`
- Agent history updates to each agent's `history.md`
- Decision entries to `decisions.md` (if any)
- Frontier updates to `frontiers.md` (if Director changed)

**Implementation Notes:**
- Scribe output must follow a structured format that the loop runner can parse
- Define the Scribe's output format explicitly (markdown sections with identifiable headers)
- Append-only for experiments.md (never edit existing entries)
- Hypotheses can have status changes (queued → testing → confirmed/refuted)
- Agent histories are appended (one entry per cycle per agent that participated)
- Validate writes: check that experiments.md grew by exactly one entry

**Testing Requirements:**
- [ ] Scribe output is parseable by the loop runner
- [ ] experiments.md grows by one entry per cycle
- [ ] hypotheses.md reflects status changes from the cycle
- [ ] Agent history files grow for agents that participated
- [ ] No data is lost on write (append-only verification)

**Acceptance Criteria:**
- [ ] All state updates are automated (no manual editing required between cycles)
- [ ] State files are valid markdown after every update
- [ ] Iteration count tracks correctly

---

### Task 2.4: E2E Validation — 5 Autonomous Cycles

**File(s):** E2E test recipe
**Type:** VALIDATION
**Estimated time:** 3-4 hours (including training time for 5 experiments)

**Description:**
Validate autonomous operation by running 5 complete cycles without intervention.

1. Load the `ke2e` skill
2. Configure loop runner for 5 iterations
3. Start the loop and let it run
4. Verify after completion:
   - 5 experiments in experiments.md
   - Each experiment has real backtest results
   - Agent histories grew
   - No cycle repeated an identical experiment
   - Director made at least one cadence decision

**Acceptance Criteria:**
- [ ] 5 cycles complete without human intervention
- [ ] Each experiment is distinct (not repeating the same strategy)
- [ ] State files accurately reflect all 5 cycles
- [ ] No crashes or unrecovered errors

## Completion Checklist
- [ ] Loop runner executes N cycles autonomously
- [ ] Director controls cadence (full/quick/synthesis/pause)
- [ ] State updates automated after every cycle
- [ ] 5 autonomous cycles validated end-to-end
