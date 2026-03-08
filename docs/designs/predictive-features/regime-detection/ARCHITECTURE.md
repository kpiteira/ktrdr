# Regime Detection — Architecture Document

## Status: Draft
## Date: 2026-03-07
## Contributors: Karl + Lux

---

## 1. System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Ensemble Backtest Runner                          │
│                                                                      │
│  For each bar:                                                       │
│    1. Get features from regime FeatureCache                          │
│    2. Run RegimeClassifier → regime probabilities                    │
│    3. RegimeRouter determines active regime + active signal model     │
│    4. Get features from active signal model's FeatureCache           │
│    5. Run active SignalModel → direction + confidence                │
│    6. On regime transition: close outgoing position, switch model     │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Model Bundle  │  │ Model Bundle  │  │ Model Bundle  │  ...        │
│  │ (regime)      │  │ (trend_long)  │  │ (mean_rev)    │             │
│  │               │  │               │  │               │             │
│  │ output_type:  │  │ output_type:  │  │ output_type:  │             │
│  │  regime_class │  │  classif.     │  │  classif.     │             │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │ Ensemble Config                                              │    │
│  │                                                              │    │
│  │ models: { regime, trend_long, trend_short, mean_reversion }  │    │
│  │ composition:                                                 │    │
│  │   type: regime_route                                         │    │
│  │   rules:                                                     │    │
│  │     trending_up:   → trend_long                              │    │
│  │     trending_down: → trend_short                             │    │
│  │     ranging:       → mean_reversion                          │    │
│  │     volatile:      → FLAT                                    │    │
│  │   on_regime_transition: close_and_switch                     │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Owns |
|-----------|---------------|------|
| RegimeLabeler | Generate forward-looking regime labels for training (4-class) | Signed ER + RV computation, thresholds |
| RegimeClassifier | Standard MLP trained on regime labels | Nothing special — it's a regular ModelBundle |
| EnsembleConfig | Define which models compose and how they route | Model references, routing rules, transition policy |
| EnsembleBacktestRunner | Orchestrate multi-model backtest | Model loading, per-bar routing, feature caches |
| RegimeRouter | Determine active regime, dispatch to correct signal model, handle transitions | Routing logic, transition handling |
| FeatureCache (existing) | Pre-compute features per model | One FeatureCache per model in ensemble |
| PositionManager (existing) | Track positions and execute trades | Unchanged — single position manager for ensemble |

---

## 2. New Components

### 2.1 RegimeLabeler

```
Location: ktrdr/training/regime_labeler.py

class RegimeLabeler:
    """Forward-looking regime labeler using Signed Efficiency Ratio + Realized Volatility.

    Produces 4-class labels:
      0 = TRENDING_UP    (efficient upward movement)
      1 = TRENDING_DOWN  (efficient downward movement)
      2 = RANGING         (inefficient, bounded movement)
      3 = VOLATILE        (extreme realized volatility)
    """

    def __init__(
        self,
        horizon: int = 24,
        trending_threshold: float = 0.5,
        vol_crisis_threshold: float = 2.0,
        vol_lookback: int = 120,
    ) -> None: ...

    def generate_labels(
        self,
        price_data: pd.DataFrame,
    ) -> pd.Series:
        """Generate regime labels for each bar.

        Returns:
            Series with values 0-3. Last `horizon` bars are NaN (no future data).
        """

    def compute_signed_efficiency_ratio(
        self,
        close: pd.Series,
        horizon: int,
    ) -> pd.Series:
        """Forward-looking signed efficiency ratio per bar.

        SER = (close[T+H] - close[T]) / Σ|close[t+1] - close[t]| for t in [T, T+H)

        Range: -1.0 (perfect downtrend) to +1.0 (perfect uptrend).
        Near 0 = ranging (lots of movement, no net direction).
        """

    def compute_realized_volatility_ratio(
        self,
        close: pd.Series,
        horizon: int,
        lookback: int,
    ) -> pd.Series:
        """Forward realized vol / rolling historical vol.

        RV_ratio > threshold indicates extreme volatility (crisis regime).
        """

    def analyze_labels(
        self,
        labels: pd.Series,
        price_data: pd.DataFrame,
    ) -> RegimeLabelStats:
        """Compute label statistics: distribution, persistence, return-by-regime,
        transition frequency, transition matrix."""

@dataclass
class RegimeLabelStats:
    """Analysis of regime label quality."""
    distribution: dict[str, float]         # {regime_name: fraction}
    mean_duration_bars: dict[str, float]   # {regime_name: avg bars}
    mean_return_by_regime: dict[str, float] # {regime_name: avg forward return}
    transition_matrix: dict[str, dict[str, float]]  # from → to → probability
    total_bars: int
    total_transitions: int
```

