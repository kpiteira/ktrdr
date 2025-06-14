"""
Unit tests for IB Pace Manager

Tests comprehensive functionality including:
- Proactive pace limiting (sync and async)
- Enhanced IB error classification
- Request rate monitoring and throttling
- Pace violation tracking and recovery
- Component-specific metrics
- Concurrent access scenarios
- Integration with existing error handler
"""

import pytest
import asyncio
import time
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from ktrdr.data.ib_pace_manager import (
    IbPaceManager,
    PaceViolationType,
    PaceViolationEvent,
    RequestMetrics,
    get_pace_manager,
    check_pace_async,
    check_pace_sync,
    handle_ib_error_async,
    handle_ib_error_sync,
)
from ktrdr.data.ib_error_handler import IbErrorType, IbErrorInfo


class TestPaceViolationEvent:
    """Test the PaceViolationEvent class."""

    def test_event_initialization(self):
        """Test pace violation event initialization."""
        event = PaceViolationEvent(
            violation_type=PaceViolationType.FREQUENCY_LIMIT,
            timestamp=1234567890.0,
            request_key="AAPL:1h:data_request",
            wait_time=30.0,
        )

        assert event.violation_type == PaceViolationType.FREQUENCY_LIMIT
        assert event.timestamp == 1234567890.0
        assert event.request_key == "AAPL:1h:data_request"
        assert event.wait_time == 30.0
        assert event.retry_count == 0
        assert event.resolved is False
        assert event.resolution_time is None

    def test_mark_resolved(self):
        """Test marking event as resolved."""
        event = PaceViolationEvent(
            violation_type=PaceViolationType.BURST_LIMIT,
            timestamp=time.time(),
            request_key="test",
            wait_time=5.0,
        )

        event.mark_resolved()

        assert event.resolved is True
        assert event.resolution_time is not None
        assert event.resolution_time > event.timestamp

    def test_get_duration(self):
        """Test duration calculation."""
        start_time = time.time()
        event = PaceViolationEvent(
            violation_type=PaceViolationType.MINIMUM_DELAY,
            timestamp=start_time,
            request_key="test",
            wait_time=2.0,
        )

        # Before resolution
        duration1 = event.get_duration()
        assert duration1 >= 0

        # After resolution
        time.sleep(0.1)
        event.mark_resolved()
        duration2 = event.get_duration()
        assert duration2 > duration1
        assert duration2 > 0.1


class TestRequestMetrics:
    """Test the RequestMetrics class."""

    def test_metrics_initialization(self):
        """Test metrics initialization."""
        metrics = RequestMetrics()

        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0
        assert metrics.pace_violations == 0
        assert metrics.total_wait_time == 0.0
        assert metrics.avg_request_interval == 0.0
        assert metrics.last_request_time == 0.0

    def test_record_successful_request(self):
        """Test recording successful requests."""
        metrics = RequestMetrics()

        metrics.record_request(success=True, wait_time=5.0)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.total_wait_time == 5.0
        assert metrics.last_request_time > 0

    def test_record_failed_request(self):
        """Test recording failed requests."""
        metrics = RequestMetrics()

        metrics.record_request(success=False, wait_time=10.0)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.total_wait_time == 10.0

    def test_average_interval_calculation(self):
        """Test average request interval calculation."""
        metrics = RequestMetrics()

        # First request
        metrics.record_request(success=True)
        assert metrics.avg_request_interval == 0.0  # No interval yet

        # Second request after delay
        time.sleep(0.1)
        metrics.record_request(success=True)
        assert metrics.avg_request_interval > 0.0
        assert metrics.avg_request_interval >= 0.1

    def test_pace_violation_recording(self):
        """Test pace violation recording."""
        metrics = RequestMetrics()

        metrics.record_pace_violation()
        metrics.record_pace_violation()

        assert metrics.pace_violations == 2


