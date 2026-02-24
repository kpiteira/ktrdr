"""Tests for generation harness — the orchestrator."""

from __future__ import annotations

import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from ktrdr.evolution.config import DateRange, EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS
from ktrdr.evolution.genome import Genome, Researcher, TraitLevel
from ktrdr.evolution.harness import GenerationHarness
from ktrdr.evolution.population import PopulationManager
from ktrdr.evolution.tracker import EvolutionTracker

# Single-slice config avoids additional backtest calls in basic tests
_SINGLE_SLICE = [DateRange(date(2021, 1, 1), date(2022, 6, 30))]


@pytest.fixture
def tmp_run_dir() -> Path:
    """Create a temporary run directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "run_test"


@pytest.fixture
def config() -> EvolutionConfig:
    """Config with fast poll interval and single slice for basic tests."""
    return EvolutionConfig(
        population_size=3, seed=42, poll_interval=0, fitness_slices=_SINGLE_SLICE
    )


@pytest.fixture
def tracker(tmp_run_dir: Path) -> EvolutionTracker:
    return EvolutionTracker(run_dir=tmp_run_dir)


@pytest.fixture
def sample_population() -> list[Researcher]:
    """3 researchers for testing."""
    return [
        Researcher(
            id="r_g00_000",
            genome=Genome(TraitLevel.OFF, TraitLevel.LOW, TraitLevel.HIGH),
            generation=0,
        ),
        Researcher(
            id="r_g00_001",
            genome=Genome(TraitLevel.HIGH, TraitLevel.HIGH, TraitLevel.OFF),
            generation=0,
        ),
        Researcher(
            id="r_g00_002",
            genome=Genome(TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
            generation=0,
        ),
    ]


def _make_trigger_response(op_id: str) -> dict[str, Any]:
    """Successful trigger response."""
    return {"triggered": True, "operation_id": op_id}


def _make_completed_operation(
    op_id: str, sharpe: float = 1.0, max_dd: float = 0.1
) -> dict[str, Any]:
    """Completed operation response with backtest result.

    Mirrors real API: backtest_result is in result_summary (persisted
    by complete_operation), not in metadata.parameters (in-memory only).
    Includes total_trades for gate checks (M3 fitness gates).
    """
    return {
        "operation_id": op_id,
        "status": "completed",
        "result_summary": {
            "success": True,
            "backtest_result": {
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "total_trades": 50,
            },
        },
        "metadata": {
            "parameters": {
                "model_path": "/models/test",
                "strategy_name": "test_strategy",
            }
        },
    }


def _make_failed_operation(op_id: str) -> dict[str, Any]:
    """Failed operation response."""
    return {
        "operation_id": op_id,
        "status": "failed",
        "metadata": {"parameters": {}},
    }


class TestGenerationHarnessTrigger:
    """Tests for trigger behavior."""

    @pytest.mark.asyncio
    async def test_trigger_persists_operation_id(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        sample_population: list[Researcher],
    ) -> None:
        """Operation IDs should be persisted to tracker after trigger."""
        mock_client = AsyncMock()
        # Trigger succeeds for all 3
        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_000"),
                _make_trigger_response("op_001"),
                _make_trigger_response("op_002"),
            ]
        )
        # All complete immediately
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_000"),
                _make_completed_operation("op_001"),
                _make_completed_operation("op_002"),
            ]
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        await harness.run_generation(0, sample_population)

        ops = tracker.load_operations(0)
        assert ops["r_g00_000"] == "op_000"
        assert ops["r_g00_001"] == "op_001"
        assert ops["r_g00_002"] == "op_002"

    @pytest.mark.asyncio
    async def test_trigger_at_capacity_retries(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        sample_population: list[Researcher],
    ) -> None:
        """at_capacity response should trigger retry."""
        mock_client = AsyncMock()
        # First researcher: at_capacity then success
        mock_client.post = AsyncMock(
            side_effect=[
                {"triggered": False, "reason": "at_capacity"},
                _make_trigger_response("op_000"),
                _make_trigger_response("op_001"),
                _make_trigger_response("op_002"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_000"),
                _make_completed_operation("op_001"),
                _make_completed_operation("op_002"),
            ]
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        await harness.run_generation(0, sample_population)

        # Should have been called 4 times (1 retry + 3 successes)
        assert mock_client.post.call_count == 4

    @pytest.mark.asyncio
    async def test_trigger_budget_exhausted_aborts(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        sample_population: list[Researcher],
    ) -> None:
        """budget_exhausted should abort the generation."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            return_value={"triggered": False, "reason": "budget_exhausted"}
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, sample_population)

        # All researchers should get minimum fitness
        for r in results:
            assert r["fitness"] == MINIMUM_FITNESS


