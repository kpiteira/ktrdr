---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: FuzzyEngine V3

**Branch:** `feature/strategy-grammar-v3-m3`
**Prerequisite:** M2 complete (IndicatorEngine v3 works)
**Builds on:** M2 IndicatorEngine

## Goal

FuzzyEngine accepts v3-style fuzzy_sets configuration with explicit indicator references and produces correctly-named membership columns.

## Why This Milestone

- Bridges v3 config format to fuzzy logic computation
- Uses `fuzzy_set_id` as primary key (not indicator name)
- Enables M4 (Training Pipeline) which combines indicators + fuzzy

---

## Tasks

### Task 3.1: Update FuzzyEngine Constructor

**File(s):** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Wiring/DI, Cross-Component

**Description:**
Modify `FuzzyEngine` to accept v3-style fuzzy_sets dict with explicit indicator references.

**Implementation Notes:**

Key change: In v3, fuzzy_set_id is decoupled from indicator_id. Multiple fuzzy sets can reference the same indicator.

```python
class FuzzyEngine:
    def __init__(self, fuzzy_sets: dict[str, FuzzySetDefinition]):
        """
        Args:
            fuzzy_sets: Dict mapping fuzzy_set_id to definition
                       Each definition has an 'indicator' field
        """
        self._fuzzy_sets: dict[str, dict[str, MembershipFunction]] = {}
        self._indicator_map: dict[str, str] = {}  # fuzzy_set_id -> indicator_id

        for fuzzy_set_id, definition in fuzzy_sets.items():
            self._fuzzy_sets[fuzzy_set_id] = self._build_membership_functions(
                definition
            )
            self._indicator_map[fuzzy_set_id] = definition.indicator

    def _build_membership_functions(
        self,
        definition: FuzzySetDefinition
    ) -> dict[str, MembershipFunction]:
        """Build MembershipFunction objects from definition."""
        result = {}
        for name in definition.get_membership_names():
            membership_def = getattr(definition, name)
            # membership_def is already expanded to {type, parameters}
            result[name] = self._create_membership_function(membership_def)
        return result

    def get_indicator_for_fuzzy_set(self, fuzzy_set_id: str) -> str:
        """Get the indicator_id that a fuzzy_set references."""
        return self._indicator_map[fuzzy_set_id]
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/fuzzy/test_fuzzy_engine_v3.py`
- [ ] Constructor accepts dict of FuzzySetDefinition
- [ ] Builds membership functions correctly
- [ ] `get_indicator_for_fuzzy_set()` returns correct indicator
- [ ] Multiple fuzzy sets referencing same indicator handled
- [ ] Dot notation indicator reference preserved (e.g., `bbands_20_2.upper`)

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.fuzzy.engine import FuzzyEngine

fuzzy_sets = {
    'rsi_fast': FuzzySetDefinition(
        indicator='rsi_14',
        oversold={'type': 'triangular', 'parameters': [0, 25, 40]},
        overbought={'type': 'triangular', 'parameters': [60, 75, 100]},
    ),
}

