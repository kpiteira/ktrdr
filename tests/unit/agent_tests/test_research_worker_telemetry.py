"""Tests for AgentResearchWorker OpenTelemetry instrumentation.

Tests cover:
- Coordinator span creation
- Child spans for each phase (via direct handler calls)
- Phase-specific attributes (strategy_name, gate results, etc.)
- Error and exception recording

NOTE: These tests must be run in isolation to avoid tracer provider conflicts
with other tests. Run with: pytest tests/unit/agent_tests/test_research_worker_telemetry.py

Updated for v2.6 M1 multi-research coordinator model.
"""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# Import the module to patch its tracer
import ktrdr.agents.workers.research_worker as worker_module
from ktrdr.api.models.operations import OperationStatus, OperationType


@pytest.fixture
def tracer_provider():
    """Create in-memory tracer provider for testing (function-scoped).

    This fixture creates a fresh tracer provider for each test and patches
    the module's tracer to use it.
    """
    # Create a fresh provider and exporter
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Set the provider globally
    trace.set_tracer_provider(provider)

    # Create a test tracer and patch the module's tracer
    test_tracer = provider.get_tracer("ktrdr.agents.workers.research_worker")
    original_tracer = worker_module.tracer
    worker_module.tracer = test_tracer

    yield provider, exporter

    # Restore original tracer
    worker_module.tracer = original_tracer
    exporter.clear()


@pytest.fixture
def mock_operations_service():
    """Create a mock operations service for coordinator model.

    Supports both get_operation and list_operations for the multi-research
    coordinator loop.
    """
    service = AsyncMock()

    # Storage for operations (tests can modify this)
    operations: dict[str, Mock] = {}

    async def get_operation(op_id):
        return operations.get(op_id)

    async def list_operations(operation_type=None, status=None, **kwargs):
        filtered = list(operations.values())
        if operation_type:
            filtered = [op for op in filtered if op.operation_type == operation_type]
        if status:
            filtered = [op for op in filtered if op.status == status]
        return filtered, len(filtered), len(filtered)

    service.get_operation.side_effect = get_operation
    service.list_operations.side_effect = list_operations
    service.create_operation.return_value = None
    service.start_operation.return_value = None
    service.complete_operation.return_value = None
    service.fail_operation.return_value = None
    service.cancel_operation.return_value = None
    service.update_progress.return_value = None

    # Expose operations dict for test manipulation
    service._operations = operations

    return service


@pytest.fixture
def mock_design_worker():
    """Create a mock design worker."""
    worker = AsyncMock()
    worker.run.return_value = {
        "success": True,
        "strategy_name": "test_strategy",
        "strategy_path": "/tmp/test_strategy.yaml",
        "input_tokens": 1000,
        "output_tokens": 500,
    }
    return worker


@pytest.fixture
def mock_assessment_worker():
    """Create a mock assessment worker."""
    worker = AsyncMock()
    worker.run.return_value = {
        "success": True,
        "verdict": "promising",
        "input_tokens": 1500,
        "output_tokens": 800,
    }
    return worker


class TestResearchWorkerTelemetrySetup:
    """Tests for telemetry module setup."""

    def test_tracer_is_defined(self, tracer_provider):
        """Test that tracer is defined at module level."""
        import ktrdr.agents.workers.research_worker as worker_module

        assert hasattr(worker_module, "tracer")
        # Should be a valid tracer (not None)
        assert worker_module.tracer is not None


