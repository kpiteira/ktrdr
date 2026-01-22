"""Unit tests for BaseAPIClient"""

from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from clients.base import BaseAPIClient, KTRDRAPIError


class TestBaseAPIClient:
    """Test BaseAPIClient functionality"""

    def test_init(self):
        """Test client initialization"""
        client = BaseAPIClient("http://localhost:8000", timeout=30.0)
        assert client.base_url == "http://localhost:8000"
        assert client.timeout == 30.0
        assert client.client is None

    def test_init_strips_trailing_slash(self):
        """Test client strips trailing slash from base_url"""
        client = BaseAPIClient("http://localhost:8000/", timeout=30.0)
        assert client.base_url == "http://localhost:8000"

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self):
        """Test async context manager initializes and cleans up client"""
        client = BaseAPIClient("http://localhost:8000", timeout=30.0)

        # Before entering context, client should be None
        assert client.client is None

        async with client:
            # Inside context, client should be initialized
            assert client.client is not None
            assert isinstance(client.client, httpx.AsyncClient)
            assert client.client.base_url == "http://localhost:8000"

        # After exiting context, client should be closed
        # Note: We can't directly check if it's closed, but we can verify it was called

    @pytest.mark.asyncio
    async def test_request_without_context_manager(self):
        """Test _request raises error if called without context manager"""
        client = BaseAPIClient("http://localhost:8000", timeout=30.0)

        with pytest.raises(KTRDRAPIError, match="API client not initialized"):
            await client._request("GET", "/test")

    @pytest.mark.asyncio
    async def test_request_successful_get(self):
        """Test successful GET request"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            # Mock the httpx client
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "data": "test"}

            client.client.request = AsyncMock(return_value=mock_response)

            result = await client._request("GET", "/api/v1/test")

            assert result == {"success": True, "data": "test"}
            client.client.request.assert_called_once_with("GET", "/api/v1/test")

    @pytest.mark.asyncio
    async def test_request_successful_post_with_json(self):
        """Test successful POST request with JSON payload"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"success": True, "id": "123"}

            client.client.request = AsyncMock(return_value=mock_response)

            payload = {"key": "value"}
            result = await client._request("POST", "/api/v1/create", json=payload)

            assert result == {"success": True, "id": "123"}
            client.client.request.assert_called_once_with(
                "POST", "/api/v1/create", json=payload
            )

    @pytest.mark.asyncio
    async def test_request_with_query_params(self):
        """Test request with query parameters"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"results": []}

            client.client.request = AsyncMock(return_value=mock_response)

            params = {"limit": 10, "offset": 0}
            result = await client._request("GET", "/api/v1/items", params=params)

            assert result == {"results": []}
            client.client.request.assert_called_once_with(
                "GET", "/api/v1/items", params=params
            )

    @pytest.mark.asyncio
    async def test_request_adds_leading_slash(self):
        """Test _request adds leading slash if missing"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}

            client.client.request = AsyncMock(return_value=mock_response)

            await client._request("GET", "api/v1/test")

            # Should have added leading slash
            client.client.request.assert_called_once_with("GET", "/api/v1/test")

    @pytest.mark.asyncio
    async def test_request_preserves_leading_slash(self):
        """Test _request preserves leading slash if present"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.json.return_value = {}

            client.client.request = AsyncMock(return_value=mock_response)

            await client._request("GET", "/api/v1/test")

            client.client.request.assert_called_once_with("GET", "/api/v1/test")

    @pytest.mark.asyncio
    async def test_request_http_404_error(self):
        """Test HTTP 404 error handling"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            # Create mock 404 response
            mock_response = Mock()
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_response.json.return_value = {"detail": "Resource not found"}

            # Create HTTPStatusError
            http_error = httpx.HTTPStatusError(
                "404 Not Found", request=Mock(), response=mock_response
            )

            client.client.request = AsyncMock(side_effect=http_error)

            with pytest.raises(KTRDRAPIError) as exc_info:
                await client._request("GET", "/api/v1/missing")

            assert exc_info.value.status_code == 404
            assert "Resource not found" in exc_info.value.message
            assert exc_info.value.details == {"detail": "Resource not found"}

    @pytest.mark.asyncio
    async def test_request_http_500_error(self):
        """Test HTTP 500 error handling"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 500
            mock_response.text = "Internal Server Error"
            mock_response.json.return_value = {"detail": "Database connection failed"}

            http_error = httpx.HTTPStatusError(
                "500 Internal Server Error", request=Mock(), response=mock_response
            )

            client.client.request = AsyncMock(side_effect=http_error)

            with pytest.raises(KTRDRAPIError) as exc_info:
                await client._request("GET", "/api/v1/test")

            assert exc_info.value.status_code == 500
            assert "Database connection failed" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_request_http_error_without_json_response(self):
        """Test HTTP error when response is not JSON"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            mock_response = Mock()
            mock_response.status_code = 503
            mock_response.text = "Service Unavailable"
            mock_response.json.side_effect = Exception("Not JSON")

            http_error = httpx.HTTPStatusError(
                "503 Service Unavailable", request=Mock(), response=mock_response
            )

            client.client.request = AsyncMock(side_effect=http_error)

            with pytest.raises(KTRDRAPIError) as exc_info:
                await client._request("GET", "/api/v1/test")

            assert exc_info.value.status_code == 503
            assert exc_info.value.details == {"detail": "Service Unavailable"}

    @pytest.mark.asyncio
    async def test_request_network_error(self):
        """Test network/connection error handling"""
        async with BaseAPIClient("http://localhost:8000", timeout=30.0) as client:
            request_error = httpx.RequestError("Connection timeout")

            client.client.request = AsyncMock(side_effect=request_error)

            with pytest.raises(KTRDRAPIError) as exc_info:
                await client._request("GET", "/api/v1/test")

            assert "Request failed" in exc_info.value.message
            assert "Connection timeout" in exc_info.value.message
            assert exc_info.value.status_code is None


