"""
Tests for ModelMetadataV3 dataclass.

Tests serialization, deserialization, and v3-specific functionality.
"""

import json
from datetime import datetime, timezone

from ktrdr.models.model_metadata import ModelMetadataV3


class TestModelMetadataV3Init:
    """Test ModelMetadataV3 initialization."""

    def test_basic_init(self):
        """Initialize with required fields."""
        meta = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            resolved_features=["5m_rsi_fast_oversold", "5m_rsi_fast_overbought"],
        )

        assert meta.model_name == "test_model"
        assert meta.strategy_name == "test_strategy"
        assert meta.resolved_features == [
            "5m_rsi_fast_oversold",
            "5m_rsi_fast_overbought",
        ]
        assert meta.strategy_version == "3.0"

    def test_init_with_all_fields(self):
        """Initialize with all optional fields."""
        now = datetime.now(timezone.utc)
        meta = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            created_at=now,
            strategy_version="3.0",
            indicators={"rsi_14": {"type": "rsi", "period": 14}},
            fuzzy_sets={"rsi_fast": {"indicator": "rsi_14", "oversold": [0, 30, 40]}},
            nn_inputs=[{"fuzzy_set": "rsi_fast", "timeframes": "all"}],
            resolved_features=["5m_rsi_fast_oversold"],
            training_symbols=["AAPL", "GOOGL"],
            training_timeframes=["5m", "1h"],
            training_metrics={"loss": 0.05, "accuracy": 0.85},
        )

        assert meta.created_at == now
        assert meta.indicators == {"rsi_14": {"type": "rsi", "period": 14}}
        assert meta.training_symbols == ["AAPL", "GOOGL"]
        assert meta.training_metrics == {"loss": 0.05, "accuracy": 0.85}

    def test_default_created_at(self):
        """created_at defaults to now if not provided."""
        before = datetime.now(timezone.utc)
        meta = ModelMetadataV3(
            model_name="test",
            strategy_name="test",
            resolved_features=[],
        )
        after = datetime.now(timezone.utc)

        assert meta.created_at is not None
        assert before <= meta.created_at <= after


class TestModelMetadataV3Serialization:
    """Test to_dict and from_dict serialization."""

    def test_to_dict(self):
        """to_dict converts all fields to serializable dict."""
        now = datetime.now(timezone.utc)
        meta = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            created_at=now,
            resolved_features=["5m_rsi_fast_oversold"],
            training_symbols=["AAPL"],
            training_metrics={"loss": 0.05},
        )

        d = meta.to_dict()

        assert d["model_name"] == "test_model"
        assert d["strategy_name"] == "test_strategy"
        assert d["created_at"] == now.isoformat()
        assert d["resolved_features"] == ["5m_rsi_fast_oversold"]
        assert d["training_symbols"] == ["AAPL"]
        assert d["strategy_version"] == "3.0"

    def test_from_dict(self):
        """from_dict reconstructs metadata from dict."""
        now = datetime.now(timezone.utc)
        data = {
            "model_name": "test_model",
            "strategy_name": "test_strategy",
            "created_at": now.isoformat(),
            "strategy_version": "3.0",
            "indicators": {"rsi_14": {"type": "rsi"}},
            "fuzzy_sets": {"rsi_fast": {"indicator": "rsi_14"}},
            "nn_inputs": [{"fuzzy_set": "rsi_fast"}],
            "resolved_features": ["5m_rsi_fast_oversold"],
            "training_symbols": ["AAPL"],
            "training_timeframes": ["5m"],
            "training_metrics": {"loss": 0.05},
        }

        meta = ModelMetadataV3.from_dict(data)

        assert meta.model_name == "test_model"
        assert meta.strategy_name == "test_strategy"
        assert meta.created_at == now
        assert meta.indicators == {"rsi_14": {"type": "rsi"}}
        assert meta.resolved_features == ["5m_rsi_fast_oversold"]

    def test_serialization_roundtrip(self):
        """Serialization roundtrip preserves all fields."""
        original = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            indicators={"rsi_14": {"type": "rsi", "period": 14}},
            fuzzy_sets={"rsi_fast": {"indicator": "rsi_14", "oversold": [0, 30, 40]}},
            nn_inputs=[{"fuzzy_set": "rsi_fast", "timeframes": "all"}],
            resolved_features=["5m_rsi_fast_oversold", "5m_rsi_fast_overbought"],
            training_symbols=["AAPL", "GOOGL"],
            training_timeframes=["5m", "1h"],
            training_metrics={"loss": 0.05, "accuracy": 0.85},
        )

        # Round trip
        d = original.to_dict()
        restored = ModelMetadataV3.from_dict(d)

        assert restored.model_name == original.model_name
        assert restored.strategy_name == original.strategy_name
        assert restored.strategy_version == original.strategy_version
        assert restored.indicators == original.indicators
        assert restored.fuzzy_sets == original.fuzzy_sets
        assert restored.nn_inputs == original.nn_inputs
        assert restored.resolved_features == original.resolved_features
        assert restored.training_symbols == original.training_symbols
        assert restored.training_timeframes == original.training_timeframes
        assert restored.training_metrics == original.training_metrics

    def test_json_serialization(self):
        """to_dict output is JSON serializable."""
        meta = ModelMetadataV3(
            model_name="test_model",
            strategy_name="test_strategy",
            resolved_features=["5m_rsi_fast_oversold"],
        )

        d = meta.to_dict()

        # Should not raise
        json_str = json.dumps(d)
        assert json_str is not None

        # Should be deserializable
        restored_dict = json.loads(json_str)
        restored = ModelMetadataV3.from_dict(restored_dict)
        assert restored.model_name == "test_model"


class TestModelMetadataV3DatetimeHandling:
    """Test datetime serialization and parsing."""

    def test_datetime_to_iso(self):
        """Datetime is serialized to ISO format."""
        now = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        meta = ModelMetadataV3(
            model_name="test",
            strategy_name="test",
            created_at=now,
            resolved_features=[],
        )

        d = meta.to_dict()
        assert d["created_at"] == "2024-01-15T10:30:00+00:00"

    def test_datetime_from_iso(self):
        """ISO datetime string is parsed correctly."""
        data = {
            "model_name": "test",
            "strategy_name": "test",
            "created_at": "2024-01-15T10:30:00+00:00",
            "resolved_features": [],
        }

        meta = ModelMetadataV3.from_dict(data)

        assert meta.created_at == datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)

    def test_naive_datetime_handled(self):
        """Naive datetime (without timezone) is handled gracefully."""
        data = {
            "model_name": "test",
            "strategy_name": "test",
            "created_at": "2024-01-15T10:30:00",  # No timezone
            "resolved_features": [],
        }

        # Should not raise
        meta = ModelMetadataV3.from_dict(data)
        assert meta.created_at.year == 2024
        assert meta.created_at.month == 1
        assert meta.created_at.day == 15


class TestModelMetadataV3Defaults:
    """Test default values."""

    def test_default_values(self):
        """Check all default values are correct."""
        meta = ModelMetadataV3(
            model_name="test",
            strategy_name="test",
            resolved_features=[],
        )

        assert meta.strategy_version == "3.0"
        assert meta.indicators == {}
        assert meta.fuzzy_sets == {}
        assert meta.nn_inputs == []
        assert meta.training_symbols == []
        assert meta.training_timeframes == []
        assert meta.training_metrics == {}
