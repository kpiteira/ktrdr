# Test: squad/m1-conversational-first-cycle

**Purpose:** Validate one complete ORIENT - WORK - LEARN cycle via the Python orchestrator (`run_cycle()` in `.squad/squad_engine/loop.py`). The Director (LLM session) reads KB state, spawns an Engineer to design a strategy, validates the YAML, executes training+backtest via executor.sh, then spawns a Scribe to record results.

**Duration:** ~20-40 minutes (dominated by training + backtest execution time)

**Category:** Squad / Conversational Orchestrator / M1

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox (slot 3, port 8003), API health

**Test-specific checks:**

- [ ] Sandbox running on slot 3 (port 8003)

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

- [ ] Executor script exists and is executable

```bash
if [ ! -x ".squad/executor.sh" ]; then
  echo "FAIL: .squad/executor.sh not found or not executable"
  exit 1
fi
echo "OK: executor.sh exists and is executable"
```

- [ ] Agent charters present for Director, Engineer, Scribe (minimum for M1)

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
echo "OK: Director, Engineer, and Scribe charters present"
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

---

## Execution Steps

### Phase 1: Snapshot Pre-Cycle State

Capture state before the cycle runs to verify actual changes afterward.

#### 1.1 Record Baseline File State

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

# Save these for Phase 3 comparison
echo "$STRAT_COUNT_BEFORE" > /tmp/squad-e2e-strat-count-before.txt
echo "$EXP_LINES_BEFORE" > /tmp/squad-e2e-exp-lines-before.txt
```

**Expected:**
- Baseline values captured (any non-negative integers)
- Exit code: 0

---

### Phase 2: Run the Cycle

Invoke `run_cycle()` and capture the CycleResult.

#### 2.1 Execute run_cycle via Python

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr-impl-research-squad-v2-M1

# Source sandbox env so executor.sh picks up the correct port
source .env.sandbox

uv run python3 -c "
import asyncio
import json
import sys
from pathlib import Path

# Add squad_engine to path
sys.path.insert(0, str(Path('.squad')))

from squad_engine.loop import run_cycle

async def main():
    result = await run_cycle(
        iteration=99,  # Use a distinctive number to identify this test cycle
        shared_dir=str(Path.home() / '.ktrdr/shared/squad'),
        charter_dir=str(Path('.squad/agents')),
    )

    # Serialize CycleResult to JSON for assertion
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
" 2>&1 | tee /tmp/squad-e2e-cycle-output.txt
```

**Expected:**
- Output contains `CYCLE_RESULT_JSON:` followed by valid JSON
- Exit code: 0 (no unhandled exceptions)
- Duration: 10-40 minutes (training + backtest dominate)

**Important:** This step calls real Claude Code sessions (Director, Engineer, Scribe). The Director outputs JSON tool calls that Python dispatches. Training and backtest run against the live sandbox.

---

### Phase 3: Validate CycleResult

Parse the CycleResult JSON and verify all success criteria.

#### 3.1 Verify Status is COMPLETE

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-e2e-cycle-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

STATUS=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")

if [ "$STATUS" != "COMPLETE" ]; then
  ERROR=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error', 'no error field'))")
  echo "FAIL: CycleResult.status='$STATUS' (expected COMPLETE), error: $ERROR"
  exit 1
fi
echo "OK: CycleResult.status=COMPLETE"
```

**Expected:**
- Output: "OK: CycleResult.status=COMPLETE"

#### 3.2 Verify Agents Spawned Include Engineer and Scribe

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-e2e-cycle-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

AGENTS=$(echo "$RESULT_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
agents = data.get('agents_spawned', [])
print(','.join(agents))
missing = []
if 'engineer' not in agents:
    missing.append('engineer')
if 'scribe' not in agents:
    missing.append('scribe')
if missing:
    print('MISSING:' + ','.join(missing))
    sys.exit(1)
")

if [ $? -ne 0 ]; then
  echo "FAIL: Missing required agents. Spawned: $AGENTS"
  exit 1
fi
echo "OK: Agents spawned include engineer and scribe: $AGENTS"
```

**Expected:**
- Output confirms both "engineer" and "scribe" in agents_spawned

#### 3.3 Verify Total Cost Greater Than Zero

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-e2e-cycle-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

COST=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin)['total_cost_usd'])")