class TestGenerationHarnessPoll:
    """Tests for polling behavior."""

    @pytest.mark.asyncio
    async def test_completed_operation_extracts_result(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
    ) -> None:
        """Completed operation should extract backtest_result."""
        population = [
            Researcher(
                id="r_g00_000",
                genome=Genome(TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
                generation=0,
            ),
        ]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_make_trigger_response("op_000"))
        mock_client.get = AsyncMock(
            return_value=_make_completed_operation("op_000", sharpe=1.5, max_dd=0.1)
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, population)

        assert len(results) == 1
        assert results[0]["researcher_id"] == "r_g00_000"
        # M3 fitness: 1.5 - 1.0*0.1 - 0.1*0.5(complexity) = 1.35
        assert abs(results[0]["fitness"] - 1.35) < 1e-9

    @pytest.mark.asyncio
    async def test_failed_operation_returns_minimum_fitness(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
    ) -> None:
        """Failed operation should get minimum fitness."""
        population = [
            Researcher(
                id="r_g00_000",
                genome=Genome(TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
                generation=0,
            ),
        ]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_make_trigger_response("op_000"))
        mock_client.get = AsyncMock(return_value=_make_failed_operation("op_000"))

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, population)

        assert results[0]["fitness"] == MINIMUM_FITNESS

    @pytest.mark.asyncio
    async def test_completed_operation_with_api_envelope(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
    ) -> None:
        """Operations API wraps responses in {success, data} — harness should unwrap."""
        population = [
            Researcher(
                id="r_g00_000",
                genome=Genome(TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
                generation=0,
            ),
        ]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_make_trigger_response("op_000"))
        # Wrap in API envelope like real backend does
        mock_client.get = AsyncMock(
            return_value={
                "success": True,
                "data": _make_completed_operation("op_000", sharpe=2.0, max_dd=0.05),
            }
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, population)

        assert len(results) == 1
        # M3 fitness: 2.0 - 1.0*0.05 - 0.1*0.5(complexity) = 1.9
        assert abs(results[0]["fitness"] - 1.9) < 1e-9

    @pytest.mark.asyncio
    async def test_failed_operation_with_api_envelope(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
    ) -> None:
        """Failed operation with API envelope should return minimum fitness."""
        population = [
            Researcher(
                id="r_g00_000",
                genome=Genome(TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
                generation=0,
            ),
        ]
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=_make_trigger_response("op_000"))
        mock_client.get = AsyncMock(
            return_value={
                "success": True,
                "data": _make_failed_operation("op_000"),
            }
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, population)

        assert results[0]["fitness"] == MINIMUM_FITNESS


class TestGenerationHarnessFullRun:
    """Tests for full run_generation flow."""

    @pytest.mark.asyncio
    async def test_full_run_3_researchers_all_complete(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        sample_population: list[Researcher],
    ) -> None:
        """Full run with 3 researchers, all complete successfully."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_000"),
                _make_trigger_response("op_001"),
                _make_trigger_response("op_002"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_000", sharpe=1.5, max_dd=0.1),
                _make_completed_operation("op_001", sharpe=0.5, max_dd=0.2),
                _make_completed_operation("op_002", sharpe=2.0, max_dd=0.05),
            ]
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, sample_population)

        assert len(results) == 3
        # All should have real fitness scores (not minimum)
        for r in results:
            assert r["fitness"] != MINIMUM_FITNESS
        # Verify ordering: results should be for each researcher
        ids = {r["researcher_id"] for r in results}
        assert ids == {"r_g00_000", "r_g00_001", "r_g00_002"}

    @pytest.mark.asyncio
    async def test_full_run_1_fails_others_succeed(
        self,
        config: EvolutionConfig,
        tracker: EvolutionTracker,
        sample_population: list[Researcher],
    ) -> None:
        """1 researcher fails, others succeed. Failed gets minimum fitness."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_000"),
                _make_trigger_response("op_001"),
                _make_trigger_response("op_002"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_000", sharpe=1.0, max_dd=0.1),
                _make_failed_operation("op_001"),
                _make_completed_operation("op_002", sharpe=1.5, max_dd=0.05),
            ]
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, sample_population)

        assert len(results) == 3
        results_by_id = {r["researcher_id"]: r for r in results}
        assert results_by_id["r_g00_001"]["fitness"] == MINIMUM_FITNESS
        assert results_by_id["r_g00_000"]["fitness"] != MINIMUM_FITNESS
        assert results_by_id["r_g00_002"]["fitness"] != MINIMUM_FITNESS


