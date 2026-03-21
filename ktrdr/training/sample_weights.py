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

    For each labeled bar t with active period [t, t + holding_period),
    i.e. over its next ``holding_period`` bars starting at t,
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


def purged_train_val_split(
    labels: pd.Series,
    holding_periods: pd.Series,
    val_ratio: float = 0.2,
    embargo_pct: float = 0.01,
) -> tuple[np.ndarray, np.ndarray]:
    """Purged temporal train/validation split for overlapping labels.

    Standard random splits leak future information when labels have overlapping
    active periods (e.g., triple barrier labels). This function:
    1. Splits temporally: val set is the last val_ratio fraction
    2. Purges: removes training samples whose active period [i, i+hold)
       overlaps with the validation set start
    3. Embargoes: removes an additional buffer of samples before the purge boundary

    Args:
        labels: Series of labels (index used for alignment).
        holding_periods: Series of holding periods (bars) per label.
        val_ratio: Fraction of data for validation (default 0.2).
        embargo_pct: Fraction of total data to embargo before val boundary (default 0.01).

    Returns:
        Tuple of (train_indices, val_indices) as numpy int arrays.
    """
    n = len(labels)
    if n == 0:
        return np.array([], dtype=np.intp), np.array([], dtype=np.intp)

    # Temporal split: val set is the last val_ratio fraction
    val_start = int(n * (1 - val_ratio))

    val_indices = np.arange(val_start, n, dtype=np.intp)

    # Embargo: remove embargo_pct * n samples before val boundary
    embargo_size = int(embargo_pct * n)
    embargo_start = max(0, val_start - embargo_size)

    # Purge: remove training samples whose active period overlaps val set
    # Sample i has active period [i, i + holding_periods[i])
    # It overlaps val set [val_start, n) when i + holding_periods[i] > val_start
    train_indices = []
    purge_boundary = embargo_start  # effective boundary after embargo
    for i in range(purge_boundary):
        hold = int(holding_periods.iloc[i])
        active_end = i + hold  # exclusive end of active period
        if active_end <= val_start:
            train_indices.append(i)

    return np.array(train_indices, dtype=np.intp), val_indices
