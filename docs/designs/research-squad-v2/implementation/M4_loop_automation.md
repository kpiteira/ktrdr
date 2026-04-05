---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# M4: Loop Automation

**When this works:** Karl starts the squad and walks away. It runs 5+ cycles unattended, manages its own cadence (full exploration → quick iteration → synthesis when context grows), detects when it's stuck (3 non-productive cycles → stop and report), avoids repeating experiments, and compounds knowledge. This replaces `loop_runner.sh` (810 lines of shell) with a Python loop that has all the same features plus the conversational model from M1-M3.

**Scenario (from design doc — "Scenario 1" extended):** Karl writes a nudge: "Focus on LSTM/GRU with 5m data." Starts the loop. Cycle 1: Director reads nudge, spawns Engineer for LSTM strategy. Cycle 2: quick_iteration — Engineer tries GRU variant. Cycle 3: Results converging, Director calls full_squad with Quant to assess cost viability. Cycle 4: Inventor suggests regime-conditional approach. Cycle 5: synthesis triggered (every 5 cycles), Scribe produces updated synthesis.md. Karl checks in, reads synthesis, writes new nudge.

**Prerequisite:** M1 complete (core cycle). Can run in parallel with M2/M3.

**v1 is dead:** `loop_runner.sh` is not coming back. This milestone completes the Python replacement. v1 shell scripts remain as reference in the repo.

---

## Task 4.1: Cadence Management

**File(s):** `.squad/orchestrator/loop.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Implement cadence control — the mechanism v1's `loop_runner.sh` uses to let the Director control loop behavior between cycles. The Director writes cadence at the end of each cycle; the outer loop reads it at the start of the next.

**Implementation Notes:**
- Cadence file: `{shared_dir}/loop/cadence.md` (same location as v1 — compatible)
- Modes (preserved from v1, all 4 supported):
  - `full_squad` — Director can invoke any/all consultants
  - `quick_iteration` — Director + Engineer only, fast parameter variant
  - `synthesis` — run synthesis cycle next (Scribe produces synthesis.md)
  - `pause` — stop the loop cleanly
- Python reads cadence at top of each iteration:
  - `pause` → exit loop with clean status
  - `synthesis` → run synthesis cycle (Task 4.2) instead of research cycle
  - `full_squad` / `quick_iteration` → pass mode to Director prompt, run normal cycle
- Director writes cadence during LEARN phase via Write tool (or Python writes based on Director's decision)
- Iteration counter: read/write `{shared_dir}/loop/iteration-count.txt` (same as v1 — compatible)
- Maximum iterations: configurable, default 20 (safety valve)
- Missing cadence file defaults to `full_squad` (first run or reset)

**Testing Requirements:**
- [ ] Unit test: reads all 4 cadence modes correctly from file
- [ ] Unit test: pause exits loop with LoopResult status="paused"
- [ ] Unit test: synthesis mode triggers synthesis cycle (not research)
- [ ] Unit test: iteration counter increments each cycle, persists to file
- [ ] Unit test: max iterations exits loop with status="max_iterations"
- [ ] Unit test: missing cadence file defaults to full_squad

**Acceptance Criteria:**
- [ ] All 4 cadence modes handled correctly
- [ ] Cadence file compatible with v1 format (same location, same values)
- [ ] Iteration counter compatible with v1 (same file, same format)
- [ ] Max iterations safety valve prevents runaway loops

---

## Task 4.2: Synthesis Triggering

**File(s):** `.squad/orchestrator/loop.py`, `.squad/orchestrator/context.py` (extend)
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Implement synthesis triggering — the mechanism that keeps the knowledge base manageable as experiments accumulate. This replaces `loop_lib.sh:needs_synthesis()` with a Python equivalent and adds the synthesis cycle execution.

**Implementation Notes:**
- **Three trigger paths** (from v1, plus emergency):
  1. Director sets cadence to `synthesis` (explicit request)
  2. Emergency: ContextLoader.needs_synthesis returns True (context > 80% of 200K budget)
  3. Periodic: every N cycles (configurable, default 10) — from v1's `loop_lib.sh` interval logic
- **Synthesis cycle is different from research:**
  - Director spawns Scribe with full `experiments.md` (this is the one time full history is loaded)
  - Scribe produces updated `synthesis.md` (distilled patterns, best results, open questions)
  - No Engineer, no consultants, no experiment execution
  - Should complete in <30K tokens, <$0.50
- After synthesis: cadence resets to previous mode (not stuck in synthesis loop)
- synthesis.md replaces full experiments.md for all agents in subsequent cycles

**Testing Requirements:**
- [ ] Unit test: Director cadence=synthesis triggers synthesis cycle
- [ ] Unit test: emergency synthesis triggered when context > 80% budget
- [ ] Unit test: periodic synthesis at configurable interval (every N cycles)
- [ ] Unit test: synthesis cycle spawns only Scribe with full experiments.md
- [ ] Unit test: cadence resets after synthesis (no infinite synthesis loop)
- [ ] Unit test: synthesis.md file updated after cycle

**Acceptance Criteria:**
- [ ] All three trigger paths work
- [ ] Synthesis is lightweight (Scribe only, <30K tokens)
- [ ] Cadence resets post-synthesis
- [ ] Functionally equivalent to v1's `loop_lib.sh:needs_synthesis()`

---

## Task 4.3: Stall Detection + De-duplication

**File(s):** `.squad/orchestrator/loop.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Detect when the squad is stuck and avoid repeating experiments. This is the mechanism that prevents the squad from burning tokens on non-productive cycles — a real problem in v1 where the squad sometimes repeated the same experiment or the Director over-paused for 3+ cycles.

