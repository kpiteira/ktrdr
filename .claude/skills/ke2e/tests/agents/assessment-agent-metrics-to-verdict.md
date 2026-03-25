# Test: agents/assessment-agent-metrics-to-verdict

**Purpose:** Validate the full assessment agent flow: POST /assessments/start with strategy metrics and backtest results, Claude Code agentic loop runs inside the container with MCP tools, and a structured assessment with verdict/strengths/weaknesses/suggestions is produced, saved via MCP, and persisted to memory
**Duration:** ~2-4 minutes (Claude Code agentic loop with MCP tool calls)
**Category:** Agents
**Cost:** This test uses REAL Claude Code API credits (typically $0.30-1.50 for an assessment session)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] assessment-agent-1 container is running: `docker ps --format '{{.Names}}' | grep -q assessment-agent`
- [ ] assessment-agent-1 is healthy: `[ -f .env.sandbox ] && source .env.sandbox; curl -sf http://localhost:${KTRDR_ASSESSMENT_AGENT_PORT:-5020}/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('healthy') is True or d.get('status')=='operational', f'Unhealthy: {d}'; print('Assessment agent healthy')"`
- [ ] Claude auth available: named Docker volume `ktrdr-agent-claude-auth` exists (`docker volume inspect ktrdr-agent-claude-auth`) OR `ANTHROPIC_API_KEY` is set in the container
- [ ] assessment-agent-1 registered with backend: `[ -f .env.sandbox ] && source .env.sandbox; API_PORT=${KTRDR_API_PORT:-8000}; curl -s http://localhost:$API_PORT/api/v1/workers | python3 -c "import sys,json; w=json.load(sys.stdin).get('workers',[]); found=[x for x in w if x.get('type')=='agent_assessment']; assert found, 'No agent_assessment worker'; print(f'Assessment agent registered: {found[0].get(\"worker_id\")}')"`
- [ ] Memory directory exists and is writable: `CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'assessment-agent' | head -1); docker exec "$CONTAINER" test -d /app/memory && echo "Memory dir exists" || echo "FAIL: /app/memory missing"`

---

## Test Data

### Strategy Metrics Input

This test provides pre-computed training and backtest metrics. The assessment agent does NOT run training or backtesting -- it evaluates results that are handed to it.

**Why these metrics:**
- Accuracy 0.72 and Sharpe 1.2 are "decent but not great" -- forces the agent to reason about trade-offs rather than giving a trivially positive or negative verdict
- Win rate 0.58 and max drawdown 0.15 provide enough signal for strengths/weaknesses analysis
- 145 trades is sufficient for the agent to consider statistical significance
- Simple enough that assessment completes in reasonable time (fewer turns, lower cost)

### Request Payload

```json
{
  "task_id": "e2e_assessment_test_{TIMESTAMP}",
  "strategy_name": "test_strategy_for_assessment",
  "training_metrics": {
    "accuracy": 0.72,
    "loss": 0.31,
    "epochs": 50
  },
  "backtest_results": {
    "sharpe": 1.2,
    "max_dd": 0.15,
    "total_trades": 145,
    "win_rate": 0.58
  }
}
```

---

## Execution Steps

### 0. Setup: Determine Ports and Clean Previous Test Artifacts

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}
ASSESSMENT_PORT=${KTRDR_ASSESSMENT_AGENT_PORT:-5020}

echo "API port: $API_PORT"
echo "Assessment agent port: $ASSESSMENT_PORT"

# Find the assessment agent container for later verification
AGENT_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'assessment-agent' | head -1)
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)
echo "Assessment agent container: $AGENT_CONTAINER"
echo "Backend container: $BACKEND_CONTAINER"

# Clean up any test assessment files from previous runs
docker exec "$BACKEND_CONTAINER" rm -f /app/strategies/test_strategy_for_assessment_assessment.json 2>/dev/null

# Clean up any test experiment records from previous runs
docker exec "$AGENT_CONTAINER" bash -c 'rm -f /app/memory/experiments/exp_*_test_strategy_for_assessment*.yaml 2>/dev/null' 2>/dev/null

# Record experiment count before test for delta check
EXPERIMENT_COUNT_BEFORE=$(docker exec "$AGENT_CONTAINER" bash -c 'ls /app/memory/experiments/*.yaml 2>/dev/null | wc -l' 2>/dev/null || echo "0")
echo "Experiment records before test: $EXPERIMENT_COUNT_BEFORE"

