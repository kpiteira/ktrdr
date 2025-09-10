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
        assert hasattr(token, "is_cancelled")
        assert hasattr(token, "cancel")
        assert hasattr(token, "wait_for_cancellation")
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
        assert all(
            token.reason == "Global shutdown" for token in [token1, token2, token3]
        )

    def test_cleanup_after_operation(self):
        """Test that tokens are cleaned up after operations complete."""
        self.coordinator.create_token("test-op-1")

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
            "test-op", test_operation, "test operation"
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
                "test-op", test_operation, "test operation"
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
                "test-op", test_operation, "test operation"
            )

        await cancel_task


class TestServiceOrchestratorIntegration:
    """Test integration with ServiceOrchestrator cancellation patterns."""

    def test_compatible_with_existing_protocol(self):
        """Test compatibility with existing CancellationToken protocol in ServiceOrchestrator."""

        # Our token should be compatible with ServiceOrchestrator protocol
        token = AsyncCancellationToken("test-op")

        # Check that our token has the required protocol method
        assert hasattr(token, "is_cancelled_requested")

        # Test the compatibility
        assert not token.is_cancelled_requested

        token.cancel()
        assert token.is_cancelled_requested

    @pytest.mark.asyncio
    async def test_service_orchestrator_execute_with_cancellation_integration(self):
        """Test integration with ServiceOrchestrator.execute_with_cancellation."""

        # Create a mock ServiceOrchestrator
        class MockServiceOrchestrator:
            async def execute_with_cancellation(
                self, operation, cancellation_token=None, **kwargs
            ):
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
            test_operation(), cancellation_token=token
        )
        assert result == "success"

        # Should raise when cancelled
        token.cancel()
        with pytest.raises(asyncio.CancelledError):
            await orchestrator.execute_with_cancellation(
                test_operation(), cancellation_token=token
            )


class TestAsyncDataLoaderCompatibility:
    """Test compatibility with existing AsyncDataLoader patterns."""

    def test_job_like_cancellation_token(self):
        """Test that our tokens work like AsyncDataLoader jobs."""
        token = AsyncCancellationToken("test-job")

        # Should support the same interface as DataLoadingJob
        assert hasattr(token, "is_cancelled_requested")
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
                "test-op", test_operation_with_progress, "test operation with progress"
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


class TestCLIIntegration:
    """Test CLI KeyboardInterrupt integration (Task 2.3 requirements)."""

    def test_setup_cli_cancellation_handler_imports(self):
        """Test that CLI cancellation handler can be imported and setup."""
        from ktrdr.async_infrastructure.cancellation import (
            setup_cli_cancellation_handler,
        )

        # Should not raise on import/call
        # We can't test signal handling in unit tests, but we can test it doesn't crash
        setup_cli_cancellation_handler()

    @pytest.mark.asyncio
    async def test_global_cancellation_affects_new_operations(self):
        """Test that global cancellation prevents new operations from starting."""
        from ktrdr.async_infrastructure.cancellation import (
            cancel_all_operations,
            get_global_coordinator,
        )

        # Cancel all operations globally
        cancel_all_operations("Test global cancellation")

        coordinator = get_global_coordinator()

        # New operations should be cancelled before they start
        with pytest.raises(CancellationError):
            await coordinator.execute_with_cancellation(
                "test-op", lambda token: asyncio.sleep(0.1), "test operation"
            )

    @pytest.mark.asyncio
    async def test_coordinator_bridges_service_orchestrator_patterns(self):
        """Test integration with ServiceOrchestrator execute_with_cancellation patterns."""
        coordinator = CancellationCoordinator()

        # Should work with async operations that take cancellation tokens
        async def mock_service_operation(cancellation_token):
            # Simulate ServiceOrchestrator-style cancellation checking
            if (
                hasattr(cancellation_token, "is_cancelled")
                and cancellation_token.is_cancelled()
            ):
                raise asyncio.CancelledError("Operation was cancelled")
            return "success"

        result = await coordinator.execute_with_cancellation(
            "service-op-1", mock_service_operation, "Mock service operation"
        )

        assert result == "success"

    @pytest.mark.asyncio
    async def test_cli_cancellation_cancels_data_operations(self):
        """Test that CLI cancellation properly cancels data operations."""
        from ktrdr.async_infrastructure.cancellation import (
            cancel_all_operations,
            get_global_coordinator,
        )

        # Use the global coordinator to ensure cancel_all_operations affects the same instance
        coordinator = get_global_coordinator()

        # Reset global state for clean test
        from ktrdr.async_infrastructure.cancellation import CancellationState

        coordinator._global_state = CancellationState()

        # Start a mock data operation
        operation_cancelled = False

        async def mock_data_operation(cancellation_token):
            nonlocal operation_cancelled
            try:
                # Simulate data loading with cancellation checking
                for i in range(100):
                    if cancellation_token.is_cancelled():
                        operation_cancelled = True
                        raise CancellationError(f"Data operation cancelled at step {i}")
                    await asyncio.sleep(0.01)  # Simulate work
                return "data_loaded"
            except CancellationError:
                operation_cancelled = True
                raise

        # Start operation and cancel after a short time
        async def cancel_after_delay():
            await asyncio.sleep(0.05)
            cancel_all_operations("CLI KeyboardInterrupt simulation")

        # Run both concurrently
        cancel_task = asyncio.create_task(cancel_after_delay())

        with pytest.raises(CancellationError):
            await coordinator.execute_with_cancellation(
                "data-op-1", mock_data_operation, "Mock data operation"
            )

        await cancel_task
        assert operation_cancelled, "Data operation should have been cancelled"


