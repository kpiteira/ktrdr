"""Population manager — seeding and lifecycle for researcher populations.

Handles initial population creation with good genome diversity.
Selection and reproduction added in M2.
"""

from __future__ import annotations

import random

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.genome import Genome, Researcher


class PopulationManager:
    """Manages researcher population lifecycle."""

    def seed(self, config: EvolutionConfig) -> list[Researcher]:
        """Create an initial population with diverse genomes.

        Randomly samples without replacement from all 27 genome combinations.
        Uses config.seed for reproducibility (None = random).
        """
        rng = random.Random(config.seed)
        all_genomes = Genome.all_combinations()
        sampled = rng.sample(all_genomes, k=config.population_size)

        return [
            Researcher(
                id=f"r_g00_{i:03d}",
                genome=genome,
                generation=0,
            )
            for i, genome in enumerate(sampled)
        ]
