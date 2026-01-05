# Handoff Document: Milestone 3b (Multi-Output Indicator Migration)

This document captures patterns, gotchas, and workarounds discovered during multi-output indicator migration.

---

## Task 3b.1 Complete: BollingerBands (Template)

### Indicators Migrated

**BollingerBands** - Template indicator for multi-output migration
- **Before:** `{"upper_20_2.0", "middle_20_2.0", "lower_20_2.0"}`
- **After:** `{"upper", "middle", "lower"}`

### Implementation Pattern

**The Core Change:**
```python
# BEFORE (M2): Parameter embedding in column names
suffix = f"{period}_{multiplier}"
result = pd.DataFrame({
    f"upper_{suffix}": upper_band,
    f"middle_{suffix}": middle_band,
    f"lower_{suffix}": lower_band,
}, index=data.index)

# AFTER (M3b): Semantic names only
result = pd.DataFrame({
    "upper": upper_band,
    "middle": middle_band,
    "lower": lower_band,
}, index=data.index)
```

**Adapter Detection:**
The adapter in `indicator_engine.py` (lines 317-330) detects new-format multi-output indicators:

1. Compare `result.columns` with `get_output_names()`
2. If they match exactly → **NEW FORMAT** → apply prefixing
3. Prefix columns: `upper` becomes `bbands_20_2.upper`
4. Add alias: `bbands_20_2` points to primary output (`bbands_20_2.upper`)

**Why This Works:**
- `get_output_names()` returns `["upper", "middle", "lower"]` (from M1)
- When columns match exactly, adapter knows it's new format
- Engine handles prefixing, so multiple BBands instances don't collide

---

## Gotcha 1: Dependent Indicators

**Problem:** Some indicators depend on multi-output indicators and expect old-format column names.

**Examples Found:**
- `BollingerBandWidthIndicator` depends on `BollingerBandsIndicator`
- `SqueezeIntensityIndicator` depends on `BollingerBandsIndicator`

**Symptom:**
```python
KeyError: 'upper_20_2.0'  # Expected new format: 'upper'
```

**Solution:**
Update dependent indicators to use semantic names:
```python
# BEFORE
bb_suffix = f"{period}_{multiplier}"
upper_band = bb_data[f"upper_{bb_suffix}"]

# AFTER
upper_band = bb_data["upper"]
```

**Files Updated in Task 3b.1:**
- `bollinger_band_width_indicator.py` (lines 112-116)
- `squeeze_intensity_indicator.py` (lines 132-135)

**NOTE:** Keltner Channels is still old-format (hasn't been migrated yet), so SqueezeIntensity still uses old-format column names for Keltner bands.

---

## Gotcha 2: Test Helper Methods

**Problem:** Existing tests use helper methods that generate old-format column names.

**Example:** `test_bollinger_bands_indicator.py`
```python
# BEFORE
@staticmethod
def _get_column_names(period: int = 20, multiplier: float = 2.0):
    suffix = f"{period}_{multiplier}"
    return {
        "upper": f"upper_{suffix}",
        "middle": f"middle_{suffix}",
        "lower": f"lower_{suffix}",
    }

# AFTER
@staticmethod
def _get_column_names(period: int = 20, multiplier: float = 2.0):
    """M3b: Now returns semantic names only."""
    return {
        "upper": "upper",
        "middle": "middle",
        "lower": "lower",
    }
```

**Lesson:** Check for test helpers that embed parameters in column names.

---

## Pattern Summary

### What Changed
1. **Indicator `compute()` method:** Return DataFrame with semantic column names only
2. **Dependent indicators:** Update to use semantic names when calling migrated indicators
3. **Test helpers:** Update to return semantic names
4. **No changes needed:**
   - `get_output_names()` (already correct from M1)
   - `get_primary_output()` (returns suffix, not full column name)
   - `get_column_name()` (will be removed in M6, kept for now)

### What Didn't Need Changes
- **Adapter logic:** Already handles new format (M2)
- **Training/backtesting:** Uses `indicator_id.output` format (already compatible)
- **Old-format indicators:** Still work through adapter (backward compatibility)

---

## Next Tasks: 3b.2 and 3b.3

### Indicators to Migrate

**Task 3b.2: Core Multi-Output Indicators (5 files)**
1. MACD → `line`, `signal`, `histogram`
2. Stochastic → `k`, `d`
3. ADX → `adx`, `plus_di`, `minus_di`
4. Aroon → `up`, `down`, `oscillator`
5. Supertrend → `trend`, `direction`

**Task 3b.3: Remaining Multi-Output Indicators (4 files)**
1. Ichimoku → `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou`
2. Donchian Channels → `upper`, `middle`, `lower`
3. Keltner Channels → `upper`, `middle`, `lower`
4. Fisher Transform → `fisher`, `signal`

### Checklist Per Indicator

1. ☐ Change `compute()` to return semantic column names (remove parameter embedding)
2. ☐ Verify `get_output_names()` matches exactly (should already be correct from M1)
3. ☐ Check for dependent indicators (grep for the indicator class name in other files)
4. ☐ Update any test helpers that generate column names
5. ☐ Add migration tests to `test_multi_output_migration.py`
6. ☐ Run unit tests to catch dependent indicators

### Expected Challenges

**Keltner Channels (Task 3b.3):**
- `SqueezeIntensityIndicator` depends on it
- Will need to update SqueezeIntensity again after migrating Keltner

**MACD (Task 3b.2):**
- May have special handling in some places (check strategy configs)
- Verify column names match `get_output_names()` exactly

---

## Milestone Progress

- ✅ Task 3b.1: BollingerBands migrated (template established)
- ⏳ Task 3b.2: Core multi-output indicators (next)
- ⏳ Task 3b.3: Remaining multi-output indicators

**Total migrated:** 1 multi-output indicator
**Remaining:** 9 multi-output indicators
