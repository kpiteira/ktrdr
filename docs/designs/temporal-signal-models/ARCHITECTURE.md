# Temporal Signal Models: Architecture

## Component Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                    Strategy YAML                                  │
│  model:                                                           │
│    type: lstm          ← dispatches model creation                │
│    architecture:                                                  │
│      sequence_length: 20                                          │
│      hidden_size: 64                                              │
│      num_layers: 2                                                │
└─────────────────────────────┬────────────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────────────┐
│              TrainingPipeline.create_model()                       │
│  Dispatches on model_type: mlp → MLPTradingModel                  │
│                             lstm → LSTMTradingModel                │
│                             gru  → GRUTradingModel                 │
└─────────────────────────────┬────────────────────────────────────┘
                              │
            ┌─────────────────┴──────────────────┐
            │                                    │
┌───────────▼──────────┐          ┌──────────────▼───────────────┐
│  MLPTradingModel     │          │  LSTMTradingModel            │
│  (unchanged)         │          │  (new)                       │
│                      │          │                              │
│  Input: (B, F)       │          │  Input: (B, S, F)            │
│  Output: (B, C)      │          │  Output: (B, C)              │
│                      │          │                              │
│  nn.Sequential(      │          │  nn.LSTM(F, H, layers)       │
│    Linear→ReLU→Drop  │          │  nn.Linear(H, C)             │
│    ...               │          │                              │
│    Linear→C          │          │  Forward:                    │
│  )                   │          │    lstm(x) → (B,S,H)         │
│                      │          │    take last hidden → (B,H)  │
│                      │          │    linear → (B,C)            │
└──────────────────────┘          └──────────────────────────────┘
```

B = batch, F = features, S = sequence_length, H = hidden_size, C = num_classes

## Data Flow: Training

```
1. FuzzyNeuralProcessor.prepare_input(fuzzy_data)
   │  Returns: (T, F) tensor — T timestamps, F features
   │  UNCHANGED from current behavior
   │
2. Labels: (T,) tensor — one label per timestamp
   │  UNCHANGED
   │
3. IF model_type == "mlp":
   │  TensorDataset(features_2d, labels)         ← existing path
   │  DataLoader → batches of (B, F) + (B,)
   │
   ELIF model_type in ("lstm", "gru"):
   │  SequenceDataset(features_2d, labels, seq_len=20)   ← NEW
   │  For index i: returns (features[i-S+1:i+1], labels[i])
   │  DataLoader → batches of (B, S, F) + (B,)
   │  First S-1 timestamps dropped (incomplete windows)
   │
4. model.forward(batch) → (B, C)
   │
5. loss_fn(logits, targets) → scalar        ← UNCHANGED
   │
6. backward() + optimizer.step()            ← UNCHANGED
```

## Data Flow: Backtest Inference

```
1. FeatureCache.compute_features(data)
   │  Returns: DataFrame (T rows, F columns)  ← UNCHANGED
   │
2. For each timestamp t:
   │
   IF model_type == "mlp":
   │  features = cache.get_features_for_timestamp(t)   ← existing
   │  → dict[str, float]
   │  → tensor (1, F)
   │
   ELIF model_type in ("lstm", "gru"):
   │  window = cache.get_feature_window(t, seq_len)    ← NEW
   │  → DataFrame (S rows, F columns), or None if insufficient history
   │  → tensor (1, S, F)
   │
3. DecisionFunction._predict(features_or_window)
   │  → model(tensor) → (1, C)
   │  → signal extraction                    ← UNCHANGED from here
```

## New Components

### LSTMTradingModel (ktrdr/neural/models/lstm.py)

```python
class LSTMTradingModel(BaseNeuralModel):
    """LSTM-based trading model for sequence input."""

    def build_model(self, input_size: int) -> nn.Module:
        # Reads from self.config["architecture"]:
        #   hidden_size: int (default 64)
        #   num_layers: int (default 2)
        #   dropout: float (default 0.2)
        #   sequence_length: int (required)
        # Returns: LSTMNetwork(input_size, hidden_size, num_layers, num_classes, dropout)

    def prepare_features(self, fuzzy_data, indicators, saved_scaler=None) -> torch.Tensor:
        # Delegates to FuzzyNeuralProcessor (same as MLP)
        # Returns 2D tensor — sequence windowing happens at DataLoader level
