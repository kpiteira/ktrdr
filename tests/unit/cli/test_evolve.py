"""Tests for evolve CLI commands — status and resume."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.app import app
from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.population import PopulationManager
from ktrdr.evolution.tracker import EvolutionTracker


@pytest.fixture
def tmp_evolution_dir(tmp_path: Path) -> Path:
    """Create a temporary data/evolution directory."""
    evo_dir = tmp_path / "data" / "evolution"
    evo_dir.mkdir(parents=True)
    return evo_dir


def _setup_run(
    evo_dir: Path,
    run_id: str,
    config: EvolutionConfig,
    completed_gens: int,
) -> Path:
    """Create a test run directory with completed generations."""
    run_dir = evo_dir / run_id
    tracker = EvolutionTracker(run_dir=run_dir)
    tracker.save_config(config)

    pm = PopulationManager()
    population = pm.seed(config)

    for gen in range(completed_gens):
        tracker.save_population(gen, population)
        results = [
            {
                "researcher_id": r.id,
                "fitness": float(i) + 0.5,
                "backtest_result": {
                    "sharpe_ratio": float(i) + 0.5,
                    "max_drawdown": 0.05,
                },
            }
            for i, r in enumerate(population)
        ]
        tracker.save_results(gen, results)

        # Update summary
        fitnesses = [r["fitness"] for r in results]
        summary = tracker.load_summary()
        if "generations" not in summary:
            summary["generations"] = []
        summary["generations"].append(
            {
                "generation": gen,
                "population_size": len(results),
                "mean_fitness": sum(fitnesses) / len(fitnesses),
                "max_fitness": max(fitnesses),
                "min_fitness": min(fitnesses),
                "successful": len(results),
                "failed": 0,
            }
        )
        tracker.save_summary(summary)

        if gen < completed_gens - 1:
            survivor_ids, _ = pm.select(results, kill_rate=config.kill_rate)
            survivor_map = {r.id: r for r in population}
            survivors = [survivor_map[sid] for sid in survivor_ids]
            population = pm.reproduce(survivors, generation=gen + 1, seed=config.seed)

    return run_dir


class TestEvolveStatus:
    """Tests for `ktrdr evolve status` command."""

    def test_no_runs_found(self, runner, tmp_path: Path) -> None:
        """Status with no runs should indicate no runs found."""
        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_path / "data" / "evolution",
        ):
            result = runner.invoke(app, ["evolve", "status"])
        assert result.exit_code == 0
        assert "No evolution runs found" in result.output

    def test_status_shows_completed_run(self, runner, tmp_evolution_dir: Path) -> None:
        """Status with a completed run should show generation stats."""
        config = EvolutionConfig(population_size=6, generations=3, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=3)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "status"])
        assert result.exit_code == 0
        assert "run_20260101_120000" in result.output
        assert "Generation" in result.output or "generation" in result.output

    def test_status_with_specific_run_id(self, runner, tmp_evolution_dir: Path) -> None:
        """Status with a specific run_id should show that run."""
        config = EvolutionConfig(population_size=6, generations=3, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=2)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "status", "run_20260101_120000"])
        assert result.exit_code == 0
        assert "run_20260101_120000" in result.output

    def test_status_shows_in_progress_run(
        self, runner, tmp_evolution_dir: Path
    ) -> None:
        """Status with in-progress run should show current generation."""
        config = EvolutionConfig(population_size=6, generations=5, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=2)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "status"])
        assert result.exit_code == 0
        # Should show it's in progress (2 of 5 generations complete)
        assert "2" in result.output


class TestEvolveResume:
    """Tests for `ktrdr evolve resume` command."""

    def test_resume_calls_harness_resume(self, runner, tmp_evolution_dir: Path) -> None:
        """Resume command should invoke the harness resume method."""
        config = EvolutionConfig(
            population_size=4, generations=3, seed=42, poll_interval=0
        )
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=1)

        with (
            patch(
                "ktrdr.cli.commands.evolve._get_evolution_dir",
                return_value=tmp_evolution_dir,
            ),
            patch(
                "ktrdr.cli.sandbox_detect.resolve_api_url",
                return_value="http://localhost:8000",
            ),
            patch("httpx.AsyncClient") as mock_async_client,
            patch(
                "ktrdr.evolution.harness.GenerationHarness.resume",
                new_callable=AsyncMock,
            ) as mock_resume,
        ):
            mock_client = AsyncMock()
            mock_async_client.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_async_client.return_value.__aexit__ = AsyncMock(return_value=False)

            result = runner.invoke(app, ["evolve", "resume", "run_20260101_120000"])

        assert result.exit_code == 0
        mock_resume.assert_called_once()