class TestServiceOrchestratorBridge:
    """Test bridging with ServiceOrchestrator patterns (Task 2.3 requirements)."""

    @pytest.mark.asyncio
    async def test_unified_cancellation_with_service_orchestrator(self):
        """Test unified cancellation working with ServiceOrchestrator-style operations."""
        coordinator = CancellationCoordinator()

        # Mock ServiceOrchestrator-style operation that checks cancellation
        async def service_style_operation(cancellation_token):
            # ServiceOrchestrator pattern: check is_cancelled_requested property
            for _i in range(10):
                if hasattr(cancellation_token, "is_cancelled_requested"):
                    if cancellation_token.is_cancelled_requested:
                        raise asyncio.CancelledError(
                            "ServiceOrchestrator style cancellation"
                        )
                elif hasattr(cancellation_token, "is_cancelled"):
                    if cancellation_token.is_cancelled():
                        raise asyncio.CancelledError("Unified style cancellation")
                await asyncio.sleep(0.01)
            return "operation_complete"

        # Test normal completion
        result = await coordinator.execute_with_cancellation(
            "service-op", service_style_operation, "Service operation"
        )
        assert result == "operation_complete"

        # Test cancellation by cancelling during execution
        async def cancel_during_execution():
            await asyncio.sleep(0.02)  # Let operation start
            coordinator.cancel_operation("service-op-cancelled", "Test cancellation")

        cancel_task = asyncio.create_task(cancel_during_execution())

        with pytest.raises((CancellationError, asyncio.CancelledError)):
            await coordinator.execute_with_cancellation(
                "service-op-cancelled", service_style_operation, "Service operation"
            )

        await cancel_task

    @pytest.mark.asyncio
    async def test_async_data_loader_pattern_compatibility(self):
        """Test compatibility with AsyncDataLoader job cancellation patterns."""
        coordinator = CancellationCoordinator()

        # Mock AsyncDataLoader-style job execution
        async def data_job_operation(cancellation_token):
            # AsyncDataLoader pattern: periodic cancellation checking during segments
            segments = 5
            for segment in range(segments):
                # Check cancellation at segment boundaries (coarse-grained)
                if cancellation_token.is_cancelled():
                    raise CancellationError(f"Data job cancelled at segment {segment}")

                # Simulate segment processing with fine-grained checks
                for i in range(100):
                    if i % 20 == 0:  # Check every 20 iterations (fine-grained)
                        if cancellation_token.is_cancelled():
                            raise CancellationError(
                                f"Data job cancelled at segment {segment}, item {i}"
                            )
                    await asyncio.sleep(0.001)  # Simulate processing

            return f"processed_{segments}_segments"

        # Test successful completion
        result = await coordinator.execute_with_cancellation(
            "data-job-1", data_job_operation, "Data loading job"
        )
        assert result == "processed_5_segments"

        # Test cancellation during processing
        async def cancel_during_processing():
            await asyncio.sleep(0.02)  # Cancel partway through
            coordinator.cancel_operation("data-job-2", "Test cancellation")

        cancel_task = asyncio.create_task(cancel_during_processing())

        with pytest.raises(CancellationError) as exc_info:
            await coordinator.execute_with_cancellation(
                "data-job-2", data_job_operation, "Data loading job"
            )

        await cancel_task
        assert "cancelled at segment" in str(exc_info.value)


