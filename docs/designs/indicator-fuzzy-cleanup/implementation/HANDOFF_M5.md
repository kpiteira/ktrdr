# M5 Handoff: Documentation

## Task 5.1 Complete: Update technical-indicators skill

**Changes made:**
- Removed `indicator_factory.py` and related files from Key Files table
- Updated Architecture Overview to show `INDICATOR_REGISTRY.get(type)` instead of `IndicatorFactory`
- Updated IndicatorEngine initialization comment to reference registry
- Replaced old "Adding a New Indicator" section with new Params pattern approach
- Added "Registry API" section documenting INDICATOR_REGISTRY methods

**Key patterns documented:**
1. Indicators auto-register via `__init_subclass__` - no manual registration needed
2. Use nested `class Params(BaseIndicator.Params)` for parameter validation
3. Call `ensure_all_registered()` before listing/validating indicators

---

## Task 5.2 Complete: Update fuzzy-logic-engine skill

**Changes made:**
- Removed v2 FuzzyConfig references from Key Files table and FuzzyEngine docs
- Removed `config.py` and `migration.py` from Key Files (no longer relevant)
- Updated FuzzyEngine initialization to show only dict format is supported
- Added "Registry API" section for MEMBERSHIP_REGISTRY
- Added "Adding a New Membership Function" section with Params pattern
- Changed "V3 mode auto-detected" gotcha to "FuzzyEngine only accepts dict format"

**Key patterns documented:**
1. MF classes auto-register via `__init_subclass__`
2. Use `@field_validator("parameters")` for parameter validation
3. Implement `_init_from_params()` and `evaluate()` methods

**Next Task Notes:**
Task 5.3 is VALIDATION — run the E2E test to verify all skill documentation is accurate.
