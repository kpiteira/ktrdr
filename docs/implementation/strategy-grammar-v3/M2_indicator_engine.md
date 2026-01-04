---
design: docs/designs/strategy-grammar-v3/DESIGN.md
architecture: docs/designs/strategy-grammar-v3/ARCHITECTURE.md
---

# Milestone 2: IndicatorEngine V3

**Branch:** `feature/strategy-grammar-v3-m2`
**Prerequisite:** M1 complete (v3 config models exist)
**Builds on:** M1 Config Loading

## Goal

IndicatorEngine accepts dict-based indicator configuration and produces correctly-named columns using the standardized indicator interface.

## Why This Milestone

- Bridges v3 config format to indicator computation
- Uses standardized `get_output_names()` from indicator prerequisite
- Enables M3 (FuzzyEngine) which depends on indicator output

---

## Tasks

### Task 2.1: Update IndicatorEngine Constructor

**File(s):** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Wiring/DI, Cross-Component

**Description:**
Modify `IndicatorEngine` to accept v3-style dict configuration instead of v2-style list.

**Implementation Notes:**

Current (v2):
```python
def __init__(self, indicators: list[dict]):
    for ind in indicators:
        self._indicators[ind['feature_id']] = ...
```

New (v3):
```python
def __init__(self, indicators: dict[str, IndicatorDefinition]):
    """
    Args:
        indicators: Dict mapping indicator_id to definition
                   e.g., {"rsi_14": IndicatorDefinition(type="rsi", period=14)}
    """
    for indicator_id, definition in indicators.items():
        self._indicators[indicator_id] = self._create_indicator(
            indicator_id, definition
        )
```

The `_create_indicator` method uses `definition.type` to look up the indicator class from the factory, then passes remaining attributes as parameters.

**Testing Requirements:**

*Unit Tests:* `tests/unit/indicators/test_indicator_engine_v3.py`
- [ ] Constructor accepts dict of `IndicatorDefinition`
- [ ] Creates correct indicator instances from definitions
- [ ] Indicator with extra params (period, multiplier) created correctly
- [ ] Unknown indicator type raises clear error

*Integration Tests:*
- [ ] IndicatorEngine importable and instantiable with v3 config

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine
indicators = {'rsi_14': IndicatorDefinition(type='rsi', period=14)}
engine = IndicatorEngine(indicators)
print('IndicatorEngine v3 init: OK')
"
```

**Acceptance Criteria:**
- [ ] Constructor signature matches ARCHITECTURE.md lines 297-307
- [ ] Existing tests updated or new tests added
- [ ] Unit tests pass

---

### Task 2.2: Update IndicatorEngine.compute() Method

**File(s):** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Update `compute()` method to use standardized indicator outputs and produce correctly-named columns.

**Implementation Notes:**

Key behaviors:
1. Accept `indicator_ids: set[str]` specifying which indicators to compute
2. For single-output indicators: column name is `indicator_id`
3. For multi-output indicators: column names are `indicator_id.output_name`

```python
def compute(
    self,
    data: pd.DataFrame,
    indicator_ids: set[str]
) -> pd.DataFrame:
    """
    Compute specified indicators on data.

    Args:
        data: OHLCV DataFrame
        indicator_ids: Which indicators to compute

    Returns:
        DataFrame with indicator columns:
        - Single-output: {indicator_id}
        - Multi-output: {indicator_id}.{output_name}

    NOTE: No timeframe prefix added here - caller handles that.
    """
    result = data.copy()

    for indicator_id in indicator_ids:
        if indicator_id not in self._indicators:
            raise ValueError(f"Unknown indicator: {indicator_id}")

        indicator = self._indicators[indicator_id]
        output = indicator.compute(data)

        if indicator.is_multi_output():
            # Validate outputs match expected
            expected = set(indicator.get_output_names())
            actual = set(output.columns)
            if expected != actual:
                raise ValueError(
                    f"Indicator {indicator_id} output mismatch: "
                    f"expected {expected}, got {actual}"
                )

            # Rename columns with indicator_id prefix
            for col in output.columns:
                result[f"{indicator_id}.{col}"] = output[col]
        else:
            # Single output - name with indicator_id
            result[indicator_id] = output

    return result
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/indicators/test_indicator_engine_v3.py`
- [ ] Single-output indicator produces `{indicator_id}` column
- [ ] Multi-output indicator produces `{indicator_id}.{output}` columns
- [ ] Unknown indicator_id raises ValueError
- [ ] Output validation catches mismatched columns
- [ ] Multiple indicators computed in single call

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine
import pandas as pd
import numpy as np

data = pd.DataFrame({
    'open': np.random.randn(50) + 100,
    'high': np.random.randn(50) + 101,
    'low': np.random.randn(50) + 99,
    'close': np.random.randn(50) + 100,
    'volume': np.random.randint(1000, 10000, 50)
})

indicators = {
    'rsi_14': IndicatorDefinition(type='rsi', period=14),
    'bbands_20_2': IndicatorDefinition(type='bbands', period=20, multiplier=2.0),
}

engine = IndicatorEngine(indicators)
result = engine.compute(data, {'rsi_14', 'bbands_20_2'})

assert 'rsi_14' in result.columns, 'Missing rsi_14'
assert 'bbands_20_2.upper' in result.columns, 'Missing bbands_20_2.upper'
assert 'bbands_20_2.middle' in result.columns, 'Missing bbands_20_2.middle'
assert 'bbands_20_2.lower' in result.columns, 'Missing bbands_20_2.lower'
print('IndicatorEngine.compute() v3: OK')
"
```

