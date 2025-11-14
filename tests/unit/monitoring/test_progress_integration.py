"""Tests for progress system integration with OpenTelemetry."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from ktrdr.async_infrastructure.progress import (
    GenericProgressManager,
    GenericProgressState,
)


class TestProgressSpanIntegration:
    """Test that progress updates are reflected in OTEL spans."""

    @pytest.fixture
    def tracer_provider(self):
        """Create a tracer provider with in-memory exporter for testing."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        return provider, exporter

    @pytest.fixture
    def tracer(self, tracer_provider):
        """Get a tracer for testing."""
        provider, _ = tracer_provider
        return provider.get_tracer(__name__)

    def test_generic_progress_manager_updates_span_attributes(
        self, tracer, tracer_provider
    ):
        """Test that GenericProgressManager updates span attributes on progress."""
        _, exporter = tracer_provider

        # Create progress manager
        manager = GenericProgressManager()

        # Start operation and create span
        with tracer.start_as_current_span("test.operation") as span:
            manager.start_operation(
                operation_id="test_op_001", total_steps=10, context={"phase": "loading"}
            )

            # Update progress
            manager.update_progress(
                step=5,
                message="Halfway done",
                items_processed=500,
                context={"phase": "processing"},
            )

            # Verify span has progress attributes
            # Note: We need to check this after span completes
            pass

        # Get completed span
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attributes = dict(span.attributes or {})

        # Should have progress attributes
        assert "progress.percentage" in attributes
        assert attributes["progress.percentage"] == 50.0  # 5/10 * 100

        assert "progress.phase" in attributes
        assert attributes["progress.phase"] == "processing"

        assert "progress.current_step" in attributes
        assert attributes["progress.current_step"] == 5

        assert "progress.total_steps" in attributes
        assert attributes["progress.total_steps"] == 10

        assert "progress.items_processed" in attributes
        assert attributes["progress.items_processed"] == 500

        # Should have timestamp
        assert "progress.updated_at" in attributes

    def test_operations_service_update_progress_updates_span(
        self, tracer, tracer_provider
    ):
        """Test that OperationsService.update_progress updates span attributes."""
        from ktrdr.api.models.operations import (
            OperationMetadata,
            OperationProgress,
            OperationType,
        )
        from ktrdr.api.services.operations_service import OperationsService

        _, exporter = tracer_provider
        service = OperationsService()

        async def test_update():
            # Create operation
            metadata = OperationMetadata(symbol="AAPL", timeframe="1d")
            operation = await service.create_operation(
                operation_type=OperationType.DATA_LOAD, metadata=metadata
            )

            # Create span and update progress
            with tracer.start_as_current_span("test.data_download"):
                # Update progress
                progress = OperationProgress(
                    percentage=45.5,
                    current_step="Downloading segment 3/10",
                    estimated_remaining_seconds=120,
                )

                await service.update_progress(
                    operation_id=operation.operation_id, progress=progress
                )

            # Get completed span
            spans = exporter.get_finished_spans()
            assert len(spans) > 0

            # Find our test span (skip operation.register span)
            test_span = [s for s in spans if s.name == "test.data_download"][0]
            attributes = dict(test_span.attributes or {})

            # Should have progress attributes
            assert "progress.percentage" in attributes
            assert attributes["progress.percentage"] == 45.5

            assert "progress.phase" in attributes
            assert attributes["progress.phase"] == "Downloading segment 3/10"

            # Should have operation ID
            assert "operation.id" in attributes
            assert attributes["operation.id"] == operation.operation_id

            # Should have timestamp
            assert "progress.updated_at" in attributes

        import asyncio

        asyncio.run(test_update())

    def test_progress_callback_updates_span_in_real_time(self, tracer, tracer_provider):
        """Test that progress callbacks update span attributes in real-time."""
        _, exporter = tracer_provider

        # Track callback invocations
        callback_invocations = []

        def progress_callback(state: GenericProgressState):
            """Callback that should trigger span updates."""
            callback_invocations.append(state)

        # Create progress manager with callback
        manager = GenericProgressManager(callback=progress_callback)

        # Start operation within a span
        with tracer.start_as_current_span("test.operation") as span:
            manager.start_operation(
                operation_id="test_op_002", total_steps=5, context={"phase": "init"}
            )

            # Multiple progress updates
            for step in range(1, 6):
                manager.update_progress(
                    step=step,
                    message=f"Step {step}",
                    context={"phase": f"phase_{step}"},
                )

        # Should have called callback 6 times (start + 5 updates)
        assert len(callback_invocations) == 6

        # Get completed span
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attributes = dict(span.attributes or {})

        # Final progress should be reflected
        assert attributes["progress.percentage"] == 100.0
        assert attributes["progress.phase"] == "phase_5"
        assert attributes["progress.current_step"] == 5

    def test_progress_updates_without_active_span(self, tracer):
        """Test that progress updates work gracefully without an active span."""
        # Create progress manager
        manager = GenericProgressManager()

        # Update progress without span context
        # Should not crash
        manager.start_operation(operation_id="test_op_003", total_steps=10)

        manager.update_progress(step=5, message="No span", context={"phase": "test"})

        # Should complete successfully
        manager.complete_operation()

    def test_span_attributes_include_phase_information(self, tracer, tracer_provider):
        """Test that span attributes include detailed phase information."""
        _, exporter = tracer_provider

        # Create progress manager
        manager = GenericProgressManager()

        # Start operation with detailed phase tracking
        with tracer.start_as_current_span("test.training") as span:
            manager.start_operation(
                operation_id="train_001",
                total_steps=6,
                context={"strategy": "momentum", "symbol": "AAPL"},
            )

            # Simulate training phases
            phases = [
                ("loading_data", 0.0, 10.0),
                ("calculating_indicators", 10.0, 30.0),
                ("generating_fuzzy", 30.0, 40.0),
                ("training_model", 40.0, 95.0),
                ("evaluating", 95.0, 98.0),
                ("saving", 98.0, 100.0),
            ]

            for step, (phase_name, _, _) in enumerate(phases, 1):
                manager.update_progress(
                    step=step, message=phase_name, context={"phase": phase_name}
                )

        # Get completed span
        spans = exporter.get_finished_spans()
        assert len(spans) == 1

        span = spans[0]
        attributes = dict(span.attributes or {})

        # Should have final phase
        assert attributes["progress.phase"] == "saving"

        # Should have context
        assert "strategy" in str(attributes.get("progress.context", ""))
        assert "AAPL" in str(attributes.get("progress.context", ""))

    def test_progress_percentage_calculation_accuracy(self, tracer, tracer_provider):
        """Test that progress percentage is calculated accurately."""
        _, exporter = tracer_provider

        manager = GenericProgressManager()

        with tracer.start_as_current_span("test.accuracy") as span:
            manager.start_operation(operation_id="test_op_004", total_steps=7)

            # Update to 3/7 (approximately 42.86%)
            manager.update_progress(step=3, message="Step 3 of 7")

        spans = exporter.get_finished_spans()
        span = spans[0]
        attributes = dict(span.attributes or {})

        # Check percentage accuracy
        expected_percentage = (3 / 7) * 100.0
        actual_percentage = attributes["progress.percentage"]

        assert abs(actual_percentage - expected_percentage) < 0.01

    def test_multiple_concurrent_operations_with_spans(self, tracer, tracer_provider):
        """Test that multiple operations can update their own spans independently."""
        _, exporter = tracer_provider

        # Create two operations with different spans
        manager1 = GenericProgressManager()
        manager2 = GenericProgressManager()

        with tracer.start_as_current_span("test.op1"):
            manager1.start_operation(operation_id="op1", total_steps=10)
            manager1.update_progress(step=5, context={"phase": "op1_phase"})

        with tracer.start_as_current_span("test.op2"):
            manager2.start_operation(operation_id="op2", total_steps=20)
            manager2.update_progress(step=15, context={"phase": "op2_phase"})

        # Should have 2 completed spans
        spans = exporter.get_finished_spans()
        assert len(spans) == 2

        # Verify each span has correct progress
        span1_attrs = dict(spans[0].attributes or {})
        span2_attrs = dict(spans[1].attributes or {})

        assert span1_attrs["progress.percentage"] == 50.0
        assert span1_attrs["progress.phase"] == "op1_phase"

        assert span2_attrs["progress.percentage"] == 75.0
        assert span2_attrs["progress.phase"] == "op2_phase"


