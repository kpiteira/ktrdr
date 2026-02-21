# Test: evolution/single-generation

**Purpose:** Validate the primordial soup M1 end-to-end: CLI triggers evolution, 3 researchers run through the research pipeline, fitness scores are produced, and all state files are persisted correctly
**Duration:** ~5-15 minutes (3 full research cycles: design + train + backtest + assess each)
**Category:** Evolution / CLI

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] CLI entry point works: `uv run python -m ktrdr.cli.app evolve --help` exits 0 and shows "start" subcommand
- [ ] Agent is idle: `curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/agent/status | jq -r '.status'` returns "idle"
- [ ] No existing evolution runs that could confuse results: `ls data/evolution/ 2>/dev/null | wc -l` (note the count; not a blocker)
- [ ] Anthropic API key configured: `curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health | jq '.api_keys_configured // "unknown"'` (or check that agent trigger does not immediately reject with "no api key")
- [ ] EURUSD data available in cache (the research pipeline will need it)

---

## Test Data

```bash
# CLI invocation -- no JSON payload, all parameters via flags
uv run ktrdr evolve start --population 3 --generations 1 --seed 42
```

**Why this data:**
- `--population 3`: Minimum interesting population (small enough to finish quickly, large enough to validate concurrent orchestration)
- `--generations 1`: M1 scope -- single generation only
- `--seed 42`: Reproducible genome selection so we can reason about failures across runs
- Default symbol (EURUSD), timeframe (1h), model (haiku): matches the pipeline's known-good configuration

---

## Execution Steps

### 1. Record Pre-Existing State

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Count existing evolution runs (to distinguish our new one later)
EXISTING_RUNS=$(ls -d data/evolution/run_* 2>/dev/null | wc -l | tr -d ' ')
echo "Existing evolution runs: $EXISTING_RUNS"

# Record current time for log filtering
START_TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "Start timestamp: $START_TIMESTAMP"
```

**Expected:**
- Command completes without error
- EXISTING_RUNS is a number (0 or more)

### 2. Run Evolution Command

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

START_TIME=$(date +%s)

# Run with timeout to prevent infinite hangs
# 15 minutes should be generous for 3 researchers
EVOLVE_OUTPUT=$(timeout 900 uv run ktrdr evolve start \
  --population 3 \
  --generations 1 \
  --seed 42 \
  2>&1)

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=== Evolution Output ==="
echo "$EVOLVE_OUTPUT"
echo "=== End Output ==="
echo ""
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"
```

**Expected:**
- Exit code 0 (not 124 which would mean timeout)
- Output contains "Evolution Experiment: run_" (run ID displayed)
- Output contains "Seeded 3 researchers"
- Output contains "Running generation 0"
- Output contains a Rich table with "Generation 0 Results"
- Duration > 30 seconds (real research cycles take time)
- Duration < 900 seconds (did not timeout)

### 3. Identify Run Directory

**Command:**
```bash
# Find the most recent run directory
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

if [ -z "$RUN_DIR" ]; then
  echo "FAIL: No evolution run directory found"
  exit 1
fi

echo "Run directory: $RUN_DIR"
ls -la "$RUN_DIR"/
echo ""
echo "Generation directory:"
ls -la "$RUN_DIR/generation_00/" 2>/dev/null || echo "FAIL: generation_00 not found"
```

**Expected:**
- RUN_DIR is set and matches pattern `data/evolution/run_YYYYMMDD_HHMMSS`
- Directory contains `config.yaml`
- Directory contains `generation_00/` subdirectory
- `generation_00/` contains `population.yaml`, `operations.yaml`, `results.yaml`

### 4. Validate config.yaml

**Command:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

echo "=== config.yaml ==="
cat "$RUN_DIR/config.yaml"
echo ""

# Validate key fields
POP_SIZE=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUN_DIR/config.yaml')); print(d['population_size'])")
GENS=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUN_DIR/config.yaml')); print(d['generations'])")
SYMBOL=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUN_DIR/config.yaml')); print(d['symbol'])")
SEED=$(python3 -c "import yaml; d=yaml.safe_load(open('$RUN_DIR/config.yaml')); print(d.get('seed', 'None'))")

echo "Population size: $POP_SIZE"
echo "Generations: $GENS"
echo "Symbol: $SYMBOL"
echo "Seed: $SEED"

