# M4 Handoff: Training Pipeline V3

## Task 4.1 Complete: TrainingPipeline for V3 Config

### Emergent Patterns

**TrainingPipelineV3 is a separate class (not modification of TrainingPipeline)**
- Original `TrainingPipeline` class with static methods preserved for v2 usage
- New `TrainingPipelineV3` class added for v3 strategy configurations
- Constructor accepts `StrategyConfigurationV3` and initializes engines with v3 config
- Pattern: separate class maintains backward compatibility

**FeatureResolver is the source of truth for feature ordering**
- Call `resolver.resolve(config)` to get canonical feature list
- `expected_columns = [f.feature_id for f in resolved]` is the order
- Features MUST be reordered to match this order before returning
- This order will be stored in `ModelMetadataV3` (Task 4.3)

**Group requirements by timeframe for efficient computation**
- `_group_requirements_by_timeframe(resolved)` returns `{timeframe: {indicators: set, fuzzy_sets: set}}`
- Only compute indicators that are actually needed
- Only apply fuzzy sets that are actually needed
- Avoids unnecessary computation for indicators not in nn_inputs

### Implementation Notes

**Column naming convention**
- Indicator columns: `{timeframe}_{indicator_id}` (from `compute_for_timeframe`)
- Multi-output indicators: `{timeframe}_{indicator_id}.{output_name}`
- Fuzzy columns: `{timeframe}_{fuzzy_set_id}_{membership}` (added by prepare_features)
- FuzzyEngine returns `{fuzzy_set_id}_{membership}` - caller adds timeframe prefix

**Type assertion for fuzzify result**
- `fuzzify()` returns Union type, but v3 mode always returns DataFrame
- Added runtime check: `if not isinstance(fuzzify_result, pd.DataFrame): raise TypeError(...)`
- This satisfies mypy and catches unexpected behavior

### Gotchas

**Don't modify indicator/fuzzy engine column names**
- IndicatorEngine.compute_for_timeframe() handles timeframe prefixing
- FuzzyEngine.fuzzify() returns columns WITHOUT timeframe prefix
- prepare_features() adds timeframe prefix to fuzzy columns

**Use underscore prefix for unused loop variables**
- `for _symbol, tf_data in data.items()` to satisfy linting
- Symbol not used in current implementation (could be used for logging)

**Avoid nested f-strings with quotes in Python < 3.12**
- Use intermediate variables for complex string formatting
- Example: `reqs_summary = ", ".join(...)` then `logger.debug(f"... {reqs_summary}")`

### Files Modified

- `ktrdr/training/training_pipeline.py`: Lines 1196-1380 (new TrainingPipelineV3 class)
- `tests/unit/training/test_training_pipeline_v3.py`: New file, 10 tests

---

## Next Task Notes

**Task 4.2: FuzzyNeuralProcessor update**
- Will need to validate feature columns against resolved_features
- FuzzyNeuralProcessor accepts v3 config and feature list
- Pattern: similar to TrainingPipelineV3 - accept config + resolved features in constructor

**Task 4.3: ModelMetadataV3**
- CRITICAL: Store `resolved_features` list from FeatureResolver
- This list is the source of truth for backtest feature ordering
- Use dataclass with `to_dict()`/`from_dict()` for JSON serialization
