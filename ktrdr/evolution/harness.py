"""Generation harness — orchestrates one generation of researchers.

Triggers research cycles via HTTP, polls for completion, extracts results,
and scores fitness. This is the core integration connecting all evolution
components to the existing research pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Protocol

from ktrdr.evolution.brief import BriefTranslator
from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS, FitnessEvaluator
from ktrdr.evolution.genome import Researcher
from ktrdr.evolution.tracker import EvolutionTracker

logger = logging.getLogger(__name__)

# Maximum backoff between retries on at_capacity (seconds)
_MAX_BACKOFF = 300  # 5 minutes


class HttpClient(Protocol):
    """Protocol for HTTP client (httpx.AsyncClient compatible)."""

    async def post(self, url: str, **kwargs: Any) -> Any: ...
    async def get(self, url: str, **kwargs: Any) -> Any: ...


class BudgetExhaustedError(Exception):
    """Raised when the trigger API reports budget exhaustion."""


def _to_dict(response: Any) -> dict[str, Any]:
    """Extract dict from an HTTP response.

    Handles both httpx.Response objects (real HTTP) and plain dicts (test mocks).
    """
    if isinstance(response, dict):
        return response
    # httpx.Response — call .json()
    return response.json()


class GenerationHarness:
    """Orchestrates one generation: trigger → poll → score.

    Uses HTTP to communicate with the research pipeline. All state
    is persisted via EvolutionTracker for crash recovery.
    """

    def __init__(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        http_client: HttpClient,
        base_url: str = "http://localhost:8000",
    ) -> None:
        self._config = config
        self._tracker = tracker
        self._client = http_client
        self._base_url = base_url
        self._brief_translator = BriefTranslator()
        self._fitness = FitnessEvaluator(config)

    async def run_generation(
        self,
        generation: int,
        population: list[Researcher],
    ) -> list[dict[str, Any]]:
        """Run one generation: trigger all researchers, poll, score.

        Returns a list of result dicts, one per researcher, containing
        researcher_id, fitness, and backtest_result.
        """
        # Phase 1: Trigger all researchers
        operation_map: dict[str, str] = {}  # researcher_id → operation_id
        aborted = False

        for researcher in population:
            try:
                op_id = await self._trigger_researcher(generation, researcher)
                operation_map[researcher.id] = op_id
            except BudgetExhaustedError:
                logger.warning("Budget exhausted — aborting generation %d", generation)
                aborted = True
                break

        # If budget exhausted, all remaining researchers get minimum fitness
        if aborted:
            return [
                {
                    "researcher_id": r.id,
                    "fitness": MINIMUM_FITNESS,
                    "backtest_result": None,
                }
                for r in population
            ]

        # Phase 2: Poll all operations and collect results
        results: list[dict[str, Any]] = []
        for researcher in population:
            op_id = operation_map[researcher.id]
            backtest_result = await self._poll_operation(op_id)
            fitness = self._fitness.evaluate(backtest_result)
            results.append(
                {
                    "researcher_id": researcher.id,
                    "fitness": fitness,
                    "backtest_result": backtest_result,
                }
            )

        return results

    async def _trigger_researcher(
        self, generation: int, researcher: Researcher
    ) -> str:
        """Trigger a research cycle for one researcher.

        Retries on at_capacity with exponential backoff.
        Raises BudgetExhaustedError on budget_exhausted.
        Persists operation ID to tracker immediately after success.
        """
        brief = self._brief_translator.translate(researcher.genome, self._config)
        backoff = 1.0

        while True:
            raw_response = await self._client.post(
                f"{self._base_url}/api/v1/agent/trigger",
                json={"model": self._config.model, "brief": brief},
            )
            data = _to_dict(raw_response)

            if data.get("triggered"):
                op_id = data["operation_id"]
                # Persist immediately for crash safety
                self._tracker.save_operation_id(generation, researcher.id, op_id)
                logger.info(
                    "Triggered %s → %s", researcher.id, op_id
                )
                return op_id

            reason = data.get("reason", "unknown")

            if reason == "budget_exhausted":
                raise BudgetExhaustedError()

            if reason == "at_capacity":
                logger.info(
                    "At capacity, retrying %s in %.0fs", researcher.id, backoff
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue

            # Unknown rejection — treat as fatal for this researcher
            logger.warning(
                "Unexpected trigger rejection for %s: %s", researcher.id, reason
            )
            raise BudgetExhaustedError()

    async def _poll_operation(self, operation_id: str) -> dict[str, Any] | None:
        """Poll an operation until completed or failed.

        Returns the backtest_result dict, or None if failed.
        """
        while True:
            raw_response = await self._client.get(
                f"{self._base_url}/api/v1/operations/{operation_id}",
            )
            data = _to_dict(raw_response)

            status = data.get("status")

            if status == "completed":
                # Extract backtest_result from operation metadata
                metadata = data.get("metadata", {})
                params = metadata.get("parameters", {})
                return params.get("backtest_result")

            if status == "failed":
                logger.warning("Operation %s failed", operation_id)
                return None

            # Still running — wait and poll again
            if self._config.poll_interval > 0:
                await asyncio.sleep(self._config.poll_interval)