**Data flow:**
```
OHLCV close prices
  → compute_signed_efficiency_ratio(close, horizon=24)
    → Series of SER values (-1.0 to +1.0) per bar
  → compute_realized_volatility_ratio(close, horizon=24, lookback=120)
    → Series of RV ratios per bar
  → classify:
      VOLATILE(3)     if RV_ratio > vol_crisis_threshold
      TRENDING_UP(0)  if SER > +trending_threshold
      TRENDING_DOWN(1) if SER < -trending_threshold
      RANGING(2)      otherwise
    → Series of labels (0, 1, 2, 3)
```

### 2.2 Ensemble Configuration

```
Location: ktrdr/config/ensemble_config.py

@dataclass
class ModelReference:
    """Reference to a trained model bundle."""
    name: str                    # Logical name in ensemble (e.g., "regime", "trend_long")
    model_path: str              # Path to model bundle directory
    output_type: str             # "regime_classification", "classification", "regression"

@dataclass
class RouteRule:
    """What to do when a specific regime is detected."""
    model: str | None            # Which signal model to dispatch to (None = no model)
    action: str | None           # Fixed action (e.g., "FLAT") — mutually exclusive with model

@dataclass
class CompositionConfig:
    """How models compose their outputs."""
    type: str                    # "regime_route" (extensible to other types later)
    gate_model: str              # Which model produces the regime classification
    regime_threshold: float      # Min probability to assign regime (default: 0.4)
    stability_bars: int          # Consecutive bars required before regime transition (default: 3, prevents flicker)
    rules: dict[str, RouteRule]  # regime_name → which signal model to route to
    on_regime_transition: str    # "close_and_switch" | "let_run" | "tighten_stops"

@dataclass
class EnsembleConfiguration:
    """Top-level ensemble configuration."""
    name: str
    description: str | None
    models: dict[str, ModelReference]
    composition: CompositionConfig
```

**Example YAML:**
```yaml
name: regime_routed_v1
description: Regime-routed strategy with per-regime signal models

models:
  regime:
    model_path: models/regime_classifier_v1
    output_type: regime_classification
  trend_long:
    model_path: models/trend_follower_long_v1
    output_type: classification
  trend_short:
    model_path: models/trend_follower_short_v1
    output_type: classification
  mean_reversion:
    model_path: models/range_trader_v1
    output_type: classification

composition:
  type: regime_route
  gate_model: regime
  regime_threshold: 0.4
  rules:
    trending_up:
      model: trend_long
    trending_down:
      model: trend_short
    ranging:
      model: mean_reversion
    volatile:
      action: FLAT
  on_regime_transition: close_and_switch
```

### 2.3 EnsembleBacktestRunner