[ "$POP_SIZE" = "3" ] && echo "OK: population_size" || echo "FAIL: population_size expected 3, got $POP_SIZE"
[ "$GENS" = "1" ] && echo "OK: generations" || echo "FAIL: generations expected 1, got $GENS"
[ "$SYMBOL" = "EURUSD" ] && echo "OK: symbol" || echo "FAIL: symbol expected EURUSD, got $SYMBOL"
[ "$SEED" = "42" ] && echo "OK: seed" || echo "FAIL: seed expected 42, got $SEED"
```

**Expected:**
- config.yaml is valid YAML
- population_size = 3
- generations = 1
- symbol = EURUSD
- seed = 42

### 5. Validate population.yaml

**Command:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

echo "=== generation_00/population.yaml ==="
cat "$RUN_DIR/generation_00/population.yaml"
echo ""

# Validate population
RESEARCHER_COUNT=$(python3 -c "
import yaml
pop = yaml.safe_load(open('$RUN_DIR/generation_00/population.yaml'))
print(len(pop))
")

echo "Researcher count: $RESEARCHER_COUNT"
[ "$RESEARCHER_COUNT" = "3" ] && echo "OK: 3 researchers" || echo "FAIL: expected 3 researchers, got $RESEARCHER_COUNT"

# Validate researcher structure
python3 -c "
import yaml
pop = yaml.safe_load(open('$RUN_DIR/generation_00/population.yaml'))
for r in pop:
    rid = r['id']
    gen = r['generation']
    genome = r['genome']
    traits = sorted(genome.keys())
    parent = r.get('parent_id')
    print(f'  {rid}: gen={gen}, genome={genome}, parent={parent}')
    assert rid.startswith('r_g00_'), f'Bad ID prefix: {rid}'
    assert gen == 0, f'Bad generation: {gen}'
    assert parent is None, f'Gen 0 should have no parent: {parent}'
    assert set(traits) == {'memory_depth', 'novelty_seeking', 'skepticism'}, f'Bad traits: {traits}'
    for t in genome.values():
        assert t in ('off', 'low', 'high'), f'Bad trait level: {t}'
print('OK: All researchers valid')
"
```

**Expected:**
- Exactly 3 researchers in population
- All IDs start with `r_g00_` (generation 0)
- All have generation = 0
- All have parent_id = None
- Each genome has exactly 3 traits (novelty_seeking, skepticism, memory_depth)
- Each trait value is one of: off, low, high
- All 3 genomes are distinct (no duplicates since seed sampling is without replacement)

### 6. Validate operations.yaml

**Command:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

echo "=== generation_00/operations.yaml ==="
cat "$RUN_DIR/generation_00/operations.yaml"
echo ""

# Validate operations
python3 -c "
import yaml
ops = yaml.safe_load(open('$RUN_DIR/generation_00/operations.yaml'))
print(f'Operations count: {len(ops)}')
for rid, oid in ops.items():
    print(f'  {rid} -> {oid}')
    assert rid.startswith('r_g00_'), f'Bad researcher ID: {rid}'
    assert oid.startswith('op_'), f'Bad operation ID: {oid}'
print('OK: All operations valid')
"
```

**Expected:**
- 3 entries mapping researcher IDs to operation IDs
- All researcher IDs match those in population.yaml
- All operation IDs have the `op_` prefix

### 7. Validate results.yaml

**Command:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

echo "=== generation_00/results.yaml ==="
cat "$RUN_DIR/generation_00/results.yaml"
echo ""

# Validate results
python3 -c "
import yaml
results = yaml.safe_load(open('$RUN_DIR/generation_00/results.yaml'))
print(f'Results count: {len(results)}')

successful = 0
failed = 0
for r in results:
    rid = r['researcher_id']
    fitness = r['fitness']
    has_backtest = r.get('backtest_result') is not None
    status = 'OK' if fitness > -999.0 else 'FAILED'
    if fitness > -999.0:
        successful += 1
    else:
        failed += 1
    print(f'  {rid}: fitness={fitness:.4f}, has_backtest={has_backtest}, status={status}')

print(f'')
print(f'Successful: {successful}')
print(f'Failed: {failed}')
print(f'Total: {len(results)}')

assert len(results) == 3, f'Expected 3 results, got {len(results)}'
print('OK: All 3 researchers have results')

assert successful >= 1, f'Expected at least 1 successful researcher, got {successful}'
print(f'OK: At least 1 researcher succeeded ({successful}/3)')
"
```

