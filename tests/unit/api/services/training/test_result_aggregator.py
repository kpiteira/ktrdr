"""Tests for training result aggregator."""

from __future__ import annotations

import pytest

from ktrdr.api.services.training.context import TrainingOperationContext
from ktrdr.api.services.training.result_aggregator import from_host_run, from_local_run


@pytest.fixture
def sample_context() -> TrainingOperationContext:
    """Create a sample training context for testing."""
    from pathlib import Path

    from ktrdr.api.models.operations import OperationMetadata, OperationStatus

    metadata = OperationMetadata(
        name="test_training",
        type="training",
        parameters={},
        status=OperationStatus.RUNNING,
    )

    return TrainingOperationContext(
        operation_id="test-op-123",
        strategy_name="TestStrategy",
        strategy_path=Path("path/to/strategy.yaml"),
        strategy_config={},
        symbols=["EURUSD", "GBPUSD"],
        timeframes=["1h", "4h"],
        start_date="2023-01-01",
        end_date="2023-12-31",
        training_config={},
        analytics_enabled=False,
        use_host_service=False,
        training_mode="local",
        total_epochs=100,
        total_batches=None,
        metadata=metadata,
    )


class TestFromLocalRun:
    """Test aggregation of local training results."""

    def test_aggregates_training_metrics_from_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract and normalize training metrics from local run."""
        raw_result = {
            "training_metrics": {
                "final_train_loss": 0.1234,
                "final_val_loss": 0.2345,
                "final_train_accuracy": 0.8765,
                "final_val_accuracy": 0.8123,
                "epochs_completed": 85,
                "early_stopped": True,
                "training_time_minutes": 12.5,
                "best_epoch": 78,
                "final_learning_rate": 0.0001,
            },
            "test_metrics": {},
            "model_info": {},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["training_metrics"]["final_train_loss"] == 0.1234
        assert result["training_metrics"]["final_val_loss"] == 0.2345
        assert result["training_metrics"]["final_train_accuracy"] == 0.8765
        assert result["training_metrics"]["final_val_accuracy"] == 0.8123
        assert result["training_metrics"]["epochs_completed"] == 85
        assert result["training_metrics"]["early_stopped"] is True
        assert result["training_metrics"]["training_time_minutes"] == 12.5
        assert result["training_metrics"]["best_epoch"] == 78
        assert result["training_metrics"]["final_learning_rate"] == 0.0001

    def test_aggregates_validation_metrics_from_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract validation metrics from training metrics."""
        raw_result = {
            "training_metrics": {
                "final_val_loss": 0.2345,
                "final_val_accuracy": 0.8123,
            },
            "test_metrics": {},
            "model_info": {},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["validation_metrics"]["val_loss"] == 0.2345
        assert result["validation_metrics"]["val_accuracy"] == 0.8123

    def test_aggregates_test_metrics_from_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract test metrics including precision, recall, f1."""
        raw_result = {
            "training_metrics": {},
            "test_metrics": {
                "test_loss": 0.3456,
                "test_accuracy": 0.7890,
                "precision": 0.8100,
                "recall": 0.7500,
                "f1_score": 0.7790,
            },
            "model_info": {},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["test_metrics"]["test_loss"] == 0.3456
        assert result["test_metrics"]["test_accuracy"] == 0.7890
        assert result["test_metrics"]["precision"] == 0.8100
        assert result["test_metrics"]["recall"] == 0.7500
        assert result["test_metrics"]["f1_score"] == 0.7790

    def test_includes_resource_usage_for_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should indicate local training mode in resource usage."""
        raw_result = {
            "training_metrics": {},
            "test_metrics": {},
            "model_info": {},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["resource_usage"]["training_mode"] == "local"
        assert result["resource_usage"]["gpu_used"] is False
        assert result["resource_usage"]["peak_memory_mb"] is None

    def test_includes_artifacts_from_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract artifacts including model path and feature importance."""
        raw_result = {
            "training_metrics": {},
            "test_metrics": {},
            "model_info": {},
            "model_path": "/path/to/model.pth",
            "feature_importance": {"feature1": 0.5, "feature2": 0.3},
            "per_symbol_metrics": {"EURUSD": {"accuracy": 0.85}},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["artifacts"]["model_path"] == "/path/to/model.pth"
        assert result["artifacts"]["feature_importance"] == {
            "feature1": 0.5,
            "feature2": 0.3,
        }
        assert result["artifacts"]["per_symbol_metrics"] == {
            "EURUSD": {"accuracy": 0.85}
        }
        assert result["artifacts"]["analytics_dir"] is None
        assert result["artifacts"]["checkpoints"] == []

    def test_includes_session_info_from_local_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should include complete session info from context."""
        raw_result = {
            "training_metrics": {},
            "test_metrics": {},
            "model_info": {},
            "data_summary": {"total_samples": 10000, "symbols": ["EURUSD", "GBPUSD"]},
        }

        result = from_local_run(sample_context, raw_result)

        assert result["session_info"]["operation_id"] == "test-op-123"
        assert result["session_info"]["strategy_name"] == "TestStrategy"
        assert result["session_info"]["symbols"] == ["EURUSD", "GBPUSD"]
        assert result["session_info"]["timeframes"] == ["1h", "4h"]
        assert result["session_info"]["training_mode"] == "local"
        assert result["session_info"]["use_host_service"] is False
        assert result["session_info"]["start_date"] == "2023-01-01"
        assert result["session_info"]["end_date"] == "2023-12-31"
        assert result["session_info"]["data_summary"]["total_samples"] == 10000

    def test_handles_missing_metrics_gracefully(
        self, sample_context: TrainingOperationContext
    ):
        """Should provide default values when metrics are missing."""
        raw_result = {}

        result = from_local_run(sample_context, raw_result)

        assert result["training_metrics"]["final_train_loss"] == 0.0
        assert result["training_metrics"]["epochs_completed"] == 100  # from context
        assert result["test_metrics"]["test_accuracy"] == 0.0
        assert result["artifacts"]["model_path"] is None


class TestFromHostRun:
    """Test aggregation of host-service training results."""

    def test_aggregates_training_metrics_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract training metrics from host snapshot."""
        sample_context.session_id = "host-session-456"
        host_snapshot = {
            "status": "completed",
            "metrics": {
                "training": {
                    "final_train_loss": 0.1111,
                    "final_train_accuracy": 0.8888,
                    "epochs_completed": 90,
                    "early_stopped": False,
                    "training_time_minutes": 25.5,
                    "best_epoch": 85,
                    "final_learning_rate": 0.00005,
                },
                "validation": {
                    "val_loss": 0.2222,
                    "val_accuracy": 0.8333,
                },
                "test": {},
            },
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["training_metrics"]["final_train_loss"] == 0.1111
        assert result["training_metrics"]["final_val_loss"] == 0.2222
        assert result["training_metrics"]["final_train_accuracy"] == 0.8888
        assert result["training_metrics"]["final_val_accuracy"] == 0.8333
        assert result["training_metrics"]["epochs_completed"] == 90
        assert result["training_metrics"]["early_stopped"] is False
        assert result["training_metrics"]["training_time_minutes"] == 25.5

    def test_aggregates_validation_metrics_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract validation metrics from host snapshot."""
        host_snapshot = {
            "status": "completed",
            "metrics": {
                "training": {},
                "validation": {
                    "val_loss": 0.3333,
                    "val_accuracy": 0.7777,
                },
                "test": {},
            },
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["validation_metrics"]["val_loss"] == 0.3333
        assert result["validation_metrics"]["val_accuracy"] == 0.7777

    def test_aggregates_test_metrics_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract test metrics from host snapshot."""
        host_snapshot = {
            "status": "completed",
            "metrics": {
                "training": {},
                "validation": {},
                "test": {
                    "test_loss": 0.4444,
                    "test_accuracy": 0.7222,
                    "precision": 0.7500,
                    "recall": 0.7000,
                    "f1_score": 0.7240,
                },
            },
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["test_metrics"]["test_loss"] == 0.4444
        assert result["test_metrics"]["test_accuracy"] == 0.7222
        assert result["test_metrics"]["precision"] == 0.7500
        assert result["test_metrics"]["recall"] == 0.7000
        assert result["test_metrics"]["f1_score"] == 0.7240

    def test_includes_resource_usage_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract GPU resource usage from host snapshot."""
        host_snapshot = {
            "status": "completed",
            "metrics": {"training": {}, "validation": {}, "test": {}},
            "resource_usage": {
                "gpu_used": True,
                "gpu_name": "NVIDIA Tesla T4",
                "gpu_utilization_percent": 87.5,
                "peak_memory_mb": 8192,
            },
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["resource_usage"]["training_mode"] == "host"
        assert result["resource_usage"]["gpu_used"] is True
        assert result["resource_usage"]["gpu_name"] == "NVIDIA Tesla T4"
        assert result["resource_usage"]["gpu_utilization_percent"] == 87.5
        assert result["resource_usage"]["peak_memory_mb"] == 8192

    def test_includes_artifacts_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should extract artifacts from host snapshot including download URLs."""
        host_snapshot = {
            "status": "completed",
            "metrics": {"training": {}, "validation": {}, "test": {}},
            "artifacts": {
                "model_path": "/remote/path/model.pth",
                "analytics_dir": "/remote/path/analytics",
                "checkpoints": ["checkpoint_epoch_50.pth", "checkpoint_epoch_75.pth"],
                "download_url": "https://host-service/download/model-123",
                "feature_importance": {"feature1": 0.6, "feature2": 0.4},
                "per_symbol_metrics": {"GBPUSD": {"accuracy": 0.82}},
            },
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["artifacts"]["model_path"] == "/remote/path/model.pth"
        assert result["artifacts"]["analytics_dir"] == "/remote/path/analytics"
        assert result["artifacts"]["checkpoints"] == [
            "checkpoint_epoch_50.pth",
            "checkpoint_epoch_75.pth",
        ]
        assert (
            result["artifacts"]["download_url"]
            == "https://host-service/download/model-123"
        )
        assert result["artifacts"]["feature_importance"] == {
            "feature1": 0.6,
            "feature2": 0.4,
        }

    def test_includes_session_info_from_host_run(
        self, sample_context: TrainingOperationContext
    ):
        """Should include session info with host-specific details."""
        sample_context.session_id = "host-session-789"
        host_snapshot = {
            "status": "completed",
            "metrics": {"training": {}, "validation": {}, "test": {}},
        }

        result = from_host_run(sample_context, host_snapshot)

        assert result["session_info"]["operation_id"] == "test-op-123"
        assert result["session_info"]["session_id"] == "host-session-789"
        assert result["session_info"]["strategy_name"] == "TestStrategy"
        assert result["session_info"]["training_mode"] == "host"
        assert result["session_info"]["use_host_service"] is True
        assert result["session_info"]["host_status"] == "completed"

    def test_handles_missing_host_metrics_gracefully(
        self, sample_context: TrainingOperationContext
    ):
        """Should provide default values when host metrics are missing."""
        host_snapshot = {"status": "completed"}

        result = from_host_run(sample_context, host_snapshot)

        assert result["training_metrics"]["final_train_loss"] == 0.0
        assert result["test_metrics"]["test_accuracy"] == 0.0
        assert result["resource_usage"]["gpu_used"] is True  # default for host
        assert result["artifacts"]["checkpoints"] == []
