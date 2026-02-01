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

**Next Task Notes:**
Task 5.2 updates the fuzzy-logic-engine skill with similar patterns for MEMBERSHIP_REGISTRY and v3-only FuzzyEngine.
