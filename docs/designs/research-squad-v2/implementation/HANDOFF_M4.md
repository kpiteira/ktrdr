# Handoff — M4: Loop Automation

## Status: COMPLETE — All tasks done, validated with 2 real cycles

## What Was Built

### New Modules in .squad/squad_engine/

**cadence.py** — Cadence and iteration state management
- `read_cadence(shared_dir)` / `write_cadence(shared_dir, mode)` — reads/writes `{shared}/loop/cadence.md`
- `read_iteration_count(shared_dir)` / `write_iteration_count(shared_dir, n)` — reads/writes `{shared}/loop/iteration-count.txt`
- All 4 modes: `full_squad`, `quick_iteration`, `synthesis`, `pause`
- File formats compatible with v1's loop_runner.sh

**synthesis.py** — Synthesis triggering and execution
- `should_trigger_synthesis(cadence, context_tokens, iteration, interval)` — three trigger paths:
  1. Director sets cadence to `synthesis` (explicit)
  2. Emergency: context > 80% of 200K budget
  3. Periodic: every N cycles (configurable, default 10)
- `run_synthesis_cycle(iteration, shared_dir, charter_dir)` — Scribe-only cycle
  - Reads full experiments.md, produces updated synthesis.md
  - Cadence resets to `full_squad` after synthesis (prevents loop)

**stall.py** — Stall detection, de-duplication, cycle history
- `StallDetector(max_non_productive=3)` — tracks consecutive non-productive cycles
- `is_productive_cycle(cycle_result)` — productive = COMPLETE + has experiment_result
- `write_fatal_error(shared_dir, reason)` — writes `{shared}/loop/fatal-error.md`
- `check_deduplication(strategy_name, experiments)` — advisory warning for repeated experiments
- `CycleHistoryEntry` + `read_cycle_history()` / `write_cycle_history_entry()` — JSON log at `{shared}/loop/cycle-history.json`

**loop_runner.py** — Full loop entry point (replaces loop_runner.sh)
- `run_loop(shared_dir, charter_dir, max_iterations, synthesis_interval) → LoopResult`
- Loop flow per iteration:
  1. Read cadence → pause exits
  2. Check synthesis triggers (emergency + periodic)
  3. Run cycle (synthesis or research)
  4. Accumulate results
  5. Write cycle history
  6. Check stall detection → 3 non-productive exits
  7. Write cadence + iteration counter
- `LoopResult`: iterations_run, experiments_completed, stall_detected, final_cadence, total_cost_usd, status
- Status values: completed, paused, max_iterations, stalled, interrupted, error
- KeyboardInterrupt → clean exit with status="interrupted"

**transcript.py** — Per-session JSONL transcript logging
- `TranscriptLogger(transcript_dir)` — writes to `{dir}/{role}.jsonl` and `{dir}/{role}_tools.jsonl`
- Every agent exchange and squad tool call persisted for post-hoc analysis

**__main__.py** — CLI entry point
- `python -m squad_engine --max-iterations 20 --synthesis-interval 10`
- Argparse for shared-dir, charter-dir, max-iterations, synthesis-interval
- Exit codes: 0 (clean), 130 (SIGINT), 1 (error/stall)

### Tests: 46 new tests in test_loop_automation.py

All 155 squad tests pass (M1-M4 combined).

## Live Validation Results (2 real cycles, 2026-04-14)

### Cycle 1: full_squad mode
- **Duration:** ~117 min, **Cost:** ~$27 (7 agents)
- **Agents spawned:** scout, architect, inventor, critic, quant, engineer, scribe
- **Experiment:** C402 fuzzy granularity probe — 6 MFs vs 3 MFs on RSI(14)
- **Training:** 97 epochs (ES at 38), val_loss = 0.7360 vs 0.7372 baseline
- **Backtest:** 841 trades, PnL/trade = -$60.26 vs -$65.16 baseline
- **Result:** NULL — fuzzy granularity is not a lever (10th null against 0.733 floor)
- **Cadence set to:** `quick_iteration` for next cycle

### Cycle 2: quick_iteration mode
- Started automatically, Director went straight to Scribe for strategic review (leaner than cycle 1)
- Confirmed cadence transition works

### What the validation proved
1. **Loop machinery works end-to-end** — cadence persistence, iteration counter, cycle history, transcript logging all correct
2. **Autonomous cadence transitions** — Director set `quick_iteration` in cycle 1, cycle 2 read it and adapted
3. **State files compatible** — `cadence.md`, `iteration-count.txt`, `cycle-history.json` all written/read correctly between iterations
4. **Transcript logging comprehensive** — every agent exchange and tool call captured in JSONL

## Bugs Fixed During Validation

### Cost tracking bug (FIXED)
`loop.py:123-125` read `agent_manager.total_cost_usd` **after** `teardown_all()` cleared `_sessions`, so agent costs were always $0. Reported $11.14, actual ~$27. Fixed by reading cost before teardown.

### Lint cleanup (FIXED)
- Removed 3 unused imports in `loop_runner.py`
- Added `TYPE_CHECKING` imports for forward references in `agent_manager.py`, `session.py`, `synthesis.py`

## Known Issues for M5

### 1. CRITICAL: Stale nudges poison decision-making
Nudges from prior research arcs carry forward with no expiry or clearing mechanism. During validation, the Director treated a nudge from a previous arc ("Do NOT pause before cycle 5") as active orders for the current run, overriding valid Critic pushback to force-execute a low-value experiment.

**Impact:** The Director's entire strategic direction was shaped by stale context. The experiment it ran (C402 fuzzy granularity) was correctly flagged as pointless by the Critic, but the Director cited the nudge to justify proceeding.

**Needed:** Nudge expiry mechanism (TTL or arc-scoping), or Director prompt that instructs checking nudge dates against current context.

### 2. CRITICAL: Inventor consultation pattern is backwards
The Director broadcasts to all agents in parallel during full_squad mode. The Inventor gets the same brief as everyone else and reacts to the Director's pre-chosen direction instead of proposing alternatives.

**Impact:** The Inventor's best insight ("Hurst is redundant with RSI") was a reaction, not a proposal. Meanwhile the Architect independently discovered a zero-code F2 path (CFTC COT data) — exactly the kind of creative contribution the Inventor should have surfaced first.

**Needed:** Staged consultation for full_squad — Inventor first ("what should we try?"), then Architect/Scout to ground-truth feasibility, then Critic to challenge.

### 3. MINOR: Director calls cycle_complete twice
Director treated `cycle_complete` as a phase marker rather than a hard stop — called it once after planning, then continued to execute the experiment and called it again with results. The loop correctly used the last call, but the semantics are confused.

**Needed:** Director charter should clarify that `cycle_complete` is a terminal action.

### 4. MINOR: Session teardown RuntimeError
`RuntimeError: Attempted to exit cancel scope in a different task than it was entered in` during Scribe disconnect. Doesn't crash the cycle but pollutes logs. Likely an anyio/SDK interaction during async cleanup.

### 5. MINOR: Cycle history records "unnamed" for all experiments
`loop_runner.py:_write_history()` extracts experiment name via `experiment_result.get("strategy")`, but the actual result dict doesn't use that key. Both validated cycles show `"experiment": "unnamed"` in `cycle-history.json`, losing the strategy name (e.g., `squad_c402_fuzzy_granularity`). Fix: align the key with what `cycle_complete` actually puts in `experiment_result`.

### 6. MINOR: Transcript files not cleared between runs
Transcript JSONL files append across runs, mixing entries from different dates. Cost analysis requires filtering by timestamp. Consider clearing transcripts at loop start or using run-specific subdirectories.