class TestExtractList:
    """Test _extract_list() method"""

    def test_extract_list_with_data_field(self):
        """Should extract list from 'data' field"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": [{"id": 1}, {"id": 2}]}

        result = client._extract_list(response)

        assert result == [{"id": 1}, {"id": 2}]

    def test_extract_list_missing_field_returns_empty(self):
        """Should return empty list when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_list(response)

        assert result == []

    def test_extract_list_custom_field(self):
        """Should extract from custom field name"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "models": [{"name": "model1"}]}

        result = client._extract_list(response, field="models")

        assert result == [{"name": "model1"}]

    def test_extract_list_custom_default(self):
        """Should use custom default when provided"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_list(response, default=[{"default": True}])

        assert result == [{"default": True}]


class TestExtractDict:
    """Test _extract_dict() method"""

    def test_extract_dict_with_data_field(self):
        """Should extract dict from 'data' field"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": {"key": "value"}}

        result = client._extract_dict(response)

        assert result == {"key": "value"}

    def test_extract_dict_missing_field_returns_empty(self):
        """Should return empty dict when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_dict(response)

        assert result == {}

    def test_extract_dict_custom_field(self):
        """Should extract from custom field name"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "result": {"status": "ok"}}

        result = client._extract_dict(response, field="result")

        assert result == {"status": "ok"}


class TestExtractOrRaise:
    """Test _extract_or_raise() method"""

    def test_extract_or_raise_success(self):
        """Should extract field when present and success=True"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": {"operation_id": "op_123"}}

        result = client._extract_or_raise(response, field="data")

        assert result == {"operation_id": "op_123"}

    def test_extract_or_raise_explicit_error_flag(self):
        """Should raise when success=False"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": False, "error": "Not found"}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(response, operation="training start")

        assert "Training start failed: Not found" in str(exc_info.value)

    def test_extract_or_raise_missing_field(self):
        """Should raise when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(
                response, field="operation_id", operation="data loading"
            )

        assert "Data loading response missing 'operation_id' field" in str(
            exc_info.value
        )

    def test_extract_or_raise_custom_operation_name(self):
        """Should use operation name in error messages"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": False, "error": "Timeout"}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(response, operation="model training")

        assert "Model training failed: Timeout" in str(exc_info.value)


class TestKTRDRAPIError:
    """Test KTRDRAPIError exception class"""

    def test_error_with_message_only(self):
        """Test error with just message"""
        error = KTRDRAPIError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.status_code is None
        assert error.details == {}
        assert str(error) == "Something went wrong"

    def test_error_with_all_fields(self):
        """Test error with all fields"""
        details = {"field": "value", "trace_id": "abc123"}
        error = KTRDRAPIError("API Error", status_code=400, details=details)
        assert error.message == "API Error"
        assert error.status_code == 400
        assert error.details == details

    def test_error_defaults_empty_details(self):
        """Test error defaults to empty dict for details"""
        error = KTRDRAPIError("Error", status_code=500, details=None)
        assert error.details == {}
