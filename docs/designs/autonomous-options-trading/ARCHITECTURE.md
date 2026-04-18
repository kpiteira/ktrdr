# ktrdr Autonomous Options Trading System — Architecture Document

> **Author**: Claude (Opus 4.6), commissioned by Karl Piteira
> **Date**: 2026-04-18
> **Status**: Architecture — ready for implementation
> **Based on**: DESIGN.md (approved), KTRDR_REALITY_MAP.md, Kronos spec (spec.md)

---

## 1. System Diagram (Detailed)

### Deployment Topology

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  Lux Process (Python 3.12, long-running)                                        │
│                                                                                 │
│  ┌──────────────────┐   ┌────────────────────┐   ┌─────────────────────┐       │
│  │ LuxOrchestrator   │──>│ KtrdrSignalClient  │──>│ ktrdr REST API      │       │
│  │ (main loop)       │   │ (HTTP client)      │   │ (separate process)  │       │
│  │                   │   │                    │   │ localhost:8000      │       │
│  │                   │   │ POST /api/v1/      │   │                     │       │
│  │                   │   │ models/predict     │   │ Returns:            │       │
│  │                   │   │                    │<──│ PredictionResponse  │       │
│  │                   │   │ KtrdrSignal        │   │ + probabilities     │       │
│  │                   │   └────────────────────┘   └─────────────────────┘       │
│  │                   │                                                          │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │──>│ KronosVolClassifier │   │ Kronos-mini (4.1M)  │       │
│  │                   │   │ (in-process)       │──>│ Frozen weights      │       │
│  │                   │   │                    │   │ + Linear(256->3)    │       │
│  │                   │   │ VolRegimeSignal    │<──│ Trained head        │       │
│  │                   │   └────────────────────┘   └─────────────────────┘       │
│  │                   │                                                          │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │──>│ OptionsDataProvider │──>│ yfinance (backtest) │       │
│  │                   │   │                    │   │ IBKR MCP (live)     │       │
│  │                   │   │ OptionsChain,      │   └─────────────────────┘       │
│  │                   │   │ IVData             │                                 │
│  │                   │   └────────────────────┘                                 │
│  │                   │                                                          │
│  │                   │   ┌────────────────────┐                                 │
│  │                   │──>│ SignalAggregator   │                                 │
│  │                   │   │                    │                                 │
│  │                   │   │ DecisionInput      │                                 │
│  │                   │   └────────┬───────────┘                                 │
│  │                   │            │                                              │
│  │                   │            v                                              │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │   │ OpusStrategyAdvisor│──>│ Anthropic API       │       │
│  │                   │   │                    │   │ Opus 4.7            │       │
│  │                   │   │ TradeRecommendation│<──│ Extended thinking   │       │
│  │                   │   │                    │   └─────────────────────┘       │
│  │                   │   │ Fallback:          │                                 │
│  │                   │   │ OptionsDecisionMat.│                                 │
│  │                   │   └────────┬───────────┘                                 │
│  │                   │            │                                              │
│  │                   │            v                                              │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │──>│ OptionsPosition    │──>│ SQLite              │       │
│  │                   │   │ Manager            │   │ positions, trades,  │       │
│  │                   │   │                    │   │ signals             │       │
│  │                   │   └────────┬───────────┘   └─────────────────────┘       │
│  │                   │            │                                              │
│  │                   │            v                                              │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │   │ Execution          │──>│ IBKR MCP (paper)    │       │
│  │                   │   │                    │   │ IBKR MCP (live)     │       │
│  │                   │   └────────────────────┘   └─────────────────────┘       │
│  │                   │                                                          │
│  │                   │   ┌────────────────────┐   ┌─────────────────────┐       │
│  │                   │──>│ Telegram Reporter  │──>│ Telegram Bot API    │       │
│  │                   │   └────────────────────┘   └─────────────────────┘       │
│  └──────────────────┘                                                           │
│                                                                                 │
│  ┌──────────────────────────────────────────────────────────────────────────┐   │
│  │ OptionsBacktestEngine (batch job, not long-running)                      │   │
│  │                                                                          │   │
│  │  Imports from ktrdr (in-process, library usage):                         │   │
│  │    DecisionFunction, ModelBundle, IndicatorEngine, FuzzyEngine,          │   │
│  │    FuzzyNeuralProcessor                                                  │   │
│  │                                                                          │   │
│  │  ┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐       │   │
│  │  │ BlackScholes     │  │ OptionsDecision  │  │ OptionsPosition   │       │   │
│  │  │ Engine           │  │ Matrix           │  │ Manager           │       │   │
│  │  └─────────────────┘  └──────────────────┘  └───────────────────┘       │   │
│  │                                                                          │   │
│  │  Output: SQLite (backtest_runs, backtest_trades)                         │   │
│  └──────────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────┐
│  ktrdr Process (separate, persistent, localhost:8000)                            │
│                                                                                 │
│  FastAPI server with loaded model(s)                                            │
│  POST /api/v1/models/predict  ->  PredictionResponse (with probabilities)       │
│                                                                                 │
│  Internal pipeline:                                                             │
│    OHLCV -> IndicatorEngine -> FuzzyEngine -> FuzzyNeuralProcessor              │
│         -> NeuralModel.predict() -> DecisionOrchestrator -> response            │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Data Type Flow

```
OHLCV (pd.DataFrame)
    │
    ├──[KtrdrSignalClient]──HTTP POST──> ktrdr REST API
    │                                         │
    │                              PredictionResponse (JSON)
    │                                         │
    │                              KtrdrSignal (dataclass)
    │                                         │
    ├──[KronosVolClassifier]──torch.Tensor──> Kronos-mini
    │                                         │
    │                              VolRegimeSignal (dataclass)
    │                                         │
    ├──[OptionsDataProvider]──HTTP──> yfinance / IBKR
    │                                         │
    │                              OptionsChain (dataclass)
    │                              IVData (dataclass)
    │                                         │
    └──[SignalAggregator]──────────> DecisionInput (dataclass, JSON-serializable)
                                              │
                                   ┌──────────┴──────────┐
                                   │                     │
                          [OpusStrategyAdvisor]   [OptionsDecisionMatrix]
                           (live/paper)           (backtest / fallback)
                                   │                     │
                                   └──────────┬──────────┘
                                              │
                                   TradeRecommendation (dataclass)
                                              │
                                   [OptionsPositionManager]
                                              │
                                   OptionsPosition (dataclass) ──> SQLite
```

---

## 2. Component Specifications

### A. KronosVolClassifier

**File**: `ktrdr_options/signals/kronos_classifier.py`

```python
from dataclasses import dataclass
from typing import Optional
import torch
import torch.nn as nn
import pandas as pd

@dataclass
class VolRegimeSignal:
    regime: str                    # "SELL_VOL" | "BUY_VOL" | "NEUTRAL"
    confidence: float              # max probability (0.0-1.0)
    probabilities: dict[str, float]  # {"SELL_VOL": float, "BUY_VOL": float, "NEUTRAL": float}
    iv_rank: float                 # current IV rank (0-100)
    timestamp: str                 # ISO 8601

REGIME_LABELS: dict[int, str] = {0: "NEUTRAL", 1: "SELL_VOL", 2: "BUY_VOL"}

class KronosVolClassifier:
    """
    Loads frozen Kronos-mini transformer, extracts hidden states,
    and classifies vol regime via a trained linear head.
    """

    def __init__(
        self,
        kronos_model_name: str = "NeoQuasar/Kronos-mini",
        tokenizer_name: str = "NeoQuasar/Kronos-Tokenizer-2k",
        classifier_weights_path: Optional[str] = None,
        device: str = "cpu",
        embedding_dim: int = 256,
        num_classes: int = 3,
        pooling: str = "last",  # "last" | "mean"
    ) -> None: ...

    # --- Public Methods ---

    def load_model(self) -> None:
        """
        Load Kronos-mini and tokenizer from HuggingFace.
        Freeze all Kronos parameters. Load classifier head weights
        from classifier_weights_path if provided.
        Raises RuntimeError if model weights cannot be loaded.
        """
        ...

    def predict(
        self,
        ohlcv: pd.DataFrame,
        iv_rank: float,
        timestamp: Optional[str] = None,
    ) -> VolRegimeSignal:
        """
        Run Kronos forward pass on OHLCV data, extract embedding,
        classify vol regime via linear head.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume].
                   Must have at least 50 rows. Uses last 512 rows if longer.
            iv_rank: Current IV rank (0-100), included in output for context.
            timestamp: ISO 8601 timestamp. Defaults to now.

        Returns:
            VolRegimeSignal with regime, confidence, probabilities, iv_rank.
        """
        ...

    def extract_embedding(self, ohlcv: pd.DataFrame) -> torch.Tensor:
        """
        Extract Kronos hidden state embedding from OHLCV data.

        Args:
            ohlcv: DataFrame with columns [open, high, low, close, volume].

        Returns:
            Tensor of shape (1, embedding_dim). Pooled according to self.pooling.
        """
        ...

    def extract_embeddings_batched(
        self,
        ohlcv: pd.DataFrame,
        window_size: int = 512,
        stride: int = 1,
    ) -> torch.Tensor:
        """
        Sliding-window embedding extraction for training/caching.

        Args:
            ohlcv: Full historical OHLCV DataFrame.
            window_size: Number of bars per window.
            stride: Step between windows.

        Returns:
            Tensor of shape (num_windows, embedding_dim).
        """
        ...

    def train_classifier(
        self,
        embeddings: torch.Tensor,
        labels: torch.Tensor,
        val_embeddings: torch.Tensor,
        val_labels: torch.Tensor,
        epochs: int = 100,
        lr: float = 0.001,
        class_weights: Optional[torch.Tensor] = None,
    ) -> dict[str, float]:
        """
        Train the linear classifier head on pre-computed embeddings.

        Args:
            embeddings: (N, embedding_dim) tensor of Kronos embeddings.
            labels: (N,) tensor of integer labels (0=NEUTRAL, 1=SELL_VOL, 2=BUY_VOL).
            val_embeddings: Validation embeddings.
            val_labels: Validation labels.
            epochs: Max training epochs.
            lr: Learning rate.
            class_weights: Optional tensor for weighted cross-entropy.

        Returns:
            Dict with keys: "train_loss", "val_loss", "val_auc", "val_accuracy",
            "per_class_precision", "per_class_recall".
        """
        ...

    def save_classifier(self, path: str) -> None:
        """Save classifier head weights and config to path."""
        ...

    def load_classifier(self, path: str) -> None:
        """Load classifier head weights from path."""
        ...

    # --- Internal State ---
    # self._kronos_model: Kronos (frozen)
    # self._tokenizer: KronosTokenizer
    # self._classifier: nn.Linear(embedding_dim, num_classes)
    # self._device: str
    # self._pooling: str ("last" | "mean")
    # self._embedding_dim: int
    # self._is_loaded: bool
```

### B. KtrdrSignalClient

**File**: `ktrdr_options/signals/ktrdr_client.py`