echo "Setup complete"
```

**Expected:**
- Ports identified from .env.sandbox
- Both containers found
- Previous test artifacts cleaned up
- Baseline experiment count recorded

### 1. Verify Assessment Agent Health and Registration

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}
ASSESSMENT_PORT=${KTRDR_ASSESSMENT_AGENT_PORT:-5020}

echo "=== Assessment Agent Health ==="
HEALTH=$(curl -sf http://localhost:$ASSESSMENT_PORT/health)
echo "$HEALTH" | python3 -m json.tool

echo ""
echo "=== Workers Registry ==="
WORKERS=$(curl -s http://localhost:$API_PORT/api/v1/workers)
echo "$WORKERS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
workers = data.get('workers', [])
for w in workers:
    if w.get('type') == 'agent_assessment':
        print(f'Assessment agent found:')
        print(f'  worker_id: {w.get(\"worker_id\")}')
        print(f'  status: {w.get(\"status\")}')
        print(f'  endpoint: {w.get(\"endpoint_url\")}')
        print(f'  capabilities: {w.get(\"capabilities\", {})}')
        break
else:
    print('FAIL: No agent_assessment worker found in registry')
    print(f'Available workers: {[w.get(\"type\") for w in workers]}')
"
```

**Expected:**
- Health endpoint returns healthy status
- Worker registry contains an `agent_assessment` type worker with status `available` or `idle`

**Capture:** Worker ID, endpoint URL

### 2. Submit Assessment Request

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
ASSESSMENT_PORT=${KTRDR_ASSESSMENT_AGENT_PORT:-5020}
TIMESTAMP=$(date +%s)

# Submit directly to the assessment agent worker
RESPONSE=$(curl -s -X POST "http://localhost:$ASSESSMENT_PORT/assessments/start" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json
print(json.dumps({
    'task_id': f'e2e_assessment_test_{TIMESTAMP}',
    'strategy_name': 'test_strategy_for_assessment',
    'training_metrics': {
        'accuracy': 0.72,
        'loss': 0.31,
        'epochs': 50
    },
    'backtest_results': {
        'sharpe': 1.2,
        'max_dd': 0.15,
        'total_trades': 145,
        'win_rate': 0.58
    }
}))
" 2>/dev/null)")

echo "=== Assessment Start Response ==="
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"

# Extract operation_id
OPERATION_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('operation_id',''))")
echo ""
echo "Operation ID: $OPERATION_ID"

# Verify response structure
echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
success = data.get('success')
status = data.get('status')
op_id = data.get('operation_id')

if success and status == 'started' and op_id:
    print(f'OK: Assessment started (operation_id={op_id})')
else:
    print(f'FAIL: Unexpected response: success={success}, status={status}, operation_id={op_id}')
"
```

**Expected:**
- HTTP 200 with `{"success": true, "operation_id": "e2e_assessment_test_...", "status": "started"}`
- Operation ID matches the task_id we submitted

**Capture:** operation_id for subsequent polling

### 3. Poll Operation Status Until Completion

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# OPERATION_ID from step 2
TIMEOUT=300  # 5 minutes max
POLL_INTERVAL=10
ELAPSED=0
STATUS="running"
POLL_COUNT=0

echo "Polling operation $OPERATION_ID (timeout: ${TIMEOUT}s, interval: ${POLL_INTERVAL}s)"
echo ""

while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    POLL_COUNT=$((POLL_COUNT + 1))

    OP_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")
    STATUS=$(echo "$OP_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('status','unknown'))" 2>/dev/null)

    # Extract progress info if available
    PROGRESS=$(echo "$OP_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', {})
progress = data.get('progress', {})
pct = progress.get('percentage', 'n/a')
step = progress.get('current_step', 'n/a')
print(f'progress={pct}%, step={step}')
" 2>/dev/null)

    echo "[${ELAPSED}s] Poll #${POLL_COUNT}: status=$STATUS $PROGRESS"

    if [ "$STATUS" = "completed" ] || [ "$STATUS" = "failed" ] || [ "$STATUS" = "cancelled" ]; then
        break
    fi

    sleep $POLL_INTERVAL
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

echo ""
echo "=== Final Operation State ==="
echo "$OP_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$OP_RESPONSE"

if [ "$STATUS" = "completed" ]; then
    echo ""
    echo "OK: Operation completed after ${ELAPSED}s (${POLL_COUNT} polls)"
elif [ "$STATUS" = "failed" ]; then
    echo ""
    echo "FAIL: Operation failed"
    echo "$OP_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin).get('data', {})
print(f'Error: {data.get(\"error_message\", \"unknown\")}')
print(f'Result: {data.get(\"result_summary\", {})}')
"
elif [ "$ELAPSED" -ge "$TIMEOUT" ]; then
    echo ""
    echo "FAIL: Timeout after ${TIMEOUT}s (status was: $STATUS)"
else
    echo ""
    echo "FAIL: Unexpected terminal status: $STATUS"
fi
```

