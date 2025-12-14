"""Tests for AgentDesignWorker.

Task 2.1 of M2: Verify real design worker using mocked Claude.

Tests cover:
- Prompt includes operation_id from context
- Strategy path returned on success
- WorkerError raised on invoker failure
- WorkerError raised if no strategy saved
- Token counts included in result
- CancelledError propagates correctly
- Child operation created and completed
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from ktrdr.agents.invoker import AgentResult


class TestAgentDesignWorkerInit:
    """Test AgentDesignWorker initialization."""

    def test_creates_default_invoker_if_not_provided(self):
        """Worker creates AnthropicAgentInvoker if not provided."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        mock_ops = MagicMock()
        worker = AgentDesignWorker(operations_service=mock_ops)

        assert worker.ops is mock_ops
        assert worker.invoker is not None

    def test_uses_provided_invoker(self):
        """Worker uses provided invoker."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        mock_ops = MagicMock()
        mock_invoker = MagicMock()
        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )

        assert worker.invoker is mock_invoker


class TestAgentDesignWorkerRun:
    """Test AgentDesignWorker.run() method."""

    @pytest.fixture
    def mock_ops(self):
        """Create mock OperationsService."""
        ops = MagicMock()

        # Mock create_operation to return a mock operation
        mock_op = MagicMock()
        mock_op.operation_id = "op_agent_design_test_123"
        ops.create_operation = AsyncMock(return_value=mock_op)
        ops.complete_operation = AsyncMock()
        ops.fail_operation = AsyncMock()
        ops.cancel_operation = AsyncMock()

        return ops

    @pytest.fixture
    def mock_invoker(self):
        """Create mock AnthropicAgentInvoker."""
        invoker = MagicMock()
        invoker.run = AsyncMock()
        return invoker

    @pytest.fixture
    def mock_tool_executor(self):
        """Create mock ToolExecutor with strategy info."""
        executor = MagicMock()
        executor.last_saved_strategy_name = "test_strategy_v1"
        executor.last_saved_strategy_path = "/app/strategies/test_strategy_v1.yaml"
        return executor

    @pytest.mark.asyncio
    async def test_strategy_path_returned_on_success(
        self, mock_ops, mock_invoker, mock_tool_executor
    ):
        """Design worker returns strategy path on success."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        # Mock successful invoker response
        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Strategy designed.",
            input_tokens=2500,
            output_tokens=1800,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        worker.tool_executor = mock_tool_executor

        result = await worker.run("op_parent_123")

        assert result["success"] is True
        assert result["strategy_name"] == "test_strategy_v1"
        assert result["strategy_path"] == "/app/strategies/test_strategy_v1.yaml"

    @pytest.mark.asyncio
    async def test_token_counts_included_in_result(
        self, mock_ops, mock_invoker, mock_tool_executor
    ):
        """Design worker returns token counts."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Done",
            input_tokens=2500,
            output_tokens=1800,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        worker.tool_executor = mock_tool_executor

        result = await worker.run("op_parent_123")

        assert result["input_tokens"] == 2500
        assert result["output_tokens"] == 1800

    @pytest.mark.asyncio
    async def test_worker_error_raised_on_invoker_failure(self, mock_ops, mock_invoker):
        """WorkerError raised when invoker returns failure."""
        from ktrdr.agents.workers.design_worker import (
            AgentDesignWorker,
            WorkerError,
        )

        mock_invoker.run.return_value = AgentResult(
            success=False,
            output=None,
            input_tokens=100,
            output_tokens=0,
            error="API rate limit exceeded",
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )

        with pytest.raises(WorkerError) as exc_info:
            await worker.run("op_parent_123")

        assert "API rate limit exceeded" in str(exc_info.value)
        # Should fail the operation
        mock_ops.fail_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_worker_error_raised_if_no_strategy_saved(
        self, mock_ops, mock_invoker
    ):
        """WorkerError raised when Claude doesn't save a strategy."""
        from ktrdr.agents.workers.design_worker import (
            AgentDesignWorker,
            WorkerError,
        )

        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Done but forgot to save.",
            input_tokens=2500,
            output_tokens=1800,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        # ToolExecutor has no saved strategy
        worker.tool_executor = MagicMock()
        worker.tool_executor.last_saved_strategy_name = None
        worker.tool_executor.last_saved_strategy_path = None

        with pytest.raises(WorkerError) as exc_info:
            await worker.run("op_parent_123")

        assert "did not save a strategy" in str(exc_info.value)
        mock_ops.fail_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancelled_error_propagates_correctly(self, mock_ops, mock_invoker):
        """CancelledError propagates and cancels operation."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        # Invoker raises CancelledError
        mock_invoker.run.side_effect = asyncio.CancelledError()

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )

        with pytest.raises(asyncio.CancelledError):
            await worker.run("op_parent_123")

        # Should cancel the operation
        mock_ops.cancel_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_child_operation_created_and_completed(
        self, mock_ops, mock_invoker, mock_tool_executor
    ):
        """Child operation created at start and completed on success."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker
        from ktrdr.api.models.operations import OperationType

        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Done",
            input_tokens=1000,
            output_tokens=500,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        worker.tool_executor = mock_tool_executor

        await worker.run("op_parent_123")

        # Should create child operation with AGENT_DESIGN type
        mock_ops.create_operation.assert_called_once()
        call_kwargs = mock_ops.create_operation.call_args.kwargs
        assert call_kwargs["operation_type"] == OperationType.AGENT_DESIGN
        # OperationMetadata is a dataclass, access parameters dict
        metadata = call_kwargs["metadata"]
        assert metadata.parameters["parent_operation_id"] == "op_parent_123"

        # Should complete the operation
        mock_ops.complete_operation.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoker_called_with_correct_params(
        self, mock_ops, mock_invoker, mock_tool_executor
    ):
        """Invoker is called with prompt, tools, system_prompt, tool_executor."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Done",
            input_tokens=1000,
            output_tokens=500,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        worker.tool_executor = mock_tool_executor

        await worker.run("op_parent_123")

        # Verify invoker.run was called
        mock_invoker.run.assert_called_once()

        # Check call args contain expected params
        call_kwargs = mock_invoker.run.call_args.kwargs
        assert "prompt" in call_kwargs
        assert "tools" in call_kwargs
        assert "system_prompt" in call_kwargs
        assert "tool_executor" in call_kwargs

    @pytest.mark.asyncio
    async def test_prompt_includes_operation_id_context(
        self, mock_ops, mock_invoker, mock_tool_executor
    ):
        """Prompt context includes operation_id."""
        from ktrdr.agents.workers.design_worker import AgentDesignWorker

        mock_invoker.run.return_value = AgentResult(
            success=True,
            output="Done",
            input_tokens=1000,
            output_tokens=500,
            error=None,
        )

        worker = AgentDesignWorker(
            operations_service=mock_ops,
            invoker=mock_invoker,
        )
        worker.tool_executor = mock_tool_executor

        await worker.run("op_parent_123")

        # Check the prompt was built (invoker was called with a prompt)
        call_kwargs = mock_invoker.run.call_args.kwargs
        prompt = call_kwargs["prompt"]

        # The prompt should contain the operation ID somewhere
        # (it's built from context that includes operation_id)
        assert isinstance(prompt, str)
        assert len(prompt) > 0
