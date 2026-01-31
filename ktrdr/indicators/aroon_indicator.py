"""
Aroon Indicator implementation.

The Aroon indicator is a trend-following indicator that measures the time between
highs and lows over a specified period. It helps identify the strength and
direction of trends by calculating how recently the highest high and lowest low
occurred within the period.

Mathematical Formula:
1. Aroon Up = ((period - periods since highest high) / period) × 100
2. Aroon Down = ((period - periods since lowest low) / period) × 100
3. Aroon Oscillator = Aroon Up - Aroon Down (optional)

The Aroon lines oscillate between 0 and 100:
- Aroon Up near 100 indicates a strong uptrend
- Aroon Down near 100 indicates a strong downtrend
- Both lines near 50 indicate a consolidation phase
- Crossovers between the lines signal potential trend changes
"""

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class AroonIndicator(BaseIndicator):
    """
    Aroon technical indicator.

    The Aroon indicator identifies trend changes and measures trend strength
    by calculating the time since the highest high and lowest low within a period.

    Attributes:
        period: Period for the Aroon calculation (default: 14)
        include_oscillator: Whether to include Aroon Oscillator (default: False)
    """

    class Params(BaseIndicator.Params):
        """Aroon parameter schema with validation."""

        period: int = Field(
            default=14,
            ge=1,
            le=200,
            strict=True,
            description="Period for Aroon calculation",
        )
        include_oscillator: bool = Field(
            default=False,
            strict=True,
            description="Whether to include Aroon Oscillator line",
        )

    # Aroon is displayed in a separate panel (oscillator)
    display_as_overlay = False

    @classmethod
    def is_multi_output(cls) -> bool:
        """Aroon produces multiple outputs (Up, Down, and optionally Oscillator)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for Aroon."""
        return ["up", "down", "oscillator"]

    def _validate_data(self, data: pd.DataFrame):
        """
        Validate input data for Aroon calculation.

        Args:
            data: Input data containing high and low prices

        Raises:
            DataError: If data is invalid or insufficient
        """
        required_columns = ["high", "low"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            raise DataError(
                message=f"Aroon indicator missing required columns: {missing_columns}",
                error_code="INDICATOR-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                },
            )

        if len(data) == 0:
            raise DataError(
                message="Aroon indicator requires non-empty data",
                error_code="INDICATOR-EmptyData",
                details={"data_length": len(data)},
            )

        # Need enough data for the calculation period
        min_required = self.params["period"]
        if len(data) < min_required:
            raise DataError(
                message=f"Aroon indicator requires at least {min_required} data points",
                error_code="INDICATOR-InsufficientData",
                details={
                    "required_points": min_required,
                    "available_points": len(data),
                    "period": self.params["period"],
                },
            )

    def compute(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Compute the Aroon indicator.

        Args:
            data: DataFrame with columns ['high', 'low']

        Returns:
            DataFrame with Aroon Up, Aroon Down, and optionally Aroon Oscillator

        Raises:
            DataError: If data validation fails
        """
        self._validate_data(data)

        period = self.params["period"]
        # M3b: Always compute oscillator to match get_output_names()

        logger.debug(f"Computing Aroon with period={period}")

        # Initialize result arrays
        aroon_up = pd.Series(index=data.index, dtype=float)
        aroon_down = pd.Series(index=data.index, dtype=float)

        # Calculate Aroon for each position starting from period-1 index
        for i in range(period - 1, len(data)):
            # Get the period window (inclusive of current position)
            start_idx = i - period + 1
            end_idx = i + 1

            period_highs = data["high"].iloc[start_idx:end_idx]
            period_lows = data["low"].iloc[start_idx:end_idx]

            # Find positions of highest high and lowest low within the period
            # argmax/argmin return relative positions within the window
            highest_high_pos = period_highs.argmax()
            lowest_low_pos = period_lows.argmin()

            # Convert to periods since highest high/lowest low
            # Since we're looking within the period window, the max periods since is (period - 1)
            periods_since_high = (len(period_highs) - 1) - highest_high_pos
            periods_since_low = (len(period_lows) - 1) - lowest_low_pos

            # Calculate Aroon values
            aroon_up_value = ((period - periods_since_high) / period) * 100.0
            aroon_down_value = ((period - periods_since_low) / period) * 100.0

            aroon_up.iloc[i] = aroon_up_value
            aroon_down.iloc[i] = aroon_down_value

        # M3b: Return semantic column names only (engine handles prefixing)
        # Always include oscillator to match get_output_names() (M3b requirement)
        aroon_oscillator = aroon_up - aroon_down

        result = pd.DataFrame(
            {
                "up": aroon_up,
                "down": aroon_down,
                "oscillator": aroon_oscillator,
            },
            index=data.index,
        )

        logger.debug(
            f"Aroon computation completed. Valid Aroon Up values: {(~pd.isna(aroon_up)).sum()}"
        )

        return result

    def get_name(self) -> str:
        """
        Get the formatted name of the indicator.

        Returns:
            Formatted indicator name including parameters
        """
        period = self.params["period"]
        include_oscillator = self.params["include_oscillator"]

        if include_oscillator:
            return f"Aroon_{period}_with_Oscillator"
        else:
            return f"Aroon_{period}"
