"""
Money Flow Index (MFI) Indicator implementation.

The Money Flow Index is a momentum oscillator that uses both price and volume
to measure buying and selling pressure. It is often referred to as the
"volume-weighted RSI" because it incorporates volume into the calculation.

Mathematical Formula:
1. Typical Price = (High + Low + Close) / 3
2. Raw Money Flow = Typical Price × Volume
3. Positive Money Flow = Sum of Raw Money Flow when Typical Price increases
4. Negative Money Flow = Sum of Raw Money Flow when Typical Price decreases
5. Money Flow Ratio = Positive Money Flow / Negative Money Flow
6. MFI = 100 - (100 / (1 + Money Flow Ratio))

The MFI oscillates between 0 and 100, with values above 80 typically indicating
overbought conditions and values below 20 indicating oversold conditions.
"""

import pandas as pd
from pydantic import Field

from ktrdr import get_logger
from ktrdr.errors import DataError
from ktrdr.indicators.base_indicator import BaseIndicator

logger = get_logger(__name__)


class MFIIndicator(BaseIndicator):
    """
    Money Flow Index (MFI) technical indicator.

    The MFI combines price and volume data to create a momentum oscillator
    that measures the strength of money flowing in and out of a security.

    Attributes:
        period: Period for the MFI calculation (default: 14)
    """

    class Params(BaseIndicator.Params):
        """MFI parameter schema with validation."""

        period: int = Field(
            default=14,
            ge=1,
            le=100,
            strict=True,
            description="Period for MFI calculation",
        )

    # MFI is displayed in a separate panel (oscillator)
    display_as_overlay = False

    def _validate_data(self, data: pd.DataFrame):
        """
        Validate input data for MFI calculation.

        Args:
            data: Input data containing OHLCV prices

        Raises:
            DataError: If data is invalid or insufficient
        """
        required_columns = ["high", "low", "close", "volume"]
        missing_columns = [col for col in required_columns if col not in data.columns]

        if missing_columns:
            raise DataError(
                message=f"MFI indicator missing required columns: {missing_columns}",
                error_code="INDICATOR-MissingColumns",
                details={
                    "missing_columns": missing_columns,
                    "required_columns": required_columns,
                },
            )

        if len(data) == 0:
            raise DataError(
                message="MFI indicator requires non-empty data",
                error_code="INDICATOR-EmptyData",
                details={"data_length": len(data)},
            )

        # Need enough data for the calculation period
        min_required = self.params["period"] + 1  # +1 for price change calculation
        if len(data) < min_required:
            raise DataError(
                message=f"MFI indicator requires at least {min_required} data points",
                error_code="INDICATOR-InsufficientData",
                details={
                    "required_points": min_required,
                    "available_points": len(data),
                    "period": self.params["period"],
                },
            )

        # Check for non-negative volume values
        # Note: Forex data may have -1 as sentinel value (no volume), should be handled at data loading
        if (data["volume"] < 0).any():
            negative_count = (data["volume"] < 0).sum()
            raise DataError(
                message=f"MFI indicator requires non-negative volume values. Found {negative_count} negative values (possibly forex data with -1 sentinel values). These should be converted to 0 during data loading.",
                error_code="INDICATOR-InvalidData",
                details={
                    "negative_volume_count": negative_count,
                    "min_volume": data["volume"].min(),
                    "data_length": len(data),
                },
            )

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute the Money Flow Index.

        Args:
            data: DataFrame with columns ['high', 'low', 'close', 'volume']

        Returns:
            Series with MFI values

        Raises:
            DataError: If data validation fails
        """
        self._validate_data(data)

        period = self.params["period"]

        logger.debug(f"Computing MFI with period={period}")

        # Calculate Typical Price
        typical_price = (data["high"] + data["low"] + data["close"]) / 3.0

        # Calculate Raw Money Flow
        raw_money_flow = typical_price * data["volume"]

        # Calculate price direction (typical price change)
        price_change = typical_price.diff()

        # Initialize MFI series
        mfi = pd.Series(index=data.index, dtype=float)

        # Calculate MFI for each position starting from period index
        for i in range(period, len(data)):
            # Get the period window
            start_idx = i - period + 1
            end_idx = i + 1

            period_changes = price_change.iloc[start_idx:end_idx]
            period_money_flows = raw_money_flow.iloc[start_idx:end_idx]

            # Calculate positive and negative money flows
            positive_flow = 0.0
            negative_flow = 0.0

            for j in range(len(period_changes)):
                change = period_changes.iloc[j]
                money_flow = period_money_flows.iloc[j]

                if pd.isna(
                    change  # type: ignore[call-overload]
                ):  # Skip NaN values (first price change is always NaN)
                    continue
                elif pd.notna(change) and change > 0:  # type: ignore[call-overload,operator]
                    positive_flow += money_flow
                elif pd.notna(change) and change < 0:  # type: ignore[call-overload,operator]
                    negative_flow += money_flow
                # If change == 0, money flow is not added to either positive or negative

            # Calculate Money Flow Index
            if negative_flow == 0:
                # All money flow was positive
                mfi_value = 100.0
            elif positive_flow == 0:
                # All money flow was negative
                mfi_value = 0.0
            else:
                money_flow_ratio = positive_flow / negative_flow
                mfi_value = 100.0 - (100.0 / (1.0 + money_flow_ratio))

            mfi.iloc[i] = mfi_value

        logger.debug(
            f"MFI computation completed. Valid MFI values: {(~pd.isna(mfi)).sum()}"
        )

        return mfi

    def get_name(self) -> str:
        """
        Get the formatted name of the indicator.

        Returns:
            Formatted indicator name including parameters
        """
        period = self.params["period"]
        return f"MFI_{period}"
