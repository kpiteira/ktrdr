# M1: LSTM/GRU Models + Training

## Goal
Train LSTM and GRU models end-to-end through the existing training pipeline, producing saved models with correct metadata.

## Tasks

### Task 1.1: LSTMTradingModel + GRUTradingModel Classes

**What:** Create `ktrdr/neural/models/lstm.py` and `ktrdr/neural/models/gru.py` with model classes that follow BaseNeuralModel interface.

**Key implementation:**
- `LSTMNetwork(nn.Module)` with `nn.LSTM` → dropout → `nn.Linear`
- `LSTMTradingModel(BaseNeuralModel)` with `build_model()` and `prepare_features()`
- Same pattern for GRU
- Config reads: `hidden_size`, `num_layers`, `dropout`, `sequence_length`
- Output shape: (batch, num_classes) — same as MLP

**Tests (RED first):**
- `tests/unit/neural/test_lstm_model.py`
  - Model builds with correct architecture from config
  - Forward pass: (batch, seq_len, features) → (batch, num_classes)
  - Handles classification (3 classes) and regression (1 output)
  - Config validation: raises on missing sequence_length
- `tests/unit/neural/test_gru_model.py` — same tests for GRU

**Files:** `ktrdr/neural/models/lstm.py` (new), `ktrdr/neural/models/gru.py` (new)

### Task 1.2: SequenceDataset

**What:** Create `ktrdr/training/sequence_dataset.py` — a PyTorch Dataset that creates sliding windows from 2D feature matrices.

**Key implementation:**
- `SequenceDataset(features_2d, labels, sequence_length)`
- `__len__`: `T - sequence_length + 1`
- `__getitem__(idx)`: returns `(features[idx:idx+seq_len], labels[idx+seq_len-1])`
- Handles edge case: raises ValueError if T < sequence_length

**Tests (RED first):**
- `tests/unit/training/test_sequence_dataset.py`
  - Correct length for various T and seq_len values
  - Each item has correct shapes: (seq_len, F) and scalar
  - Label alignment: item[i] label matches features[-1] timestamp
  - Raises on insufficient data (T < seq_len)
  - Works with DataLoader for batching: (batch, seq_len, F)

**Files:** `ktrdr/training/sequence_dataset.py` (new)

### Task 1.3: ModelTrainer Integration

**What:** Modify `ModelTrainer.train()` to use SequenceDataset when model_type is lstm/gru.

**Key implementation:**
- Detect model_type from config
- For lstm/gru: wrap features+labels in SequenceDataset instead of TensorDataset
- Sequence length from `config["architecture"]["sequence_length"]`
- Rest of training loop (loss, backprop, optimizer, early stopping, LR scheduler) unchanged
- Purged train/val split must account for sequence overlap: purge window = sequence_length bars

**Tests (RED first):**
- `tests/unit/training/test_model_trainer_lstm.py`
  - LSTM model trains for 1 epoch without error
  - Correct dataset type selected based on config
  - Val split handles sequence boundary correctly
  - Training metrics (loss, accuracy) are recorded
  - Early stopping works with sequence dataset

**Files:** `ktrdr/training/model_trainer.py` (modified)

### Task 1.4: create_model() Dispatch + Metadata

**What:** Update TrainingPipeline.create_model() to handle lstm/gru types. Update ModelMetadata to store model_type and sequence_length.

**Key implementation:**
- Add elif branches in create_model() for "lstm" and "gru"
- Add `model_type: str = "mlp"` and `sequence_length: int | None = None` to ModelMetadata
- Training pipeline saves these fields during model persistence
- Disable temporal lag features when model_type is lstm/gru (in FuzzyNeuralProcessor)

**Tests (RED first):**
- `tests/unit/training/test_create_model_dispatch.py`
  - create_model(type="lstm") returns LSTM architecture
  - create_model(type="gru") returns GRU architecture
  - create_model(type="mlp") still works (regression test)
  - Unknown type raises ValueError
- `tests/unit/models/test_metadata_temporal.py`
  - ModelMetadata serializes/deserializes model_type and sequence_length
  - Default model_type is "mlp" (backward compat)

**Files:** `ktrdr/training/training_pipeline.py` (modified), `ktrdr/models/model_metadata.py` (modified)

## E2E Validation
- Train an LSTM model via CLI: `uv run ktrdr models train trend_tb_lstm_signal_v1.yaml EURUSD 1h --start-date 2024-01-01 --end-date 2024-06-30 --follow`
- Verify model saved with correct metadata (model_type=lstm, sequence_length=20)
- Verify training metrics are reasonable (loss decreasing, not NaN)

## Completion Checklist
- [ ] LSTMNetwork and GRUNetwork produce correct output shapes
- [ ] SequenceDataset creates proper sliding windows
- [ ] ModelTrainer trains LSTM/GRU without error
- [ ] create_model() dispatches correctly
- [ ] ModelMetadata stores model_type and sequence_length
- [ ] All unit tests pass
- [ ] `make quality` passes
