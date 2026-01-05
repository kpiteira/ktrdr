# Milestone 2 Handoff: IndicatorEngine Adapter

This handoff captures gotchas, workarounds, and patterns discovered during M2 implementation.

---

## Task 2.1 Complete: compute_indicator() Method

### Emergent Patterns

#### Type Safety with Runtime Checks

**Pattern:** After `is_multi_output()` check, mypy doesn't know result is DataFrame

```python
# Multi-output indicator
if not isinstance(result, pd.DataFrame):
    raise ProcessingError(
        f"Multi-output indicator {indicator.__class__.__name__} returned {type(result).__name__} instead of DataFrame",
        "PROC-InvalidOutputType",
        {"indicator": indicator.__class__.__name__, "type": type(result).__name__},
    )

# Now mypy knows result is DataFrame and won't complain about .columns
expected_outputs = set(indicator.get_output_names())
actual_columns = set(result.columns)
```

**Rationale:**
- Mypy can't infer type from `is_multi_output()` class method
- Runtime check provides both type safety and clear error message
- Defensive programming: catches indicators that violate the contract

#### DataFrame Mutation Prevention

**Pattern:** Always copy DataFrames before modifying

```python
# Copy result to avoid modifying original
prefixed = result.copy()
prefixed = prefixed.rename(columns={...})

# OR for old format
result_copy = result.copy()
result_copy[indicator_id] = result_copy[primary_col]
return result_copy
```

**Rationale:**
- Pandas DataFrames are mutable
- Original `result` from indicator.compute() should not be modified
- Prevents subtle bugs from shared references

#### Compatibility Markers

**Pattern:** Mark all v2 compatibility code with `# CLEANUP(v3)`

```python
# CLEANUP(v3): Remove old-format handling after v3 migration complete
# OLD FORMAT: columns have params embedded -> pass through
```

**Rationale:**
- Easy to grep for all compatibility code: `grep -r "CLEANUP(v3)"`
- Clear documentation of temporary code
- Consistent with M1 pattern

### Format Detection Design

**How it works:**
1. Get expected output names from `indicator.get_output_names()`
2. Get actual columns from `result.columns`
3. If sets match exactly → NEW FORMAT (semantic names only)
4. If sets don't match → OLD FORMAT (params in column names)

**Why column set comparison:**
- Simple and reliable
- No string parsing needed
- Works for any indicator without special cases
- Clear contract: new format MUST match get_output_names() exactly

### Test Coverage Notes

**Mock indicators work well:**
- `MockOldFormatIndicator`: Returns `upper_20_2.0`, `middle_20_2.0`, `lower_20_2.0`
- `MockNewFormatIndicator`: Returns `upper`, `middle`, `lower`
- Both declare same `get_output_names()` → format detection works

**Edge cases covered:**
- Single-output returning DataFrame (rare but handled)
- Multi-output without primary output (no alias created)
- Multi-output returning Series (raises ProcessingError)

### Smoke Test Simplification

**Original test:** Used `DataManager` (which no longer exists)
**Updated test:** Simple pandas DataFrame with test data

```python
data = pd.DataFrame({
    'close': [100, 101, 102, 101, 103],
    # ... other OHLCV columns
}, index=pd.date_range('2024-01-01', periods=5, freq='h'))
```

**For Task 2.2:** Can use same pattern for testing `apply()` changes

---

## Next Task: 2.2 Update apply() to Use compute_indicator()

### Key Points for Implementer

1. **Indicator ID Source:** Get from `indicator.get_feature_id()` or fall back to `indicator.get_column_name()`
2. **Don't break existing tests:** The change should be transparent to callers
3. **Feature ID Map:** Existing `_create_feature_id_aliases()` might need adjustment
4. **Compatibility:** Old indicators (M1 complete) will use old-format path automatically

### Expected Challenges

- Need to ensure `indicator_id` is available for each indicator in the loop
- May need to adjust how `feature_id_map` is built/used
- Integration test should verify no regression in `apply()` behavior

---

## Quality Standards Met

- ✅ All 12 new unit tests passing
- ✅ Full test suite passing (3669 tests)
- ✅ Quality gates: ruff, black, mypy all clean
- ✅ No new type errors introduced
- ✅ Smoke test verifies method works with real indicator
