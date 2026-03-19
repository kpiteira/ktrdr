---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M3: Phase 1 Integration + Validation

**Phase:** 1 — Integration of Layers 1 & 3
**Dependencies:** M1 (Triple Barrier Labeler), M2 (Training Pipeline)
**Branch:** `impl/sme-M3-phase1-integration` (from main, after M1+M2 merged)

---

## Task 3.1: Label Purging for Cross-Validation

**File(s):** `ktrdr/training/training_pipeline.py`, `ktrdr/training/sample_weights.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Implement label purging for train/validation splitting with overlapping TB labels. Standard random splits leak future information: a training sample at bar t has a label depending on prices up to t+50, while a validation sample at t+1 also depends on overlapping prices. Label purging removes training samples whose active periods overlap with any validation sample's active period.

**Implementation Notes:**
- Create a `purged_train_val_split(labels, holding_periods, val_ratio=0.2, embargo_pct=0.01)` function in `sample_weights.py`
- The split must be temporal (not random): val set is the last `val_ratio` fraction of data
- Purge: remove training samples whose active period `[t, t + holding_period[t]]` overlaps with any validation sample's start time
- Embargo: additionally remove `embargo_pct * len(data)` training samples before the val set boundary (extra buffer)
- Returns: `(train_indices, val_indices)` — numpy arrays of integer indices
- Integration point: `TrainingPipeline` should use this for train/val split when `source: triple_barrier` (standard random split for other label types)
- This replaces the current implicit split in `MLPTradingModel.train()` which receives pre-split `validation_data`

**Testing Requirements:**
- [ ] Test purging removes overlapping samples near the train/val boundary
- [ ] Test embargo adds additional buffer beyond purging
- [ ] Test no leakage: no training sample's active period extends into val set
- [ ] Test with short holding periods: minimal purging needed
- [ ] Test with long holding periods: significant purging (more overlap)
- [ ] Test edge case: holding_period longer than val set (all val samples overlap)
- [ ] Test output indices are valid and non-overlapping

**Acceptance Criteria:**
- [ ] Purged split prevents information leakage between train and val sets
- [ ] Embargo provides additional safety margin
- [ ] Applied automatically when label source is `triple_barrier`

---

## Task 3.2: Signal Model Strategy YAML Template

**File(s):** `strategies/` or `configs/` directory — new YAML template
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Create a complete strategy YAML for a TB-trained signal model, replacing the current `trend_regression_signal_v1.yaml` pattern. This YAML becomes the template for Phase 1 experiments.

**Implementation Notes:**
- Based on existing `~/.ktrdr/shared/strategies/trend_regression_signal_v1.yaml` structure
- Key changes from existing:
  ```yaml
  training:
    labels:
      source: triple_barrier
      pt_multiplier: 2.0
      sl_multiplier: 1.5
      max_holding_period: 50
      vol_span: 50
      cusum_threshold: 1.0      # optional — omit for all-bar labeling
      compute_weights: true      # enable uniqueness weighting

    learning_rate: 0.001
    batch_size: 256
    epochs: 200                  # higher max, early stopping will cut
    early_stopping: true
    patience: 15
    lr_scheduler: true
    gradient_clip: 1.0
    loss: focal
    focal_gamma: 2.0

  model:
    type: mlp
    architecture:
      hidden_layers: [64, 32]
      dropout: 0.3

  decisions:
    output_format: classification
    num_classes: 3
    confidence_threshold: 0.5
  ```
- Keep the same indicators as existing trend signal (RSI, ADX, MACD, ROC) for apples-to-apples comparison in Experiment 1
- Create two variants:
  1. `trend_tb_signal_v1.yaml` — trend-regime signal model with TB labels
  2. `range_tb_signal_v1.yaml` — range-regime signal model with TB labels
- Place in `strategies/` directory alongside existing strategy files

**Testing Requirements:**
- [ ] YAML is valid and parseable by `StrategyConfigurationV3`
- [ ] All TB label parameters are present and have reasonable defaults
- [ ] Training config includes all M2 improvements (mini-batch, early stopping, etc.)
- [ ] Strategy validation passes: `ktrdr strategies validate <yaml>`

**Acceptance Criteria:**
- [ ] Two complete strategy YAMLs for TB-trained signal models
- [ ] Configs are self-documenting (comments explaining parameter choices)
- [ ] Parseable by existing strategy validation infrastructure

---

## Task 3.3: End-to-End Training Integration

**File(s):** `ktrdr/training/training_pipeline.py`
**Type:** CODING
**Estimated time:** 3 hours

**Description:**
Wire the full training path: strategy YAML → indicators → fuzzy → TB labels → purged split → mini-batch training with all M2 improvements. Verify the complete pipeline from YAML to trained model file.

**Implementation Notes:**
- The main integration point is `TrainingPipeline.run()` (or however training is orchestrated)
- When label source is `triple_barrier`:
  1. `create_labels()` produces LongTensor + holding_periods + optional weights
  2. `purged_train_val_split()` creates non-leaking train/val indices
  3. Weights passed to `MLPTradingModel.train()` via `sample_weights` parameter
  4. Model output_format set to `classification` with `num_classes: 3`
- Verify the label tensor is correctly aligned with feature tensor (TB labeler may produce fewer labels than features due to trimming — need to align)
- The feature/label alignment issue: TB labeler trims last `max_holding_period` bars. Features must be trimmed to match. This alignment must happen BEFORE train/val split.
- If CUSUM filtering is active: features must be filtered to match CUSUM-selected event bars

**Testing Requirements:**
- [ ] Integration test: full pipeline from strategy YAML to saved model
- [ ] Feature/label alignment: feature tensor and label tensor have same length
- [ ] CUSUM filtering: feature tensor filtered to match event bars
- [ ] Purged split applied: train/val indices don't overlap in label space
- [ ] Model saves correctly and includes metadata (output_type, feature names)
- [ ] Trained model loads back via `ModelBundle.load()` with correct metadata

**Acceptance Criteria:**
- [ ] Complete training path works end-to-end with TB labels
- [ ] Feature/label alignment is correct after trimming and filtering
- [ ] Saved model loads and produces 3-class probability output

---

## Task 3.4: DecisionFunction Classification Verification

**File(s):** `ktrdr/backtesting/decision_function.py` (verify, minimal changes if any)
**Type:** CODING
**Estimated time:** 1-2 hours

**Description:**
Verify that `DecisionFunction` correctly handles 3-class TB output. The existing classification path (softmax → argmax → Signal enum) should work, but verify the class mapping is correct: class 0 = BUY (TP hit), class 1 = HOLD (time expiry), class 2 = SELL (SL hit).

**Implementation Notes:**
- The existing `_CLASS_NAMES["classification"] = ["BUY", "HOLD", "SELL"]` maps to indices 0, 1, 2
- TB labels are mapped to: +1→0 (BUY), 0→1 (HOLD), -1→2 (SELL) in Task 1.4
- `_predict()` applies softmax and argmax — should produce correct Signal enum
- `confidence_threshold` filter: if `max(probabilities) < threshold` → HOLD — this is the existing behavior and exactly what we want for TB models
- Context gate via `ThresholdModifier` adjusts `confidence_threshold` — works unchanged
- **Key verification**: run inference on a saved TB model and confirm output makes sense
- May need to verify `output_format` detection — TB models should use `classification`, not `regression`

**Testing Requirements:**
- [ ] Test: 3-class softmax output maps to correct Signal (BUY/HOLD/SELL)
- [ ] Test: confidence_threshold filters low-confidence predictions to HOLD
- [ ] Test: ThresholdModifier works with TB classification (context gate)
- [ ] Test: probabilities dict includes all 3 classes with correct names
- [ ] Test: with a mock TB model that outputs known probabilities, verify correct signal

**Acceptance Criteria:**
- [ ] DecisionFunction handles TB 3-class output without code changes (or with minimal adjustments)
- [ ] Confidence threshold and context gate work correctly with TB models
- [ ] Class names are correct in reasoning/probabilities output

---

## Task 3.5: Validation — Phase 1 End-to-End (Experiment 1)

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 3 hours

**Description:**
Execute Design Experiment 1: Triple Barrier vs Forward Return Baseline. This is the critical experiment that determines whether fixing the target (Layer 1) and training pipeline (Layer 3) produces models that actually learn.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing tests covering signal model training + backtest
3. Design a test (via `ke2e-test-designer` if needed) that:
   a. Trains two signal models on EURUSD 1h (2020-2023), same indicators (RSI/ADX/MACD/ROC), same architecture ([64,32]):
      - Model A: `source: forward_return` (baseline, current behavior)
      - Model B: `source: triple_barrier` with M2 training improvements
   b. Runs ensemble backtest on 2024 validation data for both
   c. Compares:
      - Training loss convergence (does TB model show gradual improvement vs instant mean collapse?)
      - Val accuracy (>55% for TB vs ~50% for forward return)
      - Hidden layer activations (are they non-zero for TB model?)
      - Backtest Sharpe ratio (>0.3 for TB model)
      - Trade count and quality
4. Execute via `ke2e-test-runner`

**Success Criteria (from Design Section 11 — Phase 1):**
- [ ] Model val accuracy > 55% (above no-information rate for 3 classes)
- [ ] Hidden layer activations are non-zero (model uses features, not just bias)
- [ ] Training converges with early stopping (not running all epochs)
- [ ] Signal models generate directional trade decisions (not constant output)
- [ ] Backtest Sharpe > 0.3 on 2024 validation window

**Go/No-Go Decision:**
- If val accuracy > 55% → Phase 1 successful, proceed to M4/M5
- If val accuracy 50-55% → investigate: are some regimes better? Is feature encoding (Phase 2) the bottleneck?
- If val accuracy ~50% → Features carry no signal for TB outcomes either → Phase 2 becomes the critical experiment