```

### LSTMNetwork (nn.Module inside lstm.py)

```python
class LSTMNetwork(nn.Module):
    def __init__(self, input_size, hidden_size, num_layers, num_classes, dropout):
        self.lstm = nn.LSTM(input_size, hidden_size, num_layers,
                           batch_first=True, dropout=dropout if num_layers > 1 else 0)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(hidden_size, num_classes)

    def forward(self, x):
        # x: (batch, seq_len, features)
        lstm_out, (h_n, c_n) = self.lstm(x)
        # Take last hidden state: h_n[-1] → (batch, hidden_size)
        out = self.dropout(h_n[-1])
        out = self.fc(out)
        # out: (batch, num_classes)
        return out
```

### GRUTradingModel (ktrdr/neural/models/gru.py)

Identical pattern to LSTM but uses `nn.GRU` (no cell state). Separate file for clarity.

### SequenceDataset (ktrdr/training/sequence_dataset.py)

```python
class SequenceDataset(Dataset):
    def __init__(self, features: torch.Tensor, labels: torch.Tensor, sequence_length: int):
        # features: (T, F) — full 2D feature matrix
        # labels: (T,) — one per timestamp
        # sequence_length: lookback window
        # Valid indices: [sequence_length-1, T-1]

    def __len__(self):
        return len(self.labels) - self.sequence_length + 1

    def __getitem__(self, idx):
        # Returns: (sequence_length, F) tensor, scalar label
        start = idx
        end = idx + self.sequence_length
        return self.features[start:end], self.labels[end - 1]
```

## Modified Components

### TrainingPipeline.create_model() — add dispatch

```python
if model_type == "mlp":
    # existing path
elif model_type == "lstm":
    from ktrdr.neural.models.lstm import LSTMTradingModel
    model_obj = LSTMTradingModel(model_config_with_classes)
    return model_obj.build_model(input_dim)
elif model_type == "gru":
    from ktrdr.neural.models.gru import GRUTradingModel
    model_obj = GRUTradingModel(model_config_with_classes)
    return model_obj.build_model(input_dim)
```

### ModelTrainer.train() — dataset selection

```python
model_type = self.config.get("type", "mlp")
if model_type in ("lstm", "gru"):
    seq_len = self.config["architecture"]["sequence_length"]
    dataset = SequenceDataset(features, labels, seq_len)
else:
    dataset = TensorDataset(features, labels)
```

### FeatureCache — add get_feature_window()

```python
def get_feature_window(
    self, timestamp: pd.Timestamp, sequence_length: int
) -> pd.DataFrame | None:
    """Get last sequence_length rows of features ending at timestamp."""
    idx = self._cached_features.index.get_loc(timestamp)
    if idx < sequence_length - 1:
        return None  # Insufficient history
    start = idx - sequence_length + 1
    return self._cached_features.iloc[start:idx + 1]
```

### DecisionFunction — sequence-aware predict

```python
def _predict(self, features) -> dict[str, Any]:
    if isinstance(features, pd.DataFrame):
        # Sequence model: features is (seq_len, F) DataFrame
        values = features[self.feature_names].values
        tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)  # (1, S, F)
    else:
        # MLP model: features is dict[str, float]
        values = [features[name] for name in self.feature_names]
        tensor = torch.tensor(values, dtype=torch.float32).unsqueeze(0)  # (1, F)

    with torch.no_grad():
        outputs = self.model(tensor)
    # ... rest unchanged
```

### ModelBundle.load() — model type dispatch

```python
model_type = metadata.model_type  # NEW field, default "mlp"
if model_type == "lstm":
    from ktrdr.neural.models.lstm import LSTMTradingModel
    model_obj = LSTMTradingModel(model_config)
    model = model_obj.build_model(input_size)
