# Handoff — M2: Autonomous Loop

## Status: COMPLETE — 3/3 short validation cycles passed, ready for merge

## What Works
- **Loop runner** (`.squad/loop_runner.sh`) — Ralph pattern, fresh Claude session per cycle
- **Cadence control** — Director outputs full_squad/quick_iteration/synthesis/pause (demonstrated real pause decisions)
- **Direct-write state updates** — Claude writes to knowledge base files during evaluate phase (no parsing)
- **Resume pending experiments** — loop checks current-experiment.md, skips discussion if experiment already designed
- **Progress-based stall detection** — no fixed timeout, only aborts if progress hasn't changed in 15 min
- **Executor** — validate → train → backtest → structured JSON results, end-to-end proven
- **Pre-training validation** — `ktrdr validate` rejects invalid YAML before wasting training time
- **Stdin piping** — all Claude invocations use stdin to avoid ARG_MAX on large prompts
- **v3 version gate** — loop rejects non-v3 strategies (manual analysis protocols) before execution

## Validation Run Results (short training, 6-month windows)

### Final run (with all fixes)
| Cycle | Experiment | Discuss | Train+BT | Evaluate | Result |
|-------|-----------|---------|----------|----------|--------|
| 1 | squad_c13_high_confidence | 20 min | 11 min | 8 min | COMPLETE — state updated |
| 2 | squad_c14_ablation_momentum | 19 min | 2 min | 7 min | COMPLETE — state updated |
| 3 | squad_c15_loss_crossentropy | 18 min | 34 min | 9 min | COMPLETE — state updated |

### Earlier runs (before fixes)
| Cycle | Experiment | Result |
|-------|-----------|--------|
| 1 | squad_c10_confidence_regime_sweep | 74 trades, WR 31.1%, Sharpe -0.37, Return -3.02% |
| 2 | squad_c11_cdcc_concordance | FAILED — invalid strategy YAML (400 Bad Request) |
| 3 | squad_c12_f1_5_entropy_selectivity | FAILED — invalid strategy YAML |

## Bugs Fixed During M2
1. **cp identical file** — `cp` returns exit 1 on macOS when source=dest, killed executor under `set -e`
2. **Multi-document YAML** — squad output included both arms in one YAML block
3. **State update parsing** — Claude's output format varied, parser missed updates → replaced with direct writes
4. **lr_scheduler format** — boolean crashes ModelTrainer, needs dict format (from M1, still relevant)
5. **YAML validation** — ~66% failure rate. Fixed: executor validates with `ktrdr validate` before training; Engineer charter updated with full v3 grammar template
6. **ARG_MAX on evaluate phase** — `claude -p "$EVAL_PROMPT"` hit macOS ARG_MAX (~262KB) when results JSON was large. Fixed: pipe prompt via stdin (`cat file | claude -p`) instead of passing as argument. Applied to all 3 Claude invocations (discussion, synthesis, evaluate).
7. **Non-v3 strategy rejection** — squad sometimes designs manual analysis protocols instead of v3 strategies. Added version gate in loop_runner + nudge to squad.

## Remaining: 5-cycle long validation (deferred)
The 5-cycle long validation (6-year training windows) proves compounding — that cycle 5 builds on cycles 1-4. This can run in a separate session after merge. The short validation already proves the loop mechanism works end-to-end.

## How to Run Long Validation
```bash
# Reset iteration count first
echo "0" > ~/.ktrdr/shared/squad/loop/iteration-count.txt
# Set cadence to full_squad
cat > ~/.ktrdr/shared/squad/loop/cadence.md << 'EOF'
# Cadence
cadence: full_squad
reason: Long validation run — 5 cycles with 6-year training windows
updated: <timestamp>
EOF
# Run
nohup .squad/loop_runner.sh --max-cycles 5 > logs/squad/long_validation.log 2>&1 &
```
