"""
ZigZag indicator implementation for identifying price extremes.

This indicator creates a ZigZag line that connects significant price reversals,
filtering out minor fluctuations based on a percentage threshold.
"""

from typing import Optional

import numpy as np
import pandas as pd

from ..errors import DataError
from .base_indicator import BaseIndicator


class ZigZagIndicator(BaseIndicator):
    """
    ZigZag indicator that identifies significant price reversals.

    The ZigZag indicator draws lines connecting significant price extremes,
    filtering out movements smaller than the specified threshold percentage.
    This is useful for:
    - Identifying major support/resistance levels
    - Creating training labels for machine learning
    - Visualizing market structure
    """

    def __init__(self, threshold: float = 0.05, source: str = "close", **kwargs):
        """
        Initialize ZigZag indicator.

        Args:
            threshold: Minimum percentage move to constitute a reversal (default: 0.05 = 5%)
            source: Source column for calculation (default: "close")
            **kwargs: Additional parameters
        """
        # Validate parameters first
        if threshold <= 0 or threshold >= 1:
            raise ValueError(f"Threshold must be between 0 and 1, got {threshold}")

        # Generate name based on threshold
        name = f"ZigZag_{int(threshold*100)}"

        # Call parent constructor with required name parameter
        super().__init__(name=name, display_as_overlay=True, **kwargs)

        # Store our specific parameters
        self.threshold = threshold
        self.source = source

    def compute(self, data: pd.DataFrame) -> pd.Series:
        """
        Compute ZigZag indicator.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with ZigZag values (NaN where no ZigZag point exists)
        """
        if self.source not in data.columns:
            raise DataError(
                f"Source column '{self.source}' not found in data",
                "DATA-ColumnMissing",
                {"column": self.source, "available": list(data.columns)},
            )

        prices = data[self.source].values
        if len(prices) < 3:
            raise DataError(
                f"Insufficient data: {len(prices)} points available, 3 required",
                "DATA-InsufficientData",
                {"available": len(prices), "required": 3},
            )

        # Initialize result array
        zigzag = np.full(len(prices), np.nan)

        # Track current extreme and direction
        last_extreme_idx = 0
        last_extreme_price = prices[0]
        direction = None  # 1 for uptrend, -1 for downtrend

        # First point is always a ZigZag point
        zigzag[0] = prices[0]

        for i in range(1, len(prices)):
            current_price = prices[i]

            # Calculate percentage change from last extreme
            pct_change = (current_price - last_extreme_price) / last_extreme_price

            if direction is None:
                # Determine initial direction
                if abs(pct_change) >= self.threshold:
                    if pct_change > 0:
                        direction = 1  # Uptrend
                    else:
                        direction = -1  # Downtrend

                    # Mark the extreme point
                    zigzag[i] = current_price
                    last_extreme_idx = i
                    last_extreme_price = current_price

            elif direction == 1:  # Currently in uptrend
                if current_price > last_extreme_price:
                    # New high - update the extreme
                    zigzag[last_extreme_idx] = np.nan  # Remove old extreme
                    zigzag[i] = current_price  # Set new extreme
                    last_extreme_idx = i
                    last_extreme_price = current_price

                elif pct_change <= -self.threshold:
                    # Significant decline - trend reversal
                    direction = -1
                    zigzag[i] = current_price
                    last_extreme_idx = i
                    last_extreme_price = current_price

            elif direction == -1:  # Currently in downtrend
                if current_price < last_extreme_price:
                    # New low - update the extreme
                    zigzag[last_extreme_idx] = np.nan  # Remove old extreme
                    zigzag[i] = current_price  # Set new extreme
                    last_extreme_idx = i
                    last_extreme_price = current_price

                elif pct_change >= self.threshold:
                    # Significant advance - trend reversal
                    direction = 1
                    zigzag[i] = current_price
                    last_extreme_idx = i
                    last_extreme_price = current_price

        return pd.Series(zigzag, index=data.index, name=self.get_column_name())

    def get_column_name(self, suffix: Optional[str] = None) -> str:
        """Get the column name for this indicator."""
        base_name = f"ZigZag_{int(self.threshold*100)}"
        return f"{base_name}_{suffix}" if suffix else base_name

    def get_zigzag_labels(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading labels based on ZigZag extremes.

        This method creates BUY/HOLD/SELL labels by looking ahead from each
        ZigZag extreme to determine the next significant move.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with labels: 0=BUY, 1=HOLD, 2=SELL
        """
        zigzag_values = self.compute(data)
        labels = np.full(len(data), 1)  # Default to HOLD

        # Find ZigZag extremes (non-NaN values)
        extreme_indices = np.where(~np.isnan(zigzag_values))[0]

        if len(extreme_indices) < 2:
            return pd.Series(labels, index=data.index, name="ZigZag_Labels")

        # Label points based on next ZigZag move
        for i in range(len(extreme_indices) - 1):
            current_idx = extreme_indices[i]
            next_idx = extreme_indices[i + 1]

            current_price = zigzag_values.iloc[current_idx]
            next_price = zigzag_values.iloc[next_idx]

            # Determine if next move is up or down
            if next_price > current_price:
                # Next move is up - label current as BUY
                labels[current_idx] = 0
            else:
                # Next move is down - label current as SELL
                labels[current_idx] = 2

        return pd.Series(labels, index=data.index, name="ZigZag_Labels")

    def get_zigzag_segment_labels(self, data: pd.DataFrame) -> pd.Series:
        """
        Generate trading labels based on ZigZag SEGMENTS (not just extremes).

        This method labels entire segments between ZigZag extremes:
        - BUY: All bars in upward segments (from bottom to top)
        - SELL: All bars in downward segments (from top to bottom)
        - HOLD: Bars at extremes (transition points)

        This creates much more balanced training data compared to sparse extreme labeling.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            Series with labels: 0=BUY, 1=HOLD, 2=SELL
        """
        zigzag_values = self.compute(data)
        labels = np.full(len(data), 1)  # Default to HOLD

        # Find ZigZag extremes (non-NaN values)
        extreme_indices = np.where(~np.isnan(zigzag_values))[0]

        if len(extreme_indices) < 2:
            return pd.Series(labels, index=data.index, name="ZigZag_Segment_Labels")

        # Label entire segments between extremes
        for i in range(len(extreme_indices) - 1):
            current_idx = extreme_indices[i]
            next_idx = extreme_indices[i + 1]

            current_price = zigzag_values.iloc[current_idx]
            next_price = zigzag_values.iloc[next_idx]

            # Determine segment direction and label ALL bars in segment
            if next_price > current_price:
                # Upward segment - label all bars as BUY
                segment_label = 0  # BUY
            else:
                # Downward segment - label all bars as SELL
                segment_label = 2  # SELL

            # Label all bars in the segment (excluding the extremes themselves)
            for j in range(current_idx + 1, next_idx):
                labels[j] = segment_label

        # Keep extremes as HOLD (transition points) - this provides some HOLD labels
        # but much fewer than the original sparse approach

        return pd.Series(labels, index=data.index, name="ZigZag_Segment_Labels")
