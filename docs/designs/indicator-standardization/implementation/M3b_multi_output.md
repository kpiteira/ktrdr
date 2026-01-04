---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3b: Migrate Multi-Output Indicators

**Branch:** `feature/indicator-std-m3b-multi`
**Builds on:** M3a (single-output indicators migrated)
**Goal:** Multi-output indicators return semantic column names only; engine handles prefixing.

## E2E Test Scenario

**Purpose:** Verify multi-output indicators produce `indicator_id.output` column format
**Duration:** ~60 seconds
**Prerequisites:** M3a complete, development environment running

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

# 2. Verify multi-output indicators produce correct column names
uv run python -c "
from ktrdr.indicators import IndicatorEngine, BollingerBandsIndicator, MACDIndicator, StochasticIndicator
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=100)

engine = IndicatorEngine()

# BollingerBands
bbands = BollingerBandsIndicator(period=20, multiplier=2.0)
result = engine.compute_indicator(data, bbands, 'bbands_20_2')
expected = ['bbands_20_2.upper', 'bbands_20_2.middle', 'bbands_20_2.lower', 'bbands_20_2']
for col in expected:
    assert col in result.columns, f'Missing column: {col}'
print('BollingerBands:', list(result.columns), '✓')

# MACD
macd = MACDIndicator(fast_period=12, slow_period=26, signal_period=9)
result = engine.compute_indicator(data, macd, 'macd_12_26_9')
expected = ['macd_12_26_9.line', 'macd_12_26_9.signal', 'macd_12_26_9.histogram', 'macd_12_26_9']
for col in expected:
    assert col in result.columns, f'Missing column: {col}'
print('MACD:', list(result.columns), '✓')

# Stochastic
stoch = StochasticIndicator(k_period=14, d_period=3)
result = engine.compute_indicator(data, stoch, 'stoch_14_3')
expected = ['stoch_14_3.k', 'stoch_14_3.d', 'stoch_14_3']
for col in expected:
    assert col in result.columns, f'Missing column: {col}'
print('Stochastic:', list(result.columns), '✓')

print('SUCCESS: Multi-output indicators migrated')
"
```

**Success Criteria:**

- [ ] v2 smoke test passes: training completes
- [ ] v2 smoke test passes: backtesting completes (model loads correctly)
- [ ] Multi-output indicators return DataFrames with semantic column names only
- [ ] IndicatorEngine prefixes columns with `indicator_id.`
- [ ] Alias column created for bare `indicator_id` references

---

## Task 3b.1: Migrate BollingerBands (Template)

**File:** `ktrdr/indicators/bollinger_bands_indicator.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Persistence (indicator persists to DataFrame columns), Cross-Component (template for other migrations)

**Description:**
Migrate BollingerBands first as a template for other multi-output indicators. This establishes the pattern.

**Implementation Notes:**
- Change `compute()` to return DataFrame with semantic column names only: `upper`, `middle`, `lower`
- Remove parameter embedding from column names
- Remove `get_column_name()` override — will be removed in M6
- `get_output_names()` already returns `["upper", "middle", "lower"]` (from M1)

**Before:**
```python
def compute(self, data: pd.DataFrame) -> pd.DataFrame:
    # ... calculation ...
    suffix = f"{self.params['period']}_{self.params['multiplier']}"
    return pd.DataFrame({
        f"upper_{suffix}": upper_band,
        f"middle_{suffix}": middle_band,
        f"lower_{suffix}": lower_band,
    }, index=data.index)
```

**After:**
```python
def compute(self, data: pd.DataFrame) -> pd.DataFrame:
    # ... calculation ...
    return pd.DataFrame({
        "upper": upper_band,
        "middle": middle_band,
        "lower": lower_band,
    }, index=data.index)
```

**Tests:**
- Unit: `tests/unit/indicators/test_multi_output_migration.py` (new file)
- What to test:
  - `compute()` returns DataFrame with exactly `["upper", "middle", "lower"]` columns
  - Column names match `get_output_names()` exactly
  - Values are correct (regression test)
  - Works through `compute_indicator()` with prefixing

**Acceptance Criteria:**
- [ ] `compute()` returns semantic column names only
- [ ] Column names match `get_output_names()` exactly
- [ ] Values unchanged (regression test)
- [ ] Works through adapter with prefixing

---

## Task 3b.2: Migrate Core Multi-Output Indicators

**File(s):** 5 indicator files
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Persistence (indicators persist to DataFrame columns)

**Description:**
Migrate the most commonly used multi-output indicators following the BollingerBands pattern.

**Files to modify:**
1. `ktrdr/indicators/macd_indicator.py` → columns: `line`, `signal`, `histogram`
2. `ktrdr/indicators/stochastic_indicator.py` → columns: `k`, `d`
3. `ktrdr/indicators/adx_indicator.py` → columns: `adx`, `plus_di`, `minus_di`
4. `ktrdr/indicators/aroon_indicator.py` → columns: `up`, `down`, `oscillator`
5. `ktrdr/indicators/supertrend_indicator.py` → columns: `trend`, `direction`