```
Location: ktrdr/backtesting/ensemble_runner.py

class EnsembleBacktestRunner:
    """Orchestrates multi-model backtesting with regime routing."""

    def __init__(
        self,
        ensemble_config: EnsembleConfiguration,
        backtest_config: BacktestConfig,
    ) -> None: ...

    async def run(
        self,
        progress: ProgressBridge | None = None,
        cancellation: CancellationToken | None = None,
    ) -> EnsembleBacktestResults: ...

    def _load_models(self) -> dict[str, ModelBundle]:
        """Load all model bundles referenced in ensemble config."""

    def _create_feature_caches(
        self,
        models: dict[str, ModelBundle],
        price_data: dict[str, pd.DataFrame],
    ) -> dict[str, FeatureCache]:
        """Create one FeatureCache per model (each may need different indicators/features)."""

    def _run_bar(
        self,
        timestamp: pd.Timestamp,
        bar: pd.Series,
        feature_caches: dict[str, FeatureCache],
        decision_functions: dict[str, DecisionFunction],
        router: RegimeRouter,
        position_manager: PositionManager,
    ) -> BarResult: ...
```

**Per-bar flow:**
```
1. regime_features = feature_caches["regime"].get_features_for_timestamp(ts)

2. regime_decision = decision_functions["regime"](regime_features, position, bar)
   → raw classification output (4 softmax probabilities)

3. regime_probs = interpret_regime_output(regime_decision)
   → {trending_up: 0.65, trending_down: 0.10, ranging: 0.20, volatile: 0.05}

4. route_result = router.route(regime_probs, previous_regime, position)
   → RouteDecision:
       active_regime: "trending_up"
       active_model: "trend_long"
       transition: None | TransitionAction(close_position=True)

5. IF route_result.transition and route_result.transition.close_position:
     position_manager.execute_trade(close_signal, bar["close"], ts)  # Note: execute_trade(signal, price, timestamp)

6. IF route_result.active_model is not None:
     signal_features = feature_caches[route_result.active_model].get(ts)
     signal_decision = decision_functions[route_result.active_model](signal_features, position, bar)
     → TradingDecision with signal + confidence
   ELSE:
     → TradingDecision(HOLD, reasoning="regime: volatile → FLAT")

7. position_manager.execute_trade(final_decision["signal"], bar["close"], bar.name)
```

### 2.4 RegimeRouter

```
Location: ktrdr/backtesting/regime_router.py

REGIME_NAMES = ["trending_up", "trending_down", "ranging", "volatile"]

class RegimeRouter:
    """Routes to per-regime signal models based on regime classification output."""

    def __init__(self, composition: CompositionConfig) -> None:
        self._regime_counter: int = 0         # Bars since last regime change
        self._pending_regime: str | None = None  # Regime waiting for stability confirmation
        ...

    def route(
        self,
        regime_probs: dict[str, float],      # {regime: probability}
        previous_regime: str | None,          # regime from last bar
        current_position: PositionStatus,
    ) -> RouteDecision:
        """Determine which signal model to run.

        1. Find dominant regime (highest probability above threshold)
        2. Apply regime stability filter: require N consecutive bars of new regime
           before transitioning (prevents costly flicker — see Scenario 7)
        3. If stable transition: apply transition policy (close_and_switch / let_run)
        4. Look up route rule for active regime
        5. Return which model to run (or forced action)
        """

@dataclass
class TransitionAction:
    """What to do during a regime transition."""
    close_position: bool                  # Whether to close current position
    from_regime: str
    to_regime: str

@dataclass
class RouteDecision:
    """Result of regime routing."""
    active_regime: str                     # Which regime was detected
    regime_confidence: float               # Probability of active regime
    active_model: str | None               # Which signal model to run (None = FLAT)
    transition: TransitionAction | None    # If regime changed, what to do
    reasoning: str                         # Human-readable explanation
```

---

## 3. Extensions to Existing Components

### 3.1 Training Pipeline — Regime Label Source

**Important:** Label source dispatch must be updated in BOTH locations:
1. `ktrdr/training/training_pipeline.py` (container workers)
2. `training-host-service/orchestrator.py` (host service — has its own separate dispatch code)

We hit this exact dual-dispatch bug before with `forward_return` labels. The host service is always preferred for training, so missing it means the fix silently doesn't apply.

