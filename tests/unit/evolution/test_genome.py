"""Tests for genome and researcher data models."""

from __future__ import annotations

import random

from ktrdr.evolution.genome import Genome, Researcher, TraitLevel


class TestTraitLevel:
    """Tests for the TraitLevel enum."""

    def test_has_three_levels(self) -> None:
        """TraitLevel should have exactly OFF, LOW, HIGH."""
        assert set(TraitLevel) == {TraitLevel.OFF, TraitLevel.LOW, TraitLevel.HIGH}

    def test_ordering(self) -> None:
        """OFF < LOW < HIGH."""
        assert TraitLevel.OFF.value < TraitLevel.LOW.value < TraitLevel.HIGH.value


class TestGenome:
    """Tests for the Genome data model."""

    def test_all_combinations_count(self) -> None:
        """all_combinations() should return exactly 27 genomes (3^3)."""
        combos = Genome.all_combinations()
        assert len(combos) == 27

    def test_all_combinations_unique(self) -> None:
        """All 27 genomes should be distinct."""
        combos = Genome.all_combinations()
        as_dicts = [g.to_dict() for g in combos]
        # Convert dicts to tuples of sorted items for set comparison
        as_tuples = [tuple(sorted(d.items())) for d in as_dicts]
        assert len(set(as_tuples)) == 27

    def test_mutation_shifts_exactly_one_trait(self) -> None:
        """mutate() should change exactly 1 trait by exactly 1 level."""
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        rng = random.Random(42)
        mutated = genome.mutate(rng=rng)

        # Count changed traits
        changes = 0
        for trait in ["novelty_seeking", "skepticism", "memory_depth"]:
            old_val = getattr(genome, trait)
            new_val = getattr(mutated, trait)
            if old_val != new_val:
                changes += 1
                # Check shift is exactly ±1
                assert abs(old_val.value - new_val.value) == 1

        assert changes == 1

    def test_mutation_returns_new_genome(self) -> None:
        """mutate() should return a new genome, not modify the original."""
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        rng = random.Random(42)
        mutated = genome.mutate(rng=rng)
        assert mutated is not genome

    def test_mutation_clamps_off(self) -> None:
        """OFF trait can only mutate to LOW (not below OFF)."""
        genome = Genome(
            novelty_seeking=TraitLevel.OFF,
            skepticism=TraitLevel.OFF,
            memory_depth=TraitLevel.OFF,
        )
        # Run many mutations — all must go to LOW
        for seed in range(100):
            rng = random.Random(seed)
            mutated = genome.mutate(rng=rng)
            for trait in ["novelty_seeking", "skepticism", "memory_depth"]:
                new_val = getattr(mutated, trait)
                assert new_val in (TraitLevel.OFF, TraitLevel.LOW)

    def test_mutation_clamps_high(self) -> None:
        """HIGH trait can only mutate to LOW (not above HIGH)."""
        genome = Genome(
            novelty_seeking=TraitLevel.HIGH,
            skepticism=TraitLevel.HIGH,
            memory_depth=TraitLevel.HIGH,
        )
        for seed in range(100):
            rng = random.Random(seed)
            mutated = genome.mutate(rng=rng)
            for trait in ["novelty_seeking", "skepticism", "memory_depth"]:
                new_val = getattr(mutated, trait)
                assert new_val in (TraitLevel.HIGH, TraitLevel.LOW)

    def test_mutation_coverage(self) -> None:
        """Over 1000 mutations, all 3 traits should get mutated."""
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        mutated_traits: set[str] = set()
        for seed in range(1000):
            rng = random.Random(seed)
            mutated = genome.mutate(rng=rng)
            for trait in ["novelty_seeking", "skepticism", "memory_depth"]:
                if getattr(genome, trait) != getattr(mutated, trait):
                    mutated_traits.add(trait)

        assert mutated_traits == {"novelty_seeking", "skepticism", "memory_depth"}

    def test_to_dict(self) -> None:
        """to_dict() should return a dict with trait names as keys."""
        genome = Genome(
            novelty_seeking=TraitLevel.OFF,
            skepticism=TraitLevel.HIGH,
            memory_depth=TraitLevel.LOW,
        )
        d = genome.to_dict()
        assert d == {
            "novelty_seeking": "off",
            "skepticism": "high",
            "memory_depth": "low",
        }

    def test_from_dict(self) -> None:
        """from_dict() should reconstruct a genome from a dict."""
        d = {
            "novelty_seeking": "off",
            "skepticism": "high",
            "memory_depth": "low",
        }
        genome = Genome.from_dict(d)
        assert genome.novelty_seeking == TraitLevel.OFF
        assert genome.skepticism == TraitLevel.HIGH
        assert genome.memory_depth == TraitLevel.LOW

    def test_to_dict_from_dict_roundtrip(self) -> None:
        """to_dict/from_dict should roundtrip for all 27 genomes."""
        for genome in Genome.all_combinations():
            reconstructed = Genome.from_dict(genome.to_dict())
            assert reconstructed == genome


class TestResearcher:
    """Tests for the Researcher data model."""

    def test_id_format(self) -> None:
        """Researcher ID should be r_g{gen:02d}_{index:03d}."""
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        researcher = Researcher(
            id="r_g00_003",
            genome=genome,
            generation=0,
        )
        assert researcher.id == "r_g00_003"

    def test_default_parent_fields(self) -> None:
        """Researcher should default parent_id and mutation to None."""
        genome = Genome(
            novelty_seeking=TraitLevel.LOW,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        researcher = Researcher(
            id="r_g00_000",
            genome=genome,
            generation=0,
        )
        assert researcher.parent_id is None
        assert researcher.mutation is None

    def test_lineage_fields(self) -> None:
        """Researcher should carry parent_id and mutation description."""
        genome = Genome(
            novelty_seeking=TraitLevel.HIGH,
            skepticism=TraitLevel.LOW,
            memory_depth=TraitLevel.LOW,
        )
        researcher = Researcher(
            id="r_g01_000",
            genome=genome,
            generation=1,
            parent_id="r_g00_003",
            mutation="novelty_seeking: low -> high",
        )
        assert researcher.parent_id == "r_g00_003"
        assert researcher.mutation == "novelty_seeking: low -> high"
        assert researcher.generation == 1

    def test_to_dict_from_dict_roundtrip(self) -> None:
        """Researcher should serialize and deserialize cleanly."""
        genome = Genome(
            novelty_seeking=TraitLevel.HIGH,
            skepticism=TraitLevel.OFF,
            memory_depth=TraitLevel.LOW,
        )
        researcher = Researcher(
            id="r_g01_002",
            genome=genome,
            generation=1,
            parent_id="r_g00_005",
            mutation="skepticism: low -> off",
        )
        d = researcher.to_dict()
        reconstructed = Researcher.from_dict(d)
        assert reconstructed.id == researcher.id
        assert reconstructed.genome == researcher.genome
        assert reconstructed.generation == researcher.generation
        assert reconstructed.parent_id == researcher.parent_id
        assert reconstructed.mutation == researcher.mutation
