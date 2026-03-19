---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M5: Combined Validation + Experiments

**Phase:** 1+2 Combined — All Three Layers Fixed
**Dependencies:** M3 (Phase 1 Integration), M4 (Gaussian MFs + Hybrid)
**Branch:** `impl/sme-M5-combined-validation` (from main, after M3+M4 merged)

---

## Task 5.1: Ensemble Config with TB Signal Models

**File(s):** `configs/` directory — new ensemble YAML files
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Create ensemble configuration files that use TB-trained signal models with Gaussian MFs, replacing the existing regression signal model ensemble configs. These configs wire the evolved signal models into the existing ensemble routing infrastructure.

**Implementation Notes:**
- Based on existing `configs/ensemble_regression_context_gated.yaml` structure
- Key differences from existing:
  - Signal model paths point to TB-trained models (will be created during training)
  - `output_type: classification` instead of `regression` for signal models
  - Regime and context models unchanged
- Create 3 variants for comparison:
  1. `ensemble_tb_regime_only.yaml` — regime routing + TB signal models, no context gate
  2. `ensemble_tb_context_gated.yaml` — regime routing + TB signal models + context gate
  3. Container variants of both (using `/app/models/` paths)
- The context gate mechanism (ThresholdModifier) works with classification models — it adjusts `confidence_threshold` which is the existing classification code path
- Verify `allow_short_from_flat: true` is set (forex pair)

**Testing Requirements:**
- [ ] Ensemble YAML parses correctly
- [ ] Signal model `output_type: classification` is set
- [ ] Regime and context model configs unchanged from existing working configs
- [ ] Context gate modifiers have reasonable values (aligned_discount: 0.2, counter_premium: 0.3)

**Acceptance Criteria:**
- [ ] Ensemble configs ready for backtest with TB-trained signal models
- [ ] Both regime-only and context-gated variants created
- [ ] Compatible with existing `EnsembleBacktestRunner`

---

## Task 5.2: Train Signal Models with Full Pipeline

**File(s):** Strategy YAMLs from M3 + M4
**Type:** MIXED (research + execution)
**Estimated time:** 3 hours

**Description:**
Train the actual signal models using the full evolved pipeline: TB labels + all training improvements + Gaussian MFs + hybrid encoding. This produces the model files needed for ensemble backtesting.

**Implementation Notes:**
- Train 2 signal models:
  1. `trend_tb_gaussian_signal` — for trending regimes (RSI, ADX, MACD, ROC)
  2. `range_tb_gaussian_signal` — for ranging regimes (Stochastic, WilliamsR, RSI, BBWidth)
- Training data: EURUSD 1h, 2020-01-01 to 2023-12-31
- Use the Gaussian + hybrid strategy YAMLs from M4 Task 4.3
- Use the TB label config from M3 Task 3.2
- Via CLI: `uv run ktrdr models train <strategy>.yaml EURUSD 1h --start-date 2020-01-01 --end-date 2023-12-31`
- Or via sandbox if CLI training path supports TB labels
- After training, inspect:
  - Training history: did early stopping fire? At what epoch?
  - Val accuracy: > 55%?
  - Class distribution of predictions: not all same class?
  - Hidden layer activations: non-zero?

**Testing Requirements:**
- [ ] Both models train to completion without errors
- [ ] Early stopping activates (training doesn't run all epochs)
- [ ] Val accuracy is recorded and > chance level (33% for 3-class)
- [ ] Model files saved with correct metadata (output_type, resolved_features)
- [ ] Models load correctly via ModelBundle.load()

**Acceptance Criteria:**
- [ ] 2 trained signal models available for ensemble backtesting
- [ ] Training metrics logged and inspectable
- [ ] Models produce 3-class probability output on inference

---

## Task 5.3: Experiment 1 — TB vs Forward Return Comparison

**File(s):** N/A (experiment execution)
**Type:** RESEARCH
**Estimated time:** 2-3 hours

**Description:**
Execute Design Experiment 1 in full: compare TB-trained signal models (with all improvements) against the existing forward-return regression models. This is the definitive test of whether fixing all three layers produces working signal models.

**Implementation Notes:**
- Run ensemble backtest with both model sets on same data (EURUSD 1h, 2024):
  1. Regime-only ensemble with OLD regression models (existing `ensemble_regression_regime_only.yaml`)
  2. Regime-only ensemble with NEW TB classification models (from Task 5.1)
  3. Context-gated ensemble with NEW TB models (from Task 5.1)
- Compare metrics:
  - Trade count (old models: 15-18 near-random; new should be fewer, more selective)
  - Win rate (old: ~50%; new: target >55%)
  - Sharpe ratio (old: ~0; new: target >0.3)
  - Max drawdown
  - Signal diversity (old models output constant; new should vary)
- Document results in experiment log

**Key Comparison Table (fill in with actual results):**

| Metric | Forward Return (old) | TB + Gaussian (new) | Delta |
|--------|---------------------|--------------------| ------|
| Val accuracy | ~50% | ? | |
| Trade count | 15-18 | ? | |
| Win rate | ~50% | ? | |
| Sharpe | ~0 | ? | |
| Max drawdown | ? | ? | |
| Unique signal values | 1-2 (constant) | ? | |

**Acceptance Criteria:**
- [ ] Experiment completed with documented results
- [ ] Comparison table populated with actual metrics
- [ ] Go/no-go assessment for Phases 3-4 based on results

---

## Task 5.4: Validation — Full Combined E2E

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 3 hours

**Description:**
Full end-to-end validation: train TB signal models with Gaussian MFs + hybrid encoding + upgraded training pipeline, then run ensemble backtest (regime-only and context-gated), comparing against forward-return baseline. This validates all three layers are fixed and working together.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to search for existing tests covering ensemble backtesting with classification signal models
3. Design a comprehensive test (via `ke2e-test-designer` if needed) that:
   a. Verifies trained TB models exist and load correctly
   b. Runs regime-only ensemble backtest with TB models on EURUSD 1h 2024
   c. Runs context-gated ensemble backtest with TB models on same data
   d. Verifies signal models produce varied output (not constant)
   e. Compares trade count, win rate, Sharpe vs forward-return baseline
   f. Checks context gate has observable effect (context-gated ≠ regime-only)
4. Execute via `ke2e-test-runner`

**Success Criteria (from Design Section 11 — combined Phase 1+2):**
- [ ] Signal models generate directional trade decisions (not constant output)
- [ ] Val accuracy > 55% (above no-information rate)
- [ ] Zero dead-zone bars with Gaussian MFs
- [ ] Backtest Sharpe > 0.3 on 2024 validation window
- [ ] Context gate has observable effect on trade filtering
- [ ] All three layers demonstrably fixed: target (TB), features (Gaussian+hybrid), training (mini-batch+early stopping)

**Go/No-Go for Phases 3-4:**
- Signal model accuracy > 55% → M6 (meta-labeling) can add value on top
- Signal model accuracy > 55% → M7 (ANFIS) can optimize the fuzzy encoding further
- Signal model accuracy < 55% → investigate further before proceeding
