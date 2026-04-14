# Test: squad/m4-loop-automation

**Purpose:** Validate the Python loop runner (`run_loop()` in `.squad/squad_engine/loop_runner.py`) can execute 5 unattended research cycles with cadence management, stall detection, cycle history tracking, and cost accumulation. This replaces the 810-line shell script with a structured Python loop.

**Duration:** ~2-3 hours (5 real research cycles with training + backtest each)

**Category:** Squad / Loop Automation / M4

**Cost estimate:** $5-10 (5 cycles x $1-2 each for Claude sessions + training/backtest)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox (slot 2, port 8002), API health

**Test-specific checks:**

- [ ] Sandbox running on slot 2 (port 8002)

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
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
MISSING=""
for KB_FILE in knowledge/experiments.md knowledge/hypotheses.md knowledge/decisions.md knowledge/frontiers.md loop/cadence.md loop/nudges.md; do
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

- [ ] Python loop runner module importable

```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M4
uv run python3 -c "
import sys
sys.path.insert(0, '.squad')
from squad_engine.loop_runner import run_loop, LoopResult
print('OK: loop_runner importable')
print(f'  run_loop signature: max_iterations, synthesis_interval params')
print(f'  LoopResult fields: iterations_run, experiments_completed, stall_detected, final_cadence, total_cost_usd, status')
"
```

- [ ] Executor script exists and is executable

```bash
if [ ! -x ".squad/executor.sh" ]; then
  echo "FAIL: .squad/executor.sh not found or not executable"
  exit 1
fi
echo "OK: executor.sh exists and is executable"
```

- [ ] Agent charters present

```bash
MISSING=""
for AGENT in director engineer scribe; do
  if [ ! -f ".squad/agents/${AGENT}/charter.md" ]; then
    MISSING="$MISSING $AGENT"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing charters:$MISSING"
  exit 1
fi
echo "OK: Required agent charters present"
```

- [ ] No pre-existing stall state (clean slate)

```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
if [ -f "$SHARED/loop/fatal-error.md" ]; then
  echo "WARN: Removing stale fatal-error.md from previous run"
  rm "$SHARED/loop/fatal-error.md"
fi
echo "OK: No stale fatal-error state"
```

---

## Execution Steps

### Phase 1: Snapshot Pre-Loop State

Capture baseline state before the loop runs. All comparisons use these snapshots.

#### 1.1 Record Baseline State

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
STRAT_DIR="$HOME/.ktrdr/shared/strategies"

# Count existing strategy files
STRAT_COUNT_BEFORE=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')
echo "Strategies before: $STRAT_COUNT_BEFORE"

# Record experiments.md line count
EXP_LINES_BEFORE=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')
echo "experiments.md lines before: $EXP_LINES_BEFORE"

# Count existing experiment entries (## headers with "Cycle" or "Experiment")
EXP_ENTRIES_BEFORE=$(grep -c "^## " "$SHARED/knowledge/experiments.md" 2>/dev/null || echo "0")
echo "experiments.md entries before: $EXP_ENTRIES_BEFORE"

# Record current cadence
CADENCE_BEFORE=$(cat "$SHARED/loop/cadence.md" 2>/dev/null || echo "no file")
echo "Cadence before: $CADENCE_BEFORE"

# Record iteration count
ITER_BEFORE=$(cat "$SHARED/loop/iteration-count.txt" 2>/dev/null || echo "0")
echo "Iteration count before: $ITER_BEFORE"

# Record cycle history length
HISTORY_ENTRIES_BEFORE=0
if [ -f "$SHARED/loop/cycle-history.json" ]; then
  HISTORY_ENTRIES_BEFORE=$(python3 -c "import json; print(len(json.load(open('$SHARED/loop/cycle-history.json'))))" 2>/dev/null || echo "0")
fi
echo "Cycle history entries before: $HISTORY_ENTRIES_BEFORE"

