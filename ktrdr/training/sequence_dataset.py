"""Sliding window dataset for temporal models (LSTM/GRU)."""

import torch
from torch.utils.data import Dataset


class SequenceDataset(Dataset):
    """Creates sliding windows from 2D feature matrices for sequence models.

    Given a 2D feature matrix (T timestamps, F features) and labels (T,),
    produces samples of (sequence_length, F) paired with the label of the
    last timestamp in each window.

    This allows the same feature engineering pipeline to serve both MLP
    (point-in-time) and LSTM/GRU (sequence) models.
    """

    def __init__(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        sequence_length: int,
    ):
        """Initialize sliding window dataset.

        Args:
            features: 2D tensor of shape (T, F) — full feature matrix
            labels: 1D tensor of shape (T,) — one label per timestamp
            sequence_length: Number of timesteps in each sequence window

        Raises:
            ValueError: If T < sequence_length (insufficient data for even one window)
        """
        if sequence_length < 1:
            raise ValueError(
                f"sequence_length must be >= 1, got {sequence_length}"
            )
        if features.ndim != 2:
            raise ValueError(
                f"features must be 2D (timestamps, features), got {features.ndim}D"
            )
        if labels.ndim != 1:
            raise ValueError(
                f"labels must be 1D (timestamps,), got {labels.ndim}D"
            )
        if len(features) != len(labels):
            raise ValueError(
                f"features and labels must have same length, "
                f"got {len(features)} and {len(labels)}"
            )
        if len(features) < sequence_length:
            raise ValueError(
                f"insufficient data: got {len(features)} timestamps but "
                f"sequence_length={sequence_length} requires at least that many"
            )
        self.features = features
        self.labels = labels
        self.sequence_length = sequence_length

    def __len__(self) -> int:
        return len(self.features) - self.sequence_length + 1

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        """Get a single sequence window and its label.

        Args:
            idx: Index into the valid range [0, len-1]

        Returns:
            Tuple of (sequence, label) where:
                sequence: (sequence_length, F) tensor
                label: scalar tensor (label of the last timestamp in the window)
        """
        end = idx + self.sequence_length
        return self.features[idx:end], self.labels[end - 1]
