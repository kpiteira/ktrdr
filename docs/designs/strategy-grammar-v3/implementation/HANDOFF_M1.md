# M1 Handoff: V3 Config Loading & Validation

## Task 1.1 Complete: V3 Pydantic Models

### Emergent Patterns

**Model/Decisions/Training sections use `dict[str, Any]`**
- V3 spec (ARCHITECTURE.md:148-150) references `ModelConfiguration`, `DecisionConfiguration`, `TrainingConfiguration`
- These typed models don't exist yet
- Used `dict[str, Any]` as temporary solution (matches v2 pattern)
- **Action for future tasks**: When proper models are created, update `StrategyConfigurationV3`

**Reused existing v2 configuration models**
- `TrainingDataConfiguration` and `DeploymentConfiguration` already exist and work for v3
- No duplication needed
- Import location: `ktrdr.config.models`

### Implementation Notes

**Shorthand expansion**
- Implemented via `@model_validator(mode='before')` in `FuzzySetDefinition`
- Expansion happens during Pydantic parsing, so all downstream code sees full form
- Pattern already used in `ktrdr/api/models/fuzzy.py` for similar use case

**Extra fields handling**
- `model_config = {"extra": "allow"}` for `IndicatorDefinition` and `FuzzySetDefinition`
- Extra fields stored in `model_extra` attribute (Pydantic v2)
- Access via: `instance.model_extra["field_name"]`

### Gotchas

**Enum values for SymbolMode**
- `SymbolMode.SINGLE` = `"single"` (NOT `"single_symbol"`)
- `SymbolMode.MULTI_SYMBOL` = `"multi_symbol"`
- Easy to get wrong when writing test data

### Files Modified

- `ktrdr/config/models.py`: Lines 646-754 (v3 models)
- `tests/unit/config/test_models_v3.py`: 16 tests (all passing)

---

## Task 1.2 Complete: FeatureResolver

### Implementation Notes

**Timeframe access pattern**
- `TimeframeConfiguration` is a Pydantic model, not a dict
- Access timeframes list via: `config.training_data.timeframes.timeframes`
- NOT `config.training_data.timeframes["list"]` (will fail with "not subscriptable")
- Field aliasing: YAML `list:` maps to model attribute `timeframes`

**Feature ordering is deterministic**
- Order preserved from: nn_inputs order → timeframes order → membership function order
- `FuzzySetDefinition.get_membership_names()` maintains order from extra fields
- Same input config always produces same feature list order

**Dot notation parsing**
- Simple split on `.` character: `"bbands_20_2.upper"` → `("bbands_20_2", "upper")`
- Single-output indicators have no dot, return `(indicator_id, None)`
- Pattern: `indicator_ref.split(".", 1)` handles both cases correctly

### Gotchas

**Type handling for timeframes**
- `NNInputSpec.timeframes` is `Union[list[str], str]` (str for "all")
- `TimeframeConfiguration.timeframes` is `list[str] | None`
- Need explicit type annotation when assigning to avoid mypy errors
- Pattern: `timeframes_to_use: list[str]` then assign with type ignore if needed

### Files Modified

- `ktrdr/config/feature_resolver.py`: New file (150 lines)
- `tests/unit/config/test_feature_resolver.py`: 13 tests (all passing)

---

## Task 1.3 Complete: V3 Strategy Validator

### Implementation Notes

**Validation approach**
- Created standalone `validate_v3_strategy()` function (not a method)
- Returns list of warnings; raises StrategyValidationError for fatal errors
- Validates all 5 rules from ARCHITECTURE.md lines 279-287

**Dot notation validation**
- Uses `BUILT_IN_INDICATORS` dict from `ktrdr.indicators.indicator_factory`
- Pattern: `BUILT_IN_INDICATORS.get(indicator_type.lower())`
- Checks `indicator_class.is_multi_output()` before allowing dot notation
- Validates output name against `indicator_class.get_output_names()`
- Handles unknown indicator types gracefully (log warning, skip validation)

**Error handling patterns**
- Collect all errors before raising (don't fail on first error)
- Include location context in all error messages (e.g., `fuzzy_sets.bad_ref.indicator`)
- Separate errors (fatal) from warnings (informational)
- Warnings use `StrategyValidationWarning` dataclass with message + location

### Gotchas

**Type hints for circular imports**
- Use `Any` type hint, not forward reference string
- Import `StrategyConfigurationV3` inside function to avoid circular imports
- Pattern: `def validate_v3_strategy(config: Any) -> list[StrategyValidationWarning]`

**BUILT_IN_INDICATORS access**
- Dictionary keys are lowercase: `BUILT_IN_INDICATORS.get(indicator_type.lower())`
- Returns `None` if indicator type unknown (handle gracefully)
- Each value is a class (e.g., `BollingerBandsIndicator`)

### Files Modified

- `ktrdr/config/strategy_validator.py`: Lines 1019-1182 (v3 validation code)
- `tests/unit/config/test_strategy_validator_v3.py`: 246 lines (11 tests, all passing)

---

## Task 1.4 Complete: V3 Strategy Loader

### Implementation Notes

**Circular import avoidance**
- Import `validate_v3_strategy` INSIDE the `load_v3_strategy()` method, not at module level
- Pattern: `from ktrdr.config.strategy_validator import validate_v3_strategy` inside function body
- Prevents circular import since `strategy_validator.py` imports from `strategy_loader.py`

**V3 detection logic**
- Simple and robust: `isinstance(config.get("indicators"), dict) and "nn_inputs" in config`
- V2 list indicators fail `isinstance()` check
- V2 dict indicators without `nn_inputs` fail second check
- Matches ARCHITECTURE.md spec exactly

**Error message clarity**
- V2 rejection: `"Strategy '{config_path.name}' is not v3 format. Run 'ktrdr strategy migrate' to upgrade."`
- Actionable guidance for users
- Migration command included in message

### Gotchas

**Validation warning logging**
- Iterate over warnings list and log each individually
- Pattern: `for w in warnings: logger.warning(f"Strategy validation: {w.message} at {w.location}")`
- Do NOT raise warnings; only `StrategyValidationError` should propagate

**Import location for testing**
- Mock patch path is `ktrdr.config.strategy_validator.validate_v3_strategy`
- NOT `ktrdr.config.strategy_loader.validate_v3_strategy` (since imported inside function)

### Files Modified

- `ktrdr/config/strategy_loader.py`: Lines 32-103 (v3 loading methods)
- `tests/unit/config/test_strategy_loader_v3.py`: 276 lines (8 tests, all passing)

### Next Task Notes

**For Task 1.5 (CLI validate command):**
- Use `loader.load_v3_strategy(path)` to load and validate
- Catch both `ValueError` (format/YAML errors) and `StrategyValidationError` (validation failures)
- Display features via `FeatureResolver().resolve(config)`
- Exit code 0 for success, 1 for any error