class TestUnifiedCancellationInterface:
    """Test the unified cancellation interface (Task 2.3 requirements)."""

    def test_cancellation_token_protocol_consistency(self):
        """Test CancellationToken protocol works across all domains."""
        # Reset global state to ensure clean test
        from ktrdr.async_infrastructure.cancellation import _global_coordinator, CancellationState
        if _global_coordinator is not None:
            _global_coordinator._global_state = CancellationState()
        
        # Create tokens from different sources with unique operation IDs
        coordinator = (
            CancellationCoordinator()
        )  # Use local coordinator to avoid global state
        token1 = AsyncCancellationToken("protocol-test-domain1-op-unique")
        token2 = coordinator.create_token("protocol-test-domain2-op-unique")
        token3 = create_cancellation_token("protocol-test-domain3-op-unique")

        # All should implement the same interface
        for i, token in enumerate([token1, token2, token3], 1):
            assert hasattr(token, "is_cancelled")
            assert hasattr(token, "cancel")
            assert hasattr(token, "wait_for_cancellation")
            assert hasattr(
                token, "is_cancelled_requested"
            )  # ServiceOrchestrator compatibility

            # Initial state should be consistent
            assert (
                not token.is_cancelled()
            ), f"Token {i} should not be cancelled initially"
            assert (
                not token.is_cancelled_requested
            ), f"Token {i} should not be cancelled_requested initially"

            # Cancellation should work consistently
            token.cancel(f"Test cancellation {i}")
            assert token.is_cancelled(), f"Token {i} should be cancelled after cancel()"
            assert (
                token.is_cancelled_requested
            ), f"Token {i} should be cancelled_requested after cancel()"

    @pytest.mark.asyncio
    async def test_thread_safe_cancellation_management(self):
        """Test cancellation state management is thread-safe."""
        coordinator = CancellationCoordinator()
        token = coordinator.create_token("thread-test-op")

        cancellation_results = []

        def cancel_from_thread(thread_id):
            try:
                token.cancel(f"Cancelled from thread {thread_id}")
                cancellation_results.append(f"thread-{thread_id}-success")
            except Exception as e:
                cancellation_results.append(f"thread-{thread_id}-error-{e}")

        # Start multiple threads trying to cancel
        threads = []
        for i in range(5):
            thread = threading.Thread(target=cancel_from_thread, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Token should be cancelled
        assert token.is_cancelled()

        # All threads should have completed successfully (no race conditions)
        assert len(cancellation_results) == 5
        assert all("success" in result for result in cancellation_results)

    @pytest.mark.asyncio
    async def test_cancellation_context_preservation(self):
        """Test cancellation context and reasons are preserved."""
        coordinator = CancellationCoordinator()

        detailed_reason = (
            "User requested cancellation via CLI (Ctrl+C) during data loading"
        )

        async def operation_with_context(cancellation_token):
            # Operation that checks for cancellation during execution
            for _i in range(20):  # Give time for cancellation to happen
                if cancellation_token.is_cancelled():
                    raise CancellationError(
                        "Operation cancelled with detailed context",
                        operation_id="contextual-op",
                        reason=cancellation_token.reason,
                    )
                await asyncio.sleep(0.01)
            return "completed"

        # Cancel with detailed context during execution
        async def cancel_with_context():
            await asyncio.sleep(0.02)  # Let operation start
            coordinator.cancel_operation("contextual-op", detailed_reason)

        cancel_task = asyncio.create_task(cancel_with_context())

        with pytest.raises(CancellationError) as exc_info:
            await coordinator.execute_with_cancellation(
                "contextual-op", operation_with_context, "Operation with context"
            )

        await cancel_task
        assert (
            detailed_reason in str(exc_info.value)
            or exc_info.value.reason == detailed_reason
        )


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_cancellation_error_details(self):
        """Test CancellationError provides good details."""
        token = AsyncCancellationToken("test-op")
        token.cancel("Detailed reason")

        try:
            token.check_cancellation("important context")
            raise AssertionError("Should have raised CancellationError")
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
