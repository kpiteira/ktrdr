# ktrdr Autonomous Options Trading System — Implementation Plan

> **Author**: Claude (Opus 4.6), commissioned by Karl Piteira
> **Date**: 2026-04-18
> **Status**: Ready for review
> **Based on**: DESIGN.md (approved), ARCHITECTURE.md (approved)

---

## Executive Summary

This plan implements the ktrdr Autonomous Options Trading System across 5 milestones using a **backtest-first** approach. The system overlays options strategy selection on top of ktrdr's existing directional signals, using Kronos-mini embeddings for volatility regime classification and Opus 4.7 as a live-trading advisor.

The sequence is non-negotiable:

1. **M1 — Kronos Vol Regime Classifier** (8 dev-days): Prove that frozen Kronos-mini embeddings encode vol-relevant information. AUC > 0.60 gate.
2. **M2 — Black-Scholes Engine + Data Infrastructure** (7 dev-days): Build the synthetic options pricing engine and all supporting data infrastructure.
3. **M3 — Full Synthetic Backtest Loop** (12 dev-days): Wire everything together — ktrdr signals + Kronos + B-S + decision matrix + position management. Sharpe > 0.50 gate.
4. **M4 — Live/Paper Infrastructure** (10 dev-days): Build the live analysis pipeline — ktrdr HTTP client, Opus 4.7 advisor, LuxOrchestrator.
5. **M5 — IBKR Execution + Paper Trading** (8 dev-days): Close the loop with IBKR, run 60-day paper trading. Sharpe > 0.40 gate.

**Total estimated effort: 45 developer-days.**

No milestone may begin until its predecessor's go/no-go gate is passed. No live trading occurs until synthetic and paper trading are validated.

---

## Dependency Graph

```
M1: Kronos Vol Regime Classifier
│
│  Gate: AUC > 0.60
│
├──> M2: Black-Scholes + Data Infrastructure
│    │
│    │  Gate: B-S prices match textbook references within 1%
│    │        Put-call parity holds within numerical tolerance
│    │
│    └──> M3: Full Synthetic Backtest Loop
│         │
│         │  Gate: Sharpe > 0.50, >= 50 trades, max DD < 25%
│         │
│         └──> M4: Live/Paper Infrastructure
│              │
│              │  Gate: Full cycle < 90s, SQLite writes, Telegram fires
│              │        Opus fallback works
│              │
│              └──> M5: IBKR Execution + Paper Trading
│                   │
│                   │  Gate: Live Sharpe > 0.40, >= 30 trades, 60+ days
│                   │
│                   └──> PRODUCTION
```

### Cross-Milestone Dependencies

| Downstream | Requires From Upstream | Details |
|-----------|----------------------|---------|
| M2 | M1 | `KronosVolClassifier` class and trained classifier weights |
| M3 | M1 | Pre-computed Kronos embeddings cache (`.pt` files) |
| M3 | M2 | `BlackScholesEngine`, `OptionsDataProvider` (VIX history, risk-free rate) |
| M3 | ktrdr repo | ktrdr installed as Python package (library imports) |
| M4 | M3 | `OptionsDecisionMatrix`, `OptionsPositionManager`, `SignalAggregator` (reused) |
| M4 | ktrdr repo | ktrdr API extended with `probabilities` field (~10 lines) |
| M5 | M4 | Full `LuxOrchestrator`, all components integrated |
| M5 | IBKR MCP | Multi-leg options order support — `[DECISION NEEDED]` |

---

## Go/No-Go Gates

| Gate | Milestone Exit | Criteria | Fallback if Gate Fails |
|------|---------------|----------|----------------------|
| **G1** | M1 → M2 | AUC > 0.60 on held-out test set (2023 data) | Try mean pooling, Kronos-small (512d), adjust label thresholds. If still < 0.55: replace with IV rank heuristic. |
| **G2** | M2 → M3 | B-S prices match CBOE/textbook within 1%. Put-call parity holds. Greeks signs correct. | Fix implementation bugs. This is pure math — it must pass. |
| **G3** | M3 → M4 | Sharpe > 0.50 AND >= 50 trades AND max drawdown < 25% on 2022-2024 SPY | Tune confidence thresholds, adjust structure selection, review exit conditions. Sweep DTE, take-profit, stop-loss parameters. |
| **G4** | M4 → M5 | Full analysis cycle < 90s. SQLite records written. Telegram fires. Matrix fallback works when Opus mocked to fail. | Debug cycle bottlenecks. Usually Opus latency — increase timeout or optimize prompt. |
| **G5** | M5 → PROD | Live Sharpe > 0.40 over 60+ days AND >= 30 paper trades | Review signal thresholds, adjust exit rules, investigate signal degradation via calibration table. |

---

## Risk Register

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| **R1** | Kronos embeddings do not encode vol information (AUC < 0.55) | Medium | **Critical** — blocks entire system value proposition | IV rank heuristic fallback is pre-built (Design Sec. 3). System still functions, just without ML-enhanced vol classification. Try mean pooling, Kronos-small, adjusted labels before abandoning. |
| **R2** | Black-Scholes synthetic backtest overfits — real-world performance degrades | Medium | High — false confidence from backtest | 10% bid/ask haircut is conservative. Paper trading (M5) is the true validation. Do NOT increase capital allocation based on synthetic Sharpe alone. |
| **R3** | IBKR MCP does not support multi-leg options orders (BAG orders) | Medium | Medium — forces sequential leg execution with slippage risk | Validate before M5 starts. If unsupported: implement as sequential legs, add slippage tracking, widen haircut for live mode. |
| **R4** | ktrdr signal accuracy degrades during paper trading period | Low-Medium | Medium — system opens losing trades | Calibration table (M5) monitors rolling accuracy. Alert fires if ktrdr win rate drops > 20% from backtest baseline. Pause new trades on alert. |
| **R5** | Opus 4.7 API latency or availability during market hours | Low | Low — matrix fallback handles this seamlessly | Matrix fallback is deterministic and tested in M3. `TradeRecommendation.source="matrix"` tracks fallback frequency. If > 30% fallback rate, investigate. |

