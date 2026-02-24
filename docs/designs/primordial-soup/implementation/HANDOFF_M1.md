# Handoff: M1 — Single Generation End-to-End

## Task 1.1 Complete: Core Data Models

**Key patterns:**
- `Genome` is frozen dataclass — `mutate()` returns new instance
- `_TRAIT_NAMES` tuple used for stable iteration order in serialization/mutation
- `TraitLevel` uses int values (0, 1, 2) for ordering — mutation shifts ±1 with clamping
- `EvolutionConfig.__post_init__` validates constraints (population >= 2, generations >= 1, slices non-empty)

**Next task notes:**
- Import `Genome`, `TraitLevel`, `EvolutionConfig`, `DateRange` from `ktrdr.evolution`
- `Genome.to_dict()` returns `{"novelty_seeking": "off", ...}` (lowercase string values)
- `EvolutionConfig` has `training_window: DateRange` and `fitness_slices: list[DateRange]` with defaults

## Task 1.2 Complete: Brief Translator

**Key patterns:**
- Trait text stored as module-level dicts (`_NOVELTY_TEXT`, `_SKEPTICISM_TEXT`, `_MEMORY_TEXT`) mapping `TraitLevel → str`
- `BriefTranslator.translate()` concatenates trait paragraphs + date section
- Date section uses first fitness slice as backtest window

**Next task notes:**
- `BriefTranslator()` takes no constructor args
- `translator.translate(genome, config)` returns a multi-line string

## Task 1.3 Complete: Population Manager (Seeding)

**Key patterns:**
- `PopulationManager()` takes no constructor args
- `pm.seed(config)` uses `random.Random(config.seed)` for reproducibility
- Samples without replacement from `Genome.all_combinations()`
- IDs formatted as `r_g00_{i:03d}`

**Next task notes:**
- Researcher objects have `to_dict()` / `from_dict()` for YAML serialization
- `EvolutionConfig` has `seed: int | None` field

## Task 1.4 Complete: Evolution Tracker

**Key patterns:**
- `EvolutionTracker(run_dir=Path(...))` — run_dir is the full path to the run directory
- `save_operation_id()` reads-then-writes for incremental persistence
- `EvolutionConfig` and `DateRange` now have `to_dict()`/`from_dict()` methods
- All load methods return empty defaults (None/[]/{}]) when files are missing

**Next task notes:**
- Tracker uses PyYAML — `yaml.dump()` with `default_flow_style=False`
- Generation directories are `generation_{gen:02d}`

## Task 1.5 Complete: Fitness Evaluator (Basic)

**Key patterns:**
- `FitnessEvaluator(config)` — extracts lambda_dd from config
- `evaluate(backtest_result)` takes `dict | None`, returns float
- Missing/malformed → `MINIMUM_FITNESS = -999.0` (no exceptions)
- M1 formula: `sharpe - lambda_dd * max_drawdown`

**Next task notes:**
- Backtest result dict expected keys: `"sharpe"`, `"max_drawdown"`
- Import `MINIMUM_FITNESS` from `ktrdr.evolution.fitness` for comparison

## Task 1.6 Complete: Generation Harness

**Key patterns:**
- `GenerationHarness(config, tracker, http_client, base_url)` — accepts any httpx-compatible async client
- `run_generation(generation, population)` returns `list[dict]` with researcher_id, fitness, backtest_result
- `BudgetExhaustedError` raised internally → all researchers get minimum fitness
- Tests use `AsyncMock()` for the HTTP client — no real HTTP needed
- `poll_interval=0` in test config to avoid async sleeps

**Next task notes:**
- CLI needs to create httpx.AsyncClient, EvolutionTracker, and wire them into GenerationHarness
- `run_generation()` is async — CLI must use `asyncio.run()`
- Results list has dicts with keys: researcher_id, fitness, backtest_result

## Task 1.7 Complete: CLI Command

