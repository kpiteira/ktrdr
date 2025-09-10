"""Memory management and monitoring utilities for KTRDR training."""

import gc
import json
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import psutil
import torch

from ktrdr import get_logger

logger = get_logger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot at a point in time."""

    timestamp: float
    process_memory_mb: float
    system_memory_total_mb: float
    system_memory_available_mb: float
    system_memory_percent: float
    gpu_memory_allocated_mb: float = 0.0
    gpu_memory_cached_mb: float = 0.0
    gpu_memory_total_mb: float = 0.0
    gpu_memory_percent: float = 0.0
    python_objects_count: int = 0
    tensors_count: int = 0
    largest_tensor_mb: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "process_memory_mb": self.process_memory_mb,
            "system_memory_total_mb": self.system_memory_total_mb,
            "system_memory_available_mb": self.system_memory_available_mb,
            "system_memory_percent": self.system_memory_percent,
            "gpu_memory_allocated_mb": self.gpu_memory_allocated_mb,
            "gpu_memory_cached_mb": self.gpu_memory_cached_mb,
            "gpu_memory_total_mb": self.gpu_memory_total_mb,
            "gpu_memory_percent": self.gpu_memory_percent,
            "python_objects_count": self.python_objects_count,
            "tensors_count": self.tensors_count,
            "largest_tensor_mb": self.largest_tensor_mb,
        }


@dataclass
class MemoryBudget:
    """Memory budget configuration and limits."""

    max_process_memory_mb: Optional[float] = None  # None = no limit
    max_gpu_memory_percent: float = 0.9  # Use up to 90% of GPU memory
    warning_threshold_percent: float = 0.8  # Warn at 80% usage
    critical_threshold_percent: float = 0.95  # Critical at 95% usage
    enable_auto_cleanup: bool = True  # Automatic memory cleanup
    cleanup_interval_seconds: float = 30.0  # Cleanup every 30 seconds
    enable_monitoring: bool = True  # Monitor memory usage
    monitoring_interval_seconds: float = 5.0  # Monitor every 5 seconds

    def __post_init__(self):
        """Set default memory limits based on system resources."""
        if self.max_process_memory_mb is None:
            # Default to 70% of system memory
            system_memory_gb = psutil.virtual_memory().total / (1024**3)
            self.max_process_memory_mb = system_memory_gb * 0.7 * 1024


class MemoryManager:
    """Advanced memory management for multi-symbol, multi-timeframe training."""

    def __init__(
        self, budget: Optional[MemoryBudget] = None, output_dir: Optional[Path] = None
    ):
        """Initialize memory manager.

        Args:
            budget: Memory budget configuration
            output_dir: Directory to save memory monitoring logs
        """
        self.budget = budget or MemoryBudget()
        self.output_dir = Path(output_dir) if output_dir else None

        # Memory monitoring
        self.snapshots: list[MemorySnapshot] = []
        self.monitoring_thread: Optional[threading.Thread] = None
        self.monitoring_active = False

        # GPU detection
        self.has_gpu = torch.cuda.is_available()
        if self.has_gpu:
            self.gpu_count = torch.cuda.device_count()
            logger.info(
                f"GPU memory management enabled - {self.gpu_count} GPU(s) detected"
            )
        else:
            self.gpu_count = 0
            logger.info("CPU-only memory management enabled")

        # Process monitoring
        self.process = psutil.Process()

        logger.info(f"MemoryManager initialized with budget: {self.budget}")

    def start_monitoring(self):
        """Start background memory monitoring."""
        if not self.budget.enable_monitoring:
            return

        if self.monitoring_active:
            logger.warning("Memory monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self.monitoring_thread.start()

        logger.info("Memory monitoring started")

    def stop_monitoring(self):
        """Stop background memory monitoring."""
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=1.0)
            self.monitoring_thread = None

        logger.info("Memory monitoring stopped")

    def _monitor_loop(self):
        """Background monitoring loop."""
        while self.monitoring_active:
            try:
                # Suppress warnings during monitoring to avoid tensor warnings
                import warnings

                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)

                    snapshot = self.capture_snapshot()
                    self.snapshots.append(snapshot)

                    # Check for memory warnings
                    self._check_memory_warnings(snapshot)

                    # Automatic cleanup if enabled
                    if self.budget.enable_auto_cleanup:
                        self._auto_cleanup(snapshot)

                    # Keep only recent snapshots to prevent memory bloat
                    if len(self.snapshots) > 1000:
                        self.snapshots = self.snapshots[-500:]  # Keep last 500

                time.sleep(self.budget.monitoring_interval_seconds)

            except Exception as e:
                logger.warning(f"Memory monitoring error: {e}")
                time.sleep(self.budget.monitoring_interval_seconds)

    def capture_snapshot(self) -> MemorySnapshot:
        """Capture current memory usage snapshot."""
        timestamp = time.time()

        # System memory
        memory_info = psutil.virtual_memory()
        system_total = memory_info.total / (1024**2)  # MB
        system_available = memory_info.available / (1024**2)  # MB
        system_percent = memory_info.percent

        # Process memory
        process_memory = self.process.memory_info().rss / (1024**2)  # MB

        # GPU memory
        gpu_allocated = 0.0
        gpu_cached = 0.0
        gpu_total = 0.0
        gpu_percent = 0.0

        if self.has_gpu:
            gpu_allocated = torch.cuda.memory_allocated() / (1024**2)  # MB
            gpu_cached = torch.cuda.memory_reserved() / (1024**2)  # MB

            # Get total GPU memory
            if hasattr(torch.cuda, "get_device_properties"):
                gpu_total = torch.cuda.get_device_properties(0).total_memory / (
                    1024**2
                )  # MB
                if gpu_total > 0:
                    gpu_percent = (gpu_allocated / gpu_total) * 100

        # Python object counting
        python_objects = len(gc.get_objects())

        # Tensor analysis (with warning suppression)
        tensors_count = 0
        largest_tensor_mb = 0.0

        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)

                for obj in gc.get_objects():
                    try:
                        if torch.is_tensor(obj):
                            tensors_count += 1
                            # Safely get tensor size without triggering warnings
                            if hasattr(obj, "element_size") and hasattr(obj, "numel"):
                                if obj.element_size() > 0 and obj.numel() > 0:
                                    tensor_mb = (
                                        obj.numel() * obj.element_size() / (1024**2)
                                    )
                                    largest_tensor_mb = max(
                                        largest_tensor_mb, tensor_mb
                                    )
                    except (RuntimeError, AttributeError):
                        # Skip tensors that can't be safely inspected
                        continue
        except Exception:
            # Fallback: skip tensor analysis if it causes issues
            pass

        return MemorySnapshot(
            timestamp=timestamp,
            process_memory_mb=process_memory,
            system_memory_total_mb=system_total,
            system_memory_available_mb=system_available,
            system_memory_percent=system_percent,
            gpu_memory_allocated_mb=gpu_allocated,
            gpu_memory_cached_mb=gpu_cached,
            gpu_memory_total_mb=gpu_total,
            gpu_memory_percent=gpu_percent,
            python_objects_count=python_objects,
            tensors_count=tensors_count,
            largest_tensor_mb=largest_tensor_mb,
        )

    def _check_memory_warnings(self, snapshot: MemorySnapshot):
        """Check for memory usage warnings."""
        # Process memory warning
        if (
            self.budget.max_process_memory_mb
            and snapshot.process_memory_mb
            > self.budget.max_process_memory_mb * self.budget.warning_threshold_percent
        ):
            logger.warning(
                f"Process memory usage high: {snapshot.process_memory_mb:.1f}MB "
                f"({snapshot.process_memory_mb / self.budget.max_process_memory_mb * 100:.1f}% of budget)"
            )

        # System memory warning
        if snapshot.system_memory_percent > self.budget.warning_threshold_percent * 100:
            logger.warning(
                f"System memory usage high: {snapshot.system_memory_percent:.1f}% "
                f"({snapshot.system_memory_available_mb:.1f}MB available)"
            )

        # GPU memory warning
        if (
            self.has_gpu
            and snapshot.gpu_memory_percent
            > self.budget.warning_threshold_percent * 100
        ):
            logger.warning(
                f"GPU memory usage high: {snapshot.gpu_memory_percent:.1f}% "
                f"({snapshot.gpu_memory_allocated_mb:.1f}MB allocated)"
            )

        # Critical warnings
        if (
            snapshot.system_memory_percent
            > self.budget.critical_threshold_percent * 100
        ):
            logger.critical(
                f"CRITICAL: System memory usage at {snapshot.system_memory_percent:.1f}% - "
                f"Training may be unstable"
            )

        if (
            self.has_gpu
            and snapshot.gpu_memory_percent
            > self.budget.critical_threshold_percent * 100
        ):
            logger.critical(
                f"CRITICAL: GPU memory usage at {snapshot.gpu_memory_percent:.1f}% - "
                f"Risk of out-of-memory errors"
            )

    def _auto_cleanup(self, snapshot: MemorySnapshot):
        """Perform automatic memory cleanup if thresholds exceeded."""
        cleanup_needed = False

        # Check if cleanup is needed
        if (
            self.budget.max_process_memory_mb
            and snapshot.process_memory_mb
            > self.budget.max_process_memory_mb * self.budget.warning_threshold_percent
        ):
            cleanup_needed = True

        if snapshot.system_memory_percent > self.budget.warning_threshold_percent * 100:
            cleanup_needed = True

        if (
            self.has_gpu
            and snapshot.gpu_memory_percent
            > self.budget.warning_threshold_percent * 100
        ):
            cleanup_needed = True

        if cleanup_needed:
            logger.info("Performing automatic memory cleanup")
            self.cleanup_memory()

    def cleanup_memory(self):
        """Perform memory cleanup operations."""
        logger.debug("Starting memory cleanup")

        # Python garbage collection
        collected = gc.collect()
        logger.debug(f"Garbage collection freed {collected} objects")

        # GPU memory cleanup
        if self.has_gpu:
            torch.cuda.empty_cache()
            logger.debug("GPU cache cleared")

        # Force cleanup of unreferenced tensors
        self._cleanup_tensors()

        logger.debug("Memory cleanup completed")

    def _cleanup_tensors(self):
        """Clean up unreferenced tensors."""
        tensors_before = 0
        tensors_after = 0

        try:
            import warnings

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)

                # Count tensors before cleanup
                for obj in gc.get_objects():
                    try:
                        if torch.is_tensor(obj):
                            tensors_before += 1
                    except (RuntimeError, AttributeError):
                        continue

                # Force garbage collection multiple times for tensor cleanup
                for _ in range(3):
                    gc.collect()

                # Count tensors after cleanup
                for obj in gc.get_objects():
                    try:
                        if torch.is_tensor(obj):
                            tensors_after += 1
                    except (RuntimeError, AttributeError):
                        continue

                cleaned = tensors_before - tensors_after
                if cleaned > 0:
                    logger.debug(f"Cleaned up {cleaned} unreferenced tensors")
        except Exception as e:
            logger.debug(f"Tensor cleanup failed: {e}, skipping tensor counting")

    def get_memory_summary(self) -> dict[str, Any]:
        """Get current memory usage summary."""
        snapshot = self.capture_snapshot()

        summary = {
            "current_usage": snapshot.to_dict(),
            "budget": {
                "max_process_memory_mb": self.budget.max_process_memory_mb,
                "max_gpu_memory_percent": self.budget.max_gpu_memory_percent,
                "warning_threshold_percent": self.budget.warning_threshold_percent,
                "critical_threshold_percent": self.budget.critical_threshold_percent,
            },
            "recommendations": self._get_recommendations(snapshot),
        }

        return summary

    def _get_recommendations(self, snapshot: MemorySnapshot) -> list[str]:
        """Get memory optimization recommendations."""
        recommendations = []

        # Process memory recommendations
        if (
            self.budget.max_process_memory_mb
            and snapshot.process_memory_mb > self.budget.max_process_memory_mb * 0.7
        ):
            recommendations.append("Consider reducing batch size to lower memory usage")
            recommendations.append(
                "Enable gradient checkpointing for memory-efficient training"
            )

        # GPU memory recommendations
        if self.has_gpu and snapshot.gpu_memory_percent > 70:
            recommendations.append("Consider using mixed precision training (fp16)")
            recommendations.append(
                "Reduce model size or batch size for GPU memory efficiency"
            )

        # Tensor recommendations
        if snapshot.tensors_count > 10000:
            recommendations.append(
                "High tensor count detected - check for tensor leaks"
            )

        if snapshot.largest_tensor_mb > 100:
            recommendations.append("Large tensors detected - consider tensor sharding")

        return recommendations

    def export_memory_log(self, file_path: Optional[Path] = None) -> Path:
        """Export memory monitoring log to JSON file."""
        if file_path is None:
            if self.output_dir:
                file_path = (
                    self.output_dir
                    / f"memory_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )
            else:
                file_path = Path(
                    f"memory_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                )

        memory_data = {
            "metadata": {
                "start_time": (
                    self.snapshots[0].timestamp if self.snapshots else time.time()
                ),
                "end_time": (
                    self.snapshots[-1].timestamp if self.snapshots else time.time()
                ),
                "total_snapshots": len(self.snapshots),
                "monitoring_interval": self.budget.monitoring_interval_seconds,
                "has_gpu": self.has_gpu,
                "gpu_count": self.gpu_count,
            },
            "budget": {
                "max_process_memory_mb": self.budget.max_process_memory_mb,
                "max_gpu_memory_percent": self.budget.max_gpu_memory_percent,
                "warning_threshold_percent": self.budget.warning_threshold_percent,
                "critical_threshold_percent": self.budget.critical_threshold_percent,
            },
            "snapshots": [snapshot.to_dict() for snapshot in self.snapshots],
        }

        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(memory_data, f, indent=2)

        logger.info(f"Memory log exported to: {file_path}")
        return file_path

    def get_peak_usage(self) -> dict[str, float]:
        """Get peak memory usage from monitoring history."""
        if not self.snapshots:
            return {}

        peak_process = max(s.process_memory_mb for s in self.snapshots)
        peak_system_percent = max(s.system_memory_percent for s in self.snapshots)
        peak_gpu_allocated = (
            max(s.gpu_memory_allocated_mb for s in self.snapshots)
            if self.has_gpu
            else 0
        )
        peak_gpu_percent = (
            max(s.gpu_memory_percent for s in self.snapshots) if self.has_gpu else 0
        )
        peak_tensors = max(s.tensors_count for s in self.snapshots)
        peak_largest_tensor = max(s.largest_tensor_mb for s in self.snapshots)

        return {
            "peak_process_memory_mb": peak_process,
            "peak_system_memory_percent": peak_system_percent,
            "peak_gpu_memory_mb": peak_gpu_allocated,
            "peak_gpu_memory_percent": peak_gpu_percent,
            "peak_tensor_count": peak_tensors,
            "peak_largest_tensor_mb": peak_largest_tensor,
        }

    def __enter__(self):
        """Context manager entry."""
        self.start_monitoring()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop_monitoring()

        # Export log if output directory is set
        if self.output_dir:
            self.export_memory_log()
