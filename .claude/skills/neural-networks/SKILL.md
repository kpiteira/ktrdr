---
name: neural-networks
description: Use when working on MLPTradingModel, BaseNeuralModel, model architecture, model saving/loading, model metadata, or model training configuration.
---

# Neural Networks

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL neural-networks loaded!`

Load this skill when working on:

- MLPTradingModel (architecture, forward pass)
- BaseNeuralModel (abstract base)
- Model configuration in V3 strategy YAML
- Model saving and loading
- Model metadata (V3 format, resolved_features)
- Model versioning and storage

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/neural/models/mlp.py` | MLPTradingModel implementation |
| `ktrdr/neural/models/base_model.py` | BaseNeuralModel abstract class |
| `ktrdr/models/model_metadata.py` | V3 ModelMetadata dataclass |
| `ktrdr/training/model_storage.py` | Model persistence and versioning |
| `ktrdr/training/model_trainer.py` | PyTorch training loop |
| `ktrdr/backtesting/model_loader.py` | Model loading for inference |
| `ktrdr/decision/engine.py` | Uses model for trading decisions |

---

## MLPTradingModel

**Location:** `ktrdr/neural/models/mlp.py`

Multi-layer perceptron for 3-class classification (BUY=0, HOLD=1, SELL=2).

### Architecture

```
Input (N features)
    → Linear(N, hidden_1) → Activation → Dropout
    → Linear(hidden_1, hidden_2) → Activation → Dropout
    → ...
    → Linear(hidden_last, 3) → Raw Logits
```

- Output is **raw logits** (NOT softmax) — `CrossEntropyLoss` applies softmax internally
- Supported activations: ReLU (default), Tanh, Sigmoid, LeakyReLU
- Configurable hidden layers, dropout rate

### Constructor

```python
MLPTradingModel(config: dict[str, Any])
```

### Key Methods

```python
build_model(input_size: int)       # Constructs nn.Sequential from config
prepare_features(fuzzy_data, indicators, saved_scaler) -> Tensor
train(X, y, validation_data)       # Training loop, returns history
predict(features, market_timestamp) -> dict  # Inference with confidence
save_model(path)                   # Persist state + metadata
load_model(path)                   # Load pre-trained model
```

### Prediction Output

```python
{
    "signal": "BUY" | "HOLD" | "SELL",
    "confidence": float,  # 0-1, max softmax probability
    "probabilities": {"BUY": float, "HOLD": float, "SELL": float}
}
```

### Model Collapse Detection

The `predict()` method includes debugging checks:
- Warns if feature variance < 1e-8 (degenerate inputs)
- Checks for NaN/infinite values
- Detects extreme confidence (>0.99)
- Monitors output entropy for stuck models

---

## BaseNeuralModel

**Location:** `ktrdr/neural/models/base_model.py`

Abstract base for all neural model types.

```python
class BaseNeuralModel(ABC):
    # Abstract — subclasses must implement
    def build_model(self, input_size: int): ...
    def prepare_features(self, fuzzy_data, indicators, saved_scaler): ...

    # Concrete
    def predict(self, features, market_timestamp=None) -> dict
    def save_model(self, path: str)
    def load_model(self, path: str)
    def _get_device(self) -> torch.device  # CUDA > MPS > CPU
```

**Attributes:** `config`, `model` (nn.Module), `is_trained`, `feature_scaler`, `input_size`

---

## V3 Strategy Model Configuration

```yaml
model:
  type: mlp                          # Currently only type supported
  architecture:
    hidden_layers: [64, 32]          # List of hidden layer sizes
    activation: relu                 # relu, tanh, sigmoid, leaky_relu
    output_activation: softmax       # IGNORED — CrossEntropyLoss handles this
    dropout: 0.2                     # Dropout rate (0-1)
  features:
    include_price_context: false     # Pure fuzzy model (no raw indicators)
    lookback_periods: 2              # Temporal lag features
    scale_features: true             # Apply feature scaling
  training:
    learning_rate: 0.001
    batch_size: 32
    epochs: 100
    optimizer: adam                   # adam or sgd (sgd uses momentum=0.9)
    early_stopping:
      enabled: true
      patience: 15
      min_delta: 0.001
```

---

## Model Storage

### Directory Structure

```
models/
  {strategy_name}/
    {timeframe}_v{N}/
      ├── model.pt              # State dict only
      ├── model_full.pt         # Full nn.Module
      ├── config.json           # Strategy config
      ├── metrics.json          # Training metrics
      ├── metadata.json         # Model metadata
      ├── features.json         # Feature information
      └── scaler.pkl            # Optional: feature scaler (legacy)
```

**Versioning:** Symbol-agnostic. Format: `{timeframe}_v{N}`. Latest model symlinked: `{timeframe}_latest → {timeframe}_v{N}`.

### Model Metadata (V3)

**Location:** `ktrdr/models/model_metadata.py`

```python
@dataclass
class ModelMetadata:
    model_name: str
    strategy_name: str
    created_at: Optional[datetime]
    strategy_version: str = "3.0"

    # V3 config (serialized for reproducibility)
    indicators: dict[str, dict[str, Any]]
    fuzzy_sets: dict[str, dict[str, Any]]
    nn_inputs: list[dict[str, Any]]

    # CRITICAL: canonical feature order
    resolved_features: list[str]

    # Training context
    training_symbols: list[str]
    training_timeframes: list[str]
    training_metrics: dict[str, float]
```

`resolved_features` is the exact ordered list of features the model was trained on. Backtesting validates features match this list.

### Features Configuration (features.json)

**Pure Fuzzy Model:**
```json
{
    "model_version": "pure_fuzzy_v1",
    "feature_type": "pure_fuzzy",
    "fuzzy_features": ["rsi_oversold", "rsi_neutral", ...],
    "feature_count": 12,
    "temporal_config": {"lookback_periods": 2, "enabled": true},
    "scaling_info": {"requires_scaling": false, "reason": "fuzzy_values_already_normalized"}
}
```

---

## Model Loading for Inference

**Location:** `ktrdr/backtesting/model_loader.py`

```python
loader = ModelLoader()
model, metadata = loader.load_model(strategy_name, symbol, timeframe)
# model: torch.nn.Module (eval mode, on appropriate device)
# metadata: ModelMetadata with resolved_features for validation
```

---

## Gotchas

### Output is logits, NOT probabilities

`MLPTradingModel` outputs raw logits. `CrossEntropyLoss` applies softmax internally during training. During inference, softmax is applied explicitly. Don't add a softmax output layer — it causes double-softmax bugs.

### output_activation config is IGNORED

The `output_activation: softmax` config field exists for documentation but is ignored in code. The model always outputs raw logits.

### Only MLP type currently supported

Factory pattern exists for extensibility, but only `type: mlp` is implemented. Unknown types raise ValueError.

### Feature scaling is architecture-dependent

Pure fuzzy models (`include_price_context: false`) don't need scaling since fuzzy memberships are already 0-1 normalized. Legacy mixed-feature models require StandardScaler.

### Device selection: CUDA > MPS > CPU

Model automatically moves to best available device. Logged once per model to avoid spam.

### resolved_features is the canonical feature order

The model's `resolved_features` list defines the exact order features must be presented. FeatureCache and FuzzyNeuralProcessor both validate against this list. Any mismatch = garbage predictions.
