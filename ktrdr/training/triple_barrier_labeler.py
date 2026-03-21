"""Triple barrier label generation for signal model training.

Generates path-dependent, volatility-adaptive trade outcome labels:
  +1 = take-profit barrier hit
   0 = time expiry (vertical barrier)
  -1 = stop-loss barrier hit

Based on the triple barrier method from Advances in Financial Machine Learning.
"""

import logging

import numpy as np
import pandas as pd

from ktrdr.errors import DataError

logger = logging.getLogger(__name__)


class TripleBarrierLabeler:
    """Generate triple barrier labels from OHLCV price data.

    For each bar, sets volatility-scaled upper (take-profit) and lower
    (stop-loss) barriers plus a vertical (time) barrier. Walks forward
    through high/low to detect intrabar barrier hits.

    Labels:
        +1: Upper barrier hit first (take-profit)
         0: Vertical barrier hit (time expiry, return near zero)
        -1: Lower barrier hit first (stop-loss)
    """

    REQUIRED_COLUMNS = {"open", "high", "low", "close"}

    def __init__(
        self,
        pt_multiplier: float = 2.0,
        sl_multiplier: float = 1.5,
        max_holding_period: int = 50,
        vol_span: int = 50,
        vol_method: str = "atr",
    ):
        """Initialize the labeler.

        Args:
            pt_multiplier: Multiplier for vol to set upper barrier.
            sl_multiplier: Multiplier for vol to set lower barrier.
            max_holding_period: Maximum bars before vertical barrier.
            vol_span: EWMA span for volatility estimation.
            vol_method: Volatility estimation method.
                "atr" (default): Uses true range (high-low), appropriate when
                    barriers are checked against high/low. Produces wider
                    barriers that account for intrabar price range.
                "close": Uses close-to-close log returns. Produces narrower
                    barriers that may be triggered too quickly by intrabar noise.
        """
        self.pt_multiplier = pt_multiplier
        self.sl_multiplier = sl_multiplier
        self.max_holding_period = max_holding_period
        self.vol_span = vol_span
        self.vol_method = vol_method

        # Populated after generate_labels()
        self._holding_periods: pd.Series | None = None
        self._upper_barriers: np.ndarray | None = None
        self._lower_barriers: np.ndarray | None = None

    def generate_labels(self, price_data: pd.DataFrame) -> pd.Series:
        """Generate triple barrier labels.

        Args:
            price_data: DataFrame with OHLCV columns.

        Returns:
            Series of labels (+1, 0, -1), length = len(price_data) - max_holding_period.
            Last max_holding_period rows trimmed (insufficient future data).

        Raises:
            DataError: If data is insufficient or missing required columns.
        """
        self._validate_input(price_data)

        close = price_data["close"].to_numpy()
        high = price_data["high"].to_numpy()
        low = price_data["low"].to_numpy()

        # Compute volatility estimate
        daily_vol = self._compute_volatility(close, high, low)

        # Fill early NaN/zero values with first valid vol estimate
        first_valid = min(self.vol_span, len(daily_vol) - 1)
        for i in range(first_valid):
            if np.isnan(daily_vol[i]) or daily_vol[i] == 0:
                daily_vol[i] = (
                    daily_vol[first_valid] if first_valid < len(daily_vol) else 0.01
                )

        n_labels = len(price_data) - self.max_holding_period
        labels = np.zeros(n_labels, dtype=np.int64)
        holding_periods = np.zeros(n_labels, dtype=np.int64)
        upper_barriers = np.zeros(n_labels)
        lower_barriers = np.zeros(n_labels)

        for t in range(n_labels):
            entry_price = close[t]
            vol = daily_vol[t]

            # Set barriers
            upper = entry_price * (1 + self.pt_multiplier * vol)
            lower = entry_price * (1 - self.sl_multiplier * vol)
            upper_barriers[t] = (upper - entry_price) / entry_price
            lower_barriers[t] = (entry_price - lower) / entry_price

            # Walk forward through the holding period
            label = 0
            hold = self.max_holding_period

            for dt in range(1, self.max_holding_period + 1):
                idx = t + dt
                bar_high = high[idx]
                bar_low = low[idx]

                hit_upper = bar_high >= upper
                hit_lower = bar_low <= lower

                if hit_upper and hit_lower:
                    # Simultaneous hit — use close direction
                    bar_close = close[idx]
                    if bar_close >= entry_price:
                        label = 1
                    else:
                        label = -1
                    hold = dt
                    break
                elif hit_upper:
                    label = 1
                    hold = dt
                    break
                elif hit_lower:
                    label = -1
                    hold = dt
                    break

            if label == 0:
                # Vertical barrier — use sign of return
                final_close = close[t + self.max_holding_period]
                ret = (final_close - entry_price) / entry_price
                # Expiry threshold: scale with vol and sqrt(holding period)
                # If return is within this band, it's noise → expiry (0)
                expiry_threshold = vol * np.sqrt(self.max_holding_period) * 0.5
                if abs(ret) < expiry_threshold:
                    label = 0
                else:
                    label = int(np.sign(ret))
                hold = self.max_holding_period

            labels[t] = label
            holding_periods[t] = hold

        index = price_data.index[:n_labels]
        self._holding_periods = pd.Series(
            holding_periods, index=index, name="holding_period"
        )
        self._upper_barriers = upper_barriers
        self._lower_barriers = lower_barriers

        return pd.Series(labels, index=index, name="triple_barrier_label")

    def get_holding_periods(self) -> pd.Series | None:
        """Return holding periods from the last generate_labels() call.

        Returns:
            Series of holding period (bars) per label, or None if not yet computed.
        """
        return self._holding_periods

    def get_label_statistics(self, labels: pd.Series) -> dict:
        """Return distribution statistics for generated labels.

        Args:
            labels: Series of triple barrier labels.

        Returns:
            Dict with class distribution, holding periods, and barrier widths.
        """
        n = len(labels)
        tp_count = int((labels == 1).sum())
        sl_count = int((labels == -1).sum())
        exp_count = int((labels == 0).sum())

        stats: dict = {
            "total_labels": n,
            "take_profit_pct": tp_count / n * 100 if n else 0.0,
            "stop_loss_pct": sl_count / n * 100 if n else 0.0,
            "time_expiry_pct": exp_count / n * 100 if n else 0.0,
            "take_profit_count": tp_count,
            "stop_loss_count": sl_count,
            "time_expiry_count": exp_count,
        }

        if self._holding_periods is not None and len(self._holding_periods) > 0:
            stats["mean_holding_period"] = float(self._holding_periods.mean())
            stats["median_holding_period"] = float(self._holding_periods.median())
        else:
            stats["mean_holding_period"] = 0.0
            stats["median_holding_period"] = 0.0

        if (
            self._upper_barriers is not None
            and self._lower_barriers is not None
            and len(self._upper_barriers) > 0
        ):
            stats["avg_upper_barrier_pct"] = float(np.mean(self._upper_barriers) * 100)
            stats["avg_lower_barrier_pct"] = float(np.mean(self._lower_barriers) * 100)
        else:
            stats["avg_upper_barrier_pct"] = 0.0
            stats["avg_lower_barrier_pct"] = 0.0

        return stats

    def _compute_volatility(
        self,
        close: np.ndarray,
        high: np.ndarray,
        low: np.ndarray,
    ) -> np.ndarray:
        """Compute per-bar volatility estimate.

        Args:
            close: Close prices array.
            high: High prices array.
            low: Low prices array.

        Returns:
            Array of volatility estimates, same length as close.
        """
        if self.vol_method == "atr":
            # True range as fraction of close — matches barrier check against high/low
            true_range = (high - low) / close
            # EWMA smoothing of true range
            atr = pd.Series(true_range).ewm(span=self.vol_span).mean()
            return atr.to_numpy().astype(np.float64)
        else:
            # Close-to-close log return volatility
            log_returns = np.diff(np.log(close.astype(np.float64)))
            vol_series = pd.Series(log_returns).ewm(span=self.vol_span).std()
            daily_vol = np.empty(len(close), dtype=np.float64)
            daily_vol[0] = np.nan
            daily_vol[1:] = vol_series.to_numpy()
            return daily_vol

    def _validate_input(self, price_data: pd.DataFrame) -> None:
        """Validate input data."""
        missing = self.REQUIRED_COLUMNS - set(price_data.columns)
        if missing:
            raise DataError(
                f"price_data missing required columns: {missing}",
                details={"columns": list(price_data.columns), "missing": list(missing)},
            )

        min_required = self.max_holding_period + self.vol_span
        if len(price_data) < min_required:
            raise DataError(
                f"Insufficient data: need at least {min_required} bars "
                f"(max_holding_period={self.max_holding_period} + vol_span={self.vol_span}), "
                f"got {len(price_data)}",
                details={
                    "data_length": len(price_data),
                    "min_required": min_required,
                },
            )
