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
