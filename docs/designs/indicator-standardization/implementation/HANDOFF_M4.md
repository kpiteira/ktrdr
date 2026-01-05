# Handoff Document: Milestone 4 (Update Consumers)

This document captures patterns, gotchas, and workarounds discovered during M4 consumer migration.

---

## Task 4.1 Complete: Update FeatureCache

### Changes Made

**Before (M3b):**
- O(n) fuzzy string matching to find columns
- Case-insensitive `col.upper().startswith(indicator_type)` iteration
- Special handling for MACD (exclude signal/histogram columns)

**After (M4):**
- O(1) direct column lookup using `feature_id`
- Simple `if feature_id in self.indicators_df.columns`
- No special cases needed (column names are exact)

### New API

Added two new features to `FeatureCache`:

1. **`from_dataframe()` factory method:**
   ```python
   cache = FeatureCache.from_dataframe(indicators_df)
   ```
   - Simpler initialization for testing and direct use
   - Doesn't require full strategy_config
   - Backward compatible (existing `__init__` still works)

2. **`get_indicator_value()` method:**
   ```python
   value = cache.get_indicator_value('rsi_14', idx)
   value = cache.get_indicator_value('bbands_20_2.upper', idx)
   value = cache.get_indicator_value('bbands_20_2', idx)  # alias
   ```
   - Direct O(1) column lookup
   - Supports dot notation for multi-output
   - Supports alias references (bare indicator_id)
   - Clear error messages with available columns

### Gotcha 1: Type Annotation Required

**Problem:** mypy requires type annotation for dictionary literals in class methods.

**Symptom:**
```
error: Need type annotation for "dummy_config"
```

**Solution:**
```python
# BAD
dummy_config = {"indicators": [], "fuzzy_sets": {}}

# GOOD
dummy_config: dict[str, Any] = {"indicators": [], "fuzzy_sets": {}}
```

### Implementation Pattern

**Column lookup simplification (lines 152-167 in feature_cache.py):**

```python
# BEFORE (M3b): O(n) fuzzy matching
for col in self.indicators_df.columns:
    if col.upper().startswith(indicator_type):
        if indicator_type == "MACD":
            # Special handling...
        else:
            current_bar_indicators[feature_id] = self.indicators_df[col].iloc[idx]
            break

# AFTER (M4): O(1) direct lookup
if feature_id in self.indicators_df.columns:
    current_bar_indicators[feature_id] = self.indicators_df[feature_id].iloc[idx]
else:
    logger.warning(f"Column '{feature_id}' not found in indicators_df at idx {idx}")
```

### Test Coverage

**New test file:** `tests/unit/backtesting/test_feature_cache_new_format.py`

**Tests added (8 total):**
1. Direct column lookup (single-output indicators)
2. Dot notation lookup (multi-output with explicit output)
3. Alias lookup (multi-output with bare indicator_id)
4. Missing column error handling (KeyError with clear message)
5. Invalid index error handling (IndexError)
6. NaN value handling (returns NaN, doesn't raise)
7. `from_dataframe()` factory method
8. Backward compatibility with strategy_config

**All tests pass:** 3733 unit tests (76 skipped), all quality checks pass

### Backward Compatibility

The existing `FeatureCache(strategy_config)` constructor still works:
- `compute_all_features()` uses new O(1) lookup internally
- Existing backtesting code works without changes
- Only consumers using the new API need updates

### Next Tasks

- **Task 4.2:** Update FuzzyEngine to use new column format
- **Task 4.3:** Update Training Pipeline
- **Task 4.4:** Integration test for full pipeline

---

---

## Task 4.2 Complete: Update FuzzyEngine

### Changes Made

**Before (M3b):**
- Prefix matching with underscore: `bbands_20_2_upper` matches `bbands_20_2`
- Did not support dot notation for multi-output indicators

**After (M4):**
- Prefix matching with dot notation: `bbands_20_2.upper` matches `bbands_20_2`
- Backward compatible with underscore format
- Priority: Direct match → Dot notation → Underscore (legacy)

### Implementation Pattern

**Updated `_find_fuzzy_key()` (lines 715-756 in engine.py):**

```python
# M4: Dot notation prefix matching (new format from M3b)
for fuzzy_key in self._membership_functions.keys():
    if column_name.startswith(f"{fuzzy_key}."):
        return fuzzy_key

# Legacy: Underscore prefix matching (backward compatibility)
for fuzzy_key in self._membership_functions.keys():
    if column_name.startswith(f"{fuzzy_key}_"):
        return fuzzy_key
```

### Example Matching

| Column Name | Fuzzy Key | Match Type |
|-------------|-----------|------------|
| `rsi_14` | `rsi_14` | Direct (O(1)) |
| `bbands_20_2` | `bbands_20_2` | Direct (alias) |
| `bbands_20_2.upper` | `bbands_20_2` | Dot notation prefix |
| `bbands_20_2_upper` | `bbands_20_2` | Legacy underscore prefix |
| `nonexistent` | None | No match |

### Test Coverage

**New test file:** `tests/unit/fuzzy/test_fuzzy_engine_new_format.py`

**Tests added (9 total):**
1. Single-output indicator direct lookup
2. Multi-output with dot notation explicit reference
3. Direct match (`rsi_14` → `rsi_14`)
4. Dot notation prefix match (`bbands_20_2.upper` → `bbands_20_2`)
5. Alias reference (`bbands_20_2` → `bbands_20_2`)
6. No match returns None
7. Clear error messages for missing columns
8. Multi-timeframe with new column format
9. Multi-timeframe matches dot notation columns

**All tests pass:** 140 fuzzy tests (9 new + 131 existing)

### Backward Compatibility

The existing behavior is preserved:
- Old underscore format still works (`bbands_20_2_upper`)
- Direct matching still works (`rsi_14`)
- All existing tests pass without changes

---

## Notes for Next Implementer

1. **Column names are exact:** No more fuzzy matching, case normalization, or startsWith logic
2. **feature_id IS the column name:** For single-output, `feature_id` = column name. For multi-output, `feature_id` = alias column
3. **Dot notation is explicit:** Use `bbands_20_2.upper` to reference specific outputs
4. **Error messages are helpful:** KeyError shows all available columns for debugging
5. **Dot notation priority:** FuzzyEngine now checks dot notation before underscore (new format preferred)
