# Handoff: Primordial Soup M3 — Full Fitness + Reporting

## Status

| Task | Status | Notes |
|------|--------|-------|
| 3.1 Additional Backtests | Done | harness.py: _run_additional_backtests, retry once |
| 3.2 Full Fitness Function | Done | Gates + multi-slice scoring + complexity |
| 3.3 Monoculture Detection | Done | report.py: diversity + trait convergence |
| 3.4 CLI Report Command | Done | evolve report: trend, genome, lineage, diversity |
| 3.5 E2E Validation | Done | Partial — pipeline validated, researchers gate-failed on real data |
| model_path bug fix | Done | research_worker persists model_path in result_summary; harness reads it |

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
- Skipped for researchers that failed research (no backtest_result)
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

### model_path Persistence (research_worker.py + harness.py)
- Research worker now includes `model_path` in `completion_result` passed to `complete_operation()`
- The training phase sets `model_path` in `parent_op.metadata.parameters` (line 597)
- The completion handler reads it back and includes in `result_summary` (persisted to DB)
- Harness `_extract_metadata` checks both `metadata.parameters` and `result_summary` for model_path
- BacktestEngine requires model_path (no auto-discovery) — this was the root cause of additional backtest failures

## Gotchas

1. **Test fixtures need `total_trades: 50`** in mock backtest results — otherwise the min-trades gate (30) fails
2. **Existing tests use `_SINGLE_SLICE` config** to avoid triggering additional backtests
3. **Complexity penalty of 0.05** (default 0.5 * λ_complexity 0.1) affects expected fitness values in tests
4. **population_size minimum is 2** — EvolutionConfig.__post_init__ validates this
5. **Import sorting matters** — ruff I001 catches unsorted TYPE_CHECKING blocks
6. **strategy_name and model_path are in result_summary, NOT metadata.parameters** — the API persists initial trigger metadata only; the research worker's in-memory updates to metadata.parameters are not persisted. `_extract_metadata` checks both locations.
7. **BacktestEngine requires model_path** — despite BacktestStartRequest having it as Optional, the engine raises ValueError if None. There is NO auto-discovery in the backtest pipeline (DecisionOrchestrator's auto-discovery is for paper/live trading only).
8. **Sandbox needs .env.sandbox** — the CLI uses this file to detect sandbox port; if missing, it defaults to prod (port 8000). Copy from `~/.ktrdr/sandboxes/slot-N/.env.sandbox` if lost.
9. **Sandbox needs `kinfra sandbox up` (not direct docker compose)** — to inject 1Password secrets (ANTHROPIC_API_KEY etc.)
10. **Fresh DB needs `alembic upgrade head`** — run inside the backend container after first sandbox start
11. **Budget estimator overestimates ~3x** — local estimate shows $8.05 but Anthropic billing shows $2.62. Pre-existing issue.
12. **Test mock `_make_completed_operation` mirrors real API** — model_path and strategy_name in result_summary, NOT metadata.parameters. The previous mock structure was incorrect.

## Files Modified (M3)

- `ktrdr/evolution/harness.py` — Additional backtests + evaluate_slices call + model_path from result_summary
- `ktrdr/evolution/fitness.py` — Complete rewrite with gates + multi-slice scoring
- `ktrdr/evolution/report.py` — Monoculture detection + trait convergence + lineage tracing
- `ktrdr/cli/commands/evolve.py` — Report command
- `ktrdr/agents/workers/research_worker.py` — Include model_path in completion result_summary
- `tests/unit/evolution/test_harness.py` — Updated fixtures + 7 additional backtest tests + 5 extract_metadata tests
- `tests/unit/evolution/test_fitness.py` — Complete rewrite with 26 tests
- `tests/unit/evolution/test_report.py` — 12 tests (diversity, convergence, lineage)
- `tests/unit/cli/test_evolve.py` — 7 report command tests
- `tests/unit/agents/test_research_worker_multi.py` — 1 test: completion result includes model_path
- `tests/unit/agent_tests/test_budget.py` — Budget test updated for $20 default
- `ktrdr/config/settings.py` — Daily budget default bumped from $5 to $20
- `tests/unit/config/test_agent_settings.py` — Budget test updated

## E2E Validation Results

**Run:** `ktrdr evolve start --population 2 --generations 2 --seed 42` against sandbox (slot 1, port 8001)

| Feature | Validated | Notes |
|---------|-----------|-------|
| Research trigger | Yes | Both researchers triggered via agent/trigger API |
| Research polling | Yes | 30s poll interval, detected completed/failed states |
| Additional backtests triggered | Yes | POST /api/v1/backtests/start fired after research |
| Backtest retry on failure | Yes | First attempt failed, retry attempted |
| Worker contention handled | Yes | 503 "no workers available" handled gracefully |
| Gate checks (max_drawdown) | Yes | 0.494 > 0.35 → MINIMUM_FITNESS correctly |
| Selection pressure | Yes (prev run) | 1 survived, 1 died in gen 0 |
| Report command | Yes | All sections rendered with real data |
| Graceful degradation | Yes | Proceeded with 1 slice when additional backtests failed |

**Additional backtests failed** because model_path was not persisted in result_summary — **fixed** by including model_path in research worker's completion result. The fix requires rebuilding sandbox containers to take effect (backend code change).

**Not fully validated** (would need more runs with better-performing strategies + rebuilt containers):
- Multi-slice fitness with 3 successful slices (model_path fix needs container rebuild)
- Lineage tracing with real ancestry (all failed → no lineage to show)
- Monoculture warning with real convergence (too few generations)
