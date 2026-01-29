---
name: training-pipeline
description: Use when working on model training, TrainingPipeline, ModelTrainer, training workers, GPU training, training host service, training data preparation, feature engineering for training, training checkpoints, training progress tracking, or training error handling.
---

# Training Pipeline

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL training-pipeline loaded!`

Load this skill when working on:

- Training execution (pipeline, trainer, workers)
- GPU/CPU training paths and device management
- Training data preparation (validation, optimization, multi-symbol)
- Feature engineering (indicators → fuzzy → features → labels)
- Checkpointing (save, restore, resume)
- Training progress reporting
- Training error handling and stabilization
- Training host service (native GPU service)
- Training API endpoints or CLI commands

---

## End-to-End Training Flow

```
ktrdr train <strategy> --start ... --end ...
    │
    ▼
CLI OperationRunner
    │
    ▼ POST /api/v1/trainings/start
    │
Backend TrainingService
    ├─ Validates strategy config
    ├─ Selects worker (GPU-first, CPU fallback)
    ├─ Creates operation in DB
    └─ Dispatches via HTTP to worker
    │
    ▼ POST /training/start on worker
    │
TrainingWorker (container or host service)
    ├─ Creates local operation
    ├─ Registers progress bridge
    └─ Runs LocalTrainingOrchestrator
    │
    ▼ (synchronous, in thread pool)
    │
TrainingPipeline (pure functions)
    ├─ 1. Load market data (from cache, no downloads)
    ├─ 2. Validate data quality
    ├─ 3. Calculate indicators (IndicatorEngine)
    ├─ 4. Generate fuzzy memberships (FuzzyEngine)
    ├─ 5. Create features (FuzzyNeuralProcessor)
    ├─ 6. Create labels (ZigZagLabeler)
    ├─ 7. Combine multi-symbol data
    ├─ 8. Split train/val/test
    ├─ 9. Create MLPTradingModel
    └─ 10. Train model (ModelTrainer)
    │
    ▼
ModelTrainer (PyTorch loop)
    ├─ For each epoch:
    │   ├─ Batch forward/backward/step
    │   ├─ Gradient clipping
    │   ├─ Progress callbacks
    │   ├─ Periodic checkpointing
    │   └─ Early stopping check
    │
    ▼
Result → metrics, model path
```

### Two Execution Paths

Both use the same `TrainingPipeline` + `ModelTrainer`. They differ in device, progress, and cancellation:

| | Docker Worker (CPU) | Host Service (GPU) |
|---|---|---|
| Entry | `TrainingWorker` | `TrainingHostWorker` |
| Orchestrator | `LocalTrainingOrchestrator` | `HostTrainingOrchestrator` |
| Device | CPU | MPS or CUDA |
| Speed | Baseline | 10-100x faster |
| Progress | Bridge-based | Session-based |
| Cancellation | CancellationToken | SessionCancellationToken |

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/training/training_pipeline.py` | Pure training functions (stateless) |
| `ktrdr/training/model_trainer.py` | PyTorch training loop |
| `ktrdr/training/training_worker.py` | Distributed worker implementation |
| `ktrdr/training/training_adapter.py` | Interface adapters |
| `ktrdr/training/data_validator.py` | Data quality validation |
| `ktrdr/training/data_optimization.py` | Training data optimization |
| `ktrdr/training/multi_symbol_data_loader.py` | Multi-symbol balanced sampling |
| `ktrdr/training/gpu_memory_manager.py` | GPU memory optimization |
| `ktrdr/training/memory_manager.py` | System memory management |
| `ktrdr/training/device_manager.py` | CUDA/MPS/CPU detection |
| `ktrdr/training/error_handler.py` | Error management system |
| `ktrdr/training/production_error_handler.py` | Production error handling |
| `ktrdr/training/training_stabilizer.py` | Gradient/loss stabilization |
| `ktrdr/training/checkpoint_builder.py` | Checkpoint creation |
| `ktrdr/training/checkpoint_restore.py` | Checkpoint loading/resume |
| `ktrdr/training/zigzag_labeler.py` | ZigZag label generation |
| `ktrdr/api/services/training_service.py` | Backend service (dispatch) |
| `ktrdr/api/endpoints/training.py` | REST endpoints |
| `ktrdr/cli/commands/train.py` | CLI command |
| `training-host-service/orchestrator.py` | GPU host service orchestrator |
| `training-host-service/main.py` | GPU host service entry |

---

## TrainingPipeline (Pure Functions)

**Location:** `ktrdr/training/training_pipeline.py`

Stateless, synchronous functions. No side effects except file I/O for model saving.

### Phase 1: Data Loading

