---
design: docs/designs/signal-model-evolution/DESIGN.md
---

# M2: Training Pipeline Upgrades

**Phase:** 1 — Fix the Training Pipeline (Layer 3)
**Dependencies:** None (can run in parallel with M1 and M4)
**Branch:** `impl/sme-M2-training-pipeline`

**JTBD:** *When I train a neural network, I want mini-batch SGD with early stopping, LR scheduling, gradient clipping, and focal loss, so that models generalize instead of collapsing to predict the mean.*

---

## Task 2.1: Mini-Batch Training

**File(s):** `ktrdr/neural/models/mlp.py`
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Replace the full-batch training loop in `MLPTradingModel.train()` (lines 165-219) with mini-batch SGD using PyTorch's `DataLoader`. The current loop passes ALL data through the model every epoch — this provides no stochastic noise for generalization and is known to overfit to the training mean.

**Implementation Notes:**
- The `batch_size` parameter is already read from config at line 123 but never used (`training_config.get("batch_size", 32)`)
- Create a `TensorDataset(X, y)` and `DataLoader(dataset, batch_size=batch_size, shuffle=True)`
- If sample weights are provided (from M1 uniqueness weighting), use `WeightedRandomSampler` instead of `shuffle=True`
- The inner training loop changes from:
  ```python
  # Current: full-batch
  outputs = self.model(X)
  loss = criterion(outputs, y)
  ```
  to:
  ```python
  # New: mini-batch
  for batch_X, batch_y in dataloader:
      outputs = self.model(batch_X)
      loss = criterion(outputs, batch_y)
  ```
- Track epoch-level metrics by averaging over batches
- Validation stays full-batch (standard practice — val set is typically smaller)
- Default batch_size=256 (config override remains)
- Add `sample_weights: Optional[torch.Tensor] = None` parameter to `train()`

**Testing Requirements:**
- [ ] Test mini-batch training produces different results than full-batch (stochastic noise)
- [ ] Test batch_size config parameter is respected
- [ ] Test with batch_size > dataset size (should degrade to full-batch gracefully)
- [ ] Test with sample_weights parameter (WeightedRandomSampler used)
- [ ] Test training history still has per-epoch metrics
- [ ] Test validation metrics are still computed correctly (full-batch)
- [ ] Test backward compatibility: existing training configs without batch_size still work (default 256)

**Acceptance Criteria:**
- [ ] Training uses mini-batch DataLoader instead of full-batch
- [ ] Optional sample_weights parameter for uniqueness weighting
- [ ] All existing tests pass without changes
- [ ] Batch size configurable via training config

---

## Task 2.2: Early Stopping

**File(s):** `ktrdr/neural/models/mlp.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add early stopping to the training loop: monitor validation loss and stop when it hasn't improved for `patience` epochs. Save and restore the best model weights. Currently the model trains for exactly N epochs regardless of convergence or overfitting.

**Implementation Notes:**
- Add config parameters: `early_stopping: true`, `patience: 10`, `min_delta: 0.0001`
- Track `best_val_loss` and `epochs_without_improvement`
- Deep-copy model state dict when new best is found: `best_state = copy.deepcopy(self.model.state_dict())`
- After training completes (either patience exhausted or max epochs), restore best state: `self.model.load_state_dict(best_state)`
- If no validation_data provided, early stopping is disabled (with a log warning)
- Add `best_epoch` to training history dict
- Early stopping should only trigger after a minimum warmup period (e.g., `min_epochs: 10`)

**Testing Requirements:**
- [ ] Test early stopping fires: create a scenario where val loss rises after initial drop
- [ ] Test best model is restored (not the final overfit model)
- [ ] Test `patience` parameter: stopping occurs after exactly N epochs without improvement
- [ ] Test `min_delta`: small improvements below delta don't reset patience counter
- [ ] Test `min_epochs`: no early stopping before warmup period
- [ ] Test disabled when no validation data (trains full epochs)
- [ ] Test `best_epoch` appears in history
- [ ] Test backward compat: `early_stopping: false` (or absent) trains full epochs as before

**Acceptance Criteria:**
- [ ] Training stops early when validation loss plateaus
- [ ] Best model weights are restored after early stopping
- [ ] Configurable patience and min_delta via training config
- [ ] No behavioral change when early_stopping is disabled

---

## Task 2.3: Learning Rate Scheduling + Gradient Clipping

**File(s):** `ktrdr/neural/models/mlp.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Add learning rate scheduling (ReduceLROnPlateau) and gradient clipping to the training loop. Fixed LR throughout training is suboptimal — the LR should decrease as the model converges. Gradient clipping prevents exploding gradients on outlier samples.

