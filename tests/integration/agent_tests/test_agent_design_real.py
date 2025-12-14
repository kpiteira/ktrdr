"""Integration test for real Claude design (Task 2.5).

These tests require ANTHROPIC_API_KEY to be set. They test the actual
Claude integration for strategy design.

Run with:
    pytest tests/integration/agent_tests/test_agent_design_real.py -v
"""

import asyncio
import os
from pathlib import Path

import pytest
import yaml

from ktrdr.api.models.operations import OperationStatus
from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.getenv("ANTHROPIC_API_KEY"),
        reason="ANTHROPIC_API_KEY not set",
    ),
]


@pytest.fixture
def operations_service():
    """Create a fresh OperationsService for each test."""
    return OperationsService()


@pytest.fixture
def agent_service(operations_service):
    """Create AgentService with fresh OperationsService."""
    return AgentService(operations_service=operations_service)


@pytest.fixture
def cleanup_strategies():
    """Track and clean up created strategy files after test."""
    created_files: list[Path] = []
    yield created_files
    # Cleanup
    for path in created_files:
        if path.exists():
            path.unlink()


class TestRealDesignWorker:
    """Integration tests for real Claude design worker."""

    @pytest.mark.asyncio
    async def test_real_design_creates_strategy(
        self, agent_service, operations_service, cleanup_strategies
    ):
        """Real Claude design creates valid strategy file."""
        # Trigger cycle
        result = await agent_service.trigger()
        assert result["triggered"] is True

        # Wait for design to complete (training phase means design done)
        # Design typically takes 30-90 seconds with Claude
        for _ in range(120):  # Up to 2 minutes
            status = await agent_service.get_status()
            phase = status.get("phase", "")

            # Design complete when we move to training or beyond
            if phase in ["training", "backtesting", "assessing"]:
                break

            # Cycle ended (failed or completed)
            if status.get("status") == "idle":
                break

            await asyncio.sleep(1)

        # Get strategy name from status
        status = await agent_service.get_status()
        strategy_name = status.get("strategy_name")

        # May be in last_cycle if cycle completed quickly
        if strategy_name is None and status.get("last_cycle"):
            strategy_name = status["last_cycle"].get("strategy_name")

        assert strategy_name is not None, f"No strategy name in status: {status}"

        # Verify file exists
        strategy_path = Path(f"strategies/{strategy_name}.yaml")
        cleanup_strategies.append(strategy_path)

        assert strategy_path.exists(), f"Strategy file not found: {strategy_path}"

        # Verify valid YAML
        with open(strategy_path) as f:
            config = yaml.safe_load(f)

        # Check required fields
        assert "name" in config, f"Missing 'name' in config: {config.keys()}"
        has_indicators = "indicators" in config
        has_fuzzy_sets = "fuzzy_sets" in config
        assert (
            has_indicators or has_fuzzy_sets
        ), f"Config needs 'indicators' or 'fuzzy_sets': {config.keys()}"

    @pytest.mark.asyncio
    async def test_design_worker_tracks_tokens(
        self, agent_service, operations_service, cleanup_strategies
    ):
        """Design worker records token usage."""
        # Trigger cycle
        result = await agent_service.trigger()
        op_id = result["operation_id"]

        # Wait for design to complete
        for _ in range(120):
            op = await operations_service.get_operation(op_id)
            if op is None:
                break

            phase = op.metadata.parameters.get("phase")
            if phase and phase != "designing":
                break

            if op.status in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
                break

            await asyncio.sleep(1)

        # Get final operation state
        op = await operations_service.get_operation(op_id)
        assert op is not None

        # Track strategy for cleanup
        strategy_name = op.metadata.parameters.get("strategy_name")
        if strategy_name:
            cleanup_strategies.append(Path(f"strategies/{strategy_name}.yaml"))

        # Get design operation
        design_op_id = op.metadata.parameters.get("design_op_id")
        assert design_op_id is not None, f"No design_op_id in metadata: {op.metadata}"

        design_op = await operations_service.get_operation(design_op_id)
        assert design_op is not None, f"Design operation not found: {design_op_id}"

        # Verify token counts (only if design completed successfully)
        if design_op.status == OperationStatus.COMPLETED:
            result = design_op.result_summary or {}
            assert (
                result.get("input_tokens", 0) > 0
            ), f"No input_tokens recorded: {result}"
            assert (
                result.get("output_tokens", 0) > 0
            ), f"No output_tokens recorded: {result}"
