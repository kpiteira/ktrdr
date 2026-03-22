"""
Training Pipeline - Pure training work functions.

This module contains pure functions for training operations, EXTRACTED from
both local (StrategyTrainer) and host (TrainingService) training paths to
eliminate code duplication.

Design Philosophy:
- NO callbacks, NO async - pure synchronous functions
- Orchestrators wrap these functions for progress reporting and cancellation
- Each function is stateless and testable in isolation
- Code is EXTRACTED from existing implementations, not rewritten
"""

from typing import TYPE_CHECKING, Any, Optional

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

# OpenTelemetry imports for instrumentation
from opentelemetry import trace
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
)

from ktrdr import get_logger
from ktrdr.async_infrastructure.cancellation import CancellationToken
from ktrdr.config.models import FuzzySetDefinition
from ktrdr.data.multi_timeframe_coordinator import MultiTimeframeCoordinator
from ktrdr.data.repository import DataRepository
from ktrdr.fuzzy.engine import FuzzyEngine
from ktrdr.indicators.indicator_engine import IndicatorEngine

# BUILT_IN_INDICATORS import removed - no longer needed (IndicatorEngine handles it)
from ktrdr.neural.models.mlp import MLPTradingModel
from ktrdr.training.fuzzy_neural_processor import FuzzyNeuralProcessor
from ktrdr.training.model_trainer import ModelTrainer
from ktrdr.training.zigzag_labeler import ZigZagLabeler

if TYPE_CHECKING:
    from ktrdr.training.checkpoint_restore import TrainingResumeContext

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)