**Expected:**
- Operation transitions through `running` to `completed`
- Completes within 5 minutes
- Status never becomes `failed` or `cancelled`

**Capture:** Array of status snapshots with timestamps, final operation state, total duration

### 4. Validate Operation Result Summary (Assessment Fields)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Get the final operation state
OP_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")

echo "$OP_RESPONSE" | python3 -c "
import sys, json

data = json.load(sys.stdin).get('data', {})
result = data.get('result_summary', {})

print('=== Result Summary ===')
verdict = result.get('verdict')
strategy_name = result.get('strategy_name')
strengths = result.get('strengths', [])
weaknesses = result.get('weaknesses', [])
suggestions = result.get('suggestions', [])
hypotheses = result.get('hypotheses', [])
assessment_path = result.get('assessment_path')
cost_usd = result.get('cost_usd', 0)
turns = result.get('turns', 0)
session_id = result.get('session_id')

print(f'verdict: {verdict}')
print(f'strategy_name: {strategy_name}')
print(f'strengths ({len(strengths)}): {strengths}')
print(f'weaknesses ({len(weaknesses)}): {weaknesses}')
print(f'suggestions ({len(suggestions)}): {suggestions}')
print(f'hypotheses ({len(hypotheses)}): {hypotheses}')
print(f'assessment_path: {assessment_path}')
print(f'cost_usd: {cost_usd}')
print(f'turns: {turns}')
print(f'session_id: {session_id}')
print()

# Validate required fields
issues = []

# Verdict validation
valid_verdicts = {'promising', 'neutral', 'poor'}
if not verdict:
    issues.append('FAIL: verdict is empty/missing')
elif verdict not in valid_verdicts:
    issues.append(f'FAIL: verdict \"{verdict}\" not in valid set {valid_verdicts}')
else:
    print(f'OK: verdict is valid ({verdict})')

# Strategy name validation
if not strategy_name:
    issues.append('FAIL: strategy_name is empty/missing')
elif strategy_name != 'test_strategy_for_assessment':
    issues.append(f'WARNING: strategy_name is \"{strategy_name}\", expected \"test_strategy_for_assessment\"')
else:
    print(f'OK: strategy_name matches input ({strategy_name})')

# Strengths validation
if not strengths or len(strengths) == 0:
    issues.append('FAIL: strengths is empty (must have at least one)')
else:
    print(f'OK: {len(strengths)} strength(s) identified')

# Weaknesses validation
if not weaknesses or len(weaknesses) == 0:
    issues.append('FAIL: weaknesses is empty (must have at least one)')
else:
    print(f'OK: {len(weaknesses)} weakness(es) identified')

# Suggestions validation
if not suggestions or len(suggestions) == 0:
    issues.append('FAIL: suggestions is empty (must have at least one)')
else:
    print(f'OK: {len(suggestions)} suggestion(s) provided')

# Assessment path validation
if not assessment_path:
    issues.append('WARNING: assessment_path is empty/missing (MCP tool may not have returned path)')
else:
    print(f'OK: assessment_path present ({assessment_path})')

# Cost tracking
if cost_usd <= 0:
    issues.append(f'WARNING: cost_usd is {cost_usd} (expected > 0)')
else:
    print(f'OK: cost_usd tracked ({cost_usd:.4f})')

# Turns tracking
if turns < 2:
    issues.append(f'FAIL: turns is {turns} (expected >= 2 for assessment loop)')
