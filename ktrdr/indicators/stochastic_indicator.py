"""
Stochastic Oscillator indicator implementation for KTRDR.

The Stochastic Oscillator is a momentum indicator that compares a security's closing price
to its price range over a given time period. It generates two lines: %K and %D.
"""

from typing import Any, Optional

import pandas as pd

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator
from ktrdr.indicators.schemas import STOCHASTIC_SCHEMA

# Create module-level logger
logger = get_logger(__name__)


class StochasticIndicator(BaseIndicator):
    """
    Stochastic Oscillator momentum indicator.

    The Stochastic Oscillator consists of two lines:
    - %K line: ((Close - Lowest Low) / (Highest High - Lowest Low)) × 100
    - %D line: Moving average of %K line

    The indicator oscillates between 0 and 100:
    - Values above 80 indicate overbought conditions
    - Values below 20 indicate oversold conditions

    Default parameters:
        - k_period: 14 (lookback period for %K calculation)
        - d_period: 3 (smoothing period for %D calculation)
        - smooth_k: 3 (smoothing period for %K line)

    Attributes:
        k_period (int): Lookback period for %K calculation
        d_period (int): Smoothing period for %D calculation
        smooth_k (int): Smoothing period for %K line
    """

    @classmethod
    def is_multi_output(cls) -> bool:
        """Stochastic produces multiple outputs (%K and %D lines)."""
        return True

    @classmethod
    def get_primary_output_suffix(cls) -> str:
        """Primary output is the %K line."""
        return "K"

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """
        Generate column name matching what compute() actually produces.

        Stochastic format:
        - K line: "Stochastic_K_{k_period}_{smooth_k}"
        - D line: "Stochastic_D_{k_period}_{d_period}_{smooth_k}"

        Args:
            suffix: Optional suffix ("K", "D", or None for K)

        Returns:
            Column name matching compute() output format
        """
        k_period = self.params.get("k_period", 14)
        d_period = self.params.get("d_period", 3)
        smooth_k = self.params.get("smooth_k", 3)

        if suffix == "D":
            return f"Stochastic_D_{k_period}_{d_period}_{smooth_k}"
        else:
            # Default to K line (primary)
            return f"Stochastic_K_{k_period}_{smooth_k}"

    def __init__(
        self,
        k_period: int = 14,
        d_period: int = 3,
        smooth_k: int = 3,
    ):
        """
        Initialize the Stochastic Oscillator indicator.

        Args:
            k_period: Lookback period for %K calculation
            d_period: Smoothing period for %D calculation
            smooth_k: Smoothing period for %K line
        """
        # Call parent constructor with display_as_overlay=False (separate panel)
        super().__init__(
            name="Stochastic",
            display_as_overlay=False,
            k_period=k_period,
            d_period=d_period,
            smooth_k=smooth_k,
        )

        logger.debug(
            f"Initialized Stochastic indicator with k_period={k_period}, "
            f"d_period={d_period}, smooth_k={smooth_k}"
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate parameters for Stochastic indicator using schema-based validation.

        Args:
            params: Parameters to validate

        Returns:
            Validated parameters with defaults applied

        Raises:
            DataError: If parameters are invalid
        """
        return STOCHASTIC_SCHEMA.validate(params)

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the Stochastic Oscillator indicator.

        Args:
            data: DataFrame containing OHLC data

        Returns:
            DataFrame with %K and %D lines

        Raises:
            DataError: If required columns are missing or insufficient data
        """
        # Get parameters from self.params (validated by BaseIndicator)
        k_period = self.params.get("k_period", 14)
        d_period = self.params.get("d_period", 3)
        smooth_k = self.params.get("smooth_k", 3)

        # Check required columns
        required_columns = ["high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]
        if missing_columns:
            raise DataError(
                message=f"Stochastic requires columns: {', '.join(missing_columns)}",
                error_code="DATA-MissingColumn",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                    "available_columns": list(data.columns),
                },
            )

        # Check for sufficient data
        min_required = max(k_period, smooth_k) + d_period
        if len(data) < min_required:
            raise DataError(
                message=f"Stochastic requires at least {min_required} data points for accurate calculation",
                error_code="DATA-InsufficientData",
                details={
                    "required": min_required,
                    "provided": len(data),
                    "k_period": k_period,
                    "d_period": d_period,
                    "smooth_k": smooth_k,
                },
            )

        # Calculate rolling highest high and lowest low over k_period
        highest_high = data["high"].rolling(window=k_period, min_periods=k_period).max()
        lowest_low = data["low"].rolling(window=k_period, min_periods=k_period).min()

        # Calculate raw %K
        # %K = ((Close - Lowest Low) / (Highest High - Lowest Low)) × 100
        raw_k = ((data["close"] - lowest_low) / (highest_high - lowest_low)) * 100

        # Handle division by zero (when high == low)
        raw_k = raw_k.fillna(50.0)  # Fill with neutral value when range is zero

        # Smooth %K if smooth_k > 1
        if smooth_k > 1:
            percent_k = raw_k.rolling(window=smooth_k, min_periods=1).mean()
        else:
            percent_k = raw_k

        # Calculate %D as moving average of %K
        percent_d = percent_k.rolling(window=d_period, min_periods=1).mean()

        # Create result DataFrame with column names
        k_col = f"Stochastic_K_{k_period}_{smooth_k}"
        d_col = f"Stochastic_D_{k_period}_{d_period}_{smooth_k}"

        result_df = pd.DataFrame(
            {
                k_col: percent_k,
                d_col: percent_d,
            },
            index=data.index,
        )

        logger.debug(
            f"Computed Stochastic with parameters: k_period={k_period}, "
            f"d_period={d_period}, smooth_k={smooth_k}"
        )

        return result_df
