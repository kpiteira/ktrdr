"""Tests for structured logging fields."""

from ktrdr.monitoring.logging_fields import (
    BaseLogFields,
    DataLogFields,
    OperationLogFields,
    TrainingLogFields,
)


def test_base_log_fields_to_extra():
    """Test BaseLogFields converts to extra dict."""
    # This test will fail until we implement the module
    fields = BaseLogFields()
    result = fields.to_extra()
    assert isinstance(result, dict)


def test_operation_log_fields_required():
    """Test OperationLogFields with required fields."""
    fields = OperationLogFields(operation_id="op_test_123", operation_type="data_load")

    extra = fields.to_extra()

    assert extra["operation_id"] == "op_test_123"
    assert extra["operation_type"] == "data_load"
    assert "status" not in extra  # None values should be excluded


def test_operation_log_fields_with_status():
    """Test OperationLogFields with optional status."""
    fields = OperationLogFields(
        operation_id="op_test_123", operation_type="training", status="started"
    )

    extra = fields.to_extra()

    assert extra["operation_id"] == "op_test_123"
    assert extra["operation_type"] == "training"
    assert extra["status"] == "started"


def test_data_log_fields_required():
    """Test DataLogFields with required fields."""
    fields = DataLogFields(symbol="AAPL", timeframe="1d")

    extra = fields.to_extra()

    assert extra["symbol"] == "AAPL"
    assert extra["timeframe"] == "1d"
    assert "provider" not in extra  # None values excluded
    assert "start_date" not in extra
    assert "end_date" not in extra


def test_data_log_fields_complete():
    """Test DataLogFields with all fields."""
    fields = DataLogFields(
        symbol="EURUSD",
        timeframe="1h",
        provider="ib_host_service",
        start_date="2024-01-01",
        end_date="2024-12-31",
    )

    extra = fields.to_extra()

    assert extra["symbol"] == "EURUSD"
    assert extra["timeframe"] == "1h"
    assert extra["provider"] == "ib_host_service"
    assert extra["start_date"] == "2024-01-01"
    assert extra["end_date"] == "2024-12-31"


def test_training_log_fields_required():
    """Test TrainingLogFields with required fields."""
    fields = TrainingLogFields(strategy="momentum", symbol="AAPL")

    extra = fields.to_extra()

    assert extra["strategy"] == "momentum"
    assert extra["symbol"] == "AAPL"
    assert "model_id" not in extra  # None values excluded


def test_training_log_fields_complete():
    """Test TrainingLogFields with all fields."""
    fields = TrainingLogFields(
        model_id="model_v1",
        strategy="mean_reversion",
        symbol="EURUSD",
        epochs=100,
        batch_size=32,
    )

    extra = fields.to_extra()

    assert extra["model_id"] == "model_v1"
    assert extra["strategy"] == "mean_reversion"
    assert extra["symbol"] == "EURUSD"
    assert extra["epochs"] == 100
    assert extra["batch_size"] == 32


def test_none_values_excluded():
    """Test that None values are excluded from extra dict."""
    fields = DataLogFields(symbol="AAPL", timeframe="1d", provider=None)

    extra = fields.to_extra()

    assert "symbol" in extra
    assert "timeframe" in extra
    assert "provider" not in extra  # None should be excluded
