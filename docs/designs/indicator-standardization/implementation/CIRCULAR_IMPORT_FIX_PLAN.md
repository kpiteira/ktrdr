# Circular Import Fix: Implementation Plan

## Problem Summary

**Symptom:** Direct pytest execution fails with circular import error:
```bash
$ uv run pytest tests/unit/indicators/test_base_indicator.py -v
ImportError: cannot import name 'BaseIndicator' from partially initialized module
```

**Root Cause:** Module-level import chain creates circular dependency:
```
BaseIndicator → InputValidator → StrategyValidator → BUILT_IN_INDICATORS → ad_line → BaseIndicator
```

**Impact:**
- ✗ Cannot run individual test files for debugging
- ✓ Works fine with `make test-unit` (parallel execution)
- Pre-existing issue (not caused by M1 changes)

---

## Solution Analysis

### Option A: Lazy-load BUILT_IN_INDICATORS in StrategyValidator ⭐ RECOMMENDED

**What:** Move `BUILT_IN_INDICATORS` import from module-level to method-level with caching

**Changes Required:**
1. **File:** `ktrdr/config/strategy_validator.py`
2. **Lines to modify:**
   - Remove line 25: `from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS`
   - Remove lines 40-42: `_NORMALIZED_INDICATOR_NAMES` module-level computation
   - Add cached property/method for lazy loading
   - Update line 763 in `_validate_indicator_types()` method
   - Update line 769 for similar name suggestions

**Implementation:**
```python
class StrategyValidator:
    """Validator for strategy configuration files."""

    def __init__(self):
        self._cached_indicator_names: Optional[set[str]] = None

    def _get_normalized_indicator_names(self) -> set[str]:
        """Lazy-load indicator names to avoid circular import.

        BUILT_IN_INDICATORS is imported only when validation is actually needed,
        not at module load time. This breaks the circular dependency:
        BaseIndicator → InputValidator → StrategyValidator.

        Returns:
            set[str]: Lowercase indicator names for case-insensitive matching
        """
        if self._cached_indicator_names is None:
            from ktrdr.indicators.indicator_factory import BUILT_IN_INDICATORS
            self._cached_indicator_names = {
                name.lower() for name in BUILT_IN_INDICATORS.keys()
            }
        return self._cached_indicator_names

    def _validate_indicator_types(self, indicators, result):
        """Validate that indicator types exist in KTRDR's BUILT_IN_INDICATORS."""
        # Line 763: Use lazy-loaded names
        normalized_names = self._get_normalized_indicator_names()

        for idx, indicator_dict in enumerate(indicators):
            indicator_type = indicator_dict.get("name") or indicator_dict.get("type")
            indicator_type_lower = indicator_type.lower()

            if indicator_type_lower not in normalized_names:
                # Line 769: Use for similar name suggestions
                similar = get_close_matches(
                    indicator_type_lower,
                    list(normalized_names),
                    n=3,
                    cutoff=0.6,
                )
                # ... error handling
```

**Pros:**
- ✅ Minimal changes (single file)
- ✅ No API changes (preserves public interfaces)
- ✅ Logical (validation only needs names when actually validating)
- ✅ Cached (only imports once per StrategyValidator instance)
- ✅ Clean (lazy loading contained in validator)

**Cons:**
- Small overhead: first validation call pays import cost
- Adds instance variable to StrategyValidator

**Testing Required:**
- Verify `uv run pytest tests/unit/indicators/test_base_indicator.py -v` works
- Verify `make test-unit` still passes
- Verify strategy validation still works correctly
- Check config tests pass: `uv run pytest tests/unit/config/test_strategy_validator.py -v`

---

### Option B: Remove StrategyValidator from ktrdr.config.__init__.py

**What:** Make StrategyValidator a private module, not exported from package

**Changes Required:**
1. **File:** `ktrdr/config/__init__.py`
   - Remove line 10: `from .strategy_validator import StrategyValidator`
   - Remove from `__all__`

