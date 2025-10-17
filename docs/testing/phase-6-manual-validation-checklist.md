# Phase 6: Manual Validation Checklist

**Purpose**: Human verification of feature ID system functionality and quality before production deployment.

**Date**: 2025-10-16
**Phase**: Phase 6 - Comprehensive System Testing
**Status**: Ready for Execution

---

## Overview

This checklist provides step-by-step manual validation procedures to verify that the feature ID system works correctly in real-world scenarios. Each item must be verified and checked off before considering Phase 6 complete.

---

## Pre-Validation Setup

### Environment Preparation

- [ ] **Start all services**
  ```bash
  ./start_ktrdr.sh
  ```

- [ ] **Verify services running**
  ```bash
  # Check IB Host Service
  curl http://localhost:5001/health

  # Check Training Host Service
  curl http://localhost:5002/health

  # Check API
  curl http://localhost:8000/api/v1/health
  ```

- [ ] **Verify database connection**
  ```bash
  # Check data directory exists
  ls -la data/

  # Verify sample data available
  ktrdr data show AAPL 1d --limit 10
  ```

---

## Section 1: Strategy Configuration Validation

### 1.1 Upload Strategy with feature_ids

**Test**: Upload a valid strategy with explicit feature_ids

- [ ] **Navigate to strategy upload** (UI or CLI)
  ```bash
  ktrdr strategies validate strategies/rsi_mean_reversion.yaml
  ```

- [ ] **Verify validation passes**
  - ✅ No errors reported
  - ✅ feature_ids recognized
  - ✅ All indicators validated

- [ ] **Check validation output includes feature_ids**
  - Look for feature_id mentions in validation output
  - Confirm fuzzy_sets match feature_ids

**Expected Result**: Strategy validates successfully with clear confirmation.

---

### 1.2 Upload Strategy without feature_ids

**Test**: Attempt to upload old format strategy (should fail gracefully)

- [ ] **Create test strategy without feature_ids**
  ```yaml
  # test_old_format.yaml
  name: "test_old_format"
  version: "2.1"
  scope: "universal"
  indicators:
    - name: "rsi"
      period: 14  # Missing feature_id!
  fuzzy_sets:
    rsi_14:
      oversold: {type: "triangular", parameters: [0, 20, 35]}
  ```

- [ ] **Attempt validation**
  ```bash
  ktrdr strategies validate test_old_format.yaml
  ```

- [ ] **Verify clear error message**
  - ✅ Error mentions missing feature_id
  - ✅ Error includes migration command
  - ✅ Error is actionable (tells user what to do)

**Expected Result**: Clear error with migration instructions.

---

### 1.3 Upload Strategy with Duplicate feature_ids

**Test**: Verify duplicate detection works

- [ ] **Create test strategy with duplicate feature_ids**
  ```yaml
  # test_duplicate.yaml
  indicators:
    - name: "rsi"
      feature_id: "rsi_main"
      period: 14
    - name: "rsi"
      feature_id: "rsi_main"  # DUPLICATE!
      period: 21
  ```

- [ ] **Attempt validation**

- [ ] **Verify duplicate error**
  - ✅ Error clearly states "duplicate feature_id"
  - ✅ Error lists which feature_ids are duplicated
  - ✅ Error suggests how to fix (make unique)

**Expected Result**: Clear duplicate error with guidance.

---

### 1.4 Upload Strategy with Missing Fuzzy Sets

**Test**: Verify fuzzy set matching validation

- [ ] **Create strategy with indicator but no fuzzy_sets**
  ```yaml
  indicators:
    - name: "rsi"
      feature_id: "rsi_14"
      period: 14
  fuzzy_sets:
    # Missing rsi_14 entry!
    some_other_indicator:
      ...
  ```

- [ ] **Attempt validation**

- [ ] **Verify missing fuzzy_sets error**
  - ✅ Error states "missing fuzzy_sets for feature_id: rsi_14"
  - ✅ Error suggests adding fuzzy_sets entry
  - ✅ Provides example structure

**Expected Result**: Clear error indicating which fuzzy_sets are missing.

---

## Section 2: Training Pipeline Validation

### 2.1 Train Model with feature_ids (Parameter-Based Naming)

**Test**: Full training run with param-based feature_ids

- [ ] **Select strategy**: `strategies/rsi_mean_reversion.yaml`

- [ ] **Start training**
  ```bash
  ktrdr models train strategies/rsi_mean_reversion.yaml \
    --symbol AAPL \
    --timeframe 1h \
    --start-date 2024-01-01 \
    --end-date 2024-03-01
  ```

- [ ] **Monitor training logs**
  - ✅ feature_ids appear in logs
  - ✅ Indicator computation successful
  - ✅ Fuzzy processing references correct feature_ids
  - ✅ No warnings about missing columns

- [ ] **Training completes successfully**
  - ✅ No errors during training
  - ✅ Model saved
  - ✅ Metrics reported

