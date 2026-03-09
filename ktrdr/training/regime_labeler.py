"""Regime labeling using forward-looking Signed Efficiency Ratio and Realized Volatility.

Generates 4-class regime labels:
  0 = TRENDING_UP    (efficient upward movement)
  1 = TRENDING_DOWN  (efficient downward movement)
  2 = RANGING        (inefficient, bounded movement)
  3 = VOLATILE       (extreme realized volatility)
"""

import numpy as np
import pandas as pd

from ktrdr.errors import DataError

# Regime label constants
TRENDING_UP = 0
TRENDING_DOWN = 1
RANGING = 2
VOLATILE = 3

REGIME_NAMES = {
    TRENDING_UP: "trending_up",
    TRENDING_DOWN: "trending_down",
    RANGING: "ranging",
    VOLATILE: "volatile",
}


class RegimeLabeler:
    """Forward-looking regime labeler using Signed Efficiency Ratio + Realized Volatility.

    Classification priority: VOLATILE > TRENDING_UP > TRENDING_DOWN > RANGING.
    Last `horizon` bars are NaN (no future data available).
    """

    def __init__(
        self,
        horizon: int = 24,
        trending_threshold: float = 0.5,
        vol_crisis_threshold: float = 2.0,
        vol_lookback: int = 120,
    ) -> None:
        """Initialize the regime labeler.

        Args:
            horizon: Number of bars to look ahead for regime classification.
            trending_threshold: Minimum absolute SER to classify as trending (0-1).
            vol_crisis_threshold: RV ratio above this = VOLATILE regime.
            vol_lookback: Number of bars for rolling historical volatility baseline.
        """
        self.horizon = horizon
        self.trending_threshold = trending_threshold
        self.vol_crisis_threshold = vol_crisis_threshold
        self.vol_lookback = vol_lookback

    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate regime labels for each bar.

        Args:
            price_data: DataFrame with 'close' column.

        Returns:
            Series with values 0-3 (float dtype, NaN for last `horizon` bars).

        Raises:
            DataError: If data is missing 'close' column or too short.
        """
        if "close" not in price_data.columns:
            raise DataError(
                "price_data must contain 'close' column",
                details={"columns": list(price_data.columns)},
            )

        min_length = self.horizon + self.vol_lookback + 1
        if len(price_data) < min_length:
            raise DataError(
                f"Data has {len(price_data)} bars, need at least {min_length} "
                f"(horizon={self.horizon} + vol_lookback={self.vol_lookback} + 1)",
                details={
                    "data_length": len(price_data),
                    "horizon": self.horizon,
                    "vol_lookback": self.vol_lookback,
                },
            )

        close = price_data["close"]

        ser = self.compute_signed_efficiency_ratio(close, self.horizon)
        rv_ratio = self.compute_realized_volatility_ratio(
            close, self.horizon, self.vol_lookback
        )

        # Initialize as NaN, then classify
        labels = pd.Series(np.nan, index=price_data.index, dtype=float)

        # Mask for bars where we have both SER and RV values
        valid = ser.notna() & rv_ratio.notna()

        # Classification priority: VOLATILE > TRENDING_UP > TRENDING_DOWN > RANGING
        # Start with RANGING as default, then override
        labels[valid] = RANGING

        # Trending up
        trending_up = valid & (ser > self.trending_threshold)
        labels[trending_up] = TRENDING_UP

        # Trending down
        trending_down = valid & (ser < -self.trending_threshold)
        labels[trending_down] = TRENDING_DOWN

        # Volatile overrides everything
        volatile = valid & (rv_ratio > self.vol_crisis_threshold)
        labels[volatile] = VOLATILE

        return labels

    def compute_signed_efficiency_ratio(
        self, close: pd.Series, horizon: int
    ) -> pd.Series:
        """Forward-looking signed efficiency ratio per bar.

        SER = (close[T+H] - close[T]) / Σ|close[t+1] - close[t]| for t in [T, T+H)

        Range: -1.0 (perfect downtrend) to +1.0 (perfect uptrend).
        Near 0 = ranging (lots of movement, no net direction).
        Returns 0.0 when path length is 0 (constant price).

        Args:
            close: Series of close prices.
            horizon: Number of bars to look ahead.

        Returns:
            Series of SER values. Last `horizon` values are NaN.
        """
        n = len(close)
        ser_values = np.full(n, np.nan)

        close_arr = close.values.astype(float)

        # Absolute bar-to-bar changes
        abs_changes = np.abs(np.diff(close_arr))

        for t in range(n - horizon):
            net_move = close_arr[t + horizon] - close_arr[t]
            path_length = abs_changes[t : t + horizon].sum()

            if path_length == 0.0:
                ser_values[t] = 0.0
            else:
                ser_values[t] = net_move / path_length

        return pd.Series(ser_values, index=close.index, dtype=float)

    def compute_realized_volatility_ratio(
        self, close: pd.Series, horizon: int, lookback: int
    ) -> pd.Series:
        """Forward realized vol / rolling historical vol.

        RV_ratio > threshold indicates extreme volatility (crisis regime).

        Args:
            close: Series of close prices.
            horizon: Number of bars for forward RV window.
            lookback: Number of bars for rolling historical RV baseline.

        Returns:
            Series of RV ratios. NaN where insufficient data.
        """
        n = len(close)
        rv_values = np.full(n, np.nan)

        close_arr = close.values.astype(float)

        # Bar-to-bar log returns for stability
        log_returns = np.diff(np.log(np.maximum(close_arr, 1e-10)))

        for t in range(lookback, n - horizon):
            # Forward realized volatility: std of returns over [t, t+horizon)
            forward_returns = log_returns[t : t + horizon]
            forward_rv = (
                np.std(forward_returns, ddof=1) if len(forward_returns) > 1 else 0.0
            )

            # Historical realized volatility: std of returns over [t-lookback, t)
            hist_returns = log_returns[t - lookback : t]
            hist_rv = np.std(hist_returns, ddof=1) if len(hist_returns) > 1 else 0.0

            if hist_rv > 0:
                rv_values[t] = forward_rv / hist_rv
            else:
                # No historical vol — can't compute ratio meaningfully
                rv_values[t] = 0.0

        return pd.Series(rv_values, index=close.index, dtype=float)
