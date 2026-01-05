# Milestone 1 Handoff: Interface Addition

This handoff captures gotchas, workarounds, and patterns discovered during M1 implementation.

---

## Gotchas

### Circular Import in Indicator Module

**Problem:** Direct pytest execution of indicator test files fails with circular import error

**Symptom:**
```bash
$ uv run pytest tests/unit/indicators/test_base_indicator.py -v
ImportError: cannot import name 'BaseIndicator' from partially initialized module
```

**Cause:**
```
ktrdr/indicators/__init__.py
  → base_indicator.py
    → config.validation.InputValidator
      → config.strategy_validator.StrategyValidator
        → indicators.indicator_factory.BUILT_IN_INDICATORS
          → indicators.ad_line.ADLineIndicator
            → indicators.base_indicator.BaseIndicator  [CIRCULAR]
```

**Workaround:**
- Use `make test-unit` (runs with pytest `-n auto` for parallel execution)
- Parallel pytest handles module loading differently and avoids the circular import
- All tests pass with `make test-unit`
- **Impact:** This is a pre-existing issue on main branch, not introduced by M1 changes

**Solution (for future work):**
- Break the circular dependency by lazy-loading BUILT_IN_INDICATORS in StrategyValidator
- OR move InputValidator to a module that doesn't depend on config
- OR restructure indicator_factory to not be imported at config module load time
- **Recommendation:** Fix this before M2, as it will complicate development

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

## Next Task: 1.2 - Implement get_output_names() for Multi-Output Indicators

**Context for next implementer:**
- The interface is now defined in BaseIndicator
- Default implementation returns `[]` (single-output)
- Task 1.2 will override `get_output_names()` in 10 multi-output indicator classes
- Follow the pattern from `DummyMultiOutputIndicator` in the tests
- Each indicator should return semantic names matching DESIGN.md standard

**Files to modify (from M1 plan):**
1. `bollinger_bands_indicator.py` → `["upper", "middle", "lower"]`
2. `macd_indicator.py` → `["line", "signal", "histogram"]`
3. `stochastic_indicator.py` → `["k", "d"]`
4. `adx_indicator.py` → `["adx", "plus_di", "minus_di"]`
5. `aroon_indicator.py` → `["up", "down", "oscillator"]`
6. `ichimoku_indicator.py` → `["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"]`
7. `supertrend_indicator.py` → `["trend", "direction"]`
8. `donchian_channels.py` → `["upper", "middle", "lower"]`
9. `keltner_channels.py` → `["upper", "middle", "lower"]`
10. `fisher_transform.py` → `["fisher", "signal"]`

**No behavior changes yet** — `compute()` still returns old format
