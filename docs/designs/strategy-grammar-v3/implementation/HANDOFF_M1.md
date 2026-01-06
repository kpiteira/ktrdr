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

### Next Task Notes

**For Task 1.2 (FeatureResolver):**
- Can import v3 models: `from ktrdr.config.models import StrategyConfigurationV3, NNInputSpec, FuzzySetDefinition`
- `FuzzySetDefinition.get_membership_names()` returns ordered list of membership names
- Access extra fields via `model_extra` dict
- Remember `timeframes` can be either `str` (for "all") or `list[str]`
