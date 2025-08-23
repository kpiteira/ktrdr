"""Performance optimization utilities for KTRDR training."""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceConfig:
    """Configuration for performance optimizations."""

    # Mixed precision training
    enable_mixed_precision: bool = True  # Use fp16 for memory efficiency
    mixed_precision_loss_scale: Optional[float] = None  # Auto-scaling if None

    # Gradient optimization
    enable_gradient_checkpointing: bool = False  # Memory vs speed tradeoff
    max_gradient_norm: float = 1.0  # Gradient clipping

    # Batch optimization
    adaptive_batch_size: bool = True  # Automatically find optimal batch size
    min_batch_size: int = 16
    max_batch_size: int = 512
    batch_size_growth_factor: float = 1.5

    # Data loading optimization
    num_workers: int = 4  # DataLoader workers
    pin_memory: bool = True  # Pin memory for GPU transfer
    prefetch_factor: int = 2  # Prefetch batches
    persistent_workers: bool = True  # Keep workers alive

    # Compilation optimization
    compile_model: bool = False  # Use torch.compile (PyTorch 2.0+)
    compile_mode: str = "default"  # "default", "reduce-overhead", "max-autotune"

    # Device optimization
    enable_gpu_optimization: bool = True
    use_multiple_gpus: bool = False  # DataParallel/DistributedDataParallel

    def __post_init__(self):
        """Validate and adjust configuration based on available hardware."""
        # Adjust for GPU availability (CUDA or MPS)
        cuda_available = torch.cuda.is_available()
        mps_available = (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )

        if not (cuda_available or mps_available):
            self.enable_mixed_precision = False
            self.enable_gpu_optimization = False
            self.use_multiple_gpus = False
            self.pin_memory = False
            logger.info("GPU not available - disabled GPU optimizations")
        elif mps_available and not cuda_available:
            # MPS specific adjustments
            self.enable_mixed_precision = (
                False  # MPS doesn't support mixed precision well
            )
            self.use_multiple_gpus = False  # MPS is single device
            logger.info("Using MPS GPU - adjusted optimizations for Apple Silicon")

        # Adjust workers based on CPU count
        import os

        cpu_count = os.cpu_count() or 4
        if self.num_workers > cpu_count:
            self.num_workers = min(cpu_count, 8)  # Cap at 8 workers
            logger.info(
                f"Adjusted num_workers to {self.num_workers} based on CPU count"
            )