**Acceptance Criteria:**
- [ ] Column naming matches ARCHITECTURE.md lines 309-336
- [ ] No timeframe prefix added (caller responsibility)
- [ ] Multi-output validation works
- [ ] Unit tests pass

---

### Task 2.3: Add Helper Method for Timeframe Prefixing

**File(s):** `ktrdr/indicators/indicator_engine.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Cross-Component

**Description:**
Add utility method to prefix indicator columns with timeframe. This is used by training/backtest pipelines.

**Implementation Notes:**

```python
def compute_for_timeframe(
    self,
    data: pd.DataFrame,
    timeframe: str,
    indicator_ids: set[str]
) -> pd.DataFrame:
    """
    Compute indicators and prefix columns with timeframe.

    This is a convenience method for pipelines that need
    timeframe-prefixed columns.

    Args:
        data: OHLCV DataFrame
        timeframe: Timeframe string (e.g., "5m", "1h")
        indicator_ids: Which indicators to compute

    Returns:
        DataFrame with columns like "5m_rsi_14", "5m_bbands_20_2.upper"
    """
    result = self.compute(data, indicator_ids)

    # Add timeframe prefix to indicator columns (not OHLCV)
    ohlcv_cols = {'open', 'high', 'low', 'close', 'volume'}
    rename_map = {
        col: f"{timeframe}_{col}"
        for col in result.columns
        if col not in ohlcv_cols
    }

    return result.rename(columns=rename_map)
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/indicators/test_indicator_engine_v3.py`
- [ ] Timeframe prefix added correctly
- [ ] OHLCV columns not prefixed
- [ ] Works with both single and multi-output indicators

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine
import pandas as pd
import numpy as np

data = pd.DataFrame({
    'open': [100]*30, 'high': [101]*30, 'low': [99]*30,
    'close': [100]*30, 'volume': [1000]*30
})

indicators = {'rsi_14': IndicatorDefinition(type='rsi', period=14)}
engine = IndicatorEngine(indicators)
result = engine.compute_for_timeframe(data, '5m', {'rsi_14'})

assert '5m_rsi_14' in result.columns, 'Missing 5m_rsi_14'
assert 'open' in result.columns, 'OHLCV should remain unprefixed'
print('compute_for_timeframe: OK')
"
```

**Acceptance Criteria:**
- [ ] Timeframe prefix added to indicator columns only
- [ ] OHLCV columns preserved without prefix
- [ ] Unit tests pass

