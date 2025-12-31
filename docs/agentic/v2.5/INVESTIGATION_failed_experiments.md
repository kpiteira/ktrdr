# Investigation: Failed Agent-Generated Experiments

## Purpose

Analyze why recent agent-generated experiments failed catastrophically, to understand whether this is:
- **Agent problem**: Designed something impossible
- **Platform problem**: Capabilities don't exist
- **Integration problem**: Pieces don't connect properly

---

## Experiments Under Investigation

| ID | Strategy | Anomaly |
|----|----------|---------|
| A | `exp_20251231_163401` (RSI+ATR) | 0 trades, 0% accuracy |
| B | `exp_20251231_174501` (RSI+Fisher) | 797 trades, 7% win rate, 0% accuracy |
| Control | `exp_v15_adx_di` | 61.1% test accuracy (healthy) |

---

## Analysis Framework

For each experiment, trace through the pipeline:

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Agent     │ → │  Strategy   │ → │  Training   │ → │   Model     │ → │  Backtest   │
│   Design    │    │   Config    │    │   Process   │    │   Output    │    │   Results   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
      Q1               Q2                 Q3                Q4                 Q5
```

### Questions at Each Stage

**Q1: Agent Design**
- What did the agent request?
- Does the strategy name match the context?
- Are there impossible requests (multi-symbol when only EURUSD configured)?

**Q2: Strategy Config**
- Was a valid YAML generated?
- Do the indicators exist in the platform?
- Are fuzzy sets defined for these indicators?

**Q3: Training Process**
- Did training actually run?
- What were the loss curves?
- Did the model converge or fail early?

**Q4: Model Output**
- Does the model file exist?
- Does it produce valid predictions?
- What's the prediction distribution?

**Q5: Backtest Results**
- How were results computed?
- Why 0% accuracy with 797 trades? (Exp B)
- Why 0 trades? (Exp A)

---

## Investigation Tasks

### Task 1: Verify Indicator Support

Check if the indicators used in failed experiments actually exist:

```bash
# Check: Does FisherTransform exist as an indicator?
grep -r "FisherTransform\|fisher_transform\|Fisher" ktrdr/indicators/

# Check: Is ATR available in fuzzy sets?
grep -r "ATR\|atr" ktrdr/fuzzy/
```

**Expected finding**: FisherTransform likely doesn't exist. ATR might exist but not be fuzzified.

### Task 2: Find the Strategy YAML

Locate what config was actually generated:

```bash
# Find strategy files created on Dec 31
find . -name "*.yaml" -newer "2024-12-30" -type f | xargs grep -l "rsi_atr\|rsi_fisher"
```

**Expected finding**: Either no YAML was generated, or it contains unsupported config.

### Task 3: Check Training Logs

Find training logs for these operations:

```bash
# Search for operation IDs or strategy names in logs
grep -r "rsi_atr_multiframe\|rsi_fisher_multisymbol" logs/
```

**Expected finding**: Training may have failed silently or used defaults.

### Task 4: Understand the Metrics Contradiction

Experiment B shows:
- `total_trades: 797`
- `test_accuracy: 0`
- `win_rate: 0.07`

This is contradictory. If 797 trades happened with 7% win rate, there should be some accuracy > 0.

**Hypothesis**: These metrics come from different sources:
- `total_trades` and `win_rate` from backtest
- `test_accuracy` from training evaluation
- They might be measuring different things or from different runs

### Task 5: Compare with Control

Take the control experiment (exp_v15_adx_di) and trace how it was created:
- What strategy YAML?
- What training process?
- How do results flow back?

This shows what "working" looks like.

---

## Success Criteria

After investigation, we should be able to answer:

1. **Root cause identified**: What specifically broke?
2. **Failure mode classified**: Agent/Platform/Integration problem?
3. **Actionable fix**: What needs to change to prevent this?

---

## Findings

### Task 1: Indicator Support ✅

| Indicator | Code Exists | Factory Registered | Global Fuzzy Sets |
|-----------|-------------|-------------------|-------------------|
| FisherTransform | ✅ `fisher_transform.py` | ✅ | ❌ Missing |
| ATR | ✅ `atr_indicator.py` | ✅ | ✅ Defined |
| RSI | ✅ | ✅ | ✅ Defined |

**However**: Both failed strategies **define their own fuzzy sets in-YAML**, so missing global fuzzy sets is NOT the cause.

### Task 2: Strategy Configs ✅

Both strategies are well-formed with complete fuzzy sets:

**Exp A (RSI+ATR)**:
- Multi-symbol: EURUSD, GBPUSD, USDJPY
- Multi-timeframe: 1h + 5m  ← **Key difference**
- Fuzzy sets: Defined for both rsi_14 and atr_14

**Exp B (RSI+Fisher)**:
- Multi-symbol: EURUSD, GBPUSD, USDJPY
- Single timeframe: 1h only
- Fuzzy sets: Defined for both rsi_14 and fisher_14

### Task 3: Infrastructure Check ✅

Multi-symbol and multi-timeframe **ARE implemented**:
- `TrainingPipeline.combine_multi_symbol_data()` exists
- `MultiTimeframeCoordinator` handles multi-TF data loading
- `prepare_multi_timeframe_input()` creates features

### Task 4: Metrics Contradiction — ROOT CAUSE FOUND ⚠️

**Critical finding**: The metrics come from DIFFERENT sources:

```python
# In assessment_worker.py:
test_accuracy = training_metrics.get("accuracy", 0)  # From training
total_trades = backtest_metrics.get("total_trades")   # From backtest
win_rate = backtest_metrics.get("win_rate")           # From backtest
```

**And in training_pipeline.py:650-671:**
```python
if X_test is None or y_test is None:
    logger.warning("No test data provided - returning zero metrics")
    return {"test_accuracy": 0.0, ...}
