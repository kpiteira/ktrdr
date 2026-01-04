---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Add Interface (No Behavior Change)

**Branch:** `feature/indicator-std-m1-interface`
**Builds on:** Nothing (first milestone)
**Goal:** Add `get_output_names()` interface to all indicators without changing runtime behavior.

## E2E Test Scenario

**Purpose:** Verify v2 strategies still work (no behavior change)
**Duration:** ~60 seconds
**Prerequisites:** Development environment running

```bash
# 1. v2 Smoke Test: Train + Backtest
# Uses limited data for speed

# Train model (2 months of 1h data)
uv run ktrdr models train strategies/mean_reversion_momentum_v1.yaml EURUSD 1h \
    --start-date 2024-01-01 \
    --end-date 2024-03-01

# Backtest the trained model (catches model load/feature mismatch issues)
uv run ktrdr backtest run mean_reversion_momentum_v1 EURUSD 1h \
    --start-date 2024-03-01 \
    --end-date 2024-04-01

# 2. Verify new interface exists
uv run python -c "
from ktrdr.indicators import RSIIndicator, BollingerBandsIndicator, MACDIndicator

# Single-output
rsi = RSIIndicator(period=14)
assert rsi.is_multi_output() == False
assert rsi.get_output_names() == []
assert rsi.get_primary_output() is None
print('RSI: single-output, no output names ✓')

# Multi-output
bbands = BollingerBandsIndicator(period=20, multiplier=2.0)
assert bbands.is_multi_output() == True
assert bbands.get_output_names() == ['upper', 'middle', 'lower']
assert bbands.get_primary_output() == 'upper'
print('BBands: multi-output, outputs:', bbands.get_output_names(), '✓')

macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
assert macd.is_multi_output() == True
assert macd.get_output_names() == ['line', 'signal', 'histogram']
assert macd.get_primary_output() == 'line'
print('MACD: multi-output, outputs:', macd.get_output_names(), '✓')

print('SUCCESS: New interface works')
"
```

**Success Criteria:**
- [ ] v2 smoke test passes: training completes
- [ ] v2 smoke test passes: backtesting completes (model loads correctly)
- [ ] All indicators have `get_output_names()` method
- [ ] Multi-output indicators return correct output names
- [ ] Single-output indicators return empty list

---

## Task 1.1: Update BaseIndicator Interface

**File:** `ktrdr/indicators/base_indicator.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component (interface change affects all indicators)

**Description:**
Replace `get_primary_output_suffix()` with `get_output_names()` and add `get_primary_output()` convenience method. Keep `get_primary_output_suffix()` temporarily for backward compatibility.

**Implementation Notes:**
- Add new methods as class methods (not instance methods)
- Default implementation: `get_output_names()` returns `[]`, `get_primary_output()` returns `None`
- Keep `get_primary_output_suffix()` with deprecation comment — will be removed in M6
- Do NOT change `get_column_name()` or `get_feature_id()` yet

**Code sketch:**
```python
@classmethod
def is_multi_output(cls) -> bool:
    """Returns True if compute() returns DataFrame, False if Series."""
    return False  # Default: single output (already exists)

@classmethod
def get_output_names(cls) -> list[str]:
    """
    Return semantic output names for multi-output indicators.

    Single-output indicators return empty list.
    Multi-output indicators return ordered list of output names.
    First item is the primary output (used for bare indicator_id references).

    Examples:
        RSI: []
        BollingerBands: ["upper", "middle", "lower"]
        MACD: ["line", "signal", "histogram"]
    """
    return []

@classmethod
def get_primary_output(cls) -> str | None:
    """
    Return the primary output name for multi-output indicators.
    Convenience method - returns get_output_names()[0] or None.
    """
    outputs = cls.get_output_names()
    return outputs[0] if outputs else None

# CLEANUP(v3): Remove after v3 migration complete
@classmethod
def get_primary_output_suffix(cls) -> str | None:
    """DEPRECATED: Use get_primary_output() instead."""
    return cls.get_primary_output()