```python
import httpx
from dataclasses import dataclass

@dataclass
class KtrdrSignal:
    signal: str                        # "BUY" | "SELL" | "HOLD"
    confidence: float                  # max probability (0.0-1.0)
    signal_strength: float             # 0.0-1.0
    probabilities: dict[str, float]    # {"BUY": float, "HOLD": float, "SELL": float}
    model_name: str
    symbol: str
    timeframe: str
    test_date: str                     # ISO 8601
    input_features: dict[str, float]   # fuzzy feature values

class KtrdrSignalClient:
    """
    HTTP client for ktrdr REST API.
    Calls POST /api/v1/models/predict and returns extended KtrdrSignal.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout_seconds: float = 30.0,
        max_retries: int = 3,
        retry_backoff_base: float = 2.0,
    ) -> None: ...

    async def predict(
        self,
        model_name: str,
        symbol: str,
        timeframe: str = "1h",
        test_date: str | None = None,
    ) -> KtrdrSignal:
        """
        Call ktrdr prediction endpoint with retries.

        Args:
            model_name: Trained model name (e.g., "trend_tb_lstm_signal_v1").
            symbol: Ticker symbol (e.g., "SPY").
            timeframe: Bar timeframe (e.g., "1h", "1d").
            test_date: Optional ISO 8601 datetime. Defaults to latest bar.

        Returns:
            KtrdrSignal with full probability distribution.

        Raises:
            KtrdrAPIError: After max_retries exhausted.
            KtrdrStaleDataError: If response test_date is >2 bars behind current time.
        """
        ...

    async def health_check(self) -> bool:
        """Check if ktrdr server is reachable. Returns True/False."""
        ...

    # --- Internal State ---
    # self._client: httpx.AsyncClient
    # self._base_url: str
    # self._max_retries: int
    # self._retry_backoff_base: float
```

### C. OptionsDataProvider

**File**: `ktrdr_options/data/options_data.py`

```python
from dataclasses import dataclass, field
import pandas as pd

@dataclass
class OptionContract:
    strike: float
    expiry: str              # ISO 8601 date
    option_type: str         # "CALL" | "PUT"
    bid: float
    ask: float
    iv: float                # implied volatility (annualized, decimal)
    delta: float
    gamma: float
    theta: float
    vega: float
    open_interest: int
    volume: int

@dataclass
class OptionsChain:
    symbol: str
    underlying_price: float
    timestamp: str           # ISO 8601
    expiries: list[str]      # available expiry dates
    contracts: list[OptionContract]

@dataclass
class IVData:
    current_iv: float        # annualized, decimal (e.g., 0.22)
    iv_rank: float           # 0-100
    iv_percentile: float     # 0-100
    iv_history: pd.Series    # trailing 252-day IV series
    vix: float               # current VIX level
    rv_20d: float            # 20-day realized vol (annualized, decimal)

class OptionsDataProvider:
    """
    Fetches options chain data and IV context.
    Uses yfinance for backtesting / free path.
    Uses IBKR MCP for paper/live trading.
    """

    def __init__(
        self,
        mode: str = "backtest",  # "backtest" | "paper" | "live"
        ibkr_config: dict | None = None,
    ) -> None: ...

    async def get_options_chain(
        self,
        symbol: str,
        min_dte: int = 14,
        max_dte: int = 60,
        min_delta: float = 0.10,
        max_delta: float = 0.50,
    ) -> OptionsChain:
        """
        Fetch current options chain filtered by DTE and delta range.

        Args:
            symbol: Underlying ticker.
            min_dte: Minimum days to expiry.
            max_dte: Maximum days to expiry.
            min_delta: Minimum absolute delta.
            max_delta: Maximum absolute delta.

        Returns:
            OptionsChain with filtered contracts.

        Raises:
            OptionsDataError: If data source unavailable.
        """
        ...

    async def get_iv_data(
        self,
        symbol: str,
        as_of: str | None = None,
    ) -> IVData:
        """
        Compute IV rank and related vol context for symbol.

        Args:
            symbol: Ticker symbol.
            as_of: Date for historical lookback (ISO 8601). Defaults to today.

        Returns:
            IVData with iv_rank, current_iv, rv_20d, vix.
        """
        ...

    def compute_iv_rank(
        self,
        iv_current: float,
        iv_history_252d: pd.Series,
    ) -> float:
        """
        IV Rank = (current - 252d low) / (252d high - 252d low) * 100.
        Returns 50.0 if high == low (no range).
        """
        ...

    def compute_realized_vol(
        self,
        prices: pd.Series,
        window: int = 20,
    ) -> float:
        """
        Annualized realized volatility from close prices.
        = rolling std(log returns) * sqrt(252)
        """
        ...

    async def get_vix_history(
        self,
        start: str,
        end: str,
    ) -> pd.Series:
        """
        Fetch VIX daily close from yfinance.
        Returns pd.Series with DatetimeIndex.
        """
        ...

    async def get_risk_free_rate(self, as_of: str | None = None) -> float:
        """
        Fetch 3-month Treasury bill rate from FRED.
        Returns annualized rate as decimal (e.g., 0.05 for 5%).
        """
        ...

    # --- Internal State ---
    # self._mode: str
    # self._vix_cache: pd.Series | None
    # self._rate_cache: dict[str, float]
```

### D. SignalAggregator

**File**: `ktrdr_options/signals/aggregator.py`

```python
from dataclasses import dataclass

@dataclass
class DecisionInput:
    """Complete structured input for Opus 4.7 or OptionsDecisionMatrix."""

    # Metadata
    timestamp: str           # ISO 8601
    symbol: str

    # Underlying
    current_price: float
    price_change_1d: float
    price_change_5d: float

    # ktrdr signal
    ktrdr_signal: str        # "BUY" | "SELL" | "HOLD"
    ktrdr_confidence: float
    ktrdr_probabilities: dict[str, float]
    ktrdr_model_name: str
    ktrdr_timeframe: str

    # Kronos regime
    kronos_regime: str       # "SELL_VOL" | "BUY_VOL" | "NEUTRAL"
    kronos_confidence: float
    kronos_probabilities: dict[str, float]

    # Vol context
    iv_rank: float           # 0-100
    current_iv: float        # annualized decimal
    vix: float
    rv_20d: float            # annualized decimal

    # Options chain (for live/paper)
    options_chain: dict | None = None  # serialized OptionsChain

    # Portfolio state
    account_value: float = 100_000.0
    buying_power: float = 100_000.0
    open_positions_count: int = 0
    max_risk_per_trade: float = 2_000.0

    # Decision matrix pre-computation
    matrix_suggestion: str | None = None  # suggested structure name
    matrix_reasoning: str | None = None

    def to_dict(self) -> dict:
        """JSON-serializable dict for Opus 4.7 prompt or logging."""
        ...

    def to_json(self) -> str:
        """JSON string representation."""
        ...


class SignalAggregator:
    """
    Combines ktrdr directional signal + Kronos vol regime + options context
    into a unified DecisionInput for downstream decision-making.
    """

    def __init__(
        self,
        account_value: float = 100_000.0,
        max_risk_pct: float = 0.02,
    ) -> None: ...

    def aggregate(
        self,
        ktrdr_signal: "KtrdrSignal",
        kronos_regime: "VolRegimeSignal",
        iv_data: "IVData",
        current_price: float,
        price_history_5d: list[float] | None = None,
        options_chain: "OptionsChain | None" = None,
        portfolio_state: dict | None = None,
    ) -> DecisionInput:
        """
        Combine all signal sources into a single DecisionInput.

        Computes:
        - price_change_1d, price_change_5d from price_history_5d
        - max_risk_per_trade = account_value * max_risk_pct * position_size_multiplier
        - matrix_suggestion via OptionsDecisionMatrix.suggest()

        Args:
            ktrdr_signal: KtrdrSignal from KtrdrSignalClient.
            kronos_regime: VolRegimeSignal from KronosVolClassifier.
            iv_data: IVData from OptionsDataProvider.
            current_price: Current underlying price.
            price_history_5d: Last 5 daily closes for computing changes.
            options_chain: OptionsChain for live/paper mode.
            portfolio_state: Dict with account_value, buying_power, open_positions.

        Returns:
            DecisionInput ready for OpusStrategyAdvisor or OptionsDecisionMatrix.
        """
        ...

    def compute_position_size_multiplier(
        self,
        max_probability: float,
        probability_spread: float,
    ) -> float:
        """
        Compute position size multiplier from ktrdr probability distribution.

        probability_spread < 0.10 -> 0.5
        probability_spread < 0.25 -> 0.75
        else -> 1.0

        Returns: 0.5, 0.75, or 1.0
        """
        ...

    # --- Internal State ---
    # self._account_value: float
    # self._max_risk_pct: float
    # self._decision_matrix: OptionsDecisionMatrix (for pre-computing suggestion)
```

### E. OptionsDecisionMatrix

**File**: `ktrdr_options/strategy/decision_matrix.py`

```python
from dataclasses import dataclass
from enum import Enum

class StructureType(Enum):
    BULL_PUT_SPREAD = "bull_put_spread"
    IRON_CONDOR = "iron_condor"
    BULL_CALL_SPREAD = "bull_call_spread"
    BEAR_CALL_SPREAD = "bear_call_spread"
    LONG_CALL = "long_call"
    LONG_STRADDLE = "long_straddle"
    BEAR_PUT_SPREAD = "bear_put_spread"
    LONG_PUT = "long_put"
    NO_TRADE = "no_trade"

@dataclass
class StructureChoice:
    structure: StructureType
    reasoning: str
    confidence_gate_passed: bool
    target_dte_min: int          # minimum DTE for this structure
    target_dte_max: int          # maximum DTE for this structure
    target_short_delta: float | None   # for credit spreads
    target_long_delta: float | None    # for debit spreads / naked longs
    spread_width_strikes: int | None   # number of strikes wide

class OptionsDecisionMatrix:
    """
    Deterministic mapping: (ktrdr_signal, kronos_regime, iv_rank) -> StructureChoice.
    Used in backtesting (no Opus 4.7 call) and as fallback in live trading.
    """

    def __init__(
        self,
        min_ktrdr_confidence: float = 0.45,
        min_ktrdr_confidence_naked: float = 0.65,
        min_kronos_confidence_vol: float = 0.70,
        min_kronos_confidence_other: float = 0.50,
    ) -> None: ...

    def select(self, decision_input: "DecisionInput") -> StructureChoice:
        """
        Apply the decision matrix to produce a structure selection.

        Matrix:
                          SELL_VOL          NEUTRAL           BUY_VOL
            BUY      Bull Put Spread   Bull Call Spread    Long Call
            HOLD     Iron Condor       No Trade            Long Straddle
            SELL     Bear Call Spread   Bear Put Spread     Long Put

        Applies confidence gates:
        - ktrdr max_probability >= min_ktrdr_confidence (all trades)
        - ktrdr max_probability >= min_ktrdr_confidence_naked (long call/put)
        - kronos confidence >= min_kronos_confidence_vol (iron condor, straddle)
        - kronos confidence >= min_kronos_confidence_other (all other)

        Returns NO_TRADE if gates fail.

        Args:
            decision_input: DecisionInput from SignalAggregator.

        Returns:
            StructureChoice with selected structure and parameters.
        """
        ...

    def suggest(
        self,
        ktrdr_signal: str,
        kronos_regime: str,
    ) -> tuple[str, str]:
        """
        Quick lookup for matrix suggestion (structure name, reasoning).
        Used by SignalAggregator for pre-populating DecisionInput.
        Does NOT apply confidence gates.

        Returns:
            (structure_name, reasoning_text)
        """
        ...

    # --- Internal State ---
    # self._matrix: dict[tuple[str, str], StructureType]  # (signal, regime) -> structure
    # self._structure_params: dict[StructureType, dict]    # DTE, delta, width defaults
    # self._confidence_thresholds: dict[str, float]
```

