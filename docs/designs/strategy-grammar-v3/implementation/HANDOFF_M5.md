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

## Next Task Notes

**Task 5.2: BacktestingService V3 Support**
- Will need to load `ModelMetadataV3` from model directory
- Check `metadata_v3.json` file (saved by training worker in M4)
- Use `ModelMetadataV3.from_dict(json.load(...))` to deserialize
- Create FeatureCacheV3 with loaded config and metadata