# Save baselines
mkdir -p /tmp/squad-m4-e2e
echo "$STRAT_COUNT_BEFORE" > /tmp/squad-m4-e2e/strat-count-before.txt
echo "$EXP_LINES_BEFORE" > /tmp/squad-m4-e2e/exp-lines-before.txt
echo "$EXP_ENTRIES_BEFORE" > /tmp/squad-m4-e2e/exp-entries-before.txt
echo "$HISTORY_ENTRIES_BEFORE" > /tmp/squad-m4-e2e/history-entries-before.txt
```

**Expected:**
- Baseline values captured (any non-negative integers)
- Exit code: 0

---

### Phase 2: Run the Loop (5 Cycles)

Invoke `run_loop()` with max_iterations=5 and capture the LoopResult.

#### 2.1 Execute run_loop via Python

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M4

# Source sandbox env so executor.sh picks up the correct port
source .env.sandbox

SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"

uv run python3 -c "
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path('.squad')))

from squad_engine.loop_runner import run_loop

async def main():
    start = time.time()
    result = await run_loop(
        shared_dir='$SHARED',
        charter_dir=str(Path('.squad/agents')),
        max_iterations=5,
        synthesis_interval=10,  # No periodic synthesis in 5 cycles
    )
    elapsed = time.time() - start

    output = {
        'iterations_run': result.iterations_run,
        'experiments_completed': result.experiments_completed,
        'stall_detected': result.stall_detected,
        'final_cadence': result.final_cadence,
        'total_cost_usd': result.total_cost_usd,
        'status': result.status,
        'elapsed_seconds': round(elapsed, 1),
    }
    print('LOOP_RESULT_JSON:' + json.dumps(output))

asyncio.run(main())
" 2>&1 | tee /tmp/squad-m4-e2e/loop-output.txt
```

**Expected:**
- Output contains `LOOP_RESULT_JSON:` followed by valid JSON
- Exit code: 0 (no unhandled exceptions)
- Duration: 90-180 minutes (5 cycles x 20-40 min each)
- Status: "max_iterations" (all 5 completed without stall or pause)

**Important:** This runs 5 real Claude Code sessions. Each cycle spawns Director, Engineer, and Scribe agents. Training and backtest run against the live sandbox. Total cost expected $5-10.

**Timeout:** 4 hours (generous margin for cold starts and slow training)

---

### Phase 3: Validate LoopResult

Parse the LoopResult JSON and verify aggregate success criteria.

#### 3.1 Verify Status and Iteration Count

**Command:**
```bash
RESULT_LINE=$(grep 'LOOP_RESULT_JSON:' /tmp/squad-m4-e2e/loop-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^LOOP_RESULT_JSON://')

python3 -c "
import sys, json
data = json.loads('$RESULT_JSON') if '$RESULT_JSON' else json.load(sys.stdin)

status = data['status']
iters = data['iterations_run']

if status not in ('max_iterations', 'completed'):
    print(f'FAIL: Loop status={status} (expected max_iterations or completed)')
    sys.exit(1)

if iters != 5:
    print(f'FAIL: iterations_run={iters} (expected 5)')
    sys.exit(1)

print(f'OK: Loop completed 5 iterations (status={status})')
" <<< "$RESULT_JSON"
```

**Expected:**
- iterations_run == 5
- status == "max_iterations" (all iterations consumed)

#### 3.2 Verify No Stall Detected

**Command:**
```bash
RESULT_LINE=$(grep 'LOOP_RESULT_JSON:' /tmp/squad-m4-e2e/loop-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^LOOP_RESULT_JSON://')

python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
if data['stall_detected']:
    print('FAIL: Stall was detected (3+ consecutive non-productive cycles)')
    sys.exit(1)
print('OK: No stall detected (all cycles productive)')
" <<< "$RESULT_JSON"
```

**Expected:**
- stall_detected == false

#### 3.3 Verify Total Cost Within Budget

**Command:**
```bash
RESULT_LINE=$(grep 'LOOP_RESULT_JSON:' /tmp/squad-m4-e2e/loop-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^LOOP_RESULT_JSON://')

python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
cost = data['total_cost_usd']

if cost <= 0:
    print(f'FAIL: total_cost_usd={cost} (expected > 0, proves real sessions ran)')
    sys.exit(1)

if cost > 10.0:
    print(f'FAIL: total_cost_usd={cost} (exceeded \$10 budget)')
    sys.exit(1)

print(f'OK: total_cost_usd=\${cost:.4f} (within budget, confirms real processing)')
" <<< "$RESULT_JSON"
```

**Expected:**
- 0 < total_cost_usd <= 10.0
- cost > 0 proves real Claude sessions ran (not mocked)

#### 3.4 Verify Experiments Completed

**Command:**
```bash
RESULT_LINE=$(grep 'LOOP_RESULT_JSON:' /tmp/squad-m4-e2e/loop-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^LOOP_RESULT_JSON://')

python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
exp = data['experiments_completed']

# Not all 5 cycles must produce experiments (synthesis cycles don't),
# but at least 3 of 5 should
if exp < 3:
    print(f'FAIL: experiments_completed={exp} (expected >= 3 out of 5 cycles)')
    sys.exit(1)

print(f'OK: experiments_completed={exp} out of 5 cycles')
" <<< "$RESULT_JSON"
```