### F. OpusStrategyAdvisor

**File**: `ktrdr_options/strategy/opus_advisor.py`

```python
from dataclasses import dataclass

@dataclass
class OptionsLeg:
    action: str              # "BUY" | "SELL"
    option_type: str         # "CALL" | "PUT"
    strike: float
    expiry: str              # ISO 8601 date
    contracts: int
    estimated_price: float   # per-contract price

@dataclass
class ExitPlan:
    take_profit_pct: float   # e.g., 50.0 = close at 50% of max profit
    stop_loss_pct: float     # e.g., 100.0 = close at max loss
    time_exit_dte: int       # close when DTE falls below this
    signal_reversal_exit: bool = True  # exit on ktrdr signal flip

@dataclass
class TradeRecommendation:
    action: str              # "OPEN" | "CLOSE" | "ADJUST" | "HOLD"
    structure: str           # StructureType value string
    legs: list[OptionsLeg]
    expected_credit: float | None    # net credit for credit spreads
    expected_debit: float | None     # net debit for debit spreads
    max_risk: float          # max loss in dollars
    max_profit: float        # max profit in dollars
    breakeven: float | list[float]   # breakeven price(s)
    exit_plan: ExitPlan
    reasoning: str           # human-readable explanation
    confidence: str          # "HIGH" | "MEDIUM" | "LOW"
    warnings: list[str]
    source: str              # "opus" | "matrix"  (was Opus used or fallback?)

class OpusStrategyAdvisor:
    """
    Calls Opus 4.7 via Anthropic API with structured prompt.
    Validates output against risk limits and allowed structures.
    Falls back to OptionsDecisionMatrix on failure.
    """

    ALLOWED_STRUCTURES: set[str] = {
        "bull_put_spread", "iron_condor", "bull_call_spread",
        "bear_call_spread", "long_call", "long_straddle",
        "bear_put_spread", "long_put",
    }

    def __init__(
        self,
        anthropic_api_key: str,
        model: str = "claude-opus-4-7-20260401",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        fallback_matrix: "OptionsDecisionMatrix | None" = None,
    ) -> None: ...

    async def advise(
        self,
        decision_input: "DecisionInput",
    ) -> TradeRecommendation:
        """
        Send structured prompt to Opus 4.7, parse and validate response.

        Flow:
        1. Build structured JSON prompt from DecisionInput
        2. Call Anthropic API with extended thinking enabled
        3. Parse JSON response
        4. Validate: structure in ALLOWED_STRUCTURES, max_risk <= decision_input.max_risk_per_trade,
           all legs have valid strikes/expiries
        5. If validation fails after max_retries, fall back to OptionsDecisionMatrix

        Args:
            decision_input: Complete DecisionInput from SignalAggregator.

        Returns:
            Validated TradeRecommendation. source="opus" if Opus succeeded,
            source="matrix" if fallback was used.
        """
        ...

    def _build_prompt(self, decision_input: "DecisionInput") -> str:
        """Build the structured JSON prompt for Opus 4.7."""
        ...

    def _parse_response(self, response_text: str) -> TradeRecommendation:
        """
        Parse Opus JSON response into TradeRecommendation.
        Raises ValueError if JSON is malformed or missing required fields.
        """
        ...

    def _validate_recommendation(
        self,
        recommendation: TradeRecommendation,
        decision_input: "DecisionInput",
    ) -> list[str]:
        """
        Validate recommendation against risk limits.
        Returns list of validation errors (empty = valid).

        Checks:
        - structure in ALLOWED_STRUCTURES
        - max_risk <= decision_input.max_risk_per_trade
        - all legs reference valid strikes from options chain
        - contracts > 0
        - expiry in future
        """
        ...

    def _fallback_to_matrix(
        self,
        decision_input: "DecisionInput",
        reason: str,
    ) -> TradeRecommendation:
        """
        Generate TradeRecommendation from OptionsDecisionMatrix.
        source="matrix", reasoning includes fallback reason.
        """
        ...

    # --- Internal State ---
    # self._client: anthropic.AsyncAnthropic
    # self._model: str
    # self._timeout: float
    # self._max_retries: int
    # self._fallback_matrix: OptionsDecisionMatrix
```

### G. BlackScholesEngine

**File**: `ktrdr_options/backtest/black_scholes.py`

```python
from dataclasses import dataclass
import numpy as np

@dataclass
class OptionPrice:
    price: float          # theoretical price
    delta: float
    gamma: float
    theta: float          # per calendar day
    vega: float           # per 1% vol change
    rho: float

class BlackScholesEngine:
    """
    Pure-math Black-Scholes pricing and Greeks computation.
    No external dependencies beyond numpy/scipy.
    """

    def __init__(
        self,
        bid_ask_haircut: float = 0.10,  # 10% flat haircut
    ) -> None: ...

    def price_call(
        self,
        S: float,    # underlying price
        K: float,    # strike
        T: float,    # time to expiry in years
        r: float,    # risk-free rate (annualized, decimal)
        sigma: float,  # implied volatility (annualized, decimal)
    ) -> OptionPrice:
        """
        Black-Scholes call pricing with all Greeks.

        C = S * N(d1) - K * e^(-rT) * N(d2)
        d1 = (ln(S/K) + (r + sigma^2/2) * T) / (sigma * sqrt(T))
        d2 = d1 - sigma * sqrt(T)

        Returns OptionPrice with price, delta, gamma, theta, vega, rho.
        """
        ...

    def price_put(
        self,
        S: float, K: float, T: float, r: float, sigma: float,
    ) -> OptionPrice:
        """
        Black-Scholes put pricing with all Greeks.

        P = K * e^(-rT) * N(-d2) - S * N(-d1)

        Returns OptionPrice with price, delta (negative), gamma, theta, vega, rho.
        """
        ...

    def price_option(
        self,
        S: float, K: float, T: float, r: float, sigma: float,
        option_type: str,  # "CALL" | "PUT"
    ) -> OptionPrice:
        """Dispatch to price_call or price_put."""
        ...

    def find_strike_by_delta(
        self,
        S: float,
        T: float,
        r: float,
        sigma: float,
        target_delta: float,  # e.g., 0.30 for call, -0.30 for put
        option_type: str,
        strike_step: float = 1.0,  # round to nearest strike_step
    ) -> float:
        """
        Find the strike price that produces the target delta.
        Uses Newton's method on the delta function.
        Rounds to nearest strike_step.

        Args:
            target_delta: Positive for calls, negative for puts.
            strike_step: Strike rounding (e.g., 1.0 for SPY, 5.0 for SPX).

        Returns:
            Strike price (float).
        """
        ...

    def apply_haircut(
        self,
        price: float,
        side: str,  # "credit" | "debit"
    ) -> float:
        """
        Apply bid/ask haircut to theoretical price.

        credit: price * (1 - haircut)  # you receive less
        debit:  price * (1 + haircut)  # you pay more

        Returns adjusted price.
        """
        ...

    def price_spread(
        self,
        S: float,
        legs: list["OptionsLeg"],
        T: float,
        r: float,
        sigma: float,
    ) -> dict[str, float]:
        """
        Price a multi-leg structure. Returns:
        {
            "net_price": float,       # positive = credit, negative = debit
            "max_profit": float,
            "max_loss": float,
            "breakeven": float | list[float],
            "net_delta": float,
            "net_gamma": float,
            "net_theta": float,
            "net_vega": float,
        }
        """
        ...

    @staticmethod
    def estimate_iv_from_vix(
        vix: float,
        beta: float = 1.0,
    ) -> float:
        """
        Estimate single-name IV from VIX.
        sigma = VIX / 100 * max(0.8, min(2.0, beta * 0.9 + 0.3))

        Args:
            vix: VIX level (e.g., 22.4)
            beta: Stock beta relative to S&P 500.

        Returns:
            Annualized IV as decimal (e.g., 0.224).
        """
        ...

    # --- Internal State ---
    # self._haircut: float
```

### H. OptionsPosition

**File**: `ktrdr_options/positions/position.py`

```python
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class PositionStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    EXPIRED = "EXPIRED"

@dataclass
class OptionsLeg:
    leg_id: str                    # UUID
    action: str                    # "BUY" | "SELL"
    option_type: str               # "CALL" | "PUT"
    strike: float
    expiry: str                    # ISO 8601 date
    contracts: int
    entry_price: float             # per-contract price at entry
    current_price: float = 0.0     # per-contract price at current mark
    current_delta: float = 0.0
    current_gamma: float = 0.0
    current_theta: float = 0.0
    current_vega: float = 0.0

@dataclass
class OptionsPosition:
    position_id: str               # UUID
    symbol: str
    structure: str                 # StructureType value
    legs: list[OptionsLeg]
    entry_timestamp: str           # ISO 8601
    exit_timestamp: str | None = None

    # Entry metrics
    net_entry_price: float = 0.0   # positive = credit, negative = debit
    max_profit: float = 0.0
    max_loss: float = 0.0
    breakeven: float | list[float] = field(default_factory=list)

    # Current state
    status: PositionStatus = PositionStatus.OPEN
    current_pnl: float = 0.0      # unrealized P&L in dollars
    current_pnl_pct: float = 0.0  # P&L as % of max risk
    dte_remaining: int = 0

    # Portfolio Greeks (net across all legs)
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # Exit plan (from TradeRecommendation)
    take_profit_pct: float = 50.0
    stop_loss_pct: float = 100.0
    time_exit_dte: int = 7
    signal_reversal_exit: bool = True

    # Exit details (filled on close)
    exit_reason: str | None = None
    exit_pnl: float = 0.0

    # Signal context at entry
    ktrdr_signal: str = ""
    kronos_regime: str = ""
    iv_rank_at_entry: float = 0.0
    recommendation_source: str = ""  # "opus" | "matrix"

    def to_dict(self) -> dict:
        """JSON-serializable dict for persistence."""
        ...
```

### I. OptionsPositionManager

**File**: `ktrdr_options/positions/manager.py`