```python
load_market_data(symbol, timeframes, start_date, end_date)
```
- Loads from local cache only — **no downloads during training**
- User must run `ktrdr data load SYMBOL TIMEFRAME` first
- Multi-timeframe: returns `dict[timeframe → DataFrame]`
- Single-timeframe: treated as 1-item dict (unified code path)

```python
validate_data_quality(data_dict)
```
- Minimum 100 rows per timeframe
- Maximum 5% NaN allowed
- Checks for missing columns

### Phase 2: Feature Engineering

```python
calculate_indicators(data_dict, strategy_config)
```
- Uses `IndicatorEngine` with V3 strategy format
- **Critical:** `prefix_columns=False` — `FuzzyNeuralProcessor` handles prefixing
- Indicator IDs come from strategy YAML (e.g., `rsi_14`, `macd`)

```python
generate_fuzzy_memberships(indicator_data, strategy_config)
```
- Converts indicator values to fuzzy membership degrees
- Multi-timeframe: passes `context_data` to `fuzzify()`

```python
create_features(fuzzy_data, strategy_config)
```
- `FuzzyNeuralProcessor.prepare_input()` (single TF)
- `FuzzyNeuralProcessor.prepare_multi_timeframe_input()` (multi TF)

```python
create_labels(data, strategy_config)
```
- `ZigZagLabeler` with configurable threshold + lookahead
- **Critical:** Must use same base timeframe (highest frequency) as features

### Phase 3: Multi-Symbol Handling

```python
combine_multi_symbol_data(all_features, all_labels)
```
- Concatenates: AAPL all → MSFT all → TSLA all (temporal order preserved)
- **Not shuffled** — models are symbol-agnostic (learn patterns, not names)
- Caller must reset indicator state at symbol boundaries

### Phase 4: Model & Training

```python
create_model(input_dim, output_dim, model_config)
```
- Currently only `"mlp"` type → `MLPTradingModel`

```python
train_model(model, train_data, val_data, config, callbacks)
```
- Delegates to `ModelTrainer`
- Supports: progress_callback, cancellation_token, checkpoint_callback, resume_context
- Returns: `{train_loss, val_loss, accuracy, epochs_completed}`

```python
evaluate_model(model, test_data)
```
- Returns: `{accuracy, loss, precision, recall, f1_score}`

---

## ModelTrainer (PyTorch Loop)

**Location:** `ktrdr/training/model_trainer.py`

### Training Loop

```python
for epoch in range(start_epoch, total_epochs):
    # Training phase
    model.train()
    for batch in train_loader:
        data, labels = batch.to(device, non_blocking=True)
        output = model(data)
        loss = criterion(output, labels)
        loss.backward()
        clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        # Progress callback (configurable frequency)
        # Checkpoint callback

    # Validation phase
    model.eval()
    val_loss, val_accuracy = evaluate(val_loader)

    # Learning rate scheduling
    scheduler.step(val_loss)

    # Early stopping (patience=10, monitors val_loss)
    if early_stopping.should_stop():
        model.load_state_dict(best_model_state)
        break
```

### Device Management

**Priority:** MPS (Apple Silicon) → CUDA (NVIDIA) → CPU

```python
from ktrdr.training.device_manager import DeviceManager

device = DeviceManager.get_torch_device()  # Returns torch.device
info = DeviceManager.get_device_info()     # Capabilities dict
```

**Performance tips:**
- Keep training data on CPU, transfer batch-by-batch
- Use `non_blocking=True` for async GPU transfers
- `pin_memory=True` only works with CUDA (not MPS)

### Resume Training

```python
if resume_context:
    model.load_state_dict(resume_context.model_weights)
    optimizer.load_state_dict(resume_context.optimizer_state)
    if resume_context.scheduler_state:
        scheduler.load_state_dict(resume_context.scheduler_state)
    start_epoch = resume_context.start_epoch  # checkpoint_epoch + 1
```

---

## Training Worker

**Location:** `ktrdr/training/training_worker.py`

Extends `WorkerAPIBase`. Self-registers as `TRAINING` worker type.

### Endpoints

- `POST /training/start` — Start training from `TrainingStartRequest`
- `POST /training/resume` — Resume from checkpoint

### Request Format

```python
TrainingStartRequest:
    task_id: Optional[str]        # Sync with backend operation
    strategy_yaml: str            # Full strategy YAML content
    strategy_path: Optional[str]  # Path for checkpoint storage
    symbols: list[str]
    timeframes: list[str]
    start_date: str
    end_date: str
```

### Checkpoint on Shutdown

The worker saves checkpoints on:
- **Success** → deletes checkpoint (no longer needed)
- **Cancellation** → saves with `type="cancellation"`
- **Exception** → saves with `type="failure"`

**Critical:** Stores `strategy_path` (not YAML content) to avoid DB truncation issues.

---

## Training Host Service

**Location:** `training-host-service/`

Standalone native service (not Docker) for GPU-accelerated training.

