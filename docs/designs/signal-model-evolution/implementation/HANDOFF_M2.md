# M2: Training Pipeline Upgrades — Handoff

## Key Architectural Finding

The M2 design doc targeted `MLPTradingModel.train()` (mlp.py lines 165-219) for mini-batch SGD, early stopping, LR scheduling, and gradient clipping. Investigation revealed that **`ModelTrainer` (model_trainer.py) already has all these features** and is the actual production training path. `MLPTradingModel.train()` was dead code — never called outside tests.

**Production training flow:**
```
TrainingPipeline.create_model() → MLPTradingModel.build_model() → nn.Sequential
TrainingPipeline.train_model()  → ModelTrainer.train(nn_sequential, X, y)
```

`MLPTradingModel` = topology definition (build_model + prepare_features)
`ModelTrainer` = training orchestration (DataLoader, early stopping, LR scheduling, gradient clipping, checkpoints, resume, progress)

Both were created in the same commit (`c207bece`, June 2025). `ModelTrainer` grew production features over time while `MLPTradingModel.train()` remained a prototype.

## What Was Done

### Dead Code Removal
- Deleted `MLPTradingModel.train()`, `_build_criterion()`, `_evaluate()` — unused in production
- Deleted `BaseNeuralModel.train()` — placeholder that returned `{"status": "training_not_implemented"}`
- Deleted `tests/unit/neural/test_mlp_training_pipeline.py` — tested dead code
- Reduced `tests/unit/neural/test_mlp_regression.py` to build_model-only tests (removed training tests)
- Cleaned up imports in mlp.py (removed copy, Union, DataLoader, TensorDataset, WeightedRandomSampler)

### Focal Loss (the one real gap)
- Created `ktrdr/neural/losses.py` — `FocalLoss(nn.Module)` with configurable `gamma` and optional `alpha`
- Integrated into `ModelTrainer` loss selection: `loss: "focal"` + `focal_gamma: 2.0` in training config
- `gamma=0` reduces exactly to CrossEntropyLoss (verified by test)

### Orchestrator Wiring Bug (found during E2E)
- Both `local_orchestrator.py` and `training-host-service/orchestrator.py` only injected `loss`, `output_format` into `training_config` for regression models
- Classification models never received `loss: "focal"` — it was silently dropped, falling through to CrossEntropyLoss
- **Fix:** Now passes `output_format`, `loss`, and `focal_gamma` for all model types

### ModelTrainer Already Had (no changes needed)
- Mini-batch SGD via DataLoader ✓
- Early stopping with patience ✓
- ReduceLROnPlateau LR scheduling ✓
- Gradient clipping via clip_grad_norm_ ✓
- Progress callbacks, cancellation, checkpointing ✓

## Config Parameters

Focal loss config (in strategy YAML `training` section):
| Parameter | Default | Description |
|-----------|---------|-------------|
| `loss` | "cross_entropy" (cls) / "huber" (reg) | Loss function ("cross_entropy", "focal", "huber", "mse") |
| `focal_gamma` | 2.0 | Focal loss focusing parameter (0 = CE equivalent) |

## Files Modified
- `ktrdr/neural/models/mlp.py` — Removed dead train/criterion/evaluate methods
- `ktrdr/neural/models/base_model.py` — Removed dead train() placeholder
- `ktrdr/training/model_trainer.py` — Added focal loss selection (4 lines)
- `ktrdr/api/services/training/local_orchestrator.py` — Fixed loss config wiring for all output formats
- `training-host-service/orchestrator.py` — Same fix for host training path

## Files Added
- `ktrdr/neural/losses.py` — FocalLoss implementation
- `tests/unit/training/test_model_trainer_focal_loss.py` — 9 tests (5 FocalLoss unit + 4 ModelTrainer integration)
- `.claude/skills/ke2e/tests/training/focal-loss-classification.md` — E2E test recipe

## Files Deleted
- `tests/unit/neural/test_mlp_training_pipeline.py` — Tested dead code

## Test Results
- 5961 unit tests pass (was 5985 — removed 24 dead tests)
- 0 failures
- Lint clean, mypy clean
- E2E: Focal loss classification training PASSED (op_training_20260321_010102, 50 epochs, 0.91s)

## Gotchas
- `is_trained` field on BaseNeuralModel is still needed — `predict()` checks it, `load_model()` sets it
- `MLPTradingModel` is still needed in production — `build_model()` and `prepare_features()` are used by TrainingPipeline, ModelBundle, DecisionEngine, and ModelLoader
- `ModelTrainer` is topology-agnostic — takes `nn.Module`, works with any architecture. If new topologies are added (LSTM, Transformer), only the model builder needs to change, not the trainer
- No metadata field records which loss function was used — training logs are the only evidence. Consider adding `loss_function` to metadata in future work.