else:
    print(f'OK: turns tracked ({turns})')

# Session ID
if not session_id:
    issues.append('WARNING: session_id is empty/missing')
else:
    print(f'OK: session_id present ({session_id})')

print()
if issues:
    for issue in issues:
        print(issue)
else:
    print('All result_summary fields valid')
"
```

**Expected:**
- `result_summary.verdict` is one of: "promising", "neutral", "poor"
- `result_summary.strategy_name` matches the input "test_strategy_for_assessment"
- `result_summary.strengths` is a non-empty list
- `result_summary.weaknesses` is a non-empty list
- `result_summary.suggestions` is a non-empty list
- `result_summary.cost_usd` > 0 (real API usage occurred)
- `result_summary.turns` >= 2 (agent reasoned through assessment)
- `result_summary.assessment_path` present (MCP save_assessment tool was called)

**Capture:** verdict, strategy_name, strengths, weaknesses, suggestions, hypotheses, assessment_path, cost_usd, turns, session_id

### 5. Verify Assessment File Saved via MCP

**Command:**
```bash
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)

echo "=== Assessment File Check ==="
docker exec "$BACKEND_CONTAINER" ls -la /app/strategies/test_strategy_for_assessment_assessment.json 2>&1

echo ""
echo "=== Assessment File Content ==="
docker exec "$BACKEND_CONTAINER" cat /app/strategies/test_strategy_for_assessment_assessment.json 2>&1

echo ""
echo "=== Assessment File Validation ==="
docker exec "$BACKEND_CONTAINER" python3 -c "
import json, sys

try:
    with open('/app/strategies/test_strategy_for_assessment_assessment.json') as f:
        assessment = json.load(f)
except FileNotFoundError:
    print('FAIL: Assessment file not found at expected path')
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f'FAIL: Assessment file is not valid JSON: {e}')
    sys.exit(1)

print(f'verdict: {assessment.get(\"verdict\")}')
print(f'strategy_name: {assessment.get(\"strategy_name\")}')
print(f'strengths: {len(assessment.get(\"strengths\", []))} items')
print(f'weaknesses: {len(assessment.get(\"weaknesses\", []))} items')
print(f'suggestions: {len(assessment.get(\"suggestions\", []))} items')
print(f'hypotheses: {len(assessment.get(\"hypotheses\", []))} items')
print(f'timestamp: {assessment.get(\"timestamp\")}')
print()

valid_verdicts = {'promising', 'neutral', 'poor'}
issues = []

if assessment.get('verdict') not in valid_verdicts:
    issues.append(f'FAIL: verdict \"{assessment.get(\"verdict\")}\" not valid')
else:
    print(f'OK: verdict is valid ({assessment[\"verdict\"]})')

if assessment.get('strategy_name') != 'test_strategy_for_assessment':
    issues.append(f'FAIL: strategy_name mismatch: {assessment.get(\"strategy_name\")}')
else:
    print('OK: strategy_name matches')

if not assessment.get('strengths'):
    issues.append('FAIL: strengths is empty')
else:
    print(f'OK: strengths has {len(assessment[\"strengths\"])} items')

if not assessment.get('weaknesses'):
    issues.append('FAIL: weaknesses is empty')
else:
    print(f'OK: weaknesses has {len(assessment[\"weaknesses\"])} items')

if not assessment.get('timestamp'):
    issues.append('FAIL: timestamp missing')
else:
    print(f'OK: timestamp present')

print()
if issues:
    for issue in issues:
        print(issue)
else:
    print('Assessment file is valid')
"
```

**Expected:**
- Assessment JSON file exists at `/app/strategies/test_strategy_for_assessment_assessment.json`
- File is valid JSON
- Contains verdict, strategy_name, strengths, weaknesses, suggestions, timestamp
- verdict is one of the valid values
- strategy_name matches the input

**Capture:** Full assessment JSON content, validation results

### 6. Verify Experiment Record Saved to Memory

**Command:**
```bash
AGENT_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'assessment-agent' | head -1)

echo "=== Memory: Experiment Records ==="

# Count experiments after test
EXPERIMENT_COUNT_AFTER=$(docker exec "$AGENT_CONTAINER" bash -c 'ls /app/memory/experiments/*.yaml 2>/dev/null | wc -l' 2>/dev/null || echo "0")
echo "Experiment records after test: $EXPERIMENT_COUNT_AFTER"
echo "Experiment records before test: $EXPERIMENT_COUNT_BEFORE"

