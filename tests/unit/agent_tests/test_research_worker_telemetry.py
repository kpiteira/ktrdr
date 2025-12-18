"""Tests for AgentResearchWorker OpenTelemetry instrumentation.

Tests cover:
- Parent span for full research cycle
- Child spans for each phase
- operation.id attribute on all spans
- Phase-specific attributes (strategy_name, gate results, etc.)
- Error and exception recording

NOTE: These tests must be run in isolation to avoid tracer provider conflicts
with other tests. Run with: pytest tests/unit/agent_tests/test_research_worker_telemetry.py
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
from ktrdr.api.models.operations import OperationStatus


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
    """Create a mock operations service."""
    service = AsyncMock()

    # Default operation with idle phase
    mock_op = Mock()
    mock_op.operation_id = "op_agent_research_test"
    mock_op.metadata = Mock()
    mock_op.metadata.parameters = {"phase": "idle"}
    mock_op.status = OperationStatus.PENDING

    service.get_operation.return_value = mock_op
    service.create_operation.return_value = mock_op
    service.start_operation.return_value = None
    service.complete_operation.return_value = None
    service.fail_operation.return_value = None
    service.cancel_operation.return_value = None

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


class TestParentSpan:
    """Tests for parent span creation."""

    @pytest.mark.asyncio
    async def test_run_creates_parent_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that run() creates an agent.research_cycle parent span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Set up a complete cycle that finishes immediately
        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            # Simulate phase progression
            if call_count[0] <= 1:
                mock_op.metadata.parameters = {"phase": "idle"}
            elif call_count[0] <= 3:
                # Designing phase
                mock_op.metadata.parameters = {
                    "phase": "designing",
                    "design_op_id": "op_design_test",
                }
                # Return completed child
                if op_id == "op_design_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "strategy_name": "test_strategy",
                        "strategy_path": "/tmp/test.yaml",
                    }
            else:
                # Fast-forward to complete
                mock_op.metadata.parameters = {"phase": "assessing"}
                # Raise to exit the loop
                raise asyncio.CancelledError("Test complete")

            mock_op.status = OperationStatus.RUNNING
            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0  # No delay for tests

        # Run until cancelled
        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

        # Get exported spans
        spans = exporter.get_finished_spans()

        # Find the parent span
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]
        assert len(parent_spans) >= 1, "Should create agent.research_cycle parent span"

    @pytest.mark.asyncio
    async def test_parent_span_has_operation_id_attribute(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that parent span has operation.id attribute."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        # Simple mock that raises after first iteration
        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            if call_count[0] > 1:
                raise asyncio.CancelledError("Test complete")
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()
            mock_op.metadata.parameters = {"phase": "idle"}
            mock_op.status = OperationStatus.PENDING
            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_research_12345")

        spans = exporter.get_finished_spans()
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]

        assert len(parent_spans) >= 1
        span = parent_spans[0]
        assert span.attributes.get("operation.id") == "op_research_12345"
        assert span.attributes.get("operation.type") == "agent_research"


class TestPhaseSpans:
    """Tests for phase-specific child spans."""

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

        # _start_design makes 3 calls to get_operation, then run() polls
        # Total call sequence:
        # 1. run(): get parent (idle) -> calls _start_design
        # 2. _start_design: get parent to set phase
        # 3. _start_design: get parent to track child
        # 4. run(): get parent (designing)
        # 5. run(): get child (completed)
        # 6. _handle_designing_phase: get parent for metrics
        # Then cancel

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] == 1:
                # run(): First loop - idle phase, triggers _start_design
                mock_op.metadata.parameters = {"phase": "idle"}
                mock_op.status = OperationStatus.PENDING
            elif call_count[0] in (2, 3):
                # _start_design: gets parent twice to update metadata
                mock_op.metadata.parameters = {
                    "phase": "designing",
                    "design_op_id": "op_design_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 4:
                # run(): Second loop - get parent (designing phase)
                mock_op.metadata.parameters = {
                    "phase": "designing",
                    "design_op_id": "op_design_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 5:
                # run(): get child op (completed)
                if op_id == "op_design_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "strategy_name": "test_strategy",
                        "strategy_path": "/tmp/test.yaml",
                        "input_tokens": 1000,
                        "output_tokens": 500,
                    }
                else:
                    mock_op.metadata.parameters = {
                        "phase": "designing",
                        "design_op_id": "op_design_test",
                        "phase_start_time": 1000.0,
                    }
                    mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 6:
                # _handle_designing_phase: get parent for metrics update
                mock_op.metadata.parameters = {
                    "phase": "designing",
                    "design_op_id": "op_design_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            else:
                # After design span is created, cancel
                raise asyncio.CancelledError("Test complete")

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

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

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] == 1:
                # First call - get parent (training phase)
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 2:
                # Second call - get child (completed)
                if op_id == "op_training_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "accuracy": 0.65,
                        "final_loss": 0.3,
                        "initial_loss": 0.8,
                    }
                else:
                    mock_op.metadata.parameters = {
                        "phase": "training",
                        "training_op_id": "op_training_test",
                        "phase_start_time": 1000.0,
                    }
                    mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 3:
                # Third call - get parent for updating
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            else:
                # After training span is created, cancel
                raise asyncio.CancelledError("Test complete")

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

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

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] <= 2:
                mock_op.metadata.parameters = {
                    "phase": "backtesting",
                    "backtest_op_id": "op_backtest_test",
                    "phase_start_time": 1000.0,
                }
                if op_id == "op_backtest_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "metrics": {
                            "win_rate": 0.55,
                            "max_drawdown_pct": 0.2,
                            "sharpe_ratio": 1.0,
                        }
                    }
                else:
                    mock_op.status = OperationStatus.RUNNING
            else:
                raise asyncio.CancelledError("Test complete")

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

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

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] == 1:
                # First call - get parent (assessing phase)
                mock_op.metadata.parameters = {
                    "phase": "assessing",
                    "assessment_op_id": "op_assess_test",
                    "strategy_name": "test_strategy",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 2:
                # Second call - get child (completed)
                if op_id == "op_assess_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "verdict": "promising",
                        "input_tokens": 1500,
                        "output_tokens": 800,
                    }
                else:
                    mock_op.metadata.parameters = {
                        "phase": "assessing",
                        "assessment_op_id": "op_assess_test",
                        "strategy_name": "test_strategy",
                        "phase_start_time": 1000.0,
                    }
                    mock_op.status = OperationStatus.RUNNING
            else:
                # Third call - get parent for final result
                mock_op.metadata.parameters = {
                    "phase": "assessing",
                    "assessment_op_id": "op_assess_test",
                    "strategy_name": "test_strategy",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        # Assessment completes and returns result
        result = await worker.run("op_test")
        assert result["success"] is True

        spans = exporter.get_finished_spans()
        assess_spans = [s for s in spans if s.name == "agent.phase.assessment"]

        assert len(assess_spans) >= 1, "Should create agent.phase.assessment span"
        span = assess_spans[0]
        assert span.attributes.get("phase") == "assessing"


class TestSpanAttributes:
    """Tests for span attributes."""

    @pytest.mark.asyncio
    async def test_gate_pass_recorded_in_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that gate pass result is recorded in training span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] == 1:
                # First call - get parent (training phase)
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 2:
                # Second call - get child (completed)
                if op_id == "op_training_test":
                    mock_op.status = OperationStatus.COMPLETED
                    mock_op.result_summary = {
                        "accuracy": 0.65,
                        "final_loss": 0.3,
                        "initial_loss": 0.8,
                    }
                else:
                    mock_op.metadata.parameters = {
                        "phase": "training",
                        "training_op_id": "op_training_test",
                        "phase_start_time": 1000.0,
                    }
                    mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 3:
                # Third call - get parent for updating
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            else:
                # After training span is created, cancel
                raise asyncio.CancelledError("Test complete")

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

        spans = exporter.get_finished_spans()
        training_spans = [s for s in spans if s.name == "agent.phase.training"]

        assert len(training_spans) >= 1
        span = training_spans[0]
        assert span.attributes.get("gate.passed") is True
        assert span.attributes.get("gate.name") == "training"

    @pytest.mark.asyncio
    async def test_gate_fail_recorded_in_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that gate failure is recorded in span."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            GateError,
        )

        provider, exporter = tracer_provider

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            if call_count[0] == 1:
                # First call - get parent (training phase)
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING
            elif call_count[0] == 2:
                # Second call - get child (completed with bad accuracy)
                if op_id == "op_training_test":
                    mock_op.status = OperationStatus.COMPLETED
                    # Accuracy below threshold (0.45)
                    mock_op.result_summary = {
                        "accuracy": 0.30,
                        "final_loss": 0.3,
                        "initial_loss": 0.8,
                    }
                else:
                    mock_op.metadata.parameters = {
                        "phase": "training",
                        "training_op_id": "op_training_test",
                        "phase_start_time": 1000.0,
                    }
                    mock_op.status = OperationStatus.RUNNING
            else:
                # Third call - get parent for metrics (before gate check raises)
                mock_op.metadata.parameters = {
                    "phase": "training",
                    "training_op_id": "op_training_test",
                    "phase_start_time": 1000.0,
                }
                mock_op.status = OperationStatus.RUNNING

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(GateError):
            await worker.run("op_test")

        spans = exporter.get_finished_spans()
        training_spans = [s for s in spans if s.name == "agent.phase.training"]

        assert len(training_spans) >= 1
        span = training_spans[0]
        assert span.attributes.get("gate.passed") is False
        assert span.attributes.get("gate.name") == "training"


class TestOutcomeRecording:
    """Tests for outcome recording in spans."""

    @pytest.mark.asyncio
    async def test_completed_outcome_recorded(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that completed outcome is recorded in parent span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            # Simulate assessment phase completion
            mock_op.metadata.parameters = {
                "phase": "assessing",
                "assessment_op_id": "op_assess_test",
                "strategy_name": "test_strategy",
                "phase_start_time": 1000.0,
            }
            if op_id == "op_assess_test":
                mock_op.status = OperationStatus.COMPLETED
                mock_op.result_summary = {
                    "verdict": "promising",
                    "input_tokens": 1500,
                    "output_tokens": 800,
                }
            else:
                mock_op.status = OperationStatus.RUNNING

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        result = await worker.run("op_test")
        assert result["success"] is True

        spans = exporter.get_finished_spans()
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]

        assert len(parent_spans) >= 1
        span = parent_spans[0]
        assert span.attributes.get("outcome") == "completed"

    @pytest.mark.asyncio
    async def test_cancelled_outcome_recorded(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that cancelled outcome is recorded in parent span."""
        from ktrdr.agents.workers.research_worker import AgentResearchWorker

        provider, exporter = tracer_provider

        async def mock_get_operation(op_id):
            raise asyncio.CancelledError("Cancelled by user")

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_test")

        spans = exporter.get_finished_spans()
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]

        assert len(parent_spans) >= 1
        span = parent_spans[0]
        assert span.attributes.get("outcome") == "cancelled"

    @pytest.mark.asyncio
    async def test_failed_outcome_recorded(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that failed outcome is recorded in parent span."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        provider, exporter = tracer_provider

        call_count = [0]

        async def mock_get_operation(op_id):
            call_count[0] += 1
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()

            mock_op.metadata.parameters = {
                "phase": "designing",
                "design_op_id": "op_design_test",
            }
            if op_id == "op_design_test":
                mock_op.status = OperationStatus.FAILED
                mock_op.error_message = "Design worker crashed"
            else:
                mock_op.status = OperationStatus.RUNNING

            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(WorkerError):
            await worker.run("op_test")

        spans = exporter.get_finished_spans()
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]

        assert len(parent_spans) >= 1
        span = parent_spans[0]
        assert span.attributes.get("outcome") == "failed"


