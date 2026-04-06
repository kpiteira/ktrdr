# Test: squad/m2-director-consultation

**Purpose:** Validate that the Director dynamically selects DIFFERENT agent combinations across cycles based on KB state and cadence mode. Runs 3 cycles (full_squad, quick_iteration, full_squad) and proves the conversational model produces intelligent orchestration, not a fixed pipeline.

**Duration:** ~60-120 minutes (3 cycles, each 10-40 minutes)

**Category:** Squad / Conversational Orchestrator / M2

**Estimated cost:** ~$15-45 (3 real Claude sessions + agent spawns)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox (slot 3, port 8003), API health

**Test-specific checks:**

- [ ] Sandbox running on correct slot

```bash
source .env.sandbox
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:${KTRDR_API_PORT}/api/v1/health)
if [ "$HTTP_CODE" != "200" ]; then
  echo "FAIL: Backend API not responding on port ${KTRDR_API_PORT} (HTTP $HTTP_CODE)"
  exit 1
fi
echo "OK: Backend API healthy on port ${KTRDR_API_PORT}"
```

- [ ] KB files exist at shared dir

```bash
SHARED="$HOME/.ktrdr/shared/squad"
MISSING=""
for KB_FILE in knowledge/experiments.md knowledge/hypotheses.md knowledge/decisions.md knowledge/frontiers.md knowledge/synthesis.md loop/cadence.md loop/nudges.md; do
  if [ ! -f "$SHARED/$KB_FILE" ]; then
    MISSING="$MISSING $KB_FILE"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing KB files:$MISSING"
  exit 1
fi
echo "OK: All KB files present"
```

- [ ] Claude Code CLI available

```bash
if ! which claude >/dev/null 2>&1; then
  echo "FAIL: claude CLI not found in PATH"
  exit 1
fi
echo "OK: claude CLI available at $(which claude)"
```

- [ ] Executor script exists and is executable

```bash
if [ ! -x ".squad/executor.sh" ]; then
  echo "FAIL: .squad/executor.sh not found or not executable"
  exit 1
fi
echo "OK: executor.sh exists and is executable"
```

- [ ] All 8 agent charters present (all 7 consultants + director)

```bash
MISSING=""
for AGENT in director engineer scribe quant inventor scout critic architect; do
  if [ ! -f ".squad/agents/${AGENT}/charter.md" ]; then
    MISSING="$MISSING $AGENT"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing charters:$MISSING"
  exit 1
fi
echo "OK: All 8 agent charters present (director + 7 consultants)"
```

- [ ] Strategies dir exists and is writable

```bash
STRAT_DIR="$HOME/.ktrdr/shared/strategies"
mkdir -p "$STRAT_DIR"
if [ ! -w "$STRAT_DIR" ]; then
  echo "FAIL: Cannot write to $STRAT_DIR"
  exit 1
fi
echo "OK: Strategies directory writable"
```

- [ ] Cadence file is writable (test needs to set cadence between cycles)

```bash
CADENCE_FILE="$HOME/.ktrdr/shared/squad/loop/cadence.md"
if [ ! -w "$CADENCE_FILE" ]; then
  echo "FAIL: Cannot write to $CADENCE_FILE"
  exit 1
fi
echo "OK: cadence.md is writable"
```

---

## Execution Steps

### Phase 1: Snapshot Pre-Cycle State

Capture baseline state before any cycles run.

#### 1.1 Record Baseline and Prepare Cadence

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
STRAT_DIR="$HOME/.ktrdr/shared/strategies"

# Count existing strategy files
STRAT_COUNT_BEFORE=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')
echo "Strategies before: $STRAT_COUNT_BEFORE"

# Record experiments.md line count
EXP_LINES_BEFORE=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')
echo "experiments.md lines before: $EXP_LINES_BEFORE"

# Record frontiers.md content hash (Director should cite this)
FRONTIERS_HASH=$(md5 -q "$SHARED/knowledge/frontiers.md" 2>/dev/null || md5sum "$SHARED/knowledge/frontiers.md" | cut -d' ' -f1)
echo "frontiers.md hash: $FRONTIERS_HASH"

# Set cadence to full_squad for cycle 1
echo "cadence: full_squad" > "$SHARED/loop/cadence.md"
echo "Cadence set to full_squad for cycle 1"

# Save baselines
echo "$STRAT_COUNT_BEFORE" > /tmp/squad-m2-strat-count-before.txt
echo "$EXP_LINES_BEFORE" > /tmp/squad-m2-exp-lines-before.txt
echo "$FRONTIERS_HASH" > /tmp/squad-m2-frontiers-hash.txt