engine = FuzzyEngine(fuzzy_sets)
assert engine.get_indicator_for_fuzzy_set('rsi_fast') == 'rsi_14'
print('FuzzyEngine v3 init: OK')
"
```

**Acceptance Criteria:**
- [ ] Constructor signature matches ARCHITECTURE.md lines 386-397
- [ ] Indicator map correctly populated
- [ ] Unit tests pass

---

### Task 3.2: Update FuzzyEngine.fuzzify() Method

**File(s):** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Cross-Component

**Description:**
Update `fuzzify()` method to use `fuzzy_set_id` as primary key and produce correctly-named columns.

**Implementation Notes:**

Key change: Column names are `{fuzzy_set_id}_{membership}` not `{indicator_id}_{membership}`.

```python
def fuzzify(
    self,
    fuzzy_set_id: str,
    indicator_values: pd.Series,
) -> pd.DataFrame:
    """
    Apply fuzzy set to indicator values.

    Args:
        fuzzy_set_id: Which fuzzy set to apply
        indicator_values: Raw indicator values (Series)

    Returns:
        DataFrame with columns: {fuzzy_set_id}_{membership}
        NOTE: No timeframe prefix - caller adds that.
    """
    if fuzzy_set_id not in self._fuzzy_sets:
        raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

    fuzzy_set = self._fuzzy_sets[fuzzy_set_id]
    result = {}

    for membership_name, mf in fuzzy_set.items():
        col_name = f"{fuzzy_set_id}_{membership_name}"
        result[col_name] = mf.evaluate(indicator_values)

    return pd.DataFrame(result, index=indicator_values.index)
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/fuzzy/test_fuzzy_engine_v3.py`
- [ ] `fuzzify()` returns DataFrame with correct columns
- [ ] Column names follow `{fuzzy_set_id}_{membership}` pattern
- [ ] Unknown fuzzy_set_id raises ValueError
- [ ] Membership values computed correctly (triangular, trapezoidal)
- [ ] NaN handling in indicator values

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.fuzzy.engine import FuzzyEngine
import pandas as pd

fuzzy_sets = {
    'rsi_momentum': FuzzySetDefinition(
        indicator='rsi_14',
        oversold={'type': 'triangular', 'parameters': [0, 20, 35]},
        overbought={'type': 'triangular', 'parameters': [65, 80, 100]},
    ),
}

engine = FuzzyEngine(fuzzy_sets)
values = pd.Series([25, 50, 75])
result = engine.fuzzify('rsi_momentum', values)

assert 'rsi_momentum_oversold' in result.columns
assert 'rsi_momentum_overbought' in result.columns
print(f'Columns: {list(result.columns)}')
print('FuzzyEngine.fuzzify() v3: OK')
"
```

**Acceptance Criteria:**
- [ ] Column naming matches ARCHITECTURE.md lines 407-426
- [ ] No timeframe prefix (caller responsibility)
- [ ] Unit tests pass

---

### Task 3.3: Add Membership Name Accessor

**File(s):** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Add method to get ordered list of membership function names for a fuzzy set. Used by FeatureResolver.

**Implementation Notes:**

```python
def get_membership_names(self, fuzzy_set_id: str) -> list[str]:
    """
    Get ordered list of membership function names for a fuzzy set.

    Args:
        fuzzy_set_id: The fuzzy set to query

    Returns:
        List of membership names in definition order
        e.g., ["oversold", "neutral", "overbought"]
    """
    if fuzzy_set_id not in self._fuzzy_sets:
        raise ValueError(f"Unknown fuzzy set: {fuzzy_set_id}")

    return list(self._fuzzy_sets[fuzzy_set_id].keys())
```

**Testing Requirements:**

*Unit Tests:* `tests/unit/fuzzy/test_fuzzy_engine_v3.py`
- [ ] Returns correct membership names
- [ ] Order matches definition order
- [ ] Unknown fuzzy_set_id raises ValueError

*Smoke Test:*
```bash
uv run python -c "
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.fuzzy.engine import FuzzyEngine

fuzzy_sets = {
    'rsi_momentum': FuzzySetDefinition(
        indicator='rsi_14',
        oversold={'type': 'triangular', 'parameters': [0, 20, 35]},
        neutral={'type': 'triangular', 'parameters': [30, 50, 70]},
        overbought={'type': 'triangular', 'parameters': [65, 80, 100]},
    ),
}

engine = FuzzyEngine(fuzzy_sets)
names = engine.get_membership_names('rsi_momentum')
print(f'Membership names: {names}')
assert 'oversold' in names
assert 'neutral' in names
assert 'overbought' in names
print('get_membership_names: OK')
"
```

**Acceptance Criteria:**
- [ ] Method matches interface in SCENARIOS.md lines 293-294
- [ ] Order preserved from definition
- [ ] Unit tests pass

---

## E2E Test Scenario

**Purpose:** Prove FuzzyEngine accepts v3 config and produces correctly-named columns
**Duration:** ~2 seconds
**Prerequisites:** M2 complete

