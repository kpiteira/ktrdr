---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Update Consumers

**Branch:** `feature/indicator-std-m4-consumers`
**Builds on:** M3b (all indicators migrated to semantic names)
**Goal:** Consumers use new column format directly; simplified lookup logic.

## E2E Test Scenario

**Purpose:** Verify full pipeline works with new column format
**Duration:** ~90 seconds
**Prerequisites:** M3b complete, development environment running

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

# 2. Verify FeatureCache works with new format
uv run python -c "
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.indicators import IndicatorFactory, IndicatorEngine
from ktrdr.data import DataManager
import pandas as pd

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

# Create indicators
factory = IndicatorFactory([
    {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
    {'name': 'bbands', 'feature_id': 'bbands_20_2', 'period': 20, 'multiplier': 2.0},
])
indicators = factory.build()
engine = IndicatorEngine(indicators)
indicators_df = engine.apply(data)

# Create feature cache
cache = FeatureCache(indicators_df)

# Test lookup with new format
idx = 50  # Some row index

# Single-output: direct lookup
rsi_value = cache.get_indicator_value('rsi_14', idx)
assert rsi_value is not None, 'Failed to get rsi_14'
print(f'rsi_14 at idx {idx}: {rsi_value:.2f} ✓')

# Multi-output: bare reference (should get primary output)
bbands_value = cache.get_indicator_value('bbands_20_2', idx)
assert bbands_value is not None, 'Failed to get bbands_20_2'
print(f'bbands_20_2 at idx {idx}: {bbands_value:.2f} ✓')

# Multi-output: dot notation
upper_value = cache.get_indicator_value('bbands_20_2.upper', idx)
assert upper_value is not None, 'Failed to get bbands_20_2.upper'
print(f'bbands_20_2.upper at idx {idx}: {upper_value:.2f} ✓')

print('SUCCESS: FeatureCache works with new format')
"

# 4. Verify FuzzyEngine works
uv run python -c "
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.indicators import IndicatorFactory, IndicatorEngine
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

factory = IndicatorFactory([
    {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
])
indicators = factory.build()
engine = IndicatorEngine(indicators)
indicators_df = engine.apply(data)

# Create fuzzy engine with fuzzy set config
fuzzy_config = {
    'fuzzy_sets': [
        {
            'name': 'rsi_oversold',
            'indicator': 'rsi_14',
            'type': 'triangular',
            'params': {'low': 0, 'mid': 30, 'high': 40}
        }
    ]
}

fuzzy = FuzzyEngine(fuzzy_config)
result = fuzzy.fuzzify(indicators_df)

# Check fuzzy columns exist
assert any('rsi_oversold' in col for col in result.columns), 'Fuzzy output missing'
print('SUCCESS: FuzzyEngine works with new format')
"
```

**Success Criteria:**

- [ ] v2 smoke test passes: training completes
- [ ] v2 smoke test passes: backtesting completes (model loads correctly)
- [ ] FeatureCache uses simplified lookup (direct column access)
- [ ] FuzzyEngine expects `feature_id` format
- [ ] Training pipeline works end-to-end

---

## Task 4.1: Update FeatureCache

**File:** `ktrdr/backtesting/feature_cache.py`
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Persistence (reads from DataFrame), Cross-Component (used by multiple systems)

**Description:**
Simplify FeatureCache to use direct column lookup instead of fuzzy string matching.

**Implementation Notes:**
- Current code does O(n) string matching to find columns
- New code does O(1) dict lookup (column name is exact)
- Support both bare `indicator_id` and `indicator_id.output` references
- Remove case normalization logic (everything is lowercase now)

**Before (gymnastics):**
```python
def get_indicator_value(self, feature_id: str, idx: int) -> float:
    # Current: iterate through columns, try to match
    for col in self.indicators_df.columns:
        if col.upper().startswith(feature_id.upper()):
            return self.indicators_df[col].iloc[idx]
    # ... more fallback logic ...
```

**After (simplified):**
```python
def get_indicator_value(self, feature_id: str, idx: int) -> float:
    """
    Get indicator value at index.

    Args:
        feature_id: Column name (e.g., 'rsi_14', 'bbands_20_2.upper')
        idx: Row index

    Returns:
        Indicator value at the specified index
    """
    if feature_id in self.indicators_df.columns:
        return self.indicators_df[feature_id].iloc[idx]

    # CLEANUP(v3): Remove fallback after v3 migration complete
    # Fallback: try without dot notation (for bare multi-output references)
    # This should find the alias column
    raise KeyError(f"Column '{feature_id}' not found in indicators DataFrame")
```

**Tests:**
- Unit: `tests/unit/backtesting/test_feature_cache_new_format.py` (new file)
- What to test:
  - Direct lookup works (`rsi_14` → column `rsi_14`)
  - Dot notation works (`bbands_20_2.upper` → column `bbands_20_2.upper`)
  - Alias works (`bbands_20_2` → column `bbands_20_2` which is alias)
  - KeyError raised for missing columns

**Smoke Test:**
```bash
# Verify direct lookup works
uv run python -c "
from ktrdr.backtesting.feature_cache import FeatureCache
import pandas as pd

df = pd.DataFrame({
    'rsi_14': [50, 60, 70],
    'bbands_20_2.upper': [1.1, 1.2, 1.3],
    'bbands_20_2': [1.1, 1.2, 1.3],  # alias
})
cache = FeatureCache(df)

assert cache.get_indicator_value('rsi_14', 0) == 50
assert cache.get_indicator_value('bbands_20_2.upper', 0) == 1.1
assert cache.get_indicator_value('bbands_20_2', 0) == 1.1
print('FeatureCache lookup works ✓')
"
```

**Acceptance Criteria:**
- [ ] Direct column lookup works
- [ ] Dot notation references work
- [ ] Alias references work
- [ ] Old fuzzy matching logic removed or marked for cleanup
- [ ] Error handling for missing columns

---

## Task 4.2: Update FuzzyEngine

**File:** `ktrdr/fuzzy/engine.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Cross-Component (consumes indicator values)

**Description:**
Update FuzzyEngine to expect new column format.

**Implementation Notes:**
- Fuzzy sets reference indicators by `indicator` field
- This should match column name exactly (new format)
- Remove any case normalization or column name guessing

**Current flow:**
1. Fuzzy set config has `indicator: "rsi_14"`
2. FuzzyEngine looks for column matching that name
3. Currently does fuzzy matching

**New flow:**
1. Fuzzy set config has `indicator: "rsi_14"`
2. FuzzyEngine looks for column `rsi_14` directly
3. For multi-output, config can have `indicator: "bbands_20_2.upper"`

**Tests:**
- Unit: `tests/unit/fuzzy/test_fuzzy_engine_new_format.py` (new file)
- What to test:
  - Single-output indicator lookup works
  - Multi-output with dot notation works
  - Multi-output without dot notation uses alias (primary output)

**Acceptance Criteria:**
- [ ] Direct column lookup works
- [ ] Dot notation references work
- [ ] Error messages are clear for missing columns

---

## Task 4.3: Update Training Pipeline

**File(s):** `ktrdr/training/training_pipeline.py`, `ktrdr/training/fuzzy_neural_processor.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Cross-Component (orchestrates indicator → fuzzy → neural flow)

**Description:**
Update training pipeline to work with new column format.

**Implementation Notes:**
- Training pipeline creates indicators, fuzzifies, then trains
- Feature names in model metadata should use new format
- Model input features should be consistent with new naming

**Files to check:**
1. `ktrdr/training/training_pipeline.py` — Main orchestration
2. `ktrdr/training/fuzzy_neural_processor.py` — Feature extraction
3. Any feature name mapping logic

**Tests:**
- Integration: `tests/integration/training/test_pipeline_new_format.py` (new file)
- What to test:
  - Training completes with new column format
  - Model metadata has correct feature names
  - Backtesting can load and use the model

**Acceptance Criteria:**
- [ ] Training pipeline works end-to-end
- [ ] Model metadata uses new format feature names
- [ ] Backtesting works with trained model

---

## Task 4.4: Integration Test: Full Pipeline

**File:** `tests/integration/indicators/test_full_pipeline_new_format.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Testing

**Description:**
Create comprehensive integration test for the full indicator → fuzzy → training pipeline.

**Code sketch:**
```python
import pytest
from ktrdr.indicators import IndicatorFactory, IndicatorEngine
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.backtesting.feature_cache import FeatureCache
from ktrdr.data import DataManager

def test_full_pipeline_new_format():
    """Test complete flow from indicators to fuzzification."""
    # 1. Load data
    dm = DataManager()
    data = dm.load('EURUSD', '1h', limit=200)

    # 2. Create and apply indicators
    factory = IndicatorFactory([
        {'name': 'rsi', 'feature_id': 'rsi_14', 'period': 14},
        {'name': 'bbands', 'feature_id': 'bbands_20_2', 'period': 20, 'multiplier': 2.0},
        {'name': 'macd', 'feature_id': 'macd_12_26_9', 'fast_period': 12, 'slow_period': 26, 'signal_period': 9},
    ])
    indicators = factory.build()
    engine = IndicatorEngine(indicators)
    indicators_df = engine.apply(data)

    # 3. Verify column format
    assert 'rsi_14' in indicators_df.columns
    assert 'bbands_20_2.upper' in indicators_df.columns
    assert 'bbands_20_2.middle' in indicators_df.columns
    assert 'bbands_20_2.lower' in indicators_df.columns
    assert 'bbands_20_2' in indicators_df.columns  # alias
    assert 'macd_12_26_9.line' in indicators_df.columns
    assert 'macd_12_26_9' in indicators_df.columns  # alias

    # 4. Test FeatureCache
    cache = FeatureCache(indicators_df)
    idx = 50

    rsi_val = cache.get_indicator_value('rsi_14', idx)
    assert 0 <= rsi_val <= 100

    upper_val = cache.get_indicator_value('bbands_20_2.upper', idx)
    assert upper_val > 0

    # Using alias
    bbands_val = cache.get_indicator_value('bbands_20_2', idx)
    assert bbands_val == upper_val  # alias points to primary (upper)

    # 5. Test FuzzyEngine
    fuzzy_config = {
        'fuzzy_sets': [
            {
                'name': 'rsi_oversold',
                'indicator': 'rsi_14',
                'type': 'triangular',
                'params': {'low': 0, 'mid': 30, 'high': 40}
            },
            {
                'name': 'price_at_upper_band',
                'indicator': 'bbands_20_2.upper',
                'type': 'gaussian',
                'params': {'mean': 0, 'std': 0.01}
            }
        ]
    }
    fuzzy = FuzzyEngine(fuzzy_config)
    fuzzy_df = fuzzy.fuzzify(indicators_df)

    assert any('rsi_oversold' in col for col in fuzzy_df.columns)
    assert any('price_at_upper_band' in col for col in fuzzy_df.columns)
```

**Tests:**
- This IS the test file

**Acceptance Criteria:**
- [ ] Test covers indicator computation with new format
- [ ] Test covers FeatureCache lookup
- [ ] Test covers FuzzyEngine with both single and multi-output
- [ ] Test passes end-to-end

---

## Milestone 4 Verification

### E2E Full Training Test

```bash
# Run actual training with v2 strategy
uv run ktrdr models train strategies/mean_reversion_momentum_v1.yaml EURUSD 1h 

# Verify model was created
ls -la models/rsi_mean_reversion/

# Run backtest with trained model
uv run ktrdr backtest run mean_reversion_momentum_v1 EURUSD 1h  
```

### Completion Checklist

- [ ] Task 4.1: FeatureCache updated
- [ ] Task 4.2: FuzzyEngine updated
- [ ] Task 4.3: Training pipeline updated
- [ ] Task 4.4: Integration test passes
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v2 smoke test passes (full training)
- [ ] M1-M3 E2E tests still pass

### Definition of Done

At the end of M4:
- All consumers use new column format directly
- No fuzzy string matching for column lookup
- Full pipeline works: indicators → fuzzy → training → backtest
- v2 strategies train and backtest successfully
- Ready for M5: v3 Ready checkpoint
