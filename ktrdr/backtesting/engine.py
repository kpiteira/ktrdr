"""Backtesting engine for strategy evaluation.

Uses ModelBundle (single model load), FeatureCache (pre-computed features),
and DecisionFunction (stateless decisions) in a clean pipeline. The
DecisionOrchestrator is not imported — it is preserved for future paper/live
trading use (see DESIGN.md for rationale).
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, cast

import pandas as pd
from opentelemetry import trace

from .. import get_logger
from ..async_infrastructure.cancellation import CancellationToken
from ..async_infrastructure.progress_bridge import ProgressBridge
from ..data.repository import DataRepository
from ..decision.base import Signal
from .checkpoint_restore import BacktestResumeContext
from .decision_function import DecisionFunction
from .feature_cache import FeatureCache
from .model_bundle import ModelBundle
from .performance import PerformanceMetrics, PerformanceTracker
from .position_manager import Position, PositionManager, PositionStatus, Trade

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtesting run."""

    strategy_config_path: str
    model_path: Optional[str]
    symbol: str
    timeframe: str
    start_date: str
    end_date: str
    initial_capital: float = 100000.0
    commission: float = 0.001  # 0.1%
    slippage: float = 0.0005  # 0.05%
    timeframes: list[str] = field(default_factory=list)

    def get_all_timeframes(self) -> list[str]:
        """Return all timeframes for this backtest.

        If explicit timeframes list is set, returns it.
        Otherwise falls back to [self.timeframe] for backward compatibility.
        """
        return self.timeframes if self.timeframes else [self.timeframe]


@dataclass
class BacktestResults:
    """Comprehensive backtesting results."""

    strategy_name: str
    symbol: str
    timeframe: str
    config: BacktestConfig
    trades: list[Trade]
    metrics: PerformanceMetrics
    equity_curve: pd.DataFrame
    start_time: pd.Timestamp
    end_time: pd.Timestamp
    execution_time_seconds: float

    def to_dict(self) -> dict[str, Any]:
        """Convert results to dictionary."""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "execution_time_seconds": self.execution_time_seconds,
            "config": {
                "initial_capital": self.config.initial_capital,
                "commission": self.config.commission,
                "slippage": self.config.slippage,
                "start_date": self.config.start_date,
                "end_date": self.config.end_date,
            },
            "metrics": self.metrics.to_dict(),
            "trade_count": len(self.trades),
            "equity_curve_length": len(self.equity_curve),
        }