class TestIbPaceManager:
    """Test the main IB Pace Manager functionality."""

    @pytest.fixture
    def pace_manager(self):
        """Create a fresh pace manager instance."""
        # Reset singleton
        IbPaceManager._instance = None

        manager = IbPaceManager()

        # Reset state for clean testing
        manager.reset_statistics()

        yield manager

        # Clean up singleton
        IbPaceManager._instance = None

    @pytest.fixture
    def mock_error_handler(self):
        """Create a mock error handler."""
        handler = Mock()
        handler.set_request_context = Mock()
        handler.classify_error = Mock(
            return_value=IbErrorInfo(
                error_code=162,
                error_message="Test error",
                error_type=IbErrorType.PACING_VIOLATION,
                is_retryable=True,
                suggested_wait_time=30.0,
                description="Test pace violation",
            )
        )
        return handler

    def test_singleton_pattern(self):
        """Test that pace manager follows singleton pattern."""
        IbPaceManager._instance = None

        manager1 = IbPaceManager()
        manager2 = IbPaceManager()

        assert manager1 is manager2

        IbPaceManager._instance = None

    def test_request_key_creation(self, pace_manager):
        """Test request key creation."""
        # Simple key
        key1 = pace_manager._create_request_key("AAPL", "1h", "data_request")
        assert key1 == "AAPL:1h:data_request"

        # Key with dates
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)
        key2 = pace_manager._create_request_key(
            "MSFT", "1d", "backfill", start_date, end_date
        )
        assert "MSFT:1d:backfill" in key2
        assert "2024-01-01" in key2
        assert "2024-01-02" in key2

    def test_pace_limits_calculation(self, pace_manager):
        """Test pace limits calculation."""
        # No history - should be no wait
        wait_time = pace_manager._calculate_required_wait_sync(
            "test_key", "test_component"
        )
        assert wait_time == 0.0

        # Add many requests to trigger frequency limit
        current_time = time.time()
        for i in range(50):  # Above 80% threshold
            pace_manager._request_history.append((current_time - i, f"request_{i}"))

        wait_time = pace_manager._calculate_required_wait_sync(
            "new_key", "test_component"
        )
        assert wait_time > 0.0

    def test_identical_request_limit(self, pace_manager):
        """Test identical request cooldown."""
        request_key = "AAPL:1h:data_request"

        # First request should not wait
        wait_time = pace_manager._check_identical_request_limit(
            request_key, time.time()
        )
        assert wait_time == 0.0

        # Record the request
        pace_manager._identical_request_cache[request_key] = time.time()

        # Immediate repeat should trigger cooldown
        wait_time = pace_manager._check_identical_request_limit(
            request_key, time.time()
        )
        assert wait_time > 0.0

    def test_burst_limit(self, pace_manager):
        """Test burst limit detection."""
        current_time = time.time()

        # Add burst of requests
        for i in range(6):  # At burst limit
            pace_manager._request_history.append((current_time - 0.1, f"request_{i}"))

        wait_time = pace_manager._check_burst_limit(current_time)
        assert wait_time > 0.0

    def test_minimum_delay(self, pace_manager):
        """Test minimum delay between requests."""
        current_time = time.time()

        # Set last request very recently
        pace_manager._last_request_time = current_time - 0.1  # 100ms ago

        wait_time = pace_manager._check_minimum_delay(current_time)
        assert wait_time > 0.0  # Should require more delay

    @pytest.mark.asyncio
    async def test_async_pace_checking(self, pace_manager):
        """Test async pace checking."""
        # Should complete without waiting for first request
        start_time = time.time()

        await pace_manager.check_pace_limits_async(
            symbol="AAPL", timeframe="1h", component="test_component"
        )

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should be very fast

        # Verify request was recorded
        assert len(pace_manager._request_history) == 1
        assert "test_component" in pace_manager._component_metrics

    def test_sync_pace_checking(self, pace_manager):
        """Test sync pace checking."""
        # Should complete without waiting for first request
        start_time = time.time()

        pace_manager.check_pace_limits_sync(
            symbol="MSFT", timeframe="1d", component="test_component"
        )

        elapsed = time.time() - start_time
        assert elapsed < 1.0  # Should be very fast

        # Verify request was recorded
        assert len(pace_manager._request_history) == 1
        assert "test_component" in pace_manager._component_metrics

    @pytest.mark.asyncio
    async def test_pace_controlled_request_context(self, pace_manager):
        """Test pace controlled request context manager."""
        async with pace_manager.pace_controlled_request(
            symbol="TSLA", timeframe="5m", component="test_fetcher"
        ) as request_key:
            assert request_key == "TSLA:5m:data_request"

        # Verify metrics were recorded
        metrics = pace_manager._get_component_metrics("test_fetcher")
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1

    @pytest.mark.asyncio
    async def test_pace_controlled_request_with_exception(self, pace_manager):
        """Test pace controlled request with exception."""
        with pytest.raises(ValueError):
            async with pace_manager.pace_controlled_request(
                symbol="GOOGL", timeframe="1h", component="test_fetcher"
            ):
                raise ValueError("Test error")

        # Verify metrics recorded failure
        metrics = pace_manager._get_component_metrics("test_fetcher")
        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1
        assert metrics.successful_requests == 0

    @pytest.mark.asyncio
    async def test_async_error_handling(self, pace_manager, mock_error_handler):
        """Test async IB error handling."""
        pace_manager.error_handler = mock_error_handler

        should_retry, wait_time = await pace_manager.handle_ib_error_async(
            error_code=162,
            error_message="Historical data request pacing violation",
            component="test_component",
        )

        assert should_retry is True
        assert wait_time == 30.0

        # Verify error handler was called
        mock_error_handler.classify_error.assert_called_once()

    def test_sync_error_handling(self, pace_manager, mock_error_handler):
        """Test sync IB error handling."""
        pace_manager.error_handler = mock_error_handler

        should_retry, wait_time = pace_manager.handle_ib_error_sync(
            error_code=165,
            error_message="Historical data request pacing violation",
            component="test_component",
        )

        assert should_retry is True
        assert wait_time == 30.0

        # Verify error handler was called
        mock_error_handler.classify_error.assert_called_once()

    def test_component_metrics_tracking(self, pace_manager):
        """Test component-specific metrics tracking."""
        component1 = "data_fetcher"
        component2 = "symbol_validator"

        # Record requests for different components
        pace_manager._record_request("AAPL:1h", component1)
        pace_manager._record_request("MSFT:1d", component2)
        pace_manager._record_request("TSLA:5m", component1)

        # Verify separate metrics
        metrics1 = pace_manager._get_component_metrics(component1)
        metrics2 = pace_manager._get_component_metrics(component2)

        assert component1 in pace_manager._component_metrics
        assert component2 in pace_manager._component_metrics

    def test_violation_tracking(self, pace_manager):
        """Test pace violation tracking."""
        request_key = "AAPL:1h:test"

        # Simulate violation
        violation = PaceViolationEvent(
            violation_type=PaceViolationType.FREQUENCY_LIMIT,
            timestamp=time.time(),
            request_key=request_key,
            wait_time=10.0,
        )

        pace_manager._active_violations[request_key] = violation
        pace_manager._violation_history.append(violation)

        assert len(pace_manager._active_violations) == 1
        assert len(pace_manager._violation_history) == 1

    def test_statistics_generation(self, pace_manager):
        """Test comprehensive statistics generation."""
        # Add some data
        pace_manager._record_request("AAPL:1h", "component1")
        pace_manager._record_request("MSFT:1d", "component2")

        # Add violation
        violation = PaceViolationEvent(
            violation_type=PaceViolationType.BURST_LIMIT,
            timestamp=time.time(),
            request_key="test",
            wait_time=5.0,
        )
        pace_manager._violation_history.append(violation)

        stats = pace_manager.get_pace_statistics()

        assert "current_state" in stats
        assert "component_statistics" in stats
        assert "violation_statistics" in stats
        assert "configuration" in stats
        assert "history_stats" in stats

        # Check component stats
        assert "component1" in stats["component_statistics"]
        assert "component2" in stats["component_statistics"]

        # Check violation stats
        violation_stats = stats["violation_statistics"]
        assert "burst_limit" in violation_stats
        assert violation_stats["burst_limit"]["count"] == 1

    def test_statistics_reset(self, pace_manager):
        """Test statistics reset functionality."""
        # Add some data
        pace_manager._record_request("AAPL:1h", "component1")
        pace_manager._get_component_metrics("component1").record_pace_violation()

        # Verify data exists
        assert len(pace_manager._request_history) > 0
        assert len(pace_manager._component_metrics) > 0

        # Reset
        pace_manager.reset_statistics()

        # Verify reset
        assert len(pace_manager._request_history) == 0
        assert len(pace_manager._component_metrics) == 0
        assert len(pace_manager._violation_history) == 0
        assert pace_manager._last_request_time == 0.0

    def test_history_cleanup(self, pace_manager):
        """Test automatic history cleanup."""
        current_time = time.time()
        old_time = current_time - 700  # Older than max age (600s)

        # Add old and new requests
        pace_manager._request_history.append((old_time, "old_request"))
        pace_manager._request_history.append((current_time, "new_request"))

        # Clean history
        pace_manager._clean_request_history(current_time)

        # Only new request should remain
        assert len(pace_manager._request_history) == 1
        assert pace_manager._request_history[0][1] == "new_request"

    def test_violation_history_trimming(self, pace_manager):
        """Test violation history trimming."""
        # Set low limit for testing
        pace_manager._max_violation_history = 5

        # Add many violations
        for i in range(10):
            violation = PaceViolationEvent(
                violation_type=PaceViolationType.MINIMUM_DELAY,
                timestamp=time.time(),
                request_key=f"request_{i}",
                wait_time=1.0,
            )
            pace_manager._violation_history.append(violation)
            pace_manager._trim_violation_history()

        # Should be trimmed to max size
        assert len(pace_manager._violation_history) == 5

    @pytest.mark.asyncio
    async def test_concurrent_pace_checking(self, pace_manager):
        """Test concurrent pace checking operations."""

        async def check_pace_worker(component_id):
            await pace_manager.check_pace_limits_async(
                symbol=f"STOCK{component_id}",
                timeframe="1h",
                component=f"component_{component_id}",
            )
            return component_id

        # Run concurrent checks
        tasks = [check_pace_worker(i) for i in range(10)]
        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 10
        assert len(pace_manager._request_history) == 10
        assert len(pace_manager._component_metrics) == 10