```python
class OptionsPositionManager:
    """
    Creates, tracks, and exits options positions.
    Computes portfolio-level Greeks. Persists to SQLite.
    """

    def __init__(
        self,
        db_path: str = "ktrdr_options.db",
        bs_engine: "BlackScholesEngine | None" = None,
    ) -> None: ...

    def open_position(
        self,
        recommendation: "TradeRecommendation",
        decision_input: "DecisionInput",
    ) -> OptionsPosition:
        """
        Create a new OptionsPosition from a TradeRecommendation.
        Persists to SQLite positions table.

        Args:
            recommendation: Validated TradeRecommendation.
            decision_input: DecisionInput that produced the recommendation.

        Returns:
            New OptionsPosition with OPEN status.
        """
        ...

    def mark_to_market(
        self,
        position: OptionsPosition,
        underlying_price: float,
        current_iv: float,
        risk_free_rate: float,
        current_date: str,
    ) -> OptionsPosition:
        """
        Update position's current prices, Greeks, and P&L using Black-Scholes.

        Updates: current_pnl, current_pnl_pct, net_delta/gamma/theta/vega,
        dte_remaining, and each leg's current_price and Greeks.

        Returns updated OptionsPosition (mutates in place AND returns).
        """
        ...

    def check_exit_conditions(
        self,
        position: OptionsPosition,
        current_ktrdr_signal: str,
    ) -> tuple[bool, str]:
        """
        Check whether position should be closed.

        Exit conditions (in priority order):
        1. DTE < time_exit_dte -> "time_exit"
        2. P&L >= take_profit_pct% of max_profit -> "take_profit"
        3. P&L <= -stop_loss_pct% of max_loss (for credits) or debit lost -> "stop_loss"
        4. ktrdr signal reversed (BUY->SELL or SELL->BUY) and signal_reversal_exit -> "signal_reversal"

        Returns:
            (should_exit: bool, reason: str)
        """
        ...

    def close_position(
        self,
        position: OptionsPosition,
        exit_reason: str,
        exit_timestamp: str,
    ) -> OptionsPosition:
        """
        Close position. Compute final exit_pnl. Update status to CLOSED.
        Record trade in SQLite trades table.

        Returns updated OptionsPosition.
        """
        ...

    def get_open_positions(self) -> list[OptionsPosition]:
        """Return all positions with status OPEN."""
        ...

    def get_portfolio_greeks(self) -> dict[str, float]:
        """
        Compute aggregate Greeks across all open positions.

        Returns:
        {
            "total_delta": float,
            "total_gamma": float,
            "total_theta": float,
            "total_vega": float,
            "total_risk": float,    # sum of max_loss across open positions
            "position_count": int,
        }
        """
        ...

    def get_position_history(
        self,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[OptionsPosition]:
        """Return closed positions, most recent first."""
        ...

    # --- Internal State ---
    # self._db: sqlite3.Connection
    # self._bs_engine: BlackScholesEngine
    # self._open_positions: list[OptionsPosition]  # in-memory cache of open positions
```

### J. OptionsBacktestEngine

**File**: `ktrdr_options/backtest/engine.py`

```python
from dataclasses import dataclass

@dataclass
class OptionsBacktestConfig:
    strategy_config_path: str      # path to ktrdr strategy YAML
    model_path: str                # path to trained ktrdr model directory
    symbol: str
    timeframe: str                 # bar timeframe (e.g., "1h")
    start_date: str                # ISO 8601
    end_date: str                  # ISO 8601
    initial_capital: float = 100_000.0
    max_risk_pct: float = 0.02     # 2% per trade
    bid_ask_haircut: float = 0.10  # 10% B-S haircut
    vix_data_path: str | None = None  # optional cached VIX CSV
    kronos_embeddings_path: str | None = None  # pre-computed .pt file
    kronos_classifier_path: str | None = None  # trained classifier weights
    db_path: str = "backtest_results.db"

@dataclass
class OptionsBacktestTrade:
    trade_id: str                  # UUID
    backtest_run_id: str
    symbol: str
    structure: str
    entry_date: str
    exit_date: str
    entry_price: float             # net credit/debit
    exit_price: float
    pnl: float
    pnl_pct: float                 # P&L as % of max risk
    max_profit: float
    max_loss: float
    exit_reason: str
    ktrdr_signal: str
    kronos_regime: str
    iv_rank: float
    dte_at_entry: int
    legs: list[dict]               # serialized OptionsLeg list

@dataclass
class OptionsBacktestResults:
    run_id: str                    # UUID
    config: OptionsBacktestConfig
    trades: list[OptionsBacktestTrade]

    # Performance metrics
    total_return: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    profit_factor: float
    avg_win_pct: float
    avg_loss_pct: float
    avg_dte_at_entry: float
    avg_holding_period_days: float

    # Options-specific metrics
    avg_theta_collected: float     # avg daily theta on open positions
    avg_delta_exposure: float      # avg net delta
    gamma_risk_events: int         # times gamma > threshold near expiry
    structure_breakdown: dict[str, int]  # trade count per structure type

    # Time series
    equity_curve: list[dict]       # [{date, equity, drawdown}, ...]
    signal_distribution: dict[str, int]  # {"BUY": N, "SELL": N, "HOLD": N}

    execution_time_seconds: float

    def to_dict(self) -> dict:
        """JSON-serializable dict."""
        ...


class OptionsBacktestEngine:
    """
    Drives the synthetic options backtest loop.
    Reuses ktrdr's feature pipeline (DecisionFunction, ModelBundle) for signal generation.
    Uses BlackScholesEngine for option pricing.
    Writes results to SQLite.
    """

    def __init__(self, config: OptionsBacktestConfig) -> None: ...

    def run(self) -> OptionsBacktestResults:
        """
        Execute the full backtest.

        Flow per bar:
        1. Generate ktrdr signal via DecisionFunction (reuses ktrdr feature pipeline)
        2. Look up Kronos vol regime from pre-computed embeddings + classifier
        3. Compute IV rank from VIX history
        4. Apply OptionsDecisionMatrix -> StructureChoice
        5. If structure != NO_TRADE and confidence gates pass:
           a. Select strikes via BlackScholesEngine.find_strike_by_delta()
           b. Compute entry price via BlackScholesEngine.price_spread()
           c. Apply bid/ask haircut
           d. Open position via OptionsPositionManager
        6. For each open position:
           a. Mark to market via BlackScholesEngine
           b. Check exit conditions
           c. Close if triggered
        7. Record equity curve

        Returns:
            OptionsBacktestResults with full metrics and trade log.
        """
        ...

    def _load_ktrdr_pipeline(self) -> None:
        """
        Load ktrdr model and feature pipeline.

        Imports:
            from ktrdr.backtesting.decision_function import DecisionFunction
            from ktrdr.backtesting.model_bundle import ModelBundle
            from ktrdr.indicators.indicator_engine import IndicatorEngine
            from ktrdr.fuzzy.engine import FuzzyEngine
            from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
            from ktrdr.data.local_data_loader import LocalDataLoader
            from ktrdr.config.feature_resolver import FeatureResolver
        """
        ...

    def _load_kronos(self) -> None:
        """Load KronosVolClassifier with pre-computed embeddings if available."""
        ...

    def _load_vix_data(self) -> None:
        """Load VIX history. From file if vix_data_path set, else yfinance."""
        ...

    def _compute_ktrdr_signal(
        self,
        features: dict[str, float],
        position_status: str,
        bar: "pd.Series",
        last_signal_time: "pd.Timestamp | None",
    ) -> "TradingDecision":
        """
        Run ktrdr DecisionFunction for one bar.
        Uses the same interface as ktrdr's BacktestingEngine.
        """
        ...

    def _compute_kronos_regime(
        self,
        bar_index: int,
        iv_rank: float,
        timestamp: str,
    ) -> "VolRegimeSignal":
        """Look up pre-computed Kronos embedding, run classifier."""
        ...

    def _compute_iv_context(
        self,
        timestamp: "pd.Timestamp",
        underlying_price: float,
    ) -> tuple[float, float, float]:
        """
        Compute IV rank, current_iv, rv_20d for the given timestamp.
        Returns (iv_rank, current_iv, rv_20d).
        """
        ...

    def _compute_metrics(
        self,
        trades: list[OptionsBacktestTrade],
        equity_curve: list[dict],
    ) -> dict:
        """Compute all performance metrics from trade list and equity curve."""
        ...

    # --- Internal State ---
    # self._config: OptionsBacktestConfig
    # self._decision_function: DecisionFunction
    # self._model_bundle: ModelBundle
    # self._kronos_classifier: KronosVolClassifier
    # self._decision_matrix: OptionsDecisionMatrix
    # self._bs_engine: BlackScholesEngine
    # self._position_manager: OptionsPositionManager
    # self._vix_history: pd.Series
    # self._kronos_embeddings: torch.Tensor | None
    # self._risk_free_rate: float
```

### K. LuxOrchestrator

**File**: `ktrdr_options/orchestrator.py`

```python
from dataclasses import dataclass

@dataclass
class CycleResult:
    timestamp: str
    ktrdr_signal: "KtrdrSignal | None"
    kronos_regime: "VolRegimeSignal | None"
    recommendation: "TradeRecommendation | None"
    actions_taken: list[str]       # ["opened_position", "closed_position:XYZ", ...]
    errors: list[str]
    cycle_duration_seconds: float

class LuxOrchestrator:
    """
    Main loop for live/paper trading.
    Runs on schedule, coordinates all components, reports via Telegram.
    """

    def __init__(
        self,
        config_path: str = "ktrdr-options-config.yaml",
        mode: str = "paper",  # "paper" | "live"
    ) -> None: ...

    async def run_cycle(self) -> CycleResult:
        """
        Execute one analysis + trading cycle.

        Flow:
        1. Fetch ktrdr signal via KtrdrSignalClient
        2. Run KronosVolClassifier on recent OHLCV
        3. Fetch options chain + IV data via OptionsDataProvider
        4. Aggregate signals via SignalAggregator
        5. Get recommendation via OpusStrategyAdvisor
        6. Mark-to-market all open positions
        7. Check exit conditions on all open positions
        8. Execute exits if triggered
        9. Execute new trade if recommended and risk budget available
        10. Persist state to SQLite
        11. Send Telegram summary

        Returns:
            CycleResult with full audit trail.
        """
        ...

    async def start(self, interval_minutes: int = 60) -> None:
        """Start the main loop on the given interval."""
        ...

    async def stop(self) -> None:
        """Gracefully stop the main loop."""
        ...

    async def run_once(self) -> CycleResult:
        """Run a single cycle (for Telegram on-demand commands)."""
        ...

    async def _execute_trade(
        self,
        recommendation: "TradeRecommendation",
        decision_input: "DecisionInput",
    ) -> str:
        """
        Submit order to IBKR (paper or live).
        In live mode, requires Karl's Telegram approval first.

        Returns:
            Order status string.
        """
        ...

    async def _send_telegram_report(
        self,
        cycle_result: CycleResult,
    ) -> None:
        """Send cycle summary to Karl via Telegram."""
        ...

    def _check_risk_budget(self) -> float:
        """
        Compute remaining risk budget.
        = account_value * max_risk_pct_total - sum(open_position.max_loss)

        Returns available risk in dollars. 0 = no new trades.
        """
        ...

    # --- Internal State ---
    # self._config: dict (loaded from YAML)
    # self._ktrdr_client: KtrdrSignalClient
    # self._kronos_classifier: KronosVolClassifier
    # self._options_data: OptionsDataProvider
    # self._aggregator: SignalAggregator
    # self._opus_advisor: OpusStrategyAdvisor
    # self._position_manager: OptionsPositionManager
    # self._mode: str
    # self._running: bool
```

---

## 3. Data Model Specifications

### VolRegimeSignal

