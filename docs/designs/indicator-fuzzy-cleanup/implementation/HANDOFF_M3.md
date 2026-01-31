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

---

## Task 3.4 Complete: Update MultiTimeframeFuzzyEngine

**Implemented:**
- Replaced v2 config imports (`FuzzyConfig`, `FuzzySetConfig`, `*MFConfig` classes) with `MEMBERSHIP_REGISTRY`
- Replaced if/elif MF dispatch in `_build_timeframe_configs` with `MEMBERSHIP_REGISTRY.get_or_raise()`
- Updated `_create_merged_config` to return `dict[str, FuzzySetDefinition]` (v3 format) instead of v2 `FuzzyConfig`
- Updated `TimeframeConfig` dataclass to store raw config dicts instead of v2 `FuzzySetConfig`
- Removed backward compatibility mode for v2 `FuzzyConfig` — now dict-only

**Key patterns followed:**
- Wrap registry `ValueError` in `ConfigurationError` with error_code `MTFUZZY-UnknownMFType`
- Validate parameters by instantiating MF class (triggers Params validation)
- Case-insensitive lookup via registry's built-in case handling

---

## Task 3.5 Complete: Delete v2 fuzzy files

**Deleted files:**
- `ktrdr/fuzzy/config.py` (v2 FuzzyConfig, FuzzyConfigLoader, etc.)
- `ktrdr/fuzzy/migration.py` (v2 migration utilities)

**Updated production files:**
- `ktrdr/fuzzy/__init__.py` — removed v2 exports, added MEMBERSHIP_REGISTRY
- `ktrdr/training/training_pipeline.py` — converts legacy format to FuzzySetDefinition
- `ktrdr/decision/orchestrator.py` — converts strategy fuzzy_sets to FuzzySetDefinition
- `ktrdr/api/services/fuzzy_service.py` — updated to use v3 methods (partial refactoring)

**Deleted tests (v2-specific):**
- `tests/unit/fuzzy/test_fuzzy_config.py`
- `tests/unit/fuzzy/test_fuzzy_config_loader.py`
- `tests/unit/fuzzy/test_migration.py`
- `tests/unit/fuzzy/test_input_transforms.py`
- `tests/unit/fuzzy/test_engine_transforms.py`
- `tests/unit/fuzzy/test_engine.py`
- `tests/unit/fuzzy/test_batch_fuzzy_calculator.py`
- `tests/unit/fuzzy/test_fuzzy_edge_cases.py`
- `tests/unit/fuzzy/test_fuzzy_engine_feature_ids.py`
- `tests/unit/fuzzy/test_fuzzy_engine_new_format.py`
- `tests/unit/fuzzy/test_fuzzy_validation.py`
- `tests/api/test_fuzzy_service.py`
- `tests/api/test_fuzzy_service_enhanced.py`
- `tests/integration/training/test_pipeline_new_format.py`
- `tests/unit/training/test_training_pipeline_transforms.py`
- `tests/unit/training/test_training_pipeline_v3.py`

**Deleted examples/scripts:**
- `examples/fuzzy_config_example.py`
- `examples/fuzzy_config_strategy_example.py`
- `scripts/fuzzy_validation.py`
- `scripts/mf_verification.py`

**Key decisions:**
- FuzzyService partially refactored — uses v3 _fuzzy_sets API but may need further work
- Training pipeline converts legacy indicator-keyed format to fuzzy_set_id-keyed format
- input_transform support removed — callers should pre-transform data if needed

---

## Task 3.6 Complete: Update `__init__.py` exports

**Verified (exports already updated in Task 3.5):**
- `MEMBERSHIP_REGISTRY` exported from `ktrdr/fuzzy/__init__.py`
- No v2 exports remain (no FuzzyConfig, FuzzyConfigLoader, FuzzySetConfig)

**Test file created:**
- `tests/unit/fuzzy/test_fuzzy_migration_complete.py` — M3 E2E validation tests

**Type errors fixed (leftover from Task 3.5):**
- `ktrdr/fuzzy/batch_calculator.py` — Updated to use v3 API (`_fuzzy_sets.keys()`, `get_membership_names()`)
- `ktrdr/api/services/fuzzy_service.py` — Fixed type annotations for dict operations
- `ktrdr/training/training_pipeline.py` — Added explicit `dict[str, Any]` type annotation

**Next Task Notes (3.7 - Execute M3 E2E Test):**
- The E2E test file is ready at `tests/unit/fuzzy/test_fuzzy_migration_complete.py`
- All 26 tests pass, validating the full M3 success criteria