# Check that at least one new experiment was saved
if [ "$EXPERIMENT_COUNT_AFTER" -gt "$EXPERIMENT_COUNT_BEFORE" ]; then
    echo "OK: New experiment record(s) saved (delta: $((EXPERIMENT_COUNT_AFTER - EXPERIMENT_COUNT_BEFORE)))"
else
    echo "WARNING: No new experiment records detected (memory save is best-effort)"
fi

echo ""
echo "=== Most Recent Experiment Record ==="
LATEST_EXP=$(docker exec "$AGENT_CONTAINER" bash -c 'ls -t /app/memory/experiments/*.yaml 2>/dev/null | head -1')
if [ -n "$LATEST_EXP" ]; then
    docker exec "$AGENT_CONTAINER" cat "$LATEST_EXP" 2>&1

    echo ""
    echo "=== Experiment Record Validation ==="
    docker exec "$AGENT_CONTAINER" python3 -c "
import yaml, sys

try:
    with open('$LATEST_EXP') as f:
        exp = yaml.safe_load(f)
except Exception as e:
    print(f'FAIL: Cannot read experiment record: {e}')
    sys.exit(1)

print(f'id: {exp.get(\"id\")}')
print(f'strategy_name: {exp.get(\"strategy_name\")}')
print(f'timestamp: {exp.get(\"timestamp\")}')
print(f'source: {exp.get(\"source\")}')
print(f'status: {exp.get(\"status\")}')
print()

assessment = exp.get('assessment', {})
print(f'assessment.verdict: {assessment.get(\"verdict\")}')
print(f'assessment.observations: {len(assessment.get(\"observations\", []))} items')
print(f'assessment.hypotheses: {len(assessment.get(\"hypotheses\", []))} items')
print(f'assessment.limitations: {len(assessment.get(\"limitations\", []))} items')
print()

results = exp.get('results', {})
print(f'results: {results}')

issues = []
if exp.get('strategy_name') != 'test_strategy_for_assessment':
    issues.append(f'INFO: strategy_name is \"{exp.get(\"strategy_name\")}\" (may differ if agent renamed)')

if exp.get('source') != 'agent':
    issues.append(f'FAIL: source should be \"agent\", got \"{exp.get(\"source\")}\"')
else:
    print('OK: source is \"agent\"')

if not assessment.get('verdict'):
    issues.append('WARNING: assessment.verdict is empty')
else:
    print(f'OK: assessment has verdict ({assessment[\"verdict\"]})')

print()
if issues:
    for issue in issues:
        print(issue)
else:
    print('Experiment record is valid')
" 2>&1
else
    echo "WARNING: No experiment records found (memory save is best-effort, non-blocking)"
fi

echo ""
echo "=== Memory: Hypotheses ==="
docker exec "$AGENT_CONTAINER" bash -c 'cat /app/memory/hypotheses.yaml 2>/dev/null | tail -30' 2>&1 || echo "No hypotheses file found (may be first run)"
```

**Expected:**
- At least one new experiment record exists in `/app/memory/experiments/`
- Record contains strategy_name, assessment with verdict, results (backtest data)
- source field is "agent"
- Hypotheses may or may not be present (depends on agent output)

**Note:** Memory save is best-effort and non-blocking. If memory save fails, the operation still completes successfully. This step is a WARNING-level check, not a hard failure.

**Capture:** Experiment record content, hypotheses file content, experiment count delta

### 7. Verify Agent Used MCP Tools (via Cost and Turns)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

OP_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")

echo "$OP_RESPONSE" | python3 -c "
import sys, json

data = json.load(sys.stdin).get('data', {})
result = data.get('result_summary', {})
created = data.get('created_at', '')
completed = data.get('completed_at', '')
status = data.get('status', '')

turns = result.get('turns', 0)
cost_usd = result.get('cost_usd', 0)

print(f'Status: {status}')
print(f'Created: {created}')
print(f'Completed: {completed}')
print(f'Turns: {turns}')
print(f'Cost: \${cost_usd:.4f}')
print()

# Assessment sessions are typically shorter than design sessions
# (agent receives structured input, produces structured output)
if turns >= 2:
    print(f'OK: Multiple turns ({turns}) indicates real agentic loop')
elif turns > 0:
    print(f'WARNING: Only {turns} turn -- agent may not have completed full workflow')
else:
    print('FAIL: 0 turns -- agent did not run')

# Cost sanity checks
if cost_usd > 0 and cost_usd < 3.0:
    print(f'OK: Cost is reasonable (\${cost_usd:.4f})')
elif cost_usd >= 3.0:
    print(f'WARNING: Cost seems high (\${cost_usd:.4f}) for a single assessment task')
elif cost_usd == 0 and turns > 0:
    print(f'WARNING: turns > 0 but cost_usd = 0 -- cost tracking may not be working')
else:
    print('FAIL: No cost and no turns -- nothing ran')
"
```