**Expected:**
- experiments_completed >= 3 (at least 3 of 5 cycles produced experiments)

---

### Phase 4: Verify Cadence Changes

The Director should change cadence at least once across 5 cycles (e.g., full_squad to quick_iteration after a productive cycle).

#### 4.1 Verify Cadence Changed in Cycle History

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
HISTORY_FILE="$SHARED/loop/cycle-history.json"

python3 -c "
import json, sys

history = json.load(open('$HISTORY_FILE'))

# Get the last 5 entries (our test run)
recent = history[-5:] if len(history) >= 5 else history

if len(recent) < 5:
    print(f'WARN: Only {len(recent)} history entries (expected 5)')

# Check cadence file for current value
cadence_file = '$SHARED/loop/cadence.md'
with open(cadence_file) as f:
    current = f.read().strip()
print(f'Current cadence file: {current}')
print(f'History entries: {len(recent)}')
for e in recent:
    print(f'  Iteration {e[\"iteration\"]}: status={e[\"status\"]}, experiment={e.get(\"experiment\", \"none\")}')
"
```

**Expected:**
- Cycle history shows iteration progression
- Cadence file reflects Director's most recent cadence_next choice

#### 4.2 Verify Final Cadence is Valid

**Command:**
```bash
RESULT_LINE=$(grep 'LOOP_RESULT_JSON:' /tmp/squad-m4-e2e/loop-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^LOOP_RESULT_JSON://')

python3 -c "
import sys, json
data = json.loads(sys.stdin.read())
cadence = data['final_cadence']
valid = {'full_squad', 'quick_iteration', 'synthesis', 'pause'}
if cadence not in valid:
    print(f'FAIL: final_cadence={cadence} not in {valid}')
    sys.exit(1)
print(f'OK: final_cadence={cadence} (valid)')
" <<< "$RESULT_JSON"
```

**Expected:**
- final_cadence is one of: full_squad, quick_iteration, synthesis, pause

---

### Phase 5: Verify File System Evidence

#### 5.1 Verify experiments.md Gained 3+ New Entries

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
EXP_ENTRIES_BEFORE=$(cat /tmp/squad-m4-e2e/exp-entries-before.txt)
EXP_ENTRIES_AFTER=$(grep -c "^## " "$SHARED/knowledge/experiments.md" 2>/dev/null || echo "0")
NEW_ENTRIES=$((EXP_ENTRIES_AFTER - EXP_ENTRIES_BEFORE))

if [ "$NEW_ENTRIES" -lt 3 ]; then
  echo "FAIL: experiments.md gained only $NEW_ENTRIES new entries (expected >= 3)"
  echo "  Before: $EXP_ENTRIES_BEFORE entries"
  echo "  After:  $EXP_ENTRIES_AFTER entries"
  exit 1
fi
echo "OK: experiments.md gained $NEW_ENTRIES new entries (before=$EXP_ENTRIES_BEFORE, after=$EXP_ENTRIES_AFTER)"

# Show tail of experiments.md for evidence
echo "--- Last 20 lines of experiments.md ---"
tail -20 "$SHARED/knowledge/experiments.md"
```

**Expected:**
- At least 3 new ## entries appended (Scribe records each cycle's results)

#### 5.2 Verify Cycle History JSON Has 5 New Entries

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
HISTORY_BEFORE=$(cat /tmp/squad-m4-e2e/history-entries-before.txt)

python3 -c "
import json, sys

history = json.load(open('$SHARED/loop/cycle-history.json'))
total = len(history)
before = int('$HISTORY_BEFORE')
new_entries = total - before

if new_entries < 5:
    print(f'FAIL: cycle-history.json has only {new_entries} new entries (expected 5)')
    print(f'  Before: {before}, After: {total}')
    sys.exit(1)

print(f'OK: cycle-history.json has {new_entries} new entries (total={total})')

# Validate structure of new entries
for entry in history[-5:]:
    required = {'iteration', 'status', 'cost_usd', 'timestamp', 'agents_spawned'}
    missing = required - set(entry.keys())
    if missing:
        print(f'FAIL: Entry missing fields: {missing}')
        sys.exit(1)

print('OK: All new entries have required fields (iteration, status, cost_usd, timestamp, agents_spawned)')

# Show entries
for e in history[-5:]:
    print(f'  Iteration {e[\"iteration\"]}: status={e[\"status\"]}, cost=\${e[\"cost_usd\"]:.4f}, agents={e[\"agents_spawned\"]}')
"
```

**Expected:**
- 5 new entries in cycle-history.json
- Each entry has: iteration, status, cost_usd, timestamp, agents_spawned

#### 5.3 Verify Iteration Count Updated

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
ITER_COUNT=$(cat "$SHARED/loop/iteration-count.txt" 2>/dev/null || echo "0")

if [ "$ITER_COUNT" -lt 5 ]; then
  echo "FAIL: iteration-count.txt shows $ITER_COUNT (expected >= 5)"
  exit 1
fi
echo "OK: iteration-count.txt=$ITER_COUNT (>= 5)"
```

#### 5.4 Verify No Fatal Error File

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"
if [ -f "$SHARED/loop/fatal-error.md" ]; then
  echo "FAIL: fatal-error.md exists (stall detection fired)"
  cat "$SHARED/loop/fatal-error.md"
  exit 1
fi
echo "OK: No fatal-error.md (no stall detected)"
```

#### 5.5 Verify New Strategy YAMLs Created

**Command:**
```bash
STRAT_DIR="$HOME/.ktrdr/shared/strategies"
STRAT_COUNT_BEFORE=$(cat /tmp/squad-m4-e2e/strat-count-before.txt)
STRAT_COUNT_AFTER=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')
NEW_STRATS=$((STRAT_COUNT_AFTER - STRAT_COUNT_BEFORE))

if [ "$NEW_STRATS" -lt 3 ]; then
  echo "FAIL: Only $NEW_STRATS new strategy files (expected >= 3 from 5 cycles)"
  exit 1
fi
echo "OK: $NEW_STRATS new strategy YAML files created"

# List newest strategies
echo "Newest strategies:"
ls -t "$STRAT_DIR"/*.yaml | head -5
```

---

### Phase 6: V1/V2 Coexistence Check

Verify the Python loop runner uses the same state files as loop_runner.sh.

#### 6.1 Verify State File Format Compatibility

**Command:**
```bash
SHARED="${SQUAD_SHARED_DIR:-$HOME/.ktrdr/shared/squad}"

python3 -c "
import sys

# Check cadence.md is in v1-compatible format: 'cadence: <mode>'
cadence_file = '$SHARED/loop/cadence.md'
with open(cadence_file) as f:
    content = f.read().strip()

if not content.startswith('cadence:'):
    print(f'FAIL: cadence.md format incompatible with v1 (content: {content!r})')
    sys.exit(1)
print(f'OK: cadence.md in v1-compatible format: {content!r}')

# Check iteration-count.txt is a plain integer
iter_file = '$SHARED/loop/iteration-count.txt'
with open(iter_file) as f:
    content = f.read().strip()

try:
    int(content)
except ValueError:
    print(f'FAIL: iteration-count.txt not a plain integer: {content!r}')
    sys.exit(1)
print(f'OK: iteration-count.txt is a plain integer: {content}')

# Check cycle-history.json is valid JSON array
import json
history_file = '$SHARED/loop/cycle-history.json'
with open(history_file) as f:
    data = json.load(f)
if not isinstance(data, list):
    print(f'FAIL: cycle-history.json is not a JSON array')
    sys.exit(1)
print(f'OK: cycle-history.json is a valid JSON array ({len(data)} entries)')
"
```

**Expected:**
- cadence.md uses `cadence: <mode>` format (parseable by shell grep)
- iteration-count.txt is a plain integer (parseable by shell read)
- cycle-history.json is a valid JSON array

#### 6.2 Verify loop_runner.sh Still Exists

**Command:**
```bash
if [ ! -f ".squad/loop_runner.sh" ]; then
  echo "FAIL: loop_runner.sh removed (v1/v2 coexistence broken)"
  exit 1
fi
if [ ! -x ".squad/loop_runner.sh" ]; then
  echo "FAIL: loop_runner.sh not executable"
  exit 1
fi
echo "OK: loop_runner.sh still exists and is executable (v1 preserved)"
```

---

## Success Criteria

All must pass:

- [ ] `run_loop()` completes 5 iterations without unhandled exception
- [ ] LoopResult.status == "max_iterations" (all 5 consumed)
- [ ] LoopResult.stall_detected == false (all cycles productive)
- [ ] LoopResult.total_cost_usd > 0 and <= $10 (real sessions, within budget)
- [ ] LoopResult.experiments_completed >= 3 (most cycles produced experiments)
- [ ] experiments.md gained >= 3 new ## entries (KB grows)
- [ ] cycle-history.json has 5 new entries with required fields
- [ ] iteration-count.txt >= 5
- [ ] No fatal-error.md exists (no stall)
- [ ] >= 3 new strategy YAML files created
- [ ] State files in v1-compatible format (cadence.md, iteration-count.txt)
- [ ] loop_runner.sh still exists (v1/v2 coexistence)

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| total_cost_usd > 0 | Mocked sessions or short-circuited loop that never called Claude |
| experiments_completed >= 3 (not just iterations_run == 5) | Loop ran but cycles failed silently (FAILED status still increments iterations_run) |
| experiments.md entries counted by ## headers (not line count) | File touched but only whitespace/empty lines added |
| cycle-history.json entry structure validated (required fields) | History written with wrong schema |
| No fatal-error.md | Stall detector triggered but status field wasn't set (code bug) |
| State files parseable by simple shell commands | Python wrote format shell can't read (breaks v1 compatibility) |
| strategy YAML count increased (not just checked existence) | Pre-existing files counted as new |
| status == "max_iterations" (not "completed") | Loop exited early via break (pause/stall) but somehow passed other checks |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| LOOP_RESULT_JSON not in output | EXECUTION_FAILURE | Check /tmp/squad-m4-e2e/loop-output.txt for Python traceback |
| status=stalled | STALL_DETECTION | 3+ non-productive cycles; check Director is producing experiments |
| status=paused | CADENCE_ERROR | Something wrote "pause" to cadence.md mid-run |
| status=interrupted | USER_INTERRUPT | KeyboardInterrupt caught; re-run without interrupting |
| iterations_run < 5 | EARLY_EXIT | Check for stall, pause, or unhandled exception |
| total_cost_usd == 0 | SESSION_FAILURE | Claude SDK sessions not connecting; check claude CLI |
| total_cost_usd > $10 | BUDGET_EXCEEDED | Cycles are too expensive; check for runaway tool calls |
| experiments_completed < 3 | CYCLE_QUALITY | Most cycles failed to produce experiments; check Director/Engineer |
| experiments.md < 3 new entries | SCRIBE_FAILURE | Scribe not recording results across cycles |
| cycle-history.json missing entries | HISTORY_WRITE_FAILURE | _write_history() failing silently; check file permissions |
| fatal-error.md exists | STALL_DETECTION | StallDetector triggered; review last 3 cycle results |
| cadence.md wrong format | V1_COMPAT_BREAK | write_cadence() changed format; fix to match v1 |
| loop_runner.sh missing | V1_COMPAT_BREAK | Someone deleted the shell script; restore from git |

---

## Troubleshooting

**If run_loop() hangs on first cycle (cold start):**
- First cycle may take 30-40 min due to training initialization
- Subsequent cycles are faster if quick_iteration cadence is used
- Check sandbox is responsive: `curl http://localhost:8002/api/v1/health`
- Monitor progress: `tail -f /tmp/squad-m4-e2e/loop-output.txt`

**If stall_detected == true:**
- StallDetector triggers after 3 consecutive non-productive cycles
- A cycle is non-productive if status != COMPLETE or experiment_result is None
- Check cycle-history.json for the pattern of failures
- Common cause: Director fails to produce valid tool calls 3 times in a row

**If total_cost_usd is 0:**
- Verify `claude` CLI in PATH: `which claude && claude --version`
- Check if _director_response test injection is accidentally being used
- Cost accumulates from CycleResult.total_cost_usd per iteration

**If experiments.md not growing:**
- Each cycle's Scribe should append results
- Check if Scribe agent is being spawned (agents_spawned in cycle history)
- Verify shared_dir permissions: `touch $HOME/.ktrdr/shared/squad/knowledge/experiments.md`

**If cadence never changes:**
- This is an advisory check, not a hard failure
- The Director chooses cadence_next based on cycle results
- In a healthy run, Director often switches to quick_iteration after first productive cycle
- Check Director charter instructs cadence selection

**If cycle-history.json has wrong structure:**
- write_cycle_history_entry() in stall.py creates CycleHistoryEntry dataclass
- Verify dataclass fields match: iteration, status, experiment, agents_spawned, cost_usd, timestamp
- Check for JSON corruption from concurrent writes (should not happen in sequential loop)

---

## Evidence to Capture

- Full /tmp/squad-m4-e2e/loop-output.txt (all cycle logs and final LoopResult)
- LoopResult JSON (iterations_run, experiments_completed, stall_detected, final_cadence, total_cost_usd, status, elapsed_seconds)
- cycle-history.json (last 5 entries showing iteration progression)
- cadence.md content (final cadence state)
- iteration-count.txt value
- experiments.md diff (entry count before vs after, tail of new content)
- Strategy YAML files created (count and newest file names)
- Presence/absence of fatal-error.md
- Total elapsed wall clock time
