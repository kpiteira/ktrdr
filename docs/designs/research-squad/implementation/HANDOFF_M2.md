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

## Next Steps (to complete M2)
1. Add strategy validation step in executor
2. Tighten Engineer prompt with working YAML template
3. Run 5 clean cycles (short training) with both fixes
4. If 4+ cycles produce data, run 5 full cycles (6-year training)
5. ke2e test design and execution
6. PR and merge
