---
design: docs/designs/primordial-soup/DESIGN.md
architecture: docs/designs/primordial-soup/ARCHITECTURE.md
---

# Milestone 3: Full Fitness + Reporting

**Goal:** Add robust multi-slice fitness evaluation and evolution analysis reporting — making the experiment results meaningful and interpretable.

**Builds on:** M2 (multi-generation evolution loop)

**Capability:** User can run a full 5-generation, 12-researcher evolution experiment with three-slice fitness evaluation and get an analysis report showing fitness trends, genome distribution, lineage, and monoculture warnings.

---

## Task 3.1: Additional Backtests

**File(s):** `ktrdr/evolution/harness.py`
**Type:** CODING
**Task Categories:** Cross-Component

**Description:**
After each research cycle completes, run 2 additional backtests on the trained model using different time slices. This gives 3 backtest results per researcher for robust fitness evaluation.

The first slice result comes from the standard research pipeline backtest (already collected in M1). Slices 2 and 3 are triggered by the harness via the backtest API.

**Implementation Notes:**
- After extracting model_path from the completed research operation, call POST /api/v1/backtests/start with:
  - The same model_path and strategy_name
  - Different start_date and end_date (from config.fitness_slices[1] and [2])
- Poll backtest operations the same way as research operations
- Backtest API request format: check the existing BacktestStartRequest schema for required fields
- If an additional backtest fails, retry once. If still fails, score using available slices only (2 or even 1 is better than discarding the researcher entirely)
- Researchers that failed the research pipeline (no model_path) skip additional backtests

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_harness.py` (extend)
- Additional backtests triggered with correct date ranges
- Model path from research operation used correctly
- Failed additional backtest: retry once, then proceed with available slices
- Skipped for researchers with no model_path
- All 3 slice results collected and passed to fitness evaluator

**Acceptance Criteria:**
- [ ] 2 additional backtests per completed researcher
- [ ] Correct date ranges from config.fitness_slices
- [ ] Retry on failure, graceful degradation to fewer slices
- [ ] Skipped for failed researchers
- [ ] All unit tests passing

---

## Task 3.2: Full Fitness Function

**File(s):** `ktrdr/evolution/fitness.py`
**Type:** CODING

**Description:**
Replace the M1 basic fitness with the full multi-layer evaluation from DESIGN.md:

**Layer A — Gates (instant death):**
- Minimum trades per slice (default 30)
- Maximum drawdown per slice (default 35%)
- Action diversity (not >90% same direction)

**Layer B — Performance score:**
```
fitness = mean(Sharpe_i) - λ_dd * mean(MaxDD_i) - λ_var * std(Sharpe_i) - λ_cmp * complexity
```

Complexity = indicator_count/10 + nn_param_bucket (0.1 to 1.0 based on parameter count ranges).

**Implementation Notes:**
- Gate checks applied per-slice: if ANY slice fails ANY gate, researcher gets minimum fitness
- Action diversity: extract long/short trade counts from backtest result, check ratio
- Complexity: extract from strategy config (indicator count) and model metadata (parameter count). If not available, use default (0.5)
- nn_param_bucket mapping: <100→0.1, <500→0.3, <2000→0.5, <10000→0.7, ≥10000→1.0
- Handle 1 or 2 slices gracefully (if additional backtests failed): compute with available slices, std of 1 value = 0

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_fitness.py` (extend from M1)
- Gate: min trades — 29 trades fails, 30 passes
- Gate: max drawdown — 0.36 fails, 0.34 passes
- Gate: action diversity — 95% long fails, 80% long passes
- Gate failure on any slice → minimum fitness
- Multi-slice scoring: 3 slices with known Sharpe/DD → verify exact fitness value
- Cross-slice variance penalty: identical Sharpes → 0 penalty, divergent Sharpes → large penalty
- Complexity penalty: 2 indicators + small network → low penalty, 8 indicators + large network → high penalty
- 1 slice available: variance penalty = 0, mean = single value
- 2 slices available: variance computed from 2 values
- All lambdas configurable via EvolutionConfig

**Acceptance Criteria:**
- [ ] Gate checks with instant death for failures
- [ ] Multi-slice Sharpe scoring with variance penalty
- [ ] Complexity penalty
- [ ] Graceful handling of 1 or 2 slices
- [ ] All lambdas configurable
- [ ] All unit tests passing

