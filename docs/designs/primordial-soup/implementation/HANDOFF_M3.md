# Handoff: Primordial Soup M3 — Full Fitness + Reporting

## Status

| Task | Status | Notes |
|------|--------|-------|
| 3.1 Additional Backtests | Done | harness.py: _run_additional_backtests, retry once |
| 3.2 Full Fitness Function | Done | Gates + multi-slice scoring + complexity |
| 3.3 Monoculture Detection | Done | report.py: diversity + trait convergence |
| 3.4 CLI Report Command | Done | evolve report: trend, genome, lineage, diversity |
| 3.5 E2E Validation | Pending | Requires local-prod with backend + workers |

## Key Patterns

### Multi-Slice Fitness (fitness.py)
- **Layer A gates**: min_trades (30), max_drawdown (35%), action_diversity (90%) — per slice, any failure = MINIMUM_FITNESS
- **Layer B scoring**: `mean(Sharpe) - λ_dd*mean(DD) - λ_var*std(Sharpe) - λ_cmp*complexity`
- Complexity defaults to 0.5 when strategy_info unavailable
- Action diversity gate skips gracefully when long_trades/short_trades not in result
- `evaluate()` backward-compat wrapper delegates to `evaluate_slices([result])`

### Additional Backtests (harness.py)
- After research completes: trigger 2 more backtests via POST /api/v1/backtests/start
- Uses `config.fitness_slices[1:]` for date ranges
- Retry once per backtest on failure; graceful degradation to fewer slices
- Skipped for researchers that failed research (no model_path)
- All slice results collected in `slice_results` list and passed to `evaluate_slices()`

### Report Command (evolve.py)
- `ktrdr evolve report [run_id]` — defaults to most recent run
- Sections: Run Summary panel, Fitness Trend table, Genome Distribution, Diversity Across Generations, Lineage of best performer, Experiment Summary
- Uses `trace_lineage()` from report.py to follow parent_id chain
- Uses `compute_genome_diversity()` and `compute_trait_convergence()` from report.py

### Lineage Tracing (report.py)
- `trace_lineage(tracker, researcher_id, generation)` → list from gen 0 to current
- Follows parent_id chain through saved population data
- Returns partial chain if parent data missing

## Gotchas

1. **Test fixtures need `total_trades: 50`** in mock backtest results — otherwise the min-trades gate (30) fails
2. **Existing tests use `_SINGLE_SLICE` config** to avoid triggering additional backtests
3. **Complexity penalty of 0.05** (default 0.5 * λ_complexity 0.1) affects expected fitness values in tests
4. **population_size minimum is 2** — EvolutionConfig.__post_init__ validates this
5. **Import sorting matters** — ruff I001 catches unsorted TYPE_CHECKING blocks

## Files Modified (M3)

- `ktrdr/evolution/harness.py` — Additional backtests + evaluate_slices call
- `ktrdr/evolution/fitness.py` — Complete rewrite with gates + multi-slice scoring
- `ktrdr/evolution/report.py` — Monoculture detection + trait convergence + lineage tracing
- `ktrdr/cli/commands/evolve.py` — Report command
- `tests/unit/evolution/test_harness.py` — Updated fixtures + 7 additional backtest tests
- `tests/unit/evolution/test_fitness.py` — Complete rewrite with 26 tests
- `tests/unit/evolution/test_report.py` — 12 tests (diversity, convergence, lineage)
- `tests/unit/cli/test_evolve.py` — 7 report command tests
