"""Tests for evolution configuration."""

from __future__ import annotations

from datetime import date

import pytest

from ktrdr.evolution.config import DateRange, EvolutionConfig


class TestDateRange:
    """Tests for the DateRange data model."""

    def test_basic_creation(self) -> None:
        """DateRange should hold start and end dates."""
        dr = DateRange(start=date(2021, 1, 1), end=date(2022, 6, 30))
        assert dr.start == date(2021, 1, 1)
        assert dr.end == date(2022, 6, 30)

    def test_invalid_range(self) -> None:
        """DateRange should reject start > end."""
        with pytest.raises(ValueError):
            DateRange(start=date(2023, 1, 1), end=date(2022, 1, 1))


class TestEvolutionConfig:
    """Tests for the EvolutionConfig data model."""

    def test_defaults_match_design(self) -> None:
        """Default values should match DESIGN.md / ARCHITECTURE.md."""
        config = EvolutionConfig()
        assert config.population_size == 12
        assert config.generations == 5
        assert config.symbol == "EURUSD"
        assert config.timeframe == "1h"
        assert config.model == "haiku"
        assert config.kill_rate == 0.5
        assert config.mutations_per_offspring == 1
        assert config.poll_interval == 30
        assert config.stale_operation_timeout == 1800  # 30 min in seconds

    def test_training_window_defaults(self) -> None:
        """Training window should default to 2015-2020."""
        config = EvolutionConfig()
        assert config.training_window.start == date(2015, 1, 1)
        assert config.training_window.end == date(2020, 12, 31)

    def test_fitness_slices_defaults(self) -> None:
        """Should have 3 non-overlapping fitness slices post-training."""
        config = EvolutionConfig()
        assert len(config.fitness_slices) == 3
        # Slices should be after training window
        for s in config.fitness_slices:
            assert s.start > config.training_window.end

    def test_lambda_defaults(self) -> None:
        """Lambda parameters should match DESIGN.md."""
        config = EvolutionConfig()
        assert config.lambda_dd == 1.0
        assert config.lambda_var == 1.0
        assert config.lambda_complexity == 0.1

    def test_custom_population_size(self) -> None:
        """Should accept custom population size."""
        config = EvolutionConfig(population_size=6)
        assert config.population_size == 6

    def test_validation_rejects_small_population(self) -> None:
        """Population size < 2 should be rejected."""
        with pytest.raises(ValueError):
            EvolutionConfig(population_size=1)

    def test_validation_rejects_zero_generations(self) -> None:
        """Generations < 1 should be rejected."""
        with pytest.raises(ValueError):
            EvolutionConfig(generations=0)

    def test_validation_rejects_empty_fitness_slices(self) -> None:
        """Empty fitness_slices should be rejected."""
        with pytest.raises(ValueError):
            EvolutionConfig(fitness_slices=[])

    def test_seed_parameter(self) -> None:
        """Config should accept an optional random seed."""
        config = EvolutionConfig(seed=42)
        assert config.seed == 42

    def test_seed_default_none(self) -> None:
        """Seed should default to None (random)."""
        config = EvolutionConfig()
        assert config.seed is None
