---
name: technical-indicators
description: Use when working on technical indicators, IndicatorEngine, indicator computation, multi-output indicators, indicator categories, or adding new indicators.
---

# Technical Indicators

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL technical-indicators loaded!`

Load this skill when working on:

- IndicatorEngine (computation orchestrator)
- Individual indicator implementations
- Multi-output indicator handling
- Dot notation for indicator outputs
- Indicator configuration in V3 strategy YAML
- Adding new indicators
- Multi-timeframe indicator computation

---

## Architecture Overview

```
V3 Strategy YAML
    │
    ├── indicators:
    │     rsi_14: {type: rsi, period: 14}
    │     macd_12_26_9: {type: macd, fast_period: 12, slow_period: 26, signal_period: 9}
    │
    ▼
IndicatorEngine(indicators_dict)
    │
    ├── INDICATOR_REGISTRY.get(type) → instantiate BaseIndicator subclasses
    │
    ▼ compute(data, indicator_ids)
    │
    ├── Single-output: column "{indicator_id}"
    └── Multi-output: columns "{indicator_id}.{output_name}" + alias "{indicator_id}"
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/indicators/indicator_engine.py` | IndicatorEngine orchestrator |
| `ktrdr/indicators/base_indicator.py` | BaseIndicator abstract class + INDICATOR_REGISTRY |
| `ktrdr/indicators/__init__.py` | Exports, lazy loading, ensure_all_registered() |
| `ktrdr/indicators/categories.py` | IndicatorCategory enum |
| `ktrdr/config/models.py` | IndicatorDefinition Pydantic model |

### Individual Indicator Files

| File | Class | Category | Multi-Output |
|------|-------|----------|-------------|
| `rsi_indicator.py` | RSIIndicator | Momentum | No |
| `macd_indicator.py` | MACDIndicator | Momentum | Yes: line, signal, histogram |
| `ma_indicators.py` | SimpleMovingAverage, ExponentialMovingAverage | Trend | No |
| `bollinger_bands_indicator.py` | BollingerBandsIndicator | Volatility | Yes: upper, middle, lower |
| `adx_indicator.py` | ADXIndicator | Trend | Yes: adx, plus_di, minus_di |
| `atr_indicator.py` | ATRIndicator | Volatility | No |
| `stochastic_indicator.py` | StochasticIndicator | Momentum | Yes |
| `williams_r_indicator.py` | WilliamsRIndicator | Momentum | No |
| `cci_indicator.py` | CCIIndicator | Momentum | No |
| `momentum_indicator.py` | MomentumIndicator | Momentum | No |
| `roc_indicator.py` | ROCIndicator | Momentum | No |
| `obv_indicator.py` | OBVIndicator | Volume | No |
| `mfi_indicator.py` | MFIIndicator | Volume | No |
| `vwap_indicator.py` | VWAPIndicator | Volume | No |
| `ad_line.py` | ADLineIndicator | Volume | No |
| `cmf_indicator.py` | CMFIndicator | Volume | No |
| `volume_ratio_indicator.py` | VolumeRatioIndicator | Volume | No |
| `parabolic_sar_indicator.py` | ParabolicSARIndicator | Trend | No |
| `ichimoku_indicator.py` | IchimokuIndicator | Trend | Yes |
| `aroon_indicator.py` | AroonIndicator | Trend | Yes |
| `donchian_channels.py` | DonchianChannelsIndicator | Volatility | Yes |
| `keltner_channels.py` | KeltnerChannelsIndicator | Volatility | Yes |
| `supertrend_indicator.py` | SuperTrendIndicator | Trend | Yes |
| `zigzag_indicator.py` | ZigZagIndicator | Trend | No |
| `rvi_indicator.py` | RVIIndicator | Momentum | Yes |
| `fisher_transform.py` | FisherTransformIndicator | Momentum | No |
| `squeeze_intensity_indicator.py` | SqueezeIntensityIndicator | Volatility | No |
| `bollinger_band_width_indicator.py` | BollingerBandWidthIndicator | Volatility | No |
| `distance_from_ma_indicator.py` | DistanceFromMAIndicator | Support/Resistance | No |

---

## IndicatorEngine

**Location:** `ktrdr/indicators/indicator_engine.py`

### Initialization

```python
IndicatorEngine(indicators: dict[str, Any])
# V3 format ONLY: {"indicator_id": {"type": "...", ...params}}
# Converts dicts to IndicatorDefinition, instantiates via INDICATOR_REGISTRY
# Raises ConfigurationError if non-dict format passed
```

### Core Methods

```python
compute(data: pd.DataFrame, indicator_ids: set[str]) -> pd.DataFrame
# Computes specified indicators
# Single-output: column named {indicator_id}
# Multi-output: columns {indicator_id}.{output_name} + alias {indicator_id} (primary)

