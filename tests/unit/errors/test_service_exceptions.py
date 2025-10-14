"""
Tests for unified service exception hierarchy.

This module tests the custom exceptions for async service operations,
error context preservation across async boundaries, and integration
with the AsyncHostService base class.
"""

import asyncio

import pytest

from ktrdr.errors.exceptions import (
    ConfigurationError,
    ConnectionError,
    KtrdrError,
)


class TestServiceExceptions:
    """Tests for service-specific exception classes."""

    def test_service_connection_error_creation(self):
        """Test ServiceConnectionError can be created with proper attributes."""
        # This will fail initially since ServiceConnectionError doesn't exist yet
        from ktrdr.errors.exceptions import ServiceConnectionError

        error = ServiceConnectionError(
            message="Failed to connect to IB Host Service",
            error_code="SERVICE_CONNECTION_FAILED",
            details={
                "service": "ib-host",
                "endpoint": "http://localhost:8001",
                "timeout": 30,
            },
        )

        assert error.message == "Failed to connect to IB Host Service"
        assert error.error_code == "SERVICE_CONNECTION_FAILED"
        assert error.details["service"] == "ib-host"
        assert error.details["endpoint"] == "http://localhost:8001"
        assert error.details["timeout"] == 30
        assert isinstance(error, ConnectionError)
        assert isinstance(error, KtrdrError)

    def test_service_timeout_error_creation(self):
        """Test ServiceTimeoutError can be created with proper attributes."""
        from ktrdr.errors.exceptions import ServiceTimeoutError

        error = ServiceTimeoutError(
            message="Request to Training Host Service timed out after 45 seconds",
            error_code="SERVICE_TIMEOUT",
            details={
                "service": "training-host",
                "timeout_seconds": 45,
                "operation": "model_train",
            },
        )

        assert (
            error.message
            == "Request to Training Host Service timed out after 45 seconds"
        )
        assert error.error_code == "SERVICE_TIMEOUT"
        assert error.details["service"] == "training-host"
        assert error.details["timeout_seconds"] == 45
        assert error.details["operation"] == "model_train"
        assert isinstance(error, ConnectionError)
        assert isinstance(error, KtrdrError)

    def test_service_configuration_error_creation(self):
        """Test ServiceConfigurationError can be created with proper attributes."""
        from ktrdr.errors.exceptions import ServiceConfigurationError

        error = ServiceConfigurationError(
            message="Invalid service configuration: missing required URL",
            error_code="SERVICE_CONFIG_INVALID",
            details={
                "service": "ib-host",
                "missing_config": "IB_HOST_SERVICE_URL",
                "current_value": None,
            },
        )

        assert error.message == "Invalid service configuration: missing required URL"
        assert error.error_code == "SERVICE_CONFIG_INVALID"
        assert error.details["service"] == "ib-host"
        assert error.details["missing_config"] == "IB_HOST_SERVICE_URL"
        assert error.details["current_value"] is None
        assert isinstance(error, ConfigurationError)
        assert isinstance(error, KtrdrError)


