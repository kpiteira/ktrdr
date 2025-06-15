"""
Average True Range (ATR) indicator implementation for KTRDR.

Average True Range is a volatility indicator that measures the average of true ranges
over a specified period. It helps traders assess the volatility of a security.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any

from ktrdr import get_logger
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.errors import DataError
from ktrdr.indicators.schemas import ATR_SCHEMA

# Create module-level logger
logger = get_logger(__name__)


class ATRIndicator(BaseIndicator):
    """
    Average True Range (ATR) volatility indicator.

    The True Range is the greatest of:
    1. Current High - Current Low
    2. Absolute value of (Current High - Previous Close)
    3. Absolute value of (Current Low - Previous Close)
    
    ATR is the moving average of True Range values over the specified period.
    
    Higher ATR values indicate higher volatility, while lower values indicate lower volatility.
    ATR is always positive and expressed in the same units as the price.
    
    Default parameters:
        - period: 14 (lookback period for ATR calculation)

    Attributes:
        period (int): Lookback period for ATR calculation
    """

    def __init__(self, period: int = 14):
        """
        Initialize the ATR indicator.

        Args:
            period: Lookback period for ATR calculation
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="ATR",
            display_as_overlay=False,
            period=period,
        )

        logger.debug(f"Initialized ATR indicator with period={period}")

    def _validate_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for ATR indicator using schema-based validation.

        Args:
            params: Parameters to validate

        Returns:
            Validated parameters with defaults applied

        Raises:
            DataError: If parameters are invalid
        """
        return ATR_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute the Average True Range (ATR) indicator.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            Series with ATR values (always positive)

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        period = self.params.get("period", 14)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"ATR requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns)
                },
            )

        # Check for sufficient data (need at least period+1 for previous close)
        min_required = period + 1
        if len(data) < min_required:
            raise DataError(
                message=f"ATR requires at least {min_required} data points for accurate calculation",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "period": period,
                },
            )

        # Calculate True Range components
        high = data["high"]
        low = data["low"]
        close = data["close"]
        
        # Previous close (shifted by 1)
        prev_close = close.shift(1)
        
        # True Range is the maximum of:
        # 1. High - Low
        # 2. |High - Previous Close|
        # 3. |Low - Previous Close|
        tr1 = high - low
        tr2 = (high - prev_close).abs()
        tr3 = (low - prev_close).abs()
        
        # True Range is the maximum of the three
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # For the first data point, we don't have a previous close,
        # so True Range is just High - Low
        true_range.iloc[0] = tr1.iloc[0]
        
        # Calculate ATR as the simple moving average of True Range
        atr = true_range.rolling(window=period, min_periods=period).mean()

        # Create result Series with appropriate name
        result_series = pd.Series(
            atr,
            index=data.index,
            name=f"ATR_{period}",
        )

        logger.debug(f"Computed ATR with period={period}")

        return result_series