"""Tests for evolve CLI commands — status, resume, and report."""

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
                    "total_trades": 50,
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


class TestEvolveReport:
    """Tests for `ktrdr evolve report` command."""

    def test_report_no_runs_found(self, runner, tmp_path: Path) -> None:
        """Report with no runs should indicate no runs found."""
        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_path / "data" / "evolution",
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        assert "No evolution runs found" in result.output

    def test_report_renders_fitness_trend(
        self, runner, tmp_evolution_dir: Path
    ) -> None:
        """Report should include a fitness trend table."""
        config = EvolutionConfig(population_size=6, generations=3, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=3)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        assert "Fitness Trend" in result.output
        # Should show generation numbers
        assert "0" in result.output
        assert "1" in result.output
        assert "2" in result.output

    def test_report_renders_genome_distribution(
        self, runner, tmp_evolution_dir: Path
    ) -> None:
        """Report should show genome trait distribution."""
        config = EvolutionConfig(population_size=6, generations=2, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=2)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        assert "Genome Distribution" in result.output
        # Should contain trait names
        assert "novelty_seeking" in result.output or "Trait" in result.output

    def test_report_with_specific_run_id(self, runner, tmp_evolution_dir: Path) -> None:
        """Report with specific run_id should show that run."""
        config = EvolutionConfig(population_size=6, generations=2, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=2)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report", "run_20260101_120000"])
        assert result.exit_code == 0
        assert "run_20260101_120000" in result.output

    def test_report_shows_monoculture_warning(
        self, runner, tmp_evolution_dir: Path
    ) -> None:
        """Report should show monoculture warning when diversity is low."""
        # Use seed that produces low diversity after selection
        config = EvolutionConfig(
            population_size=6, generations=3, seed=42, kill_rate=0.8
        )
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=3)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        # The report should render without error; monoculture section present
        assert "Diversity" in result.output or "diversity" in result.output

    def test_report_shows_lineage(self, runner, tmp_evolution_dir: Path) -> None:
        """Report should trace best performer's lineage."""
        config = EvolutionConfig(population_size=6, generations=3, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=3)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        assert "Lineage" in result.output or "lineage" in result.output

    def test_report_shows_run_summary(self, runner, tmp_evolution_dir: Path) -> None:
        """Report should show run configuration summary."""
        config = EvolutionConfig(population_size=6, generations=2, seed=42)
        _setup_run(tmp_evolution_dir, "run_20260101_120000", config, completed_gens=2)

        with patch(
            "ktrdr.cli.commands.evolve._get_evolution_dir",
            return_value=tmp_evolution_dir,
        ):
            result = runner.invoke(app, ["evolve", "report"])
        assert result.exit_code == 0
        # Should contain config info
        assert "6" in result.output  # population_size
        assert "EURUSD" in result.output or "eurusd" in result.output.lower()
