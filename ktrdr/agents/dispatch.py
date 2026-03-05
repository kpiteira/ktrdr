"""Agent dispatch service — HTTP dispatch to containerized agent workers.

Selects agent workers from the registry and dispatches design/assessment
operations via HTTP, following the same pattern as training/backtest dispatch.
"""

from typing import Any

import httpx

from ktrdr import get_logger
from ktrdr.api.models.workers import WorkerType

logger = get_logger(__name__)


class AgentDispatchService:
    """Dispatches agent operations to containerized workers via HTTP.

    Follows the same pattern as training/backtest dispatch:
    1. Select worker from registry (LRU round-robin)
    2. POST start request to worker endpoint
    3. Return operation_id for polling

    Args:
        worker_registry: WorkerRegistry instance for worker selection.
    """

    def __init__(self, worker_registry: Any) -> None:
        self._registry = worker_registry

    async def dispatch_design(
        self,
        *,
        task_id: str,
        brief: str,
        symbol: str,
        timeframe: str,
        experiment_context: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch a design operation to a container worker.

        Args:
            task_id: Backend operation ID for synchronization.
            brief: Research brief describing what to design.
            symbol: Target symbol (e.g., EURUSD).
            timeframe: Primary timeframe (e.g., 1h).
            experiment_context: Optional summary of past experiments.

        Returns:
            Dict with operation_id, success, status from the worker.

        Raises:
            RuntimeError: If no AGENT_DESIGN workers are available.
        """
        worker = self._registry.select_worker(WorkerType.AGENT_DESIGN)
        if not worker:
            raise RuntimeError(
                "No available AGENT_DESIGN workers. "
                "Ensure design agent containers are running and registered."
            )

        payload = {
            "task_id": task_id,
            "brief": brief,
            "symbol": symbol,
            "timeframe": timeframe,
        }
        if experiment_context:
            payload["experiment_context"] = experiment_context

        url = f"{worker.endpoint_url}/designs/start"
        logger.info(
            f"Dispatching design to worker {worker.worker_id} at {url} "
            f"(task_id={task_id})"
        )

        # Timeout is for the dispatch handshake only (accepting the work),
        # not for the full operation which runs asynchronously (3-10 min).
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        operation_id = result.get("operation_id")
        if not operation_id:
            raise RuntimeError("Design worker did not return operation_id")

        logger.info(f"Design accepted by worker {worker.worker_id}: op={operation_id}")
        result["worker_endpoint"] = worker.endpoint_url
        return result

    async def dispatch_assessment(
        self,
        *,
        task_id: str,
        strategy_name: str,
        training_metrics: dict[str, Any],
        backtest_results: dict[str, Any],
        strategy_config: dict[str, Any] | None = None,
        experiment_history: str | None = None,
    ) -> dict[str, Any]:
        """Dispatch an assessment operation to a container worker.

        Args:
            task_id: Backend operation ID for synchronization.
            strategy_name: Name of the strategy to assess.
            training_metrics: Training metrics (accuracy, loss, etc.).
            backtest_results: Backtest results (sharpe, max_dd, etc.).
            strategy_config: Optional strategy YAML config as dict.
            experiment_history: Optional summary of past experiments.

        Returns:
            Dict with operation_id, success, status from the worker.

        Raises:
            RuntimeError: If no AGENT_ASSESSMENT workers are available.
        """
        worker = self._registry.select_worker(WorkerType.AGENT_ASSESSMENT)
        if not worker:
            raise RuntimeError(
                "No available AGENT_ASSESSMENT workers. "
                "Ensure assessment agent containers are running and registered."
            )

        payload: dict[str, Any] = {
            "task_id": task_id,
            "strategy_name": strategy_name,
            "training_metrics": training_metrics,
            "backtest_results": backtest_results,
        }
        if strategy_config:
            payload["strategy_config"] = strategy_config
        if experiment_history:
            payload["experiment_history"] = experiment_history

        url = f"{worker.endpoint_url}/assessments/start"
        logger.info(
            f"Dispatching assessment to worker {worker.worker_id} at {url} "
            f"(task_id={task_id}, strategy={strategy_name})"
        )

        # Timeout is for the dispatch handshake only (accepting the work),
        # not for the full operation which runs asynchronously (3-10 min).
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            result = response.json()

        operation_id = result.get("operation_id")
        if not operation_id:
            raise RuntimeError("Assessment worker did not return operation_id")

        logger.info(
            f"Assessment accepted by worker {worker.worker_id}: op={operation_id}"
        )
        result["worker_endpoint"] = worker.endpoint_url
        return result