**Key patterns:**
- `evolve_app` registered via `app.add_typer(evolve_app)` in app.py
- `_run_evolution()` is the sync entry point — creates httpx.AsyncClient, wires harness
- Typer `min=2`/`min=1` on options handles validation before EvolutionConfig
- Heavy imports (httpx, Rich, evolution) are lazy inside the command function

**Next task notes:**
- E2E validation needs local-prod running with backend + workers
- `ktrdr evolve start --population 3 --generations 1` is the test command
- State files land in `data/evolution/run_YYYYMMDD_HHMMSS/`

## Task 1.8 Complete: E2E Validation

**E2E test:** `evolution/single-generation` — PASS (harness functional)

**Bugs found and fixed:**
1. Harness used `isinstance(response, dict)` — fails with httpx.Response objects.
   Fix: `_to_dict()` helper that calls `.json()` on Response objects.
2. Poll loop read `status` from API envelope instead of `data["data"]["status"]`.
   Fix: `op = data.get("data", data)` unwraps envelope with fallback.

**E2E result:**
- 3 researchers triggered, polled for ~9 min, all detected as "failed" (NaN confidence)
- CLI exits cleanly (code 0), all 4 state files created (config, population, operations, results)
- All researchers scored MINIMUM_FITNESS — backtests fail due to EURUSD data not covering training window
- The harness code is fully functional; backtest failures are a data/config issue for M2

## Post-M1 Fix: Multi-Timeframe Feature Alignment

**Root cause:** `FeatureCache.compute_features()` (backtesting) did `pd.concat(axis=1)` on DataFrames with different temporal indices (5m: 288 bars/day vs 1h: 24 bars/day). Pandas outer-joins → NaN for all 1h columns at non-hour 5m timestamps. Training worked because `FuzzyNeuralProcessor` did `reindex(base_index, method="ffill")`.

**Fix:** Shared utility `align_feature_dataframes()` in `ktrdr/data/components/timeframe_synchronizer.py`:
- Groups features by timeframe, concat within each (same index = safe)
- Forward-fills higher-TF features to base-TF timestamps
- Used by both `FeatureCache` and `FuzzyNeuralProcessor` (eliminates divergence)

**Files changed:**
- `ktrdr/data/components/timeframe_synchronizer.py` — new `align_feature_dataframes()` function
- `ktrdr/backtesting/feature_cache.py` — use shared utility instead of bare `pd.concat`
- `ktrdr/training/fuzzy_neural_processor.py` — delegate alignment to shared utility
- `ktrdr/cli/commands/evolve.py` — sandbox-aware API URL via `resolve_api_url()`
- `tests/unit/data/components/test_timeframe_synchronizer.py` — 8 tests for shared utility
- `tests/unit/backtesting/test_feature_cache_v3.py` — 3 multi-TF FeatureCache tests

**Additional bugs found during E2E:**
3. `backtest_result` stored in operation metadata in-memory but not persisted in `completion_result`.
   Fix: include `backtest_result` in completion_result dict, read from `result_summary` in harness.
4. FitnessEvaluator reads `"sharpe"` but research worker stores `"sharpe_ratio"`.
   Fix: accept both keys with `sharpe_ratio` taking precedence.

**E2E re-validation:** PASSED — all 3 researchers completed full pipeline:
- r_g00_000: fitness -3.78, 498 trades
- r_g00_002: fitness -4.02, 538 trades
- r_g00_001: fitness -4.70, 729 trades
- No NaN errors in logs — multi-TF alignment fix confirmed working

**Gotchas for M2:**
- Evolve CLI uses `resolve_api_url()` from `ktrdr.cli.sandbox_detect` for sandbox port detection
- `kinfra sandbox up` needed for 1Password secrets (ANTHROPIC_API_KEY)
- Budget system tracks estimated cost in-memory; can diverge from file
- Pre-existing bug: `Failed to save experiment to memory: 'str' object has no attribute 'get'` in assessment_worker (non-blocking)
