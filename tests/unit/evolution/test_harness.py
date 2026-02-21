"""Tests for generation harness — the orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS
from ktrdr.evolution.genome import Genome, Researcher, TraitLevel
from ktrdr.evolution.harness import GenerationHarness
from ktrdr.evolution.tracker import EvolutionTracker


@pytest.fixture
def tmp_run_dir() -> Path:
    """Create a temporary run directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "run_test"


@pytest.fixture
def config() -> EvolutionConfig:
    """Config with fast poll interval for testing."""
    return EvolutionConfig(population_size=3, seed=42, poll_interval=0)


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
    """Completed operation response with backtest result."""
    return {
        "operation_id": op_id,
        "status": "completed",
        "metadata": {
            "parameters": {
                "backtest_result": {
                    "sharpe": sharpe,
                    "max_drawdown": max_dd,
                },
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
        # fitness = 1.5 - 1.0 * 0.1 = 1.4
        assert abs(results[0]["fitness"] - 1.4) < 1e-9

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
