"""Assessment worker that uses Claude to evaluate strategy results.

Task 5.3: Real assessment worker using AnthropicAgentInvoker.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from ktrdr import get_logger
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.invoker import (
    AnthropicAgentInvoker,
    AnthropicInvokerConfig,
    resolve_model,
)
from ktrdr.agents.prompts import (
    ASSESSMENT_SYSTEM_PROMPT,
    AssessmentContext,
    get_assessment_prompt,
)
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.api.models.operations import OperationMetadata, OperationType

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""

    pass


class AgentAssessmentWorker:
    """Worker that uses Claude to assess strategy results.

    This worker:
    1. Creates a child AGENT_ASSESSMENT operation
    2. Builds assessment prompt with training and backtest metrics
    3. Calls Claude via AnthropicAgentInvoker
    4. Saves assessment via save_assessment tool
    5. Returns verdict, assessment_path, and token counts

    Attributes:
        ops: Operations service for tracking operations.
        invoker: Claude API invoker.
        tool_executor: Executor for tool calls.
    """

    def __init__(
        self,
        operations_service: OperationsService,
        invoker: AnthropicAgentInvoker | None = None,
    ):
        """Initialize the assessment worker.

        Args:
            operations_service: Service for tracking operations.
            invoker: Optional invoker instance for testing. If provided, this
                     invoker will be used in run() instead of creating a new one
                     with the resolved model config.
        """
        self.ops = operations_service
        # Store injected invoker (for testing) - if provided, run() will use it
        self._injected_invoker = invoker
        # Also keep self.invoker for backward compatibility with init tests
        self.invoker = invoker or AnthropicAgentInvoker()
        self.tool_executor = ToolExecutor()

    async def run(
        self,
        parent_operation_id: str,
        results: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Run assessment phase using Claude.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            results: Dict with 'training' and 'backtest' result dicts.
            model: Model to use ('opus', 'sonnet', 'haiku' or full ID).
                   If None, uses AGENT_MODEL env var or default.

        Returns:
            Dict with verdict, assessment_path, and token counts.

        Raises:
            WorkerError: If assessment fails or Claude doesn't save assessment.
            asyncio.CancelledError: If cancelled.
        """
        # Resolve model (allows runtime switching via API/CLI)
        resolved_model = resolve_model(model)
        logger.info(
            f"Starting assessment phase: {parent_operation_id}, model={resolved_model}"
        )

        # Get parent operation for strategy info
        parent_op = await self.ops.get_operation(parent_operation_id)
        if parent_op is None:
            raise WorkerError(f"Parent operation not found: {parent_operation_id}")
        strategy_name = parent_op.metadata.parameters.get("strategy_name")
        strategy_path = parent_op.metadata.parameters.get("strategy_path")

        # Set strategy name in executor for save_assessment tool
        self.tool_executor._current_strategy_name = strategy_name

        # Create child operation
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata=OperationMetadata(  # type: ignore[call-arg]
                parameters={"parent_operation_id": parent_operation_id}
            ),
        )

        try:
            # Build context for prompt
            context = AssessmentContext(
                operation_id=op.operation_id,
                strategy_name=strategy_name or "unknown",
                strategy_path=strategy_path or "unknown",
                training_metrics=results.get("training", {}),
                backtest_metrics=results.get("backtest", {}),
            )
            prompt = get_assessment_prompt(context)

            # Use injected invoker (for testing) or create new with resolved model
            if self._injected_invoker is not None:
                invoker = self._injected_invoker
            else:
                # Create invoker with resolved model config (Task 8.3 runtime selection)
                config = AnthropicInvokerConfig(model=resolved_model)
                invoker = AnthropicAgentInvoker(config=config)

            # Run Claude
            result = await invoker.run(
                prompt=prompt,
                tools=AGENT_TOOLS,
                system_prompt=ASSESSMENT_SYSTEM_PROMPT,
                tool_executor=self.tool_executor,
            )

            if not result.success:
                raise WorkerError(f"Claude assessment failed: {result.error}")

            # Get assessment from tool executor
            assessment = self.tool_executor.last_saved_assessment
            assessment_path = self.tool_executor.last_saved_assessment_path

            if not assessment:
                raise WorkerError("Claude did not save an assessment")

            # Build result
            assessment_result = {
                "success": True,
                "verdict": assessment["verdict"],
                "strengths": assessment["strengths"],
                "weaknesses": assessment["weaknesses"],
                "suggestions": assessment["suggestions"],
                "assessment_path": assessment_path,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            # Complete child operation
            await self.ops.complete_operation(op.operation_id, assessment_result)

            logger.info(
                f"Assessment phase completed: verdict={assessment['verdict']}, "
                f"input_tokens={result.input_tokens}, output_tokens={result.output_tokens}"
            )

            return assessment_result

        except asyncio.CancelledError:
            await self.ops.cancel_operation(op.operation_id, "Parent cancelled")
            raise
        except WorkerError as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise
        except Exception as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise WorkerError(f"Assessment failed: {e}") from e