class TestConvenienceFunctions:
    """Test the convenience functions."""

    @pytest.fixture(autouse=True)
    def reset_pace_manager(self):
        """Reset global pace manager before each test."""
        import ktrdr.data.ib_pace_manager

        ktrdr.data.ib_pace_manager._pace_manager = None
        yield
        ktrdr.data.ib_pace_manager._pace_manager = None

    def test_get_pace_manager_singleton(self):
        """Test that get_pace_manager returns singleton."""
        manager1 = get_pace_manager()
        manager2 = get_pace_manager()

        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_check_pace_async_convenience(self):
        """Test async pace checking convenience function."""
        await check_pace_async(
            symbol="AAPL", timeframe="1h", component="test_component"
        )

        # Should have recorded the request
        manager = get_pace_manager()
        assert len(manager._request_history) == 1

    def test_check_pace_sync_convenience(self):
        """Test sync pace checking convenience function."""
        check_pace_sync(symbol="MSFT", timeframe="1d", component="test_component")

        # Should have recorded the request
        manager = get_pace_manager()
        assert len(manager._request_history) == 1

    @pytest.mark.asyncio
    async def test_handle_ib_error_async_convenience(self):
        """Test async error handling convenience function."""
        with patch.object(get_pace_manager(), "error_handler") as mock_handler:
            mock_handler.classify_error.return_value = IbErrorInfo(
                error_code=162,
                error_message="Test error",
                error_type=IbErrorType.PACING_VIOLATION,
                is_retryable=True,
                suggested_wait_time=30.0,
                description="Test",
            )

            should_retry, wait_time = await handle_ib_error_async(
                error_code=162, error_message="Test error", component="test_component"
            )

            assert should_retry is True
            assert wait_time == 30.0

    def test_handle_ib_error_sync_convenience(self):
        """Test sync error handling convenience function."""
        with patch.object(get_pace_manager(), "error_handler") as mock_handler:
            mock_handler.classify_error.return_value = IbErrorInfo(
                error_code=165,
                error_message="Test error",
                error_type=IbErrorType.PACING_VIOLATION,
                is_retryable=True,
                suggested_wait_time=60.0,
                description="Test",
            )

            should_retry, wait_time = handle_ib_error_sync(
                error_code=165, error_message="Test error", component="test_component"
            )

            assert should_retry is True
            assert wait_time == 60.0


