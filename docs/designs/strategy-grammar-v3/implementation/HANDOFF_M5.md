# M5 Handoff: Backtest Pipeline V3

## Task 5.1 Complete: FeatureCache for V3

### Implementation Notes

**FeatureCacheV3 is a separate class (not modification of FeatureCache)**
- Original `FeatureCache` class preserved for v2/legacy usage
- New `FeatureCacheV3` class added for v3 strategy configurations
- Pattern: matches TrainingPipelineV3 approach from M4

**Constructor signature**
```python
FeatureCacheV3(config: StrategyConfigurationV3, model_metadata: ModelMetadataV3)
```
- Uses v3 config for IndicatorEngine and FuzzyEngine initialization
- Extracts `expected_features` from `model_metadata.resolved_features`

**compute_features mirrors TrainingPipelineV3**
- Uses `FeatureResolver.resolve(config)` to get feature requirements
- Groups by timeframe with `_group_requirements_by_timeframe(resolved)`
- Same indicator computation and fuzzification logic as training
- Input is `dict[str, pd.DataFrame]` (single symbol, {timeframe: DataFrame})

### Gotchas

**Input format differs from TrainingPipelineV3**
- TrainingPipelineV3 accepts: `{symbol: {timeframe: DataFrame}}`
- FeatureCacheV3 accepts: `{timeframe: DataFrame}` (single symbol)
- This is intentional - backtest is single-symbol

**Validation is strict on missing, lenient on extra**
- Missing expected features → raises ValueError (critical error)
- Extra computed features → logs warning, ignores them
- Order is enforced by reordering result to match expected_features

### Files Modified

- `ktrdr/backtesting/feature_cache.py`: Added FeatureCacheV3 class (~180 lines)
- `tests/unit/backtesting/test_feature_cache_v3.py`: New file, 11 tests

---

## Task 5.2 Complete: BacktestingService V3 Support

### Implementation Notes

**Static methods added to BacktestingService**
- `load_v3_metadata(model_path)` - Load ModelMetadataV3 from metadata_v3.json
- `is_v3_model(model_path)` - Check if model has v3 metadata file
- `validate_v3_model(model_path)` - Validate and raise if not v3
- `reconstruct_config_from_metadata(metadata)` - Rebuild StrategyConfigurationV3

**Usage pattern**
```python
# Check if v3 model
if BacktestingService.is_v3_model(model_path):
    # Load metadata
    metadata = BacktestingService.load_v3_metadata(model_path)
    # Reconstruct config
    config = BacktestingService.reconstruct_config_from_metadata(metadata)
    # Create feature cache
    cache = FeatureCacheV3(config, metadata)
```

### Gotchas

**metadata_v3.json is the source file**
- V3 models store metadata in `metadata_v3.json` (not `metadata.json`)
- `is_v3_model()` checks for this file's existence
- `load_v3_metadata()` raises FileNotFoundError if missing

**Config reconstruction uses defaults for some fields**
- `model`, `decisions`, `training` fields get default values
- Full config stored in metadata includes indicators, fuzzy_sets, nn_inputs
- Training data context (symbols, timeframes) preserved in metadata

### Files Modified

- `ktrdr/backtesting/backtesting_service.py`: Added 4 static methods (~150 lines)
- `tests/unit/backtesting/test_backtesting_service_v3.py`: New file, 10 tests

---

## Next Task Notes

**Task 5.3: Feature Order Validation**
- Add explicit `_validate_feature_order()` method to FeatureCacheV3
- Show first mismatch position in error message
- Distinguish between order mismatch and count mismatch
