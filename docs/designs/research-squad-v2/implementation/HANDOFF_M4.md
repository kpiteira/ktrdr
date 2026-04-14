# Handoff — M4: Loop Automation

## Status: IN PROGRESS — Tasks 4.1-4.4 complete, 4.5 (validation) pending

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

**__main__.py** — CLI entry point
- `python -m squad_engine --max-iterations 20 --synthesis-interval 10`
- Argparse for shared-dir, charter-dir, max-iterations, synthesis-interval
- Exit codes: 0 (clean), 130 (SIGINT), 1 (error/stall)

### Tests: 46 new tests in test_loop_automation.py

| Class | Tests | Coverage |
|-------|-------|----------|
| TestCadenceReader | 7 | All 4 modes, missing/empty defaults |
| TestIterationCounter | 3 | Read, write, increment |
| TestLoopResultDataclass | 1 | Default values |
| TestRunLoop | 6 | Pause, max_iterations, synthesis, counter, cadence update, cost |
| TestSynthesisTrigger | 6 | All 3 trigger paths, pause exclusion |
| TestSynthesisCycle | 3 | Scribe-only, cadence reset, file update |
| TestLoopWithSynthesis | 2 | Emergency + periodic synthesis in loop |
| TestStallDetection | 6 | Productive/non-productive, threshold, reset, fatal-error |
| TestDeduplication | 3 | Match, no match, advisory nature |
| TestCycleHistory | 3 | Write, append, empty |
| TestLoopWithStallDetection | 2 | Stall stops loop, productive resets |
| TestCycleHistoryIntegration | 1 | History written per iteration |
| TestIntegrationThreeCycles | 1 | Varying cadence flow |
| TestSignalHandling | 1 | KeyboardInterrupt returns partial result |
| TestLoopRunnerModule | 1 | LoopResult field check |

## Gotchas

1. **Mock cycles must include experiment_result.** After integrating stall detection, earlier tests that used mock cycles without `experiment_result` started triggering the stall detector. Fixed by adding `experiment_result={"status": "success"}` to productive mock cycles.

2. **Synthesis resets cadence.** `run_synthesis_cycle` always returns `cadence_next="full_squad"` to prevent getting stuck in a synthesis loop. The Director can still explicitly request synthesis again later.

## Next: Task 4.5 (Validation)

Run 5 unattended cycles. Requires real Claude sessions, real training infrastructure.