```
Location: ktrdr/training/training_pipeline.py AND training-host-service/orchestrator.py

# Add to label source dispatch (in both files):
if label_config["source"] == "regime":
    labeler = RegimeLabeler(
        horizon=label_config.get("horizon", 24),
        trending_threshold=label_config.get("trending_threshold", 0.5),
        vol_crisis_threshold=label_config.get("vol_crisis_threshold", 2.0),
        vol_lookback=label_config.get("vol_lookback", 120),
    )
    return labeler.generate_labels(price_data)
```

### 3.2 Strategy Grammar — No Changes Needed

Regime classifier uses existing v3 format with `output_format: classification` (4-class). The regime labeler produces standard classification labels (0, 1, 2, 3) — same format as zigzag.

### 3.3 Seed Strategy — Starting Point for the Researcher

The architecture ships a **seed regime strategy** as a sensible starting point. This is a regular v3 strategy YAML — not hard-coded, not special. The Researcher can mutate it, replace it, or generate entirely new approaches.

```yaml
# strategies/regime_classifier_seed_v1.yaml
# Seed strategy for regime classification — a starting point, not the answer.
# The Researcher should evolve this: try different indicators, fuzzy shapes,
# architectures, and labeling parameters.

name: regime_classifier_seed
version: "3.0"
description: >
  Seed regime classifier using volatility and trend strength indicators.
  Predicts: 0=TRENDING_UP, 1=TRENDING_DOWN, 2=RANGING, 3=VOLATILE.
  This is a starting point for the Researcher to evolve.

training_data:
  symbols:
    mode: single
    symbol: EURUSD
  timeframes:
    mode: single
    timeframe: 1h
  history_required: 200
  start_date: "2019-01-01"
  end_date: "2024-01-01"

indicators:
  atr_14:
    type: atr
    period: 14
  atr_50:
    type: atr
    period: 50
  bbwidth_20:
    type: bollinger_band_width
    period: 20
  adx_14:
    type: adx
    period: 14
  squeeze_20:
    type: squeeze_intensity
    period: 20

fuzzy_sets:
  atr_short:
    indicator: atr_14
    low: [0, 0.0005, 0.001]
    medium: [0.0005, 0.001, 0.002]
    high: [0.001, 0.002, 0.005]

  atr_long:
    indicator: atr_50
    low: [0, 0.0005, 0.001]
    medium: [0.0005, 0.001, 0.002]
    high: [0.001, 0.002, 0.005]

  bbwidth_level:
    indicator: bbwidth_20
    tight: [0, 0.01, 0.02]
    normal: [0.01, 0.03, 0.05]
    wide: [0.03, 0.06, 0.10]

  adx_strength:
    indicator: adx_14.adx
    weak: [0, 10, 20]
    moderate: [15, 25, 35]
    strong: [25, 40, 60]

  trend_direction:
    indicator: adx_14.plus_di
    weak: [0, 10, 20]
    strong: [20, 30, 50]

  squeeze_level:
    indicator: squeeze_20
    relaxed: [0, 0.2, 0.4]
    building: [0.3, 0.5, 0.7]
    squeezed: [0.6, 0.8, 1.0]

nn_inputs:
  - fuzzy_set: atr_short
    timeframes: all
  - fuzzy_set: atr_long
    timeframes: all
  - fuzzy_set: bbwidth_level
    timeframes: all
  - fuzzy_set: adx_strength
    timeframes: all
  - fuzzy_set: trend_direction
    timeframes: all
  - fuzzy_set: squeeze_level
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [64, 32]
    dropout: 0.2
    activation: relu

decisions:
  output_format: classification
  confidence_threshold: 0.4

training:
  labels:
    source: regime
    horizon: 24
    trending_threshold: 0.5
    vol_crisis_threshold: 2.0
    vol_lookback: 120
  loss: cross_entropy
  epochs: 100
  learning_rate: 0.001
```

**Why these indicators as a starting point:**
- ATR (short + long) — the NN can learn the ratio between them (volatility expansion/contraction)
- Bollinger Band Width — normalized volatility, complementary to ATR
- ADX + DI+ — trend strength and directional bias
- Squeeze Intensity — pre-breakout detection

