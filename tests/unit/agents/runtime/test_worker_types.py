"""Tests for AGENT_DESIGN and AGENT_ASSESSMENT worker types."""

import pytest

from ktrdr.api.models.workers import WorkerEndpoint, WorkerStatus, WorkerType
from ktrdr.api.services.worker_registry import WorkerRegistry


class TestAgentWorkerTypes:
    """Verify new agent worker types exist and work correctly."""

    def test_agent_design_is_valid_worker_type(self) -> None:
        """AGENT_DESIGN is a valid WorkerType."""
        assert WorkerType.AGENT_DESIGN == "agent_design"
        assert isinstance(WorkerType.AGENT_DESIGN.value, str)

    def test_agent_assessment_is_valid_worker_type(self) -> None:
        """AGENT_ASSESSMENT is a valid WorkerType."""
        assert WorkerType.AGENT_ASSESSMENT == "agent_assessment"
        assert isinstance(WorkerType.AGENT_ASSESSMENT.value, str)

    def test_worker_endpoint_accepts_agent_design(self) -> None:
        """WorkerEndpoint can be created with AGENT_DESIGN type."""
        worker = WorkerEndpoint(
            worker_id="design-agent-1",
            worker_type=WorkerType.AGENT_DESIGN,
            endpoint_url="http://design-agent-1:5010",
            status=WorkerStatus.AVAILABLE,
        )
        assert worker.worker_type == WorkerType.AGENT_DESIGN

    def test_worker_endpoint_accepts_agent_assessment(self) -> None:
        """WorkerEndpoint can be created with AGENT_ASSESSMENT type."""
        worker = WorkerEndpoint(
            worker_id="assess-agent-1",
            worker_type=WorkerType.AGENT_ASSESSMENT,
            endpoint_url="http://assess-agent-1:5020",
            status=WorkerStatus.AVAILABLE,
        )
        assert worker.worker_type == WorkerType.AGENT_ASSESSMENT


class TestWorkerRegistryAgentTypes:
    """Verify worker registry accepts agent worker types."""

    @pytest.mark.asyncio()
    async def test_registry_accepts_agent_design(self) -> None:
        """Worker registry accepts AGENT_DESIGN registration."""
        registry = WorkerRegistry()
        result = await registry.register_worker(
            worker_id="design-agent-1",
            worker_type=WorkerType.AGENT_DESIGN,
            endpoint_url="http://design-agent-1:5010",
            capabilities={"agent_type": "design"},
        )
        assert result.worker_id == "design-agent-1"
        assert result.worker.worker_type == WorkerType.AGENT_DESIGN

    @pytest.mark.asyncio()
    async def test_registry_accepts_agent_assessment(self) -> None:
        """Worker registry accepts AGENT_ASSESSMENT registration."""
        registry = WorkerRegistry()
        result = await registry.register_worker(
            worker_id="assess-agent-1",
            worker_type=WorkerType.AGENT_ASSESSMENT,
            endpoint_url="http://assess-agent-1:5020",
            capabilities={"agent_type": "assessment"},
        )
        assert result.worker_id == "assess-agent-1"
        assert result.worker.worker_type == WorkerType.AGENT_ASSESSMENT

    @pytest.mark.asyncio()
    async def test_registry_selects_agent_design_worker(self) -> None:
        """Worker registry can select an AGENT_DESIGN worker."""
        registry = WorkerRegistry()
        await registry.register_worker(
            worker_id="design-agent-1",
            worker_type=WorkerType.AGENT_DESIGN,
            endpoint_url="http://design-agent-1:5010",
        )
        worker = registry.select_worker(WorkerType.AGENT_DESIGN)
        assert worker is not None
        assert worker.worker_type == WorkerType.AGENT_DESIGN

    @pytest.mark.asyncio()
    async def test_existing_types_still_work(self) -> None:
        """Existing worker types are not broken by new additions."""
        registry = WorkerRegistry()
        result = await registry.register_worker(
            worker_id="backtest-1",
            worker_type=WorkerType.BACKTESTING,
            endpoint_url="http://backtest-1:5003",
        )
        assert result.worker.worker_type == WorkerType.BACKTESTING