COST_OK=$(python3 -c "print('yes' if float('$COST') > 0 else 'no')")
if [ "$COST_OK" != "yes" ]; then
  echo "FAIL: total_cost_usd=$COST (expected > 0 -- proves real Claude sessions ran)"
  exit 1
fi
echo "OK: total_cost_usd=$COST (real Claude sessions confirmed)"
```

**Expected:**
- Cost > 0 (proves real Claude Code sessions were created, not short-circuited)

#### 3.4 Verify Experiment Result Present

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-e2e-cycle-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

python3 -c "
import sys, json
data = json.load(sys.stdin)
exp = data.get('experiment_result')
if exp is None:
    print('FAIL: experiment_result is None (no experiment was executed)')
    sys.exit(1)
status = exp.get('status', 'unknown')
if status != 'SUCCESS':
    error = exp.get('error', 'no error')
    print(f'FAIL: experiment status={status}, error={error}')
    sys.exit(1)
print(f'OK: experiment_result.status=SUCCESS')

# Show training and backtest summaries
training = exp.get('training', {})
backtest = exp.get('backtest', {})
print(f'  Training: {json.dumps(training)[:200]}...')
print(f'  Backtest: {json.dumps(backtest)[:200]}...')
" <<< "$RESULT_JSON"
```

**Expected:**
- experiment_result is not None
- experiment_result.status is "SUCCESS"

#### 3.5 Verify No Unhandled Exception (error field is None)

**Command:**
```bash
RESULT_LINE=$(grep 'CYCLE_RESULT_JSON:' /tmp/squad-e2e-cycle-output.txt | tail -1)
RESULT_JSON=$(echo "$RESULT_LINE" | sed 's/^CYCLE_RESULT_JSON://')

ERROR=$(echo "$RESULT_JSON" | python3 -c "import sys, json; print(json.load(sys.stdin).get('error'))")

if [ "$ERROR" != "None" ]; then
  echo "FAIL: CycleResult.error='$ERROR' (expected None)"
  exit 1
fi
echo "OK: No unhandled exceptions (error=None)"
```

---

### Phase 4: Verify Side Effects (File System Evidence)

#### 4.1 Verify New Strategy YAML Created

**Command:**
```bash
STRAT_DIR="$HOME/.ktrdr/shared/strategies"
STRAT_COUNT_BEFORE=$(cat /tmp/squad-e2e-strat-count-before.txt)
STRAT_COUNT_AFTER=$(ls "$STRAT_DIR"/*.yaml 2>/dev/null | wc -l | tr -d ' ')

if [ "$STRAT_COUNT_AFTER" -le "$STRAT_COUNT_BEFORE" ]; then
  echo "FAIL: No new strategy YAML created (before=$STRAT_COUNT_BEFORE, after=$STRAT_COUNT_AFTER)"
  echo "Contents of $STRAT_DIR:"
  ls -la "$STRAT_DIR"/*.yaml 2>/dev/null
  exit 1
fi
echo "OK: New strategy YAML created (before=$STRAT_COUNT_BEFORE, after=$STRAT_COUNT_AFTER)"

# Show the newest strategy file
NEWEST=$(ls -t "$STRAT_DIR"/*.yaml | head -1)
echo "  Newest strategy: $NEWEST"
echo "  First 5 lines:"
head -5 "$NEWEST"
```

**Expected:**
- Strategy count increased by at least 1
- New YAML file is valid (has content)

#### 4.2 Verify experiments.md Was Modified

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
EXP_LINES_BEFORE=$(cat /tmp/squad-e2e-exp-lines-before.txt)
EXP_LINES_AFTER=$(wc -l < "$SHARED/knowledge/experiments.md" | tr -d ' ')

if [ "$EXP_LINES_AFTER" -le "$EXP_LINES_BEFORE" ]; then
  echo "FAIL: experiments.md not modified (before=$EXP_LINES_BEFORE lines, after=$EXP_LINES_AFTER lines)"
  exit 1