```

**Tests:**
- Unit: `tests/unit/indicators/test_base_indicator.py`
- What to test:
  - Default `get_output_names()` returns `[]`
  - Default `get_primary_output()` returns `None`
  - `get_primary_output_suffix()` still works (backward compat)

**Acceptance Criteria:**
- [ ] New methods added to BaseIndicator
- [ ] Default implementations work correctly
- [ ] Existing tests still pass
- [ ] No behavior change to indicator computation

---

## Task 1.2: Implement get_output_names() for Multi-Output Indicators

**File(s):** 10 indicator files
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component (implementing interface)

**Description:**
Implement `get_output_names()` in all multi-output indicators. The method should return the semantic output names that will be used in v3 format.

**Files to modify:**
1. `ktrdr/indicators/bollinger_bands_indicator.py` → `["upper", "middle", "lower"]`
2. `ktrdr/indicators/macd_indicator.py` → `["line", "signal", "histogram"]`
3. `ktrdr/indicators/stochastic_indicator.py` → `["k", "d"]`
4. `ktrdr/indicators/adx_indicator.py` → `["adx", "plus_di", "minus_di"]`
5. `ktrdr/indicators/aroon_indicator.py` → `["up", "down", "oscillator"]`
6. `ktrdr/indicators/ichimoku_indicator.py` → `["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"]`
7. `ktrdr/indicators/supertrend_indicator.py` → `["trend", "direction"]`
8. `ktrdr/indicators/donchian_channels.py` → `["upper", "middle", "lower"]`
9. `ktrdr/indicators/keltner_channels.py` → `["upper", "middle", "lower"]`
10. `ktrdr/indicators/fisher_transform.py` → `["fisher", "signal"]`

**Implementation Notes:**
- Add `@classmethod` decorator
- `is_multi_output()` should already return `True` for these
- Do NOT change `compute()` yet — it still returns old format
- Do NOT change `get_primary_output_suffix()` yet

**Code sketch (BollingerBands example):**
```python
@classmethod
def get_output_names(cls) -> list[str]:
    return ["upper", "middle", "lower"]
```

**Tests:**
- Unit: `tests/unit/indicators/test_multi_output_interface.py` (new file)
- What to test:
  - Each indicator's `get_output_names()` returns expected list
  - Each indicator's `get_primary_output()` returns first item
  - Existing `compute()` still works (no behavior change)

**Acceptance Criteria:**
- [ ] All 10 multi-output indicators have `get_output_names()`
- [ ] Output names match the standard from DESIGN.md
- [ ] Primary output is first in each list
- [ ] Existing indicator tests still pass

---

## Task 1.3: Verify Single-Output Indicators

**File(s):** 18 indicator files
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Verification

**Description:**
Verify all single-output indicators inherit the default `get_output_names()` that returns `[]`. No code changes needed unless an indicator incorrectly overrides `is_multi_output()`.

**Files to verify:**
1. `ktrdr/indicators/rsi_indicator.py`
2. `ktrdr/indicators/atr_indicator.py`
3. `ktrdr/indicators/cci_indicator.py`
4. `ktrdr/indicators/cmf_indicator.py`
5. `ktrdr/indicators/mfi_indicator.py`
6. `ktrdr/indicators/obv_indicator.py`
7. `ktrdr/indicators/roc_indicator.py`
8. `ktrdr/indicators/momentum_indicator.py`
9. `ktrdr/indicators/williams_r_indicator.py`
10. `ktrdr/indicators/vwap_indicator.py`
11. `ktrdr/indicators/volume_ratio_indicator.py`
12. `ktrdr/indicators/distance_from_ma_indicator.py`
13. `ktrdr/indicators/bollinger_band_width_indicator.py`
14. `ktrdr/indicators/squeeze_intensity_indicator.py`
15. `ktrdr/indicators/parabolic_sar_indicator.py`
16. `ktrdr/indicators/zigzag_indicator.py`
17. `ktrdr/indicators/ad_line.py`
18. `ktrdr/indicators/ma_indicators.py` (SMA, EMA)

**Implementation Notes:**
- Check that `is_multi_output()` returns `False` (or isn't overridden)
- No need to add `get_output_names()` — they inherit the default
- If any indicator incorrectly returns `True` for `is_multi_output()`, fix it

**Special case: RVI**
The exploration showed `rvi_indicator.py` might be multi-output. Check and categorize correctly.

**Tests:**
- Unit: `tests/unit/indicators/test_single_output_interface.py` (new file)
- What to test:
  - Each single-output indicator's `is_multi_output()` returns `False`
  - Each single-output indicator's `get_output_names()` returns `[]`

**Acceptance Criteria:**
- [ ] All single-output indicators verified
- [ ] Any misclassified indicators corrected
- [ ] Tests document the expected interface for each

---

## Task 1.4: Integration Test for All Indicators

**File:** `tests/integration/indicators/test_indicator_interface_standard.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component (validates all indicators)

