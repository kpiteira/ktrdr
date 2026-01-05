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

## Task 2.2 Complete: apply() Routes Through compute_indicator()

### Simplification Achieved

**Before (old apply()):**
- 100+ lines with complex duplicate detection
- Manual Series/DataFrame handling
- Error-prone column overlap detection
- Fragile merge logic with workarounds

**After (new apply()):**
- ~20 lines: loop, get feature_id, call adapter, concat
- All complexity moved to `compute_indicator()`
- Format detection automatic
- No duplicate column issues

### Key Implementation Details

**Routing pattern:**
```python
for indicator in self.indicators:
    indicator_id = indicator.get_feature_id()  # Uses feature_id or falls back to column_name
    computed = self.compute_indicator(data, indicator, indicator_id)
    result_df = pd.concat([result_df, computed], axis=1)
```

**Why _create_feature_id_aliases() kept:**
- Still called for backward compatibility
- Adapter already creates aliases, so this is mostly no-op now
- Marked with `CLEANUP(v3)` for removal after migration
- Kept in case feature_id_map used elsewhere

### Test Updates Required

**test_feature_id_aliasing.py:**
- Old behavior: Created BOTH technical column (e.g., `rsi_7`) AND feature_id alias (e.g., `rsi_fast`)
- New M2 behavior: Creates feature_id column directly (e.g., `rsi_fast` only)
- Tests updated to validate M2 adapter behavior
- Marked with `CLEANUP(v3)` comments

**Why this is correct:**
- Adapter uses `indicator_id` (feature_id) as the column name
- No need for separate technical column + alias
- Simpler, cleaner, fewer columns

### Integration Test Results

✅ compute_indicator() works with real indicators
✅ apply() routes through adapter correctly
✅ Feature IDs used as column names
✅ 3596 unit tests passing
✅ All quality gates passing

---

## Next Task: 2.3 Unit Tests for Format Detection

Already complete! Format detection tests exist in `test_indicator_engine_adapter.py`.

---

## Quality Standards Met

- ✅ All 18 adapter tests passing (12 from 2.1, 6 from 2.2)
- ✅ Full test suite passing (3596 tests)
- ✅ Quality gates: ruff, black, mypy all clean
- ✅ No new type errors introduced
- ✅ Integration tests verify end-to-end flow
- ✅ Code simplified: 60+ lines of complex logic removed