**Implementation Notes:**
- Follow BollingerBands pattern from Task 3b.1
- Ensure column names match `get_output_names()` exactly
- Remove parameter embedding from column names
- Be careful with MACD — it has special handling currently

**MACD Before:**
```python
def compute(self, data: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        f"MACD_{fast}_{slow}": macd_line,
        f"MACD_signal_{fast}_{slow}_{signal}": signal_line,
        f"MACD_hist_{fast}_{slow}_{signal}": histogram,
    }, index=data.index)
```

**MACD After:**
```python
def compute(self, data: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        "line": macd_line,
        "signal": signal_line,
        "histogram": histogram,
    }, index=data.index)
```

**Tests:**
- Add to `tests/unit/indicators/test_multi_output_migration.py`
- What to test per indicator:
  - Column names match `get_output_names()` exactly
  - Values are correct

**Acceptance Criteria:**
- [ ] All 5 indicators return semantic column names only
- [ ] Column names match `get_output_names()` for each
- [ ] Works through adapter with prefixing

---

## Task 3b.3: Migrate Remaining Multi-Output Indicators

**File(s):** 4 indicator files
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Persistence (indicators persist to DataFrame columns)

**Description:**
Migrate the remaining multi-output indicators.

**Files to modify:**
1. `ktrdr/indicators/ichimoku_indicator.py` → columns: `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou`
2. `ktrdr/indicators/donchian_channels.py` → columns: `upper`, `middle`, `lower`
3. `ktrdr/indicators/keltner_channels.py` → columns: `upper`, `middle`, `lower`
4. `ktrdr/indicators/fisher_transform.py` → columns: `fisher`, `signal`

**Implementation Notes:**
- Follow BollingerBands pattern
- Ichimoku has 5 outputs — be careful with the order
- Donchian and Keltner are similar to BollingerBands

**Tests:**
- Add to `tests/unit/indicators/test_multi_output_migration.py`
- What to test:
  - Column names match `get_output_names()` for each

**Acceptance Criteria:**
- [ ] All 4 indicators return semantic column names only
- [ ] All multi-output indicators now migrated
- [ ] Integration test from M1 passes (verifies all indicators)

---

## Milestone 3b Verification

### E2E Regression Test

```bash
# Verify ALL multi-output indicators produce new format
uv run python -c "
from ktrdr.indicators import IndicatorEngine
from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
from ktrdr.data import DataManager

dm = DataManager()
data = dm.load('EURUSD', '1h', limit=200)

engine = IndicatorEngine()

# Test all multi-output indicators
multi_output_map = {
    'bbands': ['upper', 'middle', 'lower'],
    'macd': ['line', 'signal', 'histogram'],
    'stochastic': ['k', 'd'],
    'adx': ['adx', 'plus_di', 'minus_di'],
    'aroon': ['up', 'down', 'oscillator'],
    'ichimoku': ['tenkan', 'kijun', 'senkou_a', 'senkou_b', 'chikou'],
    'supertrend': ['trend', 'direction'],
    'donchian': ['upper', 'middle', 'lower'],
    'keltner': ['upper', 'middle', 'lower'],
    'fisher': ['fisher', 'signal'],
}

for indicator_type, expected_outputs in multi_output_map.items():
    if indicator_type not in BUILT_IN_INDICATORS:
        print(f'SKIP: {indicator_type} not in registry')
        continue

    indicator_class = BUILT_IN_INDICATORS[indicator_type]

    # Create with default params
    try:
        indicator = indicator_class()
    except TypeError:
        # Try with common params
        if indicator_type == 'bbands':
            indicator = indicator_class(period=20, multiplier=2.0)
        elif indicator_type == 'macd':
            indicator = indicator_class(fast_period=12, slow_period=26, signal_period=9)
        else:
            indicator = indicator_class(period=14)

    indicator_id = f'{indicator_type}_test'
    result = engine.compute_indicator(data, indicator, indicator_id)

    # Verify prefixed columns exist
    for output in expected_outputs:
        col = f'{indicator_id}.{output}'
        assert col in result.columns, f'{indicator_type}: missing {col}'

    # Verify alias exists
    assert indicator_id in result.columns, f'{indicator_type}: missing alias {indicator_id}'

    print(f'{indicator_type}: ✓ ({len(result.columns)} columns)')

print('SUCCESS: All multi-output indicators migrated')
"
```

### Completion Checklist

- [ ] Task 3b.1: BollingerBands migrated (template)
- [ ] Task 3b.2: Core multi-output indicators migrated (5 files)
- [ ] Task 3b.3: Remaining multi-output indicators migrated (4 files)
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] v2 smoke test passes
- [ ] M1 integration test passes (all indicators follow standard)
- [ ] M3a single-output still works

### Definition of Done

At the end of M3b:
- All multi-output indicators return semantic column names only (`upper`, `signal`, etc.)
- IndicatorEngine prefixes with `indicator_id.` (e.g., `bbands_20_2.upper`)
- Alias columns exist for bare `indicator_id` references
- v2 strategies work with new format
- Ready for M4: update consumers to use new format directly
