---
design: docs/designs/backtesting-pipeline-refactor/DESIGN.md
architecture: docs/designs/backtesting-pipeline-refactor/ARCHITECTURE.md
---

# Backtesting Pipeline Refactor: Implementation Overview

## Why This Refactor Exists

A research agent designed a multi-timeframe strategy, trained it on Apple Silicon (MPS), and the **backtest failed**:

```
torch.UntypedStorage(): Storage device not recognized: mps
```

Root cause: `ktrdr/neural/models/base_model.py:343` calls `torch.load()` without `map_location="cpu"`. CPU-only Docker workers can't deserialize MPS-trained tensors.

But this one-line bug exposed a deeper architecture problem: the model is loaded **three times** through three different code paths during backtest init, and only one has `map_location="cpu"`. The architecture makes bugs like this inevitable. A full review found 8 major structural issues (see DESIGN.md).

## Ultimate E2E Test

**When all 4 milestones are complete, this is the test that proves the refactor works:**

```bash
uv run ktrdr research -m haiku -f "Design a multi-timeframe strategy using RSI and Bollinger Bands on 1h and 5m data for EURUSD"
```

This triggers a full agent research cycle:
1. Agent **designs** a multi-timeframe v3 strategy
2. Agent **trains** it (on MPS — model saved with MPS device tensors)
3. Agent **backtests** it on a CPU-only Docker worker — **this is where the original bug was**
4. Agent **assesses** the results

If backtesting completes and produces valid metrics, the refactor is proven. This is the same command pattern that originally triggered the bug.

## Branch

`refactor/backtesting-pipeline`

(Create from `codex/host-service-startup-and-errors` which has the multi-TF backtesting fix and model path fixes already committed.)

## Milestone Summary

| Milestone | Name | Tasks | Gate |
|-----------|------|-------|------|
| M1 | ModelBundle + map_location fix | 5 | ModelBundle loads MPS-trained model in CPU-only Docker container |
| M2 | DecisionFunction | 3 | Unit tests prove identical decision outputs vs current DecisionEngine |
| M3 | Engine rewrite | 5 | Backtest produces equivalent metrics to current engine for known strategy |
| M4 | Worker consolidation + cleanup | 4 | Full research cycle completes training + backtesting; checkpoint resume works |

**Total: 17 tasks**

## Dependency Graph

```
M1 (ModelBundle)
  │
  ▼
M2 (DecisionFunction)
  │
  ▼
M3 (Engine rewrite) ← integrates M1 + M2
  │
  ▼
M4 (Cleanup + consolidation)
```

Linear dependency: each milestone builds on the previous one. No parallelization between milestones.

Within each milestone, tasks are sequential unless noted otherwise.

## Core Architectural Decisions (from ARCHITECTURE.md)

These decisions constrain every task:

1. **Single model load** — `ModelBundle.load()` is the ONLY model loading path for backtesting. No task may introduce a second `torch.load` call.
2. **Stateless decisions** — `DecisionFunction` receives position as input. No task may add position state to the decision layer.
3. **Pipeline ownership** — `BacktestingEngine` wires components. No god-object orchestrator.
4. **Preserve, don't delete** — `DecisionOrchestrator` and `DecisionEngine` stay. No task may delete them. Tasks must add documentation explaining the decoupling.
5. **state dict only** — Backtesting loads `model.pt` with `weights_only=True`. No task may load `model_full.pt`.

## Testing Strategy

- **Unit tests** for each new component (`ModelBundle`, `DecisionFunction`)
- **Regression test** comparing old vs new engine output for `mean_reversion_momentum_v1` strategy
- **Fast container test** for MPS portability (2 seconds, not 10-minute research cycle)
- **All existing `tests/unit/backtesting/` tests** must pass (adapted for new interfaces)
- **E2E at M4** via research cycle

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Checkpoint format change breaks resume | Medium | High | M3 task explicitly adapts checkpoint builder/restore and tests round-trip |
| DecisionFunction filters differ from DecisionEngine | Low | High | M2 includes direct comparison test fixture |
| FeatureCache interface change needed | Low | Medium | FeatureCache internals unchanged; only call sites change |
| model_full.pt fallback needed | Low | Low | Files still saved; can re-add load path if needed |