```python
@dataclass
class VolRegimeSignal:
    regime: str                    # "SELL_VOL" | "BUY_VOL" | "NEUTRAL"
    confidence: float              # max probability, range 0.0-1.0
    probabilities: dict[str, float]  # {"SELL_VOL": float, "BUY_VOL": float, "NEUTRAL": float}
    iv_rank: float                 # current IV rank, range 0-100
    timestamp: str                 # ISO 8601 datetime

# Example instantiation:
VolRegimeSignal(
    regime="SELL_VOL",
    confidence=0.68,
    probabilities={"SELL_VOL": 0.68, "BUY_VOL": 0.12, "NEUTRAL": 0.20},
    iv_rank=78.5,
    timestamp="2026-04-18T14:30:00Z",
)

# JSON serialization:
{
    "regime": "SELL_VOL",
    "confidence": 0.68,
    "probabilities": {"SELL_VOL": 0.68, "BUY_VOL": 0.12, "NEUTRAL": 0.20},
    "iv_rank": 78.5,
    "timestamp": "2026-04-18T14:30:00Z"
}
```

### KtrdrSignal

```python
@dataclass
class KtrdrSignal:
    signal: str                        # "BUY" | "SELL" | "HOLD"
    confidence: float                  # max probability, range 0.0-1.0
    signal_strength: float             # range 0.0-1.0
    probabilities: dict[str, float]    # {"BUY": float, "HOLD": float, "SELL": float}
    model_name: str                    # e.g., "trend_tb_lstm_signal_v1"
    symbol: str                        # e.g., "SPY"
    timeframe: str                     # e.g., "1h"
    test_date: str                     # ISO 8601 datetime
    input_features: dict[str, float]   # fuzzy feature snapshot

# Example:
KtrdrSignal(
    signal="BUY",
    confidence=0.756,
    signal_strength=0.694,
    probabilities={"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062},
    model_name="trend_tb_lstm_signal_v1",
    symbol="SPY",
    timeframe="1h",
    test_date="2026-04-18T14:30:00Z",
    input_features={"1h_rsi_momentum_oversold": 0.02, "1h_rsi_momentum_overbought": 0.83},
)

# JSON:
{
    "signal": "BUY",
    "confidence": 0.756,
    "signal_strength": 0.694,
    "probabilities": {"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062},
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "timeframe": "1h",
    "test_date": "2026-04-18T14:30:00Z",
    "input_features": {"1h_rsi_momentum_oversold": 0.02, "1h_rsi_momentum_overbought": 0.83}
}
```

### DecisionInput

```python
@dataclass
class DecisionInput:
    timestamp: str
    symbol: str
    current_price: float
    price_change_1d: float              # % change
    price_change_5d: float              # % change
    ktrdr_signal: str                   # "BUY" | "SELL" | "HOLD"
    ktrdr_confidence: float
    ktrdr_probabilities: dict[str, float]
    ktrdr_model_name: str
    ktrdr_timeframe: str
    kronos_regime: str                  # "SELL_VOL" | "BUY_VOL" | "NEUTRAL"
    kronos_confidence: float
    kronos_probabilities: dict[str, float]
    iv_rank: float                      # 0-100
    current_iv: float                   # annualized decimal
    vix: float
    rv_20d: float                       # annualized decimal
    options_chain: dict | None = None   # serialized OptionsChain for live/paper
    account_value: float = 100_000.0
    buying_power: float = 100_000.0
    open_positions_count: int = 0
    max_risk_per_trade: float = 2_000.0
    matrix_suggestion: str | None = None
    matrix_reasoning: str | None = None
```

### TradeRecommendation

```python
@dataclass
class TradeRecommendation:
    action: str                         # "OPEN" | "CLOSE" | "ADJUST" | "HOLD"
    structure: str                      # StructureType value
    legs: list[OptionsLeg]
    expected_credit: float | None       # positive for credit spreads
    expected_debit: float | None        # positive for debit spreads
    max_risk: float                     # dollars
    max_profit: float                   # dollars
    breakeven: float | list[float]
    exit_plan: ExitPlan
    reasoning: str
    confidence: str                     # "HIGH" | "MEDIUM" | "LOW"
    warnings: list[str]
    source: str                         # "opus" | "matrix"

# Example:
TradeRecommendation(
    action="OPEN",
    structure="bull_put_spread",
    legs=[
        OptionsLeg(action="SELL", option_type="PUT", strike=515.0, expiry="2026-05-16", contracts=2, estimated_price=3.30),
        OptionsLeg(action="BUY", option_type="PUT", strike=510.0, expiry="2026-05-16", contracts=2, estimated_price=1.45),
    ],
    expected_credit=1.85,
    expected_debit=None,
    max_risk=630.0,
    max_profit=370.0,
    breakeven=516.15,
    exit_plan=ExitPlan(take_profit_pct=50.0, stop_loss_pct=100.0, time_exit_dte=7, signal_reversal_exit=True),
    reasoning="IV rank at 78.5 with BUY signal. Selling put spread collects elevated premium.",
    confidence="HIGH",
    warnings=[],
    source="opus",
)
```

### OptionsLeg

```python
@dataclass
class OptionsLeg:
    leg_id: str = ""                   # UUID, assigned on position creation
    action: str = ""                   # "BUY" | "SELL"
    option_type: str = ""              # "CALL" | "PUT"
    strike: float = 0.0
    expiry: str = ""                   # ISO 8601 date
    contracts: int = 0
    entry_price: float = 0.0           # per-contract at entry
    estimated_price: float = 0.0       # per-contract estimated (pre-entry)
    current_price: float = 0.0         # per-contract at current mark
    current_delta: float = 0.0
    current_gamma: float = 0.0
    current_theta: float = 0.0
    current_vega: float = 0.0
```

### OptionsPosition

Full definition in Section 2.H above.

### OptionsBacktestTrade

```python
@dataclass
class OptionsBacktestTrade:
    trade_id: str                      # UUID
    backtest_run_id: str               # FK to backtest_runs
    symbol: str
    structure: str                     # StructureType value
    entry_date: str                    # ISO 8601
    exit_date: str                     # ISO 8601
    entry_price: float                 # net credit (positive) or debit (negative)
    exit_price: float                  # net P&L at exit
    pnl: float                         # dollar P&L
    pnl_pct: float                     # P&L as % of max risk
    max_profit: float
    max_loss: float
    exit_reason: str                   # "take_profit" | "stop_loss" | "time_exit" | "signal_reversal" | "expired"
    ktrdr_signal: str
    kronos_regime: str
    iv_rank: float
    dte_at_entry: int
    legs: list[dict]                   # serialized leg details
```

### OptionsBacktestResults

Full definition in Section 2.J above.

---

## 4. Persistence Schema (SQLite)

### Table: positions

```sql
CREATE TABLE positions (
    position_id     TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    structure       TEXT NOT NULL,     -- StructureType value
    status          TEXT NOT NULL DEFAULT 'OPEN',  -- OPEN | CLOSED | EXPIRED
    entry_timestamp TEXT NOT NULL,     -- ISO 8601
    exit_timestamp  TEXT,

    -- Entry metrics
    net_entry_price REAL NOT NULL,     -- positive=credit, negative=debit
    max_profit      REAL NOT NULL,
    max_loss        REAL NOT NULL,
    breakeven       TEXT NOT NULL,     -- JSON: float or list[float]

    -- Current state (updated on mark-to-market)
    current_pnl     REAL DEFAULT 0.0,
    current_pnl_pct REAL DEFAULT 0.0,
    dte_remaining   INTEGER DEFAULT 0,
    net_delta       REAL DEFAULT 0.0,
    net_gamma       REAL DEFAULT 0.0,
    net_theta       REAL DEFAULT 0.0,
    net_vega        REAL DEFAULT 0.0,

    -- Exit plan
    take_profit_pct REAL DEFAULT 50.0,
    stop_loss_pct   REAL DEFAULT 100.0,
    time_exit_dte   INTEGER DEFAULT 7,
    signal_reversal_exit INTEGER DEFAULT 1,  -- boolean

    -- Exit details
    exit_reason     TEXT,
    exit_pnl        REAL DEFAULT 0.0,

    -- Signal context
    ktrdr_signal    TEXT NOT NULL,
    kronos_regime   TEXT NOT NULL,
    iv_rank_at_entry REAL NOT NULL,
    recommendation_source TEXT NOT NULL,  -- "opus" | "matrix"

    -- Legs (JSON array)
    legs_json       TEXT NOT NULL,     -- JSON serialized list of OptionsLeg

    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_symbol ON positions(symbol);
CREATE INDEX idx_positions_entry_date ON positions(entry_timestamp);
```

### Table: trades

```sql
CREATE TABLE trades (
    trade_id        TEXT PRIMARY KEY,
    position_id     TEXT NOT NULL REFERENCES positions(position_id),
    symbol          TEXT NOT NULL,
    structure       TEXT NOT NULL,
    entry_date      TEXT NOT NULL,
    exit_date       TEXT NOT NULL,
    entry_price     REAL NOT NULL,
    exit_price      REAL NOT NULL,
    pnl             REAL NOT NULL,
    pnl_pct         REAL NOT NULL,
    max_profit      REAL NOT NULL,
    max_loss        REAL NOT NULL,
    exit_reason     TEXT NOT NULL,
    ktrdr_signal    TEXT NOT NULL,
    kronos_regime   TEXT NOT NULL,
    iv_rank         REAL NOT NULL,
    dte_at_entry    INTEGER NOT NULL,
    holding_period_days INTEGER NOT NULL,
    legs_json       TEXT NOT NULL,     -- JSON serialized legs
    recommendation_source TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_trades_symbol ON trades(symbol);
CREATE INDEX idx_trades_exit_date ON trades(exit_date);
CREATE INDEX idx_trades_structure ON trades(structure);
CREATE INDEX idx_trades_exit_reason ON trades(exit_reason);
```

### Table: signals

```sql
CREATE TABLE signals (
    signal_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,     -- ISO 8601
    symbol          TEXT NOT NULL,

    -- ktrdr signal
    ktrdr_signal    TEXT NOT NULL,     -- BUY | SELL | HOLD
    ktrdr_confidence REAL NOT NULL,
    ktrdr_prob_buy  REAL NOT NULL,
    ktrdr_prob_hold REAL NOT NULL,
    ktrdr_prob_sell REAL NOT NULL,
    ktrdr_model     TEXT NOT NULL,
    ktrdr_timeframe TEXT NOT NULL,

    -- Kronos regime
    kronos_regime   TEXT NOT NULL,     -- SELL_VOL | BUY_VOL | NEUTRAL
    kronos_confidence REAL NOT NULL,
    kronos_prob_sell_vol REAL NOT NULL,
    kronos_prob_buy_vol  REAL NOT NULL,
    kronos_prob_neutral  REAL NOT NULL,

    -- Vol context
    iv_rank         REAL NOT NULL,
    current_iv      REAL NOT NULL,
    vix             REAL NOT NULL,
    rv_20d          REAL NOT NULL,

    -- Decision outcome
    matrix_suggestion TEXT,
    action_taken    TEXT,              -- OPEN | HOLD | NO_TRADE
    position_id     TEXT,              -- FK if position opened

    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_signals_timestamp ON signals(timestamp);
CREATE INDEX idx_signals_symbol ON signals(symbol);
CREATE INDEX idx_signals_ktrdr_signal ON signals(ktrdr_signal);
CREATE INDEX idx_signals_kronos_regime ON signals(kronos_regime);
```

### Table: backtest_runs