---

## ktrdr Changes Required

**File**: `ktrdr/api/endpoints/models.py`
**Change**: Extend `Prediction` model to include `probabilities` field.

```python
# In Prediction model (line ~200):
class Prediction(BaseModel):
    signal: str
    confidence: float
    signal_strength: float
    probabilities: dict[str, float] | None = None  # NEW

# In prediction endpoint handler (line ~225):
# After obtaining TradingDecision:
probabilities = trading_decision.reasoning.get("nn_probabilities")
prediction = Prediction(
    signal=trading_decision.signal.value,
    confidence=trading_decision.confidence,
    signal_strength=trading_decision.signal_strength,
    probabilities=probabilities,  # NEW
)
```

**Estimated change**: ~5-10 lines. Backward-compatible (field is optional with `None` default).
**When needed**: M4 (live/paper mode). NOT needed for M1-M3 (backtest uses library imports, not REST).

---

## Package Structure

```
ktrdr-options/
├── pyproject.toml                          # Package config, dependencies
├── ktrdr-options-config.yaml               # Default configuration
├── README.md
│
├── ktrdr_options/
│   ├── __init__.py
│   ├── __main__.py                         # CLI entry point
│   │
│   ├── signals/
│   │   ├── __init__.py
│   │   ├── kronos_classifier.py            # KronosVolClassifier, VolRegimeSignal
│   │   ├── ktrdr_client.py                 # KtrdrSignalClient, KtrdrSignal
│   │   └── aggregator.py                   # SignalAggregator, DecisionInput
│   │
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── decision_matrix.py              # OptionsDecisionMatrix, StructureType, StructureChoice
│   │   └── opus_advisor.py                 # OpusStrategyAdvisor, TradeRecommendation, ExitPlan
│   │
│   ├── backtest/
│   │   ├── __init__.py
│   │   ├── black_scholes.py                # BlackScholesEngine, OptionPrice
│   │   └── engine.py                       # OptionsBacktestEngine, OptionsBacktestConfig, Results
│   │
│   ├── positions/
│   │   ├── __init__.py
│   │   ├── position.py                     # OptionsPosition, OptionsLeg, PositionStatus
│   │   └── manager.py                      # OptionsPositionManager
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   └── options_data.py                 # OptionsDataProvider, OptionsChain, IVData, OptionContract
│   │
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── schema.py                       # SQLite schema creation, migration
│   │
│   ├── orchestrator.py                     # LuxOrchestrator, CycleResult
│   │
│   ├── train_classifier.py                 # CLI: train Kronos vol regime classifier
│   └── backtest_cli.py                     # CLI: run synthetic backtest
│
├── tests/
│   ├── __init__.py
│   ├── test_kronos_classifier.py
│   ├── test_black_scholes.py
│   ├── test_decision_matrix.py
│   ├── test_position_manager.py
│   ├── test_backtest_engine.py
│   ├── test_ktrdr_client.py
│   ├── test_opus_advisor.py
│   ├── test_signal_aggregator.py
│   ├── test_options_data.py
│   └── test_orchestrator.py
│
├── cache/                                  # Runtime caches (gitignored)
│   ├── kronos/                             # Pre-computed embeddings
│   └── vix_daily.csv                       # Cached VIX history
│
├── models/                                 # Trained model weights (gitignored)
│   └── kronos_classifier/
│       ├── SPY_head.pt                     # Trained classifier head
│       └── config.json                     # Classifier config
│
└── logs/                                   # Runtime logs (gitignored)
    └── ktrdr_options.log
```

---

## Milestone Summary

| Milestone | Effort | Key Deliverable | Gate |
|-----------|--------|----------------|------|
| M1: Kronos Vol Regime Classifier | 8 days | Trained classifier, AUC report | AUC > 0.60 |
| M2: Black-Scholes + Data | 7 days | Pricing engine, data providers | B-S validation |
| M3: Full Backtest Loop | 12 days | End-to-end backtest, trade log | Sharpe > 0.50 |
| M4: Live/Paper Infrastructure | 10 days | Opus advisor, orchestrator | Cycle < 90s |
| M5: IBKR + Paper Trading | 8 days | 60-day paper trading results | Sharpe > 0.40 |
| **Total** | **45 days** | | |

---

## Open Decisions Requiring Karl's Input

1. **`[DECISION NEEDED]` Symbols**: SPY first. Which single-name stock second?
2. **`[DECISION NEEDED]` Historical options data budget**: $0 (B-S reconstruction), ~$200 (OptionsDX), or $1000+ (CBOE)?
3. **`[DECISION NEEDED]` ktrdr API extension**: Extend `/predict` to return `probabilities` (~10 lines). Recommended over library-direct approach.
4. **`[DECISION NEEDED]` Live trading approval gate**: All live trades require Telegram approval initially?
5. **`[DECISION NEEDED]` IBKR MCP options capabilities**: Does the existing integration support multi-leg combo (BAG) orders?
6. **`[DECISION NEEDED]` Max risk per trade**: 2% default — adjust?