class TestCoordinatorSpan:
    """Tests for coordinator parent span creation."""

    @pytest.mark.asyncio
    async def test_run_creates_coordinator_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that run() creates an agent.coordinator parent span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Empty operations - coordinator should start and exit immediately
        mock_operations_service._operations.clear()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0  # No delay for tests

        # Run - should exit immediately with no operations
        await worker.run()

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the coordinator span
        coordinator_spans = [s for s in spans if s.name == "agent.coordinator"]
        assert (
            len(coordinator_spans) >= 1
        ), "Should create agent.coordinator parent span"

    @pytest.mark.asyncio
    async def test_coordinator_span_has_operation_type_attribute(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that coordinator span has operation.type attribute."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Empty operations - coordinator exits immediately
        mock_operations_service._operations.clear()

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        await worker.run()

        spans = exporter.get_finished_spans()
        coordinator_spans = [s for s in spans if s.name == "agent.coordinator"]

        assert len(coordinator_spans) >= 1
        span = coordinator_spans[0]
        assert span.attributes.get("operation.type") == "coordinator"


class TestPhaseSpans:
    """Tests for phase-specific child spans.

    These test that phase handlers create telemetry spans by directly calling
    the handlers rather than going through the full coordinator loop.
    """

    @pytest.mark.asyncio
    async def test_designing_phase_creates_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that designing phase creates agent.phase.design span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in designing phase with completed child
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "designing",
            "design_op_id": "op_design_test",
            "phase_start_time": 1000.0,
        }
        parent_op.status = OperationStatus.RUNNING

        # Child operation (design) completed
        child_op = Mock()
        child_op.operation_id = "op_design_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "strategy_name": "test_strategy",
            "strategy_path": "/tmp/test.yaml",
            "input_tokens": 1000,
            "output_tokens": 500,
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_design_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Directly call the handler (this is what _advance_research calls)
        # We need to catch the follow-on call to _start_training which will fail
        try:
            await worker._handle_designing_phase("op_test", child_op)
        except Exception:
            pass  # Expected - _start_training will fail without full setup

        spans = exporter.get_finished_spans()
        design_spans = [s for s in spans if s.name == "agent.phase.design"]

        assert len(design_spans) >= 1, "Should create agent.phase.design span"
        span = design_spans[0]
        assert span.attributes.get("phase") == "designing"

    @pytest.mark.asyncio
    async def test_training_phase_creates_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that training phase creates agent.phase.training span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in training phase with completed child
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "training",
            "training_op_id": "op_training_test",
            "phase_start_time": 1000.0,
        }
        parent_op.status = OperationStatus.RUNNING

        # Child operation (training) completed
        child_op = Mock()
        child_op.operation_id = "op_training_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "accuracy": 0.65,
            "final_loss": 0.3,
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_training_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Directly call the handler
        try:
            await worker._handle_training_phase("op_test", child_op)
        except Exception:
            pass  # Expected - _start_backtest will fail without full setup

        spans = exporter.get_finished_spans()
        training_spans = [s for s in spans if s.name == "agent.phase.training"]

        assert len(training_spans) >= 1, "Should create agent.phase.training span"
        span = training_spans[0]
        assert span.attributes.get("phase") == "training"

    @pytest.mark.asyncio
    async def test_backtesting_phase_creates_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that backtesting phase creates agent.phase.backtest span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in backtesting phase with completed child
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "backtesting",
            "backtest_op_id": "op_backtest_test",
            "phase_start_time": 1000.0,
        }
        parent_op.status = OperationStatus.RUNNING

        # Child operation (backtest) completed
        child_op = Mock()
        child_op.operation_id = "op_backtest_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "metrics": {
                "win_rate": 0.55,
                "max_drawdown_pct": 0.2,
                "sharpe_ratio": 1.0,
            }
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_backtest_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Directly call the handler
        try:
            await worker._handle_backtesting_phase("op_test", child_op)
        except Exception:
            pass  # Expected - _start_assessment will fail without full setup

        spans = exporter.get_finished_spans()
        backtest_spans = [s for s in spans if s.name == "agent.phase.backtest"]

        assert len(backtest_spans) >= 1, "Should create agent.phase.backtest span"
        span = backtest_spans[0]
        assert span.attributes.get("phase") == "backtesting"

    @pytest.mark.asyncio
    async def test_assessing_phase_creates_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that assessing phase creates agent.phase.assessment span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in assessing phase with completed child
        from datetime import datetime, timezone

        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "assessing",
            "assessment_op_id": "op_assess_test",
            "strategy_name": "test_strategy",
            "phase_start_time": 1000.0,
        }
        parent_op.status = OperationStatus.RUNNING
        parent_op.created_at = datetime.now(timezone.utc)

        # Child operation (assessment) completed
        child_op = Mock()
        child_op.operation_id = "op_assess_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "verdict": "promising",
            "input_tokens": 1500,
            "output_tokens": 800,
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_assess_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        # Directly call the handler - this one completes the operation
        result = await worker._handle_assessing_phase("op_test", child_op)

        # Should return result
        assert result is not None
        assert result["success"] is True

        spans = exporter.get_finished_spans()
        assess_spans = [s for s in spans if s.name == "agent.phase.assessment"]

        assert len(assess_spans) >= 1, "Should create agent.phase.assessment span"
        span = assess_spans[0]
        assert span.attributes.get("phase") == "assessing"