**Expected:**
- turns >= 2 (agent analyzes metrics, calls save_assessment)
- cost_usd > 0 and < $3.00 (assessment is lighter than design)
- Both fields indicate real Claude Code execution

**Capture:** turns, cost_usd

### 8. Verify Assessment Content is Specific to Input Metrics

**Command:**
```bash
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)

echo "=== Assessment Specificity Check ==="
docker exec "$BACKEND_CONTAINER" python3 -c "
import json, sys

try:
    with open('/app/strategies/test_strategy_for_assessment_assessment.json') as f:
        assessment = json.load(f)
except FileNotFoundError:
    print('SKIP: Assessment file not found, cannot check specificity')
    sys.exit(0)
except json.JSONDecodeError:
    print('SKIP: Assessment file is not valid JSON')
    sys.exit(0)

# The assessment should reference the actual metrics we provided.
# This catches the case where the agent produces a generic/canned assessment
# without actually analyzing the input data.
all_text = json.dumps(assessment).lower()

input_indicators = {
    'accuracy': ['accuracy', '0.72', '72%', '72 percent'],
    'sharpe': ['sharpe', '1.2'],
    'drawdown': ['drawdown', 'max_dd', '0.15', '15%'],
    'win_rate': ['win rate', 'win_rate', '0.58', '58%'],
    'trades': ['trade', '145'],
}

found_refs = {}
for metric, patterns in input_indicators.items():
    found_refs[metric] = any(p in all_text for p in patterns)

print('Metric references in assessment:')
for metric, found in found_refs.items():
    status = 'OK' if found else 'MISS'
    print(f'  {status}: {metric} referenced = {found}')

ref_count = sum(1 for v in found_refs.values() if v)
total = len(found_refs)

print()
if ref_count >= 3:
    print(f'OK: Assessment references {ref_count}/{total} input metrics (specific to input)')
elif ref_count >= 1:
    print(f'WARNING: Assessment references only {ref_count}/{total} input metrics (may be partially generic)')
else:
    print(f'FAIL: Assessment references 0/{total} input metrics (appears to be generic/canned)')
" 2>&1
```

**Expected:**
- Assessment text references at least 3 of the 5 input metrics (accuracy, sharpe, drawdown, win_rate, trades)
- This confirms the agent actually analyzed the provided metrics rather than producing a generic template

**Capture:** Metric reference counts

### 9. Cleanup

**Command:**
```bash
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)
AGENT_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'assessment-agent' | head -1)

# Clean up test assessment file
docker exec "$BACKEND_CONTAINER" rm -f /app/strategies/test_strategy_for_assessment_assessment.json 2>/dev/null

# Note: We do NOT clean up experiment records -- they are part of the memory
# system and cleaning them could affect other tests or the agent's context.
# The test prefix "test_strategy_for_assessment" makes them identifiable for
# manual cleanup if needed.

echo "Cleanup complete"
```

---

## Success Criteria

All must pass for the test to pass:

