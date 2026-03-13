"""Multi-scale zigzag regime labeling for supervised learning.

Uses two zigzag scales (macro + micro) to read the market's own swing structure,
then classifies bars based on whether micro pivots show directional progression
within each macro segment.

Auto-adapts to any timeframe/instrument via ATR-scaled zigzag thresholds.

Produces 4-class labels:
  0 = TRENDING_UP    (macro up-segment with progressive higher-lows)
  1 = TRENDING_DOWN  (macro down-segment with progressive lower-highs)
  2 = RANGING        (macro segment but micro pivots don't progress)
  3 = VOLATILE       (extreme realized volatility)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ktrdr.errors import DataError
from ktrdr.training.regime_labeler import (
    RANGING,
    REGIME_NAMES,
    TRENDING_DOWN,
    TRENDING_UP,
    VOLATILE,
    RegimeLabelStats,
)


@dataclass
class MacroSegment:
    """A segment between two consecutive macro zigzag pivots."""

    start_idx: int
    end_idx: int
    direction: str  # "up" or "down"
    start_price: float
    end_price: float


class MultiScaleRegimeLabeler:
    """Forward-looking regime labeler using multi-scale zigzag + volatility overlay.

    Two zigzag scales read the market's own swing structure:
    - Macro zigzag (large threshold) captures dominant trend direction
    - Micro zigzag (small threshold) captures local structure quality
    - Progression of micro pivots distinguishes trending from ranging

    Parameters are dimensionless ATR multipliers, so the labeler auto-adapts
    to any timeframe and any instrument without manual tuning.
    """

    def __init__(
        self,
        macro_atr_mult: float = 3.0,
        micro_atr_mult: float = 1.0,
        atr_period: int = 14,
        vol_lookback: int = 120,
        vol_crisis_threshold: float = 2.0,
        progression_tolerance: float = 0.5,
    ) -> None:
        """Initialize the multi-scale regime labeler.

        Args:
            macro_atr_mult: ATR multiplier for macro zigzag threshold.
                Larger = fewer, bigger swings captured.
            micro_atr_mult: ATR multiplier for micro zigzag threshold.
                Smaller = more local detail captured.
            atr_period: Period for ATR calculation.
            vol_lookback: Rolling window for historical volatility baseline.
            vol_crisis_threshold: RV ratio above this = VOLATILE regime.
            progression_tolerance: Fraction of consecutive pivot pairs that must
                progress for a segment to be classified as trending (0-1).
                1.0 = strict monotonic, 0.5 = majority progressive.
        """
        self.macro_atr_mult = macro_atr_mult
        self.micro_atr_mult = micro_atr_mult
        self.atr_period = atr_period
        self.vol_lookback = vol_lookback
        self.vol_crisis_threshold = vol_crisis_threshold
        self.progression_tolerance = progression_tolerance

    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate regime labels for each bar.

        Args:
            price_data: DataFrame with OHLCV columns (at minimum 'close', 'high', 'low').

        Returns:
            Series with values 0-3 (float dtype, NaN for bars outside macro segments
            or with insufficient data).

        Raises:
            DataError: If required columns are missing.
        """
        for col in ("close", "high", "low"):
            if col not in price_data.columns:
                raise DataError(
                    f"price_data must contain '{col}' column",
                    details={"columns": list(price_data.columns)},
                )

        n = len(price_data)
        labels = pd.Series(np.nan, index=price_data.index, dtype=float)

        # Need enough data for ATR calculation
        if n < self.atr_period + 2:
            return labels

        # Step 1: Compute ATR-scaled thresholds
        macro_threshold = self._compute_atr_threshold(price_data, self.macro_atr_mult)
        micro_threshold = self._compute_atr_threshold(price_data, self.micro_atr_mult)

        # Handle degenerate case (constant price → ATR=0 → threshold=0)
        if macro_threshold <= 0 or micro_threshold <= 0:
            return labels

        close = price_data["close"].values.astype(float)

        # Step 2: Run zigzag at both scales
        macro_pivots = self._run_zigzag(close, macro_threshold)
        micro_pivots = self._run_zigzag(close, micro_threshold)

        if len(macro_pivots) < 2:
            return labels

        # Step 3: Extract macro segments
        macro_segments = self._extract_macro_segments(macro_pivots, n)

        # Step 4: Compute volatility mask
        vol_mask = self._compute_volatility_mask(price_data)

        # Step 5: Classify each bar
        for segment in macro_segments:
            # Get micro pivots within this macro segment
            segment_micro = [
                p for p in micro_pivots if segment.start_idx <= p[0] <= segment.end_idx
            ]

            # Check micro progression
            is_progressive = self._check_micro_progression(
                segment_micro, segment.direction
            )

            # Assign labels for all bars in this segment
            for bar_idx in range(segment.start_idx, segment.end_idx + 1):
                if bar_idx >= n:
                    break

                # Volatility takes priority
                if (
                    vol_mask is not None
                    and bar_idx < len(vol_mask)
                    and vol_mask.iloc[bar_idx]
                ):
                    labels.iloc[bar_idx] = VOLATILE
                elif is_progressive:
                    if segment.direction == "up":
                        labels.iloc[bar_idx] = TRENDING_UP
                    else:
                        labels.iloc[bar_idx] = TRENDING_DOWN
                else:
                    labels.iloc[bar_idx] = RANGING

        return labels

    def _compute_atr_threshold(
        self, price_data: pd.DataFrame, atr_mult: float
    ) -> float:
        """Compute zigzag threshold as percentage from ATR.

        threshold = atr_mult x median(ATR(atr_period)) / median(close)

        This makes the threshold dimensionless and auto-scaling:
        works for any instrument (EURUSD ~1.10, BTC ~50000) and
        any timeframe (1m, 1h, 1d).

        Args:
            price_data: DataFrame with 'high', 'low', 'close' columns.
            atr_mult: ATR multiplier for this zigzag scale.

        Returns:
            Threshold as a fraction (e.g., 0.02 for 2%).
        """
        high = price_data["high"].values.astype(float)
        low = price_data["low"].values.astype(float)
        close = price_data["close"].values.astype(float)

        # True Range calculation
        n = len(close)
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(
                high[i] - low[i],
                abs(high[i] - close[i - 1]),
                abs(low[i] - close[i - 1]),
            )

        # ATR as simple moving average of TR
        if n < self.atr_period:
            return 0.0

        atr_values = np.convolve(
            tr, np.ones(self.atr_period) / self.atr_period, mode="valid"
        )

        median_atr = float(np.median(atr_values))
        median_close = float(np.median(close))

        if median_close <= 0:
            return 0.0

        return atr_mult * median_atr / median_close

    def _run_zigzag(
        self, close: np.ndarray, threshold: float
    ) -> list[tuple[int, float]]:
        """Run zigzag algorithm, return list of (index, price) pivot points.

        Uses percentage-based reversal detection: a new pivot is confirmed when
        price moves threshold% away from the current extreme in the opposite direction.

        Args:
            close: Array of close prices.
            threshold: Minimum percentage move to constitute a reversal (as fraction).

        Returns:
            List of (bar_index, price) tuples representing zigzag pivots.
        """
        n = len(close)
        if n < 3:
            return [(0, float(close[0]))]

        pivots: list[tuple[int, float]] = []

        last_extreme_idx = 0
        last_extreme_price = close[0]
        direction: int | None = None  # 1 = uptrend, -1 = downtrend

        # First point is always a pivot
        pivots.append((0, float(close[0])))

        for i in range(1, n):
            current_price = close[i]

            if last_extreme_price == 0:
                continue

            pct_change = (current_price - last_extreme_price) / last_extreme_price

            if direction is None:
                # Determine initial direction
                if abs(pct_change) >= threshold:
                    direction = 1 if pct_change > 0 else -1
                    # Update the first pivot to be the actual starting extreme
                    # (may differ from index 0 if the first move is tiny)
                    last_extreme_idx = i
                    last_extreme_price = current_price

            elif direction == 1:  # Uptrend
                if current_price > last_extreme_price:
                    # New high — update extreme (don't add pivot yet)
                    last_extreme_idx = i
                    last_extreme_price = current_price
                elif pct_change <= -threshold:
                    # Reversal down — confirm the high as a pivot
                    pivots.append((last_extreme_idx, float(last_extreme_price)))
                    direction = -1
                    last_extreme_idx = i
                    last_extreme_price = current_price

            elif direction == -1:  # Downtrend
                if current_price < last_extreme_price:
                    # New low — update extreme
                    last_extreme_idx = i
                    last_extreme_price = current_price
                elif pct_change >= threshold:
                    # Reversal up — confirm the low as a pivot
                    pivots.append((last_extreme_idx, float(last_extreme_price)))
                    direction = 1
                    last_extreme_idx = i
                    last_extreme_price = current_price

        # Always add the last extreme as a pivot
        if pivots[-1][0] != last_extreme_idx:
            pivots.append((last_extreme_idx, float(last_extreme_price)))

        return pivots

    def _extract_macro_segments(
        self, pivots: list[tuple[int, float]], n_bars: int
    ) -> list[MacroSegment]:
        """Convert macro pivots to segments with direction and bar ranges.

        Args:
            pivots: List of (index, price) pivot points.
            n_bars: Total number of bars in the data.

        Returns:
            List of MacroSegment dataclasses.
        """
        segments: list[MacroSegment] = []

        for i in range(len(pivots) - 1):
            start_idx, start_price = pivots[i]
            end_idx, end_price = pivots[i + 1]

            direction = "up" if end_price > start_price else "down"

            segments.append(
                MacroSegment(
                    start_idx=start_idx,
                    end_idx=end_idx,
                    direction=direction,
                    start_price=start_price,
                    end_price=end_price,
                )
            )

        return segments

    def _check_micro_progression(
        self,
        micro_pivots: list[tuple[int, float]],
        macro_direction: str,
    ) -> bool:
        """Check whether micro pivots show directional progression.

        For macro "up": check if micro pivot lows form higher-lows.
        For macro "down": check if micro pivot highs form lower-highs.

        Zigzag pivots alternate between highs and lows. We classify each pivot
        based on its neighbors, then check whether the relevant subset
        (lows for up-trend, highs for down-trend) shows progression.

        Args:
            micro_pivots: List of (index, price) micro zigzag pivots, in index order.
            macro_direction: "up" or "down".

        Returns:
            True if fraction of progressive pairs >= progression_tolerance.
        """
        if len(micro_pivots) < 4:
            # Need at least 4 pivots to have 2 of the same type for comparison
            return False

        # Classify each pivot as "high" or "low" in chronological order.
        # Zigzag pivots alternate, so we determine each pivot's role
        # relative to its neighbors.
        highs: list[float] = []
        lows: list[float] = []

        n_pivots = len(micro_pivots)
        for i in range(n_pivots):
            price = micro_pivots[i][1]

            if i == 0:
                # First pivot: compare with next
                next_price = micro_pivots[1][1]
                if price < next_price:
                    lows.append(price)
                else:
                    highs.append(price)
            elif i == n_pivots - 1:
                # Last pivot: compare with previous
                prev_price = micro_pivots[i - 1][1]
                if price < prev_price:
                    lows.append(price)
                else:
                    highs.append(price)
            else:
                # Middle pivot: compare with both neighbors
                prev_price = micro_pivots[i - 1][1]
                next_price = micro_pivots[i + 1][1]
                if price > prev_price and price > next_price:
                    highs.append(price)
                elif price < prev_price and price < next_price:
                    lows.append(price)
                # If neither (equal or monotonic), skip — ambiguous

        if macro_direction == "up":
            return self._is_progressive_sequence(lows, ascending=True)
        else:
            return self._is_progressive_sequence(highs, ascending=False)

    def _is_progressive_sequence(self, values: list[float], ascending: bool) -> bool:
        """Check if a sequence of values is progressive.

        Args:
            values: List of pivot prices to check.
            ascending: True for higher-lows check, False for lower-highs.

        Returns:
            True if fraction of consecutive pairs showing progression
            meets the tolerance threshold.
        """
        if len(values) < 2:
            return False

        progressive_pairs = 0
        total_pairs = len(values) - 1

        for i in range(total_pairs):
            if ascending:
                if values[i + 1] > values[i]:
                    progressive_pairs += 1
            else:
                if values[i + 1] < values[i]:
                    progressive_pairs += 1

        fraction = progressive_pairs / total_pairs
        return fraction >= self.progression_tolerance

    def _compute_volatility_mask(self, price_data: pd.DataFrame) -> pd.Series | None:
        """Compute boolean mask for VOLATILE bars using RV ratio.

        Uses forward realized volatility / rolling historical volatility.
        Returns None if insufficient data for volatility computation.

        Args:
            price_data: DataFrame with 'close' column.

        Returns:
            Boolean Series (True where VOLATILE) or None if insufficient data.
        """
        close = price_data["close"].values.astype(float)
        n = len(close)

        if n < self.vol_lookback + 2:
            return None

        # Log returns
        log_returns = np.diff(np.log(np.maximum(close, 1e-10)))

        # Rolling historical volatility (standard deviation of log returns)
        mask = pd.Series(False, index=price_data.index)

        # Use a forward window equal to ATR period for forward vol measurement
        forward_window = self.atr_period

        for t in range(self.vol_lookback, n - forward_window):
            # Forward realized volatility
            forward_returns = log_returns[t : t + forward_window]
            forward_rv = (
                float(np.std(forward_returns, ddof=1))
                if len(forward_returns) > 1
                else 0.0
            )

            # Historical realized volatility
            hist_returns = log_returns[t - self.vol_lookback : t]
            hist_rv = (
                float(np.std(hist_returns, ddof=1)) if len(hist_returns) > 1 else 0.0
            )

            if hist_rv > 0:
                rv_ratio = forward_rv / hist_rv
                if rv_ratio > self.vol_crisis_threshold:
                    mask.iloc[t] = True

        return mask

    def analyze_labels(
        self,
        labels: pd.Series,
        price_data: pd.DataFrame,
    ) -> RegimeLabelStats:
        """Compute label quality statistics.

        Delegates to the analysis methods shared with the v1 RegimeLabeler.
        Uses RegimeLabelStats from regime_labeler module.

        Args:
            labels: Series of regime labels (0-3, may contain NaN).
            price_data: DataFrame with 'close' column.

        Returns:
            RegimeLabelStats with distribution, duration, return, and transition analysis.
        """
        valid_labels = labels.dropna().astype(int)
        total_bars = len(valid_labels)

        if total_bars == 0:
            return RegimeLabelStats(
                distribution={},
                mean_duration_bars={},
                mean_return_by_regime={},
                transition_matrix={},
                total_bars=0,
                total_transitions=0,
            )

        # Distribution
        distribution: dict[str, float] = {}
        for label_val, name in REGIME_NAMES.items():
            count = int((valid_labels == label_val).sum())
            if count > 0:
                distribution[name] = count / total_bars

        # Mean duration (consecutive run length)
        mean_duration_bars = self._compute_mean_durations(valid_labels)

        # Mean return by regime — use ATR period as a reasonable forward horizon
        mean_return_by_regime = self._compute_mean_returns(
            valid_labels, price_data, horizon=self.atr_period
        )

        # Transitions
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

        # Last run
        name = REGIME_NAMES[int(current_label)]
        durations.setdefault(name, []).append(current_run)

        return {regime: float(np.mean(runs)) for regime, runs in durations.items()}

    def _compute_mean_returns(
        self, labels: pd.Series, price_data: pd.DataFrame, horizon: int
    ) -> dict[str, float]:
        """Compute mean forward return grouped by regime label."""
        close = price_data["close"]
        future_close = close.shift(-horizon)
        forward_returns = (future_close - close) / close

        result: dict[str, float] = {}
        for label_val, name in REGIME_NAMES.items():
            label_indices = labels[labels == label_val].index
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

        # Normalize to probabilities
        matrix: dict[str, dict[str, float]] = {}
        for from_regime, to_counts in transitions.items():
            row_total = sum(to_counts.values())
            matrix[from_regime] = {
                to_regime: count / row_total for to_regime, count in to_counts.items()
            }

        return matrix, total
