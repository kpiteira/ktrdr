"""
Tests for AsyncHostService error handling integration.

This module tests how the new service exceptions integrate with
the future AsyncHostService base class. These tests serve as a
contract/specification for the AsyncHostService implementation.
"""

import asyncio
from unittest.mock import patch

import pytest

from ktrdr.errors.exceptions import (
    ServiceConfigurationError,
    ServiceConnectionError,
    ServiceTimeoutError,
)


class TestAsyncHostServiceErrorIntegration:
    """Tests for AsyncHostService error handling integration."""

    def test_mock_async_host_service_error_handling(self):
        """Test error handling patterns that AsyncHostService should implement."""

        # This is a mock implementation showing how AsyncHostService should handle errors
        class MockAsyncHostService:
            """Mock AsyncHostService to test error handling integration."""

            def __init__(self, service_name: str, base_url: str, timeout: float = 30.0):
                self.service_name = service_name
                self.base_url = base_url
                self.timeout = timeout
                self._session = None

            async def _call_host_service_post(self, endpoint: str, data: dict):
                """Mock implementation of HTTP POST with error handling."""
                # This should be implemented by AsyncHostService to convert HTTP errors
                # to service-specific exceptions using our new error hierarchy

                if endpoint == "/fail/connection":
                    raise ServiceConnectionError(
                        message=f"Failed to connect to {self.service_name} service",
                        error_code="SERVICE_CONNECTION_FAILED",
                        details={
                            "service": self.service_name,
                            "endpoint": f"{self.base_url}{endpoint}",
                            "timeout": self.timeout,
                        },
                    )
                elif endpoint == "/fail/timeout":
                    raise ServiceTimeoutError(
                        message=f"Request to {self.service_name} service timed out",
                        error_code="SERVICE_TIMEOUT",
                        details={
                            "service": self.service_name,
                            "endpoint": f"{self.base_url}{endpoint}",
                            "timeout_seconds": self.timeout,
                        },
                    )
                elif endpoint == "/fail/config":
                    raise ServiceConfigurationError(
                        message=f"Invalid configuration for {self.service_name} service",
                        error_code="SERVICE_CONFIG_INVALID",
                        details={
                            "service": self.service_name,
                            "config_issue": "missing_auth_token",
                        },
                    )
                else:
                    # Successful response
                    return {"status": "success", "data": data}

            async def health_check(self):
                """Mock health check that uses the error handling."""
                try:
                    result = await self._call_host_service_post("/health", {})
                    return result["status"] == "success"
                except (
                    ServiceConnectionError,
                    ServiceTimeoutError,
                    ServiceConfigurationError,
                ):
                    return False

        # Test successful operation
        service = MockAsyncHostService("test-service", "http://localhost:8001")

        # Since we can't run async tests directly in this non-async method,
        # we'll use asyncio.run to test the async behavior
        async def test_success():
            result = await service._call_host_service_post("/success", {"test": "data"})
            assert result["status"] == "success"
            assert result["data"]["test"] == "data"

        asyncio.run(test_success())

        # Test connection error
        async def test_connection_error():
            with pytest.raises(ServiceConnectionError) as exc_info:
                await service._call_host_service_post("/fail/connection", {})

            error = exc_info.value
            assert error.error_code == "SERVICE_CONNECTION_FAILED"
            assert error.details["service"] == "test-service"
            assert error.details["timeout"] == 30.0

        asyncio.run(test_connection_error())

        # Test timeout error
        async def test_timeout_error():
            with pytest.raises(ServiceTimeoutError) as exc_info:
                await service._call_host_service_post("/fail/timeout", {})

            error = exc_info.value
            assert error.error_code == "SERVICE_TIMEOUT"
            assert error.details["service"] == "test-service"
            assert error.details["timeout_seconds"] == 30.0

        asyncio.run(test_timeout_error())

        # Test configuration error
        async def test_config_error():
            with pytest.raises(ServiceConfigurationError) as exc_info:
                await service._call_host_service_post("/fail/config", {})

            error = exc_info.value
            assert error.error_code == "SERVICE_CONFIG_INVALID"
            assert error.details["service"] == "test-service"
            assert error.details["config_issue"] == "missing_auth_token"

        asyncio.run(test_config_error())

        # Test health check error handling
        async def test_health_check():
            # Health check should return False when services fail, not raise exceptions
            healthy_service = MockAsyncHostService("healthy", "http://localhost:8001")
            assert await healthy_service.health_check() is True

            # Create a service that will fail connection
            failing_service = MockAsyncHostService("failing", "http://localhost:8001")
            with patch.object(failing_service, "_call_host_service_post") as mock_post:
                mock_post.side_effect = ServiceConnectionError(
                    "Connection failed", "CONN_FAIL"
                )
                assert await failing_service.health_check() is False

        asyncio.run(test_health_check())

    @pytest.mark.asyncio
    async def test_async_host_service_error_context_preservation(self):
        """Test that AsyncHostService preserves error context across operations."""

        class MockAsyncHostServiceWithContext:
            """Mock AsyncHostService that demonstrates proper error context handling."""

            def __init__(self, service_name: str):
                self.service_name = service_name

            async def _call_host_service_post(self, endpoint: str, data: dict):
                """Mock HTTP call that raises connection error."""
                raise ServiceConnectionError(
                    message=f"Connection to {self.service_name} failed",
                    error_code="CONNECTION_FAILED",
                    details={"service": self.service_name, "endpoint": endpoint},
                )

            async def load_data(self, symbol: str):
                """High-level operation that should preserve error context."""
                try:
                    result = await self._call_host_service_post(
                        "/data/load", {"symbol": symbol}
                    )
                    return result
                except ServiceConnectionError as e:
                    # Re-raise with additional context while preserving the chain
                    raise ServiceConnectionError(
                        message=f"Failed to load data for {symbol}",
                        error_code="DATA_LOAD_FAILED",
                        details={"symbol": symbol, "operation": "load_data"},
                    ) from e

        service = MockAsyncHostServiceWithContext("ib-host")

        # Test that error context is preserved through the chain
        with pytest.raises(ServiceConnectionError) as exc_info:
            await service.load_data("AAPL")

        error = exc_info.value
        assert error.message == "Failed to load data for AAPL"
        assert error.error_code == "DATA_LOAD_FAILED"
        assert error.details["symbol"] == "AAPL"
        assert error.details["operation"] == "load_data"

        # Verify the original error is preserved in the chain
        original_error = error.__cause__
        assert original_error is not None
        assert isinstance(original_error, ServiceConnectionError)
        assert original_error.message == "Connection to ib-host failed"
        assert original_error.error_code == "CONNECTION_FAILED"
        assert original_error.details["service"] == "ib-host"

    @pytest.mark.asyncio
    async def test_async_host_service_retry_logic_with_errors(self):
        """Test how AsyncHostService should handle retries with service exceptions."""

        class MockAsyncHostServiceWithRetry:
            """Mock AsyncHostService that demonstrates retry logic with proper error handling."""

            def __init__(self, service_name: str, max_retries: int = 3):
                self.service_name = service_name
                self.max_retries = max_retries
                self._attempt_count = 0

            async def _call_host_service_post(self, endpoint: str, data: dict):
                """Mock HTTP call that fails first few attempts then succeeds."""
                self._attempt_count += 1

                if self._attempt_count <= 2:
                    # Fail first two attempts
                    raise ServiceConnectionError(
                        message=f"Connection to {self.service_name} failed (attempt {self._attempt_count})",
                        error_code="CONNECTION_FAILED",
                        details={
                            "service": self.service_name,
                            "attempt": self._attempt_count,
                        },
                    )
                else:
                    # Succeed on third attempt
                    return {"status": "success", "attempt": self._attempt_count}

            async def call_with_retry(self, endpoint: str, data: dict):
                """High-level method that implements retry logic."""
                last_error = None

                for attempt in range(1, self.max_retries + 1):
                    try:
                        return await self._call_host_service_post(endpoint, data)
                    except ServiceConnectionError as e:
                        last_error = e
                        if attempt < self.max_retries:
                            # Log and continue retrying
                            await asyncio.sleep(0.1)  # Small delay between retries
                            continue
                        else:
                            # Max retries exceeded, raise with additional context
                            raise ServiceConnectionError(
                                message=f"Max retries ({self.max_retries}) exceeded for {self.service_name}",
                                error_code="MAX_RETRIES_EXCEEDED",
                                details={
                                    "service": self.service_name,
                                    "max_retries": self.max_retries,
                                    "last_attempt": attempt,
                                },
                            ) from last_error

        # Test successful retry
        service = MockAsyncHostServiceWithRetry("test-service", max_retries=3)
        result = await service.call_with_retry("/test", {"data": "test"})

        assert result["status"] == "success"
        assert result["attempt"] == 3  # Should succeed on third attempt

        # Test max retries exceeded
        failing_service = MockAsyncHostServiceWithRetry(
            "failing-service", max_retries=2
        )

        with pytest.raises(ServiceConnectionError) as exc_info:
            await failing_service.call_with_retry("/test", {"data": "test"})

        error = exc_info.value
        assert error.error_code == "MAX_RETRIES_EXCEEDED"
        assert error.details["max_retries"] == 2
        assert error.details["last_attempt"] == 2

        # Verify the original error is preserved
        original_error = error.__cause__
        assert original_error is not None
        assert original_error.error_code == "CONNECTION_FAILED"
