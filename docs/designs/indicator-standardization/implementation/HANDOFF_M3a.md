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

## Next Tasks: 3a.2 and 3a.3

### What to Expect

**Task 3a.2: Volume/Trend Indicators (6 files)**
- Likely patterns: Same as 3a.1
- Watch for: OBV, VWAP may have name inheritance issues (operate on volume/price)

**Task 3a.3: Remaining + MAs (6+ files)**
- Moving Averages (SMA, EMA) in `ma_indicators.py` (multiple indicators in one file)
- May have name inheritance (MAs operate on source Series)

### Quick Checklist Per Indicator

1. ☐ Check `is_multi_output()` - if True, skip for M3a
2. ☐ Find `.name =` assignments → remove
3. ☐ Find `name=` parameters → remove
4. ☐ If operates on `data[source]` → use `.values` when creating result
5. ☐ Add test to `test_single_output_migration.py`
6. ☐ Update existing indicator tests (search for `.name ==` assertions)
7. ☐ Run `make test-unit` and `make quality`