**Expected:**
- Exactly 3 result entries (one per researcher)
- Each result has researcher_id, fitness, and backtest_result fields
- At least 1 researcher has fitness > -999.0 (successful backtest)
- Failed researchers have fitness = -999.0

### 8. Cross-Validate Researcher IDs

**Command:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

python3 -c "
import yaml

pop = yaml.safe_load(open('$RUN_DIR/generation_00/population.yaml'))
ops = yaml.safe_load(open('$RUN_DIR/generation_00/operations.yaml'))
results = yaml.safe_load(open('$RUN_DIR/generation_00/results.yaml'))

pop_ids = {r['id'] for r in pop}
ops_ids = set(ops.keys())
result_ids = {r['researcher_id'] for r in results}

print(f'Population IDs: {sorted(pop_ids)}')
print(f'Operations IDs: {sorted(ops_ids)}')
print(f'Result IDs:     {sorted(result_ids)}')

assert pop_ids == ops_ids, f'Mismatch: population vs operations: {pop_ids ^ ops_ids}'
assert pop_ids == result_ids, f'Mismatch: population vs results: {pop_ids ^ result_ids}'
print('OK: All ID sets match across population, operations, and results')
"
```

**Expected:**
- The same 3 researcher IDs appear in population.yaml, operations.yaml, and results.yaml
- No missing or extra IDs in any file

### 9. Verify Operations Exist in Backend API

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)

python3 -c "
import yaml, subprocess, json

ops = yaml.safe_load(open('$RUN_DIR/generation_00/operations.yaml'))

for rid, oid in ops.items():
    result = subprocess.run(
        ['curl', '-s', 'http://localhost:$API_PORT/api/v1/operations/' + oid],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        status = data.get('data', {}).get('status', data.get('status', 'unknown'))
        print(f'  {rid} -> {oid}: status={status}')
    except json.JSONDecodeError:
        print(f'  {rid} -> {oid}: COULD NOT PARSE RESPONSE')
        print(f'    Response: {result.stdout[:200]}')
"
```

**Expected:**
- Each operation ID resolves to a real operation in the backend
- Status is "completed" or "failed" (not "running" -- the command already finished)

---

## Success Criteria

All must pass for the test to pass:

- [ ] `ktrdr evolve start --population 3 --generations 1 --seed 42` exits with code 0
- [ ] Run directory created at `data/evolution/run_YYYYMMDD_HHMMSS/`
- [ ] `config.yaml` exists and contains correct parameters (population_size=3, generations=1, seed=42)
- [ ] `generation_00/population.yaml` exists with exactly 3 researchers, all generation 0, all with valid genomes
- [ ] `generation_00/operations.yaml` exists with 3 researcher-to-operation mappings
- [ ] `generation_00/results.yaml` exists with exactly 3 result entries
- [ ] At least 1 researcher has fitness > -999.0 (successful backtest)
- [ ] All 3 researchers have fitness scores (even failures get -999.0)
- [ ] Researcher IDs are consistent across population, operations, and results files
- [ ] CLI output shows the results table with researcher IDs and fitness scores

---

## Sanity Checks

**CRITICAL:** These catch false positives -- scenarios where the test "passes" but something is actually broken.

- [ ] **Duration > 30 seconds** -- If the command completes in < 30s, research cycles did not actually run. The harness may have short-circuited or used cached results. A real generation with 3 researchers through design+train+backtest+assess takes minutes.
- [ ] **Duration < 900 seconds** -- If it took > 15 minutes, something is stuck or retrying excessively. Check for at_capacity backoff loops.
- [ ] **At least 1 fitness is NOT -999.0** -- If all 3 researchers failed, the pipeline is broken even though the harness completed "successfully." A total wipeout means something systemic is wrong (agent trigger broken, workers down, etc.).
- [ ] **No fitness above 10.0** -- Fitness = sharpe - lambda_dd * max_drawdown. A fitness > 10 is implausible for a randomly-designed strategy and suggests the scoring formula is receiving garbage data.
- [ ] **Researcher IDs follow r_g00_NNN format** -- If IDs are malformed, the population seeding is broken.
- [ ] **3 distinct genomes in population** -- If all genomes are identical, the random sampling or genome creation is broken.
- [ ] **Operation IDs are all different** -- If any two researchers share an operation ID, the trigger logic is reusing operations.
- [ ] **Operations exist in backend** -- If the operations API returns 404 for any operation, the trigger did not actually hit the backend (possible base_url mismatch).

