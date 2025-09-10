"""
Tests for TimeEstimationEngine in its new generic infrastructure location.

Following TDD methodology - tests written first to ensure extraction preserves functionality.
"""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from ktrdr.async_infrastructure.time_estimation import TimeEstimationEngine


class TestTimeEstimationEngine:
    """Test TimeEstimationEngine functionality in generic location."""

    def test_initialization_without_cache(self):
        """Test TimeEstimationEngine initializes properly without cache file."""
        engine = TimeEstimationEngine()

        assert engine.cache_file is None
        assert engine.operation_history == {}

    def test_initialization_with_cache_file(self):
        """Test TimeEstimationEngine initializes with cache file path."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            cache_path = Path(tmp.name)

        engine = TimeEstimationEngine(cache_file=cache_path)

        assert engine.cache_file == cache_path
        assert engine.operation_history == {}

    def test_create_operation_key_basic(self):
        """Test operation key creation for basic operation types."""
        engine = TimeEstimationEngine()

        key = engine._create_operation_key("data_load", {})
        assert key == "data_load"

        key = engine._create_operation_key("training", {"model": "lstm"})
        assert key == "training"

    def test_create_operation_key_generic_size_context(self):
        """Test operation key creation with generic size-based context."""
        engine = TimeEstimationEngine()

        # Small dataset
        key = engine._create_operation_key("process", {"data_points": 500})
        assert key == "process|size:small"

        # Medium dataset
        key = engine._create_operation_key("process", {"data_points": 1000})
        assert key == "process|size:medium"

        # Large dataset
        key = engine._create_operation_key("process", {"data_points": 15000})
        assert key == "process|size:large"

    def test_record_operation_completion_basic(self):
        """Test recording operation completion."""
        engine = TimeEstimationEngine()

        engine.record_operation_completion("test_op", {}, 2.5)

        assert "test_op" in engine.operation_history
        assert len(engine.operation_history["test_op"]) == 1

        record = engine.operation_history["test_op"][0]
        assert record["duration"] == 2.5
        assert isinstance(record["timestamp"], datetime)
        assert record["context"] == {}

    def test_record_operation_completion_invalid_duration(self):
        """Test that invalid durations are ignored."""
        engine = TimeEstimationEngine()

        engine.record_operation_completion("test_op", {}, 0)
        engine.record_operation_completion("test_op", {}, -1.0)

        assert "test_op" not in engine.operation_history

    def test_record_operation_completion_with_context(self):
        """Test recording with context information."""
        engine = TimeEstimationEngine()
        context = {"type": "backfill", "data_points": 1000}

        engine.record_operation_completion("data_load", context, 3.0)

        key = "data_load|size:medium"
        assert key in engine.operation_history

        record = engine.operation_history[key][0]
        assert record["duration"] == 3.0
        assert record["context"] == context

    def test_record_operation_completion_history_limit(self):
        """Test that operation history is limited to last 10 records."""
        engine = TimeEstimationEngine()

        # Record 15 operations
        for i in range(15):
            engine.record_operation_completion("test_op", {}, i + 1.0)

        # Should only keep last 10
        assert len(engine.operation_history["test_op"]) == 10

        # Should be the last 10 durations (6.0 through 15.0)
        durations = [
            record["duration"] for record in engine.operation_history["test_op"]
        ]
        assert durations == list(range(6, 16))  # 6.0 to 15.0

    def test_estimate_duration_insufficient_data(self):
        """Test estimation returns None with insufficient data."""
        engine = TimeEstimationEngine()

        # No data
        estimate = engine.estimate_duration("unknown_op", {})
        assert estimate is None

        # Only one record
        engine.record_operation_completion("test_op", {}, 2.0)
        estimate = engine.estimate_duration("test_op", {})
        assert estimate is None

    def test_estimate_duration_with_sufficient_data(self):
        """Test estimation with sufficient historical data."""
        engine = TimeEstimationEngine()

        # Record multiple operations
        durations = [2.0, 3.0, 4.0, 3.5, 2.5]
        for duration in durations:
            engine.record_operation_completion("test_op", {}, duration)

        estimate = engine.estimate_duration("test_op", {})

        # Should return a weighted average (more recent operations weighted higher)
        assert estimate is not None
        assert 2.0 <= estimate <= 4.0

    def test_estimate_duration_weighted_by_recency(self):
        """Test that more recent operations have higher weight."""
        engine = TimeEstimationEngine()

        # Record old slow operation, then recent fast operations
        engine.record_operation_completion("test_op", {}, 10.0)  # Old, slow
        engine.record_operation_completion("test_op", {}, 1.0)  # Recent, fast
        engine.record_operation_completion("test_op", {}, 1.0)  # Recent, fast

        estimate = engine.estimate_duration("test_op", {})

        # Should be closer to recent fast operations than old slow one
        assert estimate < 5.0  # Should be much less than simple average

    @patch("ktrdr.async_infrastructure.time_estimation.datetime")
    def test_estimate_duration_time_weight_decay(self, mock_datetime):
        """Test that very old records have reduced weight."""
        engine = TimeEstimationEngine()

        # Mock current time
        now = datetime(2024, 1, 15, 12, 0, 0)
        mock_datetime.now.return_value = now

        # Record operation with old timestamp
        old_record = {
            "duration": 10.0,
            "timestamp": datetime(2023, 12, 1, 12, 0, 0),  # 45 days ago
            "context": {},
        }

        # Record recent operation
        recent_record = {
            "duration": 2.0,
            "timestamp": datetime(2024, 1, 14, 12, 0, 0),  # 1 day ago
            "context": {},
        }

        engine.operation_history["test_op"] = [old_record, recent_record]

        estimate = engine.estimate_duration("test_op", {})

        # Should heavily favor recent record due to time decay
        assert estimate < 5.0

    def test_cache_save_and_load(self):
        """Test cache persistence functionality."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            cache_path = Path(tmp.name)

        try:
            # Create engine and record some data
            engine1 = TimeEstimationEngine(cache_file=cache_path)
            engine1.record_operation_completion("test_op", {"data_points": 1000}, 2.5)
            engine1.record_operation_completion("test_op", {"data_points": 1000}, 3.0)

            # Force save
            engine1._save_cache()

            # Create new engine and load from cache
            engine2 = TimeEstimationEngine(cache_file=cache_path)

            # Should have loaded the data
            key = "test_op|size:medium"
            assert key in engine2.operation_history
            assert len(engine2.operation_history[key]) == 2

            # Should be able to estimate based on loaded data
            estimate = engine2.estimate_duration("test_op", {"data_points": 1000})
            assert estimate is not None

        finally:
            # Clean up
            if cache_path.exists():
                cache_path.unlink()

    def test_cache_load_nonexistent_file(self):
        """Test loading cache when file doesn't exist."""
        nonexistent_path = Path("/tmp/nonexistent_cache.pkl")

        engine = TimeEstimationEngine(cache_file=nonexistent_path)

        # Should initialize with empty history
        assert engine.operation_history == {}

    def test_cache_load_corrupted_file(self):
        """Test handling of corrupted cache file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            cache_path = Path(tmp.name)
            # Write invalid pickle data
            tmp.write(b"invalid pickle data")

        try:
            # Should handle gracefully
            engine = TimeEstimationEngine(cache_file=cache_path)
            assert engine.operation_history == {}

        finally:
            if cache_path.exists():
                cache_path.unlink()

    def test_generic_operation_types(self):
        """Test that engine works with any operation type (not just data operations)."""
        engine = TimeEstimationEngine()

        # Test various operation types
        operation_types = [
            "data_load",
            "model_training",
            "indicator_calculation",
            "backtest_run",
            "api_request",
            "file_processing",
        ]

        for op_type in operation_types:
            engine.record_operation_completion(op_type, {}, 1.5)
            engine.record_operation_completion(op_type, {}, 2.0)

            estimate = engine.estimate_duration(op_type, {})
            assert estimate is not None
            assert 1.0 <= estimate <= 3.0

    def test_context_isolation(self):
        """Test that different contexts produce different operation keys."""
        engine = TimeEstimationEngine()

        # Record operations with different contexts
        engine.record_operation_completion(
            "process", {"data_points": 500}, 1.0
        )  # small
        engine.record_operation_completion(
            "process", {"data_points": 5000}, 2.0
        )  # medium
        engine.record_operation_completion(
            "process", {"data_points": 50000}, 4.0
        )  # large

        # Each context should have its own history
        assert "process|size:small" in engine.operation_history
        assert "process|size:medium" in engine.operation_history
        assert "process|size:large" in engine.operation_history

        # Each should have only one record
        assert len(engine.operation_history["process|size:small"]) == 1
        assert len(engine.operation_history["process|size:medium"]) == 1
        assert len(engine.operation_history["process|size:large"]) == 1
