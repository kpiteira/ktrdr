"""
Unit tests for TrainingOperationAdapter.

Tests the training-specific logic for the unified operations pattern.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from rich.console import Console

from ktrdr.cli.operation_adapters import TrainingOperationAdapter


class TestTrainingOperationAdapter:
    """Test suite for TrainingOperationAdapter."""

    def test_initialization(self):
        """Test adapter initialization with all parameters."""
        adapter = TrainingOperationAdapter(
            strategy_name="trend_momentum",
            symbols=["AAPL", "GOOGL"],
            timeframes=["1h", "1d"],
            start_date="2024-01-01",
            end_date="2024-06-01",
            validation_split=0.2,
            detailed_analytics=True,
        )

        assert adapter.strategy_name == "trend_momentum"
        assert adapter.symbols == ["AAPL", "GOOGL"]
        assert adapter.timeframes == ["1h", "1d"]
        assert adapter.start_date == "2024-01-01"
        assert adapter.end_date == "2024-06-01"
        assert adapter.validation_split == 0.2
        assert adapter.detailed_analytics is True

    def test_initialization_with_defaults(self):
        """Test adapter initialization with optional parameters."""
        adapter = TrainingOperationAdapter(
            strategy_name="trend_momentum",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        assert adapter.start_date is None
        assert adapter.end_date is None
        assert adapter.validation_split == 0.2
        assert adapter.detailed_analytics is False

    def test_get_start_endpoint(self):
        """Test that correct endpoint is returned."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        assert adapter.get_start_endpoint() == "/api/v1/trainings/start"

    def test_get_start_payload_with_all_fields(self):
        """Test payload construction with all fields."""
        adapter = TrainingOperationAdapter(
            strategy_name="trend_momentum",
            symbols=["AAPL", "GOOGL"],
            timeframes=["1h", "1d"],
            start_date="2024-01-01",
            end_date="2024-06-01",
            detailed_analytics=True,
        )

        payload = adapter.get_start_payload()

        assert payload == {
            "strategy_name": "trend_momentum",
            "symbols": ["AAPL", "GOOGL"],
            "timeframes": ["1h", "1d"],
            "start_date": "2024-01-01",
            "end_date": "2024-06-01",
            "detailed_analytics": True,
        }

    def test_get_start_payload_without_dates(self):
        """Test payload construction without optional dates."""
        adapter = TrainingOperationAdapter(
            strategy_name="trend_momentum",
            symbols=["AAPL"],
            timeframes=["1h"],
            detailed_analytics=False,
        )

        payload = adapter.get_start_payload()

        assert payload == {
            "strategy_name": "trend_momentum",
            "symbols": ["AAPL"],
            "timeframes": ["1h"],
            "detailed_analytics": False,
        }
        # Dates should not be in payload if not provided
        assert "start_date" not in payload
        assert "end_date" not in payload

    def test_parse_start_response_with_task_id(self):
        """Test parsing response with task_id (training API format)."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        response = {
            "success": True,
            "task_id": "training-123-456",
            "status": "training_started",
            "message": "Training started",
        }

        operation_id = adapter.parse_start_response(response)
        assert operation_id == "training-123-456"

    def test_parse_start_response_with_data_operation_id(self):
        """Test parsing response with data.operation_id (standard format)."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        response = {"data": {"operation_id": "op-789"}}

        operation_id = adapter.parse_start_response(response)
        assert operation_id == "op-789"

    @pytest.mark.asyncio
    async def test_display_results_success(self):
        """Test displaying training results with full metrics."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        # Mock console
        console = MagicMock(spec=Console)

        # Mock HTTP client
        mock_response = AsyncMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "success": True,
            "training_metrics": {
                "final_train_accuracy": 0.85,
                "final_val_accuracy": 0.82,
                "epochs_completed": 50,
                "training_time_minutes": 15.5,
            },
            "test_metrics": {
                "test_accuracy": 0.83,
                "precision": 0.81,
                "recall": 0.84,
                "f1_score": 0.825,
            },
            "model_info": {
                "parameters_count": 12500,
                "model_size_bytes": 1024000,
                "architecture": "MLP",
            },
        }

        http_client = AsyncMock()
        http_client.get.return_value = mock_response

        final_status = {"operation_id": "training-123"}

        # Call display_results
        await adapter.display_results(final_status, console, http_client)

        # Verify HTTP request was made
        http_client.get.assert_called_once_with(
            "/api/v1/trainings/training-123/performance"
        )

        # Verify console.print was called (at least for success message and table)
        assert console.print.call_count >= 2

    @pytest.mark.asyncio
    async def test_display_results_api_failure(self):
        """Test displaying results when metrics API fails."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        console = MagicMock(spec=Console)

        # Mock HTTP client to raise exception
        http_client = AsyncMock()
        http_client.get.side_effect = Exception("API Error")

        final_status = {"operation_id": "training-123"}

        # Should not raise exception, just log warning
        await adapter.display_results(final_status, console, http_client)

        # Should still print completion message
        assert console.print.call_count >= 1

    @pytest.mark.asyncio
    async def test_display_results_unsuccessful_response(self):
        """Test displaying results when API returns unsuccessful response."""
        adapter = TrainingOperationAdapter(
            strategy_name="test",
            symbols=["AAPL"],
            timeframes=["1h"],
        )

        console = MagicMock(spec=Console)

        # Create a proper async mock for json()
        mock_json = AsyncMock(return_value={"success": False, "error": "Not found"})

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = mock_json

        http_client = AsyncMock()
        http_client.get = AsyncMock(return_value=mock_response)

        final_status = {"operation_id": "training-123"}

        # Should not raise exception even if metrics fetch fails
        await adapter.display_results(final_status, console, http_client)

        # Should still print completion message
        assert console.print.call_count >= 1
