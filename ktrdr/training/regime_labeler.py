"""Regime labeling using forward-looking Signed Efficiency Ratio and Realized Volatility.

Generates 4-class regime labels:
  0 = TRENDING_UP    (efficient upward movement)
  1 = TRENDING_DOWN  (efficient downward movement)
  2 = RANGING        (inefficient, bounded movement)
  3 = VOLATILE       (extreme realized volatility)
"""

from dataclasses import dataclass

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
        trending_threshold: float = 0.3,
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

    def analyze_labels(
        self,
        labels: pd.Series,
        price_data: pd.DataFrame,
    ) -> "RegimeLabelStats":
        """Compute label quality statistics.

        Analyzes distribution, persistence, return differentiation,
        and transition patterns across regime labels.

        Args:
            labels: Series of regime labels (0-3, may contain NaN).
            price_data: DataFrame with 'close' column (same index as labels).

        Returns:
            RegimeLabelStats with distribution, duration, return, and transition analysis.
        """
        # Drop NaN labels for analysis
        valid_labels = labels.dropna().astype(int)
        total_bars = len(valid_labels)

        # Distribution: fraction of bars per regime
        distribution: dict[str, float] = {}
        for label_val, name in REGIME_NAMES.items():
            count = (valid_labels == label_val).sum()
            if count > 0:
                distribution[name] = count / total_bars

        # Mean duration: average consecutive run length per regime
        mean_duration_bars = self._compute_mean_durations(valid_labels)

        # Mean return by regime: forward return grouped by label
        mean_return_by_regime = self._compute_mean_returns(valid_labels, price_data)

        # Transition matrix and count
        transition_matrix, total_transitions = self._compute_transitions(valid_labels)

        return RegimeLabelStats(
            distribution=distribution,
            mean_duration_bars=mean_duration_bars,
            mean_return_by_regime=mean_return_by_regime,
            transition_matrix=transition_matrix,
            total_bars=total_bars,
            total_transitions=total_transitions,
        )

    def _compute_mean_durations(self, labels: pd.Series) -> dict[str, float]:
        """Compute average consecutive run length per regime."""
        durations: dict[str, list[int]] = {}

        if len(labels) == 0:
            return {}

        arr = labels.values
        current_label = arr[0]
        current_run = 1

        for i in range(1, len(arr)):
            if arr[i] == current_label:
                current_run += 1
            else:
                name = REGIME_NAMES[int(current_label)]
                durations.setdefault(name, []).append(current_run)
                current_label = arr[i]
                current_run = 1

        # Don't forget the last run
        name = REGIME_NAMES[int(current_label)]
        durations.setdefault(name, []).append(current_run)

        return {regime: float(np.mean(runs)) for regime, runs in durations.items()}

    def _compute_mean_returns(
        self, labels: pd.Series, price_data: pd.DataFrame
    ) -> dict[str, float]:
        """Compute mean forward return grouped by regime label."""
        close = price_data["close"]
        horizon = self.horizon

        # Forward return: (close[T+H] - close[T]) / close[T]
        future_close = close.shift(-horizon)
        forward_returns = (future_close - close) / close

        result: dict[str, float] = {}
        for label_val, name in REGIME_NAMES.items():
            # Get indices where this label applies
            label_indices = labels[labels == label_val].index
            # Intersect with forward_returns index to handle length mismatches
            common_idx = label_indices.intersection(forward_returns.index)
            regime_returns = forward_returns.loc[common_idx].dropna()
            if len(regime_returns) > 0:
                result[name] = float(regime_returns.mean())

        return result

    def _compute_transitions(
        self, labels: pd.Series
    ) -> tuple[dict[str, dict[str, float]], int]:
        """Compute transition matrix and total transition count."""
        if len(labels) < 2:
            return {}, 0

        # Find transition points
        transitions: dict[str, dict[str, int]] = {}
        total = 0
        arr = labels.values

        for i in range(1, len(arr)):
            if arr[i] != arr[i - 1]:
                from_name = REGIME_NAMES[int(arr[i - 1])]
                to_name = REGIME_NAMES[int(arr[i])]
                transitions.setdefault(from_name, {})
                transitions[from_name][to_name] = (
                    transitions[from_name].get(to_name, 0) + 1
                )
                total += 1

        # Normalize rows to probabilities
        matrix: dict[str, dict[str, float]] = {}
        for from_regime, to_counts in transitions.items():
            row_total = sum(to_counts.values())
            matrix[from_regime] = {
                to_regime: count / row_total for to_regime, count in to_counts.items()
            }

        return matrix, total


@dataclass
class RegimeLabelStats:
    """Analysis of regime label quality."""

    distribution: dict[str, float]
    mean_duration_bars: dict[str, float]
    mean_return_by_regime: dict[str, float]
    transition_matrix: dict[str, dict[str, float]]
    total_bars: int
    total_transitions: int