**What the Researcher should try evolving:**
- Different indicator combinations (add candle structure? volume? momentum?)
- Different fuzzy set shapes and boundaries
- Different NN architectures (deeper? wider? different activation?)
- Different labeling parameters (horizon, thresholds)
- Multi-timeframe regime detection (add daily context)

### 3.4 ModelBundle — Output Type Tag

```
Location: ktrdr/models/model_metadata.py

# Add to ModelMetadata:
output_type: str = "classification"
# Values: "classification", "regression", "regime_classification"
# Stored in metadata_v3.json, read by EnsembleBacktestRunner

# regime_classification uses standard 4-class softmax.
# The tag tells the ensemble runner how to interpret outputs:
#   class 0 = TRENDING_UP, class 1 = TRENDING_DOWN, class 2 = RANGING, class 3 = VOLATILE
```

### 3.5 DecisionFunction — Needs N-Class Generalization

**Important:** The existing DecisionFunction is hardcoded to 3-class output (BUY/HOLD/SELL with a 3-element softmax). It does NOT currently handle 4-class regime classification. M2 or M3 must generalize DecisionFunction to N-class, or the EnsembleBacktestRunner must bypass DecisionFunction and interpret raw model output directly.

Once generalized, the EnsembleBacktestRunner interprets regime outputs based on `output_type`:

```python
# In EnsembleBacktestRunner._interpret_regime_output():
REGIME_NAMES = ["trending_up", "trending_down", "ranging", "volatile"]

def _interpret_regime_output(self, decision: dict) -> dict[str, float]:
    """Convert N-class DecisionFunction output to regime probabilities.

    DecisionFunction returns {"probabilities": {"TRENDING_UP": 0.65, ...}, ...}
    after M7 Task 7.3 generalizes it to N-class with regime class names.
    """
    nn_probs: dict[str, float] = decision.get("probabilities", {})
    return {name: float(nn_probs.get(name.upper(), 0.0)) for name in REGIME_NAMES}
```

---

## 4. Data Flow

### 4.1 Training Flow (Regime Classifier)

```
OHLCV Data (EURUSD 1h, 2019-2024)
  │
  ├── Feature Path (current information — Researcher decides what goes here):
  │   IndicatorEngine.compute(indicators from strategy YAML)
  │     → DataFrame with indicator columns
  │   FuzzyEngine.fuzzify(fuzzy sets from strategy YAML)
  │     → DataFrame with fuzzy membership columns (0-1)
  │   FuzzyNeuralProcessor.prepare_input()
  │     → Tensor[n_samples, n_features]  (X)
  │
  └── Label Path (future information — crystal ball):
      RegimeLabeler.generate_labels(price_data, horizon=24)
        → compute_signed_efficiency_ratio(close, 24)
        → compute_realized_volatility_ratio(close, 24, 120)
        → classify: TRENDING_UP(0) / TRENDING_DOWN(1) / RANGING(2) / VOLATILE(3)
        → Tensor[n_samples]  (y)

  MLPTradingModel.train(X, y, loss=CrossEntropy, num_classes=4)
    → Trained regime classifier
  Save as ModelBundle (model.pt + metadata_v3.json with output_type="regime_classification")
```

### 4.2 Training Flow (Per-Regime Signal Model)

```
Same as existing training pipeline — no changes.
Signal models are standard v3 strategies trained with zigzag or forward_return labels.
The Researcher generates different signal strategies optimized for each regime.

Example: trend_follower_long_v1 might use:
  - Momentum indicators (RSI, MACD)
  - Longer horizon labels (forward_return with H=40 for longer hold times)
  - Lower confidence threshold (ride the trend)

Example: range_trader_v1 might use:
  - Mean-reversion indicators (Bollinger Bands, Stochastic)
  - Shorter horizon labels (forward_return with H=10 for faster trades)
  - Higher confidence threshold (tighter discipline in ranges)
```

### 4.3 Ensemble Backtest Flow