2. **Files importing StrategyValidator:** Update all imports
   ```python
   # Old
   from ktrdr.config import StrategyValidator

   # New
   from ktrdr.config.strategy_validator import StrategyValidator
   ```

**Pros:**
- ✅ Clean separation of concerns
- ✅ No lazy loading needed
- ✅ StrategyValidator used in limited places

**Cons:**
- ❌ Changes public API of ktrdr.config package
- ❌ Requires updating multiple files
- ❌ More invasive change

---

### Option C: Make BUILT_IN_INDICATORS lazy in indicator_factory.py

**What:** Change BUILT_IN_INDICATORS from module-level dict to lazy-loading function

**Changes Required:**
1. **File:** `ktrdr/indicators/indicator_factory.py`
   - Replace module-level BUILT_IN_INDICATORS dict with function
   - Add caching mechanism

2. **All files importing BUILT_IN_INDICATORS:**
   - Update to call `get_built_in_indicators()`
   - Major refactoring across codebase

**Pros:**
- ✅ Fixes circular import at the source

**Cons:**
- ❌ Major refactoring (many files import BUILT_IN_INDICATORS)
- ❌ Changes widely-used API
- ❌ High risk of breaking changes

---

## Recommended Implementation Plan

### Phase 1: Implement Fix (Option A)

**Step 1: Modify StrategyValidator**
- Remove module-level import (line 25)
- Remove module-level `_NORMALIZED_INDICATOR_NAMES` (lines 40-42)
- Add `__init__` with `_cached_indicator_names` instance variable
- Add `_get_normalized_indicator_names()` method with lazy loading
- Update `_validate_indicator_types()` to use new method

**Step 2: Write Tests**
- Add test to verify lazy loading works
- Add test to verify caching works (import only happens once)
- Ensure existing validation tests still pass

**Step 3: Verify Fix**
```bash
# Should now work (currently fails)
uv run pytest tests/unit/indicators/test_base_indicator.py -v

# Should still work
make test-unit

# Should still work
uv run pytest tests/unit/config/test_strategy_validator.py -v
```

---

## Files to Modify

### Primary Change:
1. `ktrdr/config/strategy_validator.py`
   - Lines to remove: 25, 40-42
   - Lines to add: `__init__` method, `_get_normalized_indicator_names()` method
   - Lines to update: 763, 769 (use new method)

### Test File (if needed):
2. `tests/unit/config/test_strategy_validator.py`
   - Add test for lazy loading behavior

---

## Risk Assessment

**Low Risk** because:
- Single file change
- StrategyValidator is only instantiated in a few places
- Lazy loading is transparent to callers
- Caching ensures no performance degradation
- Easy to revert if issues arise

**Potential Issues:**
- If StrategyValidator is instantiated before indicators are loaded (unlikely)
- Thread safety if multiple threads create validators simultaneously (current code doesn't do this)

---

## Success Criteria

- [ ] Direct pytest execution works: `uv run pytest tests/unit/indicators/test_base_indicator.py -v`
- [ ] Parallel tests still pass: `make test-unit`
- [ ] Config tests pass: `uv run pytest tests/unit/config/ -v`
- [ ] Strategy validation still works correctly
- [ ] No performance degradation (caching works)
- [ ] Code quality passes: `make quality`

---

## Rollback Plan

If the fix causes issues:
1. Revert commit
2. Document the issue
3. Consider Option B or defer fix to after M1

---

## Timeline Estimate

- Implementation: 10 minutes
- Testing: 5-10 minutes
- Documentation: 5 minutes
- **Total: 20-25 minutes**

---

## Next Steps

1. **Get approval** for Option A implementation
2. **Implement** the lazy loading in StrategyValidator
3. **Test** thoroughly (direct pytest, make test-unit, config tests)
4. **Commit** with clear message
5. **Update** HANDOFF_M1.md to remove circular import from "Gotchas"
