# Handoff — M4: Gaussian MFs + Hybrid Encoding

## Task 4.1: NNInputSpec Extension for Raw Indicators ✅

**Files changed:** `ktrdr/config/models.py`, `ktrdr/config/feature_resolver.py`, `ktrdr/config/strategy_validator.py`

**What was done:**
- `NNInputSpec` now supports `raw_indicator` as alternative to `fuzzy_set` (mutually exclusive via `model_validator`)
- Added `normalization` field (minmax, zscore, none) for raw indicator value scaling
- `FeatureResolver.resolve()` handles raw indicators — produces `ResolvedFeature` with `fuzzy_set_id="__raw__"` sentinel
- Raw feature IDs follow pattern: `{tf}_{indicator_ref}_raw` (e.g., `5m_rsi_14_raw`)
- Strategy validator updated to validate `raw_indicator` references against indicators dict (including dot notation)

**Patterns:**
- `__raw__` sentinel on `fuzzy_set_id` distinguishes raw from fuzzy features downstream
- Dot notation works for raw indicators: `macd_12_26_9.line` → `indicator_id="macd_12_26_9"`, `indicator_output="line"`
- Feature ordering: nn_inputs list order preserved — raw features interleave with fuzzy as specified

**Gotchas:**
- `NNInputSpec.fuzzy_set` changed from required to optional — existing YAML still works because the validator ensures exactly one of the two is set
- Strategy validator must `continue` after handling raw_indicator to skip fuzzy_set validation

## Task 4.2: Hybrid Encoding in FuzzyNeuralProcessor ✅

**Files changed:** `ktrdr/training/fuzzy_neural_processor.py`

**What was done:**
- Added `normalize_raw_features()` — computes minmax/zscore/none normalization in-place and stores params
- Added `apply_normalization()` — applies stored params for inference/backtest consistency
- Added `normalization_params` dict to store computed statistics (min/max for minmax, mean/std for zscore)
- `_validate_fuzzy_range()` now skips `_raw` suffixed features (they aren't bounded to [0,1])

**Patterns:**
- Raw features flow through v3 mode naturally — they're just columns in the combined DataFrame
- Normalization is a separate explicit step (not automatic in prepare_input) so callers control when it happens
- `normalization_params` must be serialized into model metadata for backtest consistency

**Gotchas:**
- Normalization must be called BEFORE prepare_input for training, and with stored params for backtest
- Constant columns (std=0 or min=max) produce all-zero output — handled gracefully

## Task 4.3: Gaussian MF Strategy Templates ✅

**Files created:** `strategies/trend_tb_gaussian_signal_v1.yaml`

**What was done:**
- Created production-ready strategy YAML with Gaussian MFs (3 sets per indicator) + hybrid encoding
- 4 indicators: RSI, ADX, MACD, ROC — each with 3 Gaussian sets + raw value
- Total features per timeframe: 4 indicators × (3 fuzzy + 1 raw) = 16 features
- Dead zone tests confirm: zero dead zones across full RSI (0-100) and ADX (0-80) ranges
- Ruspini partition approximately satisfied (0.5 < sum < 2.0 for Gaussians)

**Patterns:**
- Gaussian σ values chosen for generous overlap: RSI σ=12-15, ADX σ=10-15
- MACD and ROC use zscore normalization (no fixed range); RSI and ADX use minmax
- Strategy designed for triple_barrier labeling (future M1 dependency)

## Task 4.4: FeatureCache Support for Raw Indicators ✅

**Files changed:** `ktrdr/backtesting/feature_cache.py`, `ktrdr/models/model_metadata.py`

**What was done:**
- `_group_requirements_by_timeframe` now separates `__raw__` features into `raw_features` list
- `compute_features` extracts raw indicator columns from `indicator_df` and applies stored normalization
- `ModelMetadata` now has `normalization_params` field (dict of feature_id → params) — serialized in to_dict/from_dict
- Normalization uses training-time params from model metadata (not recomputed on backtest data)

**Patterns:**
- Raw features get `feature_id` as column name (e.g., `5m_rsi_14_raw`), mapped from indicator column (e.g., `5m_rsi_14`)
- Normalization params must be saved during training and loaded at backtest — `normalization_params` on ModelMetadata is the bridge
- Dot notation for multi-output: `adx_14.adx` → indicator column `{tf}_adx_14.adx`

**Gotchas:**
- `normalization_params` defaults to empty dict — models without raw features work unchanged
- `getattr` with default used for backward compat with old metadata that lacks the field

## Task 4.5: Validation — Dead Zone Elimination ✅

**Validation results:**
- Strategy YAML validates via CLI: 32 resolved features (24 fuzzy + 8 raw)
- Dead zone analysis (all 4 indicators, 1000 samples each across full range):
  - RSI: 0/1000 dead zones (was 60.2% with triangular)
  - ADX: 0/1000 dead zones
  - MACD: 0/1000 dead zones (sigma widened from 0.0008 to 0.002 to cover tails)
  - ROC: 0/1000 dead zones (sigma widened from 0.2 to 0.35)
- Feature resolution: 24 fuzzy + 8 raw with correct `__raw__` sentinels and interleaved ordering
- Raw indicator features always non-zero for real data → hybrid encoding guarantees non-zero input

**Gotchas:**
- Initial MACD/ROC sigma values were too narrow for domain tails (316/94 dead zones). Widened sigmas fixed it.
- Dead zone threshold: membership < 0.01 counts as dead. Gaussian tails drop below this at extreme values if σ is too small.