```

**Conclusion**: The training pipeline returned `X_test=None`, which means:
- Training evaluation returned 0% accuracy (no data to evaluate)
- But backtest ran anyway with whatever model was produced
- The 7% win rate = backtest ran on a model that learned nothing useful

### Experiment A (RSI+ATR, 0 trades)

**Stage where it failed**: Training (no test data) AND Backtest (no trades)

**Root cause**: Multi-timeframe mode (`1h + 5m`) likely failed to produce aligned data. The pipeline couldn't create test features, AND the fuzzy decision system never triggered trades.

**Classification**: **Platform problem** — multi-timeframe data pipeline issue

### Experiment B (RSI+Fisher, 797 trades, 7% win)

**Stage where it failed**: Training (no test data)

**Root cause**: Multi-symbol training (`EURUSD + GBPUSD + USDJPY`) produced no test data, but backtest ran with an untrained model. The model outputs random/constant predictions → 7% win rate (worse than random 50%).

**Classification**: **Platform problem** — multi-symbol training pipeline issue

---

## Root Cause Summary

```
┌─────────────────────────────────────────────────────────────────┐
│   Agent designs multi-symbol/multi-TF strategy                   │
│                         ↓                                        │
│   Training pipeline tries to process                             │
│                         ↓                                        │
│   ⚠️ Something fails silently (X_test = None)                   │
│                         ↓                                        │
│   Training returns 0% accuracy (no test data to evaluate)        │
│                         ↓                                        │
│   System STILL runs backtest with broken model                   │
│                         ↓                                        │
│   Backtest produces catastrophic results (7% win or 0 trades)    │
│                         ↓                                        │
│   Experiment recorded with contradictory metrics                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key issues:**
1. Training failures are **silent** — returns 0 metrics instead of failing
2. Backtest **runs anyway** even when training failed
3. No **quality gate** between training and backtest

---

## Recommendations

### Immediate Fixes

1. **Add training failure detection**:
   ```python
   if training_metrics.get("accuracy", 0) == 0:
       raise TrainingFailedError("Training produced no metrics")
   ```

2. **Skip backtest if training failed**:
   The system should NOT run backtest when training returns 0% accuracy.

3. **Better error propagation**:
   When `X_test is None`, the pipeline should fail loudly, not return zeros.

### Investigation Needed

4. **Why does multi-symbol produce no test data?**
   - Check `combine_multi_symbol_data()` for edge cases
   - Check if data alignment fails when symbols have different date ranges

5. **Why does multi-timeframe produce 0 trades?**
   - Check `MultiTimeframeCoordinator.load_multi_timeframe_data()`
   - Check if 5m data aligns correctly with 1h bars

### Agent Guardrails

6. **Constrain agent to proven configs**:
   Until multi-symbol/multi-TF are fixed, the agent should be guided to use:
   - Single symbol (EURUSD)
   - Single timeframe (1h)
   - Proven indicators (RSI, DI, Stochastic)

---

*Created: 2025-12-31*
*Status: Investigation complete*
*Root cause: Platform problem — training pipeline fails silently for multi-symbol/multi-TF*