fi
echo "OK: experiments.md updated (before=$EXP_LINES_BEFORE, after=$EXP_LINES_AFTER lines)"
```

**Expected:**
- experiments.md has more lines after the cycle (Scribe appended results)

---

## Success Criteria

All must pass:

- [ ] `run_cycle()` completes without unhandled exception (error=None)
- [ ] CycleResult.status == "COMPLETE"
- [ ] CycleResult.agents_spawned includes "engineer" and "scribe"
- [ ] CycleResult.total_cost_usd > 0 (real Claude sessions ran)
- [ ] CycleResult.experiment_result is not None and status == "SUCCESS"
- [ ] A new strategy YAML file was created in ~/.ktrdr/shared/strategies/
- [ ] experiments.md was modified (new content appended by Scribe)

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| total_cost_usd > 0 | Mocked or short-circuited sessions that never called Claude |
| experiment_result.status == "SUCCESS" | Engineer produced YAML but training/backtest never ran |
| agents_spawned includes both engineer AND scribe | Director only spawned one agent (incomplete cycle) |
| experiments.md grew in line count (not just modified date) | File was touched but not actually written to |
| Strategy YAML count increased (not just checked for existence) | Pre-existing strategy file counted as new |
| error field is None (not just status==COMPLETE) | Status set to COMPLETE in finally block despite caught exception |
| Experiment has both training and backtest fields | Training ran but backtest was skipped |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| CYCLE_RESULT_JSON not found in output | EXECUTION_FAILURE | Check /tmp/squad-e2e-cycle-output.txt for Python traceback |
| status=FAILED with error | ORCHESTRATION_FAILURE | Read error field -- Director may have failed to produce tool calls |
| Missing engineer in agents_spawned | DIRECTOR_FAILURE | Director did not spawn engineer -- check charter prompt |
| Missing scribe in agents_spawned | DIRECTOR_FAILURE | Director skipped LEARN phase -- check tool call parsing |
| total_cost_usd == 0 | SESSION_FAILURE | Claude SDK sessions may not have connected -- check claude CLI |
| experiment_result is None | ENGINEER_FAILURE | Engineer did not produce a strategy or Director skipped execute_experiment |
| experiment_result.status != SUCCESS | EXECUTION_FAILURE | Training or backtest failed -- check executor.sh output |
| No new strategy YAML | ENGINEER_FAILURE | Engineer output was not a valid strategy or write path wrong |
| experiments.md not modified | SCRIBE_FAILURE | Scribe did not update knowledge base |
| Sandbox health check fails | INFRASTRUCTURE | Run `uv run kinfra sandbox up` to start sandbox |
| claude CLI not found | INFRASTRUCTURE | Install Claude Code CLI or add to PATH |

---

## Troubleshooting

**If run_cycle() hangs indefinitely:**
- The Claude SDK connect() hangs if you pass a prompt argument -- this is handled in session.py but verify no regression
- CLAUDECODE env var must be removed during session to prevent nested blocking -- session.py handles this
- Check if sandbox backend is responding: `curl http://localhost:8003/api/v1/health`
- Safety limit: max 20 tool calls per Director session prevents infinite loops

**If experiment_result.status is FAILED:**
- Check executor.sh can run standalone: `.squad/executor.sh ~/.ktrdr/shared/strategies/STRATEGY_NAME.yaml`
- Verify training worker is available: `curl http://localhost:8003/api/v1/workers | jq`
- Training stall detection: executor.sh aborts after 15 min with no progress change

**If total_cost_usd is 0:**
- Verify `claude` CLI is in PATH and working: `which claude && claude --version`
- Check if claude_agent_sdk can be imported: `uv run python3 -c "import claude_agent_sdk; print('OK')"`
- The _director_response test injection path bypasses real sessions -- ensure it is not accidentally used

**If experiments.md is not modified:**
- The Scribe agent may have failed silently -- check /tmp/squad-e2e-cycle-output.txt for Scribe-related errors
- Verify Scribe charter exists: `cat .squad/agents/scribe/charter.md | head -5`
- Check if shared dir is writable: `touch $HOME/.ktrdr/shared/squad/knowledge/experiments.md`

**If Director fails to produce valid tool calls:**
- Tool call extraction uses regex: `\{[^{}]*"tool"\s*:\s*"[^"]+?"[^{}]*\}`
- This does not handle nested JSON -- if Director wraps tool calls in larger JSON objects, parsing fails
- Check Director charter instructs it to output flat JSON tool call blocks

---

## Evidence to Capture

- Full /tmp/squad-e2e-cycle-output.txt (contains all session logs and CycleResult)
- CycleResult JSON (status, agents_spawned, cost, experiment_result, error, duration)
- Strategy YAML file path and first 20 lines
- experiments.md diff (before vs after line count, tail of new content)
- Sandbox health check response
- Duration of the full cycle in seconds