class TestErrorHandlerIntegration:
    """Test integration with existing error handler."""

    @pytest.fixture
    def pace_manager_with_real_handler(self):
        """Create pace manager with real error handler."""
        IbPaceManager._instance = None
        manager = IbPaceManager()
        manager.reset_statistics()
        yield manager
        IbPaceManager._instance = None

    def test_error_classification_integration(self, pace_manager_with_real_handler):
        """Test that error classification works with real handler."""
        manager = pace_manager_with_real_handler

        # Test different error types
        test_cases = [
            (
                162,
                "Historical data request pacing violation",
                IbErrorType.PACING_VIOLATION,
            ),
            (200, "No security definition has been found", IbErrorType.INVALID_REQUEST),
            (2106, "HMDS data farm connection is OK", IbErrorType.INFORMATIONAL),
        ]

        for error_code, error_message, expected_type in test_cases:
            should_retry, wait_time = manager.handle_ib_error_sync(
                error_code=error_code,
                error_message=error_message,
                component="test_component",
            )

            # Verify appropriate handling based on error type
            if expected_type == IbErrorType.PACING_VIOLATION:
                assert should_retry is True
                assert wait_time > 0
            elif expected_type == IbErrorType.INFORMATIONAL:
                assert should_retry is False
                assert wait_time == 0

    def test_request_context_setting(self, pace_manager_with_real_handler):
        """Test that request context is properly set."""
        manager = pace_manager_with_real_handler

        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end_date = datetime(2024, 1, 2, tzinfo=timezone.utc)

        # This should set context in the error handler
        manager.check_pace_limits_sync(
            symbol="AAPL",
            timeframe="1h",
            component="test_component",
            start_date=start_date,
            end_date=end_date,
        )

        # Verify context was set (check error handler state)
        context = manager.error_handler.last_request_context
        assert context["symbol"] == "AAPL"
        assert context["timeframe"] == "1h"
        assert context["start_date"] == start_date
        assert context["end_date"] == end_date


