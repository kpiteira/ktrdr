"""Tests for OpenTelemetry instrumentation of WorkerRegistry."""

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

from ktrdr.api.models.workers import WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry


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


class TestWorkerSelectionSpans:
    """Tests for worker_registry.select_worker span instrumentation."""

    @pytest.mark.asyncio
    async def test_select_worker_creates_span(self, tracer_setup):
        """Test that select_worker creates a span."""
        exporter = tracer_setup
        registry = WorkerRegistry()

        # Register some workers
        await registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://localhost:5003",
            capabilities={"cores": 4, "memory_gb": 8},
        )

        # Clear spans from registration
        exporter.clear()

        # Select a worker
        worker = registry.select_worker(WorkerType.BACKTESTING)

        spans = exporter.get_finished_spans()
        # Should have the existing @trace_service_method span from select_worker
        assert len(spans) >= 1

        # Find the workers.select span (from @trace_service_method("workers.select"))
        select_spans = [s for s in spans if s.name == "workers.select"]
        assert len(select_spans) == 1

        span = select_spans[0]
        assert span.status.status_code == StatusCode.OK
        assert worker is not None

    @pytest.mark.asyncio
    async def test_select_worker_span_attributes_with_available_workers(
        self, tracer_setup
    ):
        """Test that select_worker span has required attributes when workers available."""
        exporter = tracer_setup
        registry = WorkerRegistry()

        # Register multiple workers of different types
        await registry.register_worker(
            "backtest-1",
            WorkerType.BACKTESTING,
            "http://localhost:5003",
            capabilities={"cores": 4},
        )
        await registry.register_worker(
            "backtest-2",
            WorkerType.BACKTESTING,
            "http://localhost:5004",
            capabilities={"cores": 8},
        )
        await registry.register_worker(
            "training-1",
            WorkerType.TRAINING,
            "http://localhost:5005",
            capabilities={"gpu": True},
        )

        # Clear spans from registration
        exporter.clear()

        # Select a backtesting worker
        worker = registry.select_worker(WorkerType.BACKTESTING)

        spans = exporter.get_finished_spans()
        select_spans = [s for s in spans if s.name == "workers.select"]
        assert len(select_spans) == 1

        span = select_spans[0]
        attrs = span.attributes

        # Check required attributes
        assert attrs.get("worker.type") == "backtesting"
        assert attrs.get("worker.total_workers") == "3"  # Total across all types
        assert (
            attrs.get("worker.available_workers") == "2"
        )  # Available of requested type
        assert attrs.get("worker.capable_workers") == "2"  # Capable of requested type
        assert attrs.get("worker.selected_id") == worker.worker_id
        assert attrs.get("worker.selection_status") == "success"

    def test_select_worker_span_attributes_no_workers(self, tracer_setup):
        """Test that select_worker span attributes when no workers available."""
        exporter = tracer_setup
        registry = WorkerRegistry()

        # Don't register any workers

        # Select a worker
        worker = registry.select_worker(WorkerType.BACKTESTING)

        spans = exporter.get_finished_spans()
        select_spans = [s for s in spans if s.name == "workers.select"]
        assert len(select_spans) == 1

        span = select_spans[0]
        attrs = span.attributes

        # Check required attributes
        assert attrs.get("worker.type") == "backtesting"
        assert attrs.get("worker.total_workers") == "0"
        assert attrs.get("worker.available_workers") == "0"
        assert attrs.get("worker.capable_workers") == "0"
        assert attrs.get("worker.selected_id") is None
        assert attrs.get("worker.selection_status") == "no_workers_available"
        assert worker is None

    @pytest.mark.asyncio
    async def test_select_worker_span_attributes_wrong_type(self, tracer_setup):
        """Test span attributes when workers exist but wrong type."""
        exporter = tracer_setup
        registry = WorkerRegistry()

        # Register only training workers
        await registry.register_worker(
            "training-1",
            WorkerType.TRAINING,
            "http://localhost:5005",
        )
        await registry.register_worker(
            "training-2",
            WorkerType.TRAINING,
            "http://localhost:5006",
        )

        # Clear spans from registration
        exporter.clear()

        # Try to select a backtesting worker (none available)
        worker = registry.select_worker(WorkerType.BACKTESTING)

        spans = exporter.get_finished_spans()
        select_spans = [s for s in spans if s.name == "workers.select"]
        assert len(select_spans) == 1

        span = select_spans[0]
        attrs = span.attributes

        # Check attributes
        assert attrs.get("worker.type") == "backtesting"
        assert attrs.get("worker.total_workers") == "2"  # Total workers in registry
        assert attrs.get("worker.available_workers") == "0"  # No backtesting workers
        assert attrs.get("worker.capable_workers") == "0"
        assert attrs.get("worker.selected_id") is None
        assert attrs.get("worker.selection_status") == "no_workers_available"
        assert worker is None

    @pytest.mark.asyncio
    async def test_select_worker_span_attributes_all_busy(self, tracer_setup):
        """Test span attributes when workers exist but all are busy."""
        exporter = tracer_setup
        registry = WorkerRegistry()

        # Register workers and mark them as busy
        await registry.register_worker(
            "backtest-1",
            WorkerType.BACKTESTING,
            "http://localhost:5003",
        )
        await registry.register_worker(
            "backtest-2",
            WorkerType.BACKTESTING,
            "http://localhost:5004",
        )

        # Mark all workers as busy
        registry.mark_busy("backtest-1", "op-123")
        registry.mark_busy("backtest-2", "op-456")

        # Clear spans from previous operations
        exporter.clear()

        # Try to select a worker (all busy)
        worker = registry.select_worker(WorkerType.BACKTESTING)

        spans = exporter.get_finished_spans()
        select_spans = [s for s in spans if s.name == "workers.select"]
        assert len(select_spans) == 1

        span = select_spans[0]
        attrs = span.attributes

        # Check attributes
        assert attrs.get("worker.type") == "backtesting"
        assert attrs.get("worker.total_workers") == "2"
        assert attrs.get("worker.capable_workers") == "2"  # Workers exist
        assert attrs.get("worker.available_workers") == "0"  # But all busy
        assert attrs.get("worker.selected_id") is None
        assert attrs.get("worker.selection_status") == "no_workers_available"
        assert worker is None