@dataclass
class PerformanceMetrics:
    """Performance metrics tracking."""

    training_time_per_epoch: list[float] = field(default_factory=list)
    validation_time_per_epoch: list[float] = field(default_factory=list)
    data_loading_time_per_epoch: list[float] = field(default_factory=list)
    forward_pass_time: list[float] = field(default_factory=list)
    backward_pass_time: list[float] = field(default_factory=list)
    optimizer_step_time: list[float] = field(default_factory=list)

    batch_sizes_used: list[int] = field(default_factory=list)
    samples_per_second: list[float] = field(default_factory=list)

    memory_usage_peak_mb: list[float] = field(default_factory=list)
    gpu_utilization_percent: list[float] = field(default_factory=list)

    def add_epoch_metrics(
        self,
        train_time: float,
        val_time: float,
        data_time: float,
        batch_size: int,
        num_samples: int,
        memory_peak: float = 0.0,
        gpu_util: float = 0.0,
    ):
        """Add metrics for completed epoch."""
        self.training_time_per_epoch.append(train_time)
        self.validation_time_per_epoch.append(val_time)
        self.data_loading_time_per_epoch.append(data_time)
        self.batch_sizes_used.append(batch_size)

        # Calculate samples per second
        total_time = train_time + val_time + data_time
        if total_time > 0:
            sps = num_samples / total_time
            self.samples_per_second.append(sps)

        self.memory_usage_peak_mb.append(memory_peak)
        self.gpu_utilization_percent.append(gpu_util)

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary statistics."""
        if not self.training_time_per_epoch:
            return {}

        return {
            "training_time": {
                "mean_seconds": np.mean(self.training_time_per_epoch),
                "std_seconds": np.std(self.training_time_per_epoch),
                "total_seconds": np.sum(self.training_time_per_epoch),
            },
            "validation_time": {
                "mean_seconds": np.mean(self.validation_time_per_epoch),
                "std_seconds": np.std(self.validation_time_per_epoch),
                "total_seconds": np.sum(self.validation_time_per_epoch),
            },
            "data_loading_time": {
                "mean_seconds": np.mean(self.data_loading_time_per_epoch),
                "std_seconds": np.std(self.data_loading_time_per_epoch),
                "total_seconds": np.sum(self.data_loading_time_per_epoch),
            },
            "throughput": {
                "mean_samples_per_second": (
                    np.mean(self.samples_per_second) if self.samples_per_second else 0
                ),
                "max_samples_per_second": (
                    np.max(self.samples_per_second) if self.samples_per_second else 0
                ),
            },
            "batch_size": {
                "mean": np.mean(self.batch_sizes_used),
                "min": np.min(self.batch_sizes_used),
                "max": np.max(self.batch_sizes_used),
            },
            "memory_usage": {
                "peak_mb": (
                    np.max(self.memory_usage_peak_mb)
                    if self.memory_usage_peak_mb
                    else 0
                ),
                "mean_mb": (
                    np.mean(self.memory_usage_peak_mb)
                    if self.memory_usage_peak_mb
                    else 0
                ),
            },
            "gpu_utilization": {
                "mean_percent": (
                    np.mean(self.gpu_utilization_percent)
                    if self.gpu_utilization_percent
                    else 0
                ),
                "max_percent": (
                    np.max(self.gpu_utilization_percent)
                    if self.gpu_utilization_percent
                    else 0
                ),
            },
        }


class PerformanceOptimizer:
    """Performance optimizer for neural network training."""

    def __init__(self, config: Optional[PerformanceConfig] = None):
        """Initialize performance optimizer.

        Args:
            config: Performance optimization configuration
        """
        self.config = config or PerformanceConfig()
        self.metrics = PerformanceMetrics()

        # Mixed precision scaler
        self.scaler = None
        if self.config.enable_mixed_precision and torch.cuda.is_available():
            try:
                from torch.cuda.amp import GradScaler

                self.scaler = GradScaler()
                logger.info("Mixed precision training enabled")
            except ImportError:
                logger.warning("Mixed precision not available - using float32")
                self.config.enable_mixed_precision = False

        # Model compilation
        self.compile_available = hasattr(torch, "compile")
        if self.config.compile_model and not self.compile_available:
            logger.warning("torch.compile not available - requires PyTorch 2.0+")
            self.config.compile_model = False

        logger.info(f"PerformanceOptimizer initialized: {self.config}")

    def optimize_model(self, model: nn.Module) -> nn.Module:
        """Apply model-level optimizations.

        Args:
            model: PyTorch model to optimize

        Returns:
            Optimized model
        """
        optimized_model = model

        # Enable gradient checkpointing for memory efficiency
        if self.config.enable_gradient_checkpointing:
            if hasattr(model, "gradient_checkpointing_enable"):
                model.gradient_checkpointing_enable()
                logger.info("Gradient checkpointing enabled")
            else:
                logger.warning("Model does not support gradient checkpointing")

        # Compile model for faster execution (PyTorch 2.0+)
        if self.config.compile_model and self.compile_available:
            try:
                optimized_model = torch.compile(
                    model,
                    mode=self.config.compile_mode,
                    fullgraph=False,  # Allow graph breaks for compatibility
                    dynamic=True,  # Support dynamic shapes
                )
                logger.info(f"Model compiled with mode: {self.config.compile_mode}")
            except Exception as e:
                logger.warning(f"Model compilation failed: {e}")
                optimized_model = model

        # Multi-GPU optimization
        if self.config.use_multiple_gpus and torch.cuda.device_count() > 1:
            if torch.cuda.device_count() > 1:
                optimized_model = nn.DataParallel(optimized_model)
                logger.info(
                    f"DataParallel enabled for {torch.cuda.device_count()} GPUs"
                )

        return optimized_model

    def optimize_optimizer(
        self, optimizer: torch.optim.Optimizer
    ) -> torch.optim.Optimizer:
        """Apply optimizer-level optimizations.

        Args:
            optimizer: PyTorch optimizer to optimize

        Returns:
            Optimized optimizer (may be the same object)
        """
        # For now, just return the optimizer as-is
        # Future: Could implement optimizer fusion, learning rate scheduling, etc.
        return optimizer

    def find_optimal_batch_size(
        self,
        model: nn.Module,
        sample_input: torch.Tensor,
        sample_target: torch.Tensor,
        criterion: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> int:
        """Find optimal batch size through binary search.

        Args:
            model: PyTorch model
            sample_input: Sample input tensor
            sample_target: Sample target tensor
            criterion: Loss function
            optimizer: Optimizer

        Returns:
            Optimal batch size
        """
        if not self.config.adaptive_batch_size:
            return self.config.min_batch_size

        logger.info("Finding optimal batch size...")

        device = next(model.parameters()).device
        model.train()

        # Start with minimum batch size and increase until OOM
        current_batch_size = self.config.min_batch_size
        max_successful_batch_size = self.config.min_batch_size

        while current_batch_size <= self.config.max_batch_size:
            try:
                # Create batch of current size
                batch_size = min(current_batch_size, sample_input.size(0))
                if batch_size < current_batch_size:
                    # Not enough samples for this batch size
                    break

                # Test with current batch size
                batch_input = sample_input[:batch_size].to(device)
                batch_target = sample_target[:batch_size].to(device)

                # Clear cache before test
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()

                # Forward pass
                optimizer.zero_grad()

                if self.config.enable_mixed_precision and self.scaler:
                    with torch.cuda.amp.autocast():
                        outputs = model(batch_input)
                        loss = criterion(outputs, batch_target)
                    self.scaler.scale(loss).backward()
                    self.scaler.step(optimizer)
                    self.scaler.update()
                else:
                    outputs = model(batch_input)
                    loss = criterion(outputs, batch_target)
                    loss.backward()
                    optimizer.step()

                # If we get here, batch size worked
                max_successful_batch_size = current_batch_size
                logger.debug(f"Batch size {current_batch_size} successful")

                # Increase batch size
                current_batch_size = int(
                    current_batch_size * self.config.batch_size_growth_factor
                )

            except RuntimeError as e:
                if (
                    "out of memory" in str(e).lower()
                    or "cuda out of memory" in str(e).lower()
                ):
                    logger.info(
                        f"OOM at batch size {current_batch_size}, using {max_successful_batch_size}"
                    )
                    break
                else:
                    # Other error, re-raise
                    raise e
            except Exception as e:
                logger.warning(f"Error testing batch size {current_batch_size}: {e}")
                break

        # Clean up
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        # Use 80% of max successful batch size for safety margin
        optimal_batch_size = max(
            self.config.min_batch_size, int(max_successful_batch_size * 0.8)
        )

        logger.info(f"Optimal batch size: {optimal_batch_size}")
        return optimal_batch_size

    def create_optimized_dataloader(
        self, dataset: torch.utils.data.Dataset, batch_size: int, shuffle: bool = True
    ) -> torch.utils.data.DataLoader:
        """Create optimized DataLoader.

        Args:
            dataset: PyTorch dataset
            batch_size: Batch size
            shuffle: Whether to shuffle data

        Returns:
            Optimized DataLoader
        """
        return torch.utils.data.DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=self.config.num_workers,
            pin_memory=self.config.pin_memory and torch.cuda.is_available(),
            prefetch_factor=(
                self.config.prefetch_factor if self.config.num_workers > 0 else 2
            ),
            persistent_workers=self.config.persistent_workers
            and self.config.num_workers > 0,
            drop_last=True,  # Consistent batch sizes
        )

    def training_step(
        self,
        model: nn.Module,
        batch_input: torch.Tensor,
        batch_target: torch.Tensor,
        criterion: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> tuple[torch.Tensor, dict[str, float]]:
        """Optimized training step.

        Args:
            model: PyTorch model
            batch_input: Input batch
            batch_target: Target batch
            criterion: Loss function
            optimizer: Optimizer

        Returns:
            Loss tensor and timing metrics
        """
        timings = {}

        # Forward pass timing
        forward_start = time.time()
        optimizer.zero_grad()

        if self.config.enable_mixed_precision and self.scaler:
            with torch.cuda.amp.autocast():
                outputs = model(batch_input)
                loss = criterion(outputs, batch_target)
        else:
            outputs = model(batch_input)
            loss = criterion(outputs, batch_target)

        timings["forward_time"] = time.time() - forward_start

        # Backward pass timing
        backward_start = time.time()

        if self.config.enable_mixed_precision and self.scaler:
            self.scaler.scale(loss).backward()
        else:
            loss.backward()

        # Gradient clipping
        if self.config.max_gradient_norm > 0:
            if self.config.enable_mixed_precision and self.scaler:
                self.scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), self.config.max_gradient_norm
                )
            else:
                torch.nn.utils.clip_grad_norm_(
                    model.parameters(), self.config.max_gradient_norm
                )

        timings["backward_time"] = time.time() - backward_start

        # Optimizer step timing
        optimizer_start = time.time()

        if self.config.enable_mixed_precision and self.scaler:
            self.scaler.step(optimizer)
            self.scaler.update()
        else:
            optimizer.step()

        timings["optimizer_time"] = time.time() - optimizer_start

        return loss, timings

    def get_performance_summary(self) -> dict[str, Any]:
        """Get comprehensive performance summary."""
        summary = self.metrics.get_summary()

        # Add configuration info
        summary["configuration"] = {
            "mixed_precision_enabled": self.config.enable_mixed_precision,
            "gradient_checkpointing_enabled": self.config.enable_gradient_checkpointing,
            "model_compilation_enabled": self.config.compile_model,
            "adaptive_batch_size_enabled": self.config.adaptive_batch_size,
            "num_workers": self.config.num_workers,
            "pin_memory": self.config.pin_memory,
        }

        # Add hardware info
        summary["hardware"] = {
            "cuda_available": torch.cuda.is_available(),
            "gpu_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "gpu_name": (
                torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
            ),
        }

        return summary

    def get_optimization_recommendations(self) -> list[str]:
        """Get performance optimization recommendations."""
        recommendations = []

        summary = self.metrics.get_summary()

        # Memory recommendations
        if summary.get("memory_usage", {}).get("peak_mb", 0) > 8000:  # > 8GB
            recommendations.append(
                "Consider enabling gradient checkpointing to reduce memory usage"
            )
            recommendations.append("Try reducing batch size or model size")

        # Speed recommendations
        throughput = summary.get("throughput", {}).get("mean_samples_per_second", 0)
        if throughput < 100:  # < 100 samples/sec
            recommendations.append(
                "Consider enabling mixed precision training for speed"
            )
            recommendations.append("Increase batch size if memory allows")
            recommendations.append("Enable model compilation (PyTorch 2.0+)")

        # GPU utilization recommendations
        gpu_util = summary.get("gpu_utilization", {}).get("mean_percent", 0)
        if gpu_util < 70 and torch.cuda.is_available():
            recommendations.append(
                "GPU utilization is low - consider increasing batch size or model complexity"
            )
            recommendations.append("Check if data loading is the bottleneck")

        # Data loading recommendations
        data_time = summary.get("data_loading_time", {}).get("mean_seconds", 0)
        total_time = summary.get("training_time", {}).get(
            "mean_seconds", 0
        ) + summary.get("validation_time", {}).get("mean_seconds", 0)

        if (
            total_time > 0 and data_time / total_time > 0.2
        ):  # > 20% of time in data loading
            recommendations.append(
                "Data loading is slow - consider increasing num_workers"
            )
            recommendations.append("Enable pin_memory for GPU training")

        return recommendations
