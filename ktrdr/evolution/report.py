"""Evolution report — monoculture detection and analysis utilities.

Provides functions for analyzing genome diversity, trait convergence,
and generating evolution experiment reports.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from ktrdr.evolution.genome import Researcher, _TRAIT_NAMES

# Diversity below this threshold triggers a monoculture warning
_DIVERSITY_WARNING_THRESHOLD = 0.3


@dataclass
class MonocultureWarning:
    """Warning about low genome diversity in a population."""

    diversity: float
    unique_genomes: int
    population_size: int
    message: str


@dataclass
class DiversityResult:
    """Result of genome diversity computation."""

    diversity: float
    unique_genomes: int
    population_size: int
    warning: MonocultureWarning | None


def compute_genome_diversity(
    population: list[Researcher],
) -> DiversityResult:
    """Compute genome diversity for a population.

    diversity = len(unique_genomes) / population_size (0.0 to 1.0)

    Args:
        population: List of researchers in a generation.

    Returns:
        DiversityResult with diversity score and optional warning.
    """
    if not population:
        return DiversityResult(
            diversity=0.0, unique_genomes=0, population_size=0, warning=None
        )

    unique = len({r.genome for r in population})
    pop_size = len(population)
    diversity = unique / pop_size

    warning = None
    if diversity < _DIVERSITY_WARNING_THRESHOLD:
        warning = MonocultureWarning(
            diversity=diversity,
            unique_genomes=unique,
            population_size=pop_size,
            message=(
                f"Low genome diversity: {unique}/{pop_size} unique genomes "
                f"({diversity:.1%}). Population may be converging."
            ),
        )

    return DiversityResult(
        diversity=diversity,
        unique_genomes=unique,
        population_size=pop_size,
        warning=warning,
    )


def compute_trait_convergence(
    population: list[Researcher],
) -> dict[str, dict[str, Any]]:
    """Compute per-trait convergence for a population.

    For each trait, finds the dominant value and its fraction of the population.

    Args:
        population: List of researchers in a generation.

    Returns:
        Dict mapping trait name → {dominant_value, fraction, distribution}.
    """
    if not population:
        return {}

    result: dict[str, dict[str, Any]] = {}
    pop_size = len(population)

    for trait_name in _TRAIT_NAMES:
        values = [
            getattr(r.genome, trait_name).name.lower() for r in population
        ]
        counter = Counter(values)
        dominant_value, dominant_count = counter.most_common(1)[0]

        result[trait_name] = {
            "dominant_value": dominant_value,
            "fraction": dominant_count / pop_size,
            "distribution": dict(counter),
        }

    return result
