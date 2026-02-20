---
design: docs/designs/primordial-soup/DESIGN.md
architecture: docs/designs/primordial-soup/ARCHITECTURE.md
---

# Milestone 1: Single Generation End-to-End

**Goal:** Run one generation of researchers through the existing pipeline and score them — proving the external harness architecture works.

**Capability:** User can run `ktrdr evolve start --population 3 --generations 1` and see fitness scores for each researcher.

---

## Task 1.1: Core Data Models

**File(s):** `ktrdr/evolution/__init__.py`, `ktrdr/evolution/genome.py`, `ktrdr/evolution/config.py`
**Type:** CODING

**Description:**
Create the foundational data models for the evolution module. Three things: the genome (3 traits × 3 levels), the researcher (genome + identity + lineage), and the run configuration (population size, date windows, fitness parameters).

TraitLevel is an ordered enum (OFF < LOW < HIGH) so mutation can shift ±1. Genome supports mutation (pick 1 random trait, shift ±1 with clamping), serialization (to/from dict for YAML), and enumeration (all 27 combinations). Researcher carries genome, generation number, and parent lineage.

EvolutionConfig holds all run parameters with sensible defaults matching DESIGN.md. DateRange is a simple start/end date pair used for training window and fitness slices.

**Implementation Notes:**
- Use dataclasses, not Pydantic (this is internal data, not API schemas)
- TraitLevel ordering matters for mutation: OFF can only go to LOW, HIGH can only go to LOW
- Genome.mutate() returns a NEW genome (immutable pattern)
- Researcher.id format: `r_g{generation:02d}_{index:03d}`

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_genome.py`, `tests/unit/evolution/test_config.py`
- Genome: all 27 combinations enumerated correctly
- Genome: mutation shifts exactly 1 trait by ±1 level
- Genome: mutation respects clamping (OFF can't go below OFF, HIGH can't go above HIGH)
- Genome: mutation coverage — run 1000 mutations, verify all traits get mutated
- Genome: to_dict/from_dict roundtrip for all 27 genomes
- Researcher: ID format is correct
- EvolutionConfig: defaults match DESIGN.md values
- EvolutionConfig: validation rejects population_size < 2, generations < 1, empty fitness_slices

**Acceptance Criteria:**
- [ ] TraitLevel enum with OFF, LOW, HIGH
- [ ] Genome with mutate(), to_dict(), from_dict(), all_combinations()
- [ ] Researcher with id, genome, generation, parent_id, mutation fields
- [ ] EvolutionConfig with all parameters from ARCHITECTURE.md
- [ ] All unit tests passing

---

## Task 1.2: Brief Translator

**File(s):** `ktrdr/evolution/brief.py`
**Type:** CODING

**Description:**
Convert a genome into a design brief string that the research pipeline injects into the LLM's design prompt. This is the genome-to-phenotype mechanism — the only way traits influence researcher behavior.

Each trait maps to specific instructions:
- **novelty_seeking**: controls how different from recent strategies the LLM should aim (systematic → exploratory → creative)
- **skepticism**: controls conservatism in strategy design (accept results → basic checks → extremely conservative)
- **memory_depth**: controls how the LLM uses experiment history (ignore → recent 2-3 → synthesize all)

The brief also appends date windows (training + first backtest slice) and symbol/timeframe from EvolutionConfig.

**Implementation Notes:**
- See ARCHITECTURE.md "Brief Translation Examples" for the three reference briefs
- Each trait level produces a distinct paragraph of 1-3 sentences
- The combined brief should be 100-200 words total (enough to frame behavior, not so long it drowns the design prompt)
- Date window section is always the same format: "Training window: X to Y. Backtest window: A to B. Symbol: S, Timeframe: T."

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_brief.py`
- All 27 genomes produce non-empty briefs
- All 27 briefs are unique (no two genomes produce identical briefs)
- Brief contains training window dates from config
- Brief contains backtest window dates (first fitness slice) from config
- Brief contains symbol and timeframe
- novelty=off brief contains "systematic" or "proven patterns"
- novelty=high brief contains "creative" or "experimental" or "unusual"
- skepticism=high brief contains "conservative" or "maximum 2 indicators"
- memory=off brief contains "ignore" or "fresh"
- memory=high brief contains "synthesize" or "all experiment history"

**Acceptance Criteria:**
- [ ] BriefTranslator.translate(genome, config) → str
- [ ] Briefs meaningfully differ based on trait values
- [ ] Date windows and symbol/timeframe always included
- [ ] All unit tests passing

