"""Forward return label generation for regression training.

Generates float return labels: (close[t+horizon] - close[t]) / close[t].
Used as an alternative to ZigZag classification labels.
"""

import pandas as pd

from ktrdr.errors import DataError


class ForwardReturnLabeler:
    """Generate forward return labels from price data.

    Instead of categorical BUY/HOLD/SELL labels, produces continuous return
    values that represent how much the price moved over a given horizon.
    """

    def __init__(self, horizon: int = 20):
        """Initialize the labeler.

        Args:
            horizon: Number of bars to look ahead for return calculation.
        """
        self.horizon = horizon

    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate forward return labels.

        Computes simple returns: (close[t+horizon] - close[t]) / close[t].

        Args:
            price_data: DataFrame with 'close' column.

        Returns:
            Series of float returns, length = len(price_data) - horizon.
            Last `horizon` rows have no label (no future data).

        Raises:
            DataError: If data has fewer than horizon + 1 bars or missing close column.
        """
        if "close" not in price_data.columns:
            raise DataError(
                "price_data must contain 'close' column",
                details={"columns": list(price_data.columns)},
            )

        if len(price_data) < self.horizon + 1:
            raise DataError(
                f"Data has fewer than {self.horizon + 1} bars required for horizon={self.horizon}",
                details={"data_length": len(price_data), "horizon": self.horizon},
            )

        close = price_data["close"]

        # Guard against zero close prices (division by zero)
        if (close == 0).any():
            raise DataError(
                "Close prices contain zero values, cannot compute returns",
                details={"zero_count": int((close == 0).sum())},
            )

        # Compute forward returns using shift
        future_close = close.shift(-self.horizon)
        returns = (future_close - close) / close

        # Drop the last `horizon` rows which have NaN from the shift
        returns = returns.iloc[: len(price_data) - self.horizon]

        return returns

    def get_label_statistics(self, labels: pd.Series) -> dict:
        """Return distribution statistics for generated labels.

        Args:
            labels: Series of return labels.

        Returns:
            Dict with mean, std, min, max, pct_positive, pct_negative.
        """
        return {
            "mean": float(labels.mean()),
            "std": float(labels.std()),
            "min": float(labels.min()),
            "max": float(labels.max()),
            "pct_positive": float((labels > 0).sum() / len(labels) * 100),
            "pct_negative": float((labels < 0).sum() / len(labels) * 100),
        }