```sql
CREATE TABLE backtest_runs (
    run_id          TEXT PRIMARY KEY,
    symbol          TEXT NOT NULL,
    timeframe       TEXT NOT NULL,
    start_date      TEXT NOT NULL,
    end_date        TEXT NOT NULL,
    initial_capital REAL NOT NULL,
    max_risk_pct    REAL NOT NULL,
    bid_ask_haircut REAL NOT NULL,

    -- Strategy config
    strategy_config_path TEXT NOT NULL,
    model_path      TEXT NOT NULL,
    kronos_classifier_path TEXT,

    -- Results
    total_return    REAL,
    total_return_pct REAL,
    sharpe_ratio    REAL,
    max_drawdown_pct REAL,
    win_rate        REAL,
    total_trades    INTEGER,
    winning_trades  INTEGER,
    losing_trades   INTEGER,
    profit_factor   REAL,

    -- Options-specific
    avg_theta_collected REAL,
    avg_delta_exposure  REAL,
    gamma_risk_events   INTEGER,
    structure_breakdown TEXT,  -- JSON dict

    execution_time_seconds REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_backtest_runs_symbol ON backtest_runs(symbol);
CREATE INDEX idx_backtest_runs_created ON backtest_runs(created_at);
```

### Table: backtest_trades

```sql
CREATE TABLE backtest_trades (
    trade_id        TEXT PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES backtest_runs(run_id),
    symbol          TEXT NOT NULL,
    structure       TEXT NOT NULL,
    entry_date      TEXT NOT NULL,
    exit_date       TEXT NOT NULL,
    entry_price     REAL NOT NULL,
    exit_price      REAL NOT NULL,
    pnl             REAL NOT NULL,
    pnl_pct         REAL NOT NULL,
    max_profit      REAL NOT NULL,
    max_loss        REAL NOT NULL,
    exit_reason     TEXT NOT NULL,
    ktrdr_signal    TEXT NOT NULL,
    kronos_regime   TEXT NOT NULL,
    iv_rank         REAL NOT NULL,
    dte_at_entry    INTEGER NOT NULL,
    holding_period_days INTEGER NOT NULL,
    legs_json       TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_backtest_trades_run ON backtest_trades(run_id);
CREATE INDEX idx_backtest_trades_structure ON backtest_trades(structure);
CREATE INDEX idx_backtest_trades_exit_reason ON backtest_trades(exit_reason);
```

### Table: calibration

```sql
CREATE TABLE calibration (
    calibration_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp       TEXT NOT NULL,
    symbol          TEXT NOT NULL,
    window_days     INTEGER NOT NULL DEFAULT 30,

    -- ktrdr signal calibration
    ktrdr_accuracy  REAL,              -- rolling win rate
    ktrdr_buy_precision REAL,
    ktrdr_sell_precision REAL,
    ktrdr_signal_count INTEGER,
    ktrdr_hold_pct  REAL,              -- % of signals that were HOLD (degeneration check)

    -- Kronos regime calibration
    kronos_accuracy REAL,              -- did regime prediction match realized outcome?
    kronos_sell_vol_precision REAL,
    kronos_buy_vol_precision REAL,
    kronos_regime_count INTEGER,

    -- Combined system calibration
    system_win_rate REAL,              -- options trade win rate
    system_sharpe_rolling REAL,        -- rolling 30-day Sharpe
    system_avg_pnl_pct REAL,
    system_trade_count INTEGER,

    -- Structure performance
    structure_win_rates TEXT,           -- JSON: {"bull_put_spread": 0.65, ...}

    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_calibration_timestamp ON calibration(timestamp);
CREATE INDEX idx_calibration_symbol ON calibration(symbol);
```

---

## 5. Data Flow — Sequence Diagrams

### Flow A: Backtest Cycle (One Bar)

```
    OptionsBacktestEngine            ktrdr Pipeline           KronosVolClassifier
            │                              │                          │
            │  features_t (from cache)     │                          │
            ├─────────────────────────────>│                          │
            │                              │                          │
            │  DecisionFunction.__call__() │                          │
            │  (features, position, bar)   │                          │
            │                              │                          │
            │  TradingDecision             │                          │
            │  {signal, nn_probabilities}  │                          │
            │<─────────────────────────────┤                          │
            │                              │                          │
            │  kronos_embeddings[bar_idx]                             │
            ├────────────────────────────────────────────────────────>│
            │                                                         │
            │  classifier.forward(embedding)                          │
            │                                                         │
            │  VolRegimeSignal                                        │
            │  {regime, confidence, probabilities}                    │
            │<────────────────────────────────────────────────────────┤
            │
            │                    OptionsDecisionMatrix
            │                              │
            │  select(DecisionInput)       │
            ├─────────────────────────────>│
            │                              │
            │  StructureChoice             │
            │  {structure, target_delta,   │
            │   target_dte, width}         │
            │<─────────────────────────────┤
            │
            │                    BlackScholesEngine
            │                              │
            │  find_strike_by_delta()      │
            │  price_spread()              │
            │  apply_haircut()             │
            ├─────────────────────────────>│
            │                              │
            │  {strikes, entry_price,      │
            │   max_profit, max_loss,      │
            │   greeks}                    │
            │<─────────────────────────────┤
            │
            │                    OptionsPositionManager
            │                              │
            │  open_position() or          │
            │  mark_to_market() +          │
            │  check_exit_conditions()     │
            ├─────────────────────────────>│
            │                              │
            │  OptionsPosition             │
            │<─────────────────────────────┤
            │
            │                    SQLite
            │                       │
            │  INSERT/UPDATE         │
            ├──────────────────────>│
            │                       │
            v                       v
```

### Flow B: Live/Paper Analysis Cycle (Lux Triggered)

```
    LuxOrchestrator    KtrdrSignalClient     ktrdr REST API    KronosVolClassifier
          │                    │                    │                    │
          │ predict(model,     │                    │                    │
          │ symbol, tf)        │                    │                    │
          ├───────────────────>│                    │                    │
          │                    │ POST /api/v1/      │                    │
          │                    │ models/predict     │                    │
          │                    ├───────────────────>│                    │
          │                    │                    │                    │
          │                    │ PredictionResponse │                    │
          │                    │ + probabilities    │                    │
          │                    │<───────────────────┤                    │
          │ KtrdrSignal        │                    │                    │
          │<───────────────────┤                    │                    │
          │                                                             │
          │ predict(ohlcv, iv_rank)                                     │
          ├────────────────────────────────────────────────────────────>│
          │                                                             │
          │ VolRegimeSignal                                             │
          │<────────────────────────────────────────────────────────────┤
          │
          │     OptionsDataProvider
          │            │
          │ get_options_chain()
          │ get_iv_data()
          ├───────────>│──────> yfinance / IBKR MCP
          │            │<────── OptionsChain, IVData
          │<───────────┤
          │
          │     SignalAggregator
          │            │
          │ aggregate()│
          ├───────────>│
          │ DecisionInput
          │<───────────┤
          │
          │     OpusStrategyAdvisor              Anthropic API
          │            │                              │
          │ advise()   │                              │
          ├───────────>│  POST /v1/messages            │
          │            │  (structured JSON prompt)     │
          │            ├─────────────────────────────>│
          │            │                              │
          │            │  JSON response               │
          │            │  (structure, legs, reasoning) │
          │            │<─────────────────────────────┤
          │            │                              │
          │            │ validate(recommendation)     │
          │ TradeRecommendation                       │
          │<───────────┤
          │
          │     OptionsPositionManager     IBKR MCP        Telegram
          │            │                      │                │
          │ open_position()                   │                │
          ├───────────>│                      │                │
          │            │                      │                │
          │ _execute_trade()                  │                │
          ├──────────────────────────────────>│                │
          │            │  order confirmation  │                │
          │<─────────────────────────────────┤                │
          │                                                    │
          │ _send_telegram_report()                            │
          ├───────────────────────────────────────────────────>│
          │                                                    │
          v                                                    v
```

### Flow C: Error Handling — ktrdr API Unavailable

```
    LuxOrchestrator    KtrdrSignalClient         ktrdr REST API
          │                    │                        │
          │ predict()          │                        │
          ├───────────────────>│                        │
          │                    │ POST /predict          │
          │                    ├───────────────────────>│
          │                    │                        │ CONNECTION REFUSED
          │                    │<──────────────────────X│
          │                    │                        │
          │                    │ retry 1 (backoff 2s)   │
          │                    ├───────────────────────>│
          │                    │                        │ TIMEOUT
          │                    │<──────────────────────X│
          │                    │                        │
          │                    │ retry 2 (backoff 4s)   │
          │                    ├───────────────────────>│
          │                    │                        │ TIMEOUT
          │                    │<──────────────────────X│
          │                    │                        │
          │ KtrdrAPIError      │                        │
          │<───────────────────┤                        │
          │                                             │
          │ DECISION: HOLD all positions                │
          │ (no new trades opened)                      │
          │                                             │
          │     SQLite                   Telegram       │
          │        │                        │           │
          │ log signal (error)              │           │
          ├───────>│                        │           │
          │                                 │           │
          │ send alert:                     │           │
          │ "ktrdr API unavailable,         │           │
          │  holding all positions"         │           │
          ├────────────────────────────────>│           │
          │                                 │           │
          v                                 v           v
```

### Flow D: Error Handling — Opus 4.7 Unavailable

```
    OpusStrategyAdvisor          Anthropic API       OptionsDecisionMatrix
          │                           │                       │
          │ POST /v1/messages         │                       │
          ├──────────────────────────>│                       │
          │                           │ 529 OVERLOADED        │
          │<─────────────────────────X│                       │
          │                           │                       │
          │ retry 1                   │                       │
          ├──────────────────────────>│                       │
          │                           │ TIMEOUT (60s)         │
          │<─────────────────────────X│                       │
          │                           │                       │
          │ FALLBACK to matrix        │                       │
          │                           │                       │
          │ select(decision_input)                            │
          ├──────────────────────────────────────────────────>│
          │                                                   │
          │ StructureChoice                                   │
          │<──────────────────────────────────────────────────┤
          │                                                   │
          │ Build TradeRecommendation                          │
          │ source="matrix"                                   │
          │ reasoning="Opus unavailable. Fallback to          │
          │            deterministic matrix."                  │
          │ warnings=["opus_fallback"]                         │
          │                                                   │
          │ LOG: "Opus 4.7 unavailable, used matrix fallback" │
          │                                                   │
          │ return TradeRecommendation                         │
          v                                                   v
```

---

## 6. State Management

### In-Memory State

| Component | State Held | Lifecycle | Reset Behavior |
|-----------|-----------|-----------|---------------|
| `KronosVolClassifier` | `_kronos_model` (frozen weights), `_tokenizer`, `_classifier` (linear head) | Loaded once at startup | Never reset during session. Reload requires restart. |
| `KtrdrSignalClient` | `_client` (httpx.AsyncClient) | Created at init, reused | Connection pool auto-managed by httpx. |
| `OptionsDataProvider` | `_vix_cache` (pd.Series), `_rate_cache` (dict) | Populated on first call, refreshed daily | Invalidated when date changes. |
| `SignalAggregator` | `_decision_matrix` (reference) | Stateless beyond config | N/A — no mutable state. |
| `OpusStrategyAdvisor` | `_client` (anthropic.AsyncAnthropic) | Created at init | N/A — stateless per call. |
| `OptionsPositionManager` | `_open_positions` (list) | Loaded from SQLite at init, updated on open/close | Reloaded from SQLite on restart. |
| `OptionsBacktestEngine` | `_kronos_embeddings` (torch.Tensor), `_vix_history` (pd.Series), feature cache | Loaded once per run | Garbage collected after run completes. |
| `LuxOrchestrator` | `_running` (bool), component references | Init to stop | `_running` set False on stop(). |

