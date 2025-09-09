"""
Test suite for ServiceOrchestrator progress enhancements.

This test suite validates the integration of GenericProgressManager
capabilities into ServiceOrchestrator.execute_with_progress() method,
following TDD methodology.
"""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
)


class TestServiceProgressRenderer:
    """Test suite for default ServiceOrchestrator progress renderer."""

    def test_service_progress_renderer_creation_succeeds(self):
        """Test that DefaultServiceProgressRenderer class can be imported and created."""
        # This test now passes because we implemented DefaultServiceProgressRenderer
        from ktrdr.managers.base import DefaultServiceProgressRenderer

        renderer = DefaultServiceProgressRenderer("TestService")
        assert renderer is not None
        assert hasattr(renderer, "render_message")
        assert hasattr(renderer, "enhance_state")

    def test_service_progress_renderer_basic_message_rendering_fails(self):
        """Test basic message rendering - will fail until implementation."""
        # This test will fail until we implement the renderer
        try:
            from ktrdr.managers.base import DefaultServiceProgressRenderer

            renderer = DefaultServiceProgressRenderer("TestService")
            state = GenericProgressState(
                operation_id="test_op",
                current_step=1,
                total_steps=3,
                percentage=33.3,
                message="Processing data",
            )

            result = renderer.render_message(state)
            assert "Processing data" in result
            assert "[1/3]" in result
            assert "(33.3%)" in result

        except ImportError:
            pytest.fail("DefaultServiceProgressRenderer not implemented yet")

    def test_service_progress_renderer_context_enhancement_fails(self):
        """Test context enhancement - will fail until implementation."""
        try:
            from ktrdr.managers.base import DefaultServiceProgressRenderer

            renderer = DefaultServiceProgressRenderer("TestService")
            state = GenericProgressState(
                operation_id="test_op",
                current_step=2,
                total_steps=5,
                percentage=40.0,
                message="Loading data",
                context={"symbol": "AAPL", "timeframe": "1h", "mode": "backfill"},
            )

            result = renderer.render_message(state)
            assert "symbol=AAPL" in result
            assert "timeframe=1h" in result
            assert "mode=backfill" in result

        except ImportError:
            pytest.fail("DefaultServiceProgressRenderer not implemented yet")

    def test_service_progress_renderer_time_estimation_fails(self):
        """Test time estimation enhancement - will fail until implementation."""
        try:
            from ktrdr.managers.base import DefaultServiceProgressRenderer

            renderer = DefaultServiceProgressRenderer("TestService")
            past_time = datetime.now() - timedelta(seconds=30)
            state = GenericProgressState(
                operation_id="test_op",
                current_step=1,
                total_steps=4,
                percentage=25.0,
                message="Processing",
                start_time=past_time,
            )

            enhanced_state = renderer.enhance_state(state)
            assert enhanced_state.estimated_remaining is not None
            assert enhanced_state.estimated_remaining.total_seconds() > 0

        except ImportError:
            pytest.fail("DefaultServiceProgressRenderer not implemented yet")


