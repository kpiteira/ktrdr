"""Tests for agent tool subsets.

Task 8.2: Verify design phase has only necessary tools to reduce API round trips.

Tests cover:
- DESIGN_PHASE_TOOLS contains only validate_strategy_config and save_strategy_config
- DESIGN_PHASE_TOOLS does not contain discovery tools
- design_worker uses DESIGN_PHASE_TOOLS
"""

import pytest

from ktrdr.agents.tools import AGENT_TOOLS, DESIGN_PHASE_TOOLS, get_tool_names


class TestDesignPhaseTools:
    """Tests for DESIGN_PHASE_TOOLS constant."""

    def test_design_phase_tools_exists(self):
        """DESIGN_PHASE_TOOLS constant exists and is a list."""
        assert isinstance(DESIGN_PHASE_TOOLS, list)

    def test_design_phase_tools_has_two_tools(self):
        """DESIGN_PHASE_TOOLS contains exactly 2 tools."""
        assert len(DESIGN_PHASE_TOOLS) == 2

    def test_design_phase_tools_has_validate_strategy_config(self):
        """DESIGN_PHASE_TOOLS includes validate_strategy_config."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "validate_strategy_config" in tool_names

    def test_design_phase_tools_has_save_strategy_config(self):
        """DESIGN_PHASE_TOOLS includes save_strategy_config."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "save_strategy_config" in tool_names

    def test_design_phase_tools_excludes_get_available_indicators(self):
        """DESIGN_PHASE_TOOLS excludes get_available_indicators (context in prompt)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "get_available_indicators" not in tool_names

    def test_design_phase_tools_excludes_get_available_symbols(self):
        """DESIGN_PHASE_TOOLS excludes get_available_symbols (context in prompt)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "get_available_symbols" not in tool_names

    def test_design_phase_tools_excludes_get_recent_strategies(self):
        """DESIGN_PHASE_TOOLS excludes get_recent_strategies (context in prompt)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "get_recent_strategies" not in tool_names

    def test_design_phase_tools_excludes_start_training(self):
        """DESIGN_PHASE_TOOLS excludes start_training (orchestrator handles)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "start_training" not in tool_names

    def test_design_phase_tools_excludes_start_backtest(self):
        """DESIGN_PHASE_TOOLS excludes start_backtest (orchestrator handles)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "start_backtest" not in tool_names

    def test_design_phase_tools_excludes_save_assessment(self):
        """DESIGN_PHASE_TOOLS excludes save_assessment (assessment worker uses)."""
        tool_names = [t["name"] for t in DESIGN_PHASE_TOOLS]
        assert "save_assessment" not in tool_names

    def test_design_phase_tools_are_valid_schema(self):
        """Each tool in DESIGN_PHASE_TOOLS has required schema fields."""
        for tool in DESIGN_PHASE_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_agent_tools_still_has_all_tools(self):
        """AGENT_TOOLS still contains all 8 tools for other phases."""
        assert len(AGENT_TOOLS) == 8
        all_names = get_tool_names()
        assert "validate_strategy_config" in all_names
        assert "save_strategy_config" in all_names
        assert "get_available_indicators" in all_names
        assert "get_available_symbols" in all_names
        assert "get_recent_strategies" in all_names
        assert "start_training" in all_names
        assert "start_backtest" in all_names
        assert "save_assessment" in all_names


class TestDesignWorkerUsesReducedTools:
    """Tests that design_worker uses DESIGN_PHASE_TOOLS."""

    @pytest.mark.asyncio
    async def test_design_worker_passes_design_phase_tools_to_invoker(self):
        """Design worker passes DESIGN_PHASE_TOOLS to invoker, not AGENT_TOOLS."""
        from unittest.mock import AsyncMock, MagicMock

        from ktrdr.agents.invoker import AgentResult
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        # Setup mocks
        mock_ops = MagicMock()
        mock_op = MagicMock()
        mock_op.operation_id = "op_test_123"
        mock_ops.create_operation = AsyncMock(return_value=mock_op)
        mock_ops.complete_operation = AsyncMock()

        mock_invoker = MagicMock()
        mock_invoker.run = AsyncMock(
            return_value=AgentResult(
                success=True,
                output="Done",
                input_tokens=1000,
                output_tokens=500,
                error=None,
            )
        )

        # Create worker
        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )

        # Mock tool executor and context methods
        worker.tool_executor = MagicMock()
        worker.tool_executor.last_saved_strategy_name = "test_strat"
        worker.tool_executor.last_saved_strategy_path = "/path/test.yaml"
        worker._get_available_indicators = AsyncMock(return_value=[])
        worker._get_available_symbols = MagicMock(return_value=[])
        worker._get_recent_strategies = AsyncMock(return_value=[])

        # Run worker
        await worker.run("op_parent_123")

        # Verify invoker was called with DESIGN_PHASE_TOOLS
        call_kwargs = mock_invoker.run.call_args.kwargs
        tools_passed = call_kwargs["tools"]

        # Should be DESIGN_PHASE_TOOLS, not AGENT_TOOLS
        assert len(tools_passed) == 2
        tool_names = [t["name"] for t in tools_passed]
        assert "validate_strategy_config" in tool_names
        assert "save_strategy_config" in tool_names
        assert "get_available_indicators" not in tool_names