---

## E2E Test Scenario

**Purpose:** Prove IndicatorEngine accepts v3 config and produces correctly-named columns
**Duration:** ~2 seconds
**Prerequisites:** M1 complete, Indicator Standardization M1-M5 complete

### Test Steps

```bash
#!/bin/bash
# M2 E2E Test: IndicatorEngine V3

set -e

echo "=== M2 E2E Test: IndicatorEngine V3 ==="

uv run python << 'EOF'
from ktrdr.config.models import IndicatorDefinition
from ktrdr.indicators.indicator_engine import IndicatorEngine
import pandas as pd
import numpy as np

# Create sample OHLCV data
np.random.seed(42)
data = pd.DataFrame({
    'open': np.cumsum(np.random.randn(100)) + 100,
    'high': np.cumsum(np.random.randn(100)) + 101,
    'low': np.cumsum(np.random.randn(100)) + 99,
    'close': np.cumsum(np.random.randn(100)) + 100,
    'volume': np.random.randint(1000, 10000, 100)
})

# V3 style: dict of indicators
indicators = {
    'rsi_14': IndicatorDefinition(type='rsi', period=14),
    'bbands_20_2': IndicatorDefinition(type='bbands', period=20, multiplier=2.0),
    'macd_12_26_9': IndicatorDefinition(type='macd', fast_period=12, slow_period=26, signal_period=9),
}

# Test 1: Constructor
print("Test 1: Constructor with dict config...")
engine = IndicatorEngine(indicators)
print("  PASS: IndicatorEngine created")

# Test 2: Compute single-output
print("Test 2: Single-output indicator...")
result = engine.compute(data, {'rsi_14'})
assert 'rsi_14' in result.columns, "Missing rsi_14 column"
print(f"  PASS: rsi_14 column present, shape={result['rsi_14'].shape}")

# Test 3: Compute multi-output
print("Test 3: Multi-output indicator...")
result = engine.compute(data, {'bbands_20_2'})
assert 'bbands_20_2.upper' in result.columns, "Missing bbands_20_2.upper"
assert 'bbands_20_2.middle' in result.columns, "Missing bbands_20_2.middle"
assert 'bbands_20_2.lower' in result.columns, "Missing bbands_20_2.lower"
print("  PASS: bbands columns present with dot notation")

# Test 4: Compute with timeframe prefix
print("Test 4: Timeframe prefixing...")
result = engine.compute_for_timeframe(data, '5m', {'rsi_14', 'bbands_20_2'})
assert '5m_rsi_14' in result.columns, "Missing 5m_rsi_14"
assert '5m_bbands_20_2.upper' in result.columns, "Missing 5m_bbands_20_2.upper"
assert 'open' in result.columns, "OHLCV columns should remain"
print("  PASS: Timeframe prefix applied correctly")

# Test 5: Multiple indicators
print("Test 5: Multiple indicators in single call...")
result = engine.compute(data, {'rsi_14', 'macd_12_26_9'})
assert 'rsi_14' in result.columns
assert 'macd_12_26_9.line' in result.columns
assert 'macd_12_26_9.signal' in result.columns
assert 'macd_12_26_9.histogram' in result.columns
print("  PASS: Multiple indicators computed")

print("\n=== M2 E2E Test: ALL PASSED ===")
EOF

echo "M2 E2E: SUCCESS"
```

### Success Criteria

- [ ] IndicatorEngine accepts dict of IndicatorDefinition
- [ ] Single-output produces `{indicator_id}` column
- [ ] Multi-output produces `{indicator_id}.{output}` columns
- [ ] Timeframe prefix works correctly
- [ ] OHLCV columns preserved

---

## Completion Checklist

- [ ] Task 2.1: IndicatorEngine constructor updated
- [ ] Task 2.2: compute() method updated for v3 naming
- [ ] Task 2.3: compute_for_timeframe() helper added
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] M1 E2E test still passes (no regression)
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
