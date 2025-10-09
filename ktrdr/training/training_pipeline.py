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

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.data.data_manager import DataManager
from ktrdr.data.multi_timeframe_coordinator import MultiTimeframeCoordinator

logger = get_logger(__name__)


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
        data_mode: str = "local",
        data_manager: Optional[DataManager] = None,
        multi_timeframe_coordinator: Optional[MultiTimeframeCoordinator] = None,
    ) -> dict[str, pd.DataFrame]:
        """
        Load price data for training with multi-timeframe support.

        EXTRACTED FROM: StrategyTrainer._load_price_data() (train_strategy.py:563-622)

        This is the EXACT logic from the existing implementation, just extracted
        into a standalone function.

        Args:
            symbol: Trading symbol
            timeframes: List of timeframes for multi-timeframe training
            start_date: Start date
            end_date: End date
            data_mode: Data loading mode ('local', 'tail', 'backfill', 'full')
            data_manager: Optional DataManager instance (will create if not provided)
            multi_timeframe_coordinator: Optional coordinator (will create if not provided)

        Returns:
            Dictionary mapping timeframes to OHLCV DataFrames

        Raises:
            ValueError: If no timeframes successfully loaded
        """
        # Initialize components if not provided
        if data_manager is None:
            data_manager = DataManager()

        if multi_timeframe_coordinator is None:
            multi_timeframe_coordinator = MultiTimeframeCoordinator(data_manager)

        # Handle single timeframe case (backward compatibility)
        # EXTRACTED FROM: train_strategy.py:584-592
        if len(timeframes) == 1:
            timeframe = timeframes[0]
            # Pass dates to DataManager for efficient filtering
            data = data_manager.load_data(
                symbol,
                timeframe,
                start_date=start_date,
                end_date=end_date,
                mode=data_mode,
            )

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
            mode=data_mode,
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

        return multi_data

    # _filter_data_by_date_range() method removed
    # Date filtering now handled by DataManager.load_data() which is more efficient
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
