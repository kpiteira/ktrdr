"""Design worker that uses Claude to create strategies.

Task 2.1: Real design worker using AnthropicAgentInvoker.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from ktrdr import get_logger
from ktrdr.agents.executor import ToolExecutor, get_indicators_from_api
from ktrdr.agents.invoker import AnthropicAgentInvoker
from ktrdr.agents.prompts import TriggerReason, get_strategy_designer_prompt
from ktrdr.agents.strategy_utils import get_recent_strategies
from ktrdr.agents.tools import DESIGN_PHASE_TOOLS
from ktrdr.api.models.operations import OperationMetadata, OperationType
from ktrdr.data.repository.data_repository import DataRepository

if TYPE_CHECKING:
    from ktrdr.api.services.operations_service import OperationsService

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""

    pass


class AgentDesignWorker:
    """Worker that uses Claude to design trading strategies.

    This worker:
    1. Creates a child AGENT_DESIGN operation
    2. Builds a design prompt with context (indicators, symbols, recent strategies)
    3. Calls Claude via AnthropicAgentInvoker
    4. Saves strategy via save_strategy_config tool
    5. Returns strategy name, path, and token counts

    Attributes:
        SYSTEM_PROMPT: System prompt for the strategy designer.
    """

    SYSTEM_PROMPT = """You are an expert trading strategy designer. Your goal is to create
novel, well-reasoned trading strategies that can be trained and backtested.

You have access to tools for:
- Viewing available indicators and symbols
- Validating strategy configurations
- Saving strategy configurations to disk

Design strategies that are:
- Novel (different from recent strategies)
- Well-reasoned (clear hypothesis about why it should work)
- Testable (uses available indicators and symbols)
- Realistic (reasonable parameter values)

Always validate your configuration before saving it."""

    def __init__(
        self,
        operations_service: OperationsService,
        invoker: AnthropicAgentInvoker | None = None,
    ):
        """Initialize the design worker.

        Args:
            operations_service: Service for tracking operations.
            invoker: Optional invoker instance. Created if not provided.
        """
        self.ops = operations_service
        self.invoker = invoker or AnthropicAgentInvoker()
        self.tool_executor = ToolExecutor()
        self.repository = DataRepository()

    def _get_available_symbols(self) -> list[dict[str, Any]]:
        """Get available symbols with their timeframes from cached data.

        Returns:
            List of symbol dicts with symbol name and available timeframes.
        """
        try:
            # Get (symbol, timeframe) tuples from repository
            data_files = self.repository.get_available_data_files()

            # Group by symbol
            symbol_timeframes: dict[str, list[str]] = defaultdict(list)
            for symbol, timeframe in data_files:
                symbol_timeframes[symbol].append(timeframe)

            # Format for prompt
            result = []
            for symbol, timeframes in sorted(symbol_timeframes.items()):
                result.append(
                    {
                        "symbol": symbol,
                        "timeframes": sorted(timeframes),
                        "date_range": {"start": "cached", "end": "cached"},
                    }
                )

            return result
        except Exception as e:
            logger.warning(f"Failed to get available symbols: {e}")
            return []

    async def _get_available_indicators(self) -> list[dict[str, Any]]:
        """Get available indicators from the KTRDR API.

        Task 8.1: Gather indicators upfront to embed in prompt, avoiding
        tool call round trips that compound token usage.

        Returns:
            List of indicator dicts with name, type, and parameters.
        """
        try:
            indicators = await get_indicators_from_api()
            logger.info(f"Gathered {len(indicators)} available indicators")
            return indicators
        except Exception as e:
            logger.warning(f"Failed to get available indicators: {e}")
            return []

    async def _get_recent_strategies(self, limit: int = 5) -> list[dict[str, Any]]:
        """Get recent strategies to avoid repetition.

        Task 8.1: Gather recent strategies upfront to embed in prompt, avoiding
        tool call round trips that compound token usage.

        Args:
            limit: Maximum number of recent strategies to return.

        Returns:
            List of recent strategy summaries.
        """
        try:
            strategies = await get_recent_strategies(n=limit)
            logger.info(f"Gathered {len(strategies)} recent strategies")
            return strategies
        except Exception as e:
            logger.warning(f"Failed to get recent strategies: {e}")
            return []

    async def run(self, parent_operation_id: str) -> dict[str, Any]:
        """Run design phase using Claude.

        Creates a child AGENT_DESIGN operation, calls Claude with the design
        prompt, and returns the strategy info.

        Args:
            parent_operation_id: The parent AGENT_RESEARCH operation ID.

        Returns:
            Dict with strategy_name, strategy_path, and token counts.

        Raises:
            WorkerError: If design fails or no strategy is saved.
            asyncio.CancelledError: If cancelled.
        """
        logger.info(f"Starting design phase: {parent_operation_id}")

        # Create child operation for tracking
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(  # type: ignore[call-arg]
                parameters={"parent_operation_id": parent_operation_id}
            ),
        )

        try:
            # Task 8.1: Gather ALL context upfront to embed in prompt
            # This avoids discovery tool calls that compound token usage
            available_symbols = self._get_available_symbols()
            available_indicators = await self._get_available_indicators()
            recent_strategies = await self._get_recent_strategies(limit=5)

            logger.info(
                f"Context gathered: {len(available_symbols)} symbols, "
                f"{len(available_indicators)} indicators, "
                f"{len(recent_strategies)} recent strategies"
            )

            # Build prompt with ALL context embedded
            prompt_data = get_strategy_designer_prompt(
                trigger_reason=TriggerReason.START_NEW_CYCLE,
                operation_id=op.operation_id,
                phase="designing",
                available_symbols=available_symbols,
                available_indicators=available_indicators,
                recent_strategies=recent_strategies,
            )

            # Run Claude with reduced tool set (Task 8.2)
            # Discovery tools removed - context already embedded in prompt
            result = await self.invoker.run(
                prompt=prompt_data["user"],
                tools=DESIGN_PHASE_TOOLS,
                system_prompt=prompt_data["system"],
                tool_executor=self.tool_executor,
            )

            if not result.success:
                raise WorkerError(f"Claude design failed: {result.error}")

            # Get strategy info from tool executor
            strategy_name = self.tool_executor.last_saved_strategy_name
            strategy_path = self.tool_executor.last_saved_strategy_path

            if not strategy_name:
                raise WorkerError("Claude did not save a strategy configuration")

            # Build result
            design_result = {
                "success": True,
                "strategy_name": strategy_name,
                "strategy_path": strategy_path,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            # Complete child operation
            await self.ops.complete_operation(op.operation_id, design_result)

            logger.info(
                f"Design phase completed: strategy_name={strategy_name}, "
                f"input_tokens={result.input_tokens}, output_tokens={result.output_tokens}"
            )

            return design_result

        except asyncio.CancelledError:
            await self.ops.cancel_operation(op.operation_id, "Parent cancelled")
            raise
        except WorkerError as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise
        except Exception as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise WorkerError(f"Design failed: {e}") from e
