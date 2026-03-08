---
design: docs/designs/predictive-features/regime-detection/DESIGN.md
architecture: docs/designs/predictive-features/regime-detection/ARCHITECTURE.md
---

# M4: Regime Classifier

**Thread:** Regime Detection
**JTBD:** "As a researcher, I want to train a regime classifier that beats the random baseline so I can use it to route signals to specialized models."
**Depends on:** M2 (Regime Labeling)
**Tasks:** 5

---

## Task 4.1: Wire `labels.source: regime` into Training Pipeline

**File(s):**
- `ktrdr/training/training_pipeline.py` (add regime label dispatch)
- `training-host-service/orchestrator.py` (add regime label dispatch — DUAL DISPATCH!)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `regime` as a new label source in the training pipeline's label dispatch. When `labels.source == "regime"`, instantiate `RegimeLabeler` with config params and generate 4-class labels. Uses cross-entropy loss with 4 output classes.

**Implementation Notes:**
- **DUAL DISPATCH:** Must add dispatch in BOTH `training_pipeline.py` (line ~414) AND `training-host-service/orchestrator.py`. The host service has its own separate label dispatch code — we hit this bug before with `forward_return`.
- Pattern: `if label_config["source"] == "regime": labeler = RegimeLabeler(horizon=..., trending_threshold=..., ...)` — see architecture doc Section 3.1
- Regime labels are `LongTensor` (classification), same as zigzag, NOT `FloatTensor` (regression)
- Config params from strategy YAML: `horizon` (default 24), `trending_threshold` (default 0.5), `vol_crisis_threshold` (default 2.0), `vol_lookback` (default 120)

**Testing Requirements:**
- [ ] `source: regime` in label config triggers RegimeLabeler
- [ ] Labels are 4-class LongTensor (values 0-3)
- [ ] Default params used when not specified in config
- [ ] Custom params override defaults
- [ ] Unknown source raises clear error
- [ ] Host service dispatch matches container worker dispatch

**Acceptance Criteria:**
- [ ] Training pipeline generates regime labels from strategy config
- [ ] Both dispatch locations updated and tested

---

## Task 4.2: Add `output_type` to ModelMetadata

**File(s):**
- `ktrdr/models/model_metadata.py` (add `output_type` field)
- `ktrdr/backtesting/model_bundle.py` (read/write `output_type`)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Add `output_type: str = "classification"` field to `ModelMetadataV3`. Values: `"classification"` (default, backward compat), `"regression"`, `"regime_classification"`. The training pipeline sets this based on strategy config. The ensemble runner reads it to determine how to interpret model outputs.

**Implementation Notes:**
- Add to `ModelMetadataV3` at `model_metadata.py:16-122`
- Default `"classification"` ensures backward compatibility — existing models without this field are treated as standard classification
- Set during training based on `labels.source`: zigzag → "classification", forward_return → "regression", regime → "regime_classification"
- `to_dict()` and `from_dict()` must serialize/deserialize this field
- `model_bundle.py` should read `output_type` when loading metadata

**Testing Requirements:**
- [ ] Default `output_type` is `"classification"`
- [ ] Serialization round-trip preserves `output_type`
- [ ] Existing metadata without `output_type` deserializes with default
- [ ] Training sets `output_type` based on label source

**Acceptance Criteria:**
- [ ] `output_type` persisted in `metadata_v3.json`
- [ ] Backward compatible with existing model bundles

---

## Task 4.3: Create Seed Regime Strategy YAML

**File(s):**
- `strategies/regime_classifier_seed_v1.yaml` (new)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Create the seed regime classifier strategy from architecture doc Section 3.3. Uses ATR (short+long), Bollinger Band Width, ADX (+DI), and Squeeze Intensity — indicators chosen because they capture volatility state and trend strength, which are the features most relevant to regime classification.

**Implementation Notes:**
- Copy from architecture doc Section 3.3 — it's a complete, validated v3 strategy YAML
- Verify all indicator types exist: `atr` ✓, `bollinger_band_width` ✓, `adx` ✓, `squeeze_intensity` ✓
- ADX outputs are lowercase: `adx_14.adx`, `adx_14.plus_di` (verified in codebase)
- Labels config: `source: regime`, `horizon: 24`, thresholds from M2 analysis results
- Validate with `ktrdr strategy validate regime_classifier_seed_v1.yaml`

**Testing Requirements:**
- [ ] Strategy validates with `ktrdr strategy validate`
- [ ] All indicator types are recognized
- [ ] All fuzzy set indicator references resolve
- [ ] All nn_input fuzzy_set references resolve

**Acceptance Criteria:**
- [ ] Valid v3 strategy YAML at `strategies/regime_classifier_seed_v1.yaml`
- [ ] Strategy validates without errors

---

## Task 4.4: Train and Evaluate Regime Classifier

**File(s):** None (training/evaluation task)
**Type:** MIXED
**Estimated time:** 3 hours

**Description:**
Train the regime classifier on EURUSD 1h (2019-2024) using the seed strategy. Evaluate on held-out data. Compare accuracy vs 25% random baseline for 4-class. Assess prediction persistence (not flipping every bar) and per-class accuracy.

**Implementation Notes:**
- Train: `ktrdr models train regime_classifier_seed_v1.yaml`
- Evaluate: accuracy, confusion matrix, per-class precision/recall
- 4-class random baseline = 25% accuracy
- Key quality metrics:
  - Overall accuracy > 30% (meaningfully above random)
  - Prediction persistence: mean run length > 10 bars (not flipping constantly)
  - No class completely ignored (all classes have >5% of predictions)
- If accuracy is poor, try: class-weighted cross-entropy, different architectures, different indicators
- Record best model path for use in M7

**Acceptance Criteria:**
- [ ] Regime classifier trained successfully
- [ ] Accuracy exceeds 25% random baseline
- [ ] Predictions show reasonable persistence (>10 bar mean run length)
- [ ] All 4 classes predicted (not degenerate)

---

## Task 4.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate regime classifier training end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Train a regime classifier using the regime_classifier_seed_v1 strategy. Verify training completes, model is saved with output_type=regime_classification in metadata, and inference produces 4-class probabilities."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure — real training, real model saving
5. Verify: model saved, metadata has `output_type: regime_classification`, inference produces 4 probability values

**Acceptance Criteria:**
- [ ] Training completes without error
- [ ] `metadata_v3.json` includes `output_type: "regime_classification"`
- [ ] Model produces 4-class softmax output on inference
- [ ] Feature validation passes (FeatureCache validates features)