class TrainingPipeline:
    """
    Pure training work functions - no callbacks, no async.

    This class provides stateless, synchronous methods for:
    - Data loading and validation
    - Feature engineering (indicators, fuzzy memberships)
    - Model creation and training
    - Model evaluation

    Orchestrators (LocalTrainingOrchestrator, HostTrainingOrchestrator) wrap
    these methods differently for their execution environments.
    """

    # Class-level storage for triple barrier metadata (set by create_labels)
    _sample_weights: torch.Tensor | None = None
    _cusum_event_mask: pd.Series | None = None

    @staticmethod
    def get_sample_weights() -> torch.Tensor | None:
        """Return sample weights from the last create_labels() call.

        Only populated when source='triple_barrier' and compute_weights=True.
        Weights are normalized (mean=1.0) for compatibility with loss functions.
        """
        return TrainingPipeline._sample_weights

    @staticmethod
    def get_cusum_event_mask() -> pd.Series | None:
        """Return CUSUM event mask from the last create_labels() call.

        Boolean Series where True = event bar selected by CUSUM filter.
        Used by orchestrator for feature/label alignment when CUSUM is active.
        """
        return TrainingPipeline._cusum_event_mask

    # ======================================================================
    # DATA LOADING METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer::_load_price_data
    # ======================================================================

    @staticmethod
    def load_market_data(
        symbol: str,
        timeframes: list[str],
        start_date: str,
        end_date: str,
        repository: Optional[DataRepository] = None,
        multi_timeframe_coordinator: Optional[MultiTimeframeCoordinator] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Load price data for training with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._load_price_data() (train_strategy.py:563-622)

        This implementation now uses cached data only (no downloads during training).
        User must run `ktrdr data load` before training.

        Args:
            symbol: Trading symbol
            timeframes: List of timeframes for multi-timeframe training
            start_date: Start date
            end_date: End date
            repository: Optional DataRepository instance (will create if not provided)
            multi_timeframe_coordinator: Optional coordinator (will create if not provided)

        Returns:
            Dictionary mapping timeframes to OHLCV DataFrames

        Raises:
            ValueError: If no timeframes successfully loaded
            DataNotFoundError: If data not cached (must run `ktrdr data load` first)
        """
        # Create telemetry span for data loading phase
        with tracer.start_as_current_span("training.data_loading") as span:
            # Set span attributes
            span.set_attribute("data.symbol", symbol)
            span.set_attribute("data.timeframes", ",".join(timeframes))
            span.set_attribute("progress.phase", "data_loading")

            # Initialize components if not provided
            if repository is None:
                repository = DataRepository()

            if multi_timeframe_coordinator is None:
                multi_timeframe_coordinator = MultiTimeframeCoordinator(repository)

            # Handle single timeframe case (backward compatibility)
            # EXTRACTED FROM: train_strategy.py:584-592
            if len(timeframes) == 1:
                timeframe = timeframes[0]
                # Load from cache only - training uses pre-downloaded data
                data = repository.load_from_cache(
                    symbol=symbol,
                    timeframe=timeframe,
                    start_date=start_date,
                    end_date=end_date,
                )

                # Add data metrics to span
                span.set_attribute("data.rows", len(data))
                span.set_attribute("data.columns", len(data.columns))

                return {timeframe: data}

            # Multi-timeframe case - use first timeframe (highest frequency) as base
            # EXTRACTED FROM: train_strategy.py:594-622
            base_timeframe = timeframes[0]  # Always use first timeframe as base
            multi_data = multi_timeframe_coordinator.load_multi_timeframe_data(
                symbol=symbol,
                timeframes=timeframes,
                start_date=start_date,
                end_date=end_date,
                base_timeframe=base_timeframe,
            )

            # Validate multi-timeframe loading success
            if len(multi_data) != len(timeframes):
                available_tfs = list(multi_data.keys())
                missing_tfs = set(timeframes) - set(available_tfs)
                logger.warning(
                    f"⚠️ Multi-timeframe loading partial success: {len(multi_data)}/{len(timeframes)} timeframes loaded. "
                    f"Missing: {missing_tfs}, Available: {available_tfs}"
                )

                # Continue with available timeframes but warn user
                if len(multi_data) == 0:
                    raise ValueError(f"No timeframes successfully loaded for {symbol}")
            else:
                logger.info(
                    f"✅ Multi-timeframe data loaded successfully: {', '.join(multi_data.keys())}"
                )

            # Add data metrics to span (total rows across all timeframes)
            total_rows = sum(len(df) for df in multi_data.values())
            total_cols = sum(len(df.columns) for df in multi_data.values())
            span.set_attribute("data.rows", total_rows)
            span.set_attribute("data.columns", total_cols)

            return multi_data

    # _filter_data_by_date_range() method removed
    # Date filtering now handled by DataRepository.load_from_cache() which is more efficient
    # and provides consistent behavior across local and host execution paths

    @staticmethod
    def validate_data_quality(
        data: dict[str, pd.DataFrame], min_rows: int = 100
    ) -> dict[str, Any]:
        """
        Validate that loaded data has sufficient quality for training.

        This is a NEW method (not extracted) that provides basic validation
        to catch common data issues early.

        Args:
            data: Dictionary mapping timeframes to DataFrames
            min_rows: Minimum required number of rows per timeframe

        Returns:
            dict: Validation results containing:
                - valid (bool): Whether all timeframes pass validation
                - timeframes_checked (int): Number of timeframes checked
                - issues (list): List of validation issues found
                - total_rows (int): Total rows across all timeframes
        """
        result: dict[str, Any] = {
            "valid": True,
            "timeframes_checked": len(data),
            "issues": [],
            "total_rows": 0,
        }

        required_columns = ["open", "high", "low", "close", "volume"]

        for timeframe, df in data.items():
            result["total_rows"] += len(df)

            # Check row count
            if len(df) < min_rows:
                result["valid"] = False
                result["issues"].append(
                    f"{timeframe}: Only {len(df)} rows (< {min_rows} required)"
                )

            # Check required columns
            missing_cols = [col for col in required_columns if col not in df.columns]
            if missing_cols:
                result["valid"] = False
                result["issues"].append(f"{timeframe}: Missing columns {missing_cols}")

            # Check for excessive NaN values (only if columns exist)
            if not df.empty and not missing_cols:
                nan_pct = (
                    df[required_columns].isnull().sum().sum()
                    / (len(df) * len(required_columns))
                ) * 100
                if nan_pct > 5.0:  # More than 5% NaN is problematic
                    result["valid"] = False
                    result["issues"].append(
                        f"{timeframe}: {nan_pct:.1f}% missing values (> 5% threshold)"
                    )

        if result["valid"]:
            logger.info(
                f"Data validation passed: {result['timeframes_checked']} timeframes, "
                f"{result['total_rows']} total rows"
            )
        else:
            logger.warning(
                f"Data validation failed with {len(result['issues'])} issues: "
                f"{result['issues']}"
            )

        return result

    # ======================================================================
    # FEATURE ENGINEERING METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def calculate_indicators(
        price_data: dict[str, pd.DataFrame],
        indicator_configs: dict[str, dict[str, Any]],
    ) -> dict[str, pd.DataFrame]:
        """
        Calculate technical indicators (unified single/multi-timeframe approach).

        Single-timeframe is just multi-timeframe with one key. This eliminates
        code duplication and ensures consistent behavior.

        Args:
            price_data: Dictionary mapping timeframes to OHLCV DataFrames
            indicator_configs: V3 format dict mapping indicator_id to definition
                Example: {"rsi_14": {"type": "rsi", "period": 14}}

        Returns:
            Dictionary mapping timeframes to DataFrames with indicators
        """
        # Create telemetry span for indicators phase
        with tracer.start_as_current_span("training.indicators") as span:
            # Set span attributes
            span.set_attribute("indicators.count", len(indicator_configs))
            span.set_attribute("indicators.timeframes", ",".join(price_data.keys()))
            span.set_attribute("progress.phase", "indicators")

            logger.info(
                f"🔧 TrainingPipeline.calculate_indicators() - Processing {len(price_data)} timeframe(s) "
                f"with {len(indicator_configs)} indicator(s)"
            )

            # Create indicator engine ONCE - No computation on sample data (Phase 7)!
            indicator_engine = IndicatorEngine(indicators=indicator_configs)

            # Apply to all timeframes (single-timeframe is just a 1-item dict)
            # CRITICAL: Don't pass indicator_configs to prevent duplicate engine creation!
            # NOTE: prefix_columns=False because training handles prefixing later in
            # FuzzyNeuralProcessor.prepare_multi_timeframe_input(), where the actual
            # column prefixing is performed by its _align_multi_timeframe_features helper.
            # Backtesting uses prefix_columns=True (default) to prevent indicator collisions.
            indicator_results = indicator_engine.apply_multi_timeframe(
                price_data, prefix_columns=False
            )

            # Combine price data with indicator results per timeframe
            combined_results = {}

            for timeframe, tf_indicators in indicator_results.items():
                tf_price_data = price_data[timeframe]

                # Phase 3 simplified: Just combine - feature_id aliases already exist!
                # Use pd.concat to avoid DataFrame fragmentation (more efficient than iterative assignment)
                new_cols = [
                    col
                    for col in tf_indicators.columns
                    if col not in tf_price_data.columns
                ]
                if new_cols:
                    result = pd.concat([tf_price_data, tf_indicators[new_cols]], axis=1)
                else:
                    result = tf_price_data.copy()

                # Safety check: replace any inf values with NaN, then fill NaN with 0
                result = result.replace([np.inf, -np.inf], np.nan).fillna(0.0)

                combined_results[timeframe] = result

            return combined_results

    @staticmethod
    def generate_fuzzy_memberships(
        indicators: dict[str, pd.DataFrame], fuzzy_configs: dict[str, Any]
    ) -> dict[str, pd.DataFrame]:
        """
        Generate fuzzy membership values (unified single/multi-timeframe approach).

        Single-timeframe is just multi-timeframe with one key. This eliminates
        code duplication and ensures consistent behavior.

        ROOT CAUSE FIX: Multi-timeframe method now passes context_data to fuzzify(),
        fixing price_ratio transform errors.

        Args:
            indicators: Dictionary mapping timeframes to technical indicators DataFrames
            fuzzy_configs: Fuzzy set configurations

        Returns:
            Dictionary mapping timeframes to DataFrames with fuzzy membership values
        """
        # Create telemetry span for fuzzy computation phase
        with tracer.start_as_current_span("training.fuzzy_computation") as span:
            # Set span attributes
            span.set_attribute("fuzzy_sets.count", len(fuzzy_configs))
            span.set_attribute("fuzzy_sets.timeframes", ",".join(indicators.keys()))
            span.set_attribute("progress.phase", "fuzzy_computation")

            logger.info(
                f"🔧 TrainingPipeline.generate_fuzzy_memberships() - Processing {len(indicators)} timeframe(s) "
                f"with {len(fuzzy_configs)} fuzzy indicator(s)"
            )

            # Convert legacy format to v3 FuzzySetDefinition format
            # Legacy: {indicator_name: {membership_name: {...}}}
            # V3: {fuzzy_set_id: FuzzySetDefinition(indicator=..., membership=...)}
            v3_config: dict[str, FuzzySetDefinition] = {}
            for indicator_name, memberships in fuzzy_configs.items():
                # Filter out non-membership fields like "input_transform"
                mf_data: dict[str, Any] = {
                    k: v
                    for k, v in memberships.items()
                    if k != "input_transform" and isinstance(v, dict)
                }
                mf_data["indicator"] = indicator_name
                v3_config[indicator_name] = FuzzySetDefinition(**mf_data)

            # Initialize fuzzy engine with v3 config
            fuzzy_engine = FuzzyEngine(v3_config)

            # Always use multi-timeframe method (single-timeframe is just a 1-item dict)
            return fuzzy_engine.generate_multi_timeframe_memberships(
                indicators, v3_config
            )

    @staticmethod
    def create_features(
        fuzzy_data: dict[str, pd.DataFrame], feature_config: dict[str, Any]
    ) -> tuple[torch.Tensor, list[str]]:
        """
        Engineer features for neural network training using pure fuzzy approach.

        EXTRACTED FROM: StrategyTrainer._engineer_features()
        (train_strategy.py:849-878)

        Args:
            fuzzy_data: Dictionary mapping timeframes to fuzzy membership values
            feature_config: Feature engineering configuration

        Returns:
            Tuple of (features tensor, feature names list)
        """
        logger.info(
            f"🔧 TrainingPipeline.create_features() - Creating features from {len(fuzzy_data)} timeframe(s)"
        )

        # Pure neuro-fuzzy architecture: only fuzzy memberships as inputs
        processor = FuzzyNeuralProcessor(feature_config)

        # Handle single timeframe case (backward compatibility)
        if len(fuzzy_data) == 1:
            timeframe, tf_fuzzy_data = next(iter(fuzzy_data.items()))
            features, feature_names = processor.prepare_input(tf_fuzzy_data)
            logger.info(
                f"✅ Created {features.shape[1]} features from {features.shape[0]} samples"
            )
            return features, feature_names

        # Multi-timeframe case - use the new multi-timeframe method
        features, feature_names = processor.prepare_multi_timeframe_input(fuzzy_data)
        logger.info(
            f"✅ Created {features.shape[1]} features from {features.shape[0]} samples (multi-timeframe)"
        )
        return features, feature_names

    @staticmethod
    def create_labels(
        price_data: dict[str, pd.DataFrame], label_config: dict[str, Any]
    ) -> torch.Tensor:
        """
        Generate training labels with support for ZigZag (classification),
        forward return (regression), context (3-class classification),
        and regime (4-class classification) modes.

        Args:
            price_data: Dictionary mapping timeframes to OHLCV data
            label_config: Label generation configuration. Key fields:
                - source: "zigzag" (default), "forward_return", "context", or "regime"
                - For zigzag: zigzag_threshold, label_lookahead
                - For forward_return: horizon (int)
                - For context: horizon, bullish_threshold, bearish_threshold
                - For regime: horizon, trending_threshold, vol_crisis_threshold, vol_lookback

        Returns:
            Tensor of labels:
                - LongTensor for zigzag (BUY=0, SELL=1, HOLD=2)
                - FloatTensor for forward_return (continuous)
                - LongTensor for context (BULLISH=0, BEARISH=1, NEUTRAL=2)
                - LongTensor for regime (4-class)
        """
        # Clear stale state from prior runs
        TrainingPipeline._sample_weights = None
        TrainingPipeline._cusum_event_mask = None

        source = label_config.get("source", "zigzag")

        # Resolve base timeframe price data
        if len(price_data) == 1:
            timeframe, tf_price_data = next(iter(price_data.items()))
            logger.debug(f"Generating labels from {timeframe} data")
        else:
            timeframe_list = sorted(price_data.keys())
            frequency_order = TrainingPipeline._sort_timeframes_by_frequency(
                timeframe_list
            )
            base_timeframe = frequency_order[0]
            tf_price_data = price_data[base_timeframe]
            logger.debug(
                f"Generating labels from base timeframe {base_timeframe} "
                f"(out of {frequency_order}) - matching features"
            )

        if source == "forward_return":
            from ktrdr.training.forward_return_labeler import ForwardReturnLabeler

            horizon = label_config.get("horizon", 20)
            logger.info(
                f"TrainingPipeline.create_labels() - Forward return labels "
                f"(horizon={horizon}, bars={len(tf_price_data)})"
            )
            fr_labeler = ForwardReturnLabeler(horizon=horizon)
            labels = fr_labeler.generate_labels(tf_price_data)
            label_tensor: torch.Tensor = torch.FloatTensor(labels.values)

            stats = fr_labeler.get_label_statistics(labels)
            logger.info(
                f"Generated {len(label_tensor)} forward return labels - "
                f"mean={stats['mean']:.6f}, std={stats['std']:.6f}, "
                f"positive={stats['pct_positive']:.1f}%, negative={stats['pct_negative']:.1f}%"
            )
            return label_tensor

        if source == "context":
            from ktrdr.training.context_labeler import ContextLabeler

            horizon = label_config.get("horizon", 5)
            bullish_threshold = label_config.get("bullish_threshold", 0.005)
            bearish_threshold = label_config.get("bearish_threshold", -0.005)
            logger.info(
                f"TrainingPipeline.create_labels() - Context labels "
                f"(horizon={horizon}, bullish={bullish_threshold}, "
                f"bearish={bearish_threshold}, bars={len(tf_price_data)})"
            )
            ctx_labeler = ContextLabeler(
                horizon=horizon,
                bullish_threshold=bullish_threshold,
                bearish_threshold=bearish_threshold,
            )
            labels = ctx_labeler.label(tf_price_data)
            # Drop trailing NaN bars (last `horizon` bars have no future data)
            valid_labels = labels.dropna()
            label_tensor = torch.LongTensor(valid_labels.values.astype(int))

            unique, counts = torch.unique(label_tensor, return_counts=True)
            dist = {int(u): int(c) for u, c in zip(unique, counts)}
            logger.info(
                f"Generated {len(label_tensor)} context labels - Distribution: {dist}"
            )
            return label_tensor

        if source == "regime":
            from ktrdr.training.multi_scale_regime_labeler import (
                MultiScaleRegimeLabeler,
            )

            macro_atr_mult = label_config.get("macro_atr_mult", 3.0)
            micro_atr_mult = label_config.get("micro_atr_mult", 1.0)
            atr_period = label_config.get("atr_period", 14)
            vol_lookback = label_config.get("vol_lookback", 120)
            vol_crisis_threshold = label_config.get("vol_crisis_threshold", 2.0)
            progression_tolerance = label_config.get("progression_tolerance", 0.5)
            logger.info(
                f"TrainingPipeline.create_labels() - Regime labels (multi-scale zigzag) "
                f"(macro_atr_mult={macro_atr_mult}, micro_atr_mult={micro_atr_mult}, "
                f"atr_period={atr_period}, vol_crisis_threshold={vol_crisis_threshold}, "
                f"vol_lookback={vol_lookback}, bars={len(tf_price_data)})"
            )
            regime_labeler = MultiScaleRegimeLabeler(
                macro_atr_mult=macro_atr_mult,
                micro_atr_mult=micro_atr_mult,
                atr_period=atr_period,
                vol_lookback=vol_lookback,
                vol_crisis_threshold=vol_crisis_threshold,
                progression_tolerance=progression_tolerance,
            )
            labels = regime_labeler.generate_labels(tf_price_data)
            # Drop NaN labels: bars outside macro zigzag segments and
            # bars with insufficient ATR/vol data are NaN.
            valid_mask = labels.notna()
            valid_labels = labels[valid_mask]
            label_tensor = torch.LongTensor(valid_labels.values.astype(int))

            unique, counts = torch.unique(label_tensor, return_counts=True)
            dist = {int(u): int(c) for u, c in zip(unique, counts)}
            logger.info(
                f"Generated {len(label_tensor)} regime labels - Distribution: {dist}"
            )
            return label_tensor

        if source == "triple_barrier":
            from ktrdr.training.triple_barrier_labeler import TripleBarrierLabeler

            pt_multiplier = label_config.get("pt_multiplier", 2.0)
            sl_multiplier = label_config.get("sl_multiplier", 1.5)
            max_holding_period = label_config.get("max_holding_period", 50)
            vol_span = label_config.get("vol_span", 50)
            vol_method = label_config.get("vol_method", "atr")
            logger.info(
                f"TrainingPipeline.create_labels() - Triple barrier labels "
                f"(pt={pt_multiplier}, sl={sl_multiplier}, "
                f"max_hold={max_holding_period}, vol_span={vol_span}, "
                f"vol_method={vol_method}, bars={len(tf_price_data)})"
            )

            tb_labeler = TripleBarrierLabeler(
                pt_multiplier=pt_multiplier,
                sl_multiplier=sl_multiplier,
                max_holding_period=max_holding_period,
                vol_span=vol_span,
                vol_method=vol_method,
            )

            # Optionally apply CUSUM filter
            cusum_threshold = label_config.get("cusum_threshold")
            if cusum_threshold is not None:
                from ktrdr.training.cusum_filter import CUSUMFilter

                cusum_mult = label_config.get("cusum_multiplier", 0.5)
                filt = CUSUMFilter(
                    threshold=cusum_threshold if cusum_threshold > 0 else None,
                    cusum_multiplier=cusum_mult,
                    vol_span=vol_span,
                )
                events = filt.filter(tf_price_data)
                event_count = events.sum()
                logger.info(
                    f"CUSUM filter: {event_count}/{len(tf_price_data)} bars selected "
                    f"({event_count/len(tf_price_data)*100:.1f}%)"
                )

            labels = tb_labeler.generate_labels(tf_price_data)
            stats = tb_labeler.get_label_statistics(labels)

            # Apply CUSUM mask if filtering was done (before weights)
            if cusum_threshold is not None:
                event_indices = events[events].index
                labels = labels[labels.index.isin(event_indices)]
                # Store event mask for feature alignment in orchestrator
                TrainingPipeline._cusum_event_mask = events
                logger.info(f"After CUSUM filtering: {len(labels)} labels retained")

            # Optionally compute uniqueness weights (on final filtered labels)
            compute_weights = label_config.get("compute_weights", False)
            if compute_weights:
                from ktrdr.training.sample_weights import (
                    compute_uniqueness_weights,
                )

                holding_periods = tb_labeler.get_holding_periods()
                if holding_periods is not None:
                    # Filter holding periods to match CUSUM-filtered labels
                    if cusum_threshold is not None:
                        holding_periods = holding_periods[
                            holding_periods.index.isin(labels.index)
                        ]
                    weights = compute_uniqueness_weights(
                        labels, holding_periods, normalize=True
                    )
                    TrainingPipeline._sample_weights = torch.FloatTensor(weights.values)
                    logger.info(
                        f"Computed uniqueness weights: "
                        f"mean={weights.mean():.3f}, "
                        f"min={weights.min():.3f}, max={weights.max():.3f}"
                    )

            # Map TB labels to class indices: +1→0 (BUY), 0→1 (HOLD), -1→2 (SELL)
            class_map = {1: 0, 0: 1, -1: 2}
            mapped = labels.map(class_map)
            label_tensor = torch.LongTensor(mapped.values)

            logger.info(
                f"Generated {len(label_tensor)} triple barrier labels - "
                f"TP={stats['take_profit_pct']:.1f}%, "
                f"SL={stats['stop_loss_pct']:.1f}%, "
                f"Expiry={stats['time_expiry_pct']:.1f}%, "
                f"mean_hold={stats['mean_holding_period']:.1f} bars"
            )
            return label_tensor

        if source != "zigzag":
            raise ValueError(
                f"Unknown label source '{source}'. "
                f"Supported sources: 'zigzag', 'forward_return', 'context', "
                f"'regime', 'triple_barrier'"
            )

        # Default: ZigZag classification labels
        logger.info(
            f"TrainingPipeline.create_labels() - ZigZag labels "
            f"(threshold={label_config.get('zigzag_threshold', 'N/A')}, "
            f"lookahead={label_config.get('label_lookahead', 'N/A')})"
        )

        labeler = ZigZagLabeler(
            threshold=label_config["zigzag_threshold"],
            lookahead=label_config["label_lookahead"],
        )

        labels = labeler.generate_segment_labels(tf_price_data)
        label_tensor = torch.LongTensor(labels.values)

        unique, counts = torch.unique(label_tensor, return_counts=True)
        dist = {int(u): int(c) for u, c in zip(unique, counts)}
        logger.info(f"Generated {len(label_tensor)} labels - Distribution: {dist}")

        return label_tensor

    @staticmethod
    def _sort_timeframes_by_frequency(timeframes: list[str]) -> list[str]:
        """
        Sort timeframes by frequency (highest frequency first).

        Helper method for multi-timeframe label generation.
        """
        # Timeframe frequency mapping (in minutes)
        # Note: Normalized to lowercase for case-insensitive lookup
        frequency_map = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "1d": 1440,  # Daily
            "1w": 10080,  # Weekly
        }

        # Default to daily frequency (1440 minutes) for unknown timeframes
        DEFAULT_TIMEFRAME_MINUTES = 1440

        # Sort by frequency (lower minutes = higher frequency)
        # Normalize to lowercase for case-insensitive comparison
        return sorted(
            timeframes,
            key=lambda tf: frequency_map.get(tf.lower(), DEFAULT_TIMEFRAME_MINUTES),
        )

    # ======================================================================
    # MODEL METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def create_model(
        input_dim: int,
        output_dim: int,
        model_config: dict[str, Any],
    ) -> nn.Module:
        """
        Create neural network model.

        Args:
            input_dim: Number of input features
            output_dim: Number of output classes
            model_config: Model configuration dict containing:
                - type: "mlp" (default), "lstm", or "gru"
                - architecture: Architecture-specific config:
                    MLP: {hidden_layers: [64, 32], dropout: 0.2, activation: "relu"}
                    LSTM/GRU: {hidden_size: 64, num_layers: 2, dropout: 0.2, sequence_length: 20}
                - num_classes: Injected from output_dim (not user-specified)

        Returns:
            Neural network module ready for training

        Raises:
            ValueError: If model type is not supported
        """
        logger.info(
            f"🔧 TrainingPipeline.create_model() - Creating model with "
            f"input_dim={input_dim}, output_dim={output_dim}"
        )

        model_type = model_config.get("type", "mlp").lower()

        if model_type == "mlp":
            # Create MLPTradingModel and build the model
            # Inject num_classes so MLP knows the output dimension
            model_config_with_classes = {**model_config, "num_classes": output_dim}
            mlp_model = MLPTradingModel(model_config_with_classes)
            model = mlp_model.build_model(input_dim)
            logger.info(
                f"✅ Created MLP model with hidden_layers={model_config.get('hidden_layers', [])}"
            )
            return model
        elif model_type == "lstm":
            from ktrdr.neural.models.lstm import LSTMTradingModel

            model_config_with_classes = {**model_config, "num_classes": output_dim}
            lstm_model = LSTMTradingModel(model_config_with_classes)
            model = lstm_model.build_model(input_dim)
            arch = model_config.get("architecture", {})
            logger.info(
                f"✅ Created LSTM model with hidden_size={arch.get('hidden_size')}, "
                f"num_layers={arch.get('num_layers')}, "
                f"sequence_length={arch.get('sequence_length')}"
            )
            return model
        elif model_type == "gru":
            from ktrdr.neural.models.gru import GRUTradingModel

            model_config_with_classes = {**model_config, "num_classes": output_dim}
            gru_model = GRUTradingModel(model_config_with_classes)
            model = gru_model.build_model(input_dim)
            arch = model_config.get("architecture", {})
            logger.info(
                f"✅ Created GRU model with hidden_size={arch.get('hidden_size')}, "
                f"num_layers={arch.get('num_layers')}, "
                f"sequence_length={arch.get('sequence_length')}"
            )
            return model
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    @staticmethod
    def train_model(
        model: nn.Module,
        X_train: torch.Tensor,
        y_train: torch.Tensor,
        X_val: torch.Tensor,
        y_val: torch.Tensor,
        training_config: dict[str, Any],
        progress_callback=None,
        cancellation_token: Optional[CancellationToken] = None,
        checkpoint_callback=None,
        resume_context: "Optional[TrainingResumeContext]" = None,
        sample_weights: Optional[torch.Tensor] = None,
    ) -> dict[str, Any]:
        """
        Train the neural network model (symbol-agnostic).

        EXTRACTED FROM: StrategyTrainer._train_model() (train_strategy.py:942-1019)

        This is a SYNCHRONOUS method with no async operations. Orchestrators
        wrap this method differently for their execution environments.

        SYMBOL-AGNOSTIC DESIGN: This method treats all input data the same way,
        regardless of how many symbols contributed to it. Features from 1 symbol
        or 10 symbols are handled identically - the model learns patterns in
        technical indicators and fuzzy memberships, not symbol identities.

        Args:
            model: Neural network model to train
            X_train: Training features (concatenated from all symbols)
            y_train: Training labels (concatenated from all symbols)
            X_val: Validation features (concatenated from all symbols)
            y_val: Validation labels (concatenated from all symbols)
            training_config: Training configuration dict containing:
                - epochs: Number of training epochs
                - batch_size: Batch size
                - learning_rate: Learning rate
            progress_callback: Optional callback(epoch, total_epochs, metrics)
            cancellation_token: Optional cancellation token
            checkpoint_callback: Optional callback for checkpointing after each epoch.
                Called with kwargs: epoch, model, optimizer, scheduler, trainer.
            resume_context: Optional resume context for resumed training from checkpoint.
            sample_weights: Optional per-sample weights (length must match X_train).
                When provided, uses WeightedRandomSampler for importance sampling
                (e.g., uniqueness weights from triple barrier labels).

        Returns:
            Training results dict containing:
                - train_loss: Final training loss
                - val_loss: Final validation loss
                - train_accuracy: Final training accuracy
                - val_accuracy: Final validation accuracy
                - epochs_completed: Number of epochs completed
                - training_history: History of metrics per epoch
        """
        logger.info(
            f"🔧 TrainingPipeline.train_model() - Training model "
            f"(epochs={training_config.get('epochs', 'N/A')}, "
            f"batch_size={training_config.get('batch_size', 'N/A')})"
        )

        # Create trainer instance
        trainer = ModelTrainer(
            training_config,
            progress_callback=progress_callback,
            cancellation_token=cancellation_token,
            checkpoint_callback=checkpoint_callback,
            resume_context=resume_context,
        )

        # Symbol-agnostic training: Always use the same path regardless of number of symbols
        # The model doesn't care if features came from 1 symbol or 10 - it just sees
        # technical indicators and fuzzy memberships concatenated together.
        logger.debug(f"Symbol-agnostic training with {len(X_train)} samples")
        result = trainer.train(
            model=model,
            X_train=X_train,
            y_train=y_train,
            X_val=X_val,
            y_val=y_val,
            sample_weights=sample_weights,
        )

        # Use the actual keys returned by ModelTrainer
        train_loss = result.get("final_train_loss", None)
        val_loss = result.get("final_val_loss", None)
        if train_loss is not None and val_loss is not None:
            logger.info(
                f"✅ Training complete - "
                f"Final train_loss={train_loss:.4f}, "
                f"val_loss={val_loss:.4f}"
            )
        else:
            logger.info(
                f"✅ Training complete - "
                f"Final train_loss={train_loss}, "
                f"val_loss={val_loss}"
            )

        return result

    @staticmethod
    def evaluate_model(
        model: nn.Module,
        X_test: Optional[torch.Tensor],
        y_test: Optional[torch.Tensor],
        symbol_indices_test: Optional[torch.Tensor] = None,
        output_format: str = "classification",
        model_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Evaluate model on test set.

        Args:
            model: Trained model
            X_test: Test features (None for no test data)
            y_test: Test labels (None for no test data)
            symbol_indices_test: Optional symbol indices for multi-symbol evaluation
            output_format: 'classification' or 'regression'

        Returns:
            Test metrics dict. For classification: test_accuracy, test_loss,
            precision, recall, f1_score. For regression: test_accuracy
            (directional accuracy), test_loss, mae.
        """
        logger.info(
            "🔧 TrainingPipeline.evaluate_model() - Evaluating model on test set"
        )

        # Fail loudly if test data is missing - this indicates a data pipeline issue
        if X_test is None or y_test is None:
            from ktrdr.training.exceptions import TrainingDataError

            raise TrainingDataError(
                "Training produced no test data. "
                "This usually indicates a data pipeline issue with multi-symbol "
                "or multi-timeframe configurations. Check data loading and splitting."
            )

        # Move test data to the same device as the model
        device = next(model.parameters()).device

        # For temporal models, convert test data to sequences
        _model_config = model_config or {}
        model_type = _model_config.get("type", "mlp").lower()
        seq_len = _model_config.get("architecture", {}).get("sequence_length")
        if model_type in ("lstm", "gru") and isinstance(seq_len, int) and seq_len > 0:
            if X_test.size(0) >= seq_len:
                X_test_seq = X_test.unfold(dimension=0, size=seq_len, step=1)
                X_test_seq = X_test_seq.transpose(1, 2)  # (N, seq_len, F)
                num_windows = X_test_seq.size(0)
                y_test = y_test[seq_len - 1 : seq_len - 1 + num_windows]
                X_test = X_test_seq

        X_test = X_test.to(device)
        y_test = y_test.to(device)

        model.eval()
        with torch.no_grad():
            outputs = model(X_test)

            if output_format == "regression":
                # Regression: directional accuracy, Huber loss, MAE
                predicted_returns = outputs.squeeze(-1)
                criterion: nn.Module = nn.HuberLoss()
                loss = criterion(predicted_returns, y_test).item()

                # Directional accuracy: sign(predicted) == sign(actual)
                pred_sign = torch.sign(predicted_returns)
                actual_sign = torch.sign(y_test)
                accuracy = (pred_sign == actual_sign).float().mean().item()

                mae = torch.abs(predicted_returns - y_test).mean().item()

                logger.info(
                    f"✅ Regression evaluation complete - "
                    f"directional_accuracy={accuracy:.4f}, test_loss={loss:.6f}, "
                    f"mae={mae:.6f}"
                )

                return {
                    "test_accuracy": accuracy,
                    "test_loss": loss,
                    "mae": mae,
                }
            else:
                # Classification: argmax accuracy, CrossEntropyLoss, sklearn metrics
                _, predicted = torch.max(outputs, 1)
                accuracy = (predicted == y_test).float().mean().item()

                criterion = nn.CrossEntropyLoss()
                loss = criterion(outputs, y_test).item()

                y_true = y_test.cpu().numpy()
                y_pred = predicted.cpu().numpy()

                precision = precision_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
                recall = recall_score(
                    y_true, y_pred, average="weighted", zero_division=0
                )
                f1 = f1_score(y_true, y_pred, average="weighted", zero_division=0)

                logger.info(
                    f"✅ Evaluation complete - "
                    f"test_accuracy={accuracy:.4f}, test_loss={loss:.4f}, "
                    f"precision={precision:.4f}, recall={recall:.4f}, "
                    f"f1_score={f1:.4f}"
                )

                return {
                    "test_accuracy": accuracy,
                    "test_loss": loss,
                    "precision": precision,
                    "recall": recall,
                    "f1_score": f1,
                }

    # ======================================================================
    # MULTI-SYMBOL METHODS
    # Extracted from: ktrdr/training/train_strategy.py::StrategyTrainer
    # ======================================================================

    @staticmethod
    def combine_multi_symbol_data(
        all_symbols_features: dict[str, torch.Tensor],
        all_symbols_labels: dict[str, torch.Tensor],
        symbols: list[str],
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Combine features and labels from multiple symbols sequentially, preserving temporal order.

        DESIGN PRINCIPLE: Strategies are symbol-agnostic. A trading strategy operates on
        patterns in technical indicators and price action, not on symbol names. The model
        learns "when RSI is oversold AND MACD crosses up, buy" - this pattern is universal
        across all symbols.

        TEMPORAL PRESERVATION: Concatenates data sequentially (AAPL all → MSFT all → TSLA all)
        to preserve time series order within each symbol. This is critical for learning
        temporal patterns.

        INDICATOR RESETS: Caller must reset indicator state (moving averages, etc.) at
        symbol boundaries since each symbol's data is a separate time series. Concatenating
        AAPL's last day with MSFT's first day doesn't represent continuous time.

        NO DATA LOSS: Uses ALL data from all symbols - no sampling, no random selection.

        Args:
            all_symbols_features: Dict mapping symbol to features tensor
            all_symbols_labels: Dict mapping symbol to labels tensor
            symbols: List of symbol names in order

        Returns:
            Tuple of (combined_features, combined_labels)
            Note: No symbol_indices returned - strategies are symbol-agnostic
        """
        from ktrdr.training.exceptions import TrainingDataError

        combined_features_list = []
        combined_labels_list = []

        # DEBUG LOGGING: Log per-symbol sample counts to identify data loss
        logger.info(f"🔗 Combining data from {len(symbols)} symbols:")
        total_samples = 0

        for symbol in symbols:
            features = all_symbols_features[symbol]
            labels = all_symbols_labels[symbol]

            # Validate feature/label size consistency per symbol
            if features.shape[0] != labels.shape[0]:
                error_msg = (
                    f"Feature/label size mismatch for symbol {symbol}: "
                    f"features={features.shape[0]}, labels={labels.shape[0]}. "
                    f"This indicates a data alignment issue in the preprocessing pipeline."
                )
                logger.error(f"❌ {error_msg}")
                raise TrainingDataError(error_msg)

            # Validate non-empty data
            if features.shape[0] == 0:
                error_msg = f"Empty data for symbol {symbol}. Check data loading."
                logger.error(f"❌ {error_msg}")
                raise TrainingDataError(error_msg)

            # Log per-symbol details
            logger.info(
                f"   {symbol}: {features.shape[0]} samples, "
                f"{features.shape[1]} features"
            )
            total_samples += features.shape[0]

            # Concatenate sequentially - preserves temporal order
            combined_features_list.append(features)
            combined_labels_list.append(labels)

        # Validate consistent feature dimensions across symbols
        feature_dims = [f.shape[1] for f in combined_features_list]
        if len(set(feature_dims)) > 1:
            error_msg = (
                f"Inconsistent feature dimensions across symbols: "
                f"{dict(zip(symbols, feature_dims))}. "
                f"All symbols must have the same number of features."
            )
            logger.error(f"❌ {error_msg}")
            raise TrainingDataError(error_msg)

        # Concatenate all symbols (AAPL all data, then MSFT all data, etc.)
        combined_features = torch.cat(combined_features_list, dim=0)
        combined_labels = torch.cat(combined_labels_list, dim=0)

        logger.info(
            f"✅ Combined total: {combined_features.shape[0]} samples, "
            f"{combined_features.shape[1]} features"
        )

        # NO SHUFFLE - temporal order is critical for time series
        # NO SYMBOL_INDICES - strategies don't care about symbol names
        return combined_features, combined_labels


class TrainingPipelineV3:
    """
    Training pipeline for v3 strategy configuration.

    This class uses FeatureResolver to determine what features to compute
    and ensures feature order matches the canonical order from nn_inputs.

    The feature ordering is CRITICAL:
    1. nn_inputs list order (YAML order preserved)
    2. Within each nn_input: timeframes order × membership function order

    This order must be stored in ModelMetadataV3 and validated at backtest.
    """

    def __init__(self, config: "StrategyConfigurationV3"):
        """
        Initialize TrainingPipelineV3 with v3 strategy configuration.

        Args:
            config: V3 strategy configuration with indicators, fuzzy_sets, and nn_inputs
        """
        from ktrdr.config.feature_resolver import FeatureResolver

        self.config = config
        self.feature_resolver = FeatureResolver()

        # Initialize engines with v3 config
        self.indicator_engine = IndicatorEngine(config.indicators)
        self.fuzzy_engine = FuzzyEngine(config.fuzzy_sets)

        logger.info(
            f"TrainingPipelineV3 initialized with "
            f"{len(config.indicators)} indicators, "
            f"{len(config.fuzzy_sets)} fuzzy sets"
        )

    def prepare_features(
        self,
        data: dict[str, dict[str, pd.DataFrame]],
        context_data: Optional[dict[str, pd.DataFrame]] = None,
    ) -> pd.DataFrame:
        """
        Prepare NN input features from multi-symbol, multi-timeframe data.

        Args:
            data: {symbol: {timeframe: DataFrame}}
            context_data: Optional dict mapping source keys to DataFrames
                for indicators with data_source (e.g., FRED yield spreads)

        Returns:
            Feature DataFrame with columns matching resolved feature_ids,
            in the exact order from FeatureResolver
        """
        # Resolve features to get canonical order
        resolved = self.feature_resolver.resolve(self.config)
        expected_columns = [f.feature_id for f in resolved]

        logger.info(
            f"Preparing features: {len(expected_columns)} features expected "
            f"across {len(data)} symbol(s)"
        )

        # Group requirements by timeframe for efficient computation
        tf_requirements = self._group_requirements_by_timeframe(resolved)

        all_features = []
        for _symbol, tf_data in data.items():
            symbol_dfs = []

            for timeframe, df in tf_data.items():
                if timeframe not in tf_requirements:
                    logger.debug(
                        f"Skipping timeframe {timeframe} - not required by nn_inputs"
                    )
                    continue

                reqs = tf_requirements[timeframe]

                # Compute required indicators for this timeframe
                indicator_df = self.indicator_engine.compute_for_timeframe(
                    df,
                    timeframe,
                    reqs["indicators"],
                    context_data=context_data,
                )

                # Apply fuzzy sets to compute membership values
                for fuzzy_set_id in reqs["fuzzy_sets"]:
                    # Get the indicator this fuzzy set uses
                    indicator_ref = self.fuzzy_engine.get_indicator_for_fuzzy_set(
                        fuzzy_set_id
                    )

                    # Handle dot notation for multi-output indicators
                    if "." in indicator_ref:
                        base_indicator, output_name = indicator_ref.split(".", 1)
                        indicator_col = f"{timeframe}_{base_indicator}.{output_name}"
                    else:
                        indicator_col = f"{timeframe}_{indicator_ref}"

                    # Check if column exists
                    if indicator_col not in indicator_df.columns:
                        raise ValueError(
                            f"Indicator column '{indicator_col}' not found in data. "
                            f"Available columns: {list(indicator_df.columns)}"
                        )

                    # Fuzzify indicator values
                    # In v3 mode, fuzzify returns a DataFrame
                    fuzzify_result = self.fuzzy_engine.fuzzify(
                        fuzzy_set_id, indicator_df[indicator_col]
                    )

                    # Type assertion for v3 mode (always returns DataFrame for Series input)
                    if not isinstance(fuzzify_result, pd.DataFrame):
                        raise TypeError(
                            f"Expected DataFrame from fuzzify, got {type(fuzzify_result)}"
                        )
                    fuzzy_df: pd.DataFrame = fuzzify_result

                    # Add timeframe prefix to fuzzy columns
                    # fuzzify returns columns like "rsi_fast_oversold"
                    # We need "5m_rsi_fast_oversold"
                    fuzzy_df = fuzzy_df.rename(
                        columns={col: f"{timeframe}_{col}" for col in fuzzy_df.columns}
                    )

                    symbol_dfs.append(fuzzy_df)

                # Extract raw indicator features (hybrid encoding)
                for raw_feature in reqs.get("raw_features", []):
                    # Build the indicator column name
                    if raw_feature.indicator_output:
                        indicator_col = (
                            f"{timeframe}_{raw_feature.indicator_id}"
                            f".{raw_feature.indicator_output}"
                        )
                    else:
                        indicator_col = f"{timeframe}_{raw_feature.indicator_id}"

                    if indicator_col not in indicator_df.columns:
                        raise ValueError(
                            f"Raw indicator column '{indicator_col}' not found. "
                            f"Available: {list(indicator_df.columns)}"
                        )

                    # Extract raw values as a single-column DataFrame
                    raw_col = indicator_df[[indicator_col]].copy()
                    raw_col = raw_col.rename(
                        columns={indicator_col: raw_feature.feature_id}
                    )
                    symbol_dfs.append(raw_col)

            if symbol_dfs:
                # Combine all fuzzy DataFrames for this symbol
                symbol_features = pd.concat(symbol_dfs, axis=1)
                all_features.append(symbol_features)

        if not all_features:
            raise ValueError("No features computed - check data and configuration")

        # Concatenate all symbols (vertically - each symbol's features stacked)
        result = pd.concat(all_features, axis=0)

        # CRITICAL: Reorder columns to match canonical order
        # Only keep columns that are in expected_columns
        missing = set(expected_columns) - set(result.columns)
        if missing:
            logger.warning(
                f"Missing {len(missing)} expected features: {sorted(missing)[:5]}..."
            )

        # Filter to only expected columns and reorder
        available_expected = [col for col in expected_columns if col in result.columns]
        result = result[available_expected]

        logger.info(
            f"Features prepared: {result.shape[0]} samples, {result.shape[1]} features"
        )

        return result

    def _group_requirements_by_timeframe(
        self, resolved: list["ResolvedFeature"]
    ) -> dict[str, dict]:
        """
        Group indicator and fuzzy set requirements by timeframe.

        Args:
            resolved: List of resolved features from FeatureResolver

        Returns:
            Dict mapping timeframe to {indicators: set, fuzzy_sets: set}
        """
        result: dict[str, dict] = {}
        for f in resolved:
            if f.timeframe not in result:
                result[f.timeframe] = {
                    "indicators": set(),
                    "fuzzy_sets": set(),
                    "raw_features": [],
                }
            result[f.timeframe]["indicators"].add(f.indicator_id)
            if f.fuzzy_set_id == "__raw__":
                result[f.timeframe]["raw_features"].append(f)
            else:
                result[f.timeframe]["fuzzy_sets"].add(f.fuzzy_set_id)

        # Log requirements summary
        reqs_summary = ", ".join(
            f"{tf}: {len(reqs['indicators'])} ind, {len(reqs['fuzzy_sets'])} fuzzy"
            for tf, reqs in result.items()
        )
        logger.debug(f"Requirements grouped by timeframe: {reqs_summary}")

        return result


# Type hint imports at module level for forward references
if TYPE_CHECKING:
    from ktrdr.config.feature_resolver import ResolvedFeature
    from ktrdr.config.models import StrategyConfigurationV3