# Clean any prior test output
rm -f /tmp/squad-m2-cycle-*.txt
```

**Expected:**
- Baseline values captured
- Cadence file set to full_squad
- Exit code: 0

---

### Phase 2: Run 3 Cycles with Varying Cadence

Each cycle is run independently with explicit cadence control between them.

#### 2.1 Cycle 1 -- full_squad (broad consultation expected)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M2
source .env.sandbox

uv run python3 -c "
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.squad')))
from squad_engine.loop import run_cycle

async def main():
    result = await run_cycle(
        iteration=200,
        shared_dir=str(Path.home() / '.ktrdr/shared/squad'),
        charter_dir=str(Path('.squad/agents')),
    )
    output = {
        'status': result.status,
        'iteration': result.iteration,
        'total_cost_usd': result.total_cost_usd,
        'agents_spawned': result.agents_spawned,
        'experiment_result': result.experiment_result,
        'cadence_next': result.cadence_next,
        'error': result.error,
        'duration_seconds': result.duration_seconds,
    }
    print('CYCLE_RESULT_JSON:' + json.dumps(output))

asyncio.run(main())
" 2>&1 | tee /tmp/squad-m2-cycle-1.txt
```

**Expected:**
- Output contains `CYCLE_RESULT_JSON:` with valid JSON
- Duration: 10-40 minutes
- agents_spawned should include engineer, scribe, and likely 1+ consultants (full_squad cadence)

#### 2.2 Set Cadence to quick_iteration for Cycle 2

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
echo "cadence: quick_iteration" > "$SHARED/loop/cadence.md"
echo "Cadence set to quick_iteration for cycle 2"
cat "$SHARED/loop/cadence.md"
```

**Expected:**
- cadence.md contains "cadence: quick_iteration"

#### 2.3 Cycle 2 -- quick_iteration (narrow consultation expected)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M2
source .env.sandbox

uv run python3 -c "
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.squad')))
from squad_engine.loop import run_cycle

async def main():
    result = await run_cycle(
        iteration=201,
        shared_dir=str(Path.home() / '.ktrdr/shared/squad'),
        charter_dir=str(Path('.squad/agents')),
    )
    output = {
        'status': result.status,
        'iteration': result.iteration,
        'total_cost_usd': result.total_cost_usd,
        'agents_spawned': result.agents_spawned,
        'experiment_result': result.experiment_result,
        'cadence_next': result.cadence_next,
        'error': result.error,
        'duration_seconds': result.duration_seconds,
    }
    print('CYCLE_RESULT_JSON:' + json.dumps(output))

asyncio.run(main())
" 2>&1 | tee /tmp/squad-m2-cycle-2.txt
```

**Expected:**
- Output contains `CYCLE_RESULT_JSON:` with valid JSON
- agents_spawned should be narrower (engineer + scribe only, per quick_iteration instructions)
- Duration: likely shorter than cycle 1

#### 2.4 Set Cadence to full_squad for Cycle 3

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
echo "cadence: full_squad" > "$SHARED/loop/cadence.md"
echo "Cadence set to full_squad for cycle 3"
```

#### 2.5 Cycle 3 -- full_squad (broad consultation, potentially different mix from Cycle 1)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M2
source .env.sandbox

uv run python3 -c "
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path('.squad')))
from squad_engine.loop import run_cycle

async def main():
    result = await run_cycle(
        iteration=202,
        shared_dir=str(Path.home() / '.ktrdr/shared/squad'),
        charter_dir=str(Path('.squad/agents')),
    )
    output = {
        'status': result.status,
        'iteration': result.iteration,
        'total_cost_usd': result.total_cost_usd,
        'agents_spawned': result.agents_spawned,
        'experiment_result': result.experiment_result,
        'cadence_next': result.cadence_next,
        'error': result.error,
        'duration_seconds': result.duration_seconds,
    }
    print('CYCLE_RESULT_JSON:' + json.dumps(output))

asyncio.run(main())
" 2>&1 | tee /tmp/squad-m2-cycle-3.txt
```

**Expected:**
- Output contains `CYCLE_RESULT_JSON:` with valid JSON
- agents_spawned should include consultants beyond just engineer + scribe
- KB state has evolved from cycles 1 and 2, so Director may choose different consultants

---

### Phase 3: Validate Across All 3 Cycles

Parse CycleResult JSON from all 3 cycles and validate cross-cycle properties.

#### 3.1 Verify All 3 Cycles Completed Successfully

