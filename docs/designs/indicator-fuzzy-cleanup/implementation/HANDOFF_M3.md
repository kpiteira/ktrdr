# M3: Fuzzy System Migration Handoff

## Task 3.1 Complete: Add `__init_subclass__` to MembershipFunction

**Implemented:**
- `MEMBERSHIP_REGISTRY` created at module level in `ktrdr/fuzzy/membership.py`
- Added `Params` base class and `_aliases` attribute to `MembershipFunction`
- Added `__init_subclass__` that auto-registers concrete subclasses

**Key patterns followed:**
- Exactly mirrors `INDICATOR_REGISTRY` pattern from `ktrdr/indicators/base_indicator.py`
- Class name suffix "MF" stripped to get canonical name (TriangularMF → "triangular")
- Full class name lowercase added as alias (triangularmf)
- Skips abstract classes and test module classes

---

## Task 3.2 Complete: Add Params to TriangularMF, TrapezoidalMF, GaussianMF

**Implemented:**
- Base class `__init__` that validates via Pydantic Params and calls `_init_from_params`
- Abstract `_init_from_params` method on base class
- `Params` nested classes with `@field_validator` for each MF subclass
- All validation errors unified under error_code `MF-InvalidParameters`

**Key gotchas:**
- Pydantic stores parameters as floats, so `__repr__` shows `0.0` instead of `0`
- Existing tests had to be updated to check `error_code` instead of error message text

---

## Task 3.3 Complete: Update FuzzyEngine to use registry

**Implemented:**
- FuzzyEngine is now v3-only (dict[str, FuzzySetDefinition] required)
- `_create_membership_function` uses `MEMBERSHIP_REGISTRY.get_or_raise()`
- Deleted all v2 code paths:
  - `is_v3_fuzzy_config()` module function
  - `_validate_config()` method
  - `_initialize_membership_functions()` method
  - `_apply_transform()` method
  - `_fuzzify_scalar()`, `_fuzzify_series()`, `_get_output_name()` methods
  - `get_available_indicators()`, `get_fuzzy_sets()`, `get_output_names()` methods
  - `_find_close_match()`, `_levenshtein_distance()` methods
  - All v2 branches in `fuzzify()` and `generate_multi_timeframe_memberships()`
- Removed `FuzzyConfig` import

**Key gotchas:**
- v2 tests now fail with `ENGINE-V2ConfigNotSupported` (expected - will be deleted in Task 3.5)
- `training_pipeline.py:353` still uses v2 FuzzyConfig → needs update in Task 3.5
- Test file `test_fuzzy_engine_v3.py::test_v2_mode_raises_valueerror` removed (tested v2 mode)

**Next Task Notes (3.4 - Update MultiTimeframeFuzzyEngine):**
- Check if there's MF dispatch code to replace with registry
- May be minimal work if it delegates to FuzzyEngine
