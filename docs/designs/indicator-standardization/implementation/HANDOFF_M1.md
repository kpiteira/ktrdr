# Milestone 1 Handoff: Interface Addition

This handoff captures gotchas, workarounds, and patterns discovered during M1 implementation.

---

## Gotchas

### ~~Circular Import in Indicator Module~~ ✅ FIXED

~~**Problem:** Direct pytest execution of indicator test files fails with circular import error~~

**Status:** **RESOLVED** in commit `9c94e090`

**Solution implemented:**
- Lazy-loaded `BUILT_IN_INDICATORS` in StrategyValidator with caching
- Moved import from module-level to method-level in `_get_normalized_indicator_names()`
- Direct pytest execution now works: `uv run pytest tests/unit/indicators/test_base_indicator.py -v`

See `CIRCULAR_IMPORT_FIX_PLAN.md` for detailed analysis and implementation.

---

## Emergent Patterns

### Interface Method Placement

**Decision:** All new interface methods are `@classmethod` not instance methods

**Rationale:**
- `get_output_names()`, `get_primary_output()`, `is_multi_output()` describe properties of the indicator TYPE
- These don't depend on instance state (params don't affect output names)
- Example: BollingerBands always returns `["upper", "middle", "lower"]` regardless of period/multiplier
- Allows calling without instantiation: `BollingerBandsIndicator.get_output_names()`

**Implication for M2+:**
- When IndicatorEngine needs to generate column names, it can call class methods before instantiation
- Multi-timeframe strategies can query output names without creating indicator instances

### Backward Compatibility Strategy

**Decision:** Keep deprecated methods as delegation wrappers

**Pattern:**
```python
@classmethod
def get_primary_output_suffix(cls) -> Optional[str]:
    """DEPRECATED: Use get_primary_output() instead."""
    # CLEANUP(v3): Remove after v3 migration complete
    return cls.get_primary_output()
```

**Rationale:**
- Avoids breaking existing code that may call `get_primary_output_suffix()`
- Clear deprecation notice guides future cleanup
- Minimal maintenance burden (single line delegation)
- Tagged with `CLEANUP(v3)` for searchability

**Implication for M6:**
- Grep for `CLEANUP(v3)` to find all deprecated code to remove
- No behavior change between old and new methods (just renamed)

### Test Structure for Multi-Output

**Pattern:** Created `DummyMultiOutputIndicator` test helper class

**Rationale:**
- Tests need to verify both single-output and multi-output behavior
- Can't rely on real indicators (BBands, MACD) which may not exist yet in test isolation
- Test helpers should be minimal and self-contained

**Code:**
```python
class DummyMultiOutputIndicator(BaseIndicator):
    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["upper", "middle", "lower"]

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({
            "upper": df["close"] * 1.1,
            "middle": df["close"],
            "lower": df["close"] * 0.9,
        })
```

**Implication for M2+:**
- Use this pattern for testing multi-output behavior
- Don't depend on real indicators in BaseIndicator tests
- Keep test helpers in the test file (not shared fixtures unless needed elsewhere)

---

## Testing Notes

### How to Run Tests

**Standard workflow:**
```bash
make test-unit          # Fast, parallel, use this for TDD
make quality           # Lint + format + type check
```

**Known failures (unrelated to M1):**
- 5 failures in `tests/unit/cli/test_sandbox_commands.py`
- These are pre-existing and related to sandbox port conflicts
- **Do not** spend time fixing these in M1 - out of scope

### Test Coverage

**New tests added:**
- `test_get_output_names_default` — Single-output returns `[]`
- `test_get_primary_output_default` — Single-output returns `None`
- `test_get_primary_output_suffix_backward_compat` — Delegation works
- `test_multi_output_get_output_names` — Multi-output returns names
- `test_multi_output_get_primary_output` — Multi-output returns first name
- `test_multi_output_get_primary_output_suffix_backward_compat` — Multi-output delegation

**All pass in `make test-unit` (3557 passed total)**

---

## Code Quality

All quality gates passed:
- ✅ Ruff linting (no issues)
- ✅ Black formatting (auto-formatted test file)
- ✅ MyPy type checking (no new issues)

---

## Discovered Issue: RVI Indicator Not Included

**Problem:** RVI indicator (`rvi_indicator.py`) is multi-output but was not included in Task 1.2 list

**Evidence:**
- `RVIIndicator.is_multi_output()` returns `True` (line 42-44)
- Has old-style `get_primary_output_suffix()` returning "RVI"
- Missing new `get_output_names()` method
- Produces two outputs: "RVI" and "Signal"

**Impact:**
- Task 1.4's integration test will likely fail for RVI
- RVI should return `["rvi", "signal"]` (lowercase, following standard)

**Recommendation:**
- Add RVI to multi-output indicator list
- Implement `get_output_names()` → `["rvi", "signal"]`
- Or verify if RVI should be included in M1 scope

---

## Next Task: 1.4 - Integration Test for All Indicators

**Context for next implementer:**
- Task 1.1 (BaseIndicator interface): ✅ Complete
- Task 1.2 (Multi-output indicators): ✅ Complete (10 indicators)
- Task 1.3 (Single-output indicators): ✅ Complete (19 indicators verified)
- **Known gap**: RVI indicator missing from Task 1.2

**Task 1.4 will:**
- Verify ALL registered indicators in IndicatorFactory
- Test interface contract (is_multi_output ↔ get_output_names consistency)
- Verify compute() return type matches declaration
- Will likely catch the RVI gap

**Test file location:** `tests/integration/indicators/test_indicator_interface_standard.py`