**Command:**
```bash
ALL_OK=true
for CYCLE_NUM in 1 2 3; do
  RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-m2-cycle-${CYCLE_NUM}.txt | tail -1)
  if [ -z "$RESULT_LINE" ]; then
    echo "FAIL: Cycle $CYCLE_NUM has no CYCLE_RESULT_JSON output"
    ALL_OK=false
    continue
  fi
  RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

  STATUS=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
  ERROR=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error'))")

  if [ "$STATUS" != "COMPLETE" ]; then
    echo "FAIL: Cycle $CYCLE_NUM status='$STATUS', error='$ERROR'"
    ALL_OK=false
  else
    echo "OK: Cycle $CYCLE_NUM completed"
  fi
done

if [ "$ALL_OK" != "true" ]; then
  exit 1
fi
echo "OK: All 3 cycles completed successfully"
```

#### 3.2 Verify At Least 2 Distinct Agent Combinations Across Cycles

**Command:**
```bash
python3 -c "
import json, sys

combinations = []
for cycle_num in [1, 2, 3]:
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                agents = sorted(data['agents_spawned'])
                combinations.append(agents)
                print(f'Cycle {cycle_num}: {agents}')

# Convert to sets for comparison
unique_combos = set()
for combo in combinations:
    unique_combos.add(tuple(combo))

print(f'Distinct combinations: {len(unique_combos)}')
for i, combo in enumerate(unique_combos, 1):
    print(f'  Combo {i}: {list(combo)}')

if len(unique_combos) < 2:
    print('FAIL: Only 1 distinct agent combination across 3 cycles -- Director is not adapting')
    sys.exit(1)

print('OK: At least 2 distinct agent combinations (Director adapts selections)')
"
```

**Expected:**
- At least 2 distinct sets of agents_spawned across the 3 cycles
- quick_iteration cycle (cycle 2) should have a strictly smaller set than full_squad cycles

#### 3.3 Verify quick_iteration Cycle Uses Fewer Agents Than full_squad

**Command:**
```bash
python3 -c "
import json, sys

agents_per_cycle = {}
for cycle_num in [1, 2, 3]:
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                agents_per_cycle[cycle_num] = data['agents_spawned']

cycle2_count = len(agents_per_cycle[2])
cycle1_count = len(agents_per_cycle[1])
cycle3_count = len(agents_per_cycle[3])
max_full_squad = max(cycle1_count, cycle3_count)

print(f'Cycle 1 (full_squad): {cycle1_count} agents {agents_per_cycle[1]}')
print(f'Cycle 2 (quick_iteration): {cycle2_count} agents {agents_per_cycle[2]}')
print(f'Cycle 3 (full_squad): {cycle3_count} agents {agents_per_cycle[3]}')

if cycle2_count >= max_full_squad:
    print(f'FAIL: quick_iteration cycle spawned {cycle2_count} agents, same or more than full_squad ({max_full_squad})')
    sys.exit(1)

print(f'OK: quick_iteration ({cycle2_count} agents) < full_squad ({max_full_squad} agents)')
"
```

**Expected:**
- Cycle 2 (quick_iteration) agent count is strictly less than at least one full_squad cycle

#### 3.4 Verify Token Usage: Fewer Consultants = Fewer Tokens (Cost Proxy)

**Command:**
```bash
python3 -c "
import json, sys

costs = {}
for cycle_num in [1, 2, 3]:
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                costs[cycle_num] = data['total_cost_usd']

print(f'Cycle 1 (full_squad): \${costs[1]:.4f}')
print(f'Cycle 2 (quick_iteration): \${costs[2]:.4f}')
print(f'Cycle 3 (full_squad): \${costs[3]:.4f}')

# All costs must be > 0 (proves real sessions ran)
for cn, cost in costs.items():
    if cost <= 0:
        print(f'FAIL: Cycle {cn} cost is \${cost} -- sessions did not run')
        sys.exit(1)

# quick_iteration should cost less than at least one full_squad cycle
max_full = max(costs[1], costs[3])
if costs[2] >= max_full:
    print(f'WARNING: quick_iteration cost (\${costs[2]:.4f}) >= full_squad max (\${max_full:.4f})')
    print('This is unexpected but not a hard failure -- execution cost (training) may dominate')
else:
    print(f'OK: quick_iteration (\${costs[2]:.4f}) < full_squad max (\${max_full:.4f})')

# At minimum, all costs > 0
print('OK: All cycles have cost > 0 (real Claude sessions confirmed)')
"
```