```
Load EnsembleConfiguration (ensemble YAML)
  │
  ├── Load ModelBundle for each model in config
  │     regime:         regime_model, regime_features, regime_fn
  │     trend_long:     trend_long_model, trend_long_features, trend_long_fn
  │     trend_short:    trend_short_model, ...
  │     mean_reversion: mean_rev_model, ...
  │
  ├── Load OHLCV data for backtest period
  │
  ├── Create FeatureCache per model (each has different indicators/fuzzy sets)
  │     regime_cache, trend_long_cache, trend_short_cache, mean_rev_cache
  │
  └── Create RegimeRouter(composition_config)

  previous_regime = None

  For each bar t:
    ┌─ regime_features = regime_cache.get(t)
    ├─ regime_decision = regime_fn(regime_features, position, bar)
    ├─ regime_probs = {trending_up: 0.65, trending_down: 0.10, ranging: 0.20, volatile: 0.05}
    │
    ├─ route = router.route(regime_probs, previous_regime, position)
    │    → RouteDecision(regime="trending_up", model="trend_long", transition=None)
    │
    ├─ IF route.transition and route.transition.close_position:
    │    position_manager.execute_trade(close_signal, bar)
    │
    ├─ IF route.active_model:
    │    signal_features = feature_caches[route.active_model].get(t)
    │    signal_decision = decision_functions[route.active_model](signal_features, position, bar)
    │    → TradingDecision
    │  ELSE:
    │    → TradingDecision(HOLD, reasoning="volatile → FLAT")
    │
    ├─ position_manager.process_decision(final_decision, bar)
    └─ previous_regime = route.active_regime
```

---

## 5. State Management

### Regime State
- **Previous regime tracked per-bar** by EnsembleBacktestRunner (not the router itself)
- Router compares current vs. previous to detect transitions
- No regime duration tracking — regime is re-evaluated every bar from current features

### Position State During Regime Transitions
- **`close_and_switch` (default):** Close the outgoing model's position at current bar's close price, then the incoming model starts fresh (FLAT) on the next bar.
- **`let_run`:** Don't close existing position. Incoming model takes over position management but may exit on its own terms. Risk: the incoming model's logic may not understand the position the outgoing model opened.
- **`tighten_stops` (future):** Keep position but apply tighter exit criteria. Requires stop-loss infrastructure not yet built.

### Ensemble State
- EnsembleBacktestRunner owns one PositionManager (shared across all regime-routed models)
- Each model has its own FeatureCache and DecisionFunction (independent)
- The router tracks previous_regime to detect transitions
- Only one signal model is "active" at a time (determined by current regime)

---

## 6. Error Handling

| Error | Handling |
|-------|----------|
| Regime model fails to load | Fail fast — ensemble can't run without router |
| Signal model fails to load | Fail fast — missing model for a route is invalid |
| Signal model missing for a regime rule | Validation error at ensemble config load time |
| Feature cache miss (timestamp not found) | Skip bar, log warning (same as existing backtest) |
| Regime output has no class above threshold | Default to most conservative route (volatile → FLAT) |
| Multiple signal models need same OHLCV data | FeatureCaches share underlying data, compute different indicators |
| NaN in regime features | DecisionFunction returns HOLD with low confidence (existing behavior) |
| Regime flickers rapidly (A→B→A→B) | Each transition triggers close — cost accumulates. The regime model's persistence quality directly controls this. Detected in M1 label analysis. |

---

## 7. Validation Scenarios

### Scenario 1: Regime labels are meaningful
**Trace:** Generate labels for EURUSD 1h 2019-2024 → Check 4-class distribution isn't dominated by one class (>60%) → Check mean regime duration > 24h → Check return distributions differ by regime (e.g., trending_up has positive mean return) → Check transition frequency isn't excessive (<3 transitions/day average).
**Gap found:** If volatility threshold is too high, VOLATILE class may be <5% of labels. **Decision:** M1 tunes thresholds empirically. Report label quality metrics.

