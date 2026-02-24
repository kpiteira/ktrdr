"""Population manager — seeding, selection, and reproduction.

Handles initial population creation, fitness-based selection (kill bottom N%),
and reproduction (survivors spawn mutated offspring).
"""

from __future__ import annotations

import math
import random
from typing import Any

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.genome import _TRAIT_NAMES, Genome, Researcher


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

    def select(
        self,
        results: list[dict[str, Any]],
        kill_rate: float = 0.5,
    ) -> tuple[list[str], list[str]]:
        """Select survivors by fitness rank, kill the bottom kill_rate%.

        Sort by fitness descending, then by researcher_id ascending for
        deterministic tie-breaking. Keep the top (1 - kill_rate) fraction.

        Returns:
            (survivor_ids, dead_ids)
        """
        # Sort: highest fitness first, then lowest ID for ties
        sorted_results = sorted(
            results,
            key=lambda r: (-r["fitness"], r["researcher_id"]),
        )

        keep_count = len(results) - math.floor(len(results) * kill_rate)
        survivor_ids = [r["researcher_id"] for r in sorted_results[:keep_count]]
        dead_ids = [r["researcher_id"] for r in sorted_results[keep_count:]]
        return survivor_ids, dead_ids

    def reproduce(
        self,
        survivors: list[Researcher],
        generation: int,
        seed: int | None = None,
        offspring_per_survivor: int = 2,
    ) -> list[Researcher]:
        """Create offspring from survivors via mutation.

        Each survivor produces offspring_per_survivor children, each with
        exactly 1 trait mutated. Uses seeded RNG for reproducibility.

        Args:
            survivors: Researchers that survived selection.
            generation: Generation number for the offspring.
            seed: Random seed (combined with generation for reproducibility).
            offspring_per_survivor: Number of offspring per survivor (default 2).

        Returns:
            New population of offspring researchers.
        """
        rng = random.Random(seed if seed is not None else generation)
        offspring: list[Researcher] = []
        index = 0

        for parent in survivors:
            for _ in range(offspring_per_survivor):
                child_genome = parent.genome.mutate(rng)

                # Build mutation description
                parent_dict = parent.genome.to_dict()
                child_dict = child_genome.to_dict()
                mutation_desc = ""
                for trait in _TRAIT_NAMES:
                    if parent_dict[trait] != child_dict[trait]:
                        mutation_desc = (
                            f"{trait}: {parent_dict[trait]}→{child_dict[trait]}"
                        )
                        break

                offspring.append(
                    Researcher(
                        id=f"r_g{generation:02d}_{index:03d}",
                        genome=child_genome,
                        generation=generation,
                        parent_id=parent.id,
                        mutation=mutation_desc,
                    )
                )
                index += 1

        return offspring
