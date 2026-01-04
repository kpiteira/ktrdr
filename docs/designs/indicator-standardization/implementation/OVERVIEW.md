# Indicator Standardization: Implementation Plan

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md)
- **Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Scenarios:** [../SCENARIOS.md](../SCENARIOS.md)

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | Add Interface | 4 | v2 smoke test (no behavior change) | ⏳ |
| M2 | IndicatorEngine Adapter | 3 | v2 smoke test (adapter handles both formats) | ⏳ |
| M3a | Migrate Single-Output | 3 | v2 smoke test (columns now use feature_id) | ⏳ |
| M3b | Migrate Multi-Output | 3 | v2 smoke test (columns now use indicator_id.output) | ⏳ |
| M4 | Update Consumers | 4 | v2 smoke test (full E2E training works) | ⏳ |
| M5 | v3 Ready Checkpoint | 1 | All tests pass, ready for v3 Grammar | ⏳ |
| M6 | Cleanup | 3 | No v2 compatibility code remains | ⏳ DEFERRED |

**Total:** 21 tasks across 7 milestones

## Dependency Graph

```
M1 (Interface)
    ↓
M2 (Adapter) ──────────────────┐
    ↓                          │
M3a (Single-Output) ───────────┤
    ↓                          │
M3b (Multi-Output) ────────────┤
    ↓                          │
M4 (Consumers) ────────────────┤
    ↓                          │
M5 (v3 Ready) ─────────────────┘
    ↓
[Strategy Grammar v3 development happens here]
    ↓
M6 (Cleanup) ← Only after v3 complete
```

## v2 Smoke Test (Run at Every Milestone)

**Strategy:** `strategies/rsi_mean_reversion.yaml`

This strategy uses:
- Single-output: RSI
- Multi-output: MACD

**Why both training AND backtesting:**

| Stage | What Could Break | Training Catches? | Backtest Catches? |
|-------|------------------|-------------------|-------------------|
| Indicator computation | Wrong column names | ✅ | ✅ |
| FeatureCache lookup | Column not found | ✅ | ✅ |
| FuzzyEngine | Indicator reference fails | ✅ | ✅ |
| Model metadata | Feature names saved wrong | ❌ | ✅ |
| Model loading | Feature names don't match | ❌ | ✅ |
| Backtest indicator computation | Different code path | ❌ | ✅ |

**Test commands:**

```bash
# 1. Validate strategy (quick sanity check)
uv run ktrdr strategies validate strategies/mean_reversion_momentum_v1.yaml

# 2. Train model (2 months of 1h data)
uv run ktrdr models train strategies/mean_reversion_momentum_v1.yaml EURUSD 1h \
    --start-date 2024-01-01 \
    --end-date 2024-03-01

# 3. Backtest trained model (1 month of data)
uv run ktrdr backtest run mean_reversion_momentum_v1 EURUSD 1h \
    --start-date 2024-03-01 \
    --end-date 2024-04-01
```

**Duration:** ~60-90 seconds total

**Note:** Uses `mean_reversion_momentum_v1.yaml` which validates successfully (unlike `rsi_mean_reversion.yaml` which has missing fuzzy_sets for MACD).

**The smoke test must pass at every milestone (M1-M5).**

## Architecture Alignment

Every task traces back to these architectural decisions:

| Pattern | Description | Implementing Tasks |
|---------|-------------|-------------------|
| Semantic Output Names | Indicators return `upper`, `signal`, not `upper_20_2.0` | M3a.*, M3b.* |
| Caller-Owned Naming | IndicatorEngine prefixes with indicator_id | M2.1, M2.2 |
| Format Detection | Column matching determines old vs new format | M2.2 |
| Primary Output Alias | Bare `indicator_id` resolves to primary output | M2.2 |
| v2 Compatibility | Adapter handles both formats during transition | M2.*, M4.* |

## Risk Areas

| Milestone | Risk | Mitigation |
|-----------|------|------------|
| M2 | Format detection logic complexity | Thorough unit tests for both paths |
| M3b | Multi-output indicators have varied patterns | Migrate one (BollingerBands) first as template |
| M4 | Consumer changes could break v2 | Run smoke test after each consumer update |

## Files Changed Summary

### Core Infrastructure
- `ktrdr/indicators/base_indicator.py` — M1
- `ktrdr/indicators/indicator_engine.py` — M2
- `ktrdr/indicators/indicator_factory.py` — M2 (minor)

### Single-Output Indicators (M3a)
18 files: RSI, ATR, CCI, CMF, MFI, OBV, ROC, Momentum, Williams %R, RVI, VWAP, Volume Ratio, Distance from MA, BB Width, Squeeze Intensity, Parabolic SAR, ZigZag, AD Line, SMA, EMA

### Multi-Output Indicators (M3b)
10 files: BollingerBands, MACD, Stochastic, ADX, Aroon, Ichimoku, Supertrend, Donchian, Keltner, Fisher

### Consumers (M4)
- `ktrdr/fuzzy/engine.py`
- `ktrdr/backtesting/feature_cache.py`
- `ktrdr/training/training_pipeline.py`
- `ktrdr/training/fuzzy_neural_processor.py`

### Cleanup (M6 - DEFERRED)
- Delete `ktrdr/indicators/column_standardization.py`
- Remove compatibility code marked with `# CLEANUP(v3)`