def _mock_generation_responses(
    pop_size: int, generation: int, base_sharpe: float = 1.0
) -> tuple[list[dict], list[dict]]:
    """Create trigger + completion mock responses for a generation.

    Returns (trigger_responses, get_responses) for pop_size researchers.
    Each researcher gets a unique sharpe so selection is deterministic.
    """
    triggers = []
    completions = []
    for i in range(pop_size):
        op_id = f"op_g{generation:02d}_{i:03d}"
        triggers.append(_make_trigger_response(op_id))
        sharpe = base_sharpe + i * 0.1  # spread so selection is deterministic
        completions.append(_make_completed_operation(op_id, sharpe=sharpe, max_dd=0.05))
    return triggers, completions


class TestHarnessMultiGeneration:
    """Tests for GenerationHarness.run() — multi-generation loop."""

    @pytest.fixture
    def multi_gen_config(self) -> EvolutionConfig:
        """Config for 3 generations, 6 researchers, fast polling, single slice."""
        return EvolutionConfig(
            population_size=6,
            generations=3,
            seed=42,
            poll_interval=0,
            fitness_slices=_SINGLE_SLICE,
        )

    @pytest.mark.asyncio
    async def test_runs_correct_number_of_generations(
        self, multi_gen_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """run() should execute exactly config.generations generations."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        # Build responses for 3 generations × 6 researchers each
        all_triggers = []
        all_completions = []
        for gen in range(3):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=multi_gen_config, tracker=tracker, http_client=mock_client
        )
        await harness.run(PopulationManager())

        # 3 generation directories should have results
        for gen in range(3):
            results = tracker.load_results(gen)
            assert len(results) > 0, f"Generation {gen} has no results"

    @pytest.mark.asyncio
    async def test_population_flows_between_generations(
        self, multi_gen_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Gen 0 survivors should become gen 1's population (mutated)."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        all_triggers = []
        all_completions = []
        for gen in range(3):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=multi_gen_config, tracker=tracker, http_client=mock_client
        )
        await harness.run(PopulationManager())

        # Gen 1 population should be offspring of gen 0 survivors
        gen1_pop = tracker.load_population(1)
        assert len(gen1_pop) == 6
        # All gen 1 researchers should have parent_ids from gen 0
        for r in gen1_pop:
            assert r.parent_id is not None
            assert r.parent_id.startswith("r_g00_")
            assert r.generation == 1

    @pytest.mark.asyncio
    async def test_summary_updated_after_each_generation(
        self, multi_gen_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Summary.yaml should be updated incrementally after each generation."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        all_triggers = []
        all_completions = []
        for gen in range(3):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=multi_gen_config, tracker=tracker, http_client=mock_client
        )
        await harness.run(PopulationManager())

        summary = tracker.load_summary()
        assert "generations" in summary
        assert len(summary["generations"]) == 3

    @pytest.mark.asyncio
    async def test_budget_check_aborts_early(self, tmp_run_dir: Path) -> None:
        """If budget exhausted mid-run, should abort and not continue."""
        config = EvolutionConfig(
            population_size=4,
            generations=3,
            seed=42,
            poll_interval=0,
            fitness_slices=_SINGLE_SLICE,
        )
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        # Gen 0 succeeds, gen 1 hits budget_exhausted
        gen0_t, gen0_c = _mock_generation_responses(4, 0)
        mock_client.post = AsyncMock(
            side_effect=[
                *gen0_t,
                # Gen 1: budget exhausted on first trigger
                {"triggered": False, "reason": "budget_exhausted"},
            ]
        )
        mock_client.get = AsyncMock(side_effect=gen0_c)

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        await harness.run(PopulationManager())

        # Gen 0 should have real results
        gen0_results = tracker.load_results(0)
        assert len(gen0_results) == 4
        # Gen 1 should have results (all minimum fitness from budget abort)
        gen1_results = tracker.load_results(1)
        assert len(gen1_results) == 4
        for r in gen1_results:
            assert r["fitness"] == MINIMUM_FITNESS
        # Gen 2 should NOT exist (aborted)
        gen2_results = tracker.load_results(2)
        assert len(gen2_results) == 0

    @pytest.mark.asyncio
    async def test_correct_generation_numbers_in_ids(
        self, multi_gen_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Researcher IDs should contain correct generation numbers."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        all_triggers = []
        all_completions = []
        for gen in range(3):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=multi_gen_config, tracker=tracker, http_client=mock_client
        )
        await harness.run(PopulationManager())

        for gen in range(3):
            pop = tracker.load_population(gen)
            for r in pop:
                assert r.id.startswith(f"r_g{gen:02d}_")


def _setup_completed_run(
    tracker: EvolutionTracker,
    config: EvolutionConfig,
    through_gen: int,
) -> None:
    """Helper: set up tracker state as if generations 0..through_gen completed.

    Creates config, population, operations, and results for each generation.
    Uses PopulationManager to create realistic population flow.
    """
    tracker.save_config(config)
    pm = PopulationManager()
    population = pm.seed(config)

    for gen in range(through_gen + 1):
        tracker.save_population(gen, population)

        # Fake operations and results
        ops = {r.id: f"op_{r.id}" for r in population}
        for rid, oid in ops.items():
            tracker.save_operation_id(gen, rid, oid)

        results = [
            {
                "researcher_id": r.id,
                "fitness": float(i) + 0.5,
                "backtest_result": {
                    "sharpe_ratio": float(i) + 0.5,
                    "max_drawdown": 0.05,
                    "total_trades": 50,
                },
            }
            for i, r in enumerate(population)
        ]
        tracker.save_results(gen, results)

        # Evolve for next gen
        if gen < through_gen:
            survivor_ids, _ = pm.select(results, kill_rate=config.kill_rate)
            survivor_map = {r.id: r for r in population}
            survivors = [survivor_map[sid] for sid in survivor_ids]
            population = pm.reproduce(survivors, generation=gen + 1, seed=config.seed)


class TestHarnessResume:
    """Tests for GenerationHarness.resume()."""

    @pytest.fixture
    def resume_config(self) -> EvolutionConfig:
        """Config for 5 generations, 6 researchers, single slice."""
        return EvolutionConfig(
            population_size=6,
            generations=5,
            seed=42,
            poll_interval=0,
            fitness_slices=_SINGLE_SLICE,
        )

    @pytest.mark.asyncio
    async def test_resume_after_gen2_continues_from_gen3(
        self, resume_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Resume after gen 2 of 5: should continue from gen 3."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        _setup_completed_run(tracker, resume_config, through_gen=2)

        mock_client = AsyncMock()
        # Need responses for gens 3 and 4 (2 remaining)
        all_triggers = []
        all_completions = []
        for gen in range(3, 5):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=resume_config, tracker=tracker, http_client=mock_client
        )
        await harness.resume(PopulationManager())

        # All 5 generations should now have results
        for gen in range(5):
            results = tracker.load_results(gen)
            assert len(results) > 0, f"Gen {gen} has no results"

    @pytest.mark.asyncio
    async def test_resume_with_incomplete_generation_polls_running(
        self, resume_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Resume with an incomplete generation: ops with status should be polled."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        # Complete through gen 1
        _setup_completed_run(tracker, resume_config, through_gen=1)

        # Set up gen 2 as incomplete: population + operations saved, but no results
        gen2_pop = tracker.load_population(1)  # reuse for simplicity
        pm = PopulationManager()
        gen1_results = tracker.load_results(1)
        survivor_ids, _ = pm.select(gen1_results, kill_rate=resume_config.kill_rate)
        gen1_pop_map = {r.id: r for r in tracker.load_population(1)}
        survivors = [gen1_pop_map[sid] for sid in survivor_ids]
        gen2_pop = pm.reproduce(survivors, generation=2, seed=resume_config.seed)
        tracker.save_population(2, gen2_pop)

        # Save operations for gen 2 but NO results
        for r in gen2_pop:
            tracker.save_operation_id(2, r.id, f"op_{r.id}")

        mock_client = AsyncMock()
        # Gen 2 ops are "completed" when polled
        gen2_completions = [
            _make_completed_operation(f"op_{r.id}", sharpe=1.0 + i * 0.1, max_dd=0.05)
            for i, r in enumerate(gen2_pop)
        ]
        # Gens 3 and 4 normal
        all_triggers = []
        all_completions = list(gen2_completions)
        for gen in range(3, 5):
            t, c = _mock_generation_responses(6, gen)
            all_triggers.extend(t)
            all_completions.extend(c)

        mock_client.post = AsyncMock(side_effect=all_triggers)
        mock_client.get = AsyncMock(side_effect=all_completions)

        harness = GenerationHarness(
            config=resume_config, tracker=tracker, http_client=mock_client
        )
        await harness.resume(PopulationManager())

        # Gen 2 should now have results
        gen2_results = tracker.load_results(2)
        assert len(gen2_results) == 6

    @pytest.mark.asyncio
    async def test_resume_all_complete_reports_done(
        self, resume_config: EvolutionConfig, tmp_run_dir: Path
    ) -> None:
        """Resume with all generations complete: should not trigger anything."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        _setup_completed_run(tracker, resume_config, through_gen=4)

        mock_client = AsyncMock()
        mock_client.post = AsyncMock()
        mock_client.get = AsyncMock()

        harness = GenerationHarness(
            config=resume_config, tracker=tracker, http_client=mock_client
        )
        await harness.resume(PopulationManager())

        # No HTTP calls should have been made
        mock_client.post.assert_not_called()

    @pytest.mark.asyncio
    async def test_resume_with_orphaned_ops_retriggers(self, tmp_run_dir: Path) -> None:
        """Resume with orphaned ops (failed status): should re-trigger."""
        config = EvolutionConfig(
            population_size=4,
            generations=3,
            seed=42,
            poll_interval=0,
            stale_operation_timeout=0,  # treat all as stale immediately
            fitness_slices=_SINGLE_SLICE,
        )
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        _setup_completed_run(tracker, config, through_gen=0)

        # Set up gen 1 incomplete with operations but no results
        gen0_results = tracker.load_results(0)
        pm = PopulationManager()
        survivor_ids, _ = pm.select(gen0_results, kill_rate=config.kill_rate)
        gen0_pop_map = {r.id: r for r in tracker.load_population(0)}
        survivors = [gen0_pop_map[sid] for sid in survivor_ids]
        gen1_pop = pm.reproduce(survivors, generation=1, seed=config.seed)
        tracker.save_population(1, gen1_pop)
        for r in gen1_pop:
            tracker.save_operation_id(1, r.id, f"op_{r.id}")

        mock_client = AsyncMock()
        # When polled, ops show as failed → harness should re-trigger
        failed_poll_responses = [_make_failed_operation(f"op_{r.id}") for r in gen1_pop]
        # Re-trigger responses
        retrigger_responses = [
            _make_trigger_response(f"retrig_{r.id}") for r in gen1_pop
        ]
        # Then complete
        retrigger_completions = [
            _make_completed_operation(
                f"retrig_{r.id}", sharpe=1.0 + i * 0.1, max_dd=0.05
            )
            for i, r in enumerate(gen1_pop)
        ]
        # Gen 2 normal
        gen2_t, gen2_c = _mock_generation_responses(4, 2)

        mock_client.get = AsyncMock(
            side_effect=[*failed_poll_responses, *retrigger_completions, *gen2_c]
        )
        mock_client.post = AsyncMock(side_effect=[*retrigger_responses, *gen2_t])

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        await harness.resume(pm)

        # Gen 1 should have results from re-triggered ops
        gen1_results = tracker.load_results(1)
        assert len(gen1_results) == 4


# --- Helpers for additional backtest tests (Task 3.1) ---


def _make_backtest_start_response(op_id: str) -> dict[str, Any]:
    """Successful backtest start response (POST /backtests/start)."""
    return {
        "success": True,
        "operation_id": op_id,
        "status": "started",
        "message": "Backtest started",
        "symbol": "EURUSD",
        "timeframe": "1h",
    }


def _make_backtest_completed(
    op_id: str,
    sharpe: float = 1.0,
    max_dd: float = 0.1,
    total_trades: int = 50,
    long_trades: int = 25,
    short_trades: int = 25,
) -> dict[str, Any]:
    """Completed backtest operation (GET /operations/{id})."""
    return {
        "operation_id": op_id,
        "status": "completed",
        "result_summary": {
            "success": True,
            "backtest_result": {
                "sharpe_ratio": sharpe,
                "max_drawdown": max_dd,
                "total_trades": total_trades,
                "long_trades": long_trades,
                "short_trades": short_trades,
            },
        },
    }


_THREE_SLICES = [
    DateRange(date(2021, 1, 1), date(2022, 6, 30)),
    DateRange(date(2022, 7, 1), date(2023, 12, 31)),
    DateRange(date(2024, 1, 1), date(2025, 6, 30)),
]


class TestHarnessAdditionalBacktests:
    """Tests for additional backtest slices (Task 3.1)."""

    @pytest.fixture
    def three_slice_config(self) -> EvolutionConfig:
        """Config with 3 fitness slices for testing additional backtests."""
        return EvolutionConfig(
            population_size=2,
            generations=1,
            seed=42,
            poll_interval=0,
            fitness_slices=list(_THREE_SLICES),
        )

    def _single_researcher(self) -> list[Researcher]:
        return [
            Researcher(id="r_g00_000", genome=Genome(), generation=0),
        ]

    @pytest.mark.asyncio
    async def test_additional_backtests_triggered_with_correct_dates(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """Should trigger backtests for slices 2 and 3 with correct date ranges."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_research"),
                _make_backtest_start_response("op_bt_s2"),
                _make_backtest_start_response("op_bt_s3"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_research", sharpe=1.0, max_dd=0.1),
                _make_backtest_completed("op_bt_s2", sharpe=0.8, max_dd=0.15),
                _make_backtest_completed("op_bt_s3", sharpe=0.9, max_dd=0.12),
            ]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        await harness.run_generation(0, self._single_researcher())

        # Verify 3 POST calls: 1 research trigger + 2 backtest triggers
        post_calls = mock_client.post.call_args_list
        assert len(post_calls) == 3

        # Slice 2 backtest has correct dates and model metadata
        bt_s2_json = post_calls[1][1]["json"]
        assert bt_s2_json["start_date"] == "2022-07-01"
        assert bt_s2_json["end_date"] == "2023-12-31"
        assert bt_s2_json["model_path"] == "/models/test"
        assert bt_s2_json["strategy_name"] == "test_strategy"

        # Slice 3 backtest
        bt_s3_json = post_calls[2][1]["json"]
        assert bt_s3_json["start_date"] == "2024-01-01"
        assert bt_s3_json["end_date"] == "2025-06-30"

    @pytest.mark.asyncio
    async def test_model_path_from_research_operation_used(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """Model path from research op metadata should be used for backtests."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        # Custom model_path in research operation
        research_op = _make_completed_operation("op_research", sharpe=1.0, max_dd=0.1)
        research_op["metadata"]["parameters"]["model_path"] = "/models/custom_v2"
        research_op["metadata"]["parameters"]["strategy_name"] = "custom_strat"

        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_research"),
                _make_backtest_start_response("op_bt_s2"),
                _make_backtest_start_response("op_bt_s3"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                research_op,
                _make_backtest_completed("op_bt_s2"),
                _make_backtest_completed("op_bt_s3"),
            ]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        await harness.run_generation(0, self._single_researcher())

        bt_s2_json = mock_client.post.call_args_list[1][1]["json"]
        assert bt_s2_json["model_path"] == "/models/custom_v2"
        assert bt_s2_json["strategy_name"] == "custom_strat"

    @pytest.mark.asyncio
    async def test_failed_additional_backtest_retries_once(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """Failed additional backtest should retry once, then proceed."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        # Slice 2: first attempt fails, retry succeeds. Slice 3: succeeds.
        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_research"),
                _make_backtest_start_response("op_bt_s2_fail"),
                _make_backtest_start_response("op_bt_s2_retry"),
                _make_backtest_start_response("op_bt_s3"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_research"),
                _make_failed_operation("op_bt_s2_fail"),
                _make_backtest_completed("op_bt_s2_retry", sharpe=0.9),
                _make_backtest_completed("op_bt_s3", sharpe=0.7),
            ]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, self._single_researcher())

        # All 3 slice results collected (retry succeeded)
        assert len(results[0]["slice_results"]) == 3

    @pytest.mark.asyncio
    async def test_failed_additional_backtest_both_attempts_degrades(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """If both attempts fail, proceed with available slices only."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        # Slice 2: both attempts fail. Slice 3: succeeds.
        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_research"),
                _make_backtest_start_response("op_bt_s2_a1"),
                _make_backtest_start_response("op_bt_s2_a2"),
                _make_backtest_start_response("op_bt_s3"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_research"),
                _make_failed_operation("op_bt_s2_a1"),
                _make_failed_operation("op_bt_s2_a2"),
                _make_backtest_completed("op_bt_s3", sharpe=0.7),
            ]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, self._single_researcher())

        # Only 2 slice results (first + slice 3; slice 2 failed)
        assert len(results[0]["slice_results"]) == 2

    @pytest.mark.asyncio
    async def test_skipped_for_failed_researcher(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """Researchers that failed research skip additional backtests."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        mock_client.post = AsyncMock(
            side_effect=[_make_trigger_response("op_research")]
        )
        mock_client.get = AsyncMock(
            side_effect=[_make_failed_operation("op_research")]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, self._single_researcher())

        assert results[0]["fitness"] == MINIMUM_FITNESS
        assert len(results[0]["slice_results"]) == 0
        # Only 1 POST (research trigger), no backtest triggers
        assert mock_client.post.call_count == 1

    @pytest.mark.asyncio
    async def test_all_3_slice_results_collected(
        self,
        three_slice_config: EvolutionConfig,
        tmp_run_dir: Path,
    ) -> None:
        """All 3 slice results should be collected with correct values."""
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        mock_client.post = AsyncMock(
            side_effect=[
                _make_trigger_response("op_research"),
                _make_backtest_start_response("op_bt_s2"),
                _make_backtest_start_response("op_bt_s3"),
            ]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_research", sharpe=1.5, max_dd=0.1),
                _make_backtest_completed("op_bt_s2", sharpe=1.2, max_dd=0.12),
                _make_backtest_completed("op_bt_s3", sharpe=0.8, max_dd=0.2),
            ]
        )

        harness = GenerationHarness(
            config=three_slice_config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, self._single_researcher())

        slices = results[0]["slice_results"]
        assert len(slices) == 3
        assert slices[0]["sharpe_ratio"] == 1.5
        assert slices[1]["sharpe_ratio"] == 1.2
        assert slices[2]["sharpe_ratio"] == 0.8

    @pytest.mark.asyncio
    async def test_no_additional_backtests_with_single_slice(
        self,
        tmp_run_dir: Path,
    ) -> None:
        """With 1 fitness slice, no additional backtests are triggered."""
        config = EvolutionConfig(
            population_size=2,
            generations=1,
            seed=42,
            poll_interval=0,
            fitness_slices=_SINGLE_SLICE,
        )
        tracker = EvolutionTracker(run_dir=tmp_run_dir)
        mock_client = AsyncMock()

        mock_client.post = AsyncMock(
            side_effect=[_make_trigger_response("op_research")]
        )
        mock_client.get = AsyncMock(
            side_effect=[
                _make_completed_operation("op_research", sharpe=1.0, max_dd=0.1)
            ]
        )

        harness = GenerationHarness(
            config=config, tracker=tracker, http_client=mock_client
        )
        results = await harness.run_generation(0, self._single_researcher())

        # Only 1 POST (research trigger), no backtest triggers
        assert mock_client.post.call_count == 1
        # 1 slice result from research pipeline
        assert len(results[0]["slice_results"]) == 1