**Description:**
Create an integration test that verifies ALL registered indicators follow the interface standard. This test should fail if a new indicator is added without proper interface implementation.

**Implementation Notes:**
- Use IndicatorFactory's registry to get all indicator types
- For each type, verify interface contract
- This test runs at every milestone to catch regressions

**Code sketch:**
```python
import pytest
import pandas as pd
from ktrdr.indicators import IndicatorFactory

def create_sample_ohlcv(rows: int = 100) -> pd.DataFrame:
    """Create sample OHLCV data for testing."""
    # ... generate sample data ...

def test_all_indicators_follow_interface_standard():
    """Verify all registered indicators implement the interface correctly."""
    factory = IndicatorFactory([])  # Empty config, just need registry access
    sample_data = create_sample_ohlcv()

    # Get all indicator types from factory registry
    from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS

    tested = set()
    for indicator_type, indicator_class in BUILT_IN_INDICATORS.items():
        # Skip aliases (same class, different name)
        if indicator_class in tested:
            continue
        tested.add(indicator_class)

        # Test interface
        if indicator_class.is_multi_output():
            outputs = indicator_class.get_output_names()
            assert len(outputs) > 0,
                f"{indicator_type} is multi-output but has no output names"
            assert indicator_class.get_primary_output() == outputs[0],
                f"{indicator_type} primary output mismatch"
        else:
            outputs = indicator_class.get_output_names()
            assert len(outputs) == 0,
                f"{indicator_type} is single-output but has output names: {outputs}"
            assert indicator_class.get_primary_output() is None,
                f"{indicator_type} single-output should have None primary"

def test_all_indicators_compute_without_error():
    """Verify all indicators can compute on sample data."""
    sample_data = create_sample_ohlcv(rows=200)  # Extra rows for warmup

    from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS

    tested = set()
    for indicator_type, indicator_class in BUILT_IN_INDICATORS.items():
        if indicator_class in tested:
            continue
        tested.add(indicator_class)

        # Create with default params
        try:
            indicator = indicator_class()
        except TypeError:
            # Some indicators require params, skip for now
            continue

        result = indicator.compute(sample_data)

        if indicator_class.is_multi_output():
            assert isinstance(result, pd.DataFrame),
                f"{indicator_type} multi-output should return DataFrame"
        else:
            assert isinstance(result, pd.Series),
                f"{indicator_type} single-output should return Series"
```

**Tests:**
- This IS the test file

**Acceptance Criteria:**
- [ ] Test covers all registered indicators
- [ ] Test verifies interface contract (is_multi_output ↔ get_output_names consistency)
- [ ] Test verifies compute() return type matches declaration
- [ ] Test passes with current (unchanged) indicator behavior

---

## Milestone 1 Verification

### Completion Checklist

- [ ] Task 1.1: BaseIndicator interface updated
- [ ] Task 1.2: All 10 multi-output indicators have `get_output_names()`
- [ ] Task 1.3: All 18 single-output indicators verified
- [ ] Task 1.4: Integration test passes for all indicators
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v2 smoke test passes (E2E scenario above)
- [ ] No regressions: existing indicator tests still pass

### Definition of Done

At the end of M1:
- Every indicator has `get_output_names()` returning correct semantic names
- `compute()` behavior is UNCHANGED — still returns old format
- v2 strategies work exactly as before
- Ready for M2: IndicatorEngine adapter
