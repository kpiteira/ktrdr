"""GPU memory management for efficient multi-symbol, multi-timeframe training."""

import gc
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional, Union

import torch
import torch.nn as nn

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class GPUMemoryConfig:
    """Configuration for GPU memory management."""

    # Memory allocation strategy
    memory_fraction: float = 0.9  # Use 90% of GPU memory
    reserved_memory_mb: float = 512  # Reserve 512MB for system

    # Memory optimization
    enable_memory_pooling: bool = True  # Use memory pool
    enable_gradient_accumulation: bool = False  # Accumulate gradients
    gradient_accumulation_steps: int = 2

    # Mixed precision
    enable_mixed_precision: bool = True  # Use automatic mixed precision
    loss_scale: Union[float, str] = "dynamic"  # "dynamic" or fixed value

    # Memory cleanup
    aggressive_cleanup: bool = False  # More frequent cleanup
    cleanup_threshold_mb: float = 100  # Cleanup when free memory < threshold

    # Checkpointing
    enable_activation_checkpointing: bool = False  # Checkpoint activations
    checkpoint_segments: int = 4  # Number of checkpoint segments

    # Memory monitoring
    enable_memory_profiling: bool = False  # Profile memory usage
    profiling_interval_seconds: float = 1.0


@dataclass
class GPUMemorySnapshot:
    """Snapshot of GPU memory usage."""

    timestamp: float
    device_id: int
    allocated_mb: float
    reserved_mb: float
    total_mb: float
    free_mb: float
    utilization_percent: float
    temperature_celsius: Optional[float] = None
    power_usage_watts: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "allocated_mb": self.allocated_mb,
            "reserved_mb": self.reserved_mb,
            "total_mb": self.total_mb,
            "free_mb": self.free_mb,
            "utilization_percent": self.utilization_percent,
            "temperature_celsius": self.temperature_celsius,
            "power_usage_watts": self.power_usage_watts,
        }


