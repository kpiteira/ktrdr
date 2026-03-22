# Temporal Signal Models: LSTM/GRU Architecture

## Problem Statement

KTRDR's signal models use MLPs that see each bar as an independent point — "RSI = 30" with no knowledge of whether RSI is falling or rising. Signal model evolution (M1-M5) proved the training pipeline, labeling, and fuzzy encoding all work correctly, but MLP models produce uniform ~33/33/34% predictions. They genuinely cannot distinguish outcomes from point-in-time indicator values.

Hypothesis H_003 (filed Dec 2025, untested): LSTM/GRU architectures can learn temporal patterns like "RSI rising from oversold" vs "RSI falling into oversold" that MLPs cannot see. This is the simplest untested hypothesis with the highest expected information value.

## Goals

1. Add LSTM and GRU model architectures alongside the existing MLP
2. Sequence creation via sliding window over existing 2D feature matrices — no changes to feature engineering
3. Both architectures coexist, selected by `model.architecture.type` in strategy YAML
4. End-to-end: train → save → load → backtest works identically for both model types
5. Direct comparison: same features, same labels, same splits — MLP vs LSTM

## Non-Goals

- Changing fuzzy encoding or indicator computation
- New labeling approaches
- Autoresearch or evolution infrastructure
- Attention mechanisms or transformers (future, if LSTM shows signal)
- Bidirectional LSTM (future — requires future data, complicates inference)

## Design Decisions

### D1: Sequence Creation at DataLoader Level (Not in Feature Engineering)

**Decision:** Keep FuzzyNeuralProcessor producing 2D (timestamps, features) tensors. A new `SequenceDataset` creates sliding windows of (sequence_length, features) at batching time.

**Why:** Clean separation. Feature engineering doesn't change. The same feature matrix serves both MLP (row-by-row) and LSTM (windowed). No risk of breaking the MLP path.

**Trade-off:** Labels must be aligned — each sequence's label is the label of its final timestamp. First `sequence_length - 1` timestamps have no complete sequence and are dropped from training. Accepted: with sequence_length=20 on years of data, this is negligible.

### D2: Stateless Inference (Rolling Window, No Hidden State)

**Decision:** At inference time, the model receives a full window of (seq_len, features) for each prediction. No LSTM hidden state is carried between bars.

**Why:** Stateful inference (carrying h_t between bars) is fragile — state depends on seeing every bar in order, breaks on gaps, complicates backtesting. Stateless inference is simpler and more robust. The sequence window provides sufficient temporal context.

**Trade-off:** Slightly less computationally efficient (reprocesses overlapping bars). For backtesting on hourly data this is negligible. For live trading at sub-second frequencies, would reconsider.

### D3: Model Config via Strategy YAML

**Decision:** Model type and architecture parameters live in the strategy YAML under `model.architecture`:

```yaml
model:
  type: lstm  # or gru, mlp
  architecture:
    hidden_size: 64
    num_layers: 2
    dropout: 0.2
    sequence_length: 20
    # MLP-specific keys (hidden_layers) ignored for LSTM
    # LSTM-specific keys (hidden_size, num_layers, sequence_length) ignored for MLP
```

**Why:** The model config is already `dict[str, Any]` — no schema changes needed. `create_model()` dispatches on `model.type`. Each model class reads only its relevant keys.

### D4: Sequence Length Stored in Model Metadata

**Decision:** `sequence_length` is saved in ModelMetadata alongside resolved_features. At backtest time, ModelBundle reads it to know how many historical bars to fetch per prediction.

**Why:** The backtest pipeline must know the lookback window to provide correct input shape. Storing it in metadata ensures the training and inference windows match exactly.

### D5: Disable Lag Features for Sequence Models

**Decision:** When `model.type` is lstm/gru, the FuzzyNeuralProcessor's temporal lag feature extraction is disabled. The LSTM learns temporal patterns from the sequence itself — flattened lag features would be redundant and wasteful.

**Why:** Lag features exist specifically because MLP can't see sequences. LSTM makes them unnecessary. Including both would double the feature count without benefit.

## Key Scenarios

### Training
1. Features computed as 2D matrix (timestamps, features) — unchanged
2. Labels computed as 1D vector (timestamps,) — unchanged
3. SequenceDataset wraps both: for index i, returns (features[i-seq_len+1:i+1], labels[i])
4. DataLoader batches into (batch, seq_len, features) + (batch,) labels
5. LSTM forward: input (batch, seq_len, features) → hidden states → final hidden → Linear → (batch, num_classes)
6. Loss, backprop, optimizer — unchanged

### Backtest Inference
1. FeatureCache computes all features as DataFrame — unchanged
2. For each bar: `get_feature_window(timestamp, sequence_length)` returns DataFrame of last N rows
3. DecisionFunction detects sequence model, builds (1, seq_len, features) tensor
4. Model forward pass → (1, num_classes) → signal extraction — unchanged from here

### Model Save/Load
1. Training saves: model.pt (state_dict), metadata_v3.json (includes sequence_length, model_type)
2. ModelBundle.load() reads model_type from metadata, dispatches to correct architecture builder
3. Weights loaded into correct architecture → eval mode → ready for inference

## Milestone Structure

### M1: LSTM/GRU Model + Training (3 tasks)
- Task 1.1: LSTMTradingModel + GRUTradingModel classes
- Task 1.2: SequenceDataset + ModelTrainer integration
- Task 1.3: create_model() dispatch + metadata storage

### M2: Backtest Integration (3 tasks)
- Task 2.1: FeatureCache.get_feature_window() method
- Task 2.2: DecisionFunction sequence-aware inference
- Task 2.3: ModelBundle.load() for LSTM/GRU models

### M3: Comparison Experiment (2 tasks)
- Task 3.1: LSTM strategy YAML template + training
- Task 3.2: MLP vs LSTM backtest comparison on identical data

## Success Criteria

- LSTM/GRU models train end-to-end through existing pipeline
- Backtest produces trades with LSTM models
- Direct comparison: if LSTM shows >5pp improvement in backtest metrics over MLP → temporal signal exists
- If similar performance → features genuinely uninformative regardless of architecture
