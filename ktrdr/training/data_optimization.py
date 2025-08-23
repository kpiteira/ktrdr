"""Data loading and batch processing optimizations for KTRDR training."""

import queue
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset, Sampler

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class DataConfig:
    """Configuration for data loading optimizations."""

    # Memory mapping for large datasets
    enable_memory_mapping: bool = True
    mmap_cache_size_mb: int = 1024  # 1GB cache

    # Batch processing
    enable_batch_prefetching: bool = True
    prefetch_queue_size: int = 4

    # Data preprocessing
    enable_preprocessing_cache: bool = True
    cache_dir: Optional[str] = None

    # Sampling strategies
    balanced_sampling: bool = False  # Balance classes in batches
    symbol_balanced_sampling: bool = True  # Balance symbols in batches
    timeframe_stratified_sampling: bool = True  # Ensure timeframe representation

    # Memory optimization
    use_shared_memory: bool = False  # Share memory between workers
    pin_memory_device: str = "auto"  # Device for pinned memory (auto-detect)

    # Data augmentation
    enable_feature_noise: bool = False  # Add noise to features
    noise_std: float = 0.01
    enable_temporal_jitter: bool = False  # Slight temporal shifts
    jitter_range: int = 2


class EfficientMultiSymbolDataset(Dataset):
    """Memory-efficient dataset for multi-symbol, multi-timeframe data."""

    def __init__(
        self,
        feature_tensor: torch.Tensor,
        label_tensor: torch.Tensor,
        symbol_indices: torch.Tensor,
        feature_names: list[str],
        symbols: list[str],
        timeframes: list[str],
        config: Optional[DataConfig] = None,
    ):
        """Initialize efficient multi-symbol dataset.

        Args:
            feature_tensor: Features tensor [samples, features]
            label_tensor: Labels tensor [samples]
            symbol_indices: Symbol indices tensor [samples]
            feature_names: List of feature names
            symbols: List of symbol names
            timeframes: List of timeframe names
            config: Data configuration
        """
        self.config = config or DataConfig()

        # Store data
        self.feature_tensor = feature_tensor
        self.label_tensor = label_tensor
        self.symbol_indices = symbol_indices
        self.feature_names = feature_names
        self.symbols = symbols
        self.timeframes = timeframes

        # Data statistics
        self.num_samples = len(feature_tensor)
        self.num_features = feature_tensor.shape[1]
        self.num_symbols = len(symbols)
        self.num_classes = len(torch.unique(label_tensor))

        # Build indices for efficient sampling
        self._build_sampling_indices()

        # Setup memory mapping if enabled
        if self.config.enable_memory_mapping:
            self._setup_memory_mapping()

        logger.info(
            f"EfficientMultiSymbolDataset initialized: "
            f"{self.num_samples} samples, {self.num_features} features, "
            f"{self.num_symbols} symbols, {len(timeframes)} timeframes"
        )

    def _build_sampling_indices(self):
        """Build indices for efficient sampling strategies."""
        # Symbol indices mapping
        self.symbol_to_indices = {}
        for i, symbol in enumerate(self.symbols):
            mask = self.symbol_indices == i
            self.symbol_to_indices[symbol] = torch.where(mask)[0]

        # Class indices mapping
        self.class_to_indices = {}
        for class_idx in range(self.num_classes):
            mask = self.label_tensor == class_idx
            self.class_to_indices[class_idx] = torch.where(mask)[0]

        # Symbol-class combinations
        self.symbol_class_to_indices = {}
        for i, symbol in enumerate(self.symbols):
            for class_idx in range(self.num_classes):
                mask = (self.symbol_indices == i) & (self.label_tensor == class_idx)
                indices = torch.where(mask)[0]
                if len(indices) > 0:
                    self.symbol_class_to_indices[(symbol, class_idx)] = indices

    def _setup_memory_mapping(self):
        """Setup memory mapping for large datasets."""
        # For now, just log that memory mapping would be setup
        # In production, this would create memory-mapped files
        logger.debug("Memory mapping setup (placeholder)")

    def __len__(self) -> int:
        """Get dataset length."""
        return self.num_samples

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get item by index.

        Args:
            idx: Sample index

        Returns:
            Tuple of (features, label, symbol_index)
        """
        features = self.feature_tensor[idx]
        label = self.label_tensor[idx]
        symbol_idx = self.symbol_indices[idx]

        # Apply data augmentation if enabled
        if self.config.enable_feature_noise:
            noise = torch.randn_like(features) * self.config.noise_std
            features = features + noise

        return features, label, symbol_idx

    def get_symbol_batch(
        self, symbol: str, batch_size: int
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get a batch from a specific symbol.

        Args:
            symbol: Symbol name
            batch_size: Batch size

        Returns:
            Tuple of (features, labels, symbol_indices)
        """
        if symbol not in self.symbol_to_indices:
            raise ValueError(f"Symbol {symbol} not found in dataset")

        symbol_indices = self.symbol_to_indices[symbol]

        # Sample randomly from this symbol
        if len(symbol_indices) < batch_size:
            # Repeat indices if not enough samples
            selected_indices = symbol_indices.repeat(
                (batch_size // len(symbol_indices)) + 1
            )[:batch_size]
        else:
            selected_indices = symbol_indices[
                torch.randperm(len(symbol_indices))[:batch_size]
            ]

        features = self.feature_tensor[selected_indices]
        labels = self.label_tensor[selected_indices]
        symbol_idxs = self.symbol_indices[selected_indices]

        return features, labels, symbol_idxs

    def get_balanced_batch(
        self, batch_size: int
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Get a class-balanced batch.

        Args:
            batch_size: Batch size

        Returns:
            Tuple of (features, labels, symbol_indices)
        """
        samples_per_class = batch_size // self.num_classes
        remaining_samples = batch_size % self.num_classes

        selected_indices = []

        for class_idx in range(self.num_classes):
            class_indices = self.class_to_indices.get(class_idx, torch.tensor([]))
            if len(class_indices) == 0:
                continue

            # Number of samples for this class
            num_samples = samples_per_class
            if class_idx < remaining_samples:
                num_samples += 1

            if len(class_indices) < num_samples:
                # Repeat indices if not enough samples
                class_selected = class_indices.repeat(
                    (num_samples // len(class_indices)) + 1
                )[:num_samples]
            else:
                class_selected = class_indices[
                    torch.randperm(len(class_indices))[:num_samples]
                ]

            selected_indices.append(class_selected)

        # Combine and shuffle
        all_indices = torch.cat(selected_indices)
        shuffle_order = torch.randperm(len(all_indices))
        final_indices = all_indices[shuffle_order]

        features = self.feature_tensor[final_indices]
        labels = self.label_tensor[final_indices]
        symbol_idxs = self.symbol_indices[final_indices]

        return features, labels, symbol_idxs


class SymbolBalancedSampler(Sampler):
    """Sampler that ensures balanced representation of symbols in each batch."""

    def __init__(
        self,
        dataset: EfficientMultiSymbolDataset,
        batch_size: int,
        drop_last: bool = True,
    ):
        """Initialize symbol-balanced sampler.

        Args:
            dataset: Multi-symbol dataset
            batch_size: Batch size
            drop_last: Whether to drop last incomplete batch
        """
        self.dataset = dataset
        self.batch_size = batch_size
        self.drop_last = drop_last

        # Calculate samples per symbol per batch
        self.samples_per_symbol = batch_size // dataset.num_symbols
        self.extra_samples = batch_size % dataset.num_symbols

        # Calculate number of batches
        min_symbol_samples = min(
            len(indices) for indices in dataset.symbol_to_indices.values()
        )
        self.num_batches = min_symbol_samples // self.samples_per_symbol

        if not self.drop_last and min_symbol_samples % self.samples_per_symbol > 0:
            self.num_batches += 1

        logger.debug(
            f"SymbolBalancedSampler: {self.num_batches} batches, "
            f"{self.samples_per_symbol} samples/symbol, {self.extra_samples} extra"
        )

    def __iter__(self) -> Iterator[int]:
        """Generate indices for balanced sampling."""
        # Create shuffled indices for each symbol
        symbol_iterators = {}
        for symbol, indices in self.dataset.symbol_to_indices.items():
            shuffled_indices = indices[torch.randperm(len(indices))]
            symbol_iterators[symbol] = iter(shuffled_indices.tolist())

        # Generate batches
        for batch_idx in range(self.num_batches):
            batch_indices = []

            # Sample from each symbol
            for i, symbol in enumerate(self.dataset.symbols):
                num_samples = self.samples_per_symbol
                if i < self.extra_samples:
                    num_samples += 1

                symbol_iter = symbol_iterators[symbol]
                for _ in range(num_samples):
                    try:
                        idx = next(symbol_iter)
                        batch_indices.append(idx)
                    except StopIteration:
                        # Restart iterator if we run out
                        shuffled_indices = self.dataset.symbol_to_indices[symbol][
                            torch.randperm(len(self.dataset.symbol_to_indices[symbol]))
                        ]
                        symbol_iter = iter(shuffled_indices.tolist())
                        symbol_iterators[symbol] = symbol_iter
                        idx = next(symbol_iter)
                        batch_indices.append(idx)

            # Shuffle batch indices
            np.random.shuffle(batch_indices)
            yield from batch_indices

    def __len__(self) -> int:
        """Get number of samples per epoch."""
        return self.num_batches * self.batch_size


class PrefetchingDataLoader:
    """DataLoader with advanced prefetching capabilities."""

    def __init__(
        self,
        dataset: Dataset,
        batch_size: int,
        sampler: Optional[Sampler] = None,
        config: Optional[DataConfig] = None,
        device: Optional[torch.device] = None,
    ):
        """Initialize prefetching DataLoader.

        Args:
            dataset: PyTorch dataset
            batch_size: Batch size
            sampler: Custom sampler
            config: Data configuration
            device: Target device for prefetching
        """
        self.dataset = dataset
        self.batch_size = batch_size
        self.sampler = sampler
        self.config = config or DataConfig()
        self.device = device

        # Create standard DataLoader
        self.dataloader = DataLoader(
            dataset,
            batch_size=batch_size,
            sampler=sampler,
            shuffle=(sampler is None),
            num_workers=4,
            pin_memory=True,
            drop_last=True,
        )

        # Prefetching setup
        self.prefetch_queue = queue.Queue(maxsize=self.config.prefetch_queue_size)
        self.prefetch_thread = None
        self.stop_prefetching = threading.Event()

    def _prefetch_worker(self):
        """Worker thread for prefetching batches."""
        try:
            for batch in self.dataloader:
                if self.stop_prefetching.is_set():
                    break

                # Move to device if specified
                if self.device is not None:
                    if isinstance(batch, (list, tuple)):
                        batch = tuple(
                            (
                                item.to(self.device, non_blocking=True)
                                if torch.is_tensor(item)
                                else item
                            )
                            for item in batch
                        )
                    elif torch.is_tensor(batch):
                        batch = batch.to(self.device, non_blocking=True)

                # Add to queue (this will block if queue is full)
                self.prefetch_queue.put(batch)

            # Signal end of data
            self.prefetch_queue.put(None)

        except Exception as e:
            logger.error(f"Prefetching error: {e}")
            self.prefetch_queue.put(None)

    def __iter__(self):
        """Start prefetching and iterate over batches."""
        if not self.config.enable_batch_prefetching:
            # Standard iteration without prefetching
            for batch in self.dataloader:
                if self.device is not None and torch.is_tensor(batch):
                    batch = batch.to(self.device)
                yield batch
            return

        # Start prefetching
        self.stop_prefetching.clear()
        self.prefetch_thread = threading.Thread(
            target=self._prefetch_worker, daemon=True
        )
        self.prefetch_thread.start()

        try:
            while True:
                batch = self.prefetch_queue.get()
                if batch is None:  # End of data signal
                    break
                yield batch
        finally:
            # Clean up
            self.stop_prefetching.set()
            if self.prefetch_thread:
                self.prefetch_thread.join(timeout=1.0)

    def __len__(self):
        """Get number of batches."""
        return len(self.dataloader)


class DataLoadingOptimizer:
    """Optimizer for data loading and batch processing."""

    def __init__(self, config: Optional[DataConfig] = None):
        """Initialize data loading optimizer.

        Args:
            config: Data configuration
        """
        self.config = config or DataConfig()
        logger.info(f"DataLoadingOptimizer initialized: {self.config}")

    def create_optimized_dataset(
        self,
        feature_tensor: torch.Tensor,
        label_tensor: torch.Tensor,
        symbol_indices: torch.Tensor,
        feature_names: list[str],
        symbols: list[str],
        timeframes: list[str],
    ) -> EfficientMultiSymbolDataset:
        """Create optimized dataset.

        Args:
            feature_tensor: Features tensor
            label_tensor: Labels tensor
            symbol_indices: Symbol indices tensor
            feature_names: Feature names
            symbols: Symbol names
            timeframes: Timeframe names

        Returns:
            Optimized dataset
        """
        return EfficientMultiSymbolDataset(
            feature_tensor=feature_tensor,
            label_tensor=label_tensor,
            symbol_indices=symbol_indices,
            feature_names=feature_names,
            symbols=symbols,
            timeframes=timeframes,
            config=self.config,
        )

    def create_optimized_dataloader(
        self,
        dataset: EfficientMultiSymbolDataset,
        batch_size: int,
        device: Optional[torch.device] = None,
        shuffle: bool = True,
    ) -> Union[DataLoader, PrefetchingDataLoader]:
        """Create optimized DataLoader.

        Args:
            dataset: Optimized dataset
            batch_size: Batch size
            device: Target device
            shuffle: Whether to shuffle (ignored if using custom sampler)

        Returns:
            Optimized DataLoader
        """
        # Create custom sampler if needed
        sampler = None
        if self.config.symbol_balanced_sampling:
            sampler = SymbolBalancedSampler(dataset, batch_size, drop_last=True)
            shuffle = False  # Sampler handles shuffling

        # Use prefetching DataLoader if enabled
        if self.config.enable_batch_prefetching:
            return PrefetchingDataLoader(
                dataset=dataset,
                batch_size=batch_size,
                sampler=sampler,
                config=self.config,
                device=device,
            )
        else:
            return DataLoader(
                dataset,
                batch_size=batch_size,
                sampler=sampler,
                shuffle=shuffle,
                num_workers=4,
                pin_memory=True,
                drop_last=True,
            )

    def benchmark_dataloader(
        self,
        dataloader: Union[DataLoader, PrefetchingDataLoader],
        num_batches: int = 100,
    ) -> dict[str, float]:
        """Benchmark dataloader performance.

        Args:
            dataloader: DataLoader to benchmark
            num_batches: Number of batches to test

        Returns:
            Performance metrics
        """
        logger.info(f"Benchmarking dataloader for {num_batches} batches...")

        times = []
        start_time = time.time()

        for i, batch in enumerate(dataloader):
            if i >= num_batches:
                break

            batch_start = time.time()

            # Simulate some processing
            if isinstance(batch, (list, tuple)):
                for item in batch:
                    if torch.is_tensor(item) and item.dtype.is_floating_point:
                        _ = item.mean()  # Simple operation
                    elif torch.is_tensor(item):
                        _ = item.sum()  # Use sum for integer tensors
            elif torch.is_tensor(batch):
                if batch.dtype.is_floating_point:
                    _ = batch.mean()
                else:
                    _ = batch.sum()

            batch_time = time.time() - batch_start
            times.append(batch_time)

        total_time = time.time() - start_time

        metrics = {
            "total_time_seconds": total_time,
            "mean_batch_time_seconds": np.mean(times),
            "std_batch_time_seconds": np.std(times),
            "min_batch_time_seconds": np.min(times),
            "max_batch_time_seconds": np.max(times),
            "batches_per_second": len(times) / total_time,
            "samples_per_second": len(times) * dataloader.batch_size / total_time,
        }

        logger.info(
            f"Dataloader benchmark results: "
            f"{metrics['batches_per_second']:.1f} batches/sec, "
            f"{metrics['samples_per_second']:.1f} samples/sec"
        )

        return metrics

    def get_data_statistics(
        self, dataset: EfficientMultiSymbolDataset
    ) -> dict[str, Any]:
        """Get comprehensive dataset statistics.

        Args:
            dataset: Dataset to analyze

        Returns:
            Dataset statistics
        """
        stats = {
            "dataset_info": {
                "num_samples": dataset.num_samples,
                "num_features": dataset.num_features,
                "num_symbols": dataset.num_symbols,
                "num_classes": dataset.num_classes,
                "symbols": dataset.symbols,
                "timeframes": dataset.timeframes,
            },
            "class_distribution": {},
            "symbol_distribution": {},
            "symbol_class_distribution": {},
            "feature_statistics": {},
        }

        # Class distribution
        for class_idx in range(dataset.num_classes):
            count = (dataset.label_tensor == class_idx).sum().item()
            stats["class_distribution"][f"class_{class_idx}"] = count

        # Symbol distribution
        for i, symbol in enumerate(dataset.symbols):
            count = (dataset.symbol_indices == i).sum().item()
            stats["symbol_distribution"][symbol] = count

        # Symbol-class distribution
        for i, symbol in enumerate(dataset.symbols):
            stats["symbol_class_distribution"][symbol] = {}
            for class_idx in range(dataset.num_classes):
                count = (
                    (
                        (dataset.symbol_indices == i)
                        & (dataset.label_tensor == class_idx)
                    )
                    .sum()
                    .item()
                )
                stats["symbol_class_distribution"][symbol][f"class_{class_idx}"] = count

        # Feature statistics
        features = dataset.feature_tensor
        stats["feature_statistics"] = {
            "mean": features.mean(dim=0).tolist(),
            "std": features.std(dim=0).tolist(),
            "min": features.min(dim=0)[0].tolist(),
            "max": features.max(dim=0)[0].tolist(),
        }

        return stats
