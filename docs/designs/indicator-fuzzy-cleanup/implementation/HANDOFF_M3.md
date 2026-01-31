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

**Next Task Notes (3.2):**
- Add `Params` nested classes with `@field_validator` to each MF subclass
- Validators should enforce parameter count and ordering constraints
- Validation errors should raise `ConfigurationError` (already imported)
- The existing `__init__` methods in each MF handle validation themselves — Task 3.2 will add Pydantic Params for registry-based instantiation, but won't need to change existing `__init__` logic since MFs are still created directly
