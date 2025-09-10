"""
Tests for KTRDR unified cancellation system.

This test suite validates:
- CancellationToken protocol implementation
- Thread-safe cancellation state management  
- Integration with ServiceOrchestrator patterns
- Compatibility with existing AsyncDataLoader patterns
"""

import asyncio
import threading

import pytest

from ktrdr.async_infrastructure.cancellation import (
    AsyncCancellationToken,
    CancellationCoordinator,
    CancellationError,
    CancellationState,
    CancellationToken,
    create_cancellation_token,
)


class TestCancellationToken:
    """Test CancellationToken protocol implementation."""

    def test_cancellation_token_protocol(self):
        """Test that CancellationToken protocol is properly defined."""
        # Create a token instance
        token = AsyncCancellationToken("test-op")

        # Verify protocol methods exist
        assert hasattr(token, 'is_cancelled')
        assert hasattr(token, 'cancel')
        assert hasattr(token, 'wait_for_cancellation')
        assert callable(token.is_cancelled)
        assert callable(token.cancel)
        assert callable(token.wait_for_cancellation)

    def test_initial_state(self):
        """Test initial cancellation state."""
        token = AsyncCancellationToken("test-op")

        assert not token.is_cancelled()
        assert token.reason is None
        assert token.operation_id == "test-op"

    def test_cancel_operation(self):
        """Test basic cancellation functionality."""
        token = AsyncCancellationToken("test-op")

        # Cancel with default reason
        token.cancel()

        assert token.is_cancelled()
        assert token.reason == "Operation cancelled"

    def test_cancel_with_custom_reason(self):
        """Test cancellation with custom reason."""
        token = AsyncCancellationToken("test-op")
        custom_reason = "User requested cancellation"

        token.cancel(custom_reason)

        assert token.is_cancelled()
        assert token.reason == custom_reason

    def test_multiple_cancellations(self):
        """Test that multiple cancellations don't cause issues."""
        token = AsyncCancellationToken("test-op")

        # First cancellation
        token.cancel("First reason")
        assert token.is_cancelled()
        assert token.reason == "First reason"

        # Second cancellation should be ignored (first reason preserved)
        token.cancel("Second reason")
        assert token.is_cancelled()
        assert token.reason == "First reason"

    def test_check_cancellation_raises_when_cancelled(self):
        """Test that check_cancellation raises exception when cancelled."""
        token = AsyncCancellationToken("test-op")

        # Should not raise when not cancelled
        token.check_cancellation("test context")

        # Should raise when cancelled
        token.cancel("Test cancellation")
        with pytest.raises(CancellationError) as exc_info:
            token.check_cancellation("test context")

        assert "test context" in str(exc_info.value)
        assert "Test cancellation" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_cancellation(self):
        """Test async wait for cancellation."""
        token = AsyncCancellationToken("test-op")

        async def cancel_after_delay():
            await asyncio.sleep(0.1)
            token.cancel("Delayed cancellation")

        # Start the cancellation task
        cancel_task = asyncio.create_task(cancel_after_delay())

        # Wait for cancellation (should complete when token is cancelled)
        await token.wait_for_cancellation()

        assert token.is_cancelled()
        assert token.reason == "Delayed cancellation"

        # Clean up
        await cancel_task


class TestCancellationState:
    """Test thread-safe cancellation state management."""

    def test_initial_state(self):
        """Test initial cancellation state."""
        state = CancellationState()

        assert not state.is_cancelled
        assert state.reason is None
        assert not state.is_global_cancelled

    def test_cancel_operation(self):
        """Test cancelling individual operation."""
        state = CancellationState()

        state.cancel("Test reason")

        assert state.is_cancelled
        assert state.reason == "Test reason"
        assert not state.is_global_cancelled  # Global not affected

    def test_global_cancellation(self):
        """Test global cancellation."""
        state = CancellationState()

        state.set_global_cancelled("Global shutdown")

        assert state.is_cancelled
        assert state.is_global_cancelled
        assert state.reason == "Global shutdown"

    def test_thread_safety(self):
        """Test thread-safe operations."""
        state = CancellationState()
        errors = []

        def cancel_operation(thread_id: int):
            try:
                for i in range(100):
                    state.cancel(f"Thread {thread_id} iteration {i}")
                    # Quick check to ensure consistency
                    if state.is_cancelled:
                        assert isinstance(state.reason, str)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=cancel_operation, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Check results
        assert len(errors) == 0, f"Thread safety errors: {errors}"
        assert state.is_cancelled
        assert state.reason is not None