**Implementation Notes:**
- **Stall detection** (from v1 handoff HANDOFF_M2.md):
  - Non-productive cycle: no experiment executed, experiment failed, or no KB updates
  - 3 consecutive non-productive cycles → stop loop, write `{shared_dir}/loop/fatal-error.md`
  - Director over-pause: 2 consecutive pauses without experiment count as non-productive
  - v1 gotcha: Director accumulated D-rules and over-paused aggressively. v2 mitigates by giving Director better context about the cost of pausing.
- **De-duplication:**
  - Before execute_experiment: check strategy name against recent experiments in experiments.md
  - Exact name match → warn Director: "This strategy name was already run in cycle N. Confirm you want to re-run or rename."
  - Feature overlap (>80% same indicator set) → advisory warning to Director
  - De-duplication is advisory (warns, doesn't block) — Director may have good reason to repeat
- **Cycle history log:** `{shared_dir}/loop/cycle-history.json`
  - `[{iteration, status, experiment, agents_spawned, cost_usd, timestamp}]`
  - Used for stall detection, cost tracking, and diagnostics

**Testing Requirements:**
- [ ] Unit test: 3 consecutive non-productive cycles triggers stall stop
- [ ] Unit test: failed experiments count as non-productive
- [ ] Unit test: stall writes fatal-error.md with actionable explanation
- [ ] Unit test: strategy name de-duplication detects exact match
- [ ] Unit test: de-duplication warning is advisory (returns warning, doesn't block execution)
- [ ] Unit test: cycle history JSON written and read correctly
- [ ] Unit test: stall counter resets after a productive cycle

**Acceptance Criteria:**
- [ ] Stall detection stops loop after 3 non-productive cycles (matching v1 behavior)
- [ ] De-duplication warns Director about repeated experiments
- [ ] Cycle history provides diagnostic trail
- [ ] fatal-error.md written with enough context for Karl to diagnose

---

## Task 4.4: Full Loop Entry Point + v1 Replacement

**File(s):** `.squad/orchestrator/loop.py`, `.squad/orchestrator/__init__.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Wire cadence, synthesis, stall detection, and core cycle into a complete loop entry point. This is the Python replacement for `loop_runner.sh` (810 lines of shell). After this task, the entire v1 orchestration can be replaced by `python -m squad.orchestrator`.

**Implementation Notes:**
- Entry point: `async def run_loop(max_iterations: int = 20) -> LoopResult`
- Loop flow:
  ```
  for iteration in range(1, max_iterations + 1):
      1. Read cadence → if pause, exit
      2. Check stall → if 3 non-productive, exit with fatal-error.md
      3. Check synthesis triggers → if needed, run synthesis cycle
      4. Run research cycle (run_cycle from M1/M2/M3)
      5. Update cycle history
      6. Check de-duplication for advisory warnings
      7. Increment iteration counter
  ```
- `LoopResult`: `{iterations_run, experiments_completed, stall_detected, final_cadence, total_cost_usd}`
- **CLI entry:** callable via `python -m squad.orchestrator.loop` — or via a thin shell wrapper at `.squad/run_v2.sh` for parity with v1's `loop_runner.sh`
- **Logging:** structured output per iteration (iteration #, cadence, agents spawned, outcome, cost) — similar to v1's log output in `~/.ktrdr/shared/squad/loop/`
- **Signal handling:** SIGINT/SIGTERM → clean shutdown (teardown all sessions, persist state, write cycle history)
- **State files:** preserves same state file formats (`cadence.md`, `iteration-count.txt`, `fatal-error.md`) — the format is good, only the shell orchestration was broken

**Testing Requirements:**
- [ ] Unit test: loop runs N iterations when no stop condition
- [ ] Unit test: pause cadence exits loop cleanly with LoopResult
- [ ] Unit test: stall detection exits loop, writes fatal-error.md
- [ ] Unit test: synthesis cycle runs when triggered mid-loop
- [ ] Unit test: SIGINT triggers clean shutdown (sessions torn down, state saved)
- [ ] Unit test: LoopResult contains accurate cost and experiment count
- [ ] Integration test: 3 mock cycles with varying cadence (full_squad → quick_iteration → synthesis)

**Acceptance Criteria:**
- [ ] Complete loop entry point covering all loop_runner.sh features
- [ ] All stop conditions handled (pause, stall, max iterations, signal)
- [ ] State file formats preserved (same cadence.md, iteration-count.txt, fatal-error.md)
- [ ] Clean shutdown preserves state on interruption

---

## Task 4.5: VALIDATION — 5 Cycles Unattended

**Type:** VALIDATION
**Estimated time:** 3-4 hours

**Description:**
Run 5 complete cycles unattended. This proves Karl can start the squad and walk away. The loop manages cadence, compounds knowledge, and doesn't get stuck.

**Scenario under test:** Start loop with nudge "Explore GRU architectures on 5m EURUSD." Loop runs 5 cycles: Director reads nudge → designs experiments → validates → executes → records → adjusts cadence → repeats. At least one cadence change occurs. Knowledge base grows. No human intervention.

**Validation Steps:**

1. **Load the `ke2e` skill** before designing any validation
2. **Invoke ke2e-test-scout** with: "Squad v2 unattended loop: 5 cycles complete without intervention. Cadence changes at least once. experiments.md gains 3+ entries. No stall detected. Cycle history JSON shows all iterations. Total cost < $10. v1 loop_runner.sh still functional alongside (coexistence)."
3. **Invoke ke2e-test-runner** with the identified test recipe
4. **Tests must exercise real infrastructure** — real Claude sessions, real training, real KB writes

**Success Criteria:**
- [ ] 5 cycles complete without human intervention
- [ ] experiments.md grows with 3+ new entries (some cycles may skip execution)
- [ ] At least one cadence change observed (e.g., full_squad → quick_iteration, or synthesis triggered)
- [ ] Iteration counter reaches 5+
- [ ] No stall (or stall correctly detected if research genuinely stuck)
- [ ] De-duplication warnings issued if repeated experiments attempted
- [ ] Total token usage < 500K across 5 cycles (target: 275-400K, vs v1's 1.15M)
- [ ] Clean shutdown — all sessions torn down, state saved

**Evidence Required:**
- cycle-history.json showing all 5 iterations with status, cost, agents
- experiments.md diff showing new entries
- cadence.md changes across cycles
- Token usage breakdown per cycle
- LoopResult summary