**Expected:**
- All 3 costs > 0 (hard requirement -- proves real sessions)
- Cycle 2 cost < max(cycle 1, cycle 3) cost (soft expectation -- training cost may dominate)

#### 3.5 Verify All Sessions Tear Down Cleanly

**Command:**
```bash
python3 -c "
import json, sys

for cycle_num in [1, 2, 3]:
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                error = data.get('error')
                if error is not None:
                    print(f'FAIL: Cycle {cycle_num} has error: {error}')
                    sys.exit(1)
                print(f'OK: Cycle {cycle_num} error=None (clean teardown)')

print('OK: All 3 cycles tore down cleanly (no lingering errors)')
"
```

#### 3.6 Verify KB Was Modified (Scribe Wrote in Each Cycle)

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
EXP_LINES_BEFORE=$(cat /tmp/squad-m2-exp-lines-before.txt)
EXP_LINES_AFTER=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')

echo "experiments.md: before=$EXP_LINES_BEFORE, after=$EXP_LINES_AFTER"

if [ "$EXP_LINES_AFTER" -le "$EXP_LINES_BEFORE" ]; then
  echo "FAIL: experiments.md not modified after 3 cycles"
  exit 1
fi

# Rough check: at least 2 cycles should have written (cycle 2 quick_iteration still has Scribe)
GROWTH=$(( EXP_LINES_AFTER - EXP_LINES_BEFORE ))
echo "Growth: $GROWTH lines"

if [ "$GROWTH" -lt 10 ]; then
  echo "WARNING: Only $GROWTH lines added across 3 cycles (expected more)"
fi

echo "OK: experiments.md grew by $GROWTH lines across 3 cycles"
```

#### 3.7 Verify Engineer and Scribe Present in Every Cycle

**Command:**
```bash
python3 -c "
import json, sys

for cycle_num in [1, 2, 3]:
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                agents = data['agents_spawned']
                missing = []
                if 'engineer' not in agents:
                    missing.append('engineer')
                if 'scribe' not in agents:
                    missing.append('scribe')
                if missing:
                    print(f'FAIL: Cycle {cycle_num} missing core agents: {missing} (spawned: {agents})')
                    sys.exit(1)
                print(f'OK: Cycle {cycle_num} has engineer + scribe (full set: {agents})')

print('OK: Engineer and Scribe present in all 3 cycles')
"
```

#### 3.8 Verify full_squad Cycles Include At Least One Consultant Beyond Engineer+Scribe

**Command:**
```bash
python3 -c "
import json, sys

CONSULTANTS = {'quant', 'inventor', 'scout', 'critic', 'architect'}
found_consultant = False

for cycle_num in [1, 3]:  # full_squad cycles only
    with open(f'/tmp/squad-m2-cycle-{cycle_num}.txt') as f:
        for line in f:
            if line.startswith('CYCLE_RESULT_JSON:'):
                data = json.loads(line.split('CYCLE_RESULT_JSON:', 1)[1])
                agents = set(data['agents_spawned'])
                consultants_used = agents & CONSULTANTS
                print(f'Cycle {cycle_num} (full_squad): consultants used = {consultants_used or \"none\"}')
                if consultants_used:
                    found_consultant = True

if not found_consultant:
    print('FAIL: Neither full_squad cycle used any consultant beyond engineer+scribe')
    print('This means the Director is not leveraging the expanded squad')
    sys.exit(1)

