# Handoff — M2: Autonomous Loop

## Status: IN PROGRESS — Tasks 2.1-2.3 complete, Task 2.4 partially validated

## What Works
- **Loop runner** (`.squad/loop_runner.sh`) — Ralph pattern, fresh Claude session per cycle
- **Cadence control** — Director outputs full_squad/quick_iteration/synthesis/pause
- **Direct-write state updates** — Claude writes to knowledge base files during evaluate phase (no parsing)
- **Resume pending experiments** — loop checks current-experiment.md, skips discussion if experiment already designed
- **Progress-based stall detection** — no fixed timeout, only aborts if progress hasn't changed in 15 min
- **Executor** — train → backtest → structured JSON results, end-to-end proven

## Validation Run Results (short training, 6-month windows)
| Cycle | Experiment | Result |
|-------|-----------|--------|
| 1 | squad_c10_confidence_regime_sweep | 74 trades, WR 31.1%, Sharpe -0.37, Return -3.02% |
| 2 | squad_c11_cdcc_concordance | FAILED — invalid strategy YAML (400 Bad Request) |
| 3 | squad_c12_f1_5_entropy_selectivity | FAILED — invalid strategy YAML |

## What's Broken

### Strategy YAML validation (~66% failure rate)
The Engineer agent generates strategies that ktrdr rejects. Common issues:
- Using fields or label sources that don't exist in v3 grammar
- YAML structural issues (multi-document, invalid nesting)
- Designing experiments that need components not in ktrdr

**Fix needed:**
1. Add `ktrdr strategies validate` step in executor before training
2. Tighten Engineer charter with explicit examples of valid v3 YAML
3. Give Engineer the `squad_cycle1_control.yaml` as a working template

### GPU training host service
- MPS (Apple Silicon) throws "Dimension out of range" on LSTM training
- DB password mismatch between local-prod secrets and sandbox secrets resolved by nuking DB volume
- Orphaned multiprocessing children hold port 5002 after `stop-hosts`
- Stale GPU worker registrations poison the worker selection (backend always prefers GPU)

**Fix needed:** File issues for MPS LSTM compat, worker health checks before dispatch, robust process cleanup in stop-hosts

## Bugs Fixed During M2
1. **cp identical file** — `cp` returns exit 1 on macOS when source=dest, killed executor under `set -e`
2. **Multi-document YAML** — squad output included both arms in one YAML block
3. **State update parsing** — Claude's output format varied, parser missed updates → replaced with direct writes
4. **lr_scheduler format** — boolean crashes ModelTrainer, needs dict format (from M1, still relevant)

## Knowledge Base State
- 21 decisions (D1-D21)
- 7+ experiment entries
- 11+ agent history entries per agent
- Frontiers evolved: F0 (execution infra), F1 (label quality), F2 (feature enrichment), F3 (cost-aware training)

## Critical Fix: Strategy YAML Validation (blocks everything)

The squad designs strategies that ktrdr rejects ~66% of the time. The fix has two parts:

### 1. Engineer must validate its own output
The Engineer charter needs updating:
- Reference the v3 strategy grammar spec (`.claude/skills/strategy-grammar-v3/SKILL.md`)
- After generating YAML, the Engineer agent should call `ktrdr strategies validate <name>` itself
- If validation fails, fix the YAML before submitting — don't pass broken specs to the executor
- Engineers embody precision. The current charter says "no missing fields" but doesn't enforce it.

### 2. Executor pre-training validation
Add `uv run ktrdr strategies validate "$NAME"` in executor.sh before `ktrdr train`. If validation fails, return a structured error with the validation message so the squad can fix it. This is a 5-line change.

### 3. `ktrdr strategies validate` exists and works
This command has been available the whole time. We just never wired it in. The executor and the Engineer agent should both use it.

## Next Steps (to complete M2)
1. Update Engineer charter — must validate YAML with `ktrdr strategies validate`
2. Add validation step in executor.sh (5 lines)
3. Run 3 short validation cycles (6-month training) — expect 3/3 to produce data
4. Run 5 full cycles (6-year training) — prove compounding
5. ke2e test design and execution
6. PR and merge

## How to Resume
Run `/kbuild research-squad/M2` — it will read this handoff, see Tasks 2.1-2.3 done, and continue with 2.4.
The branch is `impl/research-squad-M2-loop`, pushed to origin.