- [ ] assessment-agent-1 container is running and healthy (GET /health returns 200)
- [ ] assessment-agent-1 is registered with backend as `agent_assessment` worker type
- [ ] POST /assessments/start returns `{"success": true, "status": "started", "operation_id": "..."}`
- [ ] Operation completes with status `completed` within 5 minutes
- [ ] result_summary contains `verdict` that is one of: "promising", "neutral", "poor"
- [ ] result_summary contains `strategy_name` matching input "test_strategy_for_assessment"
- [ ] result_summary.strengths is a non-empty list
- [ ] result_summary.weaknesses is a non-empty list
- [ ] result_summary.suggestions is a non-empty list
- [ ] result_summary.turns >= 2 (Claude Code actually ran an assessment loop)
- [ ] result_summary.cost_usd > 0 (real API usage confirmed)
- [ ] Assessment JSON file exists at `/app/strategies/test_strategy_for_assessment_assessment.json`
- [ ] Assessment JSON file is valid and contains matching verdict and strategy_name
- [ ] Assessment content references at least 3 of the 5 input metrics (specificity check)

---

## Sanity Checks

**CRITICAL:** These catch false positives -- scenarios where the test "passes" but the system is actually broken.

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Total duration > 15s | <= 15s fails | Assessment was cached/stubbed, not real agentic loop |
| Total duration < 300s | >= 300s fails | Agent hung or entered infinite loop |
| turns >= 2 | < 2 fails | Agent did not complete assessment workflow (analyze + save) |
| turns < 25 | >= 25 fails | Agent entered runaway loop or repeated failed attempts |
| cost_usd > 0 | <= 0 fails | No real Claude Code API usage -- possibly mocked |
| cost_usd < 3.00 | >= 3.00 fails | Cost explosion -- assessment should be lighter than design |
| verdict in valid set | not in set fails | Agent did not produce valid structured output |
| strengths count >= 1 | 0 fails | Empty assessment produced (no analysis) |
| weaknesses count >= 1 | 0 fails | Empty assessment produced (no analysis) |
| metric references >= 3 | < 3 fails | Assessment is generic, not specific to input metrics |
| operation status != "failed" | "failed" status | Agent crashed or could not produce assessment |

**Quick sanity check script:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

OP_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")
echo "$OP_RESPONSE" | python3 -c "
import sys, json

data = json.load(sys.stdin).get('data', {})
result = data.get('result_summary', {})

issues = []

# Status check
status = data.get('status')
if status != 'completed':
    issues.append(f'SANITY FAIL: Status is {status}, not completed')

# Verdict check
verdict = result.get('verdict')
valid_verdicts = {'promising', 'neutral', 'poor'}
if verdict not in valid_verdicts:
    issues.append(f'SANITY FAIL: verdict \"{verdict}\" not in {valid_verdicts}')

# Turns check
turns = result.get('turns', 0)
if turns < 2:
    issues.append(f'SANITY FAIL: Only {turns} turn(s) (expected >= 2)')
if turns >= 25:
    issues.append(f'SANITY FAIL: {turns} turns is excessive (possible runaway)')

# Cost check
cost = result.get('cost_usd', 0)
if cost <= 0:
    issues.append(f'SANITY FAIL: Cost is {cost} (expected > 0)')
if cost >= 3.0:
    issues.append(f'SANITY FAIL: Cost is \${cost:.2f} (expected < \$3.00)')

# Structured output checks
if not result.get('strengths'):
    issues.append('SANITY FAIL: No strengths in result')
if not result.get('weaknesses'):
    issues.append('SANITY FAIL: No weaknesses in result')
if not result.get('suggestions'):
    issues.append('SANITY FAIL: No suggestions in result')

# Strategy name
if result.get('strategy_name') != 'test_strategy_for_assessment':
    issues.append(f'SANITY WARN: strategy_name mismatch: {result.get(\"strategy_name\")}')

if issues:
    for issue in issues:
        print(issue)
else:
    print('All sanity checks passed')