class TestServiceOrchestratorProgressEnhancement:
    """Test suite for ServiceOrchestrator progress enhancement integration."""

    def test_service_orchestrator_has_enhanced_progress_manager_fails(self):
        """Test ServiceOrchestrator has GenericProgressManager - will fail initially."""
        # Create a test ServiceOrchestrator subclass
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        # This should fail until we add GenericProgressManager to ServiceOrchestrator
        assert hasattr(orchestrator, "_generic_progress_manager")
        assert isinstance(
            orchestrator._generic_progress_manager, GenericProgressManager
        )

    def test_enhanced_execute_with_progress_uses_generic_manager_fails(self):
        """Test enhanced execute_with_progress uses GenericProgressManager - will fail initially."""
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        # Mock an async operation
        async def test_operation():
            await asyncio.sleep(0.01)
            return "success"

        received_states = []

        def progress_callback(progress_data):
            received_states.append(progress_data)

        # This should use enhanced progress tracking but will fail until implemented
        async def run_test():
            result = await orchestrator.execute_with_progress(
                test_operation(),
                progress_callback=progress_callback,
                operation_name="test_operation",
            )
            return result

        asyncio.run(run_test())

        # Should receive GenericProgressState instances instead of simple dict
        assert len(received_states) >= 2  # start and complete
        assert isinstance(received_states[0], GenericProgressState)
        assert received_states[0].operation_id == "test_operation"
        assert received_states[-1].percentage == 100.0

    def test_hierarchical_progress_tracking_fails(self):
        """Test hierarchical progress tracking in enhanced execute_with_progress - will fail initially."""
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        # Test operation that reports step-by-step progress
        async def multi_step_operation():
            # This should trigger step progress updates
            orchestrator.update_operation_progress(1, "Step 1: Initialize")
            await asyncio.sleep(0.01)

            orchestrator.update_operation_progress(2, "Step 2: Process")
            await asyncio.sleep(0.01)

            orchestrator.update_operation_progress(3, "Step 3: Finalize")
            await asyncio.sleep(0.01)

            return "completed"

        received_states = []

        def progress_callback(state):
            received_states.append(state)

        async def run_test():
            result = await orchestrator.execute_with_progress(
                multi_step_operation(),
                progress_callback=progress_callback,
                operation_name="multi_step_test",
                total_steps=3,
            )
            return result

        # This will fail until we implement update_operation_progress method
        asyncio.run(run_test())

        # Should track hierarchical progress
        assert len(received_states) >= 5  # start + 3 steps + complete
        step_states = [
            s
            for s in received_states
            if hasattr(s, "current_step") and s.current_step > 0
        ]
        assert len(step_states) >= 3
        assert step_states[0].current_step == 1
        assert step_states[1].current_step == 2
        assert step_states[2].current_step == 3

    def test_time_estimation_engine_integration_fails(self):
        """Test TimeEstimationEngine integration - will fail initially."""
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        # Test operation with time estimation
        async def timed_operation():
            # Simulate some work time
            await asyncio.sleep(0.1)
            orchestrator.update_operation_progress(
                50,
                "Halfway done",
                context={"operation_type": "data_load", "symbol": "AAPL"},
            )
            await asyncio.sleep(0.1)
            return "completed"

        received_states = []

        def progress_callback(state):
            received_states.append(state)

        async def run_test():
            result = await orchestrator.execute_with_progress(
                timed_operation(),
                progress_callback=progress_callback,
                operation_name="timed_test",
                total_steps=100,
            )
            return result

        asyncio.run(run_test())

        # Should have time estimation from TimeEstimationEngine
        progress_states = [
            s
            for s in received_states
            if hasattr(s, "estimated_remaining") and s.estimated_remaining
        ]
        assert len(progress_states) > 0
        assert progress_states[0].estimated_remaining.total_seconds() > 0

    def test_backward_compatibility_with_existing_progress_callback_fails(self):
        """Test backward compatibility with existing ProgressCallback protocol - will fail initially."""
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        # Test with legacy dict-based progress callback (existing interface)
        async def test_operation():
            await asyncio.sleep(0.01)
            return "success"

        received_progress = []

        def legacy_callback(progress_dict):
            # Existing code expects dict with these keys
            assert isinstance(progress_dict, dict)
            assert "percentage" in progress_dict
            assert "message" in progress_dict
            assert "operation" in progress_dict
            received_progress.append(progress_dict)

        async def run_test():
            # This should still work with legacy callback style
            result = await orchestrator.execute_with_progress(
                test_operation(),
                progress_callback=legacy_callback,
                operation_name="legacy_test",
            )
            return result

        asyncio.run(run_test())

        # Should maintain backward compatibility
        assert len(received_progress) >= 2  # start and complete
        assert received_progress[0]["percentage"] == 0
        assert received_progress[-1]["percentage"] == 100
        assert received_progress[0]["operation"] == "legacy_test"

    def test_thread_safety_of_enhanced_progress_fails(self):
        """Test thread safety of enhanced progress tracking - will fail initially."""
        from ktrdr.managers.base import ServiceOrchestrator

        class TestOrchestrator(ServiceOrchestrator):
            def _initialize_adapter(self):
                return Mock()

            def _get_service_name(self) -> str:
                return "TestService"

            def _get_default_host_url(self) -> str:
                return "http://localhost:8000"

            def _get_env_var_prefix(self) -> str:
                return "TEST"

        orchestrator = TestOrchestrator()

        received_updates = []
        exceptions = []

        def progress_callback(state):
            received_updates.append(state)

        async def concurrent_operation(operation_id: str):
            try:
                await orchestrator.execute_with_progress(
                    asyncio.sleep(0.01),
                    progress_callback=progress_callback,
                    operation_name=operation_id,
                )
            except Exception as e:
                exceptions.append(e)

        async def run_concurrent_test():
            # Run multiple operations concurrently
            tasks = []
            for i in range(10):
                task = asyncio.create_task(concurrent_operation(f"op_{i}"))
                tasks.append(task)

            await asyncio.gather(*tasks)

        asyncio.run(run_concurrent_test())

        # Should handle concurrent operations without errors
        assert len(exceptions) == 0, f"Exceptions occurred: {exceptions}"
        assert len(received_updates) >= 20  # At least start/complete for each operation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