- [ ] **Inspect trained model**
  ```bash
  ktrdr models list
  ```
  - ✅ Model appears in list
  - ✅ Feature names match expected feature_ids

**Expected Result**: Training completes successfully, model uses feature_ids.

---

### 2.2 Train Model with Semantic Naming

**Test**: Training with semantic feature_ids (rsi_fast, macd_trend)

- [ ] **Create test strategy with semantic naming**
  ```yaml
  indicators:
    - name: "rsi"
      feature_id: "rsi_fast"
      period: 7
    - name: "rsi"
      feature_id: "rsi_slow"
      period: 21
  fuzzy_sets:
    rsi_fast:
      extreme_oversold: {type: "triangular", parameters: [0, 10, 25]}
    rsi_slow:
      oversold: {type: "triangular", parameters: [0, 25, 45]}
  ```

- [ ] **Start training**

- [ ] **Verify semantic names in training**
  - ✅ Logs show "rsi_fast" and "rsi_slow"
  - ✅ No confusion between the two RSIs
  - ✅ Fuzzy sets correctly map to respective indicators

- [ ] **Training completes**

- [ ] **Model features use semantic names**

**Expected Result**: Semantic names work correctly, no ambiguity.

---

### 2.3 Train with Multi-Output Indicator (MACD)

**Test**: Verify MACD feature_id maps to primary output

- [ ] **Use strategy with MACD**
  ```yaml
  indicators:
    - name: "macd"
      feature_id: "macd_12_26_9"
      fast_period: 12
      slow_period: 26
      signal_period: 9
  fuzzy_sets:
    macd_12_26_9:  # Should reference main MACD line
      bullish: {type: "triangular", parameters: [0, 5, 20]}
  ```

- [ ] **Start training**

- [ ] **Verify in logs**
  - ✅ feature_id "macd_12_26_9" appears
  - ✅ MACD main line is used (not signal or histogram)
  - ✅ Fuzzy processing uses main line values

- [ ] **Check DataFrame columns (if visible in logs)**
  - Technical columns: MACD_12_26, MACD_signal_12_26_9, MACD_hist_12_26_9
  - feature_id alias: macd_12_26_9 → MACD_12_26

**Expected Result**: MACD feature_id correctly maps to primary output.

---

### 2.4 Train with Multi-Timeframe

**Test**: feature_ids work across multiple timeframes

- [ ] **Use multi-timeframe strategy**
  ```yaml
  training_data:
    timeframes:
      mode: "multi_timeframe"
      list: ["15m", "1h"]
      base_timeframe: "15m"
  indicators:
    - name: "rsi"
      feature_id: "rsi_14"
      period: 14
  ```

- [ ] **Start training**

- [ ] **Verify feature_ids across timeframes**
  - ✅ feature_ids present in both timeframes
  - ✅ No conflicts between timeframes
  - ✅ Fuzzy processing works for both

**Expected Result**: Multi-timeframe training works with feature_ids.

---

## Section 3: Error Handling Validation

### 3.1 Verify Error Message Quality

**Test**: All errors are clear and actionable

- [ ] **Missing feature_id error** (from 1.2)
  - ✅ Includes: What's wrong
  - ✅ Includes: Where (which indicator)
  - ✅ Includes: How to fix (migration command)
  - ✅ Includes: Example code

- [ ] **Duplicate feature_id error** (from 1.3)
  - ✅ Includes: Which feature_ids are duplicated
  - ✅ Includes: How to fix (make unique)
  - ✅ Includes: Example

- [ ] **Missing fuzzy_sets error** (from 1.4)
  - ✅ Includes: Which feature_ids lack fuzzy_sets
  - ✅ Includes: How to add fuzzy_sets
  - ✅ Includes: Example structure

**Expected Result**: All errors have message, code, context, details, and suggestions.

---

### 3.2 Verify Logging Output

**Test**: Logs show feature_ids at each stage

- [ ] **During indicator computation**
  - ✅ Log shows: "Computing indicator rsi with feature_id: rsi_14"
  - ✅ Log shows column name and feature_id separately

- [ ] **During fuzzy processing**
  - ✅ Log shows: "Processing fuzzy_sets for feature_id: rsi_14"
  - ✅ Log shows successful fuzzification

- [ ] **During feature preparation**
  - ✅ Logs show feature_ids in feature list
  - ✅ No column name mismatches

**Expected Result**: Logs clearly show feature_ids being used correctly.

---

## Section 4: Integration Testing

### 4.1 End-to-End Workflow

**Test**: Complete workflow from strategy upload to model testing

- [ ] **Step 1: Create and validate strategy**
  ```bash
  ktrdr strategies validate strategies/test_e2e.yaml
  ```

- [ ] **Step 2: Train model**
  ```bash
  ktrdr models train strategies/test_e2e.yaml AAPL 1h \
    --start-date 2024-01-01 --end-date 2024-03-01
  ```

