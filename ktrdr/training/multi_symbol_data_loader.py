"""Multi-symbol data loader with balanced sampling for training."""

from typing import List, Tuple

import torch
from torch.utils.data import DataLoader, Dataset


class MultiSymbolDataset(Dataset):
    """Dataset that handles multi-symbol data with balanced sampling."""

    def __init__(
        self,
        features: torch.Tensor,
        labels: torch.Tensor,
        symbol_indices: torch.Tensor,
    ):
        """Initialize multi-symbol dataset.

        Args:
            features: Feature tensor [num_samples, num_features]
            labels: Label tensor [num_samples]
            symbol_indices: Symbol index tensor [num_samples]
        """
        self.features = features
        self.labels = labels
        self.symbol_indices = symbol_indices

        # Validate tensor shapes
        assert (
            len(features) == len(labels) == len(symbol_indices)
        ), f"Tensor length mismatch: features={len(features)}, labels={len(labels)}, symbol_indices={len(symbol_indices)}"

    def __len__(self) -> int:
        """Return dataset size."""
        return len(self.features)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get a single sample.

        Args:
            idx: Sample index

        Returns:
            Tuple of (features, label, symbol_index)
        """
        return self.features[idx], self.labels[idx], self.symbol_indices[idx]


class BalancedMultiSymbolBatchSampler:
    """Batch sampler that ensures equal representation of symbols in each batch."""

    def __init__(
        self,
        symbol_indices: torch.Tensor,
        batch_size: int,
        symbols: list[str],
        drop_last: bool = False,
    ):
        """Initialize balanced batch sampler.

        Args:
            symbol_indices: Tensor indicating which symbol each sample belongs to
            batch_size: Total batch size
            symbols: List of symbol names
            drop_last: Whether to drop incomplete batches
        """
        self.symbol_indices = symbol_indices
        self.batch_size = batch_size
        self.symbols = symbols
        self.num_symbols = len(symbols)
        self.drop_last = drop_last

        # Calculate samples per symbol per batch
        self.samples_per_symbol = max(1, batch_size // self.num_symbols)
        self.actual_batch_size = self.samples_per_symbol * self.num_symbols

        # Group indices by symbol
        self.symbol_to_indices = {}
        for symbol_idx, symbol in enumerate(symbols):
            symbol_mask = symbol_indices == symbol_idx
            self.symbol_to_indices[symbol_idx] = torch.nonzero(
                symbol_mask, as_tuple=False
            ).squeeze(1)

        # Calculate number of batches
        min_symbol_samples = min(
            len(indices) for indices in self.symbol_to_indices.values()
        )
        self.num_batches = min_symbol_samples // self.samples_per_symbol

    def __iter__(self):
        """Iterate over balanced batches."""
        # Shuffle indices for each symbol
        shuffled_indices = {}
        for symbol_idx in range(self.num_symbols):
            indices = self.symbol_to_indices[symbol_idx]
            shuffled_indices[symbol_idx] = indices[torch.randperm(len(indices))]

        # Generate batches
        for batch_idx in range(self.num_batches):
            batch_indices = []

            for symbol_idx in range(self.num_symbols):
                start_idx = batch_idx * self.samples_per_symbol
                end_idx = start_idx + self.samples_per_symbol
                symbol_batch_indices = shuffled_indices[symbol_idx][start_idx:end_idx]
                batch_indices.extend(symbol_batch_indices.tolist())

            # Shuffle the batch to mix symbols
            batch_indices = torch.tensor(batch_indices)
            batch_indices = batch_indices[torch.randperm(len(batch_indices))]

            yield batch_indices.tolist()

    def __len__(self) -> int:
        """Return number of batches."""
        return self.num_batches


class MultiSymbolDataLoader:
    """Data loader factory for multi-symbol datasets with balanced sampling."""

    @staticmethod
    def create_balanced_loader(
        features: torch.Tensor,
        labels: torch.Tensor,
        symbol_indices: torch.Tensor,
        symbols: list[str],
        batch_size: int = 32,
        shuffle: bool = True,
        drop_last: bool = False,
        **kwargs,
    ) -> DataLoader:
        """Create a balanced data loader for multi-symbol training.

        Args:
            features: Feature tensor
            labels: Label tensor
            symbol_indices: Symbol index tensor
            symbols: List of symbol names
            batch_size: Batch size
            shuffle: Whether to shuffle data (ignored - always True for balanced sampling)
            drop_last: Whether to drop incomplete batches
            **kwargs: Additional arguments for DataLoader

        Returns:
            DataLoader with balanced symbol sampling
        """
        dataset = MultiSymbolDataset(features, labels, symbol_indices)

        if len(symbols) <= 1:
            # Single symbol case - use regular DataLoader
            return DataLoader(
                dataset,
                batch_size=batch_size,
                shuffle=shuffle,
                drop_last=drop_last,
                **kwargs,
            )

        # Multi-symbol case - use balanced sampling
        batch_sampler = BalancedMultiSymbolBatchSampler(
            symbol_indices=symbol_indices,
            batch_size=batch_size,
            symbols=symbols,
            drop_last=drop_last,
        )

        return DataLoader(dataset, batch_sampler=batch_sampler, **kwargs)

    @staticmethod
    def create_regular_loader(
        features: torch.Tensor,
        labels: torch.Tensor,
        symbol_indices: torch.Tensor,
        batch_size: int = 32,
        shuffle: bool = True,
        drop_last: bool = False,
        **kwargs,
    ) -> DataLoader:
        """Create a regular data loader (no balanced sampling).

        Args:
            features: Feature tensor
            labels: Label tensor
            symbol_indices: Symbol index tensor
            batch_size: Batch size
            shuffle: Whether to shuffle data
            drop_last: Whether to drop incomplete batches
            **kwargs: Additional arguments for DataLoader

        Returns:
            Regular DataLoader
        """
        dataset = MultiSymbolDataset(features, labels, symbol_indices)

        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            drop_last=drop_last,
            **kwargs,
        )
