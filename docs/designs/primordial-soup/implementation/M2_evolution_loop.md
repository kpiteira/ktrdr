---
design: docs/designs/primordial-soup/DESIGN.md
architecture: docs/designs/primordial-soup/ARCHITECTURE.md
---

# Milestone 2: Evolution Loop

**Goal:** Add selection pressure and multi-generation dynamics — the core evolutionary mechanism.

**Builds on:** M1 (single generation runs and scores)

**Capability:** User can run `ktrdr evolve start --population 6 --generations 3` and observe populations evolving across generations. User can resume crashed runs and check status.

---

## Task 2.1: Selection

**File(s):** `ktrdr/evolution/population.py`
**Type:** CODING

**Description:**
Add selection to PopulationManager: sort researchers by fitness, kill the bottom 50%. This is the core selection pressure that drives evolution.

Simple rank-based selection: sort all researchers by fitness descending, keep the top half, discard the bottom half. Tie-breaking: if two researchers have identical fitness, the one with lower ID survives (deterministic, arbitrary, doesn't matter for v0).

**Implementation Notes:**
- select() takes list[ResearcherResult] (researcher_id + fitness), returns (survivor_ids, dead_ids)
- kill_rate from EvolutionConfig (default 0.5)
- With population=12 and kill_rate=0.5: keep top 6, kill bottom 6
- Researchers with minimum fitness (-999.0) always die (failed experiments)

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_population.py` (extend from M1)
- 12 researchers sorted correctly, top 6 survive
- Tie-breaking is deterministic
- All minimum-fitness researchers die
- Edge: all same fitness → deterministic split by ID
- Edge: only 1 researcher above minimum → 1 survives
- kill_rate configurable (0.3 keeps top 70%)

**Acceptance Criteria:**
- [ ] PopulationManager.select(results) → (survivor_ids, dead_ids)
- [ ] Bottom 50% killed by fitness rank
- [ ] Deterministic tie-breaking
- [ ] All unit tests passing

---

## Task 2.2: Reproduction

**File(s):** `ktrdr/evolution/population.py`
**Type:** CODING

**Description:**
Add reproduction: each survivor produces 2 offspring with 1 mutated trait each. This maintains population size and introduces variation.

Each offspring is a copy of its parent with exactly 1 trait mutated by ±1 level (using Genome.mutate()). The offspring gets a new researcher ID, the parent's ID as parent_id, and a description of the mutation.

**Implementation Notes:**
- reproduce() takes list of surviving Researchers + next generation number, returns new population
- Each survivor → 2 offspring. With 6 survivors × 2 = 12 offspring = stable population.
- Offspring IDs: r_g{gen:02d}_{index:03d}
- Mutation description: "novelty_seeking: off→low"
- Use seeded random for reproducibility (generation number as part of seed)

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_population.py` (extend)
- 6 survivors → 12 offspring
- Each offspring has parent_id set to its parent
- Each offspring has exactly 1 trait different from parent
- Mutation description is accurate
- Population size stable: 12 → 6 survive → 12 offspring → 12
- Offspring generation number is parent.generation + 1
- Reproducible with same seed

**Acceptance Criteria:**
- [ ] PopulationManager.reproduce(survivors, generation) → list[Researcher]
- [ ] Correct offspring count (maintains population)
- [ ] Each offspring has exactly 1 mutation from parent
- [ ] Lineage tracked (parent_id, mutation description)
- [ ] All unit tests passing

---

## Task 2.3: Multi-Generation Loop

**File(s):** `ktrdr/evolution/harness.py`
**Type:** CODING
**Task Categories:** Background/Async

**Description:**
Extend GenerationHarness with a run() method that executes multiple generations: seed → run_generation → select → reproduce → save → repeat.

The loop runs for config.generations iterations. After each generation, it saves results, performs selection, reproduces, and starts the next generation with the new population.

**Implementation Notes:**
- run() calls seed() for generation 0, then loops: run_generation → select → reproduce → save_results → update_summary
- Between generations: log generation stats (mean fitness, diversity, survivors)
- Budget tracking: after each generation, check if remaining budget is sufficient for another generation. Abort early if not.
- The summary.yaml is updated after each generation (incremental, not just at the end)

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_harness.py` (extend from M1)
- 3 generations with mocked HTTP: verify generation count correct
- Population flows between generations (gen 0 survivors → gen 1 population)
- Summary updated after each generation
- Budget check between generations (abort if insufficient)
- Correct generation numbers in researcher IDs

**Acceptance Criteria:**
- [ ] GenerationHarness.run() executes multi-generation loop
- [ ] Population evolves between generations (selection + reproduction)
- [ ] State saved after each generation
- [ ] Summary updated incrementally
- [ ] All unit tests passing

---

## Task 2.4: Resume Capability

**File(s):** `ktrdr/evolution/harness.py`, `ktrdr/evolution/tracker.py`
**Type:** CODING
**Task Categories:** Persistence

**Description:**
Enable resuming a crashed or stopped evolution run from the last completed generation.

On resume: load config, find the last generation with saved results, check if any operations from an incomplete generation are still in-flight, and continue from there.

**Implementation Notes:**
- resume(run_id) loads the run directory, calls tracker.get_last_completed_generation()
- If a generation has operations.yaml but no results.yaml → incomplete generation. Check each operation's status via API:
  - COMPLETED: read results
  - RUNNING: resume polling
  - FAILED or missing: re-trigger with same genome brief
  - Stuck >stale_operation_timeout: treat as failed, re-trigger
- After collecting all results for the incomplete generation, continue with select → reproduce → next gen
- If all generations complete, just report "run already complete"

**Testing Requirements:**

*Unit Tests:* `tests/unit/evolution/test_harness.py` (extend)
- Resume after gen 2 of 5: continues from gen 3
- Resume with incomplete generation: picks up in-flight ops
- Resume with orphaned ops (stuck): re-triggers
- Resume with all generations complete: reports done
- Resume with partially triggered generation: triggers remaining researchers

**Acceptance Criteria:**
- [ ] resume(run_id) continues from last completed generation
- [ ] In-flight operations detected and polled
- [ ] Orphaned operations re-triggered
- [ ] Already-complete runs handled gracefully
- [ ] All unit tests passing

---

## Task 2.5: CLI Status Command

**File(s):** `ktrdr/cli/evolve.py`
**Type:** CODING
**Task Categories:** API Endpoint (CLI)

**Description:**
Add `ktrdr evolve status` to show current evolution run status and `ktrdr evolve resume` to continue a stopped run.

Status reads the run directory and shows: current generation, researchers triggered/completed/failed, fitness stats for completed generations, overall progress.

**Implementation Notes:**
- `ktrdr evolve status [run_id]` — if no run_id, find the most recent run in data/evolution/
- `ktrdr evolve resume <run_id>` — calls harness.resume()
- Use Rich tables for output (follow existing CLI patterns)
- Show per-generation: mean fitness, max fitness, diversity, population size

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_evolve.py` (extend from M1)
- Status with no runs → "No evolution runs found"
- Status with completed run → shows generation stats
- Status with in-progress run → shows current generation
- Resume command calls harness.resume()
- Use runner fixture (CleanCliRunner)

**Acceptance Criteria:**
- [ ] `ktrdr evolve status` shows run progress
- [ ] `ktrdr evolve resume` continues stopped runs
- [ ] Rich table output
- [ ] All unit tests passing

---

## Task 2.6: E2E Validation

**Type:** VALIDATION

**Description:**
Validate M2 works end-to-end: run 3 generations with 6 researchers, verify selection happens and population evolves.

**Prerequisites:**
- Local-prod running with backend + workers
- Anthropic API key configured

**Validation Requirements:**
1. `ktrdr evolve start --population 6 --generations 3` completes
2. Three generation directories exist with population.yaml and results.yaml
3. Generation 1 population is different from generation 0 (selection + mutation happened)
4. Summary.yaml has stats for all 3 generations
5. `ktrdr evolve status` shows the completed run

**Acceptance Criteria:**
- [ ] E2E test passes via e2e-tester agent
- [ ] Selection visibly happens (some researchers die each generation)
- [ ] Mutation visibly happens (offspring genomes differ from parent genomes)
- [ ] No regressions in `make test-unit` or `make quality`

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] E2E test passes (Task 2.6)
- [ ] M1 E2E still passes
