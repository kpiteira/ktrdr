# Handoff: M2 — Evolution Loop

## Task 2.1 Complete: Selection

**Key patterns:**
- `PopulationManager.select(results, kill_rate=0.5)` returns `(survivor_ids, dead_ids)`
- Sort by fitness descending, then researcher_id ascending for deterministic tie-breaking
- `keep_count = len(results) - math.floor(len(results) * kill_rate)`
- No special MINIMUM_FITNESS logic needed — they naturally sort to the bottom

**Next task notes:**
- Results are `list[dict]` with keys: `researcher_id`, `fitness`, `backtest_result`
- `kill_rate` comes from `EvolutionConfig.kill_rate` (default 0.5)

## Task 2.2 Complete: Reproduction

**Key patterns:**
- `PopulationManager.reproduce(survivors, generation, seed, offspring_per_survivor=2)`
- Each offspring has exactly 1 mutated trait from parent (via `Genome.mutate(rng)`)
- Mutation description: `"novelty_seeking: off→low"` (uses `→` character)
- Offspring IDs: `r_g{gen:02d}_{index:03d}` where index is sequential
- RNG seeded from the `seed` parameter (or `generation` if seed is None)

**Next task notes:**
- `_TRAIT_NAMES` imported from `ktrdr.evolution.genome` for stable iteration order
- Each survivor produces `offspring_per_survivor` children (default 2)

## Task 2.3 Complete: Multi-Generation Loop

**Key patterns:**
- `GenerationHarness.run(population_manager)` executes full evolution loop
- Seed → run_generation → select → reproduce → save → repeat
- `_update_summary()` called after each generation — incremental
- Budget exhaustion: if all results are MINIMUM_FITNESS, abort early
- `EvolutionTracker.save_summary()` / `load_summary()` added for cross-generation stats

**Summary format:**
```yaml
generations:
  - generation: 0
    population_size: 6
    mean_fitness: 1.5
    max_fitness: 3.2
    min_fitness: -999.0
    successful: 5
    failed: 1
```

## Task 2.4 Complete: Resume Capability

**Key patterns:**
- `GenerationHarness.resume(population_manager)` continues from last completed generation
- `_find_incomplete_generation(start_gen)` checks for ops without results
- `_recover_incomplete_generation()` polls/re-triggers operations
- Already-complete runs detected via `get_last_completed_generation()`
- Failed ops get re-triggered; completed ops get their results read

**Next task notes:**
- Resume needs a PopulationManager to derive next-gen populations
- Selection + reproduction happens at the end of each resumed generation

## Task 2.5 Complete: CLI Status and Resume

**Key patterns:**
- `ktrdr evolve start` now uses `harness.run(pm)` for multi-generation execution
- `ktrdr evolve status [run_id]` shows per-generation stats in Rich table
- `ktrdr evolve resume <run_id>` calls `harness.resume(pm)`
- `_get_evolution_dir()` extracted as patchable function for testing
- `_print_run_summary()` shared between all three commands
- Heavy imports deferred inside functions for CLI startup speed
- TYPE_CHECKING block for Console, EvolutionConfig, EvolutionTracker annotations

**CLI test notes:**
- Uses `CleanCliRunner` from `tests/unit/cli/conftest.py`
- `_get_evolution_dir` patched to point at tmp directories
- Resume test patches `GenerationHarness.resume` as AsyncMock

## Task 2.6 Complete: E2E Validation

**E2E results (run_20260223_211402):**
- Gen 0: 6 researchers triggered, 1 succeeded (fitness -3.2529), 5 failed
- Selection happened: 3 survived (r_g00_001, r_g00_000, r_g00_002), 3 died
- Gen 1 population: 6 offspring with parent_ids and mutations (e.g., `memory_depth: off→low`)
- Gen 1 hit budget_exhausted (daily $5 budget consumed) → all failed → early abort
- `ktrdr evolve status` correctly shows per-generation Rich table
- State persisted: config.yaml, population.yaml, results.yaml, operations.yaml, summary.yaml

**Verified mechanics:**
1. ✅ Researcher triggering with at_capacity retry (exponential backoff)
2. ✅ Operation polling and result collection
3. ✅ Fitness evaluation (real metrics + MINIMUM_FITNESS for failures)
4. ✅ Selection: rank by fitness, deterministic tie-breaking by ID
5. ✅ Reproduction: 3 survivors × 2 = 6 offspring, each with 1 mutation
6. ✅ Early abort when all researchers fail (correct behavior)
7. ✅ CLI commands: start, status (with/without run_id)
8. ✅ Summary.yaml incremental updates

**Not fully validated (pre-existing pipeline issues):**
- Full 3-gen completion: blocked by experiment memory `'str' object has no attribute 'get'` bug
  causing most backtest_results to be null. This is a pipeline bug, not evolution.
- Resume CLI: mechanically correct per unit tests; live resume not triggered

**Gotchas for future milestones:**
- Budget is file-based per day in `data/budget/YYYY-MM-DD.json` (NOT in-memory)
- Daily limit is $5.00; a 3-gen × 6-researcher run costs ~$2-3 with haiku
- Reset budget by moving/deleting today's budget file
- ANTHROPIC_API_KEY must be in docker-compose.override.yml for sandbox
- Experiment memory str bug causes most researchers to get "poor" verdict with null backtest
