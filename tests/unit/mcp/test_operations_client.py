"""Unit tests for OperationsAPIClient"""

from unittest.mock import AsyncMock, Mock

import pytest
from clients.operations_client import OperationsAPIClient


@pytest.mark.asyncio
class TestOperationsAPIClient:
    """Test OperationsAPIClient functionality"""

    @pytest.mark.asyncio
    async def test_list_operations_no_filters(self):
        """Test list_operations with no filters"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": [],
                "total_count": 0,
                "active_count": 0,
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.list_operations()

            assert result["success"] is True
            client.client.request.assert_called_once_with(
                "GET", "/operations", params={"limit": 10, "offset": 0}
            )

    @pytest.mark.asyncio
    async def test_list_operations_with_filters(self):
        """Test list_operations with all filters"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": [{"operation_id": "op_1"}],
                "total_count": 1,
                "active_count": 1,
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.list_operations(
                operation_type="training",
                status="running",
                active_only=True,
                limit=5,
                offset=10,
            )

            assert result["success"] is True
            assert len(result["data"]) == 1
            client.client.request.assert_called_once_with(
                "GET",
                "/operations",
                params={
                    "limit": 5,
                    "offset": 10,
                    "operation_type": "training",
                    "status": "running",
                    "active_only": True,
                },
            )

    @pytest.mark.asyncio
    async def test_get_operation_status(self):
        """Test get_operation_status"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": {"operation_id": "op_123", "status": "running"},
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.get_operation_status("op_123")

            assert result["success"] is True
            assert result["data"]["status"] == "running"
            client.client.request.assert_called_once_with("GET", "/operations/op_123")

    @pytest.mark.asyncio
    async def test_cancel_operation_with_reason(self):
        """Test cancel_operation with reason"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": {"status": "cancelled"},
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.cancel_operation("op_123", "User requested")

            assert result["success"] is True
            client.client.request.assert_called_once_with(
                "DELETE",
                "/operations/op_123",
                json={"reason": "User requested"},
            )

    @pytest.mark.asyncio
    async def test_cancel_operation_without_reason(self):
        """Test cancel_operation without reason"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "data": {"status": "cancelled"},
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.cancel_operation("op_123")

            assert result["success"] is True
            client.client.request.assert_called_once_with(
                "DELETE", "/operations/op_123", json=None
            )

    @pytest.mark.asyncio
    async def test_get_operation_results(self):
        """Test get_operation_results"""
        async with OperationsAPIClient("http://localhost:8000", 30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "results": {"bars_loaded": 1000},
            }

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client.get_operation_results("op_123")

            assert result["success"] is True
            assert result["results"]["bars_loaded"] == 1000
            client.client.request.assert_called_once_with(
                "GET", "/operations/op_123/results"
            )