class GPUMemoryManager:
    """Advanced GPU memory management for training."""

    def __init__(
        self,
        config: Optional[GPUMemoryConfig] = None,
        device_ids: Optional[list[int]] = None,
    ):
        """Initialize GPU memory manager.

        Args:
            config: GPU memory configuration
            device_ids: List of GPU device IDs to manage (None = all available)
        """
        self.config = config or GPUMemoryConfig()

        # Check GPU availability (CUDA or MPS)
        self.cuda_available = torch.cuda.is_available()
        self.mps_available = (
            hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
        )

        if not (self.cuda_available or self.mps_available):
            logger.warning(
                "Neither CUDA nor MPS available - GPU memory management disabled"
            )
            self.enabled = False
            return

        if self.cuda_available:
            self.device_type = "cuda"
            logger.info("Using CUDA for GPU acceleration")
        elif self.mps_available:
            self.device_type = "mps"
            logger.info("Using MPS (Apple Silicon) for GPU acceleration")

        self.enabled = True

        # Initialize device management
        if self.device_type == "cuda":
            if device_ids is None:
                self.device_ids = list(range(torch.cuda.device_count()))
            else:
                self.device_ids = device_ids
            self.num_devices = len(self.device_ids)
        elif self.device_type == "mps":
            # MPS represents one unified GPU device
            self.device_ids = [0]  # MPS uses device 0
            self.num_devices = 1

        logger.info(
            f"Managing {self.num_devices} {self.device_type.upper()} device(s): {self.device_ids}"
        )

        # Memory tracking
        self.snapshots: list[GPUMemorySnapshot] = []
        self.peak_memory_usage: dict[int, float] = {}

        # Monitoring
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False

        # Mixed precision setup
        self.scaler: Optional[torch.cuda.amp.GradScaler] = None
        if self.config.enable_mixed_precision:
            self._setup_mixed_precision()

        # Initialize memory pools
        if self.config.enable_memory_pooling:
            self._setup_memory_pools()

        logger.info(f"GPUMemoryManager initialized: {self.config}")

    def get_device(self, device_id: int = 0) -> torch.device:
        """Get the appropriate torch device."""
        if not self.enabled:
            return torch.device("cpu")

        if self.device_type == "cuda":
            return torch.device(f"cuda:{device_id}")
        elif self.device_type == "mps":
            return torch.device("mps")
        else:
            return torch.device("cpu")

    def _setup_mixed_precision(self):
        """Setup mixed precision training."""
        try:
            if self.device_type == "cuda":
                # Use CUDA-specific scaler
                if self.config.loss_scale == "dynamic":
                    self.scaler = torch.cuda.amp.GradScaler()
                else:
                    self.scaler = torch.cuda.amp.GradScaler(
                        init_scale=float(self.config.loss_scale)
                    )
                logger.info("CUDA mixed precision training enabled")
            elif self.device_type == "mps":
                # MPS doesn't support mixed precision well yet, disable it
                logger.info("MPS mixed precision not supported - disabling")
                self.config.enable_mixed_precision = False
                return
            else:
                logger.info("Mixed precision not available for CPU")
                self.config.enable_mixed_precision = False
                return
        except Exception as e:
            logger.warning(f"Failed to setup mixed precision: {e}")
            self.config.enable_mixed_precision = False

    def _setup_memory_pools(self):
        """Setup memory pools for efficient allocation."""
        try:
            if self.device_type == "cuda":
                # Set memory fraction for each CUDA device
                for device_id in self.device_ids:
                    torch.cuda.set_per_process_memory_fraction(
                        self.config.memory_fraction, device_id
                    )
                logger.info(
                    f"CUDA memory pools configured with {self.config.memory_fraction:.1%} allocation"
                )
            elif self.device_type == "mps":
                # MPS memory management is handled by the system
                logger.info("MPS memory management handled by system")
            else:
                logger.info("Memory pools not applicable for CPU")
        except Exception as e:
            logger.warning(f"Failed to setup memory pools: {e}")

    def start_monitoring(self):
        """Start GPU memory monitoring."""
        if not self.enabled or not self.config.enable_memory_profiling:
            return

        if self.monitoring_active:
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.monitoring_thread.start()
        logger.info("GPU memory monitoring started")

    def stop_monitoring(self):
        """Stop GPU memory monitoring."""
        if not self.enabled:
            return

        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
        logger.info("GPU memory monitoring stopped")

    def _monitoring_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                for device_id in self.device_ids:
                    snapshot = self.capture_snapshot(device_id)
                    self.snapshots.append(snapshot)

                    # Update peak usage
                    current_usage = snapshot.allocated_mb
                    if (
                        device_id not in self.peak_memory_usage
                        or current_usage > self.peak_memory_usage[device_id]
                    ):
                        self.peak_memory_usage[device_id] = current_usage

                    # Check for cleanup
                    if snapshot.free_mb < self.config.cleanup_threshold_mb:
                        logger.debug(
                            f"GPU {device_id} low memory ({snapshot.free_mb:.1f}MB free) - cleaning up"
                        )
                        self.cleanup_memory(device_id)

                # Limit snapshots to prevent memory bloat
                if len(self.snapshots) > 1000:
                    self.snapshots = self.snapshots[-500:]

                time.sleep(self.config.profiling_interval_seconds)

            except Exception as e:
                logger.warning(f"GPU monitoring error: {e}")
                time.sleep(self.config.profiling_interval_seconds)

    def capture_snapshot(self, device_id: int) -> GPUMemorySnapshot:
        """Capture GPU memory snapshot.

        Args:
            device_id: GPU device ID

        Returns:
            Memory snapshot
        """
        if not self.enabled:
            return GPUMemorySnapshot(
                timestamp=time.time(),
                device_id=device_id,
                allocated_mb=0,
                reserved_mb=0,
                total_mb=0,
                free_mb=0,
                utilization_percent=0,
            )

        if self.device_type == "cuda":
            with torch.cuda.device(device_id):
                # Basic memory info
                allocated = torch.cuda.memory_allocated(device_id) / (1024**2)  # MB
                reserved = torch.cuda.memory_reserved(device_id) / (1024**2)  # MB

                # Get total memory
                try:
                    total = torch.cuda.get_device_properties(device_id).total_memory / (
                        1024**2
                    )  # MB
                except Exception:
                    total = 0
        elif self.device_type == "mps":
            # MPS memory tracking is limited
            allocated = 0  # Cannot accurately track MPS memory usage
            reserved = 0
            total = 0  # MPS shares system memory
        else:
            # CPU
            allocated = 0
            reserved = 0
            total = 0

        free = total - allocated if total > 0 else 0
        utilization = (allocated / total * 100) if total > 0 else 0

        # Additional GPU stats (if available) - only for CUDA
        temperature = None
        power_usage = None

        if self.device_type == "cuda":
            try:
                import pynvml

                if not hasattr(self, "_nvml_initialized"):
                    pynvml.nvmlInit()
                    self._nvml_initialized = True

                handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)

                # Temperature
                try:
                    temperature = pynvml.nvmlDeviceGetTemperature(
                        handle, pynvml.NVML_TEMPERATURE_GPU
                    )
                except Exception:
                    pass

                # Power usage
                try:
                    power_usage = (
                        pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0
                    )  # Convert mW to W
                except Exception:
                    pass

            except ImportError:
                pass  # pynvml not available
            except Exception:
                pass  # Other NVML errors

        return GPUMemorySnapshot(
            timestamp=time.time(),
            device_id=device_id,
            allocated_mb=allocated,
            reserved_mb=reserved,
            total_mb=total,
            free_mb=free,
            utilization_percent=utilization,
            temperature_celsius=temperature,
            power_usage_watts=power_usage,
        )

    def cleanup_memory(self, device_id: Optional[int] = None):
        """Clean up GPU memory.

        Args:
            device_id: Specific device to clean (None = all devices)
        """
        if not self.enabled:
            return

        devices_to_clean = [device_id] if device_id is not None else self.device_ids

        if self.device_type == "cuda":
            for dev_id in devices_to_clean:
                with torch.cuda.device(dev_id):
                    # Clear cache
                    torch.cuda.empty_cache()

                    # Force garbage collection
                    if self.config.aggressive_cleanup:
                        gc.collect()
                        torch.cuda.empty_cache()  # Clear again after GC
        elif self.device_type == "mps":
            # MPS cleanup - force garbage collection
            if self.config.aggressive_cleanup:
                gc.collect()
                # MPS memory is managed by the system, no cache to clear
        else:
            # CPU cleanup
            if self.config.aggressive_cleanup:
                gc.collect()

        logger.debug(f"GPU memory cleanup completed for devices: {devices_to_clean}")

    @contextmanager
    def memory_efficient_context(self, device_id: int = 0):
        """Context manager for memory-efficient operations.

        Args:
            device_id: GPU device ID
        """
        if not self.enabled:
            yield
            return

        # Capture initial memory
        initial_memory = torch.cuda.memory_allocated(device_id)

        try:
            yield
        finally:
            # Cleanup and check for leaks
            self.cleanup_memory(device_id)
            final_memory = torch.cuda.memory_allocated(device_id)

            memory_diff = final_memory - initial_memory
            if memory_diff > 100 * 1024 * 1024:  # > 100MB difference
                logger.warning(
                    f"Potential memory leak detected: {memory_diff / (1024**2):.1f}MB"
                )

    @contextmanager
    def mixed_precision_context(self):
        """Context manager for mixed precision operations."""
        if (
            not self.enabled
            or not self.config.enable_mixed_precision
            or self.scaler is None
        ):
            yield None
            return

        yield self.scaler

    def optimize_batch_size(
        self,
        model: nn.Module,
        sample_batch: tuple[torch.Tensor, ...],
        criterion: nn.Module,
        device_id: int = 0,
        max_batch_size: int = 512,
    ) -> int:
        """Find optimal batch size for GPU memory.

        Args:
            model: PyTorch model
            sample_batch: Sample batch for testing
            criterion: Loss function
            device_id: GPU device ID
            max_batch_size: Maximum batch size to test

        Returns:
            Optimal batch size
        """
        if not self.enabled:
            return 32  # Default fallback

        logger.info(f"Finding optimal batch size for GPU {device_id}...")

        # Move model to device
        device = torch.device(f"cuda:{device_id}")
        model = model.to(device)
        model.train()

        # Test progressively larger batch sizes
        optimal_batch_size = 32  # Safe default
        current_batch_size = 32

        while current_batch_size <= max_batch_size:
            try:
                # Clear memory before test
                self.cleanup_memory(device_id)

                # Create test batch
                features, labels = (
                    sample_batch[0][:current_batch_size],
                    sample_batch[1][:current_batch_size],
                )
                features = features.to(device)
                labels = labels.to(device)

                # Test forward and backward pass
                with torch.cuda.device(device_id):
                    if self.config.enable_mixed_precision and self.scaler:
                        with torch.cuda.amp.autocast():
                            outputs = model(features)
                            loss = criterion(outputs, labels)

                        self.scaler.scale(loss).backward()
                        self.scaler.step(torch.optim.Adam(model.parameters()))
                        self.scaler.update()
                    else:
                        outputs = model(features)
                        loss = criterion(outputs, labels)
                        loss.backward()

                # If we get here, batch size worked
                optimal_batch_size = current_batch_size
                logger.debug(f"Batch size {current_batch_size} successful")

                # Try larger batch size
                current_batch_size = int(current_batch_size * 1.5)

            except RuntimeError as e:
                if "out of memory" in str(e).lower():
                    logger.info(
                        f"OOM at batch size {current_batch_size}, optimal: {optimal_batch_size}"
                    )
                    break
                else:
                    raise e
            except Exception as e:
                logger.warning(f"Error testing batch size {current_batch_size}: {e}")
                break

        # Clean up
        self.cleanup_memory(device_id)

        # Use 80% of max successful batch size for safety
        final_batch_size = max(16, int(optimal_batch_size * 0.8))
        logger.info(f"Optimal batch size for GPU {device_id}: {final_batch_size}")

        return final_batch_size

    def get_memory_summary(self) -> dict[str, Any]:
        """Get comprehensive GPU memory summary."""
        if not self.enabled:
            return {"gpu_available": False}

        summary = {
            "gpu_available": True,
            "num_devices": self.num_devices,
            "device_ids": self.device_ids,
            "devices": {},
            "total_memory_mb": 0,
            "total_allocated_mb": 0,
            "total_free_mb": 0,
            "peak_usage": self.peak_memory_usage,
        }

        for device_id in self.device_ids:
            snapshot = self.capture_snapshot(device_id)

            device_info = {
                "name": torch.cuda.get_device_name(device_id),
                "capability": torch.cuda.get_device_capability(device_id),
                "memory": snapshot.to_dict(),
            }

            summary["devices"][device_id] = device_info
            summary["total_memory_mb"] += snapshot.total_mb
            summary["total_allocated_mb"] += snapshot.allocated_mb
            summary["total_free_mb"] += snapshot.free_mb

        return summary

    def get_optimization_recommendations(self) -> list[str]:
        """Get GPU memory optimization recommendations."""
        if not self.enabled:
            return ["GPU not available - consider using CPU optimization strategies"]

        recommendations = []

        for device_id in self.device_ids:
            snapshot = self.capture_snapshot(device_id)

            # Memory usage recommendations
            if snapshot.utilization_percent > 90:
                recommendations.append(
                    f"GPU {device_id}: Very high memory usage ({snapshot.utilization_percent:.1f}%) - consider reducing batch size"
                )
            elif snapshot.utilization_percent < 50:
                recommendations.append(
                    f"GPU {device_id}: Low memory usage ({snapshot.utilization_percent:.1f}%) - consider increasing batch size"
                )

            # Temperature recommendations
            if snapshot.temperature_celsius and snapshot.temperature_celsius > 80:
                recommendations.append(
                    f"GPU {device_id}: High temperature ({snapshot.temperature_celsius}°C) - check cooling"
                )

            # Power recommendations
            if snapshot.power_usage_watts and snapshot.power_usage_watts > 250:
                recommendations.append(
                    f"GPU {device_id}: High power usage ({snapshot.power_usage_watts}W) - monitor for efficiency"
                )

        # General recommendations
        if not self.config.enable_mixed_precision:
            recommendations.append(
                "Consider enabling mixed precision training for memory efficiency"
            )

        if not self.config.enable_memory_pooling:
            recommendations.append(
                "Consider enabling memory pooling for better allocation"
            )

        return recommendations

    def memory_profiler_context(self, name: str = "operation"):
        """Context manager for profiling memory usage of operations."""
        return self._MemoryProfilerContext(self, name)

    class _MemoryProfilerContext:
        """Context manager for memory profiling."""

        def __init__(self, manager: "GPUMemoryManager", name: str):
            self.manager = manager
            self.name = name
            self.start_snapshots = {}

        def __enter__(self):
            if self.manager.enabled:
                for device_id in self.manager.device_ids:
                    self.start_snapshots[device_id] = self.manager.capture_snapshot(
                        device_id
                    )
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            if self.manager.enabled:
                for device_id in self.manager.device_ids:
                    end_snapshot = self.manager.capture_snapshot(device_id)
                    start_snapshot = self.start_snapshots[device_id]

                    memory_delta = (
                        end_snapshot.allocated_mb - start_snapshot.allocated_mb
                    )

                    if abs(memory_delta) > 1.0:  # > 1MB change
                        logger.debug(
                            f"Memory profile '{self.name}' GPU {device_id}: "
                            f"{memory_delta:+.1f}MB change"
                        )

    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()
