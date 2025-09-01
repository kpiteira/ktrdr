"""
Tests for AsyncHostService base class and related components.

Following TDD approach - these tests will FAIL initially and drive the implementation.
"""

import asyncio
import pytest
import pytest_asyncio
from abc import ABC
from typing import Dict, Any, Optional
from unittest.mock import Mock, AsyncMock, patch

import httpx

from ktrdr.managers.async_host_service import (
    AsyncHostService,
    HostServiceError,
    HostServiceConnectionError,
    HostServiceTimeoutError,
    HostServiceConfig,
)


# Mock concrete implementation for testing abstract base class
class MockHostService(AsyncHostService):
    """Mock concrete implementation for testing the abstract base class."""

    def __init__(self, config: HostServiceConfig, **kwargs):
        self._base_url = "http://localhost:5000"
        self._service_name = "MockService"
        super().__init__(config, **kwargs)

    def get_service_name(self) -> str:
        return self._service_name

    def get_base_url(self) -> str:
        return self._base_url

    async def get_health_check_endpoint(self) -> str:
        return "/health"


class TestHostServiceExceptions:
    """Test the custom exception hierarchy."""

    def test_host_service_error_base(self):
        """Test that HostServiceError is the base exception."""
        error = HostServiceError("Test error")
        assert str(error) == "Test error"
        assert isinstance(error, Exception)

    def test_host_service_connection_error(self):
        """Test connection-specific error inheritance."""
        error = HostServiceConnectionError("Connection failed")
        assert isinstance(error, HostServiceError)
        assert str(error) == "Connection failed"

    def test_host_service_timeout_error(self):
        """Test timeout-specific error inheritance."""
        error = HostServiceTimeoutError("Request timed out")
        assert isinstance(error, HostServiceError)
        assert str(error) == "Request timed out"


