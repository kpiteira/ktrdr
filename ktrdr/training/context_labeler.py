"""Context label generation for multi-timeframe trend direction classification.

Generates 3-class forward-looking context labels from daily OHLCV data:
  0 = BULLISH (forward return > bullish_threshold)
  1 = BEARISH (forward return < bearish_threshold)
  2 = NEUTRAL (between thresholds)

Used by Thread 2 (Multi-TF Context) to classify daily trend direction.
The context model predicts these labels from current daily indicators,
providing directional bias that gates the signal model's threshold.
"""

import pandas as pd

from ktrdr.errors import DataError

# Label constants
BULLISH = 0
BEARISH = 1
NEUTRAL = 2


class ContextLabeler:
    """Generate forward-looking trend direction labels from daily OHLCV data.

    Labels classify whether the market moved up, down, or sideways over the
    next `horizon` daily bars, using signed return thresholds.
    """

    def __init__(
        self,
        horizon: int = 5,
        bullish_threshold: float = 0.005,
        bearish_threshold: float = -0.005,
    ):
        """Initialize the context labeler.

        Args:
            horizon: Number of daily bars to look ahead for return calculation.
            bullish_threshold: Minimum forward return to classify as BULLISH.
            bearish_threshold: Maximum forward return to classify as BEARISH (negative).
        """
        self.horizon = horizon
        self.bullish_threshold = bullish_threshold
        self.bearish_threshold = bearish_threshold

    def label(self, daily_ohlcv: pd.DataFrame) -> pd.Series:
        """Generate context labels from daily OHLCV data.

        Computes forward return over `horizon` bars and classifies:
          > bullish_threshold  → 0 (BULLISH)
          < bearish_threshold  → 1 (BEARISH)
          else                 → 2 (NEUTRAL)

        Last `horizon` bars are NaN (no future data available).

        Args:
            daily_ohlcv: DataFrame with at least a 'close' column.

        Returns:
            Series of float values: 0.0, 1.0, 2.0, or NaN for trailing bars.

        Raises:
            DataError: If close column is missing, contains zeros, or data is empty.
        """
        if "close" not in daily_ohlcv.columns:
            raise DataError(
                "daily_ohlcv must contain 'close' column",
                details={"columns": list(daily_ohlcv.columns)},
            )

        if len(daily_ohlcv) == 0:
            raise DataError(
                "daily_ohlcv is empty",
                details={"data_length": 0},
            )

        close = daily_ohlcv["close"]

        if (close == 0).any():
            raise DataError(
                "Close prices contain zero values, cannot compute returns",
                details={"zero_count": int((close == 0).sum())},
            )

        # Compute forward return: (close[T+H] - close[T]) / close[T]
        future_close = close.shift(-self.horizon)
        forward_return = (future_close - close) / close

        # Classify into 3 classes
        labels = pd.Series(float(NEUTRAL), index=daily_ohlcv.index)
        labels[forward_return > self.bullish_threshold] = float(BULLISH)
        labels[forward_return < self.bearish_threshold] = float(BEARISH)

        # Last horizon bars have no future data — mark as NaN
        labels.iloc[-self.horizon :] = float("nan")

        # Handle case where data is shorter than horizon (all NaN)
        if len(daily_ohlcv) <= self.horizon:
            labels[:] = float("nan")

        return labels
