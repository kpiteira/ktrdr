# Milestone 3a Handoff: Single-Output Indicator Migration

This handoff captures gotchas, workarounds, and patterns discovered during M3a implementation.

---

## Task 3a.1 Complete: Momentum/Oscillator Indicators

### Emergent Patterns

#### Pattern 1: Two Ways to Remove Names

**Pattern:** Series can have names in two ways - need different removal approaches

**Method 1: Direct .name assignment**
```python
# BEFORE (old format)
rsi.name = self.get_feature_id()
return rsi

# AFTER (M3a format)
# M3a: Return unnamed Series (engine handles naming)
return rsi
```

**Method 2: name= parameter in constructor**
```python
# BEFORE (old format)
result_series = pd.Series(williams_r, index=data.index, name=f"WilliamsR_{period}")

# AFTER (M3a format)
# M3a: Create unnamed Series (engine handles naming)
result_series = pd.Series(williams_r, index=data.index)
```

**Why both exist:**
- Pattern 1: Name assigned after calculation
- Pattern 2: Name set during Series construction

---

#### Pattern 2: Name Inheritance from Source Series

**Gotcha:** Series operations inherit .name from source Series

```python
# PROBLEM CODE (inherits 'close' name from data['close'])
price_series = data[source]  # source='close', so name='close'
momentum = price_series - price_series.shift(period)  # Still named 'close'!
result_series = pd.Series(momentum, index=data.index)  # STILL NAMED 'close'
return result_series  # ❌ Returns Series(name='close'), not unnamed!
```

**Symptom:** Tests fail with `assert 'close' is None` instead of expected `assert None is None`

**Solution:** Use `.values` to strip the name
```python
# CORRECT CODE
price_series = data[source]
momentum = price_series - price_series.shift(period)
# Use .values to avoid inheriting name from source Series
result_series = pd.Series(momentum.values, index=data.index)
return result_series  # ✅ Returns unnamed Series
```

**Which indicators need this:**
- Any indicator that operates on a Series and returns the result directly
- Examples: ROC, Momentum (both operate on price_series)
- Counter-examples: RSI, Williams%R (create new Series from scratch)

**How to detect:**
- If your indicator does: `data[source]` then operates on that Series
- If tests show `assert 'close' is None` (or 'open', 'high', etc.)
- If the indicator just transforms a single column

---

#### Pattern 3: Already-Migrated Indicators

**Gotcha:** Some indicators already returned unnamed Series (pre-M3a)

**Indicators found already migrated:**
- CCI: Returns Series from calculation, no name assignment
- MFI: Returns Series from calculation, no name assignment

**How to identify:**
- No `.name =` assignments in compute()
- No `name=` parameter in Series constructor
- Tests already pass without changes

**What to do:**
- Mark as "already migrated" in commit message
- No code changes needed
- May add comment: `# Already returns unnamed Series (M3a-compliant)`

---

#### Pattern 4: Multi-Output Indicators (Skip for M3a)

**Gotcha:** Some indicators are multi-output, not single-output

**How to identify:**
```python
@classmethod
def is_multi_output(cls) -> bool:
    return True  # ← Multi-output!
```

**What to do:**
- Skip in M3a (single-output migration)
- Will be handled in M3b (multi-output migration)
- Add test skip condition:
```python
if indicator.is_multi_output():
    pytest.skip("Indicator is multi-output, will be handled in M3b")
```

**Example:** RVI indicator (returns both RVI and Signal lines)

---

### Test Patterns

#### Update Existing Tests

**Gotcha:** Old tests expect named Series, will fail after migration

**Pattern:** Update assertions to expect None
```python
# BEFORE
assert result.name == "WilliamsR_14"

# AFTER
# M3a: Williams%R returns unnamed Series (engine handles naming)
assert result.name is None
```

**How to find:**
- Search for `assert.*\.name\s*==` in test files
- Run tests, look for `AssertionError: assert None == 'IndicatorName'`

**Files affected:** Indicator-specific test files (e.g., `test_williams_r_indicator.py`)

---

#### Create Migration Test File