class BacktestingEngine:
    """Backtesting engine using ModelBundle + FeatureCache + DecisionFunction pipeline.

    Wires components directly instead of routing through DecisionOrchestrator.
    One model load, one position tracker, stateless decisions.
    """

    def __init__(self, config: BacktestConfig):
        """Initialize backtesting engine.

        Args:
            config: Backtesting configuration
        """
        self.config = config

        # Load model bundle (ONE load, CPU-safe)
        if not config.model_path:
            raise ValueError("model_path is required for backtesting")
        self.bundle = ModelBundle.load(config.model_path)
        self.strategy_name = self.bundle.metadata.strategy_name

        # Feature computation
        self.feature_cache = FeatureCache(
            config=self.bundle.strategy_config,
            model_metadata=self.bundle.metadata,
        )

        # Decision making (stateless)
        decisions_config = self._get_decisions_config()
        self.decide = DecisionFunction(
            model=self.bundle.model,
            feature_names=self.bundle.feature_names,
            decisions_config=decisions_config,
        )

        # Trade execution and tracking (SOLE position tracker)
        self.position_manager = PositionManager(
            initial_capital=config.initial_capital,
            commission=config.commission,
            slippage=config.slippage,
        )
        self.performance_tracker = PerformanceTracker()

        # Data loading
        self.repository = DataRepository()

        # Context data (external data from FRED, IB cross-pair, CFTC, etc.)
        # Loaded from model metadata if the model was trained with context data
        self._context_data: dict[str, pd.DataFrame] | None = None

    def _get_decisions_config(self) -> dict[str, Any]:
        """Extract decisions config as a plain dict from strategy_config."""
        sc = self.bundle.strategy_config
        # StrategyConfigurationV3 stores decisions as a dict or Pydantic model
        decisions = getattr(sc, "decisions", {})
        if hasattr(decisions, "model_dump"):
            return decisions.model_dump()
        if isinstance(decisions, dict):
            return decisions
        return {}

    def run(
        self,
        bridge: Optional[ProgressBridge] = None,
        cancellation_token: Optional[CancellationToken] = None,
        checkpoint_callback: Optional[Callable[..., None]] = None,
        resume_start_bar: Optional[int] = None,
    ) -> BacktestResults:
        """Execute the backtest simulation.

        Args:
            bridge: Optional ProgressBridge for async progress tracking
            cancellation_token: Optional CancellationToken for cancellation
            checkpoint_callback: Optional callback for periodic checkpoint saves
            resume_start_bar: Optional bar index to resume from (processed bar space)

        Returns:
            BacktestResults with trades, metrics, and equity curve

        Raises:
            CancellationError: If cancellation is requested
        """
        execution_start = time.time()

        logger.info(
            f"Starting backtest: {self.strategy_name} | "
            f"{self.config.symbol} {self.config.timeframe} | "
            f"{self.config.start_date} to {self.config.end_date}"
        )

        # 1. Load data
        multi_tf_data = self._load_historical_data()
        base_tf = self._get_base_timeframe()
        if base_tf not in multi_tf_data:
            available = list(multi_tf_data.keys())
            logger.warning(
                "Base timeframe %s not in loaded data %s; falling back to %s",
                base_tf,
                available,
                available[0],
            )
            base_tf = available[0]
        data = multi_tf_data[base_tf]

        if data.empty:
            raise ValueError(
                f"No data for {self.config.symbol} {self.config.timeframe}"
            )

        # 2. Load context data if model was trained with it
        if self.bundle.metadata.context_data_config:
            self._context_data = self._load_context_data(data)

        # 3. Pre-compute features (with context data if available)
        with tracer.start_as_current_span("backtest.feature_compute") as span:
            span.set_attribute("data.rows", len(data))
            self.feature_cache.compute_all_features(
                multi_tf_data, context_data=self._context_data
            )

        # 4. Simulate
        start_idx = (resume_start_bar + 50) if resume_start_bar is not None else 50
        if start_idx >= len(data):
            raise ValueError(
                f"Insufficient data for backtesting: {len(data)} bars "
                f"(need at least {start_idx + 1} for indicator warm-up)"
            )
        last_signal_time = None
        pending_signal = None
        pending_metadata = None

        for idx in range(start_idx, len(data)):
            bar = data.iloc[idx]
            close_price = bar["close"]
            timestamp = cast(pd.Timestamp, bar.name)

            # Execute pending signal from previous bar at THIS bar's open
            if pending_signal is not None:
                open_price = bar["open"]
                trade = self.position_manager.execute_trade(
                    signal=pending_signal,
                    price=open_price,
                    timestamp=timestamp,
                    symbol=self.config.symbol,
                    decision_metadata=pending_metadata,
                )
                if trade:
                    last_signal_time = timestamp
                pending_signal = None
                pending_metadata = None

            # Feature lookup
            features = self.feature_cache.get_features_for_timestamp(timestamp)
            if features is not None:
                # Decision (stateless — position passed in, not tracked internally)
                decision = self.decide(
                    features=features,
                    position=self.position_manager.current_position_status,
                    bar=bar,
                    last_signal_time=last_signal_time,
                )

                # Store non-HOLD as pending for next bar execution
                if decision.signal != Signal.HOLD:
                    pending_signal = decision.signal
                    pending_metadata = {"confidence": decision.confidence}

                # Track performance at close price (mark-to-market)
                self.position_manager.update_position(close_price, timestamp)
                portfolio_value = self.position_manager.get_portfolio_value(close_price)
                self.performance_tracker.update(
                    timestamp=timestamp,
                    price=close_price,
                    portfolio_value=portfolio_value,
                    position=self.position_manager.current_position_status,
                )
            else:
                portfolio_value = self.position_manager.get_portfolio_value(close_price)

            # Infrastructure (extracted to focused helpers)
            self._report_progress(
                idx, start_idx, len(data), timestamp, portfolio_value, bridge
            )
            self._maybe_checkpoint(idx, start_idx, timestamp, checkpoint_callback)
            self._check_cancellation(idx, start_idx, len(data), cancellation_token)

        # 5. Force-close and generate results
        self._force_close_position(data)
        return self._generate_results(execution_start)

    # ------------------------------------------------------------------
    # Infrastructure helpers
    # ------------------------------------------------------------------

    def _report_progress(
        self,
        idx: int,
        start_idx: int,
        total: int,
        timestamp: pd.Timestamp,
        portfolio_value: float,
        bridge: Optional[ProgressBridge],
    ) -> None:
        """Update ProgressBridge with simulation progress."""
        if not bridge:
            return
        if (idx - start_idx) % 50 != 0:
            return
        try:
            pct = ((idx - start_idx) / (total - start_idx)) * 100.0
            bridge._update_state(
                percentage=pct,
                message=f"Backtesting {self.config.symbol} {self.config.timeframe} [{timestamp}]",
                current_bar=idx - start_idx,
                total_bars=total - start_idx,
                current_date=str(timestamp),
                current_pnl=portfolio_value - self.config.initial_capital,
                total_trades=len(self.position_manager.get_trade_history()),
                win_rate=0.0,
            )
        except Exception as e:
            logger.warning(f"ProgressBridge update failed: {e}")

    def _maybe_checkpoint(
        self,
        idx: int,
        start_idx: int,
        timestamp: pd.Timestamp,
        callback: Optional[Callable[..., None]],
    ) -> None:
        """Invoke checkpoint callback periodically."""
        if not callback:
            return
        if (idx - start_idx) % 100 != 0:
            return
        try:
            callback(
                bar_index=idx - start_idx,
                timestamp=timestamp,
                engine=self,
            )
        except Exception as e:
            logger.warning(f"Checkpoint callback failed: {e}")

    def _check_cancellation(
        self,
        idx: int,
        start_idx: int,
        total: int,
        token: Optional[CancellationToken],
    ) -> None:
        """Check for cancellation request."""
        if not token:
            return
        if (idx - start_idx) % 100 != 0:
            return
        if token.is_cancelled_requested:
            pct = ((idx - start_idx) / (total - start_idx)) * 100
            logger.info(f"Backtest cancelled at bar {idx}/{total} ({pct:.1f}%)")
            from ..async_infrastructure.cancellation import CancellationError

            raise CancellationError(
                f"Backtest cancelled by user request at bar {idx}/{total}"
            )

    def _force_close_position(self, data: pd.DataFrame) -> None:
        """Force-close any open position at end of backtest."""
        final_bar = data.iloc[-1]
        final_price = final_bar["close"]
        final_timestamp = cast(pd.Timestamp, final_bar.name)
        self.position_manager.force_close_position(
            price=final_price,
            timestamp=final_timestamp,
            symbol=self.config.symbol,
            reason="End of backtest period",
        )

    # ------------------------------------------------------------------
    # Resume and reset
    # ------------------------------------------------------------------

    def resume_from_context(self, context: BacktestResumeContext) -> pd.DataFrame:
        """Resume backtesting engine state from a checkpoint context.

        Loads data, computes features, restores portfolio state and equity curve.
        After calling this, call run() with resume_start_bar=context.start_bar.

        Args:
            context: BacktestResumeContext with checkpoint data.

        Returns:
            The base timeframe DataFrame for the full date range.
        """
        logger.info(f"Resuming backtest from bar {context.start_bar}")

        # 1. Load data for full range
        multi_tf_data = self._load_historical_data()
        base_tf = self._get_base_timeframe()
        data = multi_tf_data[base_tf]

        if data.empty:
            raise ValueError(
                f"No data loaded for {self.config.symbol} {self.config.timeframe}"
            )

        logger.info(
            f"Loaded {len(data):,} bars from {data.index[0]} to {data.index[-1]}"
        )

        # 2. Load context data if model was trained with it
        if self.bundle.metadata.context_data_config:
            self._context_data = self._load_context_data(data)

        # 3. Compute features for full range
        self.feature_cache.compute_all_features(
            multi_tf_data, context_data=self._context_data
        )
        logger.info("Feature cache ready")

        # 3. Restore portfolio state
        self._restore_portfolio_state(context)

        # 4. Restore equity curve samples
        if context.equity_samples:
            self.performance_tracker.equity_curve = list(context.equity_samples)
            logger.info(f"Restored {len(context.equity_samples)} equity samples")

        return data

    def _restore_portfolio_state(self, context: BacktestResumeContext) -> None:
        """Restore portfolio state from checkpoint context."""
        self.position_manager.current_capital = context.cash
        logger.info(f"Restored cash: ${context.cash:,.2f}")

        if context.positions:
            pos_data = context.positions[0]
            self.position_manager.current_position = Position(
                status=PositionStatus(pos_data["status"]),
                entry_price=pos_data["entry_price"],
                entry_time=pd.Timestamp(pos_data["entry_date"]),
                quantity=pos_data["quantity"],
                current_price=pos_data.get("current_price", pos_data["entry_price"]),
                last_update_time=pd.Timestamp(pos_data["entry_date"]),
            )
            logger.info(
                f"Restored {pos_data['status']} position: "
                f"{pos_data['quantity']} @ ${pos_data['entry_price']:.4f}"
            )
        else:
            self.position_manager.current_position = None
            logger.info("No open position to restore (FLAT)")

        if context.trades:
            self.position_manager.trade_history = [
                self._dict_to_trade(td) for td in context.trades
            ]
            max_trade_id = max(t.trade_id for t in self.position_manager.trade_history)
            self.position_manager.next_trade_id = max_trade_id + 1
            logger.info(
                f"Restored {len(context.trades)} trades "
                f"(next_trade_id={self.position_manager.next_trade_id})"
            )
        else:
            self.position_manager.trade_history = []
            self.position_manager.next_trade_id = 1

    def _dict_to_trade(self, trade_data: dict) -> Trade:
        """Convert a trade dictionary back to a Trade object."""
        return Trade(
            trade_id=trade_data["trade_id"],
            symbol=trade_data["symbol"],
            side=trade_data["side"],
            entry_price=trade_data["entry_price"],
            entry_time=pd.Timestamp(trade_data["entry_time"]),
            exit_price=trade_data["exit_price"],
            exit_time=pd.Timestamp(trade_data["exit_time"]),
            quantity=trade_data["quantity"],
            gross_pnl=trade_data["gross_pnl"],
            commission=trade_data["commission"],
            slippage=trade_data["slippage"],
            net_pnl=trade_data["net_pnl"],
            holding_period_hours=trade_data["holding_period_hours"],
            max_favorable_excursion=trade_data["max_favorable_excursion"],
            max_adverse_excursion=trade_data["max_adverse_excursion"],
            decision_metadata=trade_data.get("decision_metadata", {}),
        )

    def reset(self):
        """Reset the backtesting engine for a new run."""
        self.position_manager.reset()
        self.performance_tracker.reset()

    # ------------------------------------------------------------------
    # Data loading and config access
    # ------------------------------------------------------------------

    def _get_base_timeframe(self) -> str:
        """Get the base timeframe from strategy config.

        Returns:
            Base timeframe string (e.g., "1h")
        """
        td = self.bundle.strategy_config.training_data
        if td and hasattr(td, "timeframes") and td.timeframes:
            base = getattr(td.timeframes, "base_timeframe", None)
            if base:
                return base
        return self.config.timeframe

    def _get_strategy_timeframes(self) -> list[str]:
        """Get all timeframes from strategy config.

        Returns:
            List of timeframes. For single-TF strategies, returns [config.timeframe].
        """
        td = self.bundle.strategy_config.training_data
        if td and hasattr(td, "timeframes") and td.timeframes:
            mode = getattr(td.timeframes, "mode", None)
            tf_list = getattr(td.timeframes, "timeframes", None)
            if mode and hasattr(mode, "value"):
                mode = mode.value
            if mode == "multi_timeframe" and tf_list and len(tf_list) >= 2:
                return list(tf_list)
        return [self.config.timeframe]

    def _load_context_data(self, primary_data: pd.DataFrame) -> dict[str, pd.DataFrame]:
        """Load context data from model metadata for backtesting.

        Mirrors the training pipeline's context data loading: reads
        context_data_config from model metadata, fetches from providers,
        aligns to primary data index.

        Args:
            primary_data: The base timeframe's OHLCV DataFrame (for index alignment).

        Returns:
            Dict mapping source_id to aligned DataFrames.

        Raises:
            RuntimeError: If context data cannot be fetched (API down, missing cache).
        """
        from ..config.models import ContextDataEntry
        from ..data.context.base import ContextDataAligner
        from ..data.context.registry import ContextDataProviderRegistry

        metadata = self.bundle.metadata
        if not metadata.context_data_config:
            return {}

        registry = ContextDataProviderRegistry()
        aligner = ContextDataAligner()
        primary_index = pd.DatetimeIndex(primary_data.index)

        # Derive date range from primary data
        start_dt = primary_index[0].to_pydatetime()
        end_dt = primary_index[-1].to_pydatetime()
        # Strip timezone for provider API calls
        if start_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=None)
        if end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)

        logger.info(
            f"Loading context data: {len(metadata.context_data_config)} entries "
            f"({start_dt.date()} to {end_dt.date()})"
        )

        context_config = metadata.context_data_config  # Already checked non-None above

        async def _fetch_all() -> dict[str, pd.DataFrame]:
            result: dict[str, pd.DataFrame] = {}
            for entry_dict in context_config:
                entry = ContextDataEntry(**entry_dict)
                provider_name = entry.provider

                try:
                    provider = registry.get(provider_name)
                except KeyError as e:
                    raise RuntimeError(
                        f"Context data provider '{provider_name}' not available. "
                        f"Model was trained with this provider but it's not registered. "
                        f"Available: {registry.available_providers()}"
                    ) from e

                try:
                    results = await provider.fetch(entry, start_dt, end_dt)
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to fetch context data from '{provider_name}': {e}. "
                        f"Context data is required for this model — "
                        f"backtest cannot proceed without it."
                    ) from e

                for ctx_result in results:
                    aligned = aligner.align(ctx_result.data, primary_index)
                    result[ctx_result.source_id] = aligned
                    logger.info(
                        f"  Context '{ctx_result.source_id}': "
                        f"{len(ctx_result.data)} raw → {len(aligned)} aligned rows"
                    )

            return result

        return asyncio.run(_fetch_all())

    def _load_historical_data(self) -> dict[str, pd.DataFrame]:
        """Load historical data for backtesting from cache.

        Uses config.get_all_timeframes() as the primary source of timeframes.
        This field is threaded from the API through the service layer, ensuring
        consistency with the strategy config's training_data.timeframes.

        Falls back to _get_strategy_timeframes() (from model bundle) if config
        doesn't have explicit timeframes set.

        Returns:
            Dict mapping timeframes to OHLCV DataFrames
        """
        with tracer.start_as_current_span("backtest.data_loading") as span:
            span.set_attribute("data.symbol", self.config.symbol)
            span.set_attribute("data.timeframe", self.config.timeframe)

            # Prefer config.get_all_timeframes() (threaded from API) over
            # strategy config extraction — more reliable for multi-TF models
            timeframes = self.config.get_all_timeframes()
            if len(timeframes) <= 1:
                # Fall back to strategy config if config has only a single timeframe
                # or none at all (e.g., older callers that don't pass timeframes)
                timeframes = self._get_strategy_timeframes()

            if len(timeframes) >= 2:
                from ..data.multi_timeframe_coordinator import (
                    MultiTimeframeCoordinator,
                )

                coordinator = MultiTimeframeCoordinator(self.repository)
                base_tf = self._get_base_timeframe()

                logger.info(
                    f"Loading multi-timeframe data: {timeframes} (base: {base_tf})"
                )

                multi_data = coordinator.load_multi_timeframe_data(
                    symbol=self.config.symbol,
                    timeframes=timeframes,
                    start_date=self.config.start_date,
                    end_date=self.config.end_date,
                    base_timeframe=base_tf,
                )

                total_rows = sum(len(df) for df in multi_data.values())
                span.set_attribute("data.rows", total_rows)
                return multi_data
            else:
                data = self.repository.load_from_cache(
                    symbol=self.config.symbol,
                    timeframe=self.config.timeframe,
                )

                if self.config.start_date:
                    start_date = pd.to_datetime(self.config.start_date)
                    if (
                        hasattr(data.index, "tz")
                        and data.index.tz is not None
                        and start_date.tz is None
                    ):
                        start_date = start_date.tz_localize("UTC")
                    data = data[data.index >= start_date]

                if self.config.end_date:
                    end_date = pd.to_datetime(self.config.end_date)
                    if (
                        hasattr(data.index, "tz")
                        and data.index.tz is not None
                        and end_date.tz is None
                    ):
                        end_date = end_date.tz_localize("UTC")
                    data = data[data.index <= end_date]

                span.set_attribute("data.rows", len(data))
                return {self.config.timeframe: data}

    def _generate_results(self, execution_start: float) -> BacktestResults:
        """Compile backtest results.

        Args:
            execution_start: time.time() when execution started

        Returns:
            BacktestResults object
        """
        trades = self.position_manager.get_trade_history()
        equity_curve = self.performance_tracker.get_equity_curve()

        start_date = (
            pd.to_datetime(self.config.start_date) if self.config.start_date else None
        )
        end_date = (
            pd.to_datetime(self.config.end_date) if self.config.end_date else None
        )

        metrics = self.performance_tracker.calculate_metrics(
            trades=trades,
            initial_capital=self.config.initial_capital,
            start_date=start_date,
            end_date=end_date,
        )

        return BacktestResults(
            strategy_name=self.strategy_name,
            symbol=self.config.symbol,
            timeframe=self.config.timeframe,
            config=self.config,
            trades=trades,
            metrics=metrics,
            equity_curve=equity_curve,
            start_time=start_date or pd.Timestamp.now(),
            end_time=end_date or pd.Timestamp.now(),
            execution_time_seconds=time.time() - execution_start,
        )