- [ ] **Step 3: Inspect model**
  ```bash
  ktrdr models list
  ktrdr models info <model_id>
  ```

- [ ] **Step 4: Test model (if supported)**
  ```bash
  ktrdr models test <model_id> --symbol AAPL
  ```

- [ ] **Verify each step**
  - ✅ No errors at any stage
  - ✅ feature_ids consistent throughout
  - ✅ Model produces predictions

**Expected Result**: Complete workflow works smoothly.

---

### 4.2 Backtest with feature_ids

**Test**: Backtesting uses feature_ids correctly

- [ ] **Run backtest** (if supported)
  ```bash
  ktrdr backtest --strategy strategies/test_e2e.yaml \
    --symbol AAPL --start 2024-01-01 --end 2024-03-01
  ```

- [ ] **Verify**
  - ✅ Backtest completes
  - ✅ feature_ids used during execution
  - ✅ Results match training expectations

**Expected Result**: Backtesting works with feature_ids.

---

## Section 5: Documentation Validation

### 5.1 User Documentation

**Test**: Documentation is clear and helpful

- [ ] **Read indicator configuration guide**
  - docs/user-guides/indicator-configuration.md

- [ ] **Verify clarity**
  - ✅ Explains feature_id concept clearly
  - ✅ Shows naming strategies with examples
  - ✅ Includes complete configuration examples
  - ✅ Troubleshooting section is helpful

- [ ] **Read migration guide**
  - docs/migration/feature-ids-migration-guide.md

- [ ] **Verify completeness**
  - ✅ Explains why migration needed
  - ✅ Step-by-step migration process
  - ✅ Troubleshooting common issues
  - ✅ FAQ answers key questions

**Expected Result**: Documentation is comprehensive and user-friendly.

---

### 5.2 Example Strategies

**Test**: All examples use feature_ids correctly

- [ ] **Review example strategies**
  ```bash
  ls strategies/*.yaml
  ```

- [ ] **For each example**
  - ✅ Has feature_id for all indicators
  - ✅ feature_ids are unique
  - ✅ fuzzy_sets keys match feature_ids
  - ✅ Includes comments explaining feature_id choices

- [ ] **Validate all examples**
  ```bash
  for f in strategies/*.yaml; do
    echo "Validating $f"
    ktrdr strategies validate "$f"
  done
  ```

**Expected Result**: All examples valid and follow best practices.

---

## Section 6: Performance Validation

### 6.1 Training Performance

**Test**: No performance degradation

- [ ] **Baseline timing** (if available from earlier)

- [ ] **Current timing**
  ```bash
  time ktrdr models train strategies/rsi_mean_reversion.yaml \
    AAPL 1h --start-date 2024-01-01 --end-date 2024-02-01
  ```

- [ ] **Compare**
  - ✅ Training time within 10% of baseline
  - ✅ Memory usage acceptable
  - ✅ No memory leaks observed

**Expected Result**: Performance within acceptable range (< 10% difference).

---

### 6.2 Validation Performance

**Test**: Early validation is fast

- [ ] **Time validation**
  ```bash
  time ktrdr strategies validate strategies/rsi_mean_reversion.yaml
  ```

- [ ] **Verify**
  - ✅ Validation completes in < 2 seconds
  - ✅ No indicator computation during validation
  - ✅ Clear, fast feedback

**Expected Result**: Validation is fast (early failure without computation).

---

## Final Checklist

### All Sections Complete

- [ ] Section 1: Strategy Configuration Validation (4/4 tests)
- [ ] Section 2: Training Pipeline Validation (4/4 tests)
- [ ] Section 3: Error Handling Validation (2/2 tests)
- [ ] Section 4: Integration Testing (2/2 tests)
- [ ] Section 5: Documentation Validation (2/2 tests)
- [ ] Section 6: Performance Validation (2/2 tests)

### No Critical Bugs Found

- [ ] No P0 bugs (system-breaking)
- [ ] No P1 bugs (major functionality broken)
- [ ] All P2 bugs documented and triaged

### System Ready for Production

- [ ] All tests pass
- [ ] Documentation complete
- [ ] Performance acceptable
- [ ] Error messages clear
- [ ] No regressions detected

---

## Issues Log

**If any issues found during validation, log them here:**

| Issue # | Severity | Description | Status | Resolution |
|---------|----------|-------------|--------|------------|
| | | | | |

---

## Sign-Off

**Validator**: _________________
**Date**: _________________
**Result**: ☐ PASS / ☐ FAIL (with documented issues)

**Notes**:
_________________________________________________________________________________
_________________________________________________________________________________

---

## Next Steps After Validation

### If PASS:
- [ ] Merge feature branch to main
- [ ] Create release notes
- [ ] Deploy to production
- [ ] Monitor for issues

### If FAIL:
- [ ] Address all P0/P1 bugs
- [ ] Re-run validation
- [ ] Update documentation as needed
- [ ] Consider rollback plan

---

**END OF MANUAL VALIDATION CHECKLIST**
