---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: IndicatorEngine Adapter

**Branch:** `feature/indicator-std-m2-adapter`
**Builds on:** M1 (interface methods exist on all indicators)
**Goal:** Engine supports both old and new indicator output formats with v2 compatibility.

## E2E Test Scenario

**Purpose:** Verify adapter handles both old-format and new-format indicators
**Duration:** ~60 seconds
**Prerequisites:** M1 complete, development environment running

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

# 2. Test the new compute_indicator() method directly
uv run python -c "
from ktrdr.indicators import RSIIndicator, BollingerBandsIndicator, IndicatorEngine
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=100)

engine = IndicatorEngine()

# Single-output: should return DataFrame with indicator_id column
rsi = RSIIndicator(period=14)
result = engine.compute_indicator(data, rsi, 'rsi_14')
assert 'rsi_14' in result.columns, f'Expected rsi_14, got {list(result.columns)}'
print('Single-output: rsi_14 ✓')

# Multi-output (old format): should have prefixed columns + alias
bbands = BollingerBandsIndicator(period=20, multiplier=2.0)
result = engine.compute_indicator(data, bbands, 'bbands_20_2')
print('Multi-output columns:', list(result.columns))

# During transition (old format): columns might still have params
# But alias should exist
assert 'bbands_20_2' in result.columns, 'bbands_20_2 alias missing'
print('Multi-output: bbands_20_2 alias ✓')

print('SUCCESS: compute_indicator() works')
"
```

**Success Criteria:**

- [ ] v2 smoke test passes: training completes
- [ ] v2 smoke test passes: backtesting completes (model loads correctly)
- [ ] `compute_indicator(data, indicator, indicator_id)` method exists
- [ ] Old-format indicators work through adapter
- [ ] New-format indicators (when migrated) will work through adapter
- [ ] Alias columns created for bare `indicator_id` references

---

## Task 2.1: Add compute_indicator() Method

**File:** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component (new method used by all indicator computation)

**Description:**
Add new `compute_indicator()` method that handles both old-format and new-format indicator outputs. This is the core adapter logic.

**Implementation Notes:**
- New method, doesn't replace existing `apply()` yet
- Detect format by comparing `compute()` columns with `get_output_names()`
- Old format: pass through columns, add alias for primary output
- New format: prefix columns with `indicator_id.`
- Mark all compatibility code with `# CLEANUP(v3)`

**Code sketch:**
```python
def compute_indicator(
    self,
    data: pd.DataFrame,
    indicator: BaseIndicator,
    indicator_id: str,
) -> pd.DataFrame:
    """
    Compute an indicator and return properly named columns.

    Handles both old-format and new-format indicator outputs:
    - Old format: columns include params (e.g., "upper_20_2.0") -> pass through
    - New format: semantic names only (e.g., "upper") -> prefix with indicator_id

    For multi-output indicators, adds alias column for bare indicator_id
    pointing to primary output.

    Args:
        data: OHLCV DataFrame
        indicator: The indicator instance
        indicator_id: The ID from strategy config (e.g., "rsi_14", "bbands_20_2")

    Returns:
        DataFrame with columns:
        - Single-output: {indicator_id}
        - Multi-output (new): {indicator_id}.{output_name} + {indicator_id} alias
        - Multi-output (old): original columns + {indicator_id} alias
    """
    result = indicator.compute(data)

    if not indicator.is_multi_output():
        # Single-output: wrap Series in DataFrame with indicator_id column
        if isinstance(result, pd.Series):
            return pd.DataFrame({indicator_id: result}, index=data.index)
        else:
            # Already DataFrame (shouldn't happen for single-output)
            result.columns = [indicator_id]
            return result

    # Multi-output indicator
    expected_outputs = set(indicator.get_output_names())
    actual_columns = set(result.columns)

    if expected_outputs == actual_columns:
        # NEW FORMAT: semantic names only -> prefix with indicator_id
        prefixed = result.rename(columns={
            name: f"{indicator_id}.{name}"
            for name in result.columns
        })

        # Add alias for bare indicator_id -> primary output
        primary = indicator.get_primary_output()
        if primary:
            prefixed[indicator_id] = prefixed[f"{indicator_id}.{primary}"]

        return prefixed
    else:
        # CLEANUP(v3): Remove old-format handling after v3 migration complete
        # OLD FORMAT: columns have params embedded -> pass through
        # Add alias for bare indicator_id -> primary output column

        primary_suffix = indicator.get_primary_output_suffix()
        primary_col = None

        if primary_suffix:
            # Find column that matches primary suffix
            for col in result.columns:
                if primary_suffix in col:
                    primary_col = col
                    break
        else:
            # No suffix means primary is the "base" column (e.g., MACD_12_26)
            # Find column without underscore-separated suffix
            for col in result.columns:
                if col == indicator.get_column_name():
                    primary_col = col
                    break

        if primary_col:
            result[indicator_id] = result[primary_col]

        return result
```

**Tests:**
- Unit: `tests/unit/indicators/test_indicator_engine_adapter.py` (new file)
- What to test:
  - Single-output returns DataFrame with `{indicator_id}` column
  - Multi-output old-format: columns passed through + alias added
  - Multi-output new-format: columns prefixed + alias added
  - Format detection works correctly

**Smoke Test:**
```bash
uv run python -c "
from ktrdr.indicators import IndicatorEngine, RSIIndicator
engine = IndicatorEngine()
# Verify method exists
assert hasattr(engine, 'compute_indicator')
print('compute_indicator() exists ✓')
"
```