**Check for distinct genomes:**
```bash
RUN_DIR=$(ls -dt data/evolution/run_* 2>/dev/null | head -1)
python3 -c "
import yaml
pop = yaml.safe_load(open('$RUN_DIR/generation_00/population.yaml'))
genomes = [str(sorted(r['genome'].items())) for r in pop]
unique = len(set(genomes))
print(f'Unique genomes: {unique}/{len(genomes)}')
assert unique == len(genomes), f'Duplicate genomes found!'
print('OK: All genomes distinct')
"
```

---

## Troubleshooting

**If CLI exits with ModuleNotFoundError:**
- **Cause:** evolve command not registered or evolution module missing
- **Cure:** Check that `ktrdr/cli/commands/evolve.py` exists and `evolve_app` is registered in `ktrdr/cli/app.py`

**If "Seeded 3 researchers" but then hangs indefinitely:**
- **Cause:** Agent trigger returning "at_capacity" repeatedly, causing exponential backoff
- **Cure:** Check if another agent cycle is already running: `curl -s http://localhost:$API_PORT/api/v1/agent/status`. If busy, wait for it to finish or cancel it.

**If all 3 researchers fail (all fitness = -999.0):**
- **Cause:** Research pipeline broken upstream -- agent trigger, design phase, training, or backtest might be failing
- **Cure:** Check individual operation logs. Pick one operation ID from operations.yaml and trace it:
  ```bash
  curl -s "http://localhost:$API_PORT/api/v1/operations/$OP_ID" | jq
  ```
  Also check backend logs: `docker compose logs backend --since 15m | grep -i error`

**If results.yaml has fewer than 3 entries:**
- **Cause:** Budget exhaustion mid-generation -- the harness hit a "budget_exhausted" response and aborted
- **Cure:** Check budget configuration. The Anthropic API key may have hit its spending limit.

**If run directory not created:**
- **Cause:** Filesystem permissions or the CLI crashed before creating the directory
- **Cure:** Check the full CLI stderr output. Try running manually: `uv run python -m ktrdr.cli.app evolve start --population 3 --generations 1`

**If config.yaml has wrong values:**
- **Cause:** CLI parameter parsing broken or EvolutionConfig defaults overriding CLI values
- **Cure:** Check `ktrdr/cli/commands/evolve.py` parameter wiring to `EvolutionConfig`

**If operation IDs not in backend (404):**
- **Cause:** Harness using wrong base_url (e.g., localhost:8000 when sandbox is on a different port)
- **Cure:** Check if `.env.sandbox` exists and whether `GenerationHarness` reads the correct port. The harness defaults to `http://localhost:8000`.

**If timeout (exit code 124):**
- **Cause:** One or more research cycles stuck in polling loop (poll_interval is 30s by default, and operations may hang)
- **Cure:** Check for stuck operations: `curl -s "http://localhost:$API_PORT/api/v1/operations?status=running" | jq`. Check worker health.

---

## Evidence to Capture

- Full CLI output (stdout + stderr from step 2)
- Total duration in seconds
- Run directory path
- Contents of all 4 state files: config.yaml, population.yaml, operations.yaml, results.yaml
- Per-researcher: ID, genome traits, fitness score, operation ID, operation status
- Count of successful vs. failed researchers
- Any error messages from CLI or backend logs

---

## Notes for Implementation

- The `--seed 42` flag ensures reproducible genome selection, which makes debugging easier across runs. The same 3 genomes will be chosen every time.
- The harness triggers researchers sequentially (not truly concurrent) via the agent trigger API. Each trigger starts an agent cycle that goes through design, training, backtesting, and assessment. With agent concurrency limits, researchers may queue up.
- The default `poll_interval` is 30 seconds. Between triggers and polls, the total time for 3 researchers could be 5-15 minutes depending on training duration and any at_capacity backoff.
- The harness communicates via HTTP to `http://localhost:8000` by default. If running in a sandbox, this will need to match the sandbox port. Currently the harness hardcodes port 8000 -- if testing in a sandbox, this is a known limitation.
- Budget exhaustion (Anthropic API key spending cap) will cause the harness to abort the entire generation with all researchers getting MINIMUM_FITNESS (-999.0). This is by design, not a bug.
- The fitness formula is `sharpe - lambda_dd * max_drawdown`. Realistic fitness values for randomly-designed strategies are roughly in the range [-5.0, 2.0]. Values outside this range are not impossible but warrant investigation.
