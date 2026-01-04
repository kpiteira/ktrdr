---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3a: Migrate Single-Output Indicators

**Branch:** `feature/indicator-std-m3a-single`
**Builds on:** M2 (adapter handles both formats)
**Goal:** Single-output indicators return unnamed Series; engine handles naming.

## E2E Test Scenario

**Purpose:** Verify single-output indicators work through adapter with new format
**Duration:** ~60 seconds
**Prerequisites:** M2 complete, development environment running

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

# 2. Verify single-output indicators produce correct column names
uv run python -c "
from ktrdr.indicators import IndicatorEngine, RSIIndicator, ATRIndicator, SMAIndicator
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=100)

engine = IndicatorEngine()

# RSI
rsi = RSIIndicator(period=14)
result = engine.compute_indicator(data, rsi, 'rsi_14')
assert 'rsi_14' in result.columns, f'Expected rsi_14, got {list(result.columns)}'
assert len(result.columns) == 1, f'Single-output should have 1 column, got {len(result.columns)}'
print('RSI: rsi_14 ✓')

# ATR
atr = ATRIndicator(period=14)
result = engine.compute_indicator(data, atr, 'atr_14')
assert 'atr_14' in result.columns
print('ATR: atr_14 ✓')

# SMA
sma = SMAIndicator(period=20)
result = engine.compute_indicator(data, sma, 'sma_20')
assert 'sma_20' in result.columns
print('SMA: sma_20 ✓')

print('SUCCESS: Single-output indicators migrated')
"
```

**Success Criteria:**

- [ ] v2 smoke test passes: training completes
- [ ] v2 smoke test passes: backtesting completes (model loads correctly)
- [ ] Single-output indicators return unnamed Series
- [ ] IndicatorEngine names columns with `indicator_id`
- [ ] No old-format column names (e.g., `RSI_14` or `rsi_14` from indicator)

---

## Task 3a.1: Migrate Momentum/Oscillator Indicators

**File(s):** 8 indicator files
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Persistence (indicators persist to DataFrame columns)

**Description:**
Migrate the momentum and oscillator single-output indicators to return unnamed Series.

**Files to modify:**
1. `ktrdr/indicators/rsi_indicator.py` — Remove `.name` assignment
2. `ktrdr/indicators/cci_indicator.py` — Remove `.name` assignment
3. `ktrdr/indicators/mfi_indicator.py` — Remove `.name` assignment
4. `ktrdr/indicators/roc_indicator.py` — Remove `.name` assignment
5. `ktrdr/indicators/momentum_indicator.py` — Remove `.name` assignment
6. `ktrdr/indicators/williams_r_indicator.py` — Remove `.name` assignment
7. `ktrdr/indicators/rvi_indicator.py` — Check if actually single-output, then migrate
8. `ktrdr/indicators/squeeze_intensity_indicator.py` — Remove `.name` assignment

**Implementation Notes:**
- Find the line where `.name` is assigned to the Series
- Remove that line (or the `name=` parameter in Series constructor)
- Do NOT remove `get_column_name()` method if present — will be removed in M6
- Verify `is_multi_output()` returns `False` (or is not overridden)

**Before (RSI example):**
```python
def compute(self, df: pd.DataFrame) -> pd.Series:
    # ... calculation ...
    rsi.name = self.get_column_name()  # or rsi.name = f"RSI_{period}"
    return rsi
```

**After:**
```python
def compute(self, df: pd.DataFrame) -> pd.Series:
    # ... calculation ...
    return rsi  # No name - IndicatorEngine handles naming
