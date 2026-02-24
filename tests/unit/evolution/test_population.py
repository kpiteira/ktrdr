"""Tests for population manager — seeding initial populations."""

from __future__ import annotations

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.population import PopulationManager


class TestPopulationManagerSeed:
    """Tests for PopulationManager.seed()."""

    def test_returns_correct_count(self) -> None:
        """seed() should return exactly population_size researchers."""
        config = EvolutionConfig(population_size=12, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        assert len(population) == 12

    def test_small_population(self) -> None:
        """seed() should work with small populations."""
        config = EvolutionConfig(population_size=3, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        assert len(population) == 3

    def test_all_generation_zero(self) -> None:
        """All seeded researchers should have generation=0."""
        config = EvolutionConfig(population_size=6, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        for r in population:
            assert r.generation == 0

    def test_all_ids_unique(self) -> None:
        """All researcher IDs should be unique."""
        config = EvolutionConfig(population_size=12, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        ids = [r.id for r in population]
        assert len(set(ids)) == 12

    def test_id_format(self) -> None:
        """IDs should follow r_g00_NNN format."""
        config = EvolutionConfig(population_size=3, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        expected_ids = ["r_g00_000", "r_g00_001", "r_g00_002"]
        actual_ids = [r.id for r in population]
        assert actual_ids == expected_ids

    def test_no_parent_fields(self) -> None:
        """Seeded researchers should have no parent lineage."""
        config = EvolutionConfig(population_size=6, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        for r in population:
            assert r.parent_id is None
            assert r.mutation is None

    def test_no_duplicate_genomes(self) -> None:
        """No duplicate genomes when population_size <= 27."""
        config = EvolutionConfig(population_size=12, seed=42)
        pm = PopulationManager()
        population = pm.seed(config)
        genome_dicts = [r.genome.to_dict() for r in population]
        genome_tuples = [tuple(sorted(d.items())) for d in genome_dicts]
        assert len(set(genome_tuples)) == 12

    def test_seeded_reproducibility(self) -> None:
        """Same seed should produce same population."""
        config = EvolutionConfig(population_size=12, seed=42)
        pm = PopulationManager()
        pop1 = pm.seed(config)
        pop2 = pm.seed(config)
        genomes1 = [r.genome.to_dict() for r in pop1]
        genomes2 = [r.genome.to_dict() for r in pop2]
        assert genomes1 == genomes2

    def test_different_seeds_produce_different_populations(self) -> None:
        """Different seeds should (almost certainly) produce different populations."""
        config1 = EvolutionConfig(population_size=12, seed=42)
        config2 = EvolutionConfig(population_size=12, seed=99)
        pm = PopulationManager()
        pop1 = pm.seed(config1)
        pop2 = pm.seed(config2)
        genomes1 = [r.genome.to_dict() for r in pop1]
        genomes2 = [r.genome.to_dict() for r in pop2]
        assert genomes1 != genomes2