### Persistent State (SQLite)

| Data | Written When | Read When |
|------|-------------|----------|
| `positions` table | On `open_position()`, updated on `mark_to_market()` and `close_position()` | On startup (reload open positions), on `get_open_positions()`, `get_position_history()` |
| `trades` table | On `close_position()` | Performance analysis, calibration computation |
| `signals` table | End of each cycle (live/paper) | Calibration, signal distribution monitoring |
| `backtest_runs` table | After backtest completes | Backtest comparison |
| `backtest_trades` table | During backtest, per trade close | Backtest analysis |
| `calibration` table | Periodically (e.g., daily) by LuxOrchestrator | Monitoring, alerting, model degradation detection |

### Ephemeral State (Per-Cycle, Discarded)

| Data | Component | Scope |
|------|-----------|-------|
| `KtrdrSignal` (current) | `LuxOrchestrator.run_cycle()` | One cycle |
| `VolRegimeSignal` (current) | `LuxOrchestrator.run_cycle()` | One cycle |
| `OptionsChain` (current snapshot) | `LuxOrchestrator.run_cycle()` | One cycle |
| `DecisionInput` | `SignalAggregator.aggregate()` | One cycle |
| `TradeRecommendation` | `OpusStrategyAdvisor.advise()` | One cycle |
| `CycleResult` | `LuxOrchestrator.run_cycle()` | One cycle (logged, then GC'd) |
| Per-bar ktrdr signal (backtest) | `OptionsBacktestEngine.run()` | One bar iteration |

### Cached State (Disk)

| Cache | Format | Location | Invalidation |
|-------|--------|----------|-------------|
| Kronos embeddings | `.pt` (PyTorch tensor) | `cache/kronos/{symbol}_{timeframe}_embeddings.pt` | Re-compute when OHLCV data range changes or Kronos model version changes |
| ktrdr feature cache | In-memory dict (within BacktestingEngine) | Not persisted to disk — computed fresh per backtest run | Per run |
| VIX history | CSV | `cache/vix_daily.csv` | Re-download when >1 day stale |
| Risk-free rate | JSON | `cache/risk_free_rate.json` | Re-fetch when >1 day stale |
| Classifier head weights | `.pt` | `models/kronos_classifier/{symbol}_head.pt` + `config.json` | Retrain when AUC degrades or data expands |

### State Lifecycle Summary

```
STARTUP:
  1. Load config from YAML
  2. Initialize KronosVolClassifier (load model + classifier weights)
  3. Initialize KtrdrSignalClient (create HTTP client)
  4. Initialize OptionsDataProvider
  5. Initialize OptionsPositionManager (connect SQLite, load open positions)
  6. Initialize OpusStrategyAdvisor (create Anthropic client)
  7. Initialize SignalAggregator + OptionsDecisionMatrix

PER CYCLE (live/paper):
  1. Create ephemeral: KtrdrSignal, VolRegimeSignal, IVData, OptionsChain
  2. Create ephemeral: DecisionInput, TradeRecommendation
  3. Update persistent: positions (mark-to-market), trades (if closed)
  4. Create persistent: signals (log entry)
  5. Discard all ephemeral state

PER BACKTEST RUN:
  1. Load cached: Kronos embeddings (or compute + cache)
  2. Load cached: VIX history (or download + cache)
  3. Per bar: compute ephemeral signal state, update in-memory positions
  4. Write persistent: backtest_runs, backtest_trades (after run completes)
  5. Discard: all in-memory state

SHUTDOWN:
  1. Close HTTP clients
  2. Close SQLite connections
  3. GC all in-memory state
```

---

## 7. API Contract — ktrdr Endpoint Extension

### Current PredictionResponse Schema

**Source**: `ktrdr/api/endpoints/models.py`, lines 194-229

```python
class Prediction(BaseModel):
    signal: str              # "BUY" | "SELL" | "HOLD"
    confidence: float        # max probability
    signal_strength: float   # 0.0-1.0

class PredictionResponse(BaseModel):
    success: bool
    model_name: str
    symbol: str
    test_date: str
    prediction: Prediction
    input_features: dict[str, float]
```

Current response JSON:
```json
{
    "success": true,
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "test_date": "2026-04-18T14:30:00",
    "prediction": {
        "signal": "BUY",
        "confidence": 0.756,
        "signal_strength": 0.694
    },
    "input_features": {"1h_rsi_momentum_oversold": 0.02, ...}
}
```

### Proposed Extension

```python
class Prediction(BaseModel):
    signal: str
    confidence: float
    signal_strength: float
    probabilities: dict[str, float] | None = None  # NEW: optional field

class PredictionResponse(BaseModel):
    success: bool
    model_name: str
    symbol: str
    test_date: str
    prediction: Prediction
    input_features: dict[str, float]
```

Extended response JSON:
```json
{
    "success": true,
    "model_name": "trend_tb_lstm_signal_v1",
    "symbol": "SPY",
    "test_date": "2026-04-18T14:30:00",
    "prediction": {
        "signal": "BUY",
        "confidence": 0.756,
        "signal_strength": 0.694,
        "probabilities": {"BUY": 0.756, "HOLD": 0.182, "SELL": 0.062}
    },
    "input_features": {"1h_rsi_momentum_oversold": 0.02, ...}
}
```

### Backward Compatibility

- The `probabilities` field is **optional** (`None` default). Existing clients that do not expect it will ignore the extra field (standard JSON parsing behavior).
- No existing fields are modified or removed.
- The field is populated from `TradingDecision.reasoning["nn_probabilities"]` which already exists in the internal pipeline (see `ktrdr/decision/base.py:26`, reasoning dict).
- **Code change**: In the prediction endpoint handler, after obtaining `TradingDecision`, extract `reasoning.get("nn_probabilities")` and pass to `Prediction(probabilities=...)`.
- Estimated change: ~5-10 lines in `ktrdr/api/endpoints/models.py`.

---

## 8. Configuration Schema

```yaml
# ktrdr-options-config.yaml
# Complete configuration for the ktrdr Autonomous Options Trading System

# --- ktrdr Signal Source ---
ktrdr:
  base_url: "http://localhost:8000"      # ktrdr REST API base URL
  model_name: "trend_tb_lstm_signal_v1"  # trained model to use
  symbol: "SPY"                          # underlying ticker
  timeframe: "1h"                        # bar timeframe for signals
  timeout_seconds: 30.0                  # HTTP request timeout
  max_retries: 3                         # retries on failure
  retry_backoff_base: 2.0                # exponential backoff base (seconds)
  stale_bar_threshold: 2                 # alert if response is >N bars stale

# --- Kronos Vol Regime Classifier ---
kronos:
  model: "NeoQuasar/Kronos-mini"         # HuggingFace model name
  tokenizer: "NeoQuasar/Kronos-Tokenizer-2k"  # tokenizer for mini
  classifier_weights_path: "models/kronos_classifier/SPY_head.pt"
  device: "cpu"                          # "cpu" | "cuda"
  embedding_dim: 256                     # must match model (256 for mini)
  pooling: "last"                        # "last" | "mean" [VALIDATE EMPIRICALLY]
  context_window: 512                    # bars to feed Kronos
  embeddings_cache_dir: "cache/kronos"   # pre-computed embeddings

  # Classifier training config (used during Phase 1)
  training:
    iv_rank_high_pct: 70                 # percentile for SELL_VOL label
    iv_rank_low_pct: 30                  # percentile for BUY_VOL label
    rv_discount: 0.85                    # RV < IV * discount = SELL_VOL
    rv_premium: 1.15                     # RV > IV * premium = BUY_VOL
    forward_rv_window: 20               # days for forward realized vol
    train_epochs: 100
    train_lr: 0.001
    class_weights: [1.0, 2.0, 2.5]      # [NEUTRAL, SELL_VOL, BUY_VOL] — upweight rare classes

  # Fallback: if Kronos model load fails, use IV rank heuristic
  fallback_iv_rank_high: 70              # IV rank > this = SELL_VOL
  fallback_iv_rank_low: 30              # IV rank < this = BUY_VOL

# --- Options Data ---
options_data:
  mode: "backtest"                       # "backtest" | "paper" | "live"
  vix_data_path: null                    # optional cached VIX CSV
  cache_dir: "cache"
  iv_rank_lookback_days: 252             # trading days for IV rank computation

  # For paper/live mode
  ibkr:
    host: "localhost"
    port: 7497                           # 7497=paper, 7496=live
    client_id: 1

# --- Opus 4.7 Strategy Advisor ---
opus:
  enabled: true                          # set false to use matrix only
  model: "claude-opus-4-7-20260401"
  timeout_seconds: 60.0
  max_retries: 2
  # API key sourced from ANTHROPIC_API_KEY env var

# --- Decision Matrix ---
decision_matrix:
  # Confidence gates
  min_ktrdr_confidence: 0.45             # minimum for any directional trade
  min_ktrdr_confidence_naked: 0.65       # minimum for naked long options
  min_kronos_confidence_vol: 0.70        # minimum for vol-specific structures (condor, straddle)
  min_kronos_confidence_other: 0.50      # minimum for all other structures

# --- Risk Management ---
risk:
  max_risk_per_trade_pct: 0.02           # 2% of account value per trade
  max_total_risk_pct: 0.10               # 10% of account total open risk
  max_positions: 5                       # max simultaneous open positions
  initial_capital: 100000.0

  # Position sizing from probability spread
  sizing:
    low_spread_threshold: 0.10           # probability_spread < this -> 0.5x
    medium_spread_threshold: 0.25        # probability_spread < this -> 0.75x
    low_multiplier: 0.5
    medium_multiplier: 0.75
    high_multiplier: 1.0

# --- Structure Parameters ---
structures:
  bull_put_spread:
    dte_min: 30
    dte_max: 45
    short_delta: 0.30                    # target delta for short leg
    width_strikes: 1                     # width in strike increments
  iron_condor:
    dte_min: 30
    dte_max: 45
    short_delta: 0.16                    # each side
    width_strikes: 1
  bull_call_spread:
    dte_min: 21
    dte_max: 35
    long_delta: 0.45
    width_strikes: 2
  bear_call_spread:
    dte_min: 30
    dte_max: 45
    short_delta: 0.30
    width_strikes: 1
  long_call:
    dte_min: 14
    dte_max: 30
    long_delta: 0.40
  long_straddle:
    dte_min: 14
    dte_max: 30
    # ATM by definition
  bear_put_spread:
    dte_min: 21
    dte_max: 35
    long_delta: 0.45
    width_strikes: 2
  long_put:
    dte_min: 14
    dte_max: 30
    long_delta: 0.40

# --- Exit Rules ---
exits:
  take_profit_pct: 50.0                  # close at 50% of max profit
  stop_loss_pct: 100.0                   # close at 100% of max loss
  time_exit_dte: 7                       # close when DTE < 7
  signal_reversal_exit: true             # close when ktrdr signal reverses
  # Dividend protection
  exclude_near_ex_dividend_days: 5       # skip entries within N days of ex-date

# --- Backtest ---
backtest:
  bid_ask_haircut: 0.10                  # 10% flat haircut on B-S prices
  risk_free_rate_override: null          # null = fetch from FRED; set float to override
  strike_step: 1.0                       # SPY strike increment ($1)
  db_path: "backtest_results.db"

# --- Persistence ---
persistence:
  db_path: "ktrdr_options.db"            # SQLite database for live/paper

# --- Scheduling ---
schedule:
  interval_minutes: 60                   # analysis cycle frequency
  trading_hours_only: true               # skip cycles outside market hours
  market_open: "09:30"                   # ET
  market_close: "16:00"                  # ET
  timezone: "US/Eastern"

# --- Notifications ---
notifications:
  telegram:
    enabled: true
    # Bot token and chat ID sourced from env vars:
    # TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    notify_on:
      - trade_opened
      - trade_closed
      - error
      - daily_summary
      - calibration_alert

# --- Logging ---
logging:
  level: "INFO"                          # DEBUG | INFO | WARNING | ERROR
  file: "logs/ktrdr_options.log"
  rotation: "10 MB"
  retention: 30                          # days
```

---

## 9. Error Handling Matrix

| Component | Failure Mode | Detection | Impact | Mitigation | Recovery |
|-----------|-------------|-----------|--------|------------|---------|
| **KtrdrSignalClient** | API unreachable (connection refused, DNS failure) | `httpx.ConnectError` after 3 retries with exponential backoff (2s, 4s, 8s) | No directional signal for this cycle | HOLD all positions. No new trades. Log error. | Next cycle retries normally. Alert via Telegram if 3+ consecutive failures. |
| **KtrdrSignalClient** | API returns error (500, malformed response) | HTTP status != 200 or JSON parse failure | No directional signal | Same as above: HOLD, no new trades. | Auto-recovers on next successful call. |
| **KtrdrSignalClient** | Stale data (response test_date > 2 bars behind) | Compare `test_date` in response to current time | Signal based on outdated market data | Log `KtrdrStaleDataError`. Treat as HOLD. Telegram alert. | Investigate ktrdr data pipeline. May need `ktrdr data load` to refresh OHLCV cache. |
| **KronosVolClassifier** | Model weights not found / corrupted | `FileNotFoundError` or `RuntimeError` on `load_model()` | No vol regime signal | Fall back to IV rank heuristic: IV rank > 70 = SELL_VOL, < 30 = BUY_VOL, else NEUTRAL. Log warning. | Re-download weights from HuggingFace. Restart. |
| **KronosVolClassifier** | Forward pass error (OOM, NaN output) | `RuntimeError` or NaN check on output tensor | No vol regime signal | Fall back to IV rank heuristic for this cycle. | Typically transient. If persistent, reduce context_window or check input data quality. |
| **KronosVolClassifier** | Classifier head not trained (no weights file) | `classifier_weights_path` is None or file missing | Raw Kronos embedding available but no classification | Use IV rank heuristic fallback. This is expected before Phase 1 training completes. | Train classifier head (Phase 1 deliverable). |
| **OptionsDataProvider** | yfinance rate limit or outage | `HTTPError` or empty response | No IV data, no options chain | For IV: use last cached VIX value with staleness warning. For chain: cannot open new positions (HOLD). | yfinance rate limits are transient. Retry next cycle. Cache VIX history locally to reduce API calls. |
| **OptionsDataProvider** | IBKR MCP disconnected (paper/live) | MCP tool returns error | No real options chain data | Cannot open new positions. Mark-to-market uses last known chain. | Reconnect IBKR. Check IB Gateway is running. |
| **OpusStrategyAdvisor** | API unavailable (outage, rate limit) | `anthropic.APIConnectionError` or 529 status after 2 retries | No Opus reasoning for this cycle | Fall back to OptionsDecisionMatrix. TradeRecommendation.source = "matrix". Log fallback. | Auto-recovers. If persistent, set `opus.enabled: false` in config. |
| **OpusStrategyAdvisor** | Malformed JSON response | JSON parse error or missing required fields | Cannot use Opus recommendation | Retry once with explicit "respond in valid JSON" constraint. Then fall back to matrix. | Usually transient. If model consistently fails, update prompt. |
| **OpusStrategyAdvisor** | Recommendation violates risk limits | Validation detects max_risk > budget or structure not in allowed list | Would create unsafe position | Reject recommendation. Retry with explicit constraint. After 2 retries, use matrix fallback. | Log the specific violation for prompt tuning. |
| **OpusStrategyAdvisor** | Timeout (>60s) | `asyncio.TimeoutError` | Blocks cycle | Cancel request, use matrix fallback. | Transient. Consider increasing timeout if Opus consistently uses extended thinking. |
| **OptionsPositionManager** | SQLite write failure (disk full, corruption) | `sqlite3.OperationalError` | Cannot persist position state | Log CRITICAL error. Continue with in-memory state only. Telegram alert. | Free disk space. If corruption: restore from last backup. In-memory positions survive until restart. |
| **OptionsPositionManager** | Position mark-to-market fails (NaN Greeks) | NaN check on BlackScholesEngine output | Position shows invalid current values | Use last valid mark. Log warning. | Usually caused by T -> 0 (near expiry). Force-close positions at time_exit_dte threshold. |
| **BlackScholesEngine** | Invalid inputs (negative vol, T=0, S=0) | Input validation checks | Cannot price options | Return None / raise `ValueError`. Caller skips this trade. | Fix upstream data quality issue. |
| **LuxOrchestrator** | Unhandled exception in cycle | Top-level try/except in `run_cycle()` | One cycle fails | Log full traceback. Send Telegram error alert. Continue to next cycle. | Investigate logs. Fix bug. System auto-continues. |
| **LuxOrchestrator** | Multiple consecutive cycle failures (>5) | Counter of consecutive errors | System may be fundamentally broken | Stop opening new positions. Continue monitoring/exiting existing positions. Telegram CRITICAL alert. | Manual investigation required. |

---

## 10. Dependency Map

### Hard Dependencies (System Cannot Function Without)

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `python` | >= 3.12 | Runtime |
| `torch` | >= 2.0.0 | Kronos model inference, classifier training |
| `numpy` | >= 1.24 | Numerical computation (Black-Scholes, Greeks) |
| `scipy` | >= 1.10 | `scipy.stats.norm` for Black-Scholes N(d) |
| `pandas` | >= 2.0 | Data manipulation, time series |
| `httpx` | >= 0.24 | Async HTTP client for ktrdr REST API |
| `anthropic` | >= 0.40 | Anthropic API client for Opus 4.7 |
| ktrdr REST API | (local service) | Directional trading signal source |
| SQLite | (stdlib) | Persistence (positions, trades, signals) |

### Hard Dependencies — Kronos-Specific

| Dependency | Version | Purpose |
|-----------|---------|---------|
| `einops` | == 0.8.1 | Required by Kronos model code |
| `huggingface_hub` | >= 0.20 | Download Kronos model weights |
| `safetensors` | >= 0.4 | Load Kronos model weights |
| Kronos model weights | `NeoQuasar/Kronos-mini` | Frozen transformer for embeddings |
| Kronos tokenizer | `NeoQuasar/Kronos-Tokenizer-2k` | OHLCV tokenization |

### Hard Dependencies — ktrdr Library (Backtest Only)

| Dependency | Import Path | Purpose |
|-----------|-------------|---------|
| `DecisionFunction` | `ktrdr.backtesting.decision_function` | Generate directional signals per bar |
| `ModelBundle` | `ktrdr.backtesting.model_bundle` | Load trained ktrdr models |
| `IndicatorEngine` | `ktrdr.indicators.indicator_engine` | Compute technical indicators |
| `FuzzyEngine` | `ktrdr.fuzzy.engine` | Convert indicators to fuzzy memberships |
| `FuzzyNeuralProcessor` | `ktrdr.training.fuzzy_neural_processor` | Assemble feature tensors |
| `FeatureResolver` | `ktrdr.config.feature_resolver` | Canonical feature ordering |
| `LocalDataLoader` | `ktrdr.data.local_data_loader` | Load OHLCV from CSV cache |

### Soft Dependencies (Graceful Degradation)

| Dependency | Purpose | Degradation Behavior |
|-----------|---------|---------------------|
| `yfinance` | VIX history, current options chains, underlying prices | Backtest: use cached VIX CSV. Live: fall back to IBKR data only. |
| `pandas_datareader` or FRED API | Risk-free rate | Use hardcoded rate (e.g., 0.05) or config override |
| Anthropic API (Opus 4.7) | Strategy reasoning | Fall back to OptionsDecisionMatrix (deterministic) |
| IBKR MCP (paper/live) | Order execution, real options chain | Cannot execute trades. System operates in analysis-only mode. |
| Telegram Bot API | Notifications to Karl | Log locally. No notifications. System continues trading. |
| Kronos model | Vol regime classification | Fall back to IV rank heuristic (>70 = SELL_VOL, <30 = BUY_VOL, else NEUTRAL) |

### External Services

| Service | Protocol | Usage Context | Latency Tolerance |
|---------|----------|--------------|-------------------|
| ktrdr REST API | HTTP (localhost) | Every cycle (live/paper) | < 30s (including retries) |
| Anthropic API | HTTPS (remote) | Every cycle (live/paper, if Opus enabled) | < 60s |
| IBKR MCP | Local MCP protocol | Paper/live trading | < 10s per order |
| yfinance | HTTPS (remote) | Options chain + VIX fetch | < 30s |
| FRED API | HTTPS (remote) | Risk-free rate (daily) | < 10s |
| Telegram Bot API | HTTPS (remote) | Notifications | < 5s (non-blocking) |
| HuggingFace Hub | HTTPS (remote) | Model weight download (one-time) | Minutes (first run only) |

---

## Appendix: Open Decisions and Empirical Validation Items

### [DECISION NEEDED]

1. **Which symbols to start with?** SPY recommended first. Second symbol TBD by Karl.
2. **Budget for historical options data?** $0 (B-S reconstruction), ~$200 (OptionsDX), or $1000+ (CBOE).
3. **ktrdr API extension**: Extend `/predict` to return `probabilities` field (~10 lines). Recommended over library-direct approach.
4. **Live trading approval gate**: All live trades require Karl's Telegram approval initially?
5. **IBKR MCP options capabilities**: Does the existing IBKR integration support multi-leg options orders? Needs investigation.
6. **Max risk per trade**: 2% default. Karl may adjust.

### [VALIDATE EMPIRICALLY]

1. Kronos embedding AUC > 0.60 for vol regime classification (Phase 1 gate).
2. Mean pool vs last hidden state for Kronos embeddings.
3. Kronos-mini (256d) vs Kronos-small (512d) for classification quality.
4. Bid/ask haircut calibration (10% starting guess).
5. Optimal DTE per structure type (test 14, 21, 30, 45).
6. Label thresholds for vol regime (70/30 percentile, 0.85/1.15 multipliers).
7. Exit timing parameters (take profit at 40/50/60%, stop loss at 75/100%).
8. Kronos CPU inference latency on Karl's Docker stack.
9. Forward RV window length (10, 15, 20, 30 days).
