"""Tests for brief parameter propagation through the agent system.

Task 3.3: Verify brief flows from research_worker → design_worker.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.agents.workers.design_worker import AgentDesignWorker


class TestDesignWorkerBriefParameter:
    """Tests for DesignWorker accepting brief parameter."""

    @pytest.fixture
    def mock_ops_service(self):
        """Create mock operations service."""
        ops = MagicMock()
        ops.create_operation = AsyncMock(return_value=MagicMock(operation_id="op_test"))
        ops.get_operation = AsyncMock(
            return_value=MagicMock(metadata=MagicMock(parameters={}))
        )
        ops.complete_operation = AsyncMock()
        ops.fail_operation = AsyncMock()
        return ops

    @pytest.fixture
    def mock_invoker(self):
        """Create mock invoker that tracks calls."""
        invoker = MagicMock()
        invoker.run = AsyncMock(
            return_value=MagicMock(
                success=True,
                input_tokens=100,
                output_tokens=50,
            )
        )
        return invoker

    @pytest.mark.asyncio
    async def test_design_worker_accepts_brief_parameter(
        self, mock_ops_service, mock_invoker
    ):
        """DesignWorker.run() should accept optional brief parameter."""
        # Arrange
        worker = AgentDesignWorker(
            operations_service=mock_ops_service,
            invoker=mock_invoker,
        )

        # Make tool_executor return a saved strategy
        worker.tool_executor = MagicMock()
        worker.tool_executor.last_saved_strategy_name = "test_strategy"
        worker.tool_executor.last_saved_strategy_path = "/path/to/strategy.yaml"

        # Mock data repository
        worker.repository = MagicMock()
        worker.repository.get_available_data_files = MagicMock(return_value=[])

        # Act - call with brief parameter
        with patch(
            "ktrdr.agents.workers.design_worker.get_strategy_designer_prompt"
        ) as mock_prompt:
            mock_prompt.return_value = {"system": "sys", "user": "user"}
            with patch(
                "ktrdr.agents.workers.design_worker.get_indicators_from_api",
                new_callable=AsyncMock,
                return_value=[],
            ):
                await worker.run(
                    parent_operation_id="op_parent",
                    model="haiku",
                    brief="Design a simple RSI strategy.",
                )

        # Assert - brief should be passed to prompt builder with correct value
        mock_prompt.assert_called_once()
        call_kwargs = mock_prompt.call_args[1]
        assert "brief" in call_kwargs
        assert call_kwargs["brief"] == "Design a simple RSI strategy."

    @pytest.mark.asyncio
    async def test_design_worker_runs_without_brief(
        self, mock_ops_service, mock_invoker
    ):
        """DesignWorker.run() should work when brief is None."""
        # Arrange
        worker = AgentDesignWorker(
            operations_service=mock_ops_service,
            invoker=mock_invoker,
        )

        worker.tool_executor = MagicMock()
        worker.tool_executor.last_saved_strategy_name = "test_strategy"
        worker.tool_executor.last_saved_strategy_path = "/path/to/strategy.yaml"

        worker.repository = MagicMock()
        worker.repository.get_available_data_files = MagicMock(return_value=[])

        # Act - call without brief parameter
        with patch(
            "ktrdr.agents.workers.design_worker.get_strategy_designer_prompt"
        ) as mock_prompt:
            mock_prompt.return_value = {"system": "sys", "user": "user"}
            with patch(
                "ktrdr.agents.workers.design_worker.get_indicators_from_api",
                new_callable=AsyncMock,
                return_value=[],
            ):
                result = await worker.run(
                    parent_operation_id="op_parent",
                    model="haiku",
                    # No brief parameter
                )

        # Assert - should complete successfully
        assert result["success"] is True
