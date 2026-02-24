"""Genome and Researcher data models for evolution.

The genome encodes researcher personality as 3 traits x 3 levels (27 combinations).
Mutation shifts exactly 1 random trait by ±1 level with clamping.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TraitLevel(Enum):
    """Ordered trait level: OFF < LOW < HIGH.

    Ordering matters for mutation — OFF can only go to LOW,
    HIGH can only go to LOW.
    """

    OFF = 0
    LOW = 1
    HIGH = 2


# Trait names in stable order for iteration
_TRAIT_NAMES = ("novelty_seeking", "skepticism", "memory_depth")


@dataclass(frozen=True)
class Genome:
    """Three-trait genome encoding researcher personality.

    Traits:
        novelty_seeking: How different from recent strategies (systematic → creative)
        skepticism: Conservatism in strategy design (accept results → extremely conservative)
        memory_depth: How the LLM uses experiment history (ignore → synthesize all)
    """

    novelty_seeking: TraitLevel = TraitLevel.LOW
    skepticism: TraitLevel = TraitLevel.LOW
    memory_depth: TraitLevel = TraitLevel.LOW

    def mutate(self, rng: random.Random | None = None) -> Genome:
        """Return a new genome with exactly 1 trait shifted ±1 level.

        Clamping: OFF can only go to LOW, HIGH can only go to LOW.
        """
        if rng is None:
            rng = random.Random()

        trait = rng.choice(_TRAIT_NAMES)
        current: TraitLevel = getattr(self, trait)

        # Determine possible directions
        if current == TraitLevel.OFF:
            new_level = TraitLevel.LOW
        elif current == TraitLevel.HIGH:
            new_level = TraitLevel.LOW
        else:
            # LOW can go to OFF or HIGH
            new_level = rng.choice([TraitLevel.OFF, TraitLevel.HIGH])

        # Build new genome with the mutated trait
        values = {name: getattr(self, name) for name in _TRAIT_NAMES}
        values[trait] = new_level
        return Genome(**values)

    def to_dict(self) -> dict[str, str]:
        """Serialize to dict with string trait values."""
        return {name: getattr(self, name).name.lower() for name in _TRAIT_NAMES}

    @classmethod
    def from_dict(cls, d: dict[str, str]) -> Genome:
        """Reconstruct a genome from a serialized dict."""
        return cls(**{name: TraitLevel[d[name].upper()] for name in _TRAIT_NAMES})

    @classmethod
    def all_combinations(cls) -> list[Genome]:
        """Return all 27 possible genomes."""
        levels = list(TraitLevel)
        return [
            cls(novelty_seeking=n, skepticism=s, memory_depth=m)
            for n in levels
            for s in levels
            for m in levels
        ]


@dataclass
class Researcher:
    """A researcher with genome, identity, and lineage.

    Attributes:
        id: Unique ID in format r_g{generation:02d}_{index:03d}
        genome: The researcher's trait genome
        generation: Generation number (0 for initial population)
        parent_id: ID of parent researcher (None for generation 0)
        mutation: Description of mutation from parent (None for generation 0)
    """

    id: str
    genome: Genome
    generation: int
    parent_id: str | None = None
    mutation: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for YAML persistence."""
        return {
            "id": self.id,
            "genome": self.genome.to_dict(),
            "generation": self.generation,
            "parent_id": self.parent_id,
            "mutation": self.mutation,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Researcher:
        """Reconstruct a researcher from a serialized dict."""
        return cls(
            id=d["id"],
            genome=Genome.from_dict(d["genome"]),
            generation=d["generation"],
            parent_id=d.get("parent_id"),
            mutation=d.get("mutation"),
        )