"
```

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| assessment-agent-1 not running | ENVIRONMENT | Run `uv run kinfra sandbox up` or check docker compose config includes assessment-agent-1 |
| assessment-agent-1 not in workers registry | ENVIRONMENT | Check worker startup logs: `docker compose logs assessment-agent-1 --tail 50`; verify KTRDR_API_CLIENT_BASE_URL is correct |
| POST /assessments/start returns 4xx/5xx | CODE_BUG | Check AssessmentStartRequest schema matches payload; check assessment agent logs |
| Operation stuck in "running" (timeout) | CODE_BUG or ENVIRONMENT | Check assessment agent container logs for Claude Code errors; verify auth volume is mounted; check if Claude Code hung on permission prompt |
| Operation fails with "did not call save_assessment" | CODE_BUG | The system prompt may not instruct the agent to use save_assessment; check ASSESSMENT_SYSTEM_PROMPT |
| Operation fails with auth error | ENVIRONMENT | Claude auth volume not provisioned; run `docker exec assessment-agent-1 claude auth status` to check |
| Assessment file not found after completion | CODE_BUG | save_assessment MCP tool may have failed silently; check MCP server logs inside the container |
| Verdict not in valid set | CODE_BUG | System prompt not constraining verdict to valid values; or save_assessment validation not enforcing |
| Generic assessment (no metric references) | CODE_BUG | User prompt not passing metrics correctly; or system prompt not instructing agent to reference specific metrics |
| cost_usd is 0 but turns > 0 | TEST_ISSUE | SDK may not report cost for all auth methods; check if using API key vs OAuth |
| Excessive cost (> $3) | CONFIGURATION | KTRDR_AGENT_MAX_BUDGET or KTRDR_AGENT_MAX_TURNS too high; or model set to opus instead of sonnet |
| Memory save failed (no new experiment record) | CODE_BUG (soft) | Check memory module; _save_memory is best-effort, so this is a warning not a hard failure |

---

## Cleanup

```bash
BACKEND_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)
docker exec "$BACKEND_CONTAINER" rm -f /app/strategies/test_strategy_for_assessment_assessment.json 2>/dev/null
echo "Cleanup complete"
```

No other state requires cleanup. Operations are persisted by the backend and do not need explicit cleanup. Experiment records in memory are left in place intentionally.

---

## Evidence to Capture

- Assessment agent health response
- Worker registry entry for agent_assessment worker
- POST /assessments/start response (operation_id)
- All poll snapshots (status progression over time)
- Final operation state (full JSON)
- result_summary fields: verdict, strategy_name, strengths, weaknesses, suggestions, hypotheses, assessment_path, cost_usd, turns, session_id
- Assessment JSON file content (from /app/strategies/)
- Experiment record content (from /app/memory/experiments/)
- Metric specificity check results
- Assessment agent container logs (last 50 lines): `docker compose logs assessment-agent-1 --tail 50`
- Total wall-clock duration

---

## Notes for Implementation

- **This test costs real money.** Each invocation uses Claude Code API credits. Typical cost for an assessment session is $0.30-1.50 (lower than design because input is structured, not exploratory). Do NOT run this test in rapid succession.
- **The assessment agent runs inside a container.** It is a long-running service defined in docker-compose.sandbox.yml (`assessment-agent-1`). The test interacts with it via its HTTP API (POST /assessments/start on port 5020).
- **Polling is against the backend, not the worker.** The operation status is tracked by the backend's OperationsService. Poll `GET /api/v1/operations/{id}` on the backend API port, not the assessment agent port.
- **The task_id becomes the operation_id.** The AssessmentStartRequest.task_id is used as the operation_id by the worker. This means we control the operation_id format.
- **Assessment input is deterministic; output is not.** We provide fixed metrics, but the agent's analysis, verdict, and strengths/weaknesses will vary between runs. The test validates structure and specificity, not exact content.
- **Verdict must be one of three values.** The save_assessment MCP tool validates that verdict is "promising", "neutral", or "poor". If the agent provides a different verdict, the MCP tool will reject it and the agent should retry.
- **Memory save is best-effort.** The `_save_memory()` method in the worker catches all exceptions and logs warnings. The operation still completes successfully even if memory persistence fails. Step 6 is a soft check (WARNING level, not FAIL).
- **Assessment file saved to strategies/ directory.** The save_assessment MCP tool saves the JSON file as `{strategy_name}_assessment.json` in the strategies directory (shared volume between backend and agents). Both the backend container and the assessment agent container can see it.
- **The specificity check (Step 8) catches canned responses.** A key risk is the agent producing a generic "this strategy looks good/bad" without referencing the actual metrics. The specificity check ensures the assessment text mentions at least 3 of the 5 input metrics.
- **Lower turn threshold than design agent.** Assessment typically needs fewer turns than design (2+ vs 3+) because it receives structured input and produces structured output. The agent reads metrics, reasons, and calls save_assessment.
- **Timeout of 5 minutes matches the design agent test.** Assessment sessions are typically faster (1-2 minutes), but we allow 5 minutes for slow API responses or retries.