print('OK: At least one full_squad cycle used a consultant (Director leverages squad)')
"
```

**Expected:**
- At least one of cycle 1 or cycle 3 spawns a consultant from {quant, inventor, scout, critic, architect}

---

## Success Criteria

All must pass:

- [ ] All 3 cycles complete with status=COMPLETE and error=None
- [ ] At least 2 distinct agent combinations across the 3 cycles
- [ ] quick_iteration cycle (cycle 2) uses fewer agents than at least one full_squad cycle
- [ ] All 3 cycles have total_cost_usd > 0 (real Claude sessions ran)
- [ ] Engineer and Scribe present in all 3 cycles (core roles always used)
- [ ] At least one full_squad cycle uses a consultant beyond engineer+scribe
- [ ] experiments.md grew (Scribe wrote results)
- [ ] All sessions tore down cleanly (no lingering errors)

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| total_cost_usd > 0 for all 3 cycles | Mocked or short-circuited sessions |
| At least 2 DISTINCT agent combinations (not just different counts) | Director always picks the same agents regardless of cadence/KB state |
| quick_iteration agent count < full_squad agent count | Director ignores cadence instructions, always spawns full team |
| Consultant present in full_squad cycle | Director never uses expanded roles (M2 regression to M1 behavior) |
| experiments.md line count grew (not just mtime) | Scribe touched file but did not write |
| error=None checked separately from status=COMPLETE | Status set in finally block masking caught exceptions |
| Engineer+Scribe in EVERY cycle | Director skipped core roles in quick_iteration |
| Cost comparison is soft (WARNING not FAIL) | Training execution cost may dominate token cost, making cycles with fewer agents not obviously cheaper |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| CYCLE_RESULT_JSON not found in output | EXECUTION_FAILURE | Check /tmp/squad-m2-cycle-N.txt for Python traceback |
| status=FAILED on any cycle | ORCHESTRATION_FAILURE | Read error field -- Director may have failed tool calls |
| Only 1 distinct agent combination | DIRECTOR_INTELLIGENCE | Director is not adapting to cadence/KB -- check director_prompt.py cadence instructions |
| quick_iteration uses same or more agents | CADENCE_FAILURE | _build_task_instructions() may not be generating correct quick_iteration prompt |
| No consultants in full_squad cycles | DIRECTOR_INTELLIGENCE | Director not leveraging expanded squad -- check CONSULTANT_TRIGGERS in director_prompt.py |
| Missing engineer or scribe in any cycle | DIRECTOR_FAILURE | Director skipped core agents -- check charter and tool descriptions |
| total_cost_usd == 0 for any cycle | SESSION_FAILURE | Claude sessions did not connect -- check claude CLI |
| experiments.md not modified | SCRIBE_FAILURE | Scribe did not update KB -- check scribe charter |
| Cadence file not updated between cycles | TEST_SETUP | Phase 2.2/2.4 cadence write failed -- check file permissions |
| Cycle hangs > 60 minutes | TIMEOUT | Training may be stuck -- check executor.sh stall detection |

---

## Troubleshooting

**If only 1 distinct agent combination across all 3 cycles:**
- Check cadence.md was actually written between cycles: `cat ~/.ktrdr/shared/squad/loop/cadence.md`
- Verify `_build_task_instructions()` returns different instructions for `quick_iteration` vs `full_squad`
- Check the Director prompt in /tmp/squad-m2-cycle-N.txt logs for what cadence it received
- The Director may be ignoring cadence guidance -- strengthen the charter instructions

**If quick_iteration uses the same number of agents:**
- The Director has latitude even in quick_iteration to add consultants if it deems necessary
- Check the Director prompt: quick_iteration says "Use Engineer only" but the Director may override
- If this consistently happens, the quick_iteration instructions in `_build_task_instructions()` need strengthening
- As a fallback, verify the agent lists are at least different (different roles even if same count)

**If no consultants appear in full_squad cycles:**
- This means M2 regressed to M1 behavior (Director only uses engineer + scribe)
- Check `CONSULTANT_TRIGGERS` section is present in the assembled prompt
- Check the spawn_agent tool description lists all 7 roles
- Verify agent charters exist for all consultant roles: `ls .squad/agents/*/charter.md`
- Check frontiers.md has content -- empty frontiers gives the Director nothing to consult about

**If cycles 1 and 3 have identical agent sets:**
- This is acceptable if the KB state did not change enough to warrant different consultants
- The key M2 validation is cycle 2 vs cycles 1/3, not cycle 1 vs cycle 3
- If cycles 1 and 3 are always identical across multiple runs, the Director may not be reading updated KB

**If a cycle hangs:**
- Training/backtest execution dominates cycle time (10-30 min is normal)
- Check executor.sh has the 15-minute stall detection timeout
- Check sandbox backend is still healthy: `curl http://localhost:${KTRDR_API_PORT}/api/v1/health`
- Check for stuck Claude sessions: look for `claude` processes in `ps aux | grep claude`

**If total_cost_usd is 0 for one cycle but not others:**
- The `_director_response` test injection path may have been triggered accidentally
- Verify all 3 cycles use the production code path (no `_director_response` argument)
- Check claude CLI is still authenticated: `claude --version`

---

## Evidence to Capture

- Full /tmp/squad-m2-cycle-1.txt, /tmp/squad-m2-cycle-2.txt, /tmp/squad-m2-cycle-3.txt
- CycleResult JSON from each cycle (status, agents_spawned, cost, cadence_next, error, duration)
- Side-by-side comparison of agents_spawned across all 3 cycles
- experiments.md diff (before vs after line count, tail -20 of new content)
- cadence.md content at each transition point
- Total cost across all 3 cycles
- Total duration across all 3 cycles
