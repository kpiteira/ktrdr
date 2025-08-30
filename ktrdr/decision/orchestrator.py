"""Decision orchestrator that coordinates the complete decision pipeline."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, cast

import pandas as pd
import yaml  # type: ignore[import-untyped]

from .. import get_logger
from ..backtesting.model_loader import ModelLoader
from ..data.data_manager import DataManager
from ..fuzzy.engine import FuzzyEngine
from ..indicators.indicator_engine import IndicatorEngine
from .base import Position, Signal, TradingDecision
from .engine import DecisionEngine

logger = get_logger(__name__)


@dataclass
class DecisionContext:
    """Complete context for making a trading decision."""

    # Market data
    current_bar: pd.Series
    recent_bars: pd.DataFrame  # Lookback window

    # Calculated features
    indicators: dict[str, float]
    fuzzy_memberships: dict[str, float]

    # Position state
    current_position: Position
    position_entry_price: Optional[float]
    position_holding_period: Optional[float]
    unrealized_pnl: Optional[float]

    # Account state
    portfolio_value: float
    available_capital: float

    # Historical context
    recent_decisions: list[TradingDecision]
    last_signal_time: Optional[pd.Timestamp]


class PositionState:
    """Track position state for a single symbol."""

    def __init__(self, symbol: str):
        """Initialize position state.

        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        self.position = Position.FLAT
        self.entry_price = None
        self.entry_time: Optional[pd.Timestamp] = None
        self.last_signal_time: Optional[pd.Timestamp] = None
        self.unrealized_pnl = 0.0

    @property
    def holding_period(self) -> Optional[float]:
        """Holding period in hours."""
        if self.entry_time:
            current_time = pd.Timestamp.now(tz="UTC")
            if isinstance(self.entry_time, pd.Timestamp):
                # Ensure both timestamps are timezone-aware UTC
                entry_time = self.entry_time
                if entry_time.tz is None:
                    entry_time = entry_time.tz_localize("UTC")
                elif str(entry_time.tz) != "UTC":
                    entry_time = entry_time.tz_convert("UTC")

                return (current_time - entry_time).total_seconds() / 3600
        return None

    def update_from_decision(self, decision: TradingDecision, current_bar: pd.Series):
        """Update state based on decision.

        Args:
            decision: Trading decision
            current_bar: Current price bar
        """
        if decision.signal != Signal.HOLD:
            self.last_signal_time = (
                pd.Timestamp(str(current_bar.name)) if hasattr(current_bar, "name") else pd.Timestamp.now()
            )

            if decision.signal == Signal.BUY and self.position == Position.FLAT:
                self.position = Position.LONG
                self.entry_price = current_bar["close"]
                self.entry_time = self.last_signal_time
                self.unrealized_pnl = 0.0
            elif decision.signal == Signal.SELL and self.position == Position.LONG:
                # Calculate realized P&L
                if self.entry_price:
                    current_bar["close"] - self.entry_price
                    # Could store this for performance tracking

                # Close position
                self.position = Position.FLAT
                self.entry_price = None
                self.entry_time = None
                self.unrealized_pnl = 0.0

        # Update unrealized P&L for open positions
        if self.position == Position.LONG and self.entry_price:
            self.unrealized_pnl = current_bar["close"] - self.entry_price


