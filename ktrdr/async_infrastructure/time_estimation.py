"""
Generic time estimation engine for async operations.

Provides learning-based time estimation for any operation type by recording completion times
and using historical data to provide increasingly accurate estimates.

Extracted from ProgressManager to make time estimation available across all components
without domain-specific coupling.
"""

import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TimeEstimationEngine:
    """
    Learning-based time estimation engine for progress operations.

    Records completion times for different operation types and contexts,
    then uses this historical data to provide increasingly accurate estimates.

    This is a generic infrastructure component that can be used by any operation type
    (data loading, model training, API requests, file processing, etc.).
    """

    def __init__(self, cache_file: Optional[Path] = None):
        """Initialize time estimation engine with optional persistent cache."""
        self.cache_file = cache_file
        self.operation_history: dict[str, list[dict]] = {}
        self._load_cache()

    def _create_operation_key(
        self, operation_type: str, context: dict[str, Any]
    ) -> str:
        """Create a unique key for operation type and context."""
        # Create key based on operation type and relevant context
        key_parts = [operation_type]

        # Add generic context parts for better estimation
        # Size-based categorization for any operation that processes items
        if "data_points" in context:
            # Group by data size ranges for better estimation
            size = int(context["data_points"])
            if size < 1000:
                key_parts.append("size:small")
            elif size < 10000:
                key_parts.append("size:medium")
            else:
                key_parts.append("size:large")

        return "|".join(key_parts)

    def record_operation_completion(
        self, operation_type: str, context: dict[str, Any], duration_seconds: float
    ) -> None:
        """Record completed operation for future estimation."""
        if duration_seconds <= 0:
            return  # Invalid duration

        key = self._create_operation_key(operation_type, context)

        if key not in self.operation_history:
            self.operation_history[key] = []

        self.operation_history[key].append(
            {
                "duration": duration_seconds,
                "timestamp": datetime.now(),
                "context": context.copy(),
            }
        )

        # Keep only recent history (last 10 operations)
        self.operation_history[key] = self.operation_history[key][-10:]

        # Save to cache periodically
        self._save_cache()

        logger.debug(f"Recorded operation completion: {key} - {duration_seconds:.2f}s")

    def estimate_duration(
        self, operation_type: str, context: dict[str, Any]
    ) -> Optional[float]:
        """Estimate operation duration based on historical data."""
        key = self._create_operation_key(operation_type, context)

        if key not in self.operation_history or len(self.operation_history[key]) < 2:
            return None  # Not enough data for estimation

        # Use weighted average with more weight on recent operations
        history = self.operation_history[key]
        total_weight = 0.0
        weighted_sum = 0.0

        for i, record in enumerate(history):
            # More recent = higher weight, also consider recency by timestamp
            age_weight = i + 1
            time_weight = 1.0

            # Reduce weight for very old records (older than 30 days)
            age_days = (datetime.now() - record["timestamp"]).days
            if age_days > 30:
                time_weight = 0.5
            elif age_days > 7:
                time_weight = 0.8

            combined_weight = age_weight * time_weight
            weighted_sum += record["duration"] * combined_weight
            total_weight += combined_weight

        estimated = weighted_sum / total_weight if total_weight > 0 else None

        if estimated:
            logger.debug(
                f"Estimated duration for {key}: {estimated:.2f}s (based on {len(history)} records)"
            )

        return estimated

    def _load_cache(self) -> None:
        """Load operation history from cache file."""
        if not self.cache_file or not self.cache_file.exists():
            return

        try:
            with open(self.cache_file, "rb") as f:
                self.operation_history = pickle.load(f)
            logger.debug(
                f"Loaded time estimation cache with {len(self.operation_history)} operation types"
            )
        except Exception as e:
            logger.warning(f"Failed to load time estimation cache: {e}")
            self.operation_history = {}

    def _save_cache(self) -> None:
        """Save operation history to cache file."""
        if not self.cache_file:
            return

        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "wb") as f:
                pickle.dump(self.operation_history, f)
        except Exception as e:
            logger.warning(f"Failed to save time estimation cache: {e}")