---

## Task 1.3: Population Manager (Seeding)

**File(s):** `ktrdr/evolution/population.py`
**Type:** CODING

**Description:**
Create initial populations that cover the genome space well. For population_size=12 and 27 possible genomes, we can't cover everything. The seeding strategy should maximize diversity.

Approach: select 12 genomes that are maximally spread across the 27-genome space. One option is systematic sampling — pick the 12 most "distant" genomes (e.g., all corners of the 3D trait space plus some interior points). A simpler option that works well: random sample of 12 from all 27, ensuring no duplicates.

For v0: random sample without replacement from all_combinations(). This is simple, gives good coverage (~44% of space), and every run gets a different starting population — which is itself an interesting variable.

**Implementation Notes:**
- seed() takes EvolutionConfig, returns list[Researcher]
- Researchers get generation=0, parent_id=None, mutation=None
- IDs: r_g00_000 through r_g00_011
- Use a seeded random generator (from config or run ID) for reproducibility

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_population.py`
- seed() returns exactly population_size researchers
- All researchers have generation=0
- All researcher IDs are unique
- No duplicate genomes (when population_size ≤ 27)
- Seeded random produces same population for same seed

**Acceptance Criteria:**
- [ ] PopulationManager.seed(config) → list[Researcher]
- [ ] Population size matches config
- [ ] Good genome diversity in seeded population
- [ ] Reproducible with seed
- [ ] All unit tests passing

---

## Task 1.4: Evolution Tracker

**File(s):** `ktrdr/evolution/tracker.py`
**Type:** CODING
**Task Categories:** Persistence

**Description:**
Persist all evolution state as YAML files. The tracker manages the directory structure under `data/evolution/run_<id>/` and provides save/load methods for each state type.

Critical crash-safety requirement: operation IDs must be persisted immediately after trigger (before polling begins). This enables resume — if the harness crashes mid-generation, it can reload which operations were triggered and check their status.

**Implementation Notes:**
- Run ID format: `run_YYYYMMDD_HHMMSS`
- Use PyYAML for serialization (already a project dependency)
- Directory structure per ARCHITECTURE.md state management section
- save_operation_id() must be called after EACH trigger, not batched
- load methods should handle missing files gracefully (return empty lists/None for resume scenarios)
- get_last_completed_generation() checks which generation directories have results.yaml

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_tracker.py`
- save_config / load_config roundtrip
- save_population / load_population roundtrip
- save_results / load_results roundtrip
- save_operation_id persists incrementally (save one, save another, load shows both)
- get_last_completed_generation returns None for empty run
- get_last_completed_generation returns correct gen after saving results
- Directory structure created correctly
- Missing file handling (load from nonexistent path returns empty/None)

*Smoke Test:*
```bash
ls data/evolution/run_*/generation_*/population.yaml
```

**Acceptance Criteria:**
- [ ] All save/load methods work with YAML roundtrip
- [ ] Operation IDs persisted incrementally (not batched)
- [ ] Missing files handled gracefully
- [ ] Directory auto-creation
- [ ] All unit tests passing

---

## Task 1.5: Fitness Evaluator (Basic)

**File(s):** `ktrdr/evolution/fitness.py`
**Type:** CODING

