# Plan: Agent Research Cycle Reliability

## Overview

Following our investigation of failed experiments (`exp_20251231_163401` and `exp_20251231_174501`), this plan addresses the root causes and proposes fixes to make the agent research cycle more reliable.

**Related document**: [INVESTIGATION_failed_experiments.md](INVESTIGATION_failed_experiments.md)

---

## Problem Summary

The agent designed multi-symbol and multi-timeframe strategies that produced catastrophic results:
- 0% test accuracy
- 7% win rate (worse than random)
- 0 trades

These failures went undetected because **quality gates were bypassed** during testing, and even with gates enabled, **the loss decrease threshold (20%) was too strict** for exploration.

---

## Root Causes

### 1. Quality Gates Bypassed
The experiments were triggered with `bypass_gates=True`, disabling all quality checks.

**Evidence**:
```
Training gate bypassed: op_agent_research_20251231_174222_9363b14e
Backtest gate bypassed: op_agent_research_20251231_161606_7831e261
```

### 2. Loss Decrease Threshold Too Strict
Current gate requires 20% loss decrease to pass. Early experiments exploring new indicator combinations may show 5-15% improvement and still be worth evaluating.

**Current thresholds** (in [gates.py](../../../ktrdr/agents/gates.py)):
```python
min_accuracy: float = 0.45      # 45% - reasonable
max_loss: float = 0.8           # reasonable
min_loss_decrease: float = 0.2  # 20% - TOO STRICT for exploration
```

### 3. Silent Training Failures
When training produces no test data (`X_test = None`), it returns zeros instead of failing loudly:
```python
if X_test is None or y_test is None:
    logger.warning("No test data provided - returning zero metrics")
    return {"test_accuracy": 0.0, ...}  # Silent failure
```

### 4. Multi-Symbol/Multi-Timeframe Issues (needs investigation)
The infrastructure exists but may have edge cases:
- `combine_multi_symbol_data()` — may fail with different date ranges
- `MultiTimeframeCoordinator` — 5m/1h alignment may fail

---

## Proposed Fixes

### Phase 1: Quick Wins (Gate Tuning)

#### 1.1 Adjust Loss Decrease Threshold
**File**: `ktrdr/agents/gates.py`

Change:
```python
min_loss_decrease: float = 0.2  # Current: 20%
```
To:
```python
min_loss_decrease: float = 0.0  # Allow any improvement (just don't get worse)
```

**Rationale**: For exploration, we want to allow experiments that show any learning. The accuracy threshold (45%) already catches truly broken training. The loss decrease check should only catch regressions (loss got worse).

#### 1.2 Re-enable Gates by Default
Stop using `bypass_gates=True` for production experiments. The bypass flag should only be used for debugging.

**Action**: Update any scripts/docs that recommend bypassing gates.

#### 1.3 Add Catastrophic Failure Check
Add an explicit check for completely broken training (0% accuracy, 0 trades):

**File**: `ktrdr/agents/gates.py`

```python
# Add at the start of check_training_gate():
if accuracy == 0.0:
    return False, "training_completely_failed (0% accuracy)"
```

This catches cases where training returned zero metrics due to silent failures.

---

### Phase 2: Better Error Propagation

#### 2.1 Fail Loudly on Missing Test Data
**File**: `ktrdr/training/training_pipeline.py`

Change:
```python
if X_test is None or y_test is None:
    logger.warning("No test data provided - returning zero metrics")
    return {"test_accuracy": 0.0, ...}
```
To:
```python
if X_test is None or y_test is None:
    raise TrainingDataError("Training produced no test data - check data pipeline")
```

**Rationale**: Silent failures hide bugs. If training can't produce test data, that's an error worth investigating, not a "zero accuracy" result.

#### 2.2 Add Data Validation Before Training
**File**: `ktrdr/training/training_pipeline.py`

Add checks after data combination:
```python
combined_features, combined_labels = TrainingPipeline.combine_multi_symbol_data(...)

# Validate combined data
if len(combined_features) == 0:
    raise TrainingDataError(f"No samples after combining {len(symbols)} symbols")

if len(combined_features) < 100:  # Minimum viable training set
    raise TrainingDataError(f"Insufficient samples ({len(combined_features)}) for training")
```

---

### Phase 3: Multi-Symbol/Multi-Timeframe Investigation

#### 3.1 Add Debug Logging
Add detailed logging to trace data flow through the pipeline:

**Files**:
- `ktrdr/training/training_pipeline.py` (combine_multi_symbol_data)
- `ktrdr/data/multi_timeframe_coordinator.py` (load_multi_timeframe_data)

Log:
- Number of samples per symbol
- Date range per symbol
- Alignment results for multi-timeframe

#### 3.2 Create Targeted Test Cases
Write tests that specifically exercise:
- 3-symbol training (EURUSD, GBPUSD, USDJPY)
- 2-timeframe training (1h + 5m)
- Combinations of both

Track where data gets lost or misaligned.

#### 3.3 Document Known Working Configurations
Until multi-symbol/multi-TF are verified, document what works:
- Single symbol (EURUSD)
- Single timeframe (1h)
- Proven indicators (RSI, DI, Stochastic)

---

### Phase 4: Agent Guardrails

#### 4.1 Update Agent Prompt
Guide the agent toward proven configurations:

**File**: `ktrdr/agents/prompts.py`

