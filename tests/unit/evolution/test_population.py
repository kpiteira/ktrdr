"""Tests for population manager — seeding, selection, and reproduction."""

from __future__ import annotations

from ktrdr.evolution.config import EvolutionConfig
from ktrdr.evolution.fitness import MINIMUM_FITNESS
from ktrdr.evolution.genome import Genome, Researcher
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


def _make_results(fitnesses: list[tuple[str, float]]) -> list[dict]:
    """Helper to create result dicts from (researcher_id, fitness) pairs."""
    return [
        {"researcher_id": rid, "fitness": f, "backtest_result": None}
        for rid, f in fitnesses
    ]


class TestPopulationManagerSelect:
    """Tests for PopulationManager.select()."""

    def test_top_half_survives_bottom_half_dies(self) -> None:
        """With 12 researchers and kill_rate=0.5, top 6 survive."""
        pm = PopulationManager()
        results = _make_results([(f"r_g00_{i:03d}", float(i)) for i in range(12)])
        # Fitness 0..11 — top 6 are IDs 006-011
        survivors, dead = pm.select(results, kill_rate=0.5)
        assert len(survivors) == 6
        assert len(dead) == 6
        assert set(survivors) == {f"r_g00_{i:03d}" for i in range(6, 12)}
        assert set(dead) == {f"r_g00_{i:03d}" for i in range(6)}

    def test_deterministic_tiebreaking_by_id(self) -> None:
        """Tied fitness: lower ID survives (deterministic)."""
        pm = PopulationManager()
        # All same fitness — should split deterministically by ID
        results = _make_results([(f"r_g00_{i:03d}", 1.0) for i in range(4)])
        survivors, dead = pm.select(results, kill_rate=0.5)
        assert len(survivors) == 2
        assert len(dead) == 2
        # Lower IDs survive on tie
        assert set(survivors) == {"r_g00_000", "r_g00_001"}
        assert set(dead) == {"r_g00_002", "r_g00_003"}

    def test_minimum_fitness_always_dies(self) -> None:
        """Researchers with MINIMUM_FITNESS always die regardless of rank."""
        pm = PopulationManager()
        results = _make_results(
            [
                ("r_g00_000", 2.0),
                ("r_g00_001", MINIMUM_FITNESS),
                ("r_g00_002", 1.0),
                ("r_g00_003", MINIMUM_FITNESS),
            ]
        )
        # kill_rate=0.5 → keep 2. Both MINIMUM_FITNESS should die.
        survivors, dead = pm.select(results, kill_rate=0.5)
        assert "r_g00_001" in dead
        assert "r_g00_003" in dead
        assert "r_g00_000" in survivors
        assert "r_g00_002" in survivors

    def test_edge_all_same_fitness_deterministic_split(self) -> None:
        """When all have identical fitness, split deterministically by ID."""
        pm = PopulationManager()
        results = _make_results([(f"r_g00_{i:03d}", 5.0) for i in range(6)])
        survivors, dead = pm.select(results, kill_rate=0.5)
        assert len(survivors) == 3
        assert len(dead) == 3
        # Lower IDs survive
        assert set(survivors) == {"r_g00_000", "r_g00_001", "r_g00_002"}

    def test_edge_only_one_above_minimum(self) -> None:
        """Only 1 researcher above MINIMUM_FITNESS — it survives."""
        pm = PopulationManager()
        results = _make_results(
            [
                ("r_g00_000", 1.0),
                ("r_g00_001", MINIMUM_FITNESS),
                ("r_g00_002", MINIMUM_FITNESS),
                ("r_g00_003", MINIMUM_FITNESS),
            ]
        )
        survivors, dead = pm.select(results, kill_rate=0.5)
        # kill_rate=0.5 keeps top 2, but 3 have MINIMUM → all 3 die
        # Actually: sort by fitness desc, keep top 2. top 2 = 000 and then
        # tie among 001/002/003 by ID → 001 survives
        assert "r_g00_000" in survivors

    def test_configurable_kill_rate(self) -> None:
        """kill_rate=0.3 keeps top 70%."""
        pm = PopulationManager()
        results = _make_results([(f"r_g00_{i:03d}", float(i)) for i in range(10)])
        survivors, dead = pm.select(results, kill_rate=0.3)
        assert len(survivors) == 7  # 10 * 0.7 = 7
        assert len(dead) == 3


def _make_survivors(n: int, generation: int = 0) -> list[Researcher]:
    """Helper to create n survivors with distinct genomes."""
    genomes = Genome.all_combinations()[:n]
    return [
        Researcher(
            id=f"r_g{generation:02d}_{i:03d}",
            genome=genomes[i],
            generation=generation,
        )
        for i in range(n)
    ]


class TestPopulationManagerReproduce:
    """Tests for PopulationManager.reproduce()."""

    def test_correct_offspring_count(self) -> None:
        """6 survivors → 12 offspring (2 per survivor)."""
        pm = PopulationManager()
        survivors = _make_survivors(6)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        assert len(offspring) == 12

    def test_offspring_have_parent_id(self) -> None:
        """Each offspring should reference its parent."""
        pm = PopulationManager()
        survivors = _make_survivors(3)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        parent_ids = {o.parent_id for o in offspring}
        expected = {s.id for s in survivors}
        assert parent_ids == expected

    def test_each_offspring_has_one_mutation(self) -> None:
        """Each offspring genome differs from parent by exactly 1 trait."""
        pm = PopulationManager()
        survivors = _make_survivors(6)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        for child in offspring:
            # Find parent
            parent = next(s for s in survivors if s.id == child.parent_id)
            parent_dict = parent.genome.to_dict()
            child_dict = child.genome.to_dict()
            diffs = sum(1 for k in parent_dict if parent_dict[k] != child_dict[k])
            assert diffs == 1, f"{child.id}: expected 1 diff, got {diffs}"

    def test_mutation_description_is_accurate(self) -> None:
        """Mutation description should describe the actual trait change."""
        pm = PopulationManager()
        survivors = _make_survivors(3)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        for child in offspring:
            assert child.mutation is not None
            # Should contain "→" showing the change
            assert "→" in child.mutation or "->" in child.mutation

    def test_population_size_stable(self) -> None:
        """12 → select 6 → reproduce → 12."""
        pm = PopulationManager()
        survivors = _make_survivors(6)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        assert len(offspring) == 12

    def test_offspring_generation_number(self) -> None:
        """Offspring generation should be the specified generation."""
        pm = PopulationManager()
        survivors = _make_survivors(3, generation=2)
        offspring = pm.reproduce(survivors, generation=3, seed=42)
        for child in offspring:
            assert child.generation == 3

    def test_offspring_ids_follow_format(self) -> None:
        """Offspring IDs should follow r_gNN_NNN format for their generation."""
        pm = PopulationManager()
        survivors = _make_survivors(3, generation=0)
        offspring = pm.reproduce(survivors, generation=1, seed=42)
        for child in offspring:
            assert child.id.startswith("r_g01_")

    def test_reproducible_with_same_seed(self) -> None:
        """Same seed produces identical offspring."""
        pm = PopulationManager()
        survivors = _make_survivors(6)
        off1 = pm.reproduce(survivors, generation=1, seed=42)
        off2 = pm.reproduce(survivors, generation=1, seed=42)
        genomes1 = [o.genome.to_dict() for o in off1]
        genomes2 = [o.genome.to_dict() for o in off2]
        assert genomes1 == genomes2