**Description:**
Score researchers based on backtest results. For M1, this is single-slice only (from the research pipeline's standard backtest). The full multi-slice scoring with gates comes in M3.

M1 fitness: `fitness = sharpe - lambda_dd * max_drawdown`. Simple, but enough to differentiate researchers and prove the scoring pipeline works.

Researchers with no backtest results (failed research, gate rejection) get minimum fitness (-999.0).

**Implementation Notes:**
- Extract Sharpe ratio and max drawdown from the backtest result dict
- The backtest result format comes from operation metadata (`parameters["backtest_result"]`) — check what fields are available
- Handle missing/malformed results gracefully (minimum fitness, not exceptions)
- FitnessEvaluator takes EvolutionConfig for lambda values

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_fitness.py`
- Positive Sharpe, low drawdown → positive fitness
- Negative Sharpe → negative fitness
- High drawdown penalized via lambda_dd
- Missing backtest results → minimum fitness (-999.0)
- Malformed results (missing keys) → minimum fitness
- Lambda parameters from config affect scoring

**Acceptance Criteria:**
- [ ] FitnessEvaluator.evaluate(backtest_result) → float
- [ ] Handles missing/malformed results without exceptions
- [ ] Lambda parameters configurable
- [ ] All unit tests passing

---

## Task 1.6: Generation Harness

**File(s):** `ktrdr/evolution/harness.py`
**Type:** CODING
**Task Categories:** Cross-Component, Background/Async

**Description:**
The orchestrator. Drives one generation: translate genomes to briefs, trigger research cycles via HTTP, poll for completion, extract results, score fitness. This is the core integration piece connecting all components.

Uses httpx for HTTP communication (consistent with WorkerAPIBase pattern). Runs as an async loop — triggers researchers (respecting capacity), polls operations, collects results when complete.

**Implementation Notes:**
- Use httpx.AsyncClient for HTTP calls
- Trigger pattern: POST /api/v1/agent/trigger with {model, brief}. On "at_capacity" response, back off and retry (exponential, cap at 5 min). On "budget_exhausted", abort.
- Poll pattern: GET /api/v1/operations/{id}, check status field. Poll every config.poll_interval seconds.
- Extract from completed operation: metadata.parameters["model_path"], metadata.parameters["backtest_result"], metadata.parameters["strategy_name"]
- Persist operation ID to tracker IMMEDIATELY after successful trigger (before polling)
- For M1: run_generation() only (no multi-gen loop, no selection/reproduction — those are M2)
- Failed operations (status=FAILED) get minimum fitness, not retried

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_harness.py`
- Trigger: successful trigger returns operation_id, persisted to tracker
- Trigger: at_capacity response triggers retry with backoff
- Trigger: budget_exhausted response aborts generation
- Poll: completed operation extracts backtest_result correctly
- Poll: failed operation returns None result
- Full run_generation: mocked HTTP, 3 researchers, all complete, results scored
- Full run_generation: 1 researcher fails, others succeed, failed gets minimum fitness

**Acceptance Criteria:**
- [ ] GenerationHarness.run_generation(population) triggers, polls, collects, scores
- [ ] Operation IDs persisted immediately after trigger
- [ ] Capacity backoff works (retries on at_capacity)
- [ ] Budget exhaustion aborts cleanly
- [ ] Failed operations handled (minimum fitness, no crash)
- [ ] All unit tests passing

---

## Task 1.7: CLI Command

**File(s):** `ktrdr/cli/evolve.py`
**Type:** CODING
**Task Categories:** API Endpoint (CLI)

**Description:**
Add `ktrdr evolve start` CLI command that initializes and runs an evolution experiment. For M1, only `--generations 1` is meaningful (multi-gen loop comes in M2), but accept the parameter for forward compatibility.

Register the evolve command group on cli_app (from _commands_base.py) following the existing command registration pattern.

**Implementation Notes:**
- Follow existing CLI patterns: lazy imports inside command functions, use Typer app group
- Register on cli_app from ktrdr/cli/_commands_base.py (current entry point)
- Parameters: --population (default 12), --generations (default 5), --symbol (default EURUSD), --timeframe (default 1h), --model (default haiku)
- Date windows: use defaults from EvolutionConfig (configurable via a YAML config file is nice-to-have but not required for M1)
- Output: print generation progress (researcher triggered, completed, fitness scores) using Rich tables
- The command runs synchronously from the user's perspective (blocks until generation complete)

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_evolve.py`
- Use `runner` fixture (CleanCliRunner) from conftest.py
- Command registered and help text shows
- Start command with mocked harness — verify harness.run_generation() called
- Invalid parameters rejected (population < 2, generations < 1)

**Acceptance Criteria:**
- [ ] `ktrdr evolve start` command works
- [ ] Parameters accepted with defaults
- [ ] Progress output during run
- [ ] Registered on cli_app
- [ ] All unit tests passing (using runner fixture)

---

## Task 1.8: E2E Validation

**Type:** VALIDATION

**Description:**
Validate M1 works end-to-end: run 1 generation with 3 researchers in local-prod, verify results are collected, scored, and state is persisted.

**Prerequisites:**
- Local-prod running with backend + workers
- Anthropic API key configured
- EURUSD 1h data available

**Validation Requirements:**
1. `ktrdr evolve start --population 3 --generations 1` completes without error
2. At least 1 researcher produces a backtest result with fitness score
3. State files exist: config.yaml, generation_00/population.yaml, generation_00/results.yaml
4. Results contain fitness scores for all 3 researchers (even if some failed)

**Acceptance Criteria:**
- [ ] E2E test passes via e2e-tester agent
- [ ] No regressions in existing `make test-unit` or `make quality`

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] E2E test passes (Task 1.8)
- [ ] State files readable and contain expected structure