class TestCancellationCoordinator:
    """Test centralized cancellation coordination."""

    def setup_method(self):
        """Set up fresh coordinator for each test."""
        self.coordinator = CancellationCoordinator()

    def test_create_token(self):
        """Test token creation."""
        token = self.coordinator.create_token("test-op-1")

        assert isinstance(token, AsyncCancellationToken)
        assert token.operation_id == "test-op-1"
        assert not token.is_cancelled()

    def test_cancel_single_operation(self):
        """Test cancelling single operation."""
        token = self.coordinator.create_token("test-op-1")

        result = self.coordinator.cancel_operation("test-op-1", "Test cancellation")

        assert result is True
        assert token.is_cancelled()
        assert token.reason == "Test cancellation"

    def test_cancel_nonexistent_operation(self):
        """Test cancelling operation that doesn't exist."""
        result = self.coordinator.cancel_operation("nonexistent", "Test")

        assert result is False

    def test_cancel_all_operations(self):
        """Test cancelling all operations."""
        token1 = self.coordinator.create_token("test-op-1")
        token2 = self.coordinator.create_token("test-op-2")
        token3 = self.coordinator.create_token("test-op-3")

        self.coordinator.cancel_all_operations("Global shutdown")

        assert token1.is_cancelled()
        assert token2.is_cancelled()
        assert token3.is_cancelled()
        assert all(token.reason == "Global shutdown" for token in [token1, token2, token3])

    def test_cleanup_after_operation(self):
        """Test that tokens are cleaned up after operations complete."""
        token = self.coordinator.create_token("test-op-1")

        # Simulate operation completion
        self.coordinator._cleanup_token("test-op-1")

        # Should not be able to cancel cleaned up operation
        result = self.coordinator.cancel_operation("test-op-1", "Test")
        assert result is False

    @pytest.mark.asyncio
    async def test_execute_with_cancellation_success(self):
        """Test successful execution with cancellation support."""
        async def test_operation(token: CancellationToken):
            # Simulate some work with cancellation checks
            for i in range(5):
                token.check_cancellation(f"step {i}")
                await asyncio.sleep(0.01)
            return "success"

        result = await self.coordinator.execute_with_cancellation(
            "test-op",
            test_operation,
            "test operation"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_cancellation_cancelled(self):
        """Test execution that gets cancelled."""
        async def test_operation(token: CancellationToken):
            # Simulate work that gets cancelled partway through
            for i in range(10):
                token.check_cancellation(f"step {i}")
                if i == 3:  # Cancel during execution
                    token.cancel("Mid-execution cancellation")
                await asyncio.sleep(0.01)
            return "should not reach here"

        with pytest.raises(CancellationError):
            await self.coordinator.execute_with_cancellation(
                "test-op",
                test_operation,
                "test operation"
            )

    @pytest.mark.asyncio
    async def test_execute_with_global_cancellation(self):
        """Test execution with global cancellation."""
        async def test_operation(token: CancellationToken):
            for i in range(10):
                token.check_cancellation(f"step {i}")
                await asyncio.sleep(0.01)
            return "success"

        # Start operation and cancel globally mid-execution
        async def cancel_globally():
            await asyncio.sleep(0.02)  # Let operation start
            self.coordinator.cancel_all_operations("Global cancellation")

        cancel_task = asyncio.create_task(cancel_globally())

        with pytest.raises(CancellationError):
            await self.coordinator.execute_with_cancellation(
                "test-op",
                test_operation,
                "test operation"
            )

        await cancel_task


class TestServiceOrchestratorIntegration:
    """Test integration with ServiceOrchestrator cancellation patterns."""

    def test_compatible_with_existing_protocol(self):
        """Test compatibility with existing CancellationToken protocol in ServiceOrchestrator."""

        # Our token should be compatible with ServiceOrchestrator protocol
        token = AsyncCancellationToken("test-op")

        # Check that our token has the required protocol method
        assert hasattr(token, 'is_cancelled_requested')

        # Test the compatibility
        assert not token.is_cancelled_requested

        token.cancel()
        assert token.is_cancelled_requested

    @pytest.mark.asyncio
    async def test_service_orchestrator_execute_with_cancellation_integration(self):
        """Test integration with ServiceOrchestrator.execute_with_cancellation."""
        # Create a mock ServiceOrchestrator
        class MockServiceOrchestrator:
            async def execute_with_cancellation(self, operation, cancellation_token=None, **kwargs):
                # This mimics ServiceOrchestrator behavior
                if cancellation_token and cancellation_token.is_cancelled_requested:
                    raise asyncio.CancelledError("Operation was cancelled")

                # Execute the operation
                return await operation

        orchestrator = MockServiceOrchestrator()
        token = AsyncCancellationToken("test-op")

        async def test_operation():
            return "success"

        # Should work when not cancelled
        result = await orchestrator.execute_with_cancellation(
            test_operation(),
            cancellation_token=token
        )
        assert result == "success"

        # Should raise when cancelled
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            await orchestrator.execute_with_cancellation(
                test_operation(),
                cancellation_token=token
            )


class TestAsyncDataLoaderCompatibility:
    """Test compatibility with existing AsyncDataLoader patterns."""

    def test_job_like_cancellation_token(self):
        """Test that our tokens work like AsyncDataLoader jobs."""
        token = AsyncCancellationToken("test-job")

        # Should support the same interface as DataLoadingJob
        assert hasattr(token, 'is_cancelled_requested')
        assert not token.is_cancelled_requested

        token.cancel("Job cancelled")
        assert token.is_cancelled_requested

    def test_progress_callback_integration(self):
        """Test integration with progress callback patterns."""
        coordinator = CancellationCoordinator()

        # Mock progress callback like in AsyncDataLoader
        progress_calls = []
        def progress_callback(progress_info):
            progress_calls.append(progress_info)

        @pytest.mark.asyncio
        async def test_operation_with_progress(token: CancellationToken):
            # Simulate progress updates with cancellation checks
            for i in range(3):
                token.check_cancellation(f"step {i}")
                progress_calls.append({"step": i, "total": 3})
                await asyncio.sleep(0.01)
            return "completed"

        # This pattern should work (mimicking AsyncDataLoader usage)
        async def run_test():
            return await coordinator.execute_with_cancellation(
                "test-op",
                test_operation_with_progress,
                "test operation with progress"
            )

        # Run the test
        result = asyncio.run(run_test())
        assert result == "completed"
        assert len(progress_calls) == 3


class TestFactoryFunctions:
    """Test factory and utility functions."""

    def test_create_cancellation_token(self):
        """Test factory function for creating tokens."""
        token = create_cancellation_token("test-op")

        assert isinstance(token, AsyncCancellationToken)
        assert token.operation_id == "test-op"
        assert not token.is_cancelled()

    def test_create_cancellation_token_with_coordinator(self):
        """Test factory function with coordinator."""
        coordinator = CancellationCoordinator()
        token = create_cancellation_token("test-op", coordinator=coordinator)

        assert isinstance(token, AsyncCancellationToken)
        assert token.operation_id == "test-op"

        # Should be registered with coordinator
        result = coordinator.cancel_operation("test-op", "Test")
        assert result is True
        assert token.is_cancelled()


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_cancellation_error_details(self):
        """Test CancellationError provides good details."""
        token = AsyncCancellationToken("test-op")
        token.cancel("Detailed reason")

        try:
            token.check_cancellation("important context")
            assert False, "Should have raised CancellationError"
        except CancellationError as e:
            error_str = str(e)
            assert "important context" in error_str
            assert "Detailed reason" in error_str
            assert "test-op" in error_str

    def test_concurrent_cancellation_safety(self):
        """Test safety under concurrent cancellation attempts."""
        token = AsyncCancellationToken("test-op")
        errors = []

        def cancel_concurrently(reason: str):
            try:
                token.cancel(reason)
                # Verify state is consistent
                assert token.is_cancelled()
                assert isinstance(token.reason, str)
            except Exception as e:
                errors.append(e)

        # Start multiple threads trying to cancel simultaneously
        threads = []
        for i in range(10):
            t = threading.Thread(target=cancel_concurrently, args=(f"Reason {i}",))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Check results - should be no errors, token should be cancelled
        assert len(errors) == 0
        assert token.is_cancelled()
        assert token.reason is not None
