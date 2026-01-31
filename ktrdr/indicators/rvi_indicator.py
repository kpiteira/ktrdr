"""
Relative Vigor Index (RVI) Indicator implementation.

The Relative Vigor Index is a momentum oscillator that measures the conviction
of a recent price action and the likelihood that it will continue. It compares
the closing price relative to the opening price against the high-low range.

Mathematical Formula:
1. Numerator = (Close - Open) + 2*(Close[1] - Open[1]) + 2*(Close[2] - Open[2]) + (Close[3] - Open[3])
2. Denominator = (High - Low) + 2*(High[1] - Low[1]) + 2*(High[2] - Low[2]) + (High[3] - Low[3])
3. RVI = SMA(Numerator, period) / SMA(Denominator, period)
4. Signal = SMA(RVI, signal_period)

The RVI oscillates around zero, with values above zero indicating bullish momentum
and values below zero indicating bearish momentum.
"""

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class RVIIndicator(BaseIndicator):
    """
    Relative Vigor Index (RVI) technical indicator.

    The RVI is a momentum oscillator that measures the conviction of price movements
    by comparing closing prices relative to opening prices against the high-low range.

    Attributes:
        period: Period for the RVI calculation (default: 10)
        signal_period: Period for the signal line calculation (default: 4)
    """

    class Params(BaseIndicator.Params):
        """RVI parameter schema with validation."""

        period: int = Field(
            default=10,
            ge=4,
            le=100,
            strict=True,
            description="Period for the RVI calculation (must be >= 4)",
        )
        signal_period: int = Field(
            default=4,
            ge=1,
            le=50,
            strict=True,
            description="Period for the signal line calculation",
        )

    # RVI is displayed in a separate panel (oscillator)
    display_as_overlay = False

    @classmethod
    def is_multi_output(cls) -> bool:
        """RVI produces multiple outputs (RVI and Signal)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for RVI indicator."""
        return ["rvi", "signal"]

    def _validate_data(self, data: pd.DataFrame):
        """
        Validate input data for RVI calculation.

        Args:
            data: Input data containing OHLC prices

        Raises:
            DataError: If data is invalid or insufficient
        """
        required_columns = ["open", "high", "low", "close"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            raise DataError(
                message=f"RVI indicator missing required columns: {missing_columns}",
                error_code="INDICATOR-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                },
            )

        if len(data) == 0:
            raise DataError(
                message="RVI indicator requires non-empty data",
                error_code="INDICATOR-EmptyData",
                details={"data_length": len(data)},
            )

        # Need enough data for the weighted calculation (4 periods) plus the main period
        min_required = self.params["period"] + 3
        if len(data) < min_required:
            raise DataError(
                message=f"RVI indicator requires at least {min_required} data points",
                error_code="INDICATOR-InsufficientData",
                details={
                    "required_points": min_required,
                    "available_points": len(data),
                    "period": self.params["period"],
                },
            )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the Relative Vigor Index.

        Args:
            data: DataFrame with columns ['open', 'high', 'low', 'close']

        Returns:
            DataFrame with RVI and Signal columns

        Raises:
            DataError: If data validation fails
        """
        self._validate_data(data)

        period = self.params["period"]
        signal_period = self.params["signal_period"]

        logger.debug(
            f"Computing RVI with period={period}, signal_period={signal_period}"
        )

        # Calculate price differences
        close_open = data["close"] - data["open"]
        high_low = data["high"] - data["low"]

        # Apply weighted moving average as per RVI formula:
        # Weight pattern: [1, 2, 2, 1] for 4-period smoothing
        # This creates a weighted sum where middle values have more influence

        numerator_weighted = pd.Series(index=data.index, dtype=float)
        denominator_weighted = pd.Series(index=data.index, dtype=float)

        # Calculate weighted sums for each position
        for i in range(3, len(data)):
            # Weights: [1, 2, 2, 1] applied to positions [i-3, i-2, i-1, i]
            num_sum = (
                close_open.iloc[i - 3]
                + 2 * close_open.iloc[i - 2]
                + 2 * close_open.iloc[i - 1]
                + close_open.iloc[i]
            )

            den_sum = (
                high_low.iloc[i - 3]
                + 2 * high_low.iloc[i - 2]
                + 2 * high_low.iloc[i - 1]
                + high_low.iloc[i]
            )

            numerator_weighted.iloc[i] = num_sum / 6.0  # Normalize by weight sum
            denominator_weighted.iloc[i] = den_sum / 6.0

        # Calculate moving averages
        numerator_ma = numerator_weighted.rolling(
            window=period, min_periods=period
        ).mean()
        denominator_ma = denominator_weighted.rolling(
            window=period, min_periods=period
        ).mean()

        # Calculate RVI (avoid division by zero)
        rvi = pd.Series(index=data.index, dtype=float)
        mask = (denominator_ma != 0) & (~pd.isna(denominator_ma))
        rvi[mask] = numerator_ma[mask] / denominator_ma[mask]

        # Calculate Signal line
        signal = rvi.rolling(window=signal_period, min_periods=signal_period).mean()

        # M3b: Return semantic column names only (engine handles prefixing)
        result = pd.DataFrame(
            {
                "rvi": rvi,
                "signal": signal,
            },
            index=data.index,
        )

        logger.debug(
            f"RVI computation completed. Valid RVI values: {(~pd.isna(rvi)).sum()}"
        )

        return result

    def get_name(self) -> str:
        """
        Get the formatted name of the indicator.

        Returns:
            Formatted indicator name including parameters
        """
        period = self.params["period"]
        signal_period = self.params["signal_period"]
        return f"RVI_{period}_{signal_period}"