class TestSpanAttributes:
    """Tests for span attributes."""

    @pytest.mark.asyncio
    async def test_gate_pass_recorded_in_training_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that gate pass is recorded in training span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in training phase
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "training",
            "training_op_id": "op_training_test",
            "phase_start_time": 1000.0,
            "bypass_gates": False,  # Don't bypass gates
        }
        parent_op.status = OperationStatus.RUNNING

        # Child operation completed with good metrics (gate should pass)
        child_op = Mock()
        child_op.operation_id = "op_training_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "accuracy": 0.7,  # Above threshold
            "final_loss": 0.3,
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_training_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        try:
            await worker._handle_training_phase("op_test", child_op)
        except Exception:
            # Intentionally ignore: we only care that telemetry spans were recorded
            pass

        spans = exporter.get_finished_spans()
        training_spans = [s for s in spans if s.name == "agent.phase.training"]

        assert len(training_spans) >= 1
        span = training_spans[0]
        assert span.attributes.get("gate.name") == "training"
        assert span.attributes.get("gate.passed") is True

    @pytest.mark.asyncio
    async def test_gate_fail_recorded_in_training_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that gate fail is recorded in training span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up parent operation in training phase
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {
            "phase": "training",
            "training_op_id": "op_training_test",
            "phase_start_time": 1000.0,
            "bypass_gates": False,
        }
        parent_op.status = OperationStatus.RUNNING

        # Child operation completed with poor metrics (gate should fail)
        # Default min_accuracy is 0.10, so use < 10% to fail
        child_op = Mock()
        child_op.operation_id = "op_training_test"
        child_op.status = OperationStatus.COMPLETED
        child_op.result_summary = {
            "accuracy": 0.05,  # Below 10% threshold
            "final_loss": 0.9,  # Above 0.8 threshold
        }

        mock_operations_service._operations["op_test"] = parent_op
        mock_operations_service._operations["op_training_test"] = child_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )

        try:
            await worker._handle_training_phase("op_test", child_op)
        except Exception:
            # Intentionally ignore: we only care that telemetry spans were recorded
            pass

        spans = exporter.get_finished_spans()
        training_spans = [s for s in spans if s.name == "agent.phase.training"]

        assert len(training_spans) >= 1
        span = training_spans[0]
        assert span.attributes.get("gate.name") == "training"
        assert span.attributes.get("gate.passed") is False


class TestOutcomeRecording:
    """Tests for outcome recording in coordinator span."""

    @pytest.mark.asyncio
    async def test_cancelled_outcome_recorded(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that cancelled outcome is recorded in coordinator span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up an operation that will cause cancellation
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {"phase": "idle"}
        parent_op.status = OperationStatus.RUNNING

        mock_operations_service._operations["op_test"] = parent_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        # Make _start_design raise CancelledError to simulate cancellation
        async def raise_cancelled(*args, **kwargs):
            raise asyncio.CancelledError("Test cancellation")

        worker._start_design = raise_cancelled

        with pytest.raises(asyncio.CancelledError):
            await worker.run()

        spans = exporter.get_finished_spans()
        coordinator_spans = [s for s in spans if s.name == "agent.coordinator"]

        assert len(coordinator_spans) >= 1
        span = coordinator_spans[0]
        assert span.attributes.get("outcome") == "cancelled"


class TestErrorRecording:
    """Tests for error recording in spans."""

    @pytest.mark.asyncio
    async def test_exception_recorded_in_coordinator_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that exceptions are recorded in coordinator span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up an operation
        parent_op = Mock()
        parent_op.operation_id = "op_test"
        parent_op.operation_type = OperationType.AGENT_RESEARCH
        parent_op.metadata = Mock()
        parent_op.metadata.parameters = {"phase": "idle"}
        parent_op.status = OperationStatus.RUNNING

        mock_operations_service._operations["op_test"] = parent_op

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        # Make _start_design raise an error
        async def raise_error(*args, **kwargs):
            raise RuntimeError("Test error")

        worker._start_design = raise_error

        with pytest.raises(RuntimeError):
            await worker.run()

        spans = exporter.get_finished_spans()
        coordinator_spans = [s for s in spans if s.name == "agent.coordinator"]

        assert len(coordinator_spans) >= 1
        span = coordinator_spans[0]
        assert span.attributes.get("outcome") == "failed"
        assert "Test error" in str(span.attributes.get("error", ""))