class TestAsyncErrorContextPreservation:
    """Tests for error context preservation across async boundaries."""

    @pytest.mark.asyncio
    async def test_async_error_chain_preservation(self):
        """Test that error context is preserved when raising across async calls."""
        from ktrdr.errors.exceptions import ServiceConnectionError, ServiceTimeoutError

        async def inner_async_call():
            """Simulates an inner async service call that fails."""
            raise ServiceConnectionError(
                message="Connection refused by service",
                error_code="CONNECTION_REFUSED",
                details={"service": "ib-host", "port": 8001},
            )

        async def outer_async_call():
            """Simulates an outer async call that catches and re-raises."""
            try:
                await inner_async_call()
            except ServiceConnectionError as e:
                # Re-raise with additional context while preserving the chain
                raise ServiceTimeoutError(
                    message="Operation failed due to connection issues",
                    error_code="OPERATION_FAILED",
                    details={"operation": "data_load", "original_error": str(e)},
                ) from e

        # Test that the error chain is preserved
        with pytest.raises(ServiceTimeoutError) as exc_info:
            await outer_async_call()

        error = exc_info.value
        assert error.message == "Operation failed due to connection issues"
        assert error.error_code == "OPERATION_FAILED"
        assert error.details["operation"] == "data_load"

        # Verify the original exception is preserved in the chain
        assert error.__cause__ is not None
        assert isinstance(error.__cause__, ServiceConnectionError)
        assert error.__cause__.message == "Connection refused by service"
        assert error.__cause__.error_code == "CONNECTION_REFUSED"

    @pytest.mark.asyncio
    async def test_async_context_manager_error_handling(self):
        """Test error handling in async context managers."""
        from ktrdr.errors.exceptions import ServiceConnectionError

        class MockAsyncContextManager:
            """Mock async context manager that can raise service errors."""

            def __init__(self, should_fail=False):
                self.should_fail = should_fail

            async def __aenter__(self):
                if self.should_fail:
                    raise ServiceConnectionError(
                        message="Failed to establish service connection",
                        error_code="CONTEXT_CONNECTION_FAILED",
                        details={"context": "async_service_manager"},
                    )
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return False

        # Test successful context manager
        async with MockAsyncContextManager(should_fail=False) as manager:
            assert manager is not None

        # Test failing context manager
        with pytest.raises(ServiceConnectionError) as exc_info:
            async with MockAsyncContextManager(should_fail=True):
                pass

        error = exc_info.value
        assert error.error_code == "CONTEXT_CONNECTION_FAILED"
        assert error.details["context"] == "async_service_manager"

    @pytest.mark.asyncio
    async def test_asyncio_gather_error_propagation(self):
        """Test that service errors propagate correctly through asyncio.gather."""
        from ktrdr.errors.exceptions import ServiceConnectionError, ServiceTimeoutError

        async def successful_operation():
            """Simulates a successful async operation."""
            await asyncio.sleep(0.01)
            return "success"

        async def failing_connection():
            """Simulates a failing connection."""
            await asyncio.sleep(0.01)
            raise ServiceConnectionError(
                message="Service connection failed",
                error_code="GATHER_CONNECTION_FAILED",
            )

        async def failing_timeout():
            """Simulates a timeout."""
            await asyncio.sleep(0.01)
            raise ServiceTimeoutError(
                message="Service operation timed out", error_code="GATHER_TIMEOUT"
            )

        # Test that gather properly propagates the first error it encounters
        with pytest.raises((ServiceConnectionError, ServiceTimeoutError)):
            await asyncio.gather(
                successful_operation(),
                failing_connection(),
                failing_timeout(),
                return_exceptions=False,
            )

        # Test that gather can collect all exceptions when return_exceptions=True
        results = await asyncio.gather(
            successful_operation(),
            failing_connection(),
            failing_timeout(),
            return_exceptions=True,
        )

        assert results[0] == "success"
        assert isinstance(results[1], ServiceConnectionError)
        assert isinstance(results[2], ServiceTimeoutError)
        assert results[1].error_code == "GATHER_CONNECTION_FAILED"
        assert results[2].error_code == "GATHER_TIMEOUT"


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing error handling."""

    def test_service_exceptions_inherit_from_existing_hierarchy(self):
        """Test that new service exceptions properly inherit from existing classes."""
        from ktrdr.errors.exceptions import (
            ConfigurationError,
            ConnectionError,
            KtrdrError,
            ServiceConfigurationError,
            ServiceConnectionError,
            ServiceTimeoutError,
        )

        # Test inheritance hierarchy
        connection_error = ServiceConnectionError("test")
        timeout_error = ServiceTimeoutError("test")
        config_error = ServiceConfigurationError("test")

        # ServiceConnectionError and ServiceTimeoutError should inherit from ConnectionError
        assert isinstance(connection_error, ConnectionError)
        assert isinstance(connection_error, KtrdrError)
        assert isinstance(timeout_error, ConnectionError)
        assert isinstance(timeout_error, KtrdrError)

        # ServiceConfigurationError should inherit from ConfigurationError
        assert isinstance(config_error, ConfigurationError)
        assert isinstance(config_error, KtrdrError)

    def test_existing_error_handling_still_works(self):
        """Test that existing error catching patterns still work with new exceptions."""
        from ktrdr.errors.exceptions import (
            ConnectionError,
            ServiceConnectionError,
            ServiceTimeoutError,
        )

        def old_error_handler(func):
            """Simulates existing error handling code that catches ConnectionError."""
            try:
                func()
            except ConnectionError as e:
                return f"Caught connection error: {e.message}"
            except Exception as e:
                return f"Caught general error: {str(e)}"

        def raise_service_connection_error():
            raise ServiceConnectionError("Service unavailable", error_code="TEST")

        def raise_service_timeout_error():
            raise ServiceTimeoutError("Service timeout", error_code="TEST")

        # Old error handlers should catch new service exceptions
        result1 = old_error_handler(raise_service_connection_error)
        result2 = old_error_handler(raise_service_timeout_error)

        assert "Caught connection error: Service unavailable" == result1
        assert "Caught connection error: Service timeout" == result2

    def test_error_attribute_consistency(self):
        """Test that all service exceptions have consistent attributes."""
        from ktrdr.errors.exceptions import (
            ServiceConfigurationError,
            ServiceConnectionError,
            ServiceTimeoutError,
        )

        exceptions = [
            ServiceConnectionError(
                "test", error_code="TEST1", details={"key": "value"}
            ),
            ServiceTimeoutError("test", error_code="TEST2", details={"key": "value"}),
            ServiceConfigurationError(
                "test", error_code="TEST3", details={"key": "value"}
            ),
        ]

        for exception in exceptions:
            # All should have the standard KtrdrError attributes
            assert hasattr(exception, "message")
            assert hasattr(exception, "error_code")
            assert hasattr(exception, "details")
            assert exception.message == "test"
            assert exception.error_code in ["TEST1", "TEST2", "TEST3"]
            assert exception.details == {"key": "value"}

            # Only ServiceConfigurationError (subclass of ConfigurationError) includes
            # error_code in string representation due to enhanced ConfigurationError.__str__
            if isinstance(exception, ServiceConfigurationError):
                assert str(exception) == f"[{exception.error_code}] test"
            else:
                # ConnectionError subclasses use default __str__
                assert str(exception) == "test"


class TestServiceExceptionUsagePatterns:
    """Tests for common usage patterns with service exceptions."""

    def test_http_client_error_mapping(self):
        """Test mapping HTTP client errors to service exceptions."""
        import aiohttp

        from ktrdr.errors.exceptions import ServiceConnectionError, ServiceTimeoutError

        def map_http_error_to_service_error(http_error: Exception, service_name: str):
            """Helper function to map HTTP errors to service errors."""
            if isinstance(http_error, aiohttp.ServerTimeoutError):
                # Check ServerTimeoutError first since it inherits from ClientConnectionError
                return ServiceTimeoutError(
                    message=f"Request to {service_name} service timed out",
                    error_code="HTTP_TIMEOUT_ERROR",
                    details={
                        "service": service_name,
                        "original_error": str(http_error),
                    },
                )
            elif isinstance(http_error, aiohttp.ClientConnectionError):
                return ServiceConnectionError(
                    message=f"Failed to connect to {service_name} service",
                    error_code="HTTP_CONNECTION_ERROR",
                    details={
                        "service": service_name,
                        "original_error": str(http_error),
                    },
                )
            else:
                return ServiceConnectionError(
                    message=f"HTTP error communicating with {service_name} service",
                    error_code="HTTP_GENERAL_ERROR",
                    details={
                        "service": service_name,
                        "original_error": str(http_error),
                    },
                )

        # Test connection error mapping
        connection_err = aiohttp.ClientConnectionError("Connection refused")
        mapped_err = map_http_error_to_service_error(connection_err, "ib-host")

        assert isinstance(mapped_err, ServiceConnectionError)
        assert mapped_err.error_code == "HTTP_CONNECTION_ERROR"
        assert mapped_err.details["service"] == "ib-host"

        # Test timeout error mapping
        timeout_err = aiohttp.ServerTimeoutError("Server timeout")
        mapped_timeout = map_http_error_to_service_error(timeout_err, "training-host")

        assert isinstance(mapped_timeout, ServiceTimeoutError)
        assert mapped_timeout.error_code == "HTTP_TIMEOUT_ERROR"
        assert mapped_timeout.details["service"] == "training-host"

    @pytest.mark.asyncio
    async def test_service_health_check_error_patterns(self):
        """Test the health check error patterns."""
        from ktrdr.errors.exceptions import ServiceConnectionError, ServiceTimeoutError

        async def simulate_health_check(service_name: str, should_fail: str = None):
            """Simulate a service health check with various failure modes."""
            await asyncio.sleep(0.01)  # Simulate network delay

            if should_fail == "connection":
                raise ServiceConnectionError(
                    message=f"{service_name} service is unreachable",
                    error_code="HEALTH_CHECK_CONNECTION_FAILED",
                    details={
                        "service": service_name,
                        "check_type": "health",
                        "endpoint": "http://localhost:8001/health",
                    },
                )
            elif should_fail == "timeout":
                raise ServiceTimeoutError(
                    message=f"{service_name} service health check timed out",
                    error_code="HEALTH_CHECK_TIMEOUT",
                    details={
                        "service": service_name,
                        "check_type": "health",
                        "timeout_seconds": 30,
                    },
                )

            return {"status": "healthy", "service": service_name}

        # Test successful health check
        result = await simulate_health_check("ib-host")
        assert result["status"] == "healthy"
        assert result["service"] == "ib-host"

        # Test connection failure
        with pytest.raises(ServiceConnectionError) as exc_info:
            await simulate_health_check("ib-host", should_fail="connection")

        assert exc_info.value.error_code == "HEALTH_CHECK_CONNECTION_FAILED"
        assert exc_info.value.details["service"] == "ib-host"
        assert exc_info.value.details["check_type"] == "health"

        # Test timeout failure
        with pytest.raises(ServiceTimeoutError) as exc_info:
            await simulate_health_check("training-host", should_fail="timeout")

        assert exc_info.value.error_code == "HEALTH_CHECK_TIMEOUT"
        assert exc_info.value.details["service"] == "training-host"
        assert exc_info.value.details["timeout_seconds"] == 30
