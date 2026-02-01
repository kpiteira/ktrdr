---
name: fuzzy-logic-engine
description: Use when working on fuzzy membership functions, fuzzy sets, fuzzy-to-neural bridging, FuzzyEngine configuration, or V3 fuzzy set definitions.
---

# Fuzzy Logic Engine

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL fuzzy-logic-engine loaded!`

Load this skill when working on:

- FuzzyEngine (fuzzification of indicator values)
- Membership functions (triangular, trapezoidal, gaussian)
- V3 fuzzy set definitions in strategy YAML
- FuzzyNeuralProcessor (fuzzy-to-neural bridge)
- Multi-timeframe fuzzy processing
- Feature ordering and validation
- Fuzzy configuration and shorthand notation

---

## Architecture Overview

```
V3 Strategy YAML
    │
    ├── indicators: {rsi_14: {type: rsi, period: 14}, ...}
    ├── fuzzy_sets: {rsi_momentum: {indicator: rsi_14, oversold: [0,20,35], ...}}
    └── nn_inputs: [{fuzzy_set: rsi_momentum, timeframes: [1h, 4h]}]
    │
    ▼
IndicatorEngine.compute() → raw indicator values (e.g., RSI=35.2)
    │
    ▼
FuzzyEngine.fuzzify() → membership degrees (e.g., oversold=0.7, neutral=0.3)
    │
    ▼
FuzzyNeuralProcessor.prepare_input() → ordered tensor for neural network
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/fuzzy/engine.py` | FuzzyEngine — main fuzzification entry point |
| `ktrdr/fuzzy/membership.py` | MembershipFunction base class + MEMBERSHIP_REGISTRY |
| `ktrdr/fuzzy/__init__.py` | Exports MEMBERSHIP_REGISTRY and all MF types |
| `ktrdr/fuzzy/batch_calculator.py` | BatchFuzzyCalculator for time series |
| `ktrdr/fuzzy/multi_timeframe_engine.py` | Multi-timeframe fuzzy processing |
| `ktrdr/training/fuzzy_neural_processor.py` | FuzzyNeuralProcessor (fuzzy → neural) |
| `ktrdr/config/models.py` | FuzzySetDefinition, NNInputSpec |
| `config/fuzzy.yaml` | Default fuzzy set definitions |

---

## FuzzyEngine

**Location:** `ktrdr/fuzzy/engine.py`

FuzzyEngine only accepts dict of `FuzzySetDefinition` format.

### Initialization

```python
FuzzyEngine(config: dict[str, FuzzySetDefinition])
# Raises ConfigurationError if legacy format is passed
```

### Key Methods

```python
fuzzify(fuzzy_set_id: str, indicator_values: pd.Series, context_data=None)
    -> dict[str, pd.Series]  # {membership_name: degree_series}

get_indicator_for_fuzzy_set(fuzzy_set_id: str) -> str
get_membership_names(fuzzy_set_id: str) -> list[str]
```

**Multi-timeframe:**

```python
generate_multi_timeframe_memberships(
    multi_timeframe_indicators: dict[str, pd.DataFrame],
    fuzzy_sets_config: Optional[dict[str, dict]] = None
) -> dict[str, pd.DataFrame]
# Input: {"15m": DataFrame[rsi_14, sma_20, ...], "1h": DataFrame[...]}
# Output: {"15m": DataFrame[15m_rsi_oversold, 15m_rsi_neutral, ...], ...}
```

---

## Membership Functions

**Location:** `ktrdr/fuzzy/membership.py`

### Types Supported

| Type | Parameters | Formula |
|------|-----------|---------|
| Triangular | `[a, b, c]` | Ramps up from a to peak b, down to c |
| Trapezoidal | `[a, b, c, d]` | Ramps up a→b, flat b→c, down c→d |
| Gaussian | `[mu, sigma]` | `exp(-0.5 * ((x-mu)/sigma)^2)` |

### Triangular: `[a, b, c]` where a <= b <= c

```
mu(x) = 0,                 if x <= a or x >= c
mu(x) = (x - a) / (b - a), if a < x < b
mu(x) = (c - x) / (c - b), if b <= x < c
```

Special cases: `a == b` (left edge peak), `b == c` (right edge peak). Peak always returns exactly 1.0.

### Trapezoidal: `[a, b, c, d]` where a <= b <= c <= d

```
mu(x) = 0,                 if x <= a or x >= d
mu(x) = (x - a) / (b - a), if a < x < b
mu(x) = 1,                 if b <= x <= c
mu(x) = (d - x) / (d - c), if c < x < d
```

Flat-top peak between b and c.

### Gaussian: `[mu, sigma]` where sigma > 0

```
mu(x) = exp(-0.5 * ((x - mu) / sigma)^2)
```

Smooth bell curve, never exactly 0.

### Vectorization

All `evaluate()` methods accept scalar, `pd.Series`, or `np.ndarray`. Returns same type as input. Vectorized numpy implementations for speed.

### Registry API

```python
from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

