"""Tests for OpenTelemetry instrumentation of OperationsService."""

import asyncio

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture(autouse=True)
def reset_tracer():
    """Reset tracer provider before each test."""
    original_provider = trace.get_tracer_provider()
    # Reset to None so we can set a new provider
    trace._TRACER_PROVIDER = None
    yield
    # Restore original provider
    trace._TRACER_PROVIDER = original_provider


@pytest.fixture
def tracer_setup(reset_tracer):
    """Setup in-memory span exporter for testing."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    processor = SimpleSpanProcessor(exporter)
    provider.add_span_processor(processor)
    # Directly assign to bypass override warning
    trace._TRACER_PROVIDER = provider
    yield exporter
    # Force flush before clearing
    processor.force_flush()
    exporter.clear()


class TestOperationRegistrationSpans:
    """Tests for operation.register span instrumentation."""

    @pytest.mark.asyncio
    async def test_create_operation_creates_span(self, tracer_setup):
        """Test that create_operation creates an operation.register span."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(
            symbol="AAPL",
            timeframe="1d",
            mode="download",
            parameters={"test": "param"},
        )

        await service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )

        spans = exporter.get_finished_spans()
        # Should have both the existing @trace_service_method span AND the new operation.register span
        assert len(spans) >= 1

        # Find the operation.register span
        register_spans = [s for s in spans if s.name == "operation.register"]
        assert len(register_spans) == 1

        span = register_spans[0]
        assert span.status.status_code == StatusCode.OK

    @pytest.mark.asyncio
    async def test_operation_register_span_attributes(self, tracer_setup):
        """Test that operation.register span has required attributes."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(
            symbol="EURUSD",
            timeframe="1h",
            mode="backtest",
            parameters={"strategy": "momentum"},
        )

        operation = await service.create_operation(
            operation_type=OperationType.BACKTESTING, metadata=metadata
        )

        spans = exporter.get_finished_spans()
        register_spans = [s for s in spans if s.name == "operation.register"]
        assert len(register_spans) == 1

        span = register_spans[0]
        attrs = span.attributes

        # Check required attributes
        assert attrs.get("operation.id") == operation.operation_id
        assert attrs.get("operation.type") == "backtesting"
        assert attrs.get("operation.status") == "pending"
        assert attrs.get("data.symbol") == "EURUSD"
        assert attrs.get("data.timeframe") == "1h"


class TestOperationStateTransitionSpans:
    """Tests for operation.state_transition span instrumentation."""

    @pytest.mark.asyncio
    async def test_start_operation_creates_transition_span(self, tracer_setup):
        """Test that start_operation creates a state transition span."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(symbol="AAPL", timeframe="1d", mode="test")
        operation = await service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )

        # Clear spans from create_operation
        exporter.clear()

        # Create a mock task
        async def mock_task():
            await asyncio.sleep(0.001)

        task = asyncio.create_task(mock_task())

        await service.start_operation(operation.operation_id, task)

        spans = exporter.get_finished_spans()
        transition_spans = [s for s in spans if s.name == "operation.state_transition"]
        assert len(transition_spans) == 1

        span = transition_spans[0]
        attrs = span.attributes
        assert attrs.get("operation.id") == operation.operation_id
        assert attrs.get("operation.from_status") == "pending"
        assert attrs.get("operation.to_status") == "running"

    @pytest.mark.asyncio
    async def test_complete_operation_creates_transition_span(self, tracer_setup):
        """Test that complete_operation creates a state transition span."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(symbol="AAPL", timeframe="1d", mode="test")
        operation = await service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )

        async def mock_task():
            await asyncio.sleep(0.001)

        task = asyncio.create_task(mock_task())
        await service.start_operation(operation.operation_id, task)

        # Clear spans from previous operations
        exporter.clear()

        await service.complete_operation(
            operation.operation_id, result_summary={"rows": 100}
        )

        spans = exporter.get_finished_spans()
        transition_spans = [s for s in spans if s.name == "operation.state_transition"]
        assert len(transition_spans) == 1

        span = transition_spans[0]
        attrs = span.attributes
        assert attrs.get("operation.id") == operation.operation_id
        assert attrs.get("operation.from_status") == "running"
        assert attrs.get("operation.to_status") == "completed"

    @pytest.mark.asyncio
    async def test_fail_operation_creates_transition_span(self, tracer_setup):
        """Test that fail_operation creates a state transition span."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(symbol="AAPL", timeframe="1d", mode="test")
        operation = await service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )

        async def mock_task():
            await asyncio.sleep(0.001)

        task = asyncio.create_task(mock_task())
        await service.start_operation(operation.operation_id, task)

        # Clear spans from previous operations
        exporter.clear()

        await service.fail_operation(operation.operation_id, "Test error")

        spans = exporter.get_finished_spans()
        transition_spans = [s for s in spans if s.name == "operation.state_transition"]
        assert len(transition_spans) == 1

        span = transition_spans[0]
        attrs = span.attributes
        assert attrs.get("operation.id") == operation.operation_id
        assert attrs.get("operation.from_status") == "running"
        assert attrs.get("operation.to_status") == "failed"
        assert attrs.get("operation.error") == "Test error"

    @pytest.mark.asyncio
    async def test_cancel_operation_creates_transition_span(self, tracer_setup):
        """Test that cancel_operation creates a state transition span."""
        exporter = tracer_setup
        service = OperationsService()

        metadata = OperationMetadata(symbol="AAPL", timeframe="1d", mode="test")
        operation = await service.create_operation(
            operation_type=OperationType.DATA_LOAD, metadata=metadata
        )

        async def mock_task():
            await asyncio.sleep(0.001)

        task = asyncio.create_task(mock_task())
        await service.start_operation(operation.operation_id, task)

        # Clear spans from previous operations
        exporter.clear()

        await service.cancel_operation(operation.operation_id, reason="User requested")

        spans = exporter.get_finished_spans()
        transition_spans = [s for s in spans if s.name == "operation.state_transition"]
        assert len(transition_spans) == 1

        span = transition_spans[0]
        attrs = span.attributes
        assert attrs.get("operation.id") == operation.operation_id
        assert attrs.get("operation.from_status") == "running"
        assert attrs.get("operation.to_status") == "cancelled"
        assert attrs.get("operation.cancellation_reason") == "User requested"