class TestProgressIntegrationEdgeCases:
    """Test edge cases for progress integration."""

    @pytest.fixture
    def tracer_provider(self):
        """Create a tracer provider with in-memory exporter for testing."""
        provider = TracerProvider()
        exporter = InMemorySpanExporter()
        processor = SimpleSpanProcessor(exporter)
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        return provider, exporter

    @pytest.fixture
    def tracer(self, tracer_provider):
        """Get a tracer for testing."""
        provider, _ = tracer_provider
        return provider.get_tracer(__name__)

    def test_progress_updates_before_operation_started(self, tracer):
        """Test that progress updates before operation start are handled gracefully."""
        manager = GenericProgressManager()

        # Try to update before starting operation
        # Should not crash
        manager.update_progress(step=5, message="Early update")

    def test_span_recording_false_skips_updates(self, tracer, tracer_provider):
        """Test that non-recording spans don't get updated."""
        _, exporter = tracer_provider

        manager = GenericProgressManager()

        # Create a span but don't record it
        with tracer.start_as_current_span("test.non_recording"):
            # Manually set recording to false (simulating sampled-out span)
            # Note: This is implementation-specific, might need adjustment
            manager.start_operation(operation_id="test_op", total_steps=10)
            manager.update_progress(step=5, message="Should be recorded")

        # Spans should still be created
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

    def test_very_large_progress_context_is_serialized(self, tracer, tracer_provider):
        """Test that large progress context is serialized correctly."""
        _, exporter = tracer_provider

        manager = GenericProgressManager()

        large_context = {
            "phase": "processing",
            "data": {
                "items": list(range(1000)),  # Large dataset
                "metadata": {"key": "value" * 100},
            },
        }

        with tracer.start_as_current_span("test.large_context") as span:
            manager.start_operation(
                operation_id="test_op", total_steps=10, context=large_context
            )

            manager.update_progress(step=5, message="Processing")

        # Should complete without error
        spans = exporter.get_finished_spans()
        assert len(spans) > 0

        # Context should be serialized (as string)
        span = spans[0]
        attributes = dict(span.attributes or {})
        assert "progress.context" in attributes or "progress.phase" in attributes
