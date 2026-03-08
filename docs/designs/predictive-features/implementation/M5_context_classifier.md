---
design: docs/designs/predictive-features/multi-timeframe-context/DESIGN.md
architecture: docs/designs/predictive-features/multi-timeframe-context/ARCHITECTURE.md
---

# M5: Context Classifier

**Thread:** Multi-TF Context
**JTBD:** "As a researcher, I want to train a context classifier that beats the random baseline so I can use daily trend direction to gate hourly signal models."
**Depends on:** M3 (Context Labeling)
**Tasks:** 5

---

## Task 5.1: Wire `labels.source: context` into Training Pipeline

**File(s):**
- `ktrdr/training/training_pipeline.py` (add context label dispatch)
- `training-host-service/orchestrator.py` (add context label dispatch — DUAL DISPATCH!)

**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add `context` as a new label source. When `labels.source == "context"`, instantiate `ContextLabeler` with config params and generate 3-class labels (BULLISH/BEARISH/NEUTRAL). Uses cross-entropy loss with 3 output classes.

**Implementation Notes:**
- **DUAL DISPATCH:** Both `training_pipeline.py` AND `training-host-service/orchestrator.py` — same pattern as M4's regime dispatch.
- Pattern: `elif label_config["source"] == "context": labeler = ContextLabeler(horizon=..., bullish_threshold=..., bearish_threshold=...)`
- Context labels are `LongTensor` (classification), 3 classes
- Config params: `horizon` (default 5), `bullish_threshold` (default 0.005), `bearish_threshold` (default -0.005)
- Note: context model trains on daily data (`timeframe: 1d`), not hourly

**Testing Requirements:**
- [ ] `source: context` triggers ContextLabeler
- [ ] Labels are 3-class LongTensor (values 0-2)
- [ ] Default and custom params work correctly
- [ ] Both dispatch locations updated

**Acceptance Criteria:**
- [ ] Training pipeline generates context labels
- [ ] Both dispatch locations handle context source

---

## Task 5.2: Add `context_classification` Output Type

**File(s):**
- `ktrdr/models/model_metadata.py` (add `context_classification` to output_type values)

**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Add `"context_classification"` as a valid `output_type` value. Set it when `labels.source == "context"` during training. This parallels M4's `regime_classification`.

**Implementation Notes:**
- This is a value addition, not a code change — `output_type` is a plain string field (added in M4 Task 4.2)
- Set in training pipeline: when `labels.source == "context"`, set `metadata.output_type = "context_classification"`
- Ensemble runner will use this to identify the context model

**Testing Requirements:**
- [ ] Training with `source: context` saves `output_type: "context_classification"` in metadata
- [ ] Serialization round-trip preserves value

**Acceptance Criteria:**
- [ ] Context classifier metadata has `output_type: "context_classification"`

---

## Task 5.3: Create Seed Context Strategy YAML

**File(s):**
- `strategies/context_classifier_seed_v1.yaml` (new)

**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Create the seed context classifier strategy from architecture doc Section 4.1. Uses daily ROC (10, 20), ADX, RSI, and EMA — indicators that capture trend direction and strength on a daily timeframe.

**Implementation Notes:**
- Copy from architecture doc Section 4.1 — complete v3 strategy
- Trains on daily data: `timeframe: "1d"`, `symbol: EURUSD`
- All indicator types exist: `roc` ✓, `adx` ✓, `rsi` ✓, `ema` ✓
- **No `output_activation: softmax`** — MLP applies softmax via cross-entropy loss. Specifying it would cause double-softmax.
- Labels: `source: context`, `horizon: 5`, thresholds from M3 analysis
- Validate with `ktrdr strategy validate`

**Testing Requirements:**
- [ ] Strategy validates without errors
- [ ] All indicator types recognized
- [ ] All fuzzy set and nn_input references resolve

**Acceptance Criteria:**
- [ ] Valid v3 strategy at `strategies/context_classifier_seed_v1.yaml`
- [ ] Passes strategy validation

---

## Task 5.4: Train and Evaluate Context Classifier

**File(s):** None (training/evaluation task)
**Type:** MIXED
**Estimated time:** 3 hours

**Description:**
Train the context classifier on EURUSD 1d. Evaluate accuracy vs 33% random baseline (3-class). Assess prediction persistence and whether filtering a naive hourly momentum strategy by predicted context improves performance.

**Implementation Notes:**
- Train: `ktrdr models train context_classifier_seed_v1.yaml`
- Quality metrics:
  - Overall accuracy > 38% (above 33% random)
  - Prediction persistence: mean run length > 3 days
  - No class completely ignored
- Qualitative test: use predicted context to filter a simple hourly strategy. Does trading only in "bullish context" direction produce better results?
- Record model path for use in M8

**Acceptance Criteria:**
- [ ] Context classifier trained successfully
- [ ] Accuracy exceeds 33% random baseline
- [ ] Predictions show persistence (>3 day mean run length)
- [ ] All 3 classes predicted

---

## Task 5.5: Validation

**File(s):** None (validation task)
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate context classifier training end-to-end.

**Validation Steps:**
1. Load the `ke2e` skill before designing any validation
2. Invoke `ke2e-test-scout` with: "Train a context classifier on EURUSD 1d using the context_classifier_seed_v1 strategy. Verify training completes, model saved with output_type=context_classification, and inference produces 3-class probabilities."
3. Invoke `ke2e-test-runner` with the identified test recipes
4. Tests must exercise real infrastructure
5. Verify: model saved, metadata correct, inference produces 3 probability values

**Acceptance Criteria:**
- [ ] Training completes without error
- [ ] `metadata_v3.json` includes `output_type: "context_classification"`
- [ ] Model produces 3-class softmax output on inference