**Pattern:** Create comprehensive migration test file for all indicators in a task

**Structure:**
1. `TestMomentumOscillatorMigration` - Check each indicator returns unnamed Series
2. `TestIndicatorValuesUnchanged` - Regression tests for values
3. `TestAdapterIntegration` - Verify works through IndicatorEngine adapter

**Why:** Centralized validation that all indicators follow M3a format

---

### Gotchas Summary

| Gotcha | Symptom | Solution |
|--------|---------|----------|
| Name inheritance | `assert 'close' is None` fails | Use `.values` when creating Series from derived calculation |
| Two naming patterns | Inconsistent removal approach | Check both `.name =` and `name=` parameter |
| Already migrated | Unnecessary changes | Check if name is already None before modifying |
| Multi-output | Wrong milestone | Check `is_multi_output()`, skip if True |
| Old test assertions | Tests fail after migration | Update `assert .name == "X"` to `assert .name is None` |

---

---

## Task 3a.2 Complete: Volume/Trend Indicators

### Indicators Migrated

**Single-output (4 indicators):**
1. OBV - `name="OBV"` in constructor → removed
2. VWAP - `name=self.get_name()` in constructor → removed
3. VolumeRatio - `name=self.get_column_name()` in constructor → removed
4. ATR - `name=f"ATR_{period}"` in constructor → removed

**Skipped (multi-output, for M3b):**
1. CMF - `is_multi_output()` returns `True`
2. AD Line - `is_multi_output()` returns `True`

### Patterns Observed

**Pattern:** All 4 single-output indicators used `name=` parameter in Series constructor

No name inheritance issues observed (OBV and VWAP create new Series, not derived from source).

### Test Updates

Updated existing indicator-specific tests:
- `test_obv_indicator.py`: 3 assertions changed from `assert result.name == "OBV"` to `assert result.name is None`
- `test_atr_indicator.py`: 5 assertions changed from `assert result.name == "ATR_X"` to `assert result.name is None`

---

## Task 3a.3 Complete: Remaining + MA Indicators

### Indicators Migrated

**All 6 indicators migrated successfully:**
1. SMA - `.name` assignment removed, `.values` used (name inheritance)
2. EMA - `.name` assignment removed, `.values` used (name inheritance)
3. DistanceFromMA - `name=` parameter removed
4. BollingerBandWidth - `name=` parameter removed
5. ParabolicSAR - `name=` parameter removed
6. ZigZag - `name=` parameter removed

### Patterns Confirmed

**Name inheritance (Handoff Pattern 2) confirmed for MAs:**
- Both SMA and EMA inherit the name 'close' from `data[source]`
- Solution: Use `.values` when creating the result Series
- Same pattern as Momentum and ROC from Task 3a.1

**No name inheritance for derived indicators:**
- DistanceFromMA, BollingerBandWidth, ParabolicSAR, ZigZag create new Series
- Simply removing `name=` parameter was sufficient
- No `.values` workaround needed

### Milestone 3a Status

**ALL TASKS COMPLETE:**
- ✅ Task 3a.1: Momentum/oscillator indicators (8 files)
- ✅ Task 3a.2: Volume/trend indicators (4 single-output files, 2 multi-output skipped)
- ✅ Task 3a.3: Remaining + MA indicators (6 files)

**Total indicators migrated:** 18 single-output indicators
**Ready for:** M3b (multi-output indicator migration)

---

## Next Milestone: M3b

### What to Expect

**M3b: Multi-Output Indicator Migration**
- Multi-output indicators return unnamed DataFrame (not Series)
- Engine handles naming with suffixes (e.g., `bbands_20_2_upper`, `bbands_20_2_middle`, `bbands_20_2_lower`)
- Different adapter logic than single-output
- Examples: Bollinger Bands, MACD, Stochastic, ADX

### Key Differences from M3a

1. **Return type:** DataFrame instead of Series
2. **Column naming:** Engine applies suffixes based on `get_output_names()`
3. **Adapter logic:** Different code path in `compute_indicator()`
4. **Name inheritance:** Not applicable (DataFrame columns already unnamed in calculation)

---