MEMBERSHIP_REGISTRY.list_types()  # ['gaussian', 'trapezoidal', 'triangular']
MEMBERSHIP_REGISTRY.get('triangular')  # TriangularMF class
MEMBERSHIP_REGISTRY.get_params_schema('gaussian')  # GaussianMF.Params model
```

---

## Adding a New Membership Function

Create one file:

```python
# ktrdr/fuzzy/sigmoid_mf.py
from pydantic import field_validator
from ktrdr.fuzzy.membership import MembershipFunction

class SigmoidMF(MembershipFunction):
    class Params(MembershipFunction.Params):
        @field_validator("parameters")
        @classmethod
        def validate_parameters(cls, v):
            if len(v) != 2:
                raise ValueError("Sigmoid requires [center, slope]")
            return v

    def _init_from_params(self, parameters):
        self.center, self.slope = parameters

    def evaluate(self, x):
        # Return membership degree in [0, 1]
        ...
```

Auto-registers as 'sigmoid', 'sigmoidmf', etc.

---

## Fuzzy Set Configuration

### FuzzySetDefinition

**Location:** `ktrdr/config/models.py`

```python
class FuzzySetDefinition(BaseModel):
    indicator: str              # indicator_id or indicator_id.output_name
    model_config = {"extra": "allow"}  # Membership names stored as extra fields
```

### Strategy YAML Format

```yaml
fuzzy_sets:
  rsi_momentum:                # fuzzy_set_id
    indicator: "rsi_14"        # Links to indicator definition
    oversold: [0, 20, 35]      # Shorthand triangular
    neutral: [30, 50, 70]
    overbought: [65, 80, 100]

  bbands_position:
    indicator: "bbands_20_2.upper"  # Dot notation for multi-output
    near_price:
      type: triangular
      parameters: [0.98, 1.0, 1.02]
    far_price:
      type: gaussian
      parameters: [1.1, 0.05]
```

### Shorthand Notation

`[a, b, c]` automatically expands to `{type: "triangular", parameters: [a, b, c]}` via a Pydantic `model_validator`.

### Dot Notation for Multi-Output Indicators

`indicator: "adx_14.plus_di"` references a specific output of a multi-output indicator. FuzzyEngine resolves this to the actual DataFrame column.

---

## FuzzyNeuralProcessor

**Location:** `ktrdr/training/fuzzy_neural_processor.py`

Converts fuzzy membership DataFrames into neural network input tensors.

### Initialization

```python
FuzzyNeuralProcessor(
    config: dict[str, Any],                    # Fuzzy processing config
    disable_temporal: bool = False,            # Skip temporal features (for backtesting)
    resolved_features: Optional[list[str]] = None  # V3 canonical feature order
)
```

### Single Timeframe

```python
prepare_input(fuzzy_data: pd.DataFrame) -> tuple[torch.Tensor, list[str]]
# V3 mode: validates all features present, returns in canonical order
# Legacy mode: extracts fuzzy columns, adds temporal features, converts NaN to 0.0
# Returns: (tensor of shape [batch, features], feature_names)
```

### Multi-Timeframe

```python
prepare_multi_timeframe_input(
    multi_timeframe_fuzzy: dict[str, pd.DataFrame],
    timeframe_order: Optional[list[str]] = None
) -> tuple[torch.Tensor, list[str]]
# Aligns timeframes temporally (e.g., 1h timestamp uses matching 1d features)
# Column names prefixed: "{timeframe}_{feature_name}"
```

### Feature Ordering

**V3 mode (resolved_features set):**
- Features must be in exact order from `resolved_features` list
- All feature names must match exactly (case-sensitive)
- Raises `ValueError` if features are missing
- This ensures training and backtesting use identical feature order

**Legacy mode:**
- Extracts columns containing underscore, "membership", or fuzzy keywords
- Adds temporal features if `lookback_periods > 0` (format: `{column}_lag_{N}`)
- Alphabetical sort for consistency

### NNInputSpec in V3 YAML

```yaml
nn_inputs:
  - fuzzy_set: "rsi_momentum"
    timeframes: ["15m", "1h", "4h"]
  - fuzzy_set: "bbands_position"
    timeframes: "all"