class DecisionOrchestrator:
    """Central orchestrator that coordinates the complete decision pipeline."""

    def __init__(
        self,
        strategy_config_path: str,
        model_path: Optional[str] = None,
        mode: str = "backtest",
    ):
        """Initialize the decision orchestrator.

        Args:
            strategy_config_path: Path to strategy YAML file
            model_path: Path to trained model (if None, loads latest)
            mode: Operating mode (backtest, paper, live)
        """
        self.mode = mode

        # Load strategy configuration
        self.strategy_config = self._load_strategy_config(strategy_config_path)
        self.strategy_name = self.strategy_config["name"]

        # Initialize data pipeline components (existing)
        self.data_manager = DataManager()
        self.indicator_engine = IndicatorEngine()

        # Initialize fuzzy engine with strategy fuzzy sets
        self.fuzzy_engine = self._initialize_fuzzy_engine()

        # Load trained model
        self.model_loader = ModelLoader()
        self.model = None
        self.model_metadata = None

        if model_path:
            # Load specific model
            self.model, self.model_metadata = self._load_model_from_path(model_path)

        # Initialize decision engine
        self.decision_engine = DecisionEngine(
            strategy_config=self.strategy_config, model_path=model_path
        )

        # State management
        self.position_states: dict[str, PositionState] = {}
        self.decision_history: list[TradingDecision] = []
        self.max_history = 100

        # Feature caching for backtesting performance
        self.feature_cache = None
        if mode == "backtest":
            from ..backtesting.feature_cache import FeatureCache

            self.feature_cache = FeatureCache(self.strategy_config)

    def prepare_feature_cache(self, historical_data: pd.DataFrame) -> None:
        """Pre-compute all features for backtesting performance.

        Args:
            historical_data: Complete historical OHLCV data for backtesting
        """
        if self.feature_cache is None:
            return

        logger.info("🚀 Preparing feature cache for backtesting...")
        self.feature_cache.compute_all_features(historical_data)
        logger.info("✅ Feature cache ready!")

    def make_decision(
        self,
        symbol: str,
        timeframe: str,
        current_bar: pd.Series,
        historical_data: pd.DataFrame,
        portfolio_state: dict[str, Any],
    ) -> TradingDecision:
        """Main entry point for generating trading decisions.

        This method:
        1. Calculates indicators from historical data
        2. Generates fuzzy memberships
        3. Prepares decision context
        4. Gets neural network decision
        5. Applies orchestrator-level logic
        6. Returns final trading decision

        Args:
            symbol: Trading symbol
            timeframe: Timeframe (must match model training)
            current_bar: Latest price bar
            historical_data: Historical bars including current
            portfolio_state: Current portfolio/account state

        Returns:
            TradingDecision with signal, confidence, and metadata
        """
        # Step 1 & 2: Get indicators and fuzzy memberships (cached or computed)
        # FEATURE CACHE ENABLED: Fixed sliding window computation
        if self.feature_cache and self.feature_cache.is_ready():
            current_timestamp = (
                current_bar.name if hasattr(current_bar, "name") else pd.Timestamp.now()
            )

            try:
                # Use pre-computed cached features for fast lookup
                mapped_indicators, fuzzy_values = (
                    self.feature_cache.get_features_for_timestamp(pd.Timestamp(str(current_timestamp)))
                )
                logger.debug(
                    f"🚀 [{cast(pd.Timestamp, current_timestamp).strftime('%Y-%m-%d %H:%M')}] Using cached features: {len(mapped_indicators)} indicators, {len(fuzzy_values)} fuzzy"
                )
            except ValueError as e:
                logger.debug(
                    f"⚠️ Cache lookup failed: {e}, falling back to real-time computation"
                )
                # Fall back to real-time computation
                mapped_indicators, fuzzy_values = self._compute_features_realtime(
                    historical_data, current_bar
                )
        else:
            # Real-time computation (for non-backtest modes or when cache not ready)
            mapped_indicators, fuzzy_values = self._compute_features_realtime(
                historical_data, current_bar
            )

        # Step 3: Prepare decision context
        context = self._prepare_context(
            symbol=symbol,
            current_bar=current_bar,
            historical_data=historical_data,
            indicators=mapped_indicators,
            fuzzy_memberships=fuzzy_values,
            portfolio_state=portfolio_state,
        )

        # Step 4: Load model if needed (for multi-symbol support)
        if not self.model:
            logger.info(
                f"🤖 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Loading neural model for {symbol} {timeframe}"
            )
            self.model, self.model_metadata = self._load_model_for_symbol(
                symbol, timeframe
            )
            if self.decision_engine.neural_model is not None:
                self.decision_engine.neural_model.model = self.model
                self.decision_engine.neural_model.is_trained = True
                # Set the saved scaler for consistent feature scaling
                self.decision_engine.neural_model.feature_scaler = self.model_metadata.get(
                    "scaler"
                )
                logger.info(
                    f"🤖 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Model loaded successfully, is_trained: {self.decision_engine.neural_model.is_trained}"
                )
            else:
                logger.warning("Neural model not initialized")
        else:
            if self.decision_engine.neural_model is not None:
                logger.debug(
                    f"🤖 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Using existing model, is_trained: {self.decision_engine.neural_model.is_trained}"
                )
            else:
                logger.debug("Neural model not initialized")

        # Step 5: Generate decision using the decision engine
        logger.debug(
            f"🎯 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Calling decision engine with {len(context.fuzzy_memberships)} fuzzy features"
        )

        decision = self.decision_engine.generate_decision(
            current_data=current_bar,
            fuzzy_memberships=context.fuzzy_memberships,
            indicators=context.indicators,
        )

        logger.debug(
            f"🎯 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Decision engine returned: {decision.signal.value} (confidence: {decision.confidence:.4f})"
        )

        # Step 6: Apply orchestrator-level logic
        logger.debug(
            f"🎯 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Applying orchestrator logic to {decision.signal.value}"
        )

        final_decision = self._apply_orchestrator_logic(decision, context)

        if final_decision.signal != decision.signal:
            logger.info(
                f"🚫 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Orchestrator OVERRODE {decision.signal.value} → {final_decision.signal.value} (reason: {final_decision.reasoning.get('orchestrator_override', 'Unknown')})"
            )
        else:
            logger.debug(
                f"✅ [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Orchestrator kept {final_decision.signal.value}"
            )

        # Step 7: Update state
        self._update_state(symbol, final_decision, context)

        return final_decision

    def _compute_features_realtime(
        self, historical_data: pd.DataFrame, current_bar: pd.Series
    ) -> tuple[dict[str, float], dict[str, float]]:
        """Compute features in real-time (original expensive method).

        Args:
            historical_data: Historical bars including current
            current_bar: Current price bar

        Returns:
            Tuple of (mapped_indicators, fuzzy_values) dictionaries
        """
        # Step 1: Calculate indicators (original logic)
        # Initialize indicator engine with strategy configs if not already done
        if not self.indicator_engine.indicators:
            # Convert dict configs to proper format using same mapping as training
            indicator_configs = self.strategy_config["indicators"]
            fixed_configs = []

            # Use same mapping as training for consistency
            name_mapping = {
                "bollinger_bands": "BollingerBands",
                "keltner_channels": "KeltnerChannels",
                "momentum": "Momentum",
                "volume_sma": "SMA",
                "atr": "ATR",
                "rsi": "RSI",
                "sma": "SMA",
                "ema": "EMA",
                "macd": "MACD",
            }

            for config in indicator_configs:
                if isinstance(config, dict) and "type" not in config:
                    config = config.copy()
                    indicator_name = config["name"].lower()
                    if indicator_name in name_mapping:
                        config["type"] = name_mapping[indicator_name]
                    else:
                        # Fallback: convert snake_case to PascalCase
                        config["type"] = "".join(
                            word.capitalize() for word in indicator_name.split("_")
                        )
                fixed_configs.append(config)

            from ..indicators.indicator_engine import IndicatorEngine

            self.indicator_engine = IndicatorEngine(indicators=fixed_configs)

        # Apply indicators to get calculated values
        indicators_df = self.indicator_engine.apply(historical_data)

        # Map indicators to original names for fuzzy processing (same as training)
        mapped_indicators = {}
        for config in self.strategy_config["indicators"]:
            original_name = config["name"]
            indicator_type = config["name"].upper()

            # Find matching columns
            for col in indicators_df.columns:
                if col.upper().startswith(indicator_type):
                    if indicator_type in ["SMA", "EMA"]:
                        # Use price ratio for moving averages
                        mapped_indicators[original_name] = (
                            historical_data["close"].iloc[-1]
                            / indicators_df[col].iloc[-1]
                        )
                    elif indicator_type == "MACD":
                        # Use main MACD line
                        if (
                            col.startswith("MACD_")
                            and "_signal_" not in col
                            and "_hist_" not in col
                        ):
                            mapped_indicators[original_name] = indicators_df[col].iloc[
                                -1
                            ]
                            break
                    else:
                        # Use raw values for other indicators
                        mapped_indicators[original_name] = indicators_df[col].iloc[-1]
                        break

        # Step 2: Generate fuzzy memberships
        fuzzy_values: dict[str, Any] = {}
        logger.debug(
            f"🔀 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Generating fuzzy memberships for {len(mapped_indicators)} indicators"
        )

        for indicator_name, indicator_value in mapped_indicators.items():
            if indicator_name in self.strategy_config["fuzzy_sets"]:
                # Fuzzify this indicator
                membership_result = self.fuzzy_engine.fuzzify(
                    indicator_name, indicator_value
                )
                fuzzy_values.update(membership_result)
                logger.debug(
                    f"🔀 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Fuzzified {indicator_name}={indicator_value:.4f} → {len(membership_result)} memberships"
                )

        logger.debug(
            f"🔀 [{cast(pd.Timestamp, current_bar.name).strftime('%Y-%m-%d %H:%M') if hasattr(current_bar, 'name') else 'Unknown'}] Total fuzzy features: {len(fuzzy_values)}"
        )

        return mapped_indicators, fuzzy_values

    def _initialize_fuzzy_engine(self) -> FuzzyEngine:
        """Initialize fuzzy engine from strategy configuration.

        Returns:
            FuzzyEngine instance configured with strategy fuzzy sets
        """
        # Use the same approach as training system - load directly from dict
        from ..fuzzy.config import FuzzyConfigLoader

        strategy_fuzzy_sets = self.strategy_config.get("fuzzy_sets", {})
        if not strategy_fuzzy_sets:
            raise ValueError("No fuzzy_sets found in strategy configuration")

        # Load fuzzy config directly from the strategy fuzzy_sets
        fuzzy_config = FuzzyConfigLoader.load_from_dict(strategy_fuzzy_sets)

        return FuzzyEngine(fuzzy_config)

    def _load_strategy_config(self, config_path: str) -> dict[str, Any]:
        """Load strategy configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Strategy configuration dictionary
        """
        path_obj = Path(config_path)
        if not path_obj.exists():
            raise FileNotFoundError(f"Strategy config not found: {path_obj}")

        with open(path_obj) as f:
            config = yaml.safe_load(f)

        # Validate required sections
        required_sections = ["name", "indicators", "fuzzy_sets", "model"]
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing required configuration section: {section}")

        return config

    def _load_model_from_path(self, model_path: str) -> tuple:
        """Load model from specific path.

        Args:
            model_path: Path to model directory

        Returns:
            Tuple of (model, metadata)
        """
        # Parse path to extract strategy/symbol/timeframe
        path_parts = Path(model_path).name.split("_")
        if len(path_parts) < 3:
            raise ValueError(f"Invalid model path format: {model_path}")

        symbol = path_parts[0]
        timeframe_version = "_".join(path_parts[1:])

        # Split timeframe and version
        if "_v" in timeframe_version:
            parts = timeframe_version.split("_v")
            timeframe = parts[0]
            version = "v" + parts[1]  # Re-add the 'v' prefix
        elif timeframe_version.endswith("_latest"):
            timeframe = timeframe_version.replace("_latest", "")
            version = None  # Let model storage handle latest
        else:
            timeframe = timeframe_version
            version = None

        return self.model_loader.load_model(
            strategy_name=self.strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            version=version,
        )

    def _load_model_for_symbol(self, symbol: str, timeframe: str) -> tuple:
        """Load the appropriate model for a symbol/timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Timeframe

        Returns:
            Tuple of (model, metadata)
        """
        return self.model_loader.load_model(
            strategy_name=self.strategy_name, symbol=symbol, timeframe=timeframe
        )

    def _prepare_context(
        self,
        symbol: str,
        current_bar: pd.Series,
        historical_data: pd.DataFrame,
        indicators: dict[str, float],
        fuzzy_memberships: dict[str, float],
        portfolio_state: dict[str, Any],
    ) -> DecisionContext:
        """Prepare complete context for decision making.

        Args:
            symbol: Trading symbol
            current_bar: Current price bar
            historical_data: Historical price data
            indicators: Current indicator values
            fuzzy_memberships: Current fuzzy membership values
            portfolio_state: Portfolio state information

        Returns:
            DecisionContext with all relevant information
        """
        # Get or create position state
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)

        position_state = self.position_states[symbol]

        # Get recent decisions for this symbol
        recent_decisions = [
            d
            for d in self.decision_history[-20:]  # Last 20 decisions
            if hasattr(d.reasoning, "symbol") and d.reasoning.get("symbol") == symbol
        ]

        return DecisionContext(
            current_bar=current_bar,
            recent_bars=historical_data.tail(20),  # Last 20 bars
            indicators=indicators,
            fuzzy_memberships=fuzzy_memberships,
            current_position=position_state.position,
            position_entry_price=position_state.entry_price,
            position_holding_period=position_state.holding_period,
            unrealized_pnl=position_state.unrealized_pnl,
            portfolio_value=portfolio_state.get("total_value", 0),
            available_capital=portfolio_state.get("available_capital", 0),
            recent_decisions=recent_decisions,
            last_signal_time=position_state.last_signal_time,
        )

    def _apply_orchestrator_logic(
        self, decision: TradingDecision, context: DecisionContext
    ) -> TradingDecision:
        """Apply additional orchestrator-level logic beyond the neural network.

        Args:
            decision: Initial decision from neural network
            context: Decision context

        Returns:
            Final decision after orchestrator logic
        """
        original_signal = decision.signal

        # Get orchestrator config if available
        orchestrator_config = self.strategy_config.get("orchestrator", {})

        # Risk check: Maximum position size
        max_position_size = orchestrator_config.get("max_position_size", 0.95)
        if context.portfolio_value > 0:
            current_exposure = (
                context.portfolio_value - context.available_capital
            ) / context.portfolio_value
            if current_exposure > max_position_size and decision.signal == Signal.BUY:
                decision.signal = Signal.HOLD
                decision.reasoning["orchestrator_override"] = (
                    f"Position size limit ({max_position_size:.0%})"
                )

        # Mode-specific logic
        mode_config = orchestrator_config.get("modes", {}).get(self.mode, {})

        if self.mode != "backtest":
            # More strict in live modes
            if context.available_capital < 1000:  # Minimum capital threshold
                decision.signal = Signal.HOLD
                decision.reasoning["orchestrator_override"] = "Insufficient capital"

        # Apply mode-specific confidence threshold
        mode_confidence_threshold = mode_config.get("confidence_threshold")
        if (
            mode_confidence_threshold
            and decision.confidence < mode_confidence_threshold
        ):
            decision.signal = Signal.HOLD
            decision.reasoning["orchestrator_override"] = (
                f"Confidence below {self.mode} threshold ({mode_confidence_threshold})"
            )

        # Special live trading safety
        if self.mode == "live":
            require_confirmation = mode_config.get("require_confirmation", False)
            if require_confirmation and decision.signal != Signal.HOLD:
                # In a real system, this might check for additional confirmation
                # For now, we'll just apply higher confidence requirement
                if decision.confidence < 0.8:
                    decision.signal = Signal.HOLD
                    decision.reasoning["orchestrator_override"] = (
                        "Live trading requires high confidence"
                    )

        # Add orchestrator metadata
        decision.reasoning["orchestrator"] = {
            "original_signal": original_signal.value,
            "final_signal": decision.signal.value,
            "mode": self.mode,
            "position_state": context.current_position.value,
            "applied_overrides": decision.reasoning.get("orchestrator_override")
            is not None,
        }

        return decision

    def _update_state(
        self, symbol: str, decision: TradingDecision, context: DecisionContext
    ):
        """Update internal state after decision.

        Args:
            symbol: Trading symbol
            decision: Final trading decision
            context: Decision context
        """
        # Get or create position state
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)

        # Update position state
        position_state = self.position_states[symbol]
        position_state.update_from_decision(decision, context.current_bar)

        # Add symbol to decision reasoning for tracking
        decision.reasoning["symbol"] = symbol

        # Add to history
        self.decision_history.append(decision)
        if len(self.decision_history) > self.max_history:
            self.decision_history.pop(0)

    def get_position_state(self, symbol: str) -> PositionState:
        """Get current position state for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            PositionState for the symbol
        """
        if symbol not in self.position_states:
            self.position_states[symbol] = PositionState(symbol)
        return self.position_states[symbol]

    def get_decision_history(
        self, symbol: Optional[str] = None, limit: int = 20
    ) -> list[TradingDecision]:
        """Get recent decision history.

        Args:
            symbol: Filter by symbol (None for all)
            limit: Maximum number of decisions to return

        Returns:
            List of recent decisions
        """
        decisions = self.decision_history[-limit:]

        if symbol:
            decisions = [d for d in decisions if d.reasoning.get("symbol") == symbol]

        return decisions

    def reset_state(self, symbol: Optional[str] = None):
        """Reset orchestrator state.

        Args:
            symbol: Reset specific symbol (None for all)
        """
        if symbol:
            if symbol in self.position_states:
                self.position_states[symbol] = PositionState(symbol)
        else:
            self.position_states.clear()
            self.decision_history.clear()
