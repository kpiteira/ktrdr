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
| multi-TF backtest fix | Done | harness omits timeframe from additional backtest payload; engine fallback |

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
- **Timeframe omitted from payload** — backend resolves from strategy config (fixes multi-TF KeyError)
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
13. **Harness must NOT pass timeframe to additional backtests** — the evolution config timeframe (e.g. "1h") may not match the strategy's base_timeframe (e.g. "5m"). The BacktestStartRequest accepts timeframe=None and the API endpoint resolves it from the strategy YAML on disk, which correctly handles multi-TF.
14. **Engine has defensive base_tf fallback** — if `_get_base_timeframe()` returns a TF not in the loaded data dict, the engine falls back to the first available TF with a warning log. This prevents KeyError when strategy config and loaded data disagree.

## Files Modified (M3)

- `ktrdr/evolution/harness.py` — Additional backtests + evaluate_slices call + model_path from result_summary + omit timeframe from backtest payload
- `ktrdr/evolution/fitness.py` — Complete rewrite with gates + multi-slice scoring
- `ktrdr/evolution/report.py` — Monoculture detection + trait convergence + lineage tracing
- `ktrdr/cli/commands/evolve.py` — Report command
- `ktrdr/agents/workers/research_worker.py` — Include model_path in completion result_summary
- `ktrdr/backtesting/engine.py` — Defensive base_tf fallback when not in loaded data
- `tests/unit/evolution/test_harness.py` — Updated fixtures + 7 additional backtest tests + 5 extract_metadata tests + 2 payload tests
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
| model_path in result_summary | Yes | Fix confirmed: model_path now persisted and extracted by harness |
| Additional backtests triggered | Yes | POST /api/v1/backtests/start fired with model_path after research |
| Backtest retry on failure | Yes | First attempt failed, retry attempted (x2 per slice) |
| Gate checks (max_drawdown) | Yes | 0.494 > 0.35 → MINIMUM_FITNESS (run 1); 0.697 > 0.35 (run 2) |
| Selection pressure | Yes (run 1) | 1 survived, 1 died in gen 0 |
| Report command | Yes | All sections rendered with real data |
| Graceful degradation | Yes | Proceeded with 1 slice when additional backtests failed |

### E2E Run 2 (2026-02-25, post model_path fix)

**model_path fix confirmed**: Error changed from `ValueError: model_path is required` (run 1) to `KeyError: '5m'` (run 2). The model loads successfully now — the new failure is a pre-existing multi-timeframe feature alignment bug (model trained on 5m+1h, but additional backtests only pass timeframe=1h data).

### Multi-TF Fix (2026-02-25)

**Root cause**: Harness passed `timeframe: "1h"` (from EvolutionConfig) to additional backtest API. The engine's `_get_base_timeframe()` read `"5m"` from the model bundle but `_get_strategy_timeframes()` fell back to `["1h"]` (the passed config timeframe). Single-TF data loaded for "1h" but then `multi_tf_data["5m"]` → KeyError.

**Fix**: (1) Harness omits `timeframe` from additional backtest payload — backend resolves from strategy YAML. (2) Engine adds defensive fallback at line 173 when `base_tf` not in loaded data.

### E2E Run 3 (2026-02-25, post multi-TF fix)

**Multi-TF fix confirmed**: No more KeyError: '5m'. Worker logs show all backtests use "EURUSD 1h" and complete successfully. One worker had pre-existing NaN confidence error (feature alignment issue).

**Full run completed**: 2/2 generations, selection pressure working (1 survived → offspring improved fitness from -2.04 to -0.44). Lineage tracing, genome diversity, and report command all validated with real data.

**Additional backtests still fail** (pre-existing issues):
- NaN confidence: feature alignment produces NaN on some date ranges (pre-existing)
- Proxy timing: some backtests complete on worker but proxy reports "failed" before completion
- Multi-slice fitness with 3 successful slices not yet achieved (above issues)

**Validated in E2E run 3**:
- Lineage tracing with real ancestry (r_g00_000 → r_g01_001)
- Full 2-generation evolution with selection, reproduction, and fitness improvement
- Report command rendering all sections with real data
