"""Tests for evolution tracker — YAML state persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.genome import Genome, Researcher, TraitLevel
from ktrdr.evolution.tracker import EvolutionTracker


@pytest.fixture
def tmp_data_dir() -> Path:
    """Create a temporary directory for test data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def tracker(tmp_data_dir: Path) -> EvolutionTracker:
    """Create a tracker with a temporary run directory."""
    return EvolutionTracker(run_dir=tmp_data_dir / "run_20260220_120000")


@pytest.fixture
def sample_config() -> EvolutionConfig:
    """A sample config for testing."""
    return EvolutionConfig(population_size=3, seed=42)


@pytest.fixture
def sample_population() -> list[Researcher]:
    """A small sample population."""
    return [
        Researcher(
            id="r_g00_000",
            genome=Genome(
                novelty_seeking=TraitLevel.OFF,
                skepticism=TraitLevel.LOW,
                memory_depth=TraitLevel.HIGH,
            ),
            generation=0,
        ),
        Researcher(
            id="r_g00_001",
            genome=Genome(
                novelty_seeking=TraitLevel.HIGH,
                skepticism=TraitLevel.HIGH,
                memory_depth=TraitLevel.OFF,
            ),
            generation=0,
        ),
    ]


@pytest.fixture
def sample_results() -> list[dict[str, Any]]:
    """Sample results for testing."""
    return [
        {
            "researcher_id": "r_g00_000",
            "fitness": 1.23,
            "gate_passed": True,
            "backtest_result": {"sharpe": 1.5, "max_drawdown": 0.12},
        },
        {
            "researcher_id": "r_g00_001",
            "fitness": -999.0,
            "gate_passed": False,
            "backtest_result": None,
        },
    ]


class TestEvolutionTrackerConfig:
    """Tests for config save/load roundtrip."""

    def test_save_load_config_roundtrip(
        self, tracker: EvolutionTracker, sample_config: EvolutionConfig
    ) -> None:
        """Config should roundtrip through YAML."""
        tracker.save_config(sample_config)
        loaded = tracker.load_config()
        assert loaded is not None
        assert loaded.population_size == sample_config.population_size
        assert loaded.seed == sample_config.seed
        assert loaded.training_window.start == sample_config.training_window.start
        assert loaded.training_window.end == sample_config.training_window.end
        assert len(loaded.fitness_slices) == len(sample_config.fitness_slices)

    def test_load_config_missing_file(self, tracker: EvolutionTracker) -> None:
        """Loading config from nonexistent path returns None."""
        loaded = tracker.load_config()
        assert loaded is None


class TestEvolutionTrackerPopulation:
    """Tests for population save/load roundtrip."""

    def test_save_load_population_roundtrip(
        self, tracker: EvolutionTracker, sample_population: list[Researcher]
    ) -> None:
        """Population should roundtrip through YAML."""
        tracker.save_population(0, sample_population)
        loaded = tracker.load_population(0)
        assert len(loaded) == 2
        assert loaded[0].id == "r_g00_000"
        assert loaded[0].genome.novelty_seeking == TraitLevel.OFF
        assert loaded[1].id == "r_g00_001"
        assert loaded[1].genome.skepticism == TraitLevel.HIGH

    def test_load_population_missing_file(self, tracker: EvolutionTracker) -> None:
        """Loading population from nonexistent path returns empty list."""
        loaded = tracker.load_population(0)
        assert loaded == []


class TestEvolutionTrackerResults:
    """Tests for results save/load roundtrip."""

    def test_save_load_results_roundtrip(
        self, tracker: EvolutionTracker, sample_results: list[dict[str, Any]]
    ) -> None:
        """Results should roundtrip through YAML."""
        tracker.save_results(0, sample_results)
        loaded = tracker.load_results(0)
        assert len(loaded) == 2
        assert loaded[0]["researcher_id"] == "r_g00_000"
        assert loaded[0]["fitness"] == 1.23
        assert loaded[1]["fitness"] == -999.0

    def test_load_results_missing_file(self, tracker: EvolutionTracker) -> None:
        """Loading results from nonexistent path returns empty list."""
        loaded = tracker.load_results(0)
        assert loaded == []


class TestEvolutionTrackerOperations:
    """Tests for operation ID persistence."""

    def test_save_operation_id_incremental(self, tracker: EvolutionTracker) -> None:
        """Operation IDs should persist incrementally, not batched."""
        tracker.save_operation_id(0, "r_g00_000", "op_abc123")
        tracker.save_operation_id(0, "r_g00_001", "op_def456")

        loaded = tracker.load_operations(0)
        assert loaded["r_g00_000"] == "op_abc123"
        assert loaded["r_g00_001"] == "op_def456"

    def test_save_operation_id_persists_after_each_call(
        self, tracker: EvolutionTracker
    ) -> None:
        """Each save should be readable immediately (crash safety)."""
        tracker.save_operation_id(0, "r_g00_000", "op_abc123")
        loaded = tracker.load_operations(0)
        assert len(loaded) == 1
        assert loaded["r_g00_000"] == "op_abc123"

        tracker.save_operation_id(0, "r_g00_001", "op_def456")
        loaded = tracker.load_operations(0)
        assert len(loaded) == 2

    def test_load_operations_missing_file(self, tracker: EvolutionTracker) -> None:
        """Loading operations from nonexistent path returns empty dict."""
        loaded = tracker.load_operations(0)
        assert loaded == {}


class TestEvolutionTrackerGenerations:
    """Tests for generation tracking."""

    def test_get_last_completed_generation_empty(
        self, tracker: EvolutionTracker
    ) -> None:
        """Empty run should return None."""
        result = tracker.get_last_completed_generation()
        assert result is None

    def test_get_last_completed_generation_with_results(
        self,
        tracker: EvolutionTracker,
        sample_results: list[dict[str, Any]],
    ) -> None:
        """Should return generation number after saving results."""
        tracker.save_results(0, sample_results)
        assert tracker.get_last_completed_generation() == 0

        tracker.save_results(1, sample_results)
        assert tracker.get_last_completed_generation() == 1

    def test_directory_auto_creation(self, tracker: EvolutionTracker) -> None:
        """Directories should be created automatically on save."""
        tracker.save_operation_id(0, "r_g00_000", "op_test")
        gen_dir = tracker.run_dir / "generation_00"
        assert gen_dir.exists()
        assert (gen_dir / "operations.yaml").exists()