**Implementation Notes:**
- LR Scheduling: `torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)`
  - Step the scheduler after each epoch with val_loss (or train_loss if no val data)
  - Config: `lr_scheduler: true`, `lr_factor: 0.5`, `lr_patience: 5`, `lr_min: 1e-6`
- Gradient Clipping: `torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)`
  - Apply after `loss.backward()`, before `optimizer.step()`
  - Config: `gradient_clip: 1.0` (or `null` to disable)
- Log LR changes: when scheduler reduces LR, log the new value
- Add current LR to training history for monitoring

**Testing Requirements:**
- [ ] Test LR reduces after plateau (create scenario with stable loss)
- [ ] Test LR doesn't go below lr_min
- [ ] Test gradient clipping: create scenario with large gradients (large outlier in data)
- [ ] Test gradient clip norm is configurable
- [ ] Test LR history appears in training output
- [ ] Test backward compat: both features disabled by default if not in config

**Acceptance Criteria:**
- [ ] LR reduces when loss plateaus (ReduceLROnPlateau)
- [ ] Gradients clipped to configurable max_norm
- [ ] Both features are opt-in via training config

---

## Task 2.4: Focal Loss for Class Imbalance

**File(s):** `ktrdr/neural/losses.py` (new), `ktrdr/neural/models/mlp.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement Focal Loss for handling class imbalance in TB labels. Standard CrossEntropyLoss weights all samples equally — Focal Loss down-weights easy (well-classified) examples and focuses training on hard examples.

**Implementation Notes:**
- Create `ktrdr/neural/losses.py` with `FocalLoss(nn.Module)`:
  ```python
  class FocalLoss(nn.Module):
      def __init__(self, gamma: float = 2.0, alpha: Optional[torch.Tensor] = None):
          """
          gamma: focusing parameter (0 = CE, 2 = standard focal)
          alpha: per-class weight tensor (optional)
          """
  ```
- Formula: `FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)`
  - `p_t` = model's estimated probability for the true class
  - When `gamma=0`, this reduces to standard cross-entropy
- In `mlp.py`, add loss selection:
  ```python
  loss_name = self.config.get("loss", "cross_entropy")
  if loss_name == "focal":
      gamma = self.config.get("focal_gamma", 2.0)
      criterion = FocalLoss(gamma=gamma)
  elif loss_name == "cross_entropy":
      criterion = nn.CrossEntropyLoss()
  ```
- Also support class weights: `nn.CrossEntropyLoss(weight=class_weights_tensor)` as a simpler alternative

**Testing Requirements:**
- [ ] Test FocalLoss matches CrossEntropyLoss when gamma=0
- [ ] Test FocalLoss reduces loss contribution from easy examples (high p_t)
- [ ] Test FocalLoss increases loss contribution from hard examples (low p_t)
- [ ] Test with per-class alpha weights
- [ ] Test integration: `loss: "focal"` in config selects FocalLoss
- [ ] Test backward compat: default `loss: "cross_entropy"` unchanged
- [ ] Test with imbalanced 3-class data: focal loss should produce more balanced predictions

**Acceptance Criteria:**
- [ ] FocalLoss implemented as configurable nn.Module
- [ ] Selectable via `loss` parameter in training config
- [ ] Gamma and alpha configurable
- [ ] CrossEntropyLoss remains default

---

## Task 2.5: Validation — Training Pipeline Quality

**File(s):** N/A (validation task)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that all training pipeline improvements work together correctly: mini-batch + early stopping + LR scheduling + gradient clipping + focal loss. Train a real model and verify convergence behavior.

**Validation Steps:**
1. Load the `ke2e` skill before designing validation
2. Use `ke2e-test-scout` to find existing tests covering training pipeline convergence or early stopping
3. If no match found, hand off to `ke2e-test-designer` to design a new test that:
   a. Starts the sandbox (`uv run kinfra sandbox up`)
   b. Trains a classification model via CLI with all improvements enabled (strategy YAML with: `batch_size: 256`, `early_stopping: true`, `patience: 10`, `lr_scheduler: true`, `gradient_clip: 1.0`, `loss: focal`)
   c. Inspects training output/logs for: early stopping triggered before max_epochs, LR reduction observed, no NaN losses, final model accuracy
   d. Trains a second model with improvements disabled for comparison
4. Execute the test via `ke2e-test-runner` against the real sandbox

**What "real E2E" means here:** Real training run through the CLI, producing a real saved model. The test inspects training logs and model metadata to verify convergence behavior — not mock training loops.

**Success Criteria (from Design Section 11):**
- [ ] Training converges with early stopping (does not run all epochs)
- [ ] Mini-batch training shows train/val gap < 10% (generalization, not overfitting)
- [ ] LR scheduling activates (at least one reduction observed in training log)
- [ ] No NaN or infinite loss values during training