```

```python
class NNInputSpec(BaseModel):
    fuzzy_set: str                           # fuzzy_set_id
    timeframes: Union[list[str], str]        # Specific list or "all"
```

---

## Feature ID Matching

When FuzzyEngine maps indicator columns to fuzzy sets, it uses this priority:

1. **Direct match:** Column name exactly equals fuzzy key
2. **Dot notation prefix:** Column starts with fuzzy_key + "." (multi-output)
3. **Indicator map:** Column matches the indicator referenced by the fuzzy set
4. **Legacy underscore:** Column starts with fuzzy_key + "_" (backward compatibility)

---

## Multi-Timeframe Processing

### Flow

```python
# 1. Compute indicators per timeframe
indicator_data = {
    "15m": indicator_engine.compute(data_15m, indicator_ids),
    "1h": indicator_engine.compute(data_1h, indicator_ids),
}

# 2. Generate fuzzy memberships per timeframe
fuzzy_data = fuzzy_engine.generate_multi_timeframe_memberships(indicator_data)
# Result: {"15m": DataFrame[15m_rsi_oversold, ...], "1h": DataFrame[1h_rsi_oversold, ...]}

# 3. Align and combine for neural network
tensor, names = processor.prepare_multi_timeframe_input(fuzzy_data)
# Temporal alignment: 1h timestamp uses matching 4h features
# Result: combined tensor with all timeframes horizontally concatenated
```

### Temporal Alignment

Higher-frequency timeframes drive resolution. Lower-frequency features are forward-filled:
- `1h 2024-01-02 09:00` uses `1d 2024-01-02` features
- `1h 2024-01-02 10:00` uses same `1d 2024-01-02` features
- `1h 2024-01-03 09:00` uses new `1d 2024-01-03` features

---

## Gotchas

### Feature order must match training exactly

The `FeatureCache` and `FuzzyNeuralProcessor` validate that features match `model_metadata.resolved_features` in exact order. Mismatched features produce garbage model predictions. This is the single most common source of backtesting bugs.

### Shorthand is triangular only

`[a, b, c]` always expands to triangular. For trapezoidal or gaussian, use full form: `{type: "gaussian", parameters: [50, 15]}`.

### FuzzyNeuralProcessor handles column prefixing

When computing indicators for fuzzy processing, use `prefix_columns=False` on `IndicatorEngine`. The `FuzzyNeuralProcessor` handles all prefixing. Double-prefixing breaks feature matching.

### FuzzyEngine only accepts dict format

`FuzzyEngine` requires `dict[str, FuzzySetDefinition]` format. Legacy FuzzyConfig is no longer supported.

### context_data enables price ratios

Passing `context_data` (DataFrame with OHLCV columns) to `fuzzify()` enables input transforms like `price_ratio = close / indicator_value`. Without it, raw indicator values are used.

### NaN values converted to 0.0 in neural processor

`FuzzyNeuralProcessor.prepare_input()` replaces NaN with 0.0 before creating tensors. This handles warmup period NaN values from indicators.