class TestErrorRecording:
    """Tests for error recording in spans."""

    @pytest.mark.asyncio
    async def test_exception_recorded_in_span(
        self,
        tracer_provider,
        mock_operations_service,
        mock_design_worker,
        mock_assessment_worker,
    ):
        """Test that exceptions are recorded in spans."""
        from ktrdr.agents.workers.research_worker import (
            AgentResearchWorker,
            WorkerError,
        )

        provider, exporter = tracer_provider

        async def mock_get_operation(op_id):
            mock_op = Mock()
            mock_op.operation_id = op_id
            mock_op.metadata = Mock()
            mock_op.metadata.parameters = {
                "phase": "designing",
                "design_op_id": "op_design_test",
            }
            if op_id == "op_design_test":
                mock_op.status = OperationStatus.FAILED
                mock_op.error_message = "API rate limit exceeded"
            else:
                mock_op.status = OperationStatus.RUNNING
            return mock_op

        mock_operations_service.get_operation.side_effect = mock_get_operation

        worker = AgentResearchWorker(
            operations_service=mock_operations_service,
            design_worker=mock_design_worker,
            assessment_worker=mock_assessment_worker,
        )
        worker.POLL_INTERVAL = 0

        with pytest.raises(WorkerError):
            await worker.run("op_test")

        spans = exporter.get_finished_spans()
        parent_spans = [s for s in spans if s.name == "agent.research_cycle"]

        assert len(parent_spans) >= 1
        span = parent_spans[0]

        # Check that error was recorded
        assert span.attributes.get("error") is not None or "error" in str(span.events)
