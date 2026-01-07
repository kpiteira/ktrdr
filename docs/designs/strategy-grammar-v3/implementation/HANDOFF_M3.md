# M3 Handoff: FuzzyEngine V3

## Task 3.1 Complete: V3 Constructor

### Emergent Patterns

**V3 uses separate `_fuzzy_sets` and `_indicator_map` attributes**
- V3 format stores fuzzy sets in `self._fuzzy_sets: dict[str, dict[str, MembershipFunction]]`
- V3 format tracks indicator mapping in `self._indicator_map: dict[str, str]`
- V2 format continues using `self._membership_functions` and `self._config`
- This maintains backward compatibility without conflicts

**Constructor accepts Union type for backward compatibility**
- Signature: `__init__(self, config: Union[FuzzyConfig, dict[str, FuzzySetDefinition]])`
- `isinstance(config, dict)` check determines v3 vs v2 mode
- V3 path initializes `_fuzzy_sets` and `_indicator_map`
- V2 path initializes `_membership_functions` and `_config`

**FuzzySetDefinition stores membership functions in `model_extra`**
- Access membership names via: `definition.get_membership_names()`
- Access membership spec via: `getattr(definition, name)`
- Pydantic expands shorthand `[a,b,c]` to `{type: triangular, parameters: [a,b,c]}`
- Pattern: iterate names, getattr each, create MembershipFunction

### Implementation Notes

**Type narrowing for mypy**
- Added assertions in v2-only methods: `assert self._config is not None`
- This helps mypy understand that `_config` is not None in those contexts
- Pattern used in: `_validate_config()`, `_initialize_membership_functions()`, `_apply_transform()`

**MembershipFunctionFactory.create()**
- Use factory for all membership function creation
- Takes `(type: str, parameters: list[float])`
- Returns appropriate MembershipFunction subclass
- Handles triangular, trapezoidal, gaussian types

### Gotchas

**Don't access `definition.model_extra` directly**
- Use `definition.get_membership_names()` to get list of membership names
- Use `getattr(definition, name)` to get membership spec
- Pydantic stores membership functions as attributes after expansion

**Indicator map is v3-only**
- `get_indicator_for_fuzzy_set()` only works in v3 mode
- Raises ValueError if called in v2 mode (when `_indicator_map` is empty)
- Check for v3 mode: `if not self._indicator_map: raise ValueError(...)`

**Shorthand and explicit formats both work**
- `[0, 25, 40]` → Pydantic expands to `{type: triangular, parameters: [0, 25, 40]}`
- `{type: triangular, parameters: [0, 25, 40]}` → Already in correct format
- Both result in same membership_def structure when accessed via getattr

### Files Modified

- `ktrdr/fuzzy/engine.py`: Lines 8, 14, 50-88, 96, 119-126, 155-263 (constructor + v3 init + helpers)
- `tests/unit/fuzzy/test_fuzzy_engine_v3.py`: New file, 161 lines, 9 tests (all passing)

## Task 3.2 Complete: V3 fuzzify() Method

### Emergent Patterns

**fuzzify() supports both v2 and v3 modes via runtime detection**
- Check `if hasattr(self, "_fuzzy_sets") and self._fuzzy_sets:` for v3 mode
- v3 path interprets first param as fuzzy_set_id, second as indicator_values
- v2 path interprets first param as indicator, second as values (Union types)
- Both modes return DataFrame for Series input

**Column naming differs between v2 and v3**
- v3: `{fuzzy_set_id}_{membership}` (e.g., "rsi_fast_oversold")
- v2: `{indicator}_{membership}` (e.g., "rsi_oversold")
- NO timeframe prefix in either mode - that's caller's responsibility

**Return type is always DataFrame for Series input**
- v3: Always returns DataFrame (no scalar input supported)
- v2: Returns dict for scalar, DataFrame for Series/array
- Index preserved from input Series

### Implementation Notes

**Mode detection pattern**
- Use `hasattr(self, "_fuzzy_sets") and self._fuzzy_sets` to detect v3
- This is the standard pattern for v3-specific logic
- Don't check `_membership_functions` - it may not exist in v3 mode

**Updated docstring reflects dual mode**
- Docstring documents both v2 and v3 behavior
- Parameter names generic enough for both modes
- Raises ValueError in v3 mode for unknown fuzzy_set_id

### Gotchas

**Don't assume v3 input is always pd.Series**
- v3 spec says indicator_values is pd.Series, but implementation handles edge cases
- Check `isinstance(indicator_values, pd.Series)` before using `.index`
- Pattern: return `pd.DataFrame(result, index=indicator_values.index)`

**Backward compatibility is critical**
- All v2 tests must pass after v3 changes
- v2 callers don't know about v3 - method signature must be flexible
- Run both v2 and v3 test suites after changes

### Files Modified

- `ktrdr/fuzzy/engine.py`: Lines 263-323 (fuzzify method + docstring)
- `tests/unit/fuzzy/test_fuzzy_engine_v3.py`: Lines 166-365 (8 new tests)

## Task 3.3 Complete: get_membership_names() Method

### Emergent Patterns

**v3-only accessor follows same pattern as get_indicator_for_fuzzy_set()**
- Check `if not hasattr(self, "_fuzzy_sets") or not self._fuzzy_sets:` for v2 mode detection
- Raises ValueError in v2 mode with message "only available in v3 mode"
- Returns `list(self._fuzzy_sets[fuzzy_set_id].keys())` for ordered membership names

### Implementation Notes

**Order preservation**
- Python dicts maintain insertion order (3.7+)
- Membership names returned in definition order
- Example: `['oversold', 'neutral', 'overbought']`

### Gotchas

**v2 mode doesn't have `_fuzzy_sets` attribute at all**
- Must use `hasattr()` check before accessing `_fuzzy_sets`
- Pattern: `if not hasattr(self, "_fuzzy_sets") or not self._fuzzy_sets:`

### Files Modified

- `ktrdr/fuzzy/engine.py`: Lines 263-283 (new method)
- `tests/unit/fuzzy/test_fuzzy_engine_v3.py`: Lines 375-444 (4 new tests)

---

## Milestone 3 Complete

**All tasks completed:**
- Task 3.1: V3 constructor ✓
- Task 3.2: V3 fuzzify() method ✓
- Task 3.3: get_membership_names() method ✓

**E2E test passed** - All 6 test scenarios pass

**No regression** - All 73 v3 tests pass (M1, M2, M3)

### Next Milestone Notes

**M4: Training Pipeline V3**
- FuzzyEngine is now ready to be used by TrainingPipeline
- Key methods: `fuzzify(fuzzy_set_id, values)`, `get_indicator_for_fuzzy_set(fuzzy_set_id)`, `get_membership_names(fuzzy_set_id)`
- Column naming: `{fuzzy_set_id}_{membership}` (no timeframe prefix)
