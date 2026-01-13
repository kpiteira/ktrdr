"""
Unit tests for DummyOperationAdapter.

Tests the dummy operation adapter - a simple reference implementation
used for testing and as an example for developers.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from rich.console import Console

from ktrdr.cli.operation_adapters import DummyOperationAdapter


class TestDummyOperationAdapter:
    """Test suite for DummyOperationAdapter."""

    def test_initialization_with_defaults(self):
        """Test adapter initialization with default parameters."""
        adapter = DummyOperationAdapter()

        assert adapter.duration == 200
        assert adapter.iterations == 100

    def test_initialization_with_custom_values(self):
        """Test adapter initialization with custom parameters."""
        adapter = DummyOperationAdapter(duration=300, iterations=150)

        assert adapter.duration == 300
        assert adapter.iterations == 150

    def test_get_start_endpoint(self):
        """Test that correct endpoint is returned with /api/v1 prefix."""
        adapter = DummyOperationAdapter()

        assert adapter.get_start_endpoint() == "/api/v1/dummy/start"

    def test_get_start_payload(self):
        """Test payload construction - should be empty for dummy."""
        adapter = DummyOperationAdapter(duration=100, iterations=50)

        payload = adapter.get_start_payload()

        # Dummy operation doesn't require payload parameters
        assert payload == {}

    def test_parse_start_response(self):
        """Test parsing response to extract operation_id."""
        adapter = DummyOperationAdapter()

        response = {
            "success": True,
            "data": {
                "operation_id": "dummy-op-123",
                "status": "running",
            },
        }

        operation_id = adapter.parse_start_response(response)
        assert operation_id == "dummy-op-123"

    def test_parse_start_response_missing_data(self):
        """Test parsing response when data is missing raises KeyError."""
        adapter = DummyOperationAdapter()

        response = {"success": True}

        with pytest.raises(KeyError):
            adapter.parse_start_response(response)

    @pytest.mark.asyncio
    async def test_display_results_success(self):
        """Test displaying dummy operation results."""
        adapter = DummyOperationAdapter()

        # Mock console
        console = MagicMock(spec=Console)

        # Mock HTTP client (not used by dummy, but required by interface)
        http_client = AsyncMock()

        final_status = {
            "operation_id": "dummy-123",
            "status": "completed",
            "progress": {"current_step": 100, "total_steps": 100},
            "metadata": {"duration": 200},
        }

        # Call display_results
        await adapter.display_results(final_status, console, http_client)

        # Verify console.print was called with completion message
        assert console.print.call_count == 3

        # Verify the messages contain expected content
        calls = [str(call) for call in console.print.call_args_list]
        assert any("completed" in call.lower() for call in calls)
        assert any("100" in call for call in calls)  # iterations
        assert any("200" in call for call in calls)  # duration

    @pytest.mark.asyncio
    async def test_display_results_missing_fields(self):
        """Test displaying results when some fields are missing."""
        adapter = DummyOperationAdapter()

        console = MagicMock(spec=Console)
        http_client = AsyncMock()

        # Minimal final_status without progress/metadata
        final_status = {
            "operation_id": "dummy-123",
            "status": "completed",
        }

        # Should not raise exception, just show N/A
        await adapter.display_results(final_status, console, http_client)

        # Should still print completion message
        assert console.print.call_count == 3

        # Check that N/A is shown for missing values
        calls = [str(call) for call in console.print.call_args_list]
        assert any("N/A" in call for call in calls)
