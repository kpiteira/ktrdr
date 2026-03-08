# Predictive Features: Implementation Plan

## Status: Plan
## Date: 2026-03-08

---

## Summary

Three threads composing the "adult brain" architecture — regime detection, multi-timeframe context, and external data sources — planned as 10 unified milestones with explicit dependencies and parallelism.

**Critical path:** M2 → M4 → M7 (regime labeling → classifier → ensemble backtest)

---

## Thread-Level JTBDs

These are the end-state user scenarios. Each must be E2E-verifiable at the listed milestone.

| Thread | JTBD | Verified At |
|--------|------|-------------|
| **Regime Detection** | "As a trader, I want the system to detect market regime and route to specialized strategies so I get better risk-adjusted returns than a single unrouted model." | M7 |
| **Multi-TF Context** | "As a trader, I want daily trend context to adjust trading aggressiveness so I trade with the macro trend, not against it." | M8 |
| **External Data** | "As a researcher, I want to train and backtest strategies using interest rate differentials, cross-pair context, and positioning data." | M9 |

---

## Milestones

| # | Name | Thread | Tasks | JTBD | Depends On |
|---|------|--------|-------|------|------------|
| M1 | Multi-TF Backtest Fix | Context (prereq) | 4 | Train multi-TF strategy and backtest end-to-end | — |
| M2 | Regime Labeling & Analysis | Regime | 5 | Analyze whether meaningful market regimes exist | — |
| M3 | Context Labeling & Analysis | Context | 5 | Analyze whether daily trend context adds value | — |
| M4 | Regime Classifier | Regime | 5 | Train regime classifier that beats random baseline | M2 |
| M5 | Context Classifier | Context | 5 | Train context classifier that beats random baseline | M3 |
| M6 | External Data: FRED Training | External | 7 | Train model using FRED yield spread data | — |
| M7 | Ensemble + Regime Backtest | Regime | 7 | Run regime-routed ensemble backtest with per-regime models | M4 |
| M8 | Multi-Gate Context Integration | Context | 5 | Add context gating to ensemble, compare vs regime-only | M7, M5 |
| M9 | External Data: Backtest + CFTC | External | 6 | Backtest strategies with external data (FRED, cross-pair, CFTC) | M6 |
| M10 | Agent Integration | All | 5 | Researcher generates ensemble configs and evaluates regime routing | M7, M8 |

**Total: 54 tasks across 10 milestones**

---

## Dependency Graph

```
Wave 1 (all parallel — no dependencies):
  M1  Multi-TF Backtest Fix
  M2  Regime Labeling
  M3  Context Labeling
  M6  External Data + FRED Training

Wave 2 (after respective labeler):
  M4  Regime Classifier          ← M2
  M5  Context Classifier         ← M3
                                          M9  External Backtest + CFTC  ← M6

Wave 3:
  M7  Ensemble + Regime Backtest ← M4

Wave 4:
  M8  Context Gate               ← M7 + M5

Wave 5:
  M10 Agent Integration          ← M7 + M8
```

```
M1 ─────────────────────────────────────────────────────────────────────┐
                                                                        │
M2 ──→ M4 ──→ M7 (Ensemble + Regime Backtest) ──→ M8 (Context Gate) ──→ M10 (Agent)
                                                    ↑
M3 ──→ M5 ─────────────────────────────────────────┘

M6 ──→ M9 (External Backtest + CFTC)
```

**M1** (multi-TF fix) is independent — the critical path doesn't depend on it because regime/context/ensemble models are single-TF. M1 is needed before the Researcher designs multi-TF strategies (M10).

---

## Parallel Execution Lanes

Maximum 4 parallel worktrees in Wave 1, then 2-3 in subsequent waves.

```
Lane A (Regime):     M2 ──→ M4 ──→ M7 ──→ M8 ──→ M10
Lane B (Context):    M3 ──→ M5 ─────────↗
Lane C (External):   M6 ──→ M9
Lane D (Prereq):     M1
```

---

## Branch Strategy

Each milestone gets its own `impl/` worktree:
- `impl/predictive-M1` through `impl/predictive-M10`
- Merge to main after each milestone's validation passes
- Wave 1 milestones can run as 4 parallel worktrees

---

## Shared Infrastructure

These items are built once but used by multiple milestones. Each is assigned to the earliest milestone that needs it.

| Infrastructure | Built In | Used By |
|---|---|---|
| `ModelMetadata.output_type` field | M4 | M4, M5, M7, M8 |
| `labels.source: regime` (both pipelines!) | M4 | M4, M7 |
| `labels.source: context` (both pipelines!) | M5 | M5, M8 |
| DecisionFunction N-class generalization | M7 | M7, M8 |
| `context_data` grammar + `data_source` field | M6 | M6, M9 |
| EnsembleConfig + Runner + Router | M7 | M7, M8, M9, M10 |
| Backtest multi-TF `timeframes: list[str]` | M1 | M1, M10 |

---

## Design Documents

All design docs live under `docs/designs/predictive-features/`:

```
predictive-features/
  INTENT.md                              — Problem statement + 3 threads
  regime-detection/
    DESIGN.md                            — Regime detection design
    ARCHITECTURE.md                      — Regime detection architecture
  multi-timeframe-context/
    DESIGN.md                            — Multi-TF context design
    ARCHITECTURE.md                      — Multi-TF context architecture
  external-data/
    DESIGN.md                            — External data design
    ARCHITECTURE.md                      — External data architecture
  implementation/
    OVERVIEW.md                          — This file
    M1_multi_tf_backtest_fix.md
    M2_regime_labeling.md
    M3_context_labeling.md
    M4_regime_classifier.md
    M5_context_classifier.md
    M6_external_data_fred.md
    M7_ensemble_regime_backtest.md
    M8_context_gate.md
    M9_external_data_backtest.md
    M10_agent_integration.md
```

---

## Key Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Regime labels show no persistence (<24h average) | Thread 1 hypothesis falsified | M2 is a validation gate — stop if regimes aren't meaningful |
| Context labels show no differentiation | Thread 2 hypothesis falsified | M3 is a validation gate — stop if context doesn't add value |
| DecisionFunction N-class generalization breaks existing 3-class | Regression in existing backtests | M7 adds N-class; existing tests must still pass |
| Host service label dispatch missed (again) | Models train as wrong type | Explicit dual-dispatch warning in M4 and M5 task descriptions |
| FRED API key not configured | M6 fails at data fetch | M6 task 1 includes env var setup and validation |
| Ensemble backtest too slow (N models × bars) | M7 validation slow | Profile in M7; FeatureCache pre-computation helps |