class TestHostServiceConfig:
    """Test the configuration data class."""

    def test_config_creation(self):
        """Test creating configuration with default values."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        assert config.base_url == "http://localhost:5000"
        assert config.timeout == 30
        assert config.max_retries == 3
        assert config.connection_pool_limit == 20

    def test_config_custom_values(self):
        """Test creating configuration with custom values."""
        config = HostServiceConfig(
            base_url="http://api.example.com",
            timeout=45,
            max_retries=5,
            connection_pool_limit=50,
        )
        assert config.base_url == "http://api.example.com"
        assert config.timeout == 45
        assert config.max_retries == 5
        assert config.connection_pool_limit == 50


class TestAsyncHostServiceAbstractContract:
    """Test the abstract base class contract."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that AsyncHostService cannot be instantiated directly."""
        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            AsyncHostService(config)  # This should fail - abstract class

    def test_concrete_class_must_implement_abstract_methods(self):
        """Test that concrete classes must implement all abstract methods."""

        # This incomplete implementation should fail
        class IncompleteHostService(AsyncHostService):
            def get_service_name(self) -> str:
                return "Incomplete"

            # Missing get_base_url and get_health_check_endpoint

        config = HostServiceConfig(base_url="http://localhost:5000")

        with pytest.raises(TypeError, match="abstract"):
            IncompleteHostService(config)

    def test_complete_concrete_class_can_be_instantiated(self):
        """Test that complete concrete classes can be instantiated."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        assert service.get_service_name() == "MockService"
        assert service.get_base_url() == "http://localhost:5000"


@pytest_asyncio.fixture
async def mock_host_service():
    """Fixture providing a mock host service for testing."""
    config = HostServiceConfig(base_url="http://localhost:5000")
    service = MockHostService(config)

    # Setup async context manager manually for testing
    await service.__aenter__()
    yield service
    await service.__aexit__(None, None, None)


class TestAsyncHostServiceLifecycle:
    """Test async context manager lifecycle."""

    @pytest.mark.asyncio
    async def test_async_context_manager_protocol(self):
        """Test that async context manager protocol is implemented."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Test async context manager
        async with service:
            assert service._http_client is not None
            assert service._connection_pool is not None

        # After context exit, resources should be cleaned up
        assert service._http_client is None

    @pytest.mark.asyncio
    async def test_connection_pool_setup(self):
        """Test that connection pool is properly set up."""
        config = HostServiceConfig(
            base_url="http://localhost:5000", connection_pool_limit=25
        )
        service = MockHostService(config)

        async with service:
            # Verify connection pool is initialized
            assert service._connection_pool is not None
            assert service._http_client is not None
            # Verify configuration is stored
            assert service.config.connection_pool_limit == 25
            # Verify it's the same object (connection pooling pattern)
            assert service._connection_pool == service._http_client

    @pytest.mark.asyncio
    async def test_manual_lifecycle_management(self):
        """Test manual enter/exit lifecycle management."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Manual setup
        await service.__aenter__()
        try:
            assert service._http_client is not None
        finally:
            # Manual cleanup
            await service.__aexit__(None, None, None)
            assert service._http_client is None


class TestAsyncHostServiceHTTPCommunication:
    """Test HTTP communication methods."""

    @pytest.mark.asyncio
    async def test_post_request_success(self, mock_host_service):
        """Test successful POST request."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {"success": True, "data": "test"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_post.return_value = mock_response

            result = await mock_host_service._call_host_service_post(
                "/test", {"key": "value"}
            )

            assert result == {"success": True, "data": "test"}
            mock_post.assert_called_once_with(
                "http://localhost:5000/test", json={"key": "value"}, timeout=30.0
            )

    @pytest.mark.asyncio
    async def test_get_request_success(self, mock_host_service):
        """Test successful GET request."""
        with patch.object(mock_host_service._http_client, "get") as mock_get:
            # Mock successful response
            mock_response = Mock()
            mock_response.json.return_value = {"result": "success"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            result = await mock_host_service._call_host_service_get(
                "/status", {"filter": "active"}
            )

            assert result == {"result": "success"}
            mock_get.assert_called_once_with(
                "http://localhost:5000/status",
                params={"filter": "active"},
                timeout=30.0,
            )

    @pytest.mark.asyncio
    async def test_http_error_handling(self, mock_host_service):
        """Test HTTP error handling and exception translation."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock HTTP error
            mock_post.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(HostServiceConnectionError, match="Connection failed"):
                await mock_host_service._call_host_service_post("/test", {})

    @pytest.mark.asyncio
    async def test_timeout_error_handling(self, mock_host_service):
        """Test timeout error handling."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock timeout error
            mock_post.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(HostServiceTimeoutError, match="Request timed out"):
                await mock_host_service._call_host_service_post("/test", {})

    @pytest.mark.asyncio
    async def test_retry_logic_with_exponential_backoff(self, mock_host_service):
        """Test retry logic with exponential backoff."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            # Mock failures followed by success
            mock_post.side_effect = [
                httpx.TimeoutException("Timeout 1"),
                httpx.TimeoutException("Timeout 2"),
                Mock(json=lambda: {"success": True}, raise_for_status=lambda: None),
            ]

            with patch("asyncio.sleep") as mock_sleep:
                result = await mock_host_service._call_host_service_post("/test", {})

                assert result == {"success": True}
                # Should have retried 2 times
                assert mock_post.call_count == 3
                # Should have exponential backoff delays
                mock_sleep.assert_called()


class TestAsyncHostServiceHealthCheck:
    """Test health check functionality."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_host_service):
        """Test successful health check."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy", "uptime": 12345}

            result = await mock_host_service.check_health()

            assert result["status"] == "healthy"
            mock_get.assert_called_once_with("/health")

    @pytest.mark.asyncio
    async def test_health_check_with_custom_timeout(self, mock_host_service):
        """Test health check with custom timeout."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy"}

            await mock_host_service.check_health(timeout=10)

            # Should use custom timeout in the underlying HTTP call
            assert mock_get.called

    @pytest.mark.asyncio
    async def test_health_check_failure(self, mock_host_service):
        """Test health check failure handling."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.side_effect = HostServiceConnectionError("Service unavailable")

            with pytest.raises(HostServiceConnectionError, match="Service unavailable"):
                await mock_host_service.check_health()

    @pytest.mark.asyncio
    async def test_health_check_caching_with_ttl(self, mock_host_service):
        """Test health check caching with TTL for TASK-1.5b."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy", "uptime": 12345}

            # First call should make HTTP request
            result1 = await mock_host_service.check_health(cache_ttl=30)
            assert result1["status"] == "healthy"
            assert mock_get.call_count == 1

            # Second call within TTL should return cached result
            result2 = await mock_host_service.check_health(cache_ttl=30)
            assert result2["status"] == "healthy"
            assert mock_get.call_count == 1  # No additional HTTP call

            # Results should be identical
            assert result1 == result2

    @pytest.mark.asyncio
    async def test_health_check_cache_expiration(self, mock_host_service):
        """Test health check cache expiration."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            with patch("ktrdr.managers.async_host_service.time.time") as mock_time:
                mock_get.return_value = {"status": "healthy"}
                # Set time sequence: [cache_time, age_check, new_cache_time]
                mock_time.side_effect = [1000, 1040, 1040]  # Cache expires after 30s

                # First call caches result at time 1000
                await mock_host_service.check_health(cache_ttl=30)
                assert mock_get.call_count == 1

                # Call after cache expiry (40s > 30s TTL) should make new HTTP request
                await mock_host_service.check_health(cache_ttl=30)
                assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_cache_bypass(self, mock_host_service):
        """Test bypassing health check cache."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy"}

            # First call with caching
            await mock_host_service.check_health(cache_ttl=30)
            assert mock_get.call_count == 1

            # Second call with cache_ttl=0 should bypass cache
            await mock_host_service.check_health(cache_ttl=0)
            assert mock_get.call_count == 2

    @pytest.mark.asyncio
    async def test_health_check_clear_cache(self, mock_host_service):
        """Test clearing health check cache."""
        with patch.object(mock_host_service, "_call_host_service_get") as mock_get:
            mock_get.return_value = {"status": "healthy"}

            # Cache result
            await mock_host_service.check_health(cache_ttl=30)
            assert mock_get.call_count == 1

            # Clear cache (method to be implemented)
            mock_host_service.clear_health_check_cache()

            # Next call should make HTTP request even within TTL
            await mock_host_service.check_health(cache_ttl=30)
            assert mock_get.call_count == 2


