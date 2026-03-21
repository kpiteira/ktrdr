"""Sample uniqueness weighting for triple barrier labels.

Because triple barrier labels have overlapping active periods,
samples are not independent. Uniqueness weighting assigns lower
weights to samples that overlap heavily with others.
"""

import numpy as np
import pandas as pd


def compute_uniqueness_weights(
    labels: pd.Series,
    holding_periods: pd.Series,
    normalize: bool = False,
) -> pd.Series:
    """Compute sample uniqueness weights based on label concurrency.

    For each labeled bar t with active period [t, t + holding_period],
    the weight is the average of 1/concurrency across its active period.

    Args:
        labels: Series of labels (used for index alignment).
        holding_periods: Series of holding periods (bars) per label.
        normalize: If True, normalize weights to have mean 1.0.

    Returns:
        Series of float weights, same index as labels.
    """
    n = len(labels)
    if n == 0:
        return pd.Series([], dtype=float)

    # Build concurrency array
    # Maximum possible extent: last label index + its holding period
    max_extent = n + int(holding_periods.max()) if n > 0 else 0
    concurrency = np.zeros(max_extent, dtype=np.float64)

    # Count how many labels are "active" at each position
    for i in range(n):
        hold = int(holding_periods.iloc[i])
        for j in range(hold):
            if i + j < max_extent:
                concurrency[i + j] += 1.0

    # Compute weight for each sample
    weights = np.zeros(n, dtype=np.float64)
    for i in range(n):
        hold = int(holding_periods.iloc[i])
        inv_conc_sum = 0.0
        count = 0
        for j in range(hold):
            if i + j < max_extent and concurrency[i + j] > 0:
                inv_conc_sum += 1.0 / concurrency[i + j]
                count += 1
        weights[i] = inv_conc_sum / count if count > 0 else 1.0

    if normalize and n > 0:
        mean_w = weights.mean()
        if mean_w > 0:
            weights = weights / mean_w

    return pd.Series(weights, index=labels.index, name="uniqueness_weight")