apply(data: pd.DataFrame) -> pd.DataFrame
# Convenience: computes ALL configured indicators
# Requires 'close' column minimum

compute_for_timeframe(data: pd.DataFrame, timeframe: str, indicator_ids: set[str]) -> pd.DataFrame
# Like compute(), but prefixes indicator columns with {timeframe}_
# OHLCV columns NOT prefixed

apply_multi_timeframe(
    multi_timeframe_ohlcv: dict[str, pd.DataFrame],
    indicator_configs: Optional[dict[str, dict]] = None,
    prefix_columns: bool = True
) -> dict[str, pd.DataFrame]
# Processes all timeframes with same indicators
# Default: prefixes columns with timeframe to prevent collisions
```

---

## BaseIndicator

**Location:** `ktrdr/indicators/base_indicator.py`

Abstract base class for all indicators.

```python
class BaseIndicator(ABC):
    @abstractmethod
    def compute(self, df: pd.DataFrame) -> Union[pd.Series, pd.DataFrame]:
        """Compute indicator values."""

    @classmethod
    def is_multi_output(cls) -> bool:
        """True if indicator returns DataFrame."""
        return False

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Semantic output names for multi-output indicators."""
        # Single-output: return []
        # Multi-output: return ["output1", "output2", ...]
        # First item is primary output
        return []

    @classmethod
    def get_primary_output(cls) -> Optional[str]:
        """First output name, or None for single-output."""

    def validate_input_data(self, df: pd.DataFrame, required_columns: list) -> None
    def validate_sufficient_data(self, df: pd.DataFrame, min_periods: int) -> None
```

---

## V3 Strategy Configuration

### IndicatorDefinition

```python
class IndicatorDefinition(BaseModel):
    type: str  # Indicator type (rsi, macd, bbands, adx, etc.)
    model_config = {"extra": "allow"}  # All other fields are parameters
```

### YAML Format

```yaml
indicators:
  rsi_14:                     # indicator_id (user-chosen name)
    type: rsi                 # type: lowercase, PascalCase, or UPPERCASE
    period: 14
    source: close             # Optional parameter

  macd_12_26_9:               # Multi-output indicator
    type: macd
    fast_period: 12
    slow_period: 26
    signal_period: 9

  bbands_20_2:
    type: BollingerBands      # PascalCase works too
    period: 20
    multiplier: 2.0
```

### Naming Convention

- **Format:** `{indicator_name}_{param1}[_{param2}...]`
- **Examples:** `rsi_14`, `ema_20`, `macd_12_26_9`, `bbands_20_2`, `adx_14`
- Must start with letter, alphanumeric + underscore + dash only
- Cannot use reserved OHLCV names (open, high, low, close, volume)

---

## Multi-Output Indicators and Dot Notation

### Column Naming

When IndicatorEngine computes a multi-output indicator:

```python
# For indicator_id "macd_12_26_9" with outputs ["line", "signal", "histogram"]:
# Columns produced:
#   macd_12_26_9.line        (primary)
#   macd_12_26_9.signal
#   macd_12_26_9.histogram
#   macd_12_26_9             (alias → points to .line)
```

### Common Multi-Output Indicators

| Indicator | Outputs |
|-----------|---------|
| MACD | `line`, `signal`, `histogram` |
| Bollinger Bands | `upper`, `middle`, `lower` |
| ADX | `adx`, `plus_di`, `minus_di` |
| Stochastic | `k`, `d` |
| Ichimoku | `tenkan`, `kijun`, `senkou_a`, `senkou_b`, `chikou` |
| Keltner Channels | `upper`, `middle`, `lower` |
| Donchian Channels | `upper`, `middle`, `lower` |
| Aroon | `up`, `down`, `oscillator` |
| RVI | `rvi`, `signal` |
| SuperTrend | `trend`, `direction` |

### Using Dot Notation in Fuzzy Sets

```yaml
indicators:
  adx_14:
    type: adx
    period: 14

fuzzy_sets:
  adx_strength:
    indicator: adx_14.adx         # Specific output
  di_plus:
    indicator: adx_14.plus_di     # Another output
  di_minus:
    indicator: adx_14.minus_di    # Third output
```

Reference `indicator_id` (without dot) to use primary output. Reference `indicator_id.output_name` for a specific output.

---

## Indicator Categories

```python
class IndicatorCategory(Enum):
    TREND = "trend"                        # SMA, EMA, ADX, Ichimoku, etc.
    MOMENTUM = "momentum"                  # RSI, MACD, Stochastic, etc.
    VOLATILITY = "volatility"              # ATR, Bollinger, Keltner, etc.
    VOLUME = "volume"                      # OBV, MFI, VWAP, CMF, etc.
    SUPPORT_RESISTANCE = "support_resistance"  # DistanceFromMA
    MULTI_PURPOSE = "multi_purpose"        # Versatile indicators
```

---

## Computation Details

### Implementation

All indicators use **custom implementations** with pandas and numpy. No external TA-Lib or pandas-ta dependency.

### NaN Handling

- Indicators produce NaN for initial warmup rows (e.g., RSI(14) → first 14 rows NaN)
- Engine does NOT strip NaN rows — preserves full index alignment
- Caller is responsible for handling NaN (e.g., FuzzyNeuralProcessor converts to 0.0)

### Timeframe Prefixing

```python
# With prefix_columns=True (default in apply_multi_timeframe):
# "rsi_14" → "1h_rsi_14"
# "macd_12_26_9.line" → "1h_macd_12_26_9.line"

# OHLCV columns (open, high, low, close, volume) are NEVER prefixed
```

---

## Adding a New Indicator

Create one file:

```python
# ktrdr/indicators/awesome_indicator.py
from pydantic import Field
from ktrdr.indicators.base_indicator import BaseIndicator

class AwesomeIndicator(BaseIndicator):
    class Params(BaseIndicator.Params):
        fast_period: int = Field(default=5, ge=1)
        slow_period: int = Field(default=34, ge=1)

    # No __init__ needed - BaseIndicator handles validation

    def compute(self, df):
        # Use self.fast_period, self.slow_period (set from Params)
        self.validate_input_data(df, ["close"])
        # ... compute indicator ...
        return result_series
```

That's it. The indicator auto-registers as 'awesome', 'awesomeindicator', etc.

For multi-output indicators, also override:
```python
    @classmethod
    def is_multi_output(cls) -> bool:
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        return ["line", "signal", "histogram"]  # First is primary
```

---

## Registry API

```python
from ktrdr.indicators import INDICATOR_REGISTRY

INDICATOR_REGISTRY.list_types()           # ['adx', 'atr', 'bollingerbands', ...]
INDICATOR_REGISTRY.get('rsi')             # RSIIndicator class
INDICATOR_REGISTRY.get_params_schema('rsi')  # RSIIndicator.Params model
```

Use `ensure_all_registered()` before listing/validating to ensure lazy-loaded indicators are available:

```python
from ktrdr.indicators import INDICATOR_REGISTRY, ensure_all_registered

ensure_all_registered()  # Loads all indicator modules
print(INDICATOR_REGISTRY.list_types())  # Full list
```

---

## Gotchas

### V3 format only

IndicatorEngine only accepts `dict[str, IndicatorDefinition]`. Legacy list formats raise `ConfigurationError`.

### prefix_columns=False for training pipeline

`IndicatorEngine.apply()` must use `prefix_columns=False` when computing for fuzzy processing, because `FuzzyNeuralProcessor` handles all column prefixing. Double-prefixing breaks feature matching.

### Indicator state resets at symbol boundaries

When computing indicators for multi-symbol training data, indicator state (e.g., EMA history) must reset between symbols. Otherwise the first symbol's final values pollute the next symbol's initial values.

### Alias column for primary output

Multi-output indicators create an alias column without dot notation (`macd_12_26_9`) pointing to the primary output (`macd_12_26_9.line`). This enables simple references in fuzzy set configs.

### Case-insensitive type lookup

The factory registry maps PascalCase, UPPERCASE, and lowercase to the same class. `rsi`, `RSI`, and `RSIIndicator` all resolve to `RSIIndicator`.

### NaN rows are preserved

Unlike some TA libraries, the engine preserves NaN rows from warmup periods. The simulation loop typically skips the first ~50 bars to account for indicator warmup.
