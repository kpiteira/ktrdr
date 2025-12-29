"""Tests for WorkerAPIBase._update_operation_status HTTP implementation (M6 Task 6.3).

This tests the actual HTTP call to the backend, not the integration with
graceful shutdown (which is tested in test_base_graceful_shutdown.py).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import OperationType
from ktrdr.api.models.workers import WorkerType
from ktrdr.workers.base import WorkerAPIBase


class _WorkerForStatusTesting(WorkerAPIBase):
    """Worker that doesn't override _update_operation_status for testing."""

    def __init__(self, backend_url: str = "http://backend:8000"):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=5003,
            backend_url=backend_url,
        )


class TestUpdateOperationStatusHTTP:
    """Tests for _update_operation_status HTTP implementation (Task 6.3)."""

    @pytest.mark.asyncio
    async def test_update_status_makes_patch_request(self):
        """Test that _update_operation_status makes a PATCH request to backend."""
        worker = _WorkerForStatusTesting(backend_url="http://test-backend:8000")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await worker._update_operation_status(
                operation_id="op_123",
                status="CANCELLED",
                error_message="Graceful shutdown",
            )

            mock_client.patch.assert_called_once_with(
                "http://test-backend:8000/api/v1/operations/op_123/status",
                json={
                    "status": "CANCELLED",
                    "error_message": "Graceful shutdown",
                },
            )

    @pytest.mark.asyncio
    async def test_update_status_uses_correct_backend_url(self):
        """Test that _update_operation_status uses the configured backend_url."""
        worker = _WorkerForStatusTesting(backend_url="http://custom-backend:9000")

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await worker._update_operation_status("op_xyz", "FAILED")

            call_url = mock_client.patch.call_args[0][0]
            assert call_url.startswith("http://custom-backend:9000/")

    @pytest.mark.asyncio
    async def test_update_status_has_timeout(self):
        """Test that _update_operation_status uses a timeout to prevent hanging."""
        worker = _WorkerForStatusTesting()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await worker._update_operation_status("op_123", "CANCELLED")

            # Verify timeout was set (should be 5.0 seconds as per plan)
            mock_client_class.assert_called_once()
            call_kwargs = mock_client_class.call_args[1]
            assert "timeout" in call_kwargs
            assert call_kwargs["timeout"] == 5.0

    @pytest.mark.asyncio
    async def test_update_status_handles_success(self):
        """Test that successful status update is logged."""
        worker = _WorkerForStatusTesting()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should complete without raising
            await worker._update_operation_status("op_123", "CANCELLED")

    @pytest.mark.asyncio
    async def test_update_status_handles_non_200_response(self):
        """Test that non-200 response logs warning but doesn't raise."""
        worker = _WorkerForStatusTesting()

        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should complete without raising (failure doesn't block shutdown)
            await worker._update_operation_status("op_123", "CANCELLED")

    @pytest.mark.asyncio
    async def test_update_status_handles_connection_error(self):
        """Test that connection errors don't block shutdown."""
        worker = _WorkerForStatusTesting()

        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should complete without raising (failure doesn't block shutdown)
            await worker._update_operation_status("op_123", "CANCELLED")

    @pytest.mark.asyncio
    async def test_update_status_handles_timeout_error(self):
        """Test that timeout errors don't block shutdown."""
        worker = _WorkerForStatusTesting()

        import httpx

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should complete without raising (failure doesn't block shutdown)
            await worker._update_operation_status("op_123", "CANCELLED")

    @pytest.mark.asyncio
    async def test_update_status_handles_generic_exception(self):
        """Test that generic exceptions don't block shutdown."""
        worker = _WorkerForStatusTesting()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(side_effect=Exception("Unexpected error"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            # Should complete without raising (failure doesn't block shutdown)
            await worker._update_operation_status("op_123", "CANCELLED")

    @pytest.mark.asyncio
    async def test_update_status_optional_error_message(self):
        """Test that error_message is optional."""
        worker = _WorkerForStatusTesting()

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.patch = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client

            await worker._update_operation_status("op_123", "CANCELLED")

            call_json = mock_client.patch.call_args[1]["json"]
            assert "status" in call_json
            # error_message can be None
            assert "error_message" in call_json
