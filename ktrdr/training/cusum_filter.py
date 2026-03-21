"""CUSUM (Cumulative Sum) event filter for selective bar labeling.

Identifies bars where a significant price move has accumulated,
producing a smaller but higher-quality training set.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CUSUMFilter:
    """CUSUM filter that emits events at significant price moves.

    Maintains two running sums (positive and negative). When either
    exceeds the threshold, an event is emitted and that sum resets.

    This is a pure filter — it selects WHICH bars to label, not
    HOW to label them. In the training pipeline, labels are generated
    on the full series and this filter is then used to select event bars.
    """

    def __init__(
        self,
        threshold: float | None = None,
        cusum_multiplier: float = 0.5,
        vol_span: int = 50,
    ):
        """Initialize the CUSUM filter.

        Args:
            threshold: Fixed threshold for event detection. If None,
                computed as cusum_multiplier * ewma_vol.
            cusum_multiplier: Multiplier for auto-threshold from volatility.
                Only used when threshold is None. Default 0.5 targets 30-60%
                event retention on typical FX hourly data. Note: the CUSUM
                algorithm effectively doubles the threshold (subtracts h from
                each return AND requires accumulation > h), so 0.5x vol gives
                an effective threshold of ~1x vol.
            vol_span: EWMA span for volatility estimation (auto-threshold mode).
        """
        self.threshold = threshold
        self.cusum_multiplier = cusum_multiplier
        self.vol_span = vol_span

    def filter(self, price_data: pd.DataFrame) -> pd.Series:
        """Apply CUSUM filter to price data.

        Args:
            price_data: DataFrame with 'close' column.

        Returns:
            Boolean Series (True = event bar), aligned with input index.
        """
        close = price_data["close"].values
        log_returns = np.diff(np.log(close.astype(np.float64)))

        # Determine threshold
        if self.threshold is not None:
            h = self.threshold
        else:
            vol = pd.Series(log_returns).ewm(span=self.vol_span).std().mean()
            h = self.cusum_multiplier * vol
            logger.info(
                f"CUSUM auto-threshold: vol={vol:.6f}, "
                f"multiplier={self.cusum_multiplier}, threshold={h:.6f}"
            )

        # Run CUSUM
        events = np.zeros(len(close), dtype=bool)
        s_pos = 0.0
        s_neg = 0.0

        for i in range(len(log_returns)):
            r = log_returns[i]
            s_pos = max(0.0, s_pos + (r - h))
            s_neg = min(0.0, s_neg + (r + h))

            if s_pos > h:
                events[i + 1] = True  # +1 because log_returns is offset by 1
                s_pos = 0.0
            elif s_neg < -h:
                events[i + 1] = True
                s_neg = 0.0

        return pd.Series(events, index=price_data.index, name="cusum_event")