```

**Tests:**
- Unit: `tests/unit/indicators/test_single_output_migration.py` (new file)
- What to test per indicator:
  - `compute()` returns Series (not DataFrame)
  - Returned Series has no `.name` (or name is None)
  - Values are correct (spot check)

**Acceptance Criteria:**
- [ ] All 8 indicators return unnamed Series
- [ ] Indicator values unchanged (regression test)
- [ ] Works through `compute_indicator()` with adapter

---

## Task 3a.2: Migrate Volume/Trend Indicators

**File(s):** 6 indicator files
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Persistence (indicators persist to DataFrame columns)

**Description:**
Migrate the volume and trend-based single-output indicators.

**Files to modify:**
1. `ktrdr/indicators/obv_indicator.py` — Remove `.name` assignment
2. `ktrdr/indicators/cmf_indicator.py` — Remove `.name` assignment
3. `ktrdr/indicators/vwap_indicator.py` — Remove `.name` assignment
4. `ktrdr/indicators/volume_ratio_indicator.py` — Remove `.name` assignment
5. `ktrdr/indicators/ad_line.py` — Remove `.name` assignment
6. `ktrdr/indicators/atr_indicator.py` — Remove `.name` assignment

**Implementation Notes:**
Same as Task 3a.1 — remove `.name` assignment from returned Series.

**Tests:**
- Add to `tests/unit/indicators/test_single_output_migration.py`
- What to test per indicator:
  - `compute()` returns unnamed Series
  - Values are correct

**Acceptance Criteria:**
- [ ] All 6 indicators return unnamed Series
- [ ] Indicator values unchanged
- [ ] Works through adapter

---

## Task 3a.3: Migrate Remaining Single-Output Indicators

**File(s):** 6 indicator files + MA indicators
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Persistence (indicators persist to DataFrame columns)

**Description:**
Migrate the remaining single-output indicators including moving averages.

**Files to modify:**
1. `ktrdr/indicators/distance_from_ma_indicator.py` — Remove `.name` assignment
2. `ktrdr/indicators/bollinger_band_width_indicator.py` — Remove `.name` assignment
3. `ktrdr/indicators/parabolic_sar_indicator.py` — Remove `.name` assignment
4. `ktrdr/indicators/zigzag_indicator.py` — Remove `.name` assignment
5. `ktrdr/indicators/ma_indicators.py`:
   - `SMAIndicator` — Remove `.name` assignment
   - `EMAIndicator` — Remove `.name` assignment
   - Any other MA variants (WMA, etc.)

**Implementation Notes:**
Same as Task 3a.1 — remove `.name` assignment from returned Series.

**Tests:**
- Add to `tests/unit/indicators/test_single_output_migration.py`
- What to test:
  - Each indicator returns unnamed Series
  - MA indicators (SMA, EMA) return unnamed Series

**Acceptance Criteria:**
- [ ] All remaining single-output indicators return unnamed Series
- [ ] MA indicators migrated
- [ ] Works through adapter
- [ ] Integration test from M1 still passes

---

## Milestone 3a Verification

### E2E Regression Test

```bash
# Verify ALL single-output indicators work through adapter
uv run python -c "
from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.data import DataManager
import pandas as pd

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

engine = IndicatorEngine()

# Test all single-output indicators
single_output_types = [
    'rsi', 'atr', 'cci', 'cmf', 'mfi', 'obv', 'roc', 'momentum',
    'williams_r', 'vwap', 'volume_ratio', 'distance_from_ma',
    'bollinger_band_width', 'squeeze_intensity', 'parabolic_sar',
    'zigzag', 'ad_line', 'sma', 'ema'
]

for indicator_type in single_output_types:
    if indicator_type not in BUILT_IN_INDICATORS:
        print(f'SKIP: {indicator_type} not in registry')
        continue

    indicator_class = BUILT_IN_INDICATORS[indicator_type]
    if indicator_class.is_multi_output():
        print(f'SKIP: {indicator_type} is multi-output')
        continue

    # Create with default params
    try:
        indicator = indicator_class()
    except TypeError:
        indicator = indicator_class(period=14)  # Most need period

    indicator_id = f'{indicator_type}_test'
    result = engine.compute_indicator(data, indicator, indicator_id)

    assert indicator_id in result.columns, f'{indicator_type}: missing {indicator_id}'
    assert len(result.columns) == 1, f'{indicator_type}: expected 1 column, got {len(result.columns)}'
    print(f'{indicator_type}: ✓')

print('SUCCESS: All single-output indicators migrated')
"
```

### Completion Checklist

- [ ] Task 3a.1: Momentum/oscillator indicators migrated (8 files)
- [ ] Task 3a.2: Volume/trend indicators migrated (6 files)
- [ ] Task 3a.3: Remaining indicators + MAs migrated (6+ files)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v2 smoke test passes
- [ ] M1 integration test still passes
- [ ] M2 format detection still works

### Definition of Done

At the end of M3a:
- All single-output indicators return unnamed Series
- IndicatorEngine handles all naming via `indicator_id`
- v2 strategies work (feature_id becomes indicator_id)
- Ready for M3b: migrate multi-output indicators