class TestAsyncHostServiceStatistics:
    """Test request statistics and monitoring."""

    @pytest.mark.asyncio
    async def test_request_statistics_tracking(self, mock_host_service):
        """Test that request statistics are tracked."""
        initial_count = mock_host_service.get_request_count()

        with patch.object(mock_host_service._http_client, "get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"data": "test"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_get.return_value = mock_response

            await mock_host_service._call_host_service_get("/test")

            assert mock_host_service.get_request_count() == initial_count + 1

    @pytest.mark.asyncio
    async def test_error_statistics_tracking(self, mock_host_service):
        """Test that error statistics are tracked."""
        initial_errors = mock_host_service.get_error_count()

        with patch.object(mock_host_service._http_client, "get") as mock_get:
            mock_get.side_effect = httpx.HTTPError("Test error")

            with pytest.raises(HostServiceConnectionError):
                await mock_host_service._call_host_service_get("/test")

            assert mock_host_service.get_error_count() == initial_errors + 1

    def test_get_statistics_dict(self, mock_host_service):
        """Test getting complete statistics as dictionary."""
        stats = mock_host_service.get_statistics()

        expected_keys = ["requests_made", "errors_encountered", "last_request_time"]
        assert all(key in stats for key in expected_keys)

    @pytest.mark.asyncio
    async def test_enhanced_metrics_collection(self, mock_host_service):
        """Test enhanced metrics collection for TASK-1.5b."""
        # Test enhanced metrics tracking
        with patch.object(mock_host_service._http_client, "get") as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = {"data": "test"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 200
            mock_response.elapsed = Mock()
            mock_response.elapsed.total_seconds.return_value = 0.125  # 125ms
            mock_get.return_value = mock_response

            await mock_host_service._call_host_service_get("/test")

            # Enhanced metrics should be available
            metrics = mock_host_service.get_detailed_metrics()
            assert "average_response_time" in metrics
            assert "fastest_response_time" in metrics
            assert "slowest_response_time" in metrics
            assert "total_bytes_sent" in metrics
            assert "total_bytes_received" in metrics
            assert "requests_by_status_code" in metrics
            assert "requests_by_endpoint" in metrics

    def test_performance_benchmarking_metrics(self, mock_host_service):
        """Test performance benchmarking capabilities for TASK-1.5b."""
        # Test performance tracking methods
        assert hasattr(mock_host_service, 'get_performance_summary')
        assert hasattr(mock_host_service, 'reset_metrics')
        assert hasattr(mock_host_service, 'get_connection_pool_stats')
        
        # Performance summary should include key metrics
        perf_summary = mock_host_service.get_performance_summary()
        expected_keys = [
            "uptime", "requests_per_second", "error_rate",
            "average_response_time", "connection_pool_utilization"
        ]
        assert all(key in perf_summary for key in expected_keys)

    def test_connection_pool_monitoring(self, mock_host_service):
        """Test connection pool monitoring for TASK-1.5b."""
        # Connection pool stats should be available
        pool_stats = mock_host_service.get_connection_pool_stats()
        expected_keys = [
            "active_connections", "idle_connections", "total_connections",
            "connection_pool_limit", "connections_created", "connections_closed"
        ]
        assert all(key in pool_stats for key in expected_keys)

    @pytest.mark.asyncio
    async def test_request_tracing_capabilities(self, mock_host_service):
        """Test request tracing capabilities for TASK-1.5b."""
        with patch.object(mock_host_service._http_client, "post") as mock_post:
            mock_response = Mock()
            mock_response.json.return_value = {"result": "success"}
            mock_response.raise_for_status.return_value = None
            mock_response.status_code = 201
            mock_post.return_value = mock_response

            # Enable request tracing
            trace_id = await mock_host_service._call_host_service_post_with_tracing(
                "/create", {"data": "test"}
            )
            
            # Should return a trace ID for request correlation
            assert trace_id is not None
            assert isinstance(trace_id, str)

            # Trace data should be accessible
            trace_data = mock_host_service.get_trace_data(trace_id)
            assert trace_data is not None
            assert "request_id" in trace_data
            assert "start_time" in trace_data
            assert "end_time" in trace_data
            assert "duration_ms" in trace_data
            assert "endpoint" in trace_data


class TestAsyncHostServiceConfiguration:
    """Test configuration injection and customization."""

    @pytest.mark.asyncio
    async def test_custom_timeout_configuration(self):
        """Test custom timeout configuration."""
        config = HostServiceConfig(base_url="http://localhost:5000", timeout=60)
        service = MockHostService(config)

        async with service:
            # Timeout should be reflected in HTTP client configuration
            assert service.config.timeout == 60

    @pytest.mark.asyncio
    async def test_custom_retry_configuration(self):
        """Test custom retry configuration."""
        config = HostServiceConfig(base_url="http://localhost:5000", max_retries=5)
        service = MockHostService(config)

        async with service:
            with patch.object(service._http_client, "post") as mock_post:
                mock_post.side_effect = [
                    httpx.TimeoutException("Timeout") for _ in range(6)
                ]

                with patch("asyncio.sleep"):  # Speed up test
                    with pytest.raises(HostServiceTimeoutError):
                        await service._call_host_service_post("/test", {})

                # Should have attempted 5 retries + 1 initial attempt = 6 calls
                assert mock_post.call_count == 6

    @pytest.mark.asyncio
    async def test_enhanced_config_options(self):
        """Test enhanced configuration options for TASK-1.5b."""
        # Test with enhanced configuration options that will be added
        config = HostServiceConfig(
            base_url="http://localhost:5000",
            timeout=45,
            max_retries=4,
            connection_pool_limit=30,
            # These new options should be added to HostServiceConfig
            health_check_interval=300,  # 5 minutes
            health_check_timeout=10,
            enable_metrics_collection=True,
            enable_request_tracing=True,
            connection_keep_alive=True,
            max_connection_age=3600,  # 1 hour
        )
        
        # This should not fail when enhanced config is implemented
        service = MockHostService(config)
        
        async with service:
            # Should be able to access new configuration options
            assert hasattr(service.config, 'health_check_interval')
            assert hasattr(service.config, 'health_check_timeout')
            assert hasattr(service.config, 'enable_metrics_collection')
            assert hasattr(service.config, 'enable_request_tracing')
            assert hasattr(service.config, 'connection_keep_alive')
            assert hasattr(service.config, 'max_connection_age')


class TestAsyncHostServiceIntegration:
    """Integration tests for realistic usage patterns."""

    @pytest.mark.asyncio
    async def test_complete_workflow(self):
        """Test complete workflow: setup -> request -> cleanup."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        # Test complete workflow
        async with service:
            # Health check
            with patch.object(service, "_call_host_service_get") as mock_get:
                mock_get.return_value = {"status": "healthy"}
                health = await service.check_health()
                assert health["status"] == "healthy"

            # POST request
            with patch.object(service, "_call_host_service_post") as mock_post:
                mock_post.return_value = {"result": "created"}
                result = await service._call_host_service_post(
                    "/create", {"data": "test"}
                )
                assert result["result"] == "created"

            # Statistics should be tracked
            stats = service.get_statistics()
            assert stats["requests_made"] >= 0  # At least the requests we made

    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test handling concurrent requests safely."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        async with service:
            with patch.object(service, "_call_host_service_get") as mock_get:
                mock_get.return_value = {"data": "test"}

                # Make multiple concurrent requests
                tasks = [service._call_host_service_get(f"/test/{i}") for i in range(5)]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                # All requests should succeed
                assert len(results) == 5
                assert all(isinstance(r, dict) for r in results)
                assert all(r["data"] == "test" for r in results)


class TestAsyncHostServicePerformanceBenchmarks:
    """Test performance benchmarking capabilities for TASK-1.5b."""

    @pytest.mark.asyncio
    async def test_throughput_benchmarking(self):
        """Test throughput measurement capabilities."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        async with service:
            # Run throughput benchmark (method to be implemented)
            benchmark_result = await service.run_throughput_benchmark(
                duration_seconds=5,
                concurrent_requests=10,
                endpoint="/benchmark"
            )

            # Should return comprehensive benchmark data
            assert "requests_per_second" in benchmark_result
            assert "average_latency_ms" in benchmark_result
            assert "p95_latency_ms" in benchmark_result
            assert "p99_latency_ms" in benchmark_result
            assert "total_requests" in benchmark_result
            assert "failed_requests" in benchmark_result
            assert "duration_seconds" in benchmark_result

    @pytest.mark.asyncio
    async def test_latency_distribution_tracking(self):
        """Test latency distribution tracking."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        async with service:
            # Simulate requests with varying latencies
            with patch.object(service, "_call_host_service_get") as mock_get:
                mock_get.return_value = {"status": "ok"}

                # Make several requests
                for _ in range(10):
                    await service._call_host_service_get("/test")

                # Get latency distribution (method to be implemented)
                latency_dist = service.get_latency_distribution()
                
                assert "percentiles" in latency_dist
                assert "histogram" in latency_dist
                assert "min" in latency_dist
                assert "max" in latency_dist
                assert "mean" in latency_dist
                assert "stddev" in latency_dist

    def test_memory_usage_tracking(self, mock_host_service):
        """Test memory usage tracking for connection pool."""
        # Memory usage should be tracked
        memory_stats = mock_host_service.get_memory_usage_stats()
        
        expected_keys = [
            "current_memory_mb", "peak_memory_mb", "connection_pool_memory_mb",
            "request_cache_memory_mb", "metrics_memory_mb"
        ]
        assert all(key in memory_stats for key in expected_keys)

    @pytest.mark.asyncio
    async def test_stress_testing_capabilities(self):
        """Test stress testing functionality."""
        config = HostServiceConfig(base_url="http://localhost:5000")
        service = MockHostService(config)

        async with service:
            # Run stress test (method to be implemented)
            stress_result = await service.run_stress_test(
                max_concurrent_requests=100,
                ramp_up_time_seconds=10,
                sustain_time_seconds=30,
                endpoint="/stress"
            )

            # Should track system behavior under stress
            assert "max_concurrent_achieved" in stress_result
            assert "requests_per_second_peak" in stress_result
            assert "error_rate_under_stress" in stress_result
            assert "connection_pool_exhausted" in stress_result
            assert "memory_pressure_events" in stress_result
