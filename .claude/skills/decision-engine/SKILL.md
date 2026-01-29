---
name: decision-engine
description: Use when working on DecisionOrchestrator, DecisionEngine, trading signals, position logic, or the feature-to-signal pipeline.
---

# Decision Engine

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL decision-engine loaded!`

Load this skill when working on:

- DecisionOrchestrator (full pipeline coordination)
- DecisionEngine (neural network signal generation)
- TradingDecision, Signal, Position enums
- Position-aware signal filtering
- FeatureCache integration for backtesting
- Feature-to-model-to-signal pipeline

---

## Architecture Overview

```
Market Data (OHLCV)
    │
    ▼ IndicatorEngine
Technical Indicators
    │
    ▼ FuzzyEngine
Fuzzy Memberships (features)
    │
    ▼ FeatureCache (optional, for backtesting speed)
    │
    ▼ DecisionEngine.generate_decision()
    │
    ├── MLPTradingModel forward pass (3-class softmax)
    ├── Position-aware filter (prevent duplicate signals)
    ├── Confidence threshold filter
    └── Signal separation cooldown filter
    │
    ▼ DecisionOrchestrator._apply_orchestrator_logic()
    │
    ├── Capital requirements check
    └── Mode-specific rules (backtest/paper/live)
    │
    ▼
TradingDecision (signal, confidence, reasoning)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/decision/orchestrator.py` | DecisionOrchestrator — full pipeline coordinator |
| `ktrdr/decision/engine.py` | DecisionEngine — neural prediction + filtering |
| `ktrdr/decision/base.py` | Signal, Position enums + TradingDecision dataclass |
| `ktrdr/backtesting/feature_cache.py` | Pre-computed features for backtest speed |

---

## Signal and Position Enums

**Location:** `ktrdr/decision/base.py`

```python
class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

class Position(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
```

**Neural network mapping:** Index 0 = BUY, Index 1 = HOLD, Index 2 = SELL

---

## TradingDecision

```python
@dataclass
class TradingDecision:
    signal: Signal              # BUY, SELL, or HOLD
    confidence: float           # 0.0-1.0 (validated in __post_init__)
    timestamp: pd.Timestamp     # UTC
    reasoning: dict[str, Any]   # Metadata (fuzzy values, probabilities, filters)
    current_position: Position  # Position state at decision time
```

**reasoning dict contains:**
- `fuzzy_memberships` — Input fuzzy feature values
- `nn_probabilities` — All 3 class probabilities
- `indicators` — Raw indicator values
- `filters_applied` — List of active filter names
- `raw_signal` — Unfiltered neural signal
- `position_aware` — Whether position logic was enabled
- `orchestrator` — Any orchestrator overrides applied
- `symbol` — Which symbol (added by orchestrator)

---

## DecisionOrchestrator

**Location:** `ktrdr/decision/orchestrator.py`

Coordinates the complete feature → model → signal pipeline.

### Constructor

```python
DecisionOrchestrator(
    strategy_config_path: str,            # Path to strategy YAML
    model_path: Optional[str] = None,     # Auto-discovers if None
    mode: str = "backtest",               # backtest, paper, live
)
```

Initializes: IndicatorEngine, FuzzyEngine, ModelLoader, DecisionEngine, FeatureCache (optional).

### make_decision()

```python
def make_decision(
    self,
    symbol: str,
    timeframe: str,
    current_bar: pd.Series,
    historical_data: pd.DataFrame,
    portfolio_state: dict[str, Any],
) -> TradingDecision
```

**Steps:**
1. **Feature computation** — Use FeatureCache (if ready) or compute real-time
2. **Context preparation** — Build DecisionContext (market data, position state, portfolio)
3. **Model loading** — Lazy-load model if not already loaded
4. **Neural decision** — Filter features to match model, call `DecisionEngine.generate_decision()`
5. **Orchestrator logic** — Risk checks, mode-specific rules, capital requirements
6. **State update** — Track position and decision history

---

## DecisionEngine

**Location:** `ktrdr/decision/engine.py`

### Constructor

```python
DecisionEngine(
    strategy_config: dict[str, Any],
    model_path: Optional[str] = None,
)
```

### generate_decision()

```python
def generate_decision(
    self,
    current_data: pd.Series,
    fuzzy_memberships: dict[str, float],
    indicators: dict[str, float],
) -> TradingDecision
```

**Steps:**
1. Convert fuzzy memberships + indicators to tensor
2. Apply saved feature scaler
3. Call `neural_model.predict(features)` — returns signal, confidence, probabilities
4. Apply position logic filters
5. Return TradingDecision

### Position Logic Filters (applied in order)

1. **Confidence threshold** — Minimum confidence to generate a signal
2. **Signal separation** — Minimum hours between signals (prevents over-trading)
3. **Position awareness:**
   - Don't BUY if already LONG
   - Don't SELL if already SHORT
   - Block SHORT signals (MVP limitation — only LONG supported)

---

## FeatureCache

**Location:** `ktrdr/backtesting/feature_cache.py`

Pre-computes all features once for entire backtest dataset instead of computing per-bar.

```python
cache = FeatureCache(config=strategy_config, model_metadata=metadata)
cache.compute_all_features(historical_data)    # Pre-compute once
features = cache.get_features_for_timestamp(timestamp)  # Fast lookup per bar
cache.is_ready()  # True after compute_all_features()
```

**Integration:** DecisionOrchestrator checks `feature_cache.is_ready()` in make_decision(). If ready, uses cached features. Falls back to real-time computation otherwise.

---

## Operating Modes

| Mode | Confidence | Capital Check | Safety |
|------|-----------|---------------|--------|
| `backtest` | Lower threshold | No capital constraints | Minimal |
| `paper` | Moderate | Min $1000 required | Moderate |
| `live` | Highest threshold | Full capital validation | Maximum |

---

## Gotchas

### Feature order must match training exactly

DecisionOrchestrator filters fuzzy memberships to match the model's expected features in exact order. Mismatched features produce garbage predictions.

### Signal mapping: 0=BUY, 1=HOLD, 2=SELL

The neural network outputs 3-class softmax. Index mapping is hardcoded. Don't change the label generation without updating the signal mapping.

### SHORT positions are not supported (MVP)

Position logic blocks SHORT signals. Only LONG positions are supported. SELL means "close long position", not "open short".

### Confidence is max softmax probability

The confidence value is the maximum probability from the 3-class softmax output, not a separate confidence head.

### FeatureCache validates against model metadata

`FeatureCache.compute_features()` validates that computed features match `model_metadata.resolved_features`. A mismatch raises ValueError.