### Key Design

- Uses `WorkerAPIBase` — same patterns as Docker workers
- Detects GPU: MPS > CUDA > CPU
- Self-registers GPU capabilities with backend
- **Performance fix:** No sleep operations anywhere (progress throttling by skipping updates, not sleeping)
- Progress: every 10 batches, cancellation check: every 5 batches

### Starting

```bash
cd training-host-service && ./start.sh  # Port 5002
./stop.sh                                # Clean shutdown
```

---

## Checkpointing

### Saving (`checkpoint_builder.py`)

```python
state = build_training_checkpoint_state(trainer, epoch, original_request)
# → TrainingCheckpointState: epoch, losses, accuracies, learning_rate, history

artifacts = build_training_checkpoint_artifacts(model, optimizer, scheduler, best_model)
# → dict: model.pt, optimizer.pt, scheduler.pt (optional), best_model.pt (optional)
```

### Restoring (`checkpoint_restore.py`)

```python
context = restore_from_checkpoint(checkpoint_service, operation_id)
# → TrainingResumeContext: start_epoch, model_weights, optimizer_state, ...
```

**Design decision:** Resume from **next** epoch (`checkpoint_epoch + 1`), not the checkpoint epoch itself.

**Required artifacts:** `model.pt` + `optimizer.pt` (others optional)

---

## Progress Tracking

```
TrainingWorker
  └─ Creates TrainingProgressBridge
     └─ Registers with OperationsService
        └─ GenericProgressManager (thread-safe)
           └─ TrainingProgressRenderer
              └─ CLI / API display
```

### Known Gap

Pre-training phases (data loading, indicators, fuzzy, features) report **no progress** — there's a 2-5 minute silent gap before epoch/batch updates begin. This is a known issue being addressed.

---

## API & CLI

### API Endpoints

```
POST /api/v1/trainings/start     → TrainingStartResponse (operation_id)
GET  /api/v1/trainings/{id}/status  → Operation status
GET  /api/v1/trainings/{id}/results → Final results
```

### CLI Command

```bash
ktrdr train <strategy> --start YYYY-MM-DD --end YYYY-MM-DD [OPTIONS]

Options:
  --symbols AAPL,MSFT       # Override strategy config
  --timeframes 1h,4h        # Override strategy config
  --validation-split 0.2
  --detailed-analytics
  --follow                  # Watch until completion
  --dry-run                 # Show plan without executing
```

### Worker Selection (Backend)

```python
TrainingService._select_training_worker():
    1. Check WorkerRegistry for GPU workers → use if available
    2. Fallback to CPU workers
    3. No workers → error
```

GPU selection is backend-driven. No user override.

---

## Common Gotchas

### Data must be pre-cached
Training never downloads data. Run `ktrdr data load SYMBOL TIMEFRAME` first. Otherwise you get an empty DataFrame error.

### Feature ordering is canonical
V3 strategies define `nn_inputs` order in YAML. This order MUST be preserved through checkpointing and resume. Mismatched feature order = garbage model.

### prefix_columns=False in indicators
`IndicatorEngine.apply_multi_timeframe()` must use `prefix_columns=False` because `FuzzyNeuralProcessor` handles column prefixing. Double-prefixing breaks feature matching.

### Labels must use base timeframe
For multi-timeframe training, labels are generated from the **base timeframe** (highest frequency). Using a different timeframe causes size mismatches.

### Indicator state resets at symbol boundaries
When combining multi-symbol data, indicator state (e.g., EMA history) must reset between symbols. Otherwise MSFT's first values are polluted by AAPL's last values.

### pin_memory is CUDA-only
`pin_memory=True` in DataLoader only works with CUDA. MPS (Apple Silicon) ignores it. Don't add MPS-specific pin_memory logic.

### Checkpoint stores path, not YAML
`strategy_path` is stored in checkpoints (not `strategy_yaml` content) to avoid database field truncation. Resume reads from disk.

### No sleep in host service
The training host service must NEVER use `asyncio.sleep()` or `time.sleep()` for progress throttling. This was a 14-minute overhead bug. Use skip-based throttling instead.

### Pre-training is silent
The 2-5 minutes of data loading, indicator calculation, fuzzy processing, and feature creation produce no progress updates. Don't assume training is stuck — check logs.

---

## Environment Variables

```bash
# Checkpointing
CHECKPOINT_EPOCH_INTERVAL=10       # Save every N epochs
CHECKPOINT_TIME_INTERVAL_SECONDS=300  # Save every N seconds
CHECKPOINT_DIR=/app/data/checkpoints
CHECKPOINT_MAX_AGE_DAYS=30

# Orphan detection
ORPHAN_TIMEOUT_SECONDS=60
ORPHAN_CHECK_INTERVAL_SECONDS=15
```