Add to system prompt:
```
## Configuration Guidelines

PROVEN configurations (recommended):
- Single symbol: EURUSD
- Single timeframe: 1h
- Indicators: RSI, DI, Stochastic (well-tested)
- Zigzag threshold: 1.5% for 1h

EXPERIMENTAL configurations (may have issues):
- Multi-symbol training (untested at scale)
- Multi-timeframe (1h + 5m alignment issues)
- Less common indicators (Fisher, ADX as primary)

Start with proven configs. Only try experimental after understanding the baseline.
```

#### 4.2 Add Strategy Validation Warnings
**File**: `ktrdr/agents/workers/design_worker.py` (or similar)

When agent designs a strategy, check:
```python
if len(symbols) > 1:
    logger.warning("Multi-symbol training is experimental")
if len(timeframes) > 1:
    logger.warning("Multi-timeframe training is experimental")
```

---

## Implementation Order

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Adjust loss threshold (0.0) | Small | High - unblocks exploration |
| 2 | Re-enable gates | Small | High - catches failures |
| 3 | Add 0% accuracy check | Small | High - catches broken training |
| 4 | Fail loudly on missing data | Medium | Medium - surfaces bugs |
| 5 | Add data validation | Medium | Medium - prevents silent failures |
| 6 | Update agent prompt | Small | Medium - guides toward success |
| 7 | Multi-symbol investigation | Large | Low priority until needed |
| 8 | Multi-timeframe investigation | Large | Low priority until needed |

---

## Success Criteria

After implementing Phase 1-2:
1. Gates are enabled by default (no bypass)
2. 0% accuracy experiments are caught and rejected
3. Loss regressions are caught
4. Experiments with 30-60% accuracy pass and get backtested
5. Missing test data raises an error (not silent 0%)

After Phase 4:
6. Agent prefers proven configs
7. Experimental configs are flagged with warnings

---

## Agent Maturity Model

The agent should evolve through developmental stages, with gates becoming stricter as learnings solidify:

### Stage 1: Baby (Current)
**Characteristics**: Extreme learning mode, make lots of mistakes, try everything.

**Gate Configuration**:
```python
min_accuracy: 0.10        # Only catch completely broken (0-10%)
min_loss_decrease: -0.5   # Allow some regression while exploring
min_win_rate: 0.10        # Only catch catastrophic backtest
```

**Focus**: Gather data, explore indicator combinations, build experiment history.

### Stage 2: Toddler
**Characteristics**: Starting to recognize patterns, basic learnings solidifying.

**Gate Configuration**:
```python
min_accuracy: 0.35        # Require basic learning signal
min_loss_decrease: 0.0    # Don't allow regression
min_win_rate: 0.30        # Require better than terrible
```

**Focus**: Validate early patterns, refine what works.

### Stage 3: Child (7 y.o.)
**Characteristics**: Structured learning, clear preferences emerging.

**Gate Configuration**:
```python
min_accuracy: 0.45        # Require meaningful improvement
min_loss_decrease: 0.1    # Require 10% improvement
min_win_rate: 0.40        # Require reasonable performance
```

**Focus**: Consolidate learnings, depth over breadth.

### Stage 4: Pre-teen (10 y.o.)
**Characteristics**: Consistent results, refined strategies.

**Gate Configuration**:
```python
min_accuracy: 0.55        # Require strong signal
min_loss_decrease: 0.15   # Require solid improvement
min_win_rate: 0.45        # Require good performance
```

**Focus**: Optimize within proven patterns.

### Stage 5: Teenager / Production
**Characteristics**: Mature, reliable, deployment-ready.

**Gate Configuration**:
```python
min_accuracy: 0.60        # High bar
min_loss_decrease: 0.2    # Strong improvement required
min_win_rate: 0.50        # Must beat random
```

**Focus**: Production deployment, live trading.

---

## Decisions

### Multi-Symbol / Multi-Timeframe: MUST FIX

These are **not optional** — they're key hypotheses (H_001, H_004) for breaking the 64.2% plateau. The platform issues need to be fixed, not worked around.

**Priority**: Phase 3 (Investigation) moves to **Phase 1** priority.

### Current Stage: Baby

We're in Stage 1 (Baby). Gates should be:
- **Very lax**: Only catch catastrophic failures (0% accuracy, 0 trades)
- **Allow exploration**: Let the agent try multi-symbol, multi-TF, unusual indicators
- **Learn from failures**: Record everything, even failures, to build knowledge

---

## Revised Implementation Order

| Priority | Task | Why |
|----------|------|-----|
| 1 | **Fix multi-symbol training** | Needed to test H_004 |
| 2 | **Fix multi-timeframe training** | Needed to test H_001 |
| 3 | Implement maturity-based gate config | Enable Stage 1 (Baby) mode |
| 4 | Add 0% accuracy catastrophic check | Catch completely broken training |
| 5 | Fail loudly on missing data | Surface bugs for investigation |
| 6 | Add data validation | Prevent silent failures |

---

## Success Criteria

**Immediate (Stage 1 - Baby)**:
1. Multi-symbol training produces valid test data
2. Multi-timeframe training produces valid test data
3. Gates set to Baby mode (very lax)
4. 0% accuracy experiments are caught
5. All experiments recorded (successes AND failures)

**Near-term (Stage 2 - Toddler)**:
6. First strategies validated with real backtest results
7. Gates tightened based on accumulated data
8. Patterns start to emerge from experiment history

---

*Created: 2025-12-31*
*Updated: 2025-12-31 — Added maturity model, prioritized multi-symbol/multi-TF fixes*
*Status: Ready for review*