elif model_type == "gru":
    from ktrdr.neural.models.gru import GRUTradingModel
    model_obj = GRUTradingModel(model_config)
    model = model_obj.build_model(input_size)
else:
    # existing MLP path
```

### ModelMetadata — new fields

```python
model_type: str = "mlp"          # "mlp", "lstm", "gru"
sequence_length: int | None = None  # Required for lstm/gru
```

## Strategy YAML Example

```yaml
version: "3.0"
name: trend_tb_lstm_signal_v1

training_data:
  symbols: [EURUSD]
  timeframes: [1h]
  date_range:
    start: "2020-01-01"
    end: "2023-12-31"

labeling:
  method: triple_barrier
  params:
    profit_target_atr: 2.0
    stop_loss_atr: 2.0
    max_holding_bars: 20
    vol_lookback: 20

indicators:
  rsi_14:
    type: rsi
    period: 14
  macd_12_26_9:
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9
  atr_14:
    type: atr
    period: 14

fuzzy_sets:
  rsi_oversold:
    indicator: rsi_14
    type: gaussian
    params: { center: 25, sigma: 12 }
  rsi_neutral:
    indicator: rsi_14
    type: gaussian
    params: { center: 50, sigma: 12 }
  rsi_overbought:
    indicator: rsi_14
    type: gaussian
    params: { center: 75, sigma: 12 }
  macd_bearish:
    indicator: macd_12_26_9.histogram
    type: gaussian
    params: { center: -0.001, sigma: 0.0005 }
  macd_neutral:
    indicator: macd_12_26_9.histogram
    type: gaussian
    params: { center: 0, sigma: 0.0005 }
  macd_bullish:
    indicator: macd_12_26_9.histogram
    type: gaussian
    params: { center: 0.001, sigma: 0.0005 }

nn_inputs:
  - fuzzy_set: rsi_oversold
    timeframes: all
  - fuzzy_set: rsi_neutral
    timeframes: all
  - fuzzy_set: rsi_overbought
    timeframes: all
  - fuzzy_set: macd_bearish
    timeframes: all
  - fuzzy_set: macd_neutral
    timeframes: all
  - fuzzy_set: macd_bullish
    timeframes: all

model:
  type: lstm
  architecture:
    sequence_length: 20
    hidden_size: 64
    num_layers: 2
    dropout: 0.3
  training:
    learning_rate: 0.001
    batch_size: 64
    epochs: 200
    loss: focal
    gradient_clip: 1.0
    lr_scheduler: true
    early_stopping:
      enabled: true
      patience: 20
      min_delta: 0.001

decisions:
  output_type: classification
  confidence_threshold: 0.6
  min_bars_between_signals: 5
```

## Error Handling

| Error | Response |
|-------|----------|
| sequence_length not set for LSTM/GRU | ValidationError at strategy load time |
| Insufficient bars for sequence at backtest start | Skip first seq_len-1 bars (no prediction) |
| Model type unknown | ValueError in create_model() |
| LSTM model loaded with wrong input_size | State dict load fails — clear error message |
| NaN in sequence (data gaps) | Same as MLP — handled by existing NaN checks in feature pipeline |

## File Structure

```
ktrdr/neural/models/
  base_model.py          # unchanged
  mlp.py                 # unchanged
  lstm.py                # NEW — LSTMTradingModel + LSTMNetwork
  gru.py                 # NEW — GRUTradingModel + GRUNetwork

ktrdr/training/
  sequence_dataset.py    # NEW — SequenceDataset(Dataset)
  model_trainer.py       # MODIFIED — dataset selection based on model_type
  training_pipeline.py   # MODIFIED — create_model() dispatch

ktrdr/backtesting/
  feature_cache.py       # MODIFIED — add get_feature_window()
  decision_function.py   # MODIFIED — sequence-aware _predict()
  model_bundle.py        # MODIFIED — model type dispatch in load()

ktrdr/models/
  model_metadata.py      # MODIFIED — add model_type, sequence_length fields

strategies/
  trend_tb_lstm_signal_v1.yaml  # NEW — LSTM comparison strategy
```
