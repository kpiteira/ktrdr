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

from typing import Any, Optional

import pandas as pd

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

    @classmethod
    def is_multi_output(cls) -> bool:
        """Aroon produces multiple outputs (Up, Down, and optionally Oscillator)."""
        return True

    @classmethod
    def get_output_names(cls) -> list[str]:
        """Return semantic output names for Aroon."""
        return ["up", "down", "oscillator"]

    @classmethod
    def get_primary_output_suffix(cls) -> str:
        """Primary output is the Aroon Up line."""
        return "Up"

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """
        Generate column name matching what compute() actually produces.

        Aroon format:
        - Up: "Aroon_{period}_Up"
        - Down: "Aroon_{period}_Down"
        - Oscillator: "Aroon_{period}_Oscillator"

        Args:
            suffix: Optional suffix ("Up", "Down", "Oscillator", or None for Up)

        Returns:
            Column name matching compute() output format
        """
        period = self.params.get("period", 14)

        if suffix == "Down":
            return f"Aroon_{period}_Down"
        elif suffix == "Oscillator":
            return f"Aroon_{period}_Oscillator"
        else:
            # Default to Up (primary)
            return f"Aroon_{period}_Up"

    def __init__(self, period: int = 14, include_oscillator: bool = False):
        """
        Initialize the Aroon indicator.

        Args:
            period: Period for the Aroon calculation (must be >= 1)
            include_oscillator: Whether to include Aroon Oscillator line

        Raises:
            DataError: If parameters are invalid
        """
        # Initialize base class with parameters
        super().__init__(
            name="Aroon", period=period, include_oscillator=include_oscillator
        )

        logger.debug(
            f"Initialized Aroon indicator with period={period}, include_oscillator={include_oscillator}"
        )

    def _validate_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Validate Aroon parameters.

        Args:
            params: Dictionary of parameters to validate

        Returns:
            Dictionary of validated parameters

        Raises:
            DataError: If any parameter is invalid
        """
        validated_params = {}

        # Validate period
        period = params.get("period", 14)
        if not isinstance(period, int) or period < 1:
            raise DataError(
                message="Aroon period must be an integer >= 1",
                error_code="INDICATOR-InvalidParameter",
                details={"parameter": "period", "value": period, "minimum": 1},
            )

        if period > 200:
            raise DataError(
                message="Aroon period must be <= 200",
                error_code="INDICATOR-InvalidParameter",
                details={"parameter": "period", "value": period, "maximum": 200},
            )
        validated_params["period"] = period

        # Validate include_oscillator
        include_oscillator = params.get("include_oscillator", False)
        if not isinstance(include_oscillator, bool):
            raise DataError(
                message="Aroon include_oscillator must be a boolean",
                error_code="INDICATOR-InvalidParameter",
                details={
                    "parameter": "include_oscillator",
                    "value": include_oscillator,
                    "expected_type": "bool",
                },
            )
        validated_params["include_oscillator"] = include_oscillator

        return validated_params

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
        include_oscillator = self.params["include_oscillator"]

        logger.debug(
            f"Computing Aroon with period={period}, include_oscillator={include_oscillator}"
        )

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

        # Create result DataFrame
        result = pd.DataFrame(index=data.index)
        result[f"Aroon_{period}_Up"] = aroon_up
        result[f"Aroon_{period}_Down"] = aroon_down

        # Add Aroon Oscillator if requested
        if include_oscillator:
            aroon_oscillator = aroon_up - aroon_down
            result[f"Aroon_{period}_Oscillator"] = aroon_oscillator

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