### Test Steps

```bash
#!/bin/bash
# M3 E2E Test: FuzzyEngine V3

set -e

echo "=== M3 E2E Test: FuzzyEngine V3 ==="

uv run python << 'EOF'
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.fuzzy.engine import FuzzyEngine
import pandas as pd
import numpy as np

# Test 1: Constructor with v3 config
print("Test 1: Constructor with v3 config...")
fuzzy_sets = {
    'rsi_fast': FuzzySetDefinition(
        indicator='rsi_14',
        oversold={'type': 'triangular', 'parameters': [0, 25, 40]},
        overbought={'type': 'triangular', 'parameters': [60, 75, 100]},
    ),
    'rsi_slow': FuzzySetDefinition(
        indicator='rsi_14',  # Same indicator, different interpretation
        oversold={'type': 'triangular', 'parameters': [0, 15, 25]},
        overbought={'type': 'triangular', 'parameters': [75, 85, 100]},
    ),
}

engine = FuzzyEngine(fuzzy_sets)
print("  PASS: FuzzyEngine created")

# Test 2: Indicator mapping
print("Test 2: Indicator mapping...")
assert engine.get_indicator_for_fuzzy_set('rsi_fast') == 'rsi_14'
assert engine.get_indicator_for_fuzzy_set('rsi_slow') == 'rsi_14'
print("  PASS: Both fuzzy sets reference rsi_14")

# Test 3: Fuzzification output naming
print("Test 3: Fuzzification output naming...")
values = pd.Series([10, 30, 50, 70, 90])  # Various RSI levels
result = engine.fuzzify('rsi_fast', values)
assert 'rsi_fast_oversold' in result.columns, "Missing rsi_fast_oversold"
assert 'rsi_fast_overbought' in result.columns, "Missing rsi_fast_overbought"
print(f"  PASS: Columns are {list(result.columns)}")

# Test 4: Different fuzzy set, same indicator
print("Test 4: Different interpretation of same indicator...")
result_slow = engine.fuzzify('rsi_slow', values)
assert 'rsi_slow_oversold' in result_slow.columns
assert 'rsi_slow_overbought' in result_slow.columns
print("  PASS: rsi_slow columns distinct from rsi_fast")

# Test 5: Membership values make sense
print("Test 5: Membership value sanity check...")
# At RSI=10, rsi_fast_oversold should be high, overbought should be 0
assert result.loc[0, 'rsi_fast_oversold'] > 0.5, "RSI 10 should be oversold"
assert result.loc[0, 'rsi_fast_overbought'] == 0, "RSI 10 should not be overbought"
# At RSI=90, opposite
assert result.loc[4, 'rsi_fast_overbought'] > 0.5, "RSI 90 should be overbought"
assert result.loc[4, 'rsi_fast_oversold'] == 0, "RSI 90 should not be oversold"
print("  PASS: Membership values are sensible")

# Test 6: Membership names accessor
print("Test 6: get_membership_names()...")
names = engine.get_membership_names('rsi_fast')
assert 'oversold' in names
assert 'overbought' in names
print(f"  PASS: Membership names: {names}")

print("\n=== M3 E2E Test: ALL PASSED ===")
EOF

echo "M3 E2E: SUCCESS"
```

### Success Criteria

- [ ] FuzzyEngine accepts dict of FuzzySetDefinition
- [ ] Multiple fuzzy sets can reference same indicator
- [ ] Column names are `{fuzzy_set_id}_{membership}`
- [ ] Membership values computed correctly
- [ ] `get_membership_names()` works

---

## Completion Checklist

- [ ] Task 3.1: FuzzyEngine constructor updated
- [ ] Task 3.2: fuzzify() method updated for v3 naming
- [ ] Task 3.3: get_membership_names() added
- [ ] All unit tests pass: `make test-unit`
- [ ] E2E test script passes
- [ ] M1, M2 E2E tests still pass (no regression)
- [ ] Quality gates pass: `make quality`
- [ ] Code reviewed and merged
