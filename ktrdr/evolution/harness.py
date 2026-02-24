"""Generation harness — orchestrates evolution across generations.

Triggers research cycles via HTTP, polls for completion, extracts results,
and scores fitness. The run() method drives the full evolution loop:
seed → run_generation → select → reproduce → save → repeat.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Protocol

from ktrdr.evolution.brief import BriefTranslator
from ktrdr.evolution.config import DateRange, EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS, FitnessEvaluator
from ktrdr.evolution.genome import Researcher
from ktrdr.evolution.tracker import EvolutionTracker

if TYPE_CHECKING:
    from ktrdr.evolution.population import PopulationManager

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

    async def run(self, population_manager: PopulationManager) -> None:
        """Execute the full multi-generation evolution loop.

        Seed → run_generation → select → reproduce → save → repeat.
        Updates summary.yaml incrementally after each generation.
        """
        # Seed generation 0
        population = population_manager.seed(self._config)
        self._tracker.save_population(0, population)
        logger.info("Seeded %d researchers for generation 0", len(population))

        for gen in range(self._config.generations):
            logger.info("=== Generation %d ===", gen)

            # Run this generation
            results = await self.run_generation(gen, population)
            self._tracker.save_results(gen, results)

            # Update summary
            self._update_summary(gen, results)

            # Check if budget was exhausted (all results are MINIMUM_FITNESS)
            all_failed = all(r["fitness"] == MINIMUM_FITNESS for r in results)
            if all_failed and gen < self._config.generations - 1:
                logger.warning(
                    "All researchers failed in generation %d — aborting run", gen
                )
                break

            # Selection + reproduction for next generation
            if gen < self._config.generations - 1:
                survivor_ids, dead_ids = population_manager.select(
                    results, kill_rate=self._config.kill_rate
                )
                logger.info(
                    "Generation %d: %d survived, %d died",
                    gen,
                    len(survivor_ids),
                    len(dead_ids),
                )

                # Get survivor Researcher objects
                survivor_map = {r.id: r for r in population}
                survivors = [survivor_map[sid] for sid in survivor_ids]

                # Reproduce
                next_gen = gen + 1
                population = population_manager.reproduce(
                    survivors,
                    generation=next_gen,
                    seed=self._config.seed,
                )
                self._tracker.save_population(next_gen, population)

    async def resume(self, population_manager: PopulationManager) -> None:
        """Resume a crashed or stopped evolution run.

        Loads state from tracker, finds the last completed generation,
        handles any incomplete generation, and continues the loop.
        """
        last_completed = self._tracker.get_last_completed_generation()

        if (
            last_completed is not None
            and last_completed >= self._config.generations - 1
        ):
            logger.info("Run already complete (%d generations)", last_completed + 1)
            return

        # Determine where to start
        if last_completed is None:
            start_gen = 0
        else:
            start_gen = last_completed + 1

        # Check for incomplete generation (has operations but no results)
        incomplete_gen = self._find_incomplete_generation(start_gen)
        if incomplete_gen is not None:
            population = self._tracker.load_population(incomplete_gen)
            if population:
                results = await self._recover_incomplete_generation(
                    incomplete_gen, population
                )
                self._tracker.save_results(incomplete_gen, results)
                self._update_summary(incomplete_gen, results)
                start_gen = incomplete_gen + 1

        # Continue with remaining generations
        for gen in range(start_gen, self._config.generations):
            # Load or create population for this generation
            population = self._tracker.load_population(gen)
            if not population:
                # Need to derive population from previous generation
                if gen == 0:
                    population = population_manager.seed(self._config)
                else:
                    prev_results = self._tracker.load_results(gen - 1)
                    prev_pop = self._tracker.load_population(gen - 1)
                    survivor_ids, _ = population_manager.select(
                        prev_results, kill_rate=self._config.kill_rate
                    )
                    survivor_map = {r.id: r for r in prev_pop}
                    survivors = [survivor_map[sid] for sid in survivor_ids]
                    population = population_manager.reproduce(
                        survivors, generation=gen, seed=self._config.seed
                    )
                self._tracker.save_population(gen, population)

            results = await self.run_generation(gen, population)
            self._tracker.save_results(gen, results)
            self._update_summary(gen, results)

            # Abort if all failed
            all_failed = all(r["fitness"] == MINIMUM_FITNESS for r in results)
            if all_failed and gen < self._config.generations - 1:
                logger.warning(
                    "All researchers failed in generation %d — aborting", gen
                )
                break

            # Selection + reproduction for next gen
            if gen < self._config.generations - 1:
                survivor_ids, dead_ids = population_manager.select(
                    results, kill_rate=self._config.kill_rate
                )
                survivor_map = {r.id: r for r in population}
                survivors = [survivor_map[sid] for sid in survivor_ids]
                next_pop = population_manager.reproduce(
                    survivors, generation=gen + 1, seed=self._config.seed
                )
                self._tracker.save_population(gen + 1, next_pop)

    def _find_incomplete_generation(self, start_gen: int) -> int | None:
        """Check if start_gen has operations but no results (incomplete)."""
        ops = self._tracker.load_operations(start_gen)
        results = self._tracker.load_results(start_gen)
        if ops and not results:
            return start_gen
        return None

    async def _recover_incomplete_generation(
        self, generation: int, population: list[Researcher]
    ) -> list[dict[str, Any]]:
        """Recover an incomplete generation by polling/re-triggering ops.

        For each researcher: check operation status, poll if running,
        re-trigger if failed/missing.
        """
        ops = self._tracker.load_operations(generation)
        results: list[dict[str, Any]] = []

        for researcher in population:
            op_id = ops.get(researcher.id)

            if op_id is None:
                # Never triggered — trigger now
                try:
                    new_op_id = await self._trigger_researcher(generation, researcher)
                    if new_op_id:
                        backtest_result = await self._poll_operation(new_op_id)
                        fitness = self._fitness.evaluate(backtest_result)
                        results.append(
                            {
                                "researcher_id": researcher.id,
                                "fitness": fitness,
                                "backtest_result": backtest_result,
                            }
                        )
                    else:
                        results.append(
                            {
                                "researcher_id": researcher.id,
                                "fitness": MINIMUM_FITNESS,
                                "backtest_result": None,
                            }
                        )
                except BudgetExhaustedError:
                    results.append(
                        {
                            "researcher_id": researcher.id,
                            "fitness": MINIMUM_FITNESS,
                            "backtest_result": None,
                        }
                    )
                continue

            # Has operation — check status
            backtest_result = await self._poll_operation(op_id)
            if backtest_result is not None:
                fitness = self._fitness.evaluate(backtest_result)
                results.append(
                    {
                        "researcher_id": researcher.id,
                        "fitness": fitness,
                        "backtest_result": backtest_result,
                    }
                )
            else:
                # Failed — re-trigger
                try:
                    new_op_id = await self._trigger_researcher(generation, researcher)
                    if new_op_id:
                        backtest_result = await self._poll_operation(new_op_id)
                        fitness = self._fitness.evaluate(backtest_result)
                        results.append(
                            {
                                "researcher_id": researcher.id,
                                "fitness": fitness,
                                "backtest_result": backtest_result,
                            }
                        )
                    else:
                        results.append(
                            {
                                "researcher_id": researcher.id,
                                "fitness": MINIMUM_FITNESS,
                                "backtest_result": None,
                            }
                        )
                except BudgetExhaustedError:
                    results.append(
                        {
                            "researcher_id": researcher.id,
                            "fitness": MINIMUM_FITNESS,
                            "backtest_result": None,
                        }
                    )

        return results

    def _update_summary(self, generation: int, results: list[dict[str, Any]]) -> None:
        """Update the cross-generation summary with stats for this generation."""
        summary = self._tracker.load_summary()
        if "generations" not in summary:
            summary["generations"] = []

        fitnesses = [r["fitness"] for r in results]
        real_fitnesses = [f for f in fitnesses if f > MINIMUM_FITNESS]

        gen_stats: dict[str, Any] = {
            "generation": generation,
            "population_size": len(results),
            "mean_fitness": sum(fitnesses) / len(fitnesses) if fitnesses else 0.0,
            "max_fitness": max(fitnesses) if fitnesses else MINIMUM_FITNESS,
            "min_fitness": min(fitnesses) if fitnesses else MINIMUM_FITNESS,
            "successful": len(real_fitnesses),
            "failed": len(fitnesses) - len(real_fitnesses),
        }
        summary["generations"].append(gen_stats)
        self._tracker.save_summary(summary)

    async def run_generation(
        self,
        generation: int,
        population: list[Researcher],
    ) -> list[dict[str, Any]]:
        """Run one generation: trigger all researchers, poll, score.

        Returns a list of result dicts, one per researcher, containing
        researcher_id, fitness, backtest_result (first slice), and
        slice_results (all slices including additional backtests).
        """
        # Phase 1: Trigger all researchers
        operation_map: dict[str, str] = {}  # researcher_id → operation_id
        aborted = False

        for researcher in population:
            try:
                op_id = await self._trigger_researcher(generation, researcher)
                if op_id is not None:
                    operation_map[researcher.id] = op_id
                # else: researcher rejected (non-budget) — gets MINIMUM_FITNESS
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
                    "slice_results": [],
                }
                for r in population
            ]

        # Phase 2: Poll, run additional backtests, score
        results: list[dict[str, Any]] = []
        for researcher in population:
            op_id = operation_map.get(researcher.id)
            if op_id is None:
                results.append(
                    {
                        "researcher_id": researcher.id,
                        "fitness": MINIMUM_FITNESS,
                        "backtest_result": None,
                        "slice_results": [],
                    }
                )
                continue

            # Poll research operation (get full operation data)
            op_data = await self._poll_until_terminal(op_id)
            if op_data is None:
                results.append(
                    {
                        "researcher_id": researcher.id,
                        "fitness": MINIMUM_FITNESS,
                        "backtest_result": None,
                        "slice_results": [],
                    }
                )
                continue

            backtest_result = self._extract_backtest_result(op_data)
            slice_results: list[dict[str, Any]] = (
                [backtest_result] if backtest_result else []
            )

            # Run additional backtests if we have strategy metadata
            model_path, strategy_name = self._extract_metadata(op_data)
            if backtest_result and strategy_name:
                additional = await self._run_additional_backtests(
                    model_path, strategy_name
                )
                slice_results.extend(additional)

            fitness = self._fitness.evaluate_slices(slice_results)
            results.append(
                {
                    "researcher_id": researcher.id,
                    "fitness": fitness,
                    "backtest_result": backtest_result,
                    "slice_results": slice_results,
                }
            )

        return results

    async def _trigger_researcher(
        self, generation: int, researcher: Researcher
    ) -> str | None:
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
                logger.info("Triggered %s → %s", researcher.id, op_id)
                return op_id

            reason = data.get("reason", "unknown")

            if reason == "budget_exhausted":
                raise BudgetExhaustedError()

            if reason == "at_capacity":
                logger.info("At capacity, retrying %s in %.0fs", researcher.id, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF)
                continue

            # Unknown rejection — fatal for this researcher, not the generation
            logger.warning(
                "Unexpected trigger rejection for %s: %s", researcher.id, reason
            )
            return None

    async def _poll_until_terminal(self, operation_id: str) -> dict[str, Any] | None:
        """Poll an operation until completed or failed.

        Returns the full operation data dict on completion, None on failure.
        """
        while True:
            raw_response = await self._client.get(
                f"{self._base_url}/api/v1/operations/{operation_id}",
            )
            data = _to_dict(raw_response)

            # Operations API wraps response in {"success": ..., "data": {...}}
            op = data.get("data", data)
            status = op.get("status")

            if status == "completed":
                return op

            if status == "failed":
                logger.warning("Operation %s failed", operation_id)
                return None

            # Still running — wait and poll again
            if self._config.poll_interval > 0:
                await asyncio.sleep(self._config.poll_interval)

    async def _poll_operation(self, operation_id: str) -> dict[str, Any] | None:
        """Poll an operation and extract backtest_result.

        Convenience wrapper around _poll_until_terminal for callers that
        only need the backtest result (e.g. resume recovery, additional backtests).
        """
        op = await self._poll_until_terminal(operation_id)
        return self._extract_backtest_result(op) if op else None

    @staticmethod
    def _extract_backtest_result(
        op_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Extract backtest_result from completed operation data."""
        result_summary = op_data.get("result_summary", {})
        if result_summary:
            return result_summary.get("backtest_result")
        return None

    @staticmethod
    def _extract_metadata(
        op_data: dict[str, Any],
    ) -> tuple[str | None, str | None]:
        """Extract model_path and strategy_name from operation data.

        Checks metadata.parameters first (set by research worker in-memory),
        then falls back to result_summary (always persisted by the API).
        model_path is optional — the backtest API can auto-discover it
        from strategy_name.
        """
        metadata = op_data.get("metadata", {})
        params = metadata.get("parameters", {})
        result_summary = op_data.get("result_summary", {}) or {}

        model_path = params.get("model_path")
        strategy_name = params.get("strategy_name") or result_summary.get(
            "strategy_name"
        )
        return model_path, strategy_name

    async def _trigger_backtest(
        self,
        model_path: str | None,
        strategy_name: str,
        date_range: DateRange,
    ) -> str | None:
        """Trigger a single backtest via the backtest API.

        Returns the operation_id on success, None on failure.
        model_path is optional — the backtest API can auto-discover it.
        """
        payload: dict[str, Any] = {
            "strategy_name": strategy_name,
            "symbol": self._config.symbol,
            "timeframe": self._config.timeframe,
            "start_date": date_range.start.isoformat(),
            "end_date": date_range.end.isoformat(),
        }
        if model_path:
            payload["model_path"] = model_path
        raw_response = await self._client.post(
            f"{self._base_url}/api/v1/backtests/start",
            json=payload,
        )
        data = _to_dict(raw_response)
        if data.get("success"):
            return data.get("operation_id")
        logger.warning("Backtest trigger failed: %s", data)
        return None

    async def _run_single_backtest(
        self,
        model_path: str | None,
        strategy_name: str,
        date_range: DateRange,
    ) -> dict[str, Any] | None:
        """Run a single backtest and return the result. Retries once on failure."""
        for attempt in range(2):
            op_id = await self._trigger_backtest(model_path, strategy_name, date_range)
            if op_id is None:
                if attempt == 0:
                    logger.info("Backtest trigger failed for %s, retrying", date_range)
                    continue
                return None

            result = await self._poll_operation(op_id)
            if result is not None:
                return result

            if attempt == 0:
                logger.info("Backtest %s failed, retrying", op_id)
        return None

    async def _run_additional_backtests(
        self,
        model_path: str | None,
        strategy_name: str,
    ) -> list[dict[str, Any]]:
        """Run additional backtests for fitness slices beyond the first.

        Returns list of backtest_result dicts (one per successful slice).
        Failed slices are omitted — the fitness evaluator handles partial data.
        """
        additional_slices = self._config.fitness_slices[1:]
        results: list[dict[str, Any]] = []

        for slice_range in additional_slices:
            result = await self._run_single_backtest(
                model_path, strategy_name, slice_range
            )
            if result is not None:
                results.append(result)
            else:
                logger.warning(
                    "Additional backtest failed for %s after retry", slice_range
                )

        return results