**Acceptance Criteria:**
- [ ] Method handles single-output indicators
- [ ] Method handles multi-output old-format indicators
- [ ] Method handles multi-output new-format indicators (tested with mock)
- [ ] Alias column created for multi-output indicators
- [ ] Format detection via column matching works

---

## Task 2.2: Update apply() to Use compute_indicator()

**File:** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Wiring/DI (connecting new method to existing flow)

**Description:**
Update the existing `apply()` method to use `compute_indicator()` internally. This ensures all indicator computation goes through the adapter.

**Implementation Notes:**
- `apply()` currently iterates over indicators and calls `compute()` directly
- Change to call `compute_indicator()` instead
- Need to pass `indicator_id` (from `feature_id` config or generated)
- Keep backward compatibility with existing calling code

**Current flow:**
```python
def apply(self, data: pd.DataFrame) -> pd.DataFrame:
    result_df = data.copy()
    for indicator in self.indicators:
        computed = indicator.compute(data)
        # ... merge into result_df ...
    return result_df
```

**New flow:**
```python
def apply(self, data: pd.DataFrame) -> pd.DataFrame:
    result_df = data.copy()
    for indicator in self.indicators:
        # Get indicator_id from feature_id or generate from column name
        indicator_id = indicator.get_feature_id()
        computed = self.compute_indicator(data, indicator, indicator_id)
        result_df = pd.concat([result_df, computed], axis=1)
    return result_df
```

**Tests:**
- Unit: Add tests to `tests/unit/indicators/test_indicator_engine_adapter.py`
- What to test:
  - `apply()` produces same results as before (regression test)
  - Feature IDs are used as indicator_ids
  - Multi-output indicators have alias columns

**Integration Test:**
```python
def test_apply_uses_compute_indicator():
    """Verify apply() routes through compute_indicator()."""
    factory = IndicatorFactory([
        {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
        {'name': 'bbands', 'feature_id': 'bbands_20_2', 'period': 20},
    ])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)

    result = engine.apply(sample_data)

    # Verify feature_id columns exist (adapter creates them)
    assert 'rsi_14' in result.columns
    assert 'bbands_20_2' in result.columns  # Alias for primary output
```

**Acceptance Criteria:**
- [ ] `apply()` uses `compute_indicator()` internally
- [ ] Existing tests still pass (no regression)
- [ ] Feature IDs used as indicator_ids
- [ ] Alias columns created for multi-output indicators

---

## Task 2.3: Unit Tests for Format Detection

**File:** `tests/unit/indicators/test_format_detection.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Testing

**Description:**
Create comprehensive tests for format detection logic. This is critical for the transition period.

**Implementation Notes:**
- Test with mock indicators that return old-format and new-format
- Verify correct code path is taken
- Test edge cases (empty output names, mismatched columns)

**Code sketch:**
```python
import pytest
import pandas as pd
from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.base_indicator import BaseIndicator

class MockOldFormatIndicator(BaseIndicator):
    """Mock indicator returning old-format columns (params in names)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        # OLD FORMAT: params in column names
        return pd.DataFrame({
            "upper_20_2.0": [1.0] * len(df),
            "middle_20_2.0": [0.5] * len(df),
            "lower_20_2.0": [0.0] * len(df),
        }, index=df.index)

class MockNewFormatIndicator(BaseIndicator):
    """Mock indicator returning new-format columns (semantic only)."""

    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        # NEW FORMAT: semantic names only
        return pd.DataFrame({
            "upper": [1.0] * len(df),
            "middle": [0.5] * len(df),
            "lower": [0.0] * len(df),
        }, index=df.index)

def test_old_format_detection():
    """Old-format columns are passed through with alias added."""
    engine = IndicatorEngine()
    indicator = MockOldFormatIndicator(name="test")
    sample = pd.DataFrame({"close": [1, 2, 3]})

    result = engine.compute_indicator(sample, indicator, "bbands_20_2")

    # Old format: original columns preserved
    assert "upper_20_2.0" in result.columns
    # Alias added
    assert "bbands_20_2" in result.columns

def test_new_format_detection():
    """New-format columns are prefixed with indicator_id."""
    engine = IndicatorEngine()
    indicator = MockNewFormatIndicator(name="test")
    sample = pd.DataFrame({"close": [1, 2, 3]})

    result = engine.compute_indicator(sample, indicator, "bbands_20_2")

    # New format: columns prefixed
    assert "bbands_20_2.upper" in result.columns
    assert "bbands_20_2.middle" in result.columns
    assert "bbands_20_2.lower" in result.columns
    # Alias added
    assert "bbands_20_2" in result.columns
    # Original semantic names NOT present
    assert "upper" not in result.columns
```

**Tests:**
- This IS the test file

**Acceptance Criteria:**
- [ ] Old-format detection works (params in column names)
- [ ] New-format detection works (semantic names only)
- [ ] Alias creation works for both formats
- [ ] Edge cases handled (single-output, empty output names)

---

## Milestone 2 Verification

### Completion Checklist

- [ ] Task 2.1: `compute_indicator()` method implemented
- [ ] Task 2.2: `apply()` routes through `compute_indicator()`
- [ ] Task 2.3: Format detection tests pass
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v2 smoke test passes (E2E scenario above)
- [ ] M1 E2E test still passes (regression check)

### Definition of Done

At the end of M2:
- IndicatorEngine has adapter layer supporting both formats
- Old-format indicators work (current state)
- New-format indicators work (ready for M3a/M3b)
- v2 strategies continue to work
- Ready for M3a: migrate single-output indicators
