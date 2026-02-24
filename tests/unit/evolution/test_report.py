"""Tests for evolution report — monoculture detection and analysis."""

from __future__ import annotations

from ktrdr.evolution.genome import Genome, Researcher, TraitLevel
from ktrdr.evolution.report import (
    MonocultureWarning,
    compute_genome_diversity,
    compute_trait_convergence,
)


def _make_researcher(
    gen: int,
    idx: int,
    novelty: TraitLevel = TraitLevel.LOW,
    skepticism: TraitLevel = TraitLevel.LOW,
    memory: TraitLevel = TraitLevel.LOW,
) -> Researcher:
    """Helper to create a researcher with specific traits."""
    return Researcher(
        id=f"r_g{gen:02d}_{idx:03d}",
        genome=Genome(
            novelty_seeking=novelty,
            skepticism=skepticism,
            memory_depth=memory,
        ),
        generation=gen,
    )


class TestGenomeDiversity:
    """Tests for genome_diversity computation."""

    def test_all_unique_genomes_diversity_1(self) -> None:
        """All unique genomes → diversity = 1.0."""
        researchers = [
            _make_researcher(0, 0, TraitLevel.OFF, TraitLevel.OFF, TraitLevel.OFF),
            _make_researcher(0, 1, TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
            _make_researcher(0, 2, TraitLevel.HIGH, TraitLevel.HIGH, TraitLevel.HIGH),
            _make_researcher(0, 3, TraitLevel.OFF, TraitLevel.LOW, TraitLevel.HIGH),
        ]
        result = compute_genome_diversity(researchers)
        assert result.diversity == 1.0
        assert result.warning is None

    def test_all_same_genome_low_diversity(self) -> None:
        """All same genome → diversity = 1/N."""
        researchers = [
            _make_researcher(0, i, TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW)
            for i in range(12)
        ]
        result = compute_genome_diversity(researchers)
        assert abs(result.diversity - 1 / 12) < 1e-9
        assert result.warning is not None

    def test_diversity_below_threshold_triggers_warning(self) -> None:
        """Diversity < 0.3 → warning flag set."""
        # 3 unique out of 12 = 0.25 < 0.3
        researchers = []
        for i in range(4):
            researchers.append(
                _make_researcher(0, i, TraitLevel.OFF, TraitLevel.OFF, TraitLevel.OFF)
            )
        for i in range(4):
            researchers.append(
                _make_researcher(0, i + 4, TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW)
            )
        for i in range(4):
            researchers.append(
                _make_researcher(
                    0, i + 8, TraitLevel.HIGH, TraitLevel.HIGH, TraitLevel.HIGH
                )
            )
        result = compute_genome_diversity(researchers)
        assert result.diversity == 3 / 12
        assert result.warning is not None

    def test_diversity_above_threshold_no_warning(self) -> None:
        """Diversity >= 0.3 → no warning."""
        # 4 unique out of 12 = 0.333 >= 0.3
        researchers = []
        for i in range(3):
            researchers.append(
                _make_researcher(0, i, TraitLevel.OFF, TraitLevel.OFF, TraitLevel.OFF)
            )
        for i in range(3):
            researchers.append(
                _make_researcher(0, i + 3, TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW)
            )
        for i in range(3):
            researchers.append(
                _make_researcher(
                    0, i + 6, TraitLevel.HIGH, TraitLevel.HIGH, TraitLevel.HIGH
                )
            )
        for i in range(3):
            researchers.append(
                _make_researcher(0, i + 9, TraitLevel.OFF, TraitLevel.LOW, TraitLevel.HIGH)
            )
        result = compute_genome_diversity(researchers)
        assert result.diversity == 4 / 12
        assert result.warning is None

    def test_empty_population_diversity_zero(self) -> None:
        """Empty population → diversity 0."""
        result = compute_genome_diversity([])
        assert result.diversity == 0.0


class TestTraitConvergence:
    """Tests for per-trait convergence tracking."""

    def test_strong_convergence_on_one_trait(self) -> None:
        """10/12 have novelty=high → 83% convergence on novelty."""
        researchers = []
        for i in range(10):
            researchers.append(
                _make_researcher(0, i, TraitLevel.HIGH, TraitLevel.LOW, TraitLevel.LOW)
            )
        for i in range(2):
            researchers.append(
                _make_researcher(0, i + 10, TraitLevel.OFF, TraitLevel.LOW, TraitLevel.LOW)
            )

        convergence = compute_trait_convergence(researchers)

        # novelty_seeking: HIGH is dominant at 10/12
        assert convergence["novelty_seeking"]["dominant_value"] == "high"
        assert abs(convergence["novelty_seeking"]["fraction"] - 10 / 12) < 1e-9

    def test_no_convergence(self) -> None:
        """Even distribution → low convergence fractions."""
        researchers = [
            _make_researcher(0, 0, TraitLevel.OFF, TraitLevel.OFF, TraitLevel.OFF),
            _make_researcher(0, 1, TraitLevel.LOW, TraitLevel.LOW, TraitLevel.LOW),
            _make_researcher(0, 2, TraitLevel.HIGH, TraitLevel.HIGH, TraitLevel.HIGH),
        ]
        convergence = compute_trait_convergence(researchers)

        # Each trait has 1/3 for each level — no strong convergence
        for trait in convergence:
            assert convergence[trait]["fraction"] <= 1 / 3 + 1e-9

    def test_all_traits_converged(self) -> None:
        """All same genome → 100% convergence on all traits."""
        researchers = [
            _make_researcher(0, i, TraitLevel.HIGH, TraitLevel.OFF, TraitLevel.LOW)
            for i in range(6)
        ]
        convergence = compute_trait_convergence(researchers)

        assert convergence["novelty_seeking"]["dominant_value"] == "high"
        assert convergence["novelty_seeking"]["fraction"] == 1.0
        assert convergence["skepticism"]["dominant_value"] == "off"
        assert convergence["skepticism"]["fraction"] == 1.0
        assert convergence["memory_depth"]["dominant_value"] == "low"
        assert convergence["memory_depth"]["fraction"] == 1.0

    def test_empty_population(self) -> None:
        """Empty population → empty convergence."""
        convergence = compute_trait_convergence([])
        assert len(convergence) == 0