### Scenario 2: Regime model predicts better than majority-class baseline
**Trace:** Train 4-class classifier → Evaluate on held-out 2024 data → Compare accuracy vs. always-predicting-most-common-class. 4-class random baseline = 25%.
**Gap found:** Class imbalance may cause model to ignore minority classes (volatile, trending_down). **Decision:** Use class-weighted cross-entropy loss.

### Scenario 3: Per-regime signal models trade differently
**Trace:** Train trend_long and mean_reversion models → Backtest each individually → Verify they exhibit different trading patterns (hold duration, trade frequency, signal distribution).
**No gap if models use different strategies.** If the Researcher generates meaningfully different strategies for each regime, they will naturally trade differently.

### Scenario 4: Regime transition closes position correctly
**Trace:** Position opened by trend_long during trending_up → regime transitions to ranging → router triggers close_and_switch → position closed at current bar close → mean_reversion model starts fresh from FLAT.
**Edge case:** What if the transition close is at a loss? That's the cost of regime routing. Track "transition cost" metric.

### Scenario 5: Multiple models need different features
**Trace:** Regime model uses ATR, ADX, BB width. Trend_long uses RSI, MACD. Mean_reversion uses Stochastic, BB. Each has own FeatureCache computing independently from same OHLCV data.
**No gap:** FeatureCache already supports arbitrary strategy configs. One cache per model.

### Scenario 6: Adding a third brain region later
**Trace:** Add `context` model (multi-TF daily trend) → feeds into routing alongside regime. Now routing needs two inputs: regime state + daily trend context.
**Gap found:** Current `regime_route` only supports one gate model. For multi-gate composition, we'd need a DAG or priority chain. **Decision:** Defer. For now, regime is the only gate. Adding a second gate is a separate design when Thread 2 (multi-TF) is ready.

### Scenario 7: Volatile regime flicker
**Trace:** Bar 100: trending_up. Bar 101: volatile (barely above threshold). Bar 102: trending_up. Close-and-switch fires twice in 2 bars. Cost: 2 round-trip commissions for no reason.
**Decision:** The router should implement a **regime stability filter**: require N consecutive bars of new regime before transitioning (configurable, default N=3). Prevents costly flickers.

---

## 8. Milestone Structure

### M1: Regime Labeling & Validation (no ML)
- Build RegimeLabeler (signed ER + RV, 4 classes)
- Build RegimeLabelStats analysis
- CLI command: `ktrdr regime analyze EURUSD 1h --start-date ... --end-date ...`
- Generate and validate labels for EURUSD 1h 2019-2024
- Report: distribution, persistence, return-by-regime, transition frequency
- **Proves:** Regimes exist and are meaningful in the data
- **Proves:** Transition frequency is manageable for close-and-switch routing

### M2: Regime Classifier Training
- Wire `labels.source: regime` into training pipeline (4-class cross-entropy)
- Add `output_type` tag to ModelMetadata
- Train regime classifier on EURUSD 1h (Researcher generates the strategy YAML)
- Evaluate: accuracy vs. 25% random baseline, confusion matrix, prediction persistence
- **Proves:** Current indicators contain information about forward regime state

### M3: Ensemble Architecture
- Build EnsembleConfiguration (config format + loader + validator)
- Build EnsembleBacktestRunner (multi-model orchestration)
- Build RegimeRouter (routing logic + transition handling + stability filter)
- Wire ensemble backtest into CLI and worker
- **Proves:** Multi-model routing works end-to-end

### M4: Full Regime-Routed Backtesting
- Train per-regime signal models (Researcher generates strategies for each regime)
- Run full ensemble backtest: regime classifier + per-regime signal models
- Compare vs. single unrouted signal model
- Report: regime accuracy, transition costs, per-regime performance, overall improvement
- **Proves:** Regime routing improves risk-adjusted returns (or identifies why not)

### M5: Agent Integration
- Researcher agent generates regime strategies, per-regime signal strategies, and ensemble configs
- Assessment workflow evaluates regime quality + per-regime signal quality + ensemble effectiveness
- Researcher can iterate independently on regime classifier vs. signal models
- **Proves:** System is operationally ready for iterative regime research
