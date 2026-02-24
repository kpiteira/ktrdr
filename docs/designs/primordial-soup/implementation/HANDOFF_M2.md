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

**E2E results (run_20260223_220336) — Full 3-gen evolution:**
- Gen 0: 4 researchers triggered, 1 succeeded (fitness -3.26), 3 failed → 2 survived, 2 died
- Gen 1: 4 researchers, 2 succeeded (max fitness 0.0), 2 failed → 2 survived, 2 died
- Gen 2: 4 researchers, all 4 succeeded (max fitness -3.09)
- Full 3-generation evolution completed successfully

**Verified mechanics:**
1. ✅ Researcher triggering with at_capacity retry (exponential backoff)
2. ✅ Operation polling and result collection
3. ✅ Fitness evaluation (real metrics + MINIMUM_FITNESS for failures)
4. ✅ Selection: rank by fitness, deterministic tie-breaking by ID
5. ✅ Reproduction: survivors × 2 offspring, each with 1 mutation
6. ✅ Multi-generation loop: seed → trigger → poll → select → reproduce → repeat
7. ✅ CLI commands: start, status (with/without run_id)
8. ✅ Summary.yaml incremental updates
9. ✅ Population lineage tracking (parent_id, mutation descriptions)

**Pipeline bugs fixed during validation:**
1. **Experiment memory str bug** — `yaml.safe_load()` can return str instead of dict.
   Fixed in: `assessment_worker.py`, `strategy_utils.py`, `research_worker.py`
   (Added `isinstance(result, dict)` check after yaml.safe_load)
2. **V3 indicators format** — Strategy indicators is a dict in V3, code assumed list.
   Fixed in: `assessment_worker.py`, `strategy_utils.py`
3. **Indicator output name mismatch** — `compute()` returned prefixed columns (e.g. `AD_Line`)
   but `get_output_names()` declared semantic names (e.g. `line`).
   Fixed in: `ad_line.py`, `cmf_indicator.py`
4. **save_assessment missing args** — Haiku sometimes drops required tool args.
   Fixed in: `executor.py` (made parameters optional with defaults)

**Gotchas for future milestones:**
- Budget is file-based per day in `data/budget/YYYY-MM-DD.json` (NOT in-memory)
- Daily limit configurable via `KTRDR_AGENT_DAILY_BUDGET` env var (default $5.00)
- A 3-gen × 4-researcher run costs ~$2.50 with haiku
- Reset budget by moving/deleting today's budget file
- ANTHROPIC_API_KEY must be injected into docker-compose.override.yml for sandbox E2E
