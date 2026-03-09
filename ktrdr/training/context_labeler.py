"""Context label generation for multi-timeframe trend direction classification.

Generates 3-class forward-looking context labels from daily OHLCV data:
  0 = BULLISH (forward return > bullish_threshold)
  1 = BEARISH (forward return < bearish_threshold)
  2 = NEUTRAL (between thresholds)

Used by Thread 2 (Multi-TF Context) to classify daily trend direction.
The context model predicts these labels from current daily indicators,
providing directional bias that gates the signal model's threshold.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ktrdr.errors import DataError

# Label constants
BULLISH = 0
BEARISH = 1
NEUTRAL = 2


@dataclass
class ContextLabelStats:
    """Statistics from context label analysis.

    Attributes:
        distribution: Fraction of days per context class {0: 0.35, 1: 0.36, 2: 0.29}.
        mean_duration_days: Average consecutive run length per class.
        mean_hourly_return_by_context: Mean hourly return during each context period,
            or None if hourly data was not provided.
        regime_correlation: Cramér's V between context and regime labels,
            or None if regime labels were not provided.
    """

    distribution: dict[int, float]
    mean_duration_days: dict[int, float]
    mean_hourly_return_by_context: dict[int, float] | None
    regime_correlation: float | None


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

    def analyze_labels(
        self,
        labels: pd.Series,
        hourly_data: pd.DataFrame | None = None,
        regime_labels: pd.Series | None = None,
    ) -> ContextLabelStats:
        """Compute statistics on context labels.

        Args:
            labels: Series of context labels (0=BULLISH, 1=BEARISH, 2=NEUTRAL).
                NaN values are excluded from analysis.
            hourly_data: Optional DataFrame with 'close' column at hourly frequency.
                Used to compute mean hourly return by context period.
            regime_labels: Optional Series of regime labels (e.g., 0-3).
                Used to compute correlation (Cramér's V) between context and regime.

        Returns:
            ContextLabelStats with distribution, persistence, and optional metrics.
        """
        valid = labels.dropna()

        distribution = self._compute_distribution(valid)
        mean_duration = self._compute_mean_duration(valid)
        hourly_returns = self._compute_hourly_returns(valid, hourly_data)
        correlation = self._compute_regime_correlation(valid, regime_labels)

        return ContextLabelStats(
            distribution=distribution,
            mean_duration_days=mean_duration,
            mean_hourly_return_by_context=hourly_returns,
            regime_correlation=correlation,
        )

    def _compute_distribution(self, valid_labels: pd.Series) -> dict[int, float]:
        """Compute fraction of days per context class."""
        counts = valid_labels.value_counts()
        total = len(valid_labels)
        dist: dict[int, float] = {}
        for cls in [BULLISH, BEARISH, NEUTRAL]:
            dist[cls] = float(counts.get(cls, 0)) / total if total > 0 else 0.0
        return dist

    def _compute_mean_duration(self, valid_labels: pd.Series) -> dict[int, float]:
        """Compute average consecutive run length (in days) per class."""
        durations: dict[int, list[int]] = {BULLISH: [], BEARISH: [], NEUTRAL: []}

        if len(valid_labels) == 0:
            return dict.fromkeys([BULLISH, BEARISH, NEUTRAL], 0.0)

        current_label = valid_labels.iloc[0]
        run_length = 1

        for i in range(1, len(valid_labels)):
            if valid_labels.iloc[i] == current_label:
                run_length += 1
            else:
                durations[int(current_label)].append(run_length)
                current_label = valid_labels.iloc[i]
                run_length = 1

        # Don't forget the last run
        durations[int(current_label)].append(run_length)

        result: dict[int, float] = {}
        for cls in [BULLISH, BEARISH, NEUTRAL]:
            runs = durations[cls]
            result[cls] = float(np.mean(runs)) if runs else 0.0
        return result

    def _compute_hourly_returns(
        self,
        valid_labels: pd.Series,
        hourly_data: pd.DataFrame | None,
    ) -> dict[int, float] | None:
        """Compute mean hourly return during each context period.

        Forward-fills daily context labels onto hourly timestamps, then
        groups hourly returns by the active context label.
        """
        if hourly_data is None:
            return None

        close = hourly_data["close"]
        hourly_returns = close.pct_change()

        # Forward-fill daily context labels onto hourly index
        # Reindex to union of both indices, forward-fill, then select hourly timestamps
        context_on_hourly = valid_labels.reindex(
            valid_labels.index.union(hourly_data.index)
        ).ffill()
        context_on_hourly = context_on_hourly.reindex(hourly_data.index)

        result: dict[int, float] = {}
        for cls in [BULLISH, BEARISH, NEUTRAL]:
            mask = context_on_hourly == cls
            cls_returns = hourly_returns[mask].dropna()
            result[cls] = float(cls_returns.mean()) if len(cls_returns) > 0 else 0.0

        return result

    def _compute_regime_correlation(
        self,
        valid_labels: pd.Series,
        regime_labels: pd.Series | None,
    ) -> float | None:
        """Compute Cramér's V between context and regime labels.

        Cramér's V measures association between two categorical variables,
        ranging from 0 (independent) to 1 (perfectly associated).
        """
        if regime_labels is None:
            return None

        # Align on common index
        common_idx = valid_labels.index.intersection(regime_labels.index)
        if len(common_idx) < 2:
            return 0.0

        ctx = valid_labels.reindex(common_idx).dropna()
        reg = regime_labels.reindex(common_idx).dropna()

        # Re-align after dropna
        common_idx = ctx.index.intersection(reg.index)
        ctx = ctx.reindex(common_idx)
        reg = reg.reindex(common_idx)

        if len(ctx) < 2:
            return 0.0

        # Build contingency table and compute Cramér's V
        contingency = pd.crosstab(ctx, reg)
        n = contingency.values.sum()
        if n == 0:
            return 0.0

        # Chi-squared statistic
        row_sums = contingency.sum(axis=1).values.astype(float)
        col_sums = contingency.sum(axis=0).values.astype(float)
        expected = np.outer(row_sums, col_sums) / n
        # Avoid division by zero in expected
        with np.errstate(divide="ignore", invalid="ignore"):
            chi2 = np.where(
                expected > 0, (contingency.values - expected) ** 2 / expected, 0.0
            )
        chi2_stat = float(chi2.sum())

        r, k = contingency.shape
        min_dim = min(r, k) - 1
        if min_dim <= 0:
            return 0.0

        cramers_v = float(np.sqrt(chi2_stat / (n * min_dim)))
        return cramers_v
