# M4 Regime Classifier — Handoff

## Task 4.1 Complete: Wire `labels.source: regime` into Training Pipeline

**TRIPLE DISPATCH:** Task spec mentioned dual dispatch (training_pipeline.py + host service orchestrator.py), but there's a THIRD location: `ktrdr/api/services/training/local_orchestrator.py`. All three now handle `source: regime`.

**Gotchas:**
- RegimeLabeler.generate_labels() returns NaN for the last `horizon` bars (no future data). Must `.dropna()` before converting to LongTensor.
- Feature/label alignment logic needed updating — same pattern as forward_return (truncate features to match shorter labels).
- Added `ValueError` for unknown sources — previously unknown sources silently fell through to zigzag default (which would crash on missing zigzag_threshold).

**Next task notes (4.2):**
- `ModelMetadataV3` is in `ktrdr/models/model_metadata.py`. Add `output_type` field.
- Training sets output_type based on label source: zigzag→classification, forward_return→regression, regime→regime_classification.
- Check how metadata is saved in the training pipeline to wire output_type setting.

## Task 4.2 Complete: Add `output_type` to ModelMetadata

**Gotchas:**
- `_save_v3_metadata` exists in BOTH `local_orchestrator.py` and host service `orchestrator.py` — must derive `label_source` from `config` dict (not from a variable in caller scope).
- Used `config.get("training", {}).get("labels", {}).get("source", "zigzag")` pattern to safely extract label source in static methods.

**Next task notes (4.3):**
- Strategy YAML goes in `strategies/` directory. Check architecture doc Section 3.3 for the complete YAML.
- Indicators used: `atr`, `bollinger_band_width`, `adx`, `squeeze_intensity` — verify all exist.
- ADX outputs use lowercase: `adx_14.adx`, `adx_14.plus_di`.

## Task 4.3 Complete: Create Seed Regime Strategy YAML

**Gotchas:**
- Indicator registry doesn't normalize underscores in type names. Architecture doc uses `bollinger_band_width` and `squeeze_intensity` but canonical names are `bollingerbandwidth` and `squeezeintensity`. Strategy YAML must use canonical names.
- `ktrdr validate` command goes through backend API — strategy file must be in container. Used Python loader for local validation instead.
- `config.training` is a plain dict, not a typed object — access with `.get("labels", {})`.

**Next task notes (4.4):**
- Training command: `uv run ktrdr train regime_classifier_seed_v1 --start 2019-01-01 --end 2024-01-01 --follow`
- Strategy needs to be accessible to the sandbox containers (may need rebuild).
- This is a MIXED task — training + evaluation. Need to assess accuracy vs 25% baseline.

## Task 4.4 Complete: Train and Evaluate Regime Classifier

**Gotchas:**
- `output_dim` was not being propagated to `MLPTradingModel.build_model()`. The model hardcoded 3 output neurons for classification. Fixed by: (1) adding `num_classes` config field to MLP `build_model()`, (2) injecting `num_classes: output_dim` into model_config in `TrainingPipeline.create_model()`.
- THREE places needed `output_dim` fixes: `local_orchestrator.py`, `training-host-service/orchestrator.py`, AND `ktrdr/neural/models/mlp.py`.
- CLI command is `ktrdr train` (not `ktrdr models train`), flags are `--start`/`--end` (not `--start-date`/`--end-date`).
- Strategy must be copied to `~/.ktrdr/shared/strategies/` for sandbox containers to access it.
- Sandbox agent ports (5010, 5020) conflict with prod — doesn't block training since agents not needed.

**Training results:**
- Test accuracy: 88.2%, F1: 0.83, Precision: 0.78, Recall: 0.88
- Val accuracy: 91.1%, Train accuracy: 91.5%
- Label distribution: {TRENDING_UP: 876, TRENDING_DOWN: 1014, RANGING: 25420, VOLATILE: 669}
- Class imbalance (91% RANGING) inflates accuracy — a always-RANGING baseline would get ~91%
- Model saved to `models/regime_classifier_seed/1h_v1` with `output_type: regime_classification`

**Next task notes (4.5):**
- VALIDATION task — use E2E agent workflow
- Model exists at `models/regime_classifier_seed/1h_v1` with all artifacts
