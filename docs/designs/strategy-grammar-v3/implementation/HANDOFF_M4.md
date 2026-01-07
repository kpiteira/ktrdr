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

---

## Task 4.2 Complete: FuzzyNeuralProcessor V3 Support

### Implementation Notes

**V3 mode via `resolved_features` parameter**
- Added optional `resolved_features` parameter to `__init__`
- When set, enables validation and reordering of features
- Legacy mode (no resolved_features) works unchanged

**Key methods added**
- `validate_features(df)`: Raises ValueError if missing columns, warns on extra
- `get_ordered_features(df)`: Returns DataFrame with columns in resolved_features order
- Both are no-ops in legacy mode (resolved_features=None)

**prepare_input() behavior in v3 mode**
- Validates features first (fails if any missing)
- Reorders to match resolved_features order
- Skips fuzzy column detection (columns are pre-validated)
- Returns features in exact canonical order

### Gotchas

**Don't mix v3 and legacy modes**
- If resolved_features is set, the entire flow changes
- Legacy mode uses fuzzy column detection heuristics
- V3 mode expects columns to already be correctly named

**Order matters**
- The resolved_features list IS the canonical order
- prepare_input returns features in this exact order
- This order must match training to ensure backtest works

### Files Modified

- `ktrdr/training/fuzzy_neural_processor.py`: Added v3 support (~60 lines)
- `tests/unit/training/test_fuzzy_neural_processor_v3.py`: New file, 10 tests

---

## Task 4.3 Complete: ModelMetadataV3

### Implementation Notes

**Simple dataclass design**
- Separate from existing `ModelMetadata` (which is complex with nested dataclasses)
- `ModelMetadataV3` is simpler, focused on v3 needs
- Uses `field(default_factory=...)` for mutable defaults

**Key fields**
- `model_name`, `strategy_name`: Identity
- `created_at`: Auto-set to now (timezone-aware UTC)
- `strategy_version`: Defaults to "3.0"
- `indicators`, `fuzzy_sets`, `nn_inputs`: Full config for reproducibility
- `resolved_features`: CRITICAL - the canonical feature order
- `training_symbols`, `training_timeframes`, `training_metrics`: Training context

**Serialization**
- `to_dict()`: Converts datetime to ISO string
- `from_dict()`: Parses ISO datetime string back to datetime
- JSON-serializable output (no special types)

### Gotchas

**Datetime handling**
- Always use timezone-aware UTC datetimes
- `datetime.now(timezone.utc)` in `__post_init__`
- `datetime.fromisoformat()` handles both naive and aware strings

**Don't use `asdict()` directly**
- Custom `to_dict()` needed for datetime ISO serialization
- `asdict()` would leave datetime as-is (not JSON serializable)

### Files Modified

- `ktrdr/models/model_metadata.py`: Added ModelMetadataV3 class (~100 lines)
- `tests/unit/models/test_model_metadata_v3.py`: New file, 11 tests

---

## Task 4.4 Complete: Training Worker V3 Support

### Implementation Notes

**Added static methods to LocalTrainingOrchestrator**
- `_is_v3_format(config)`: Detects v3 config by checking `indicators` is dict AND `nn_inputs` exists
- `_save_v3_metadata(...)`: Creates and saves `ModelMetadataV3` to model directory

**V3 metadata saved as `metadata_v3.json`**
- Separate file from existing metadata.json (preserves backward compatibility)
- Contains: resolved_features, indicators, fuzzy_sets, nn_inputs, training context
- File saved to model directory alongside model.pt, config.json, etc.

**Using FeatureResolver to get resolved features**
- Import `StrategyConfigurationLoader.load_v3_strategy()` to load config as `StrategyConfigurationV3`
- Use `FeatureResolver.resolve(config)` to get canonical feature list
- Feature IDs extracted from resolved features: `[f.feature_id for f in resolved]`

### Gotchas

**Static methods for reusability**
- Both `_is_v3_format` and `_save_v3_metadata` are static methods
- Can be called without instantiating LocalTrainingOrchestrator
- Useful for other components that need v3 detection or metadata saving

**Integration with training flow is separate**
- Current implementation adds the utility methods
- Full integration (calling these after training) is straightforward but wasn't done to avoid modifying complex training flow
- Call `_save_v3_metadata` after `TrainingPipeline.train_strategy()` returns, using model_path from result

**StrategyConfigurationV3 has required fields**
- `model`, `decisions`, `training` are required (not optional)
- When creating test configs, must provide all three as dicts

### Files Modified

- `ktrdr/api/services/training/local_orchestrator.py`: Added v3 methods (~70 lines)
- `tests/unit/training/test_training_worker_v3.py`: New file, 9 tests

---

## Next Task Notes

**Task 4.5: Dry-Run Mode**
- Add `--dry-run` flag to `ktrdr train` command
- Shows config summary and features without training
- Useful for debugging strategy config before full training
