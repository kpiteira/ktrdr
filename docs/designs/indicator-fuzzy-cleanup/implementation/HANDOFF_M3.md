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

**Next Task Notes (3.3 - Update FuzzyEngine):**
- Delete `_initialize_membership_functions` (v2 path)
- Delete `is_v3_format` detection logic
- Replace if/elif MF dispatch with `MEMBERSHIP_REGISTRY.get_or_raise()`
- Add clear error for non-dict config