---

## Task 3.3: Monoculture Detection

**File(s):** `ktrdr/evolution/report.py`
**Type:** CODING

**Description:**
Detect and warn when the population converges to too few distinct genomes. This is the monoculture problem — if selection is too aggressive or mutation too weak, all researchers end up with the same genome and evolution stalls.

**Implementation Notes:**
- genome_diversity = len(unique_genomes) / population_size (0.0 to 1.0)
- Compute per generation as part of summary stats
- Warning threshold: diversity < 0.3 (fewer than 4 unique genomes in a population of 12)
- Also track per-trait convergence: for each trait, what's the dominant value and what fraction has it?
- This feeds into the report (Task 3.4), not a runtime action

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_report.py`
- All unique genomes → diversity = 1.0
- All same genome → diversity = 1/12 ≈ 0.083
- Diversity below threshold → warning flag set
- Per-trait convergence: 10/12 have novelty=high → 83% convergence on novelty

**Acceptance Criteria:**
- [ ] genome_diversity computed per generation
- [ ] Monoculture warning when diversity < threshold
- [ ] Per-trait convergence tracking
- [ ] All unit tests passing

---

## Task 3.4: CLI Report Command

**File(s):** `ktrdr/cli/evolve.py`, `ktrdr/evolution/report.py`
**Type:** CODING
**Task Categories:** API Endpoint (CLI)

**Description:**
Add `ktrdr evolve report [run_id]` that renders the evolution experiment results in a readable format.

The report should answer the experiment's core questions:
1. Did fitness improve across generations?
2. Did trait patterns emerge in survivors?
3. Did the population converge or stay diverse?
4. Were there any surprises?

**Report sections:**
- **Run summary:** population size, generations, symbol, total experiments
- **Fitness trend:** per-generation mean/max/min fitness (table)
- **Genome distribution:** which genomes survived in each generation, trait frequency in survivors
- **Lineage:** top performer's ancestry (genome → mutations → final genome)
- **Monoculture warnings:** if diversity dropped below threshold
- **Cost:** total LLM spend, total experiments, experiments per generation

**Implementation Notes:**
- Use Rich tables and panels for output (follow existing CLI patterns)
- Read from summary.yaml + per-generation results.yaml
- Lineage tracking: follow parent_id chain from best researcher back to gen 0
- If no run_id provided, use most recent run

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_evolve.py` (extend), `tests/unit/evolution/test_report.py` (extend)
- Report with sample data renders all sections
- Fitness trend table has correct values
- Lineage traces back to gen 0
- Monoculture warning appears when diversity is low
- Use runner fixture (CleanCliRunner)

**Acceptance Criteria:**
- [ ] `ktrdr evolve report` renders readable analysis
- [ ] Fitness trends, genome distribution, lineage, monoculture warnings all present
- [ ] Works with partial data (run stopped early)
- [ ] All unit tests passing

---

## Task 3.5: E2E Validation

**Type:** VALIDATION

**Description:**
Validate M3 with a full evolution run: 5 generations, 12 researchers, multi-slice fitness.

This is the real experiment (or a shorter version of it). It validates that the entire system works end-to-end: genome diversity, selection pressure, multi-slice scoring, and reporting.

**Prerequisites:**
- Local-prod running with backend + workers
- Anthropic API key configured
- EURUSD 1h data available for all configured date ranges
- Budget: ~$5-10 for a full run with haiku

**Validation Requirements:**
1. `ktrdr evolve start --population 12 --generations 5` completes (or run overnight)
2. Each generation has 3-slice fitness evaluation
3. Selection has teeth: some researchers die each generation
4. Fitness trend is non-random (improvement or at least non-declining mean)
5. `ktrdr evolve report` produces readable output with all sections
6. Monoculture detection works if convergence occurs

**Acceptance Criteria:**
- [ ] E2E test passes via e2e-tester agent
- [ ] Multi-slice backtests executed (3 results per researcher)
- [ ] Report contains meaningful data (not empty/default values)
- [ ] No regressions in `make test-unit` or `make quality`
- [ ] M1 and M2 E2E tests still pass

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] E2E test passes (Task 3.5)
- [ ] M1 and M2 E2E tests still pass
- [ ] Report is readable and answers the experiment's core questions
