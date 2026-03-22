"""Tests for SequenceDataset sliding window."""

import pytest
import torch
from torch.utils.data import DataLoader

from ktrdr.training.sequence_dataset import SequenceDataset


class TestSequenceDataset:
    """Test sliding window dataset for temporal models."""

    def test_length_correct(self):
        """Dataset length = T - seq_len + 1."""
        features = torch.randn(100, 6)
        labels = torch.randint(0, 3, (100,))
        ds = SequenceDataset(features, labels, sequence_length=20)
        assert len(ds) == 81  # 100 - 20 + 1

    def test_item_shapes(self):
        """Each item returns (seq_len, features) and scalar label."""
        features = torch.randn(50, 4)
        labels = torch.randint(0, 3, (50,))
        ds = SequenceDataset(features, labels, sequence_length=10)
        x, y = ds[0]
        assert x.shape == (10, 4)
        assert y.shape == ()  # scalar

    def test_label_alignment(self):
        """Label for each sequence matches the last timestamp in the window."""
        features = torch.randn(30, 2)
        labels = torch.arange(30)  # labels 0..29
        ds = SequenceDataset(features, labels, sequence_length=5)
        # Item 0: features[0:5], label = labels[4] = 4
        _, y0 = ds[0]
        assert y0.item() == 4
        # Item 10: features[10:15], label = labels[14] = 14
        _, y10 = ds[10]
        assert y10.item() == 14
        # Last item: features[25:30], label = labels[29] = 29
        _, ylast = ds[len(ds) - 1]
        assert ylast.item() == 29

    def test_feature_window_values(self):
        """Feature window contains the correct slice of data."""
        features = torch.arange(20).float().reshape(10, 2)  # [[0,1],[2,3],...,[18,19]]
        labels = torch.zeros(10)
        ds = SequenceDataset(features, labels, sequence_length=3)
        x, _ = ds[2]  # features[2:5]
        expected = torch.tensor([[4, 5], [6, 7], [8, 9]], dtype=torch.float)
        assert torch.equal(x, expected)

    def test_dataloader_batching(self):
        """Works correctly with DataLoader for batching."""
        features = torch.randn(100, 6)
        labels = torch.randint(0, 3, (100,))
        ds = SequenceDataset(features, labels, sequence_length=20)
        loader = DataLoader(ds, batch_size=16, shuffle=False)
        batch_x, batch_y = next(iter(loader))
        assert batch_x.shape == (16, 20, 6)
        assert batch_y.shape == (16,)

    def test_insufficient_data_raises(self):
        """Raises ValueError when T < sequence_length."""
        features = torch.randn(5, 4)
        labels = torch.randint(0, 3, (5,))
        with pytest.raises(ValueError, match="insufficient"):
            SequenceDataset(features, labels, sequence_length=10)

    def test_exact_length_works(self):
        """T == sequence_length produces dataset of length 1."""
        features = torch.randn(10, 4)
        labels = torch.randint(0, 3, (10,))
        ds = SequenceDataset(features, labels, sequence_length=10)
        assert len(ds) == 1
        x, y = ds[0]
        assert x.shape == (10, 4)

    def test_sequence_length_one(self):
        """sequence_length=1 behaves like point-in-time (no windowing)."""
        features = torch.randn(20, 4)
        labels = torch.randint(0, 3, (20,))
        ds = SequenceDataset(features, labels, sequence_length=1)
        assert len(ds) == 20
        x, y = ds[5]
        assert x.shape == (1, 4)
        assert torch.equal(x[0], features[5])
