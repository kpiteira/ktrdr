"""
Tests for worker unavailability error handling (Issue #200).

These tests verify that:
1. WorkerUnavailableError is raised with proper context
2. Training endpoint returns 503 with diagnostic info
3. Backtesting endpoint returns 503 with diagnostic info
4. Error response includes all required fields
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from ktrdr.errors import WorkerUnavailableError


class TestWorkerUnavailableError:
    """Test the WorkerUnavailableError exception class."""

    def test_error_has_required_attributes(self) -> None:
        """WorkerUnavailableError should have all required attributes."""
        error = WorkerUnavailableError(
            worker_type="training",
            registered_count=0,
            backend_uptime_seconds=5.2,
        )

        assert error.worker_type == "training"
        assert error.registered_count == 0
        assert error.backend_uptime_seconds == 5.2
        assert "auto-register" in error.hint

    def test_error_default_hint(self) -> None:
        """WorkerUnavailableError should have a helpful default hint."""
        error = WorkerUnavailableError(
            worker_type="backtesting",
            registered_count=0,
            backend_uptime_seconds=10.0,
        )

        assert "Workers auto-register" in error.hint
        assert "Retry" in error.hint

    def test_error_custom_hint(self) -> None:
        """WorkerUnavailableError should accept custom hint."""
        custom_hint = "All workers are busy. Try again later."
        error = WorkerUnavailableError(
            worker_type="training",
            registered_count=2,
            backend_uptime_seconds=100.0,
            hint=custom_hint,
        )

        assert error.hint == custom_hint

    def test_error_message_format(self) -> None:
        """WorkerUnavailableError should have descriptive message."""
        error = WorkerUnavailableError(
            worker_type="training",
            registered_count=0,
            backend_uptime_seconds=5.0,
        )

        assert "training" in error.message
        assert "workers" in error.message.lower()

    def test_error_details_dict(self) -> None:
        """WorkerUnavailableError should have proper details dict."""
        error = WorkerUnavailableError(
            worker_type="training",
            registered_count=3,
            backend_uptime_seconds=42.5,
        )

        assert error.details["worker_type"] == "training"
        assert error.details["registered_workers"] == 3
        assert error.details["backend_uptime_seconds"] == 42.5
        assert "hint" in error.details

    def test_to_response_dict(self) -> None:
        """WorkerUnavailableError.to_response_dict() should format for HTTP response."""
        error = WorkerUnavailableError(
            worker_type="backtesting",
            registered_count=0,
            backend_uptime_seconds=7.3,
        )

        response = error.to_response_dict()

        assert "error" in response
        assert response["worker_type"] == "backtesting"
        assert response["registered_workers"] == 0
        assert response["backend_uptime_seconds"] == 7.3
        assert "hint" in response

    def test_error_code(self) -> None:
        """WorkerUnavailableError should have correct error code."""
        error = WorkerUnavailableError(
            worker_type="training",
            registered_count=0,
            backend_uptime_seconds=0.0,
        )

        assert error.error_code == "WORKER_UNAVAILABLE"


class TestTrainingEndpointNoWorkers:
    """Test training endpoint behavior when no workers are available."""

    @pytest.mark.asyncio
    @patch("ktrdr.api.endpoints.training.get_training_service")
    async def test_training_start_no_workers_returns_503(
        self, mock_get_service: MagicMock
    ) -> None:
        """When no training workers available, return 503 with context."""
        from ktrdr.api.endpoints.training import TrainingRequest, start_training

        # Setup mock to raise WorkerUnavailableError
        mock_service = MagicMock()
        mock_service.start_training.side_effect = WorkerUnavailableError(
            worker_type="training",
            registered_count=0,
            backend_uptime_seconds=5.0,
        )
        mock_get_service.return_value = mock_service

        request = TrainingRequest(
            strategy_name="test_strategy",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_training(request, service=mock_service)

        assert exc_info.value.status_code == 503
        assert "registered_workers" in exc_info.value.detail
        assert exc_info.value.detail["registered_workers"] == 0
        assert "backend_uptime_seconds" in exc_info.value.detail
        assert "hint" in exc_info.value.detail

    @pytest.mark.asyncio
    @patch("ktrdr.api.endpoints.training.get_training_service")
    async def test_training_start_no_workers_error_format(
        self, mock_get_service: MagicMock
    ) -> None:
        """Verify 503 error response has all required fields."""
        from ktrdr.api.endpoints.training import TrainingRequest, start_training

        mock_service = MagicMock()
        mock_service.start_training.side_effect = WorkerUnavailableError(
            worker_type="training",
            registered_count=0,
            backend_uptime_seconds=12.5,
        )
        mock_get_service.return_value = mock_service

        request = TrainingRequest(
            strategy_name="test_strategy",
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_training(request, service=mock_service)

        detail = exc_info.value.detail
        required_fields = [
            "error",
            "worker_type",
            "registered_workers",
            "backend_uptime_seconds",
            "hint",
        ]
        for field in required_fields:
            assert field in detail, f"Missing required field: {field}"


class TestBacktestingEndpointNoWorkers:
    """Test backtesting endpoint behavior when no workers are available."""

    @pytest.mark.asyncio
    @patch("ktrdr.api.endpoints.backtesting.get_backtesting_service")
    async def test_backtest_start_no_workers_returns_503(
        self, mock_get_service: MagicMock
    ) -> None:
        """When no backtest workers available, return 503 with context."""
        from ktrdr.api.endpoints.backtesting import start_backtest
        from ktrdr.api.models.backtesting import BacktestStartRequest

        mock_service = MagicMock()
        mock_service.run_backtest.side_effect = WorkerUnavailableError(
            worker_type="backtesting",
            registered_count=0,
            backend_uptime_seconds=3.0,
        )
        mock_get_service.return_value = mock_service

        request = BacktestStartRequest(
            symbol="AAPL",
            timeframe="1h",
            strategy_name="test_strategy",
            start_date="2024-01-01",
            end_date="2024-06-01",
        )

        with pytest.raises(HTTPException) as exc_info:
            await start_backtest(request, service=mock_service)

        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["worker_type"] == "backtesting"
        assert exc_info.value.detail["registered_workers"] == 0


class TestUptimeModule:
    """Test the uptime tracking module."""

    def test_get_uptime_returns_zero_before_set(self) -> None:
        """get_uptime_seconds should return 0.0 before start time is set."""
        from ktrdr.api import uptime

        # Reset to initial state
        uptime._app_start_time = 0.0

        result = uptime.get_uptime_seconds()
        assert result == 0.0

    def test_set_start_time_records_current_time(self) -> None:
        """set_start_time should record current time."""
        import time

        from ktrdr.api import uptime

        uptime.set_start_time()

        # Check that start time was set to approximately now
        assert uptime._app_start_time > 0
        assert abs(uptime._app_start_time - time.time()) < 1.0

    def test_get_uptime_returns_elapsed_time(self) -> None:
        """get_uptime_seconds should return time since start."""
        import time

        from ktrdr.api import uptime

        uptime._app_start_time = time.time() - 10.0  # 10 seconds ago

        result = uptime.get_uptime_seconds()
        assert 9.5 <= result <= 11.0  # Allow some tolerance


class TestTrainingServiceWorkerSelection:
    """Test TrainingService worker selection with WorkerUnavailableError."""

    def test_select_training_worker_raises_error_when_no_workers(self) -> None:
        """_select_training_worker should raise WorkerUnavailableError when no workers."""
        from ktrdr.api.services.training_service import TrainingService

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        service = TrainingService(worker_registry=mock_registry)

        with pytest.raises(WorkerUnavailableError) as exc_info:
            service._select_training_worker({})

        assert exc_info.value.worker_type == "training"
        assert exc_info.value.registered_count == 0

    def test_select_training_worker_includes_uptime(self) -> None:
        """_select_training_worker should include backend uptime in error."""
        import time

        from ktrdr.api import uptime
        from ktrdr.api.services.training_service import TrainingService

        # Set a known start time
        uptime._app_start_time = time.time() - 30.0

        mock_registry = MagicMock()
        mock_registry.list_workers.return_value = []

        service = TrainingService(worker_registry=mock_registry)

        with pytest.raises(WorkerUnavailableError) as exc_info:
            service._select_training_worker({})

        # Uptime should be approximately 30 seconds
        assert 29.0 <= exc_info.value.backend_uptime_seconds <= 31.0