class TestPerformanceAndStress:
    """Test performance and stress scenarios."""

    @pytest.fixture
    def stress_pace_manager(self):
        """Create pace manager for stress testing."""
        IbPaceManager._instance = None
        manager = IbPaceManager()
        manager.reset_statistics()
        yield manager
        IbPaceManager._instance = None

    def test_large_request_history_performance(self, stress_pace_manager):
        """Test performance with large request history."""
        manager = stress_pace_manager

        # Add many historical requests
        current_time = time.time()
        for i in range(1000):
            manager._request_history.append((current_time - i, f"request_{i}"))

        # Measure pace checking performance
        start_time = time.time()
        wait_time = manager._calculate_required_wait_sync(
            "new_request", "test_component"
        )
        elapsed = time.time() - start_time

        # Should complete quickly even with large history
        assert elapsed < 1.0
        assert wait_time >= 0  # Should return valid result

    @pytest.mark.asyncio
    async def test_concurrent_async_operations(self, stress_pace_manager):
        """Test many concurrent async operations."""
        manager = stress_pace_manager

        async def pace_check_worker(worker_id):
            for i in range(5):
                await manager.check_pace_limits_async(
                    symbol=f"STOCK{worker_id}",
                    timeframe="1h",
                    component=f"worker_{worker_id}",
                )
                await asyncio.sleep(0.01)  # Small delay
            return worker_id

        # Run many concurrent workers
        tasks = [pace_check_worker(i) for i in range(20)]
        results = await asyncio.gather(*tasks)

        # All should complete successfully
        assert len(results) == 20
        assert len(set(results)) == 20  # All unique

        # Verify request tracking
        assert len(manager._request_history) == 100  # 20 workers * 5 requests each


if __name__ == "__main__":
    pytest.main([__file__])
