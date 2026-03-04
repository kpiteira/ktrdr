# Test: agents/design-agent-brief-to-strategy

**Purpose:** Validate the full design agent flow: POST /designs/start with a research brief, Claude Code agentic loop runs inside the container with MCP tools, and a valid v3 strategy is produced and saved
**Duration:** ~3-5 minutes (Claude Code agentic loop with multiple MCP tool calls)
**Category:** Agents
**Cost:** This test uses REAL Claude Code API credits (typically $0.50-2.00 for a multi-turn design session)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] design-agent-1 container is running: `docker ps --format '{{.Names}}' | grep -q design-agent`
- [ ] design-agent-1 is healthy: `[ -f .env.sandbox ] && source .env.sandbox; curl -sf http://localhost:${KTRDR_DESIGN_AGENT_PORT:-5010}/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok', f'Unhealthy: {d}'; print('Design agent healthy')"`
- [ ] Claude auth available: named Docker volume `ktrdr-agent-claude-auth` exists (`docker volume inspect ktrdr-agent-claude-auth`) OR `ANTHROPIC_API_KEY` is set in the container
- [ ] design-agent-1 registered with backend: `[ -f .env.sandbox ] && source .env.sandbox; API_PORT=${KTRDR_API_PORT:-8000}; curl -s http://localhost:$API_PORT/api/v1/workers | python3 -c "import sys,json; w=json.load(sys.stdin).get('workers',[]); found=[x for x in w if x.get('type')=='agent_design']; assert found, 'No agent_design worker'; print(f'Design agent registered: {found[0].get(\"worker_id\")}')"`
- [ ] EURUSD data available (needed for indicator discovery): `[ -f .env.sandbox ] && source .env.sandbox; API_PORT=${KTRDR_API_PORT:-8000}; curl -sf http://localhost:$API_PORT/api/v1/data/status/EURUSD/1h | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'EURUSD 1h data: {d}')"`

---

## Test Data

### Research Brief

```
Design a simple mean-reversion strategy for EURUSD on the 1h timeframe.

Requirements:
- Use RSI as the primary momentum indicator
- Use Bollinger Bands for volatility context
- Keep the design simple: 2-3 indicators maximum
- Use a classification model with a single hidden layer

The strategy should detect oversold conditions (RSI low + price near lower Bollinger Band) as buy signals and overbought conditions as sell signals.
```

**Why this brief:**
- Simple enough to complete in reasonable time (fewer turns, lower cost)
- Specific enough that Claude can produce a strategy without excessive exploration
- Uses well-known indicators that exist in the KTRDR indicator registry
- EURUSD/1h is the standard test pair used throughout the codebase
- Requests a small model to keep the strategy minimal

### Request Payload

```json
{
  "task_id": "e2e_design_test_{TIMESTAMP}",
  "brief": "<brief text above>",
  "symbol": "EURUSD",
  "timeframe": "1h",
  "experiment_context": null
}
```

---

## Execution Steps

### 0. Setup: Determine Ports and Clean Previous Test Artifacts

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}
DESIGN_PORT=${KTRDR_DESIGN_AGENT_PORT:-5010}

echo "API port: $API_PORT"
echo "Design agent port: $DESIGN_PORT"

# Find the backend container for later strategy file verification
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)
echo "Backend container: $CONTAINER"

# Clean up any test strategy from previous runs
docker exec "$CONTAINER" rm -f /app/strategies/e2e_design_test_*.yaml 2>/dev/null
docker exec "$CONTAINER" rm -f /app/strategies/e2e_design_test_*_assessment.json 2>/dev/null

echo "Setup complete"
```

**Expected:**
- Ports identified from .env.sandbox
- Backend container found
- Previous test artifacts cleaned up

### 1. Verify Design Agent Health and Registration

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}
DESIGN_PORT=${KTRDR_DESIGN_AGENT_PORT:-5010}

echo "=== Design Agent Health ==="
HEALTH=$(curl -sf http://localhost:$DESIGN_PORT/health)
echo "$HEALTH" | python3 -m json.tool

echo ""
echo "=== Workers Registry ==="
WORKERS=$(curl -s http://localhost:$API_PORT/api/v1/workers)
echo "$WORKERS" | python3 -c "
import sys, json
data = json.load(sys.stdin)
workers = data.get('workers', [])
for w in workers:
    if w.get('type') == 'agent_design':
        print(f'Design agent found:')
        print(f'  worker_id: {w.get(\"worker_id\")}')
        print(f'  status: {w.get(\"status\")}')
        print(f'  endpoint: {w.get(\"endpoint_url\")}')
        print(f'  capabilities: {w.get(\"capabilities\", {})}')
        break
else:
    print('FAIL: No agent_design worker found in registry')
    print(f'Available workers: {[w.get(\"type\") for w in workers]}')
"
```

**Expected:**
- Health endpoint returns `{"status": "ok"}`
- Worker registry contains an `agent_design` type worker with status `available` or `idle`

**Capture:** Worker ID, endpoint URL

### 2. Submit Design Request

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
DESIGN_PORT=${KTRDR_DESIGN_AGENT_PORT:-5010}
TIMESTAMP=$(date +%s)

BRIEF="Design a simple mean-reversion strategy for EURUSD on the 1h timeframe.

Requirements:
- Use RSI as the primary momentum indicator
- Use Bollinger Bands for volatility context
- Keep the design simple: 2-3 indicators maximum
- Use a classification model with a single hidden layer

The strategy should detect oversold conditions (RSI low + price near lower Bollinger Band) as buy signals and overbought conditions as sell signals."

# Submit directly to the design agent worker
RESPONSE=$(curl -s -X POST "http://localhost:$DESIGN_PORT/designs/start" \
  -H "Content-Type: application/json" \
  -d "$(python3 -c "
import json
print(json.dumps({
    'task_id': 'e2e_design_test_${TIMESTAMP}',
    'brief': '''$BRIEF'''.strip(),
    'symbol': 'EURUSD',
    'timeframe': '1h',
    'experiment_context': None
}))
")")

echo "=== Design Start Response ==="
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
    print(f'OK: Design started (operation_id={op_id})')
else:
    print(f'FAIL: Unexpected response: success={success}, status={status}, operation_id={op_id}')
"
```

**Expected:**
- HTTP 200 with `{"success": true, "operation_id": "e2e_design_test_...", "status": "started"}`
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

### 4. Validate Operation Result Summary

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
strategy_name = result.get('strategy_name')
strategy_path = result.get('strategy_path')
cost_usd = result.get('cost_usd', 0)
turns = result.get('turns', 0)
session_id = result.get('session_id')

print(f'strategy_name: {strategy_name}')
print(f'strategy_path: {strategy_path}')
print(f'cost_usd: {cost_usd}')
print(f'turns: {turns}')
print(f'session_id: {session_id}')
print()

# Validate required fields
issues = []
if not strategy_name:
    issues.append('FAIL: strategy_name is empty/missing')
else:
    print(f'OK: strategy_name present ({strategy_name})')

if not strategy_path:
    issues.append('FAIL: strategy_path is empty/missing')
else:
    print(f'OK: strategy_path present ({strategy_path})')

if cost_usd <= 0:
    issues.append(f'WARNING: cost_usd is {cost_usd} (expected > 0)')
else:
    print(f'OK: cost_usd tracked ({cost_usd:.4f})')

if turns <= 0:
    issues.append(f'FAIL: turns is {turns} (expected > 0)')
else:
    print(f'OK: turns tracked ({turns})')

print()
if issues:
    for issue in issues:
        print(issue)
else:
    print('All result_summary fields valid')
"
```

**Expected:**
- `result_summary.strategy_name` is non-empty
- `result_summary.strategy_path` points to a `.yaml` file
- `result_summary.cost_usd` > 0 (real API usage occurred)
- `result_summary.turns` > 0 (multiple turns completed)

**Capture:** strategy_name, strategy_path, cost_usd, turns

### 5. Read and Validate Strategy File

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)

# Get the strategy_name from the operation result
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

OP_RESPONSE=$(curl -s "http://localhost:$API_PORT/api/v1/operations/$OPERATION_ID")
STRATEGY_NAME=$(echo "$OP_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('result_summary',{}).get('strategy_name',''))")
STRATEGY_PATH=$(echo "$OP_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('result_summary',{}).get('strategy_path',''))")

echo "Strategy name: $STRATEGY_NAME"
echo "Strategy path: $STRATEGY_PATH"
echo ""

# Check file exists in the backend container (strategies are on a shared volume)
echo "=== File Check ==="
docker exec "$CONTAINER" ls -la "/app/strategies/${STRATEGY_NAME}.yaml" 2>&1

echo ""
echo "=== Strategy Content ==="
docker exec "$CONTAINER" cat "/app/strategies/${STRATEGY_NAME}.yaml" 2>&1

echo ""
echo "=== V3 Format Validation ==="
docker exec "$CONTAINER" python3 -c "
import yaml, sys

try:
    with open('/app/strategies/${STRATEGY_NAME}.yaml') as f:
        config = yaml.safe_load(f)
except FileNotFoundError:
    print('FAIL: Strategy file not found')
    sys.exit(1)

print(f'name: {config.get(\"name\")}')
print(f'version: {config.get(\"version\")}')
print()

# V3 required sections
required_sections = ['training_data', 'indicators', 'fuzzy_sets', 'nn_inputs', 'model', 'decisions', 'training']
for section in required_sections:
    present = section in config
    status = 'OK' if present else 'FAIL'
    print(f'{status}: {section} {\"present\" if present else \"MISSING\"}')

# Check indicators
indicators = config.get('indicators', {})
print(f'\\nIndicators ({len(indicators)}):')
for name, spec in indicators.items():
    print(f'  - {name}: type={spec.get(\"type\")}, params={dict((k,v) for k,v in spec.items() if k != \"type\")}')

# Check fuzzy_sets reference indicators
fuzzy_sets = config.get('fuzzy_sets', {})
print(f'\\nFuzzy sets ({len(fuzzy_sets)}):')
for name, spec in fuzzy_sets.items():
    ind_ref = spec.get('indicator', 'MISSING')
    valid_ref = ind_ref in indicators
    status = 'OK' if valid_ref else 'WARN'
    print(f'  - {name}: indicator={ind_ref} ({status})')

# Check nn_inputs reference fuzzy_sets
nn_inputs = config.get('nn_inputs', [])
print(f'\\nNN inputs ({len(nn_inputs)}):')
for inp in nn_inputs:
    fs_ref = inp.get('fuzzy_set', 'MISSING')
    valid_ref = fs_ref in fuzzy_sets
    status = 'OK' if valid_ref else 'WARN'
    print(f'  - fuzzy_set={fs_ref} ({status}), timeframes={inp.get(\"timeframes\")}')

# Check version is 3.0
version = str(config.get('version', ''))
if version == '3.0':
    print('\\nOK: Valid v3 strategy format')
else:
    print(f'\\nFAIL: Expected version 3.0, got {version}')

# Check that training_data specifies EURUSD
symbols = config.get('training_data', {}).get('symbols', {}).get('list', [])
if 'EURUSD' in symbols:
    print('OK: EURUSD in training_data.symbols')
else:
    print(f'WARN: Expected EURUSD in symbols, got {symbols}')
"
```

**Expected:**
- Strategy file exists at the returned path
- YAML is parseable
- Contains all required v3 sections: training_data, indicators, fuzzy_sets, nn_inputs, model, decisions, training
- version is "3.0"
- Indicators reference real indicator types (rsi, bollinger_bands, etc.)
- Fuzzy sets reference declared indicators
- NN inputs reference declared fuzzy sets
- training_data includes EURUSD

**Capture:** Full strategy YAML content, validation results

### 6. Verify Agent Used MCP Tools (via Cost and Turns)

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

# A real design session should have multiple turns
# (discover indicators, design strategy, validate, save)
if turns >= 3:
    print(f'OK: Multiple turns ({turns}) indicates real agentic loop')
elif turns > 0:
    print(f'WARNING: Only {turns} turn(s) -- agent may not have completed full workflow')
else:
    print('FAIL: 0 turns -- agent did not run')

# Cost sanity checks
if cost_usd > 0 and cost_usd < 5.0:
    print(f'OK: Cost is reasonable (\${cost_usd:.4f})')
elif cost_usd >= 5.0:
    print(f'WARNING: Cost seems high (\${cost_usd:.4f}) for a single design task')
elif cost_usd == 0 and turns > 0:
    print(f'WARNING: turns > 0 but cost_usd = 0 -- cost tracking may not be working')
else:
    print('FAIL: No cost and no turns -- nothing ran')
"
```

**Expected:**
- turns >= 3 (agent goes through discover, design, validate, save phases)
- cost_usd > 0 and < $5.00
- Both fields indicate real Claude Code execution

**Capture:** turns, cost_usd

### 7. Verify Strategy via get_recent_strategies MCP Tool (Optional Cross-Check)

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)

INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
RECENT_MSG='{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"get_recent_strategies","arguments":{"limit":5}}}'

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$RECENT_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

RECENT_RESPONSE=$(echo "$RESPONSES" | grep '"id":2' | head -1)
echo "=== Recent Strategies ==="
echo "$RECENT_RESPONSE" | python3 -c "
import sys, json

data = json.load(sys.stdin)
result = data.get('result', {})
content = result.get('content', [])
if content and isinstance(content, list):
    text = content[0].get('text', '[]')
    strategies = json.loads(text)
else:
    strategies = result if isinstance(result, list) else []

print(f'Strategies returned: {len(strategies)}')
found = False
for s in strategies:
    name = s.get('name', 'unknown')
    indicators = s.get('indicators', [])
    print(f'  - {name}: indicators={indicators}')
    if name.startswith('e2e_design_test_') or '${STRATEGY_NAME}' in name or name == '${STRATEGY_NAME}':
        found = True
        print(f'    ** This is our test strategy')

if found:
    print('\\nOK: Test strategy visible in recent strategies')
else:
    print('\\nWARNING: Test strategy not found in recent list (may have different name)')
    print('This is not a hard failure -- the agent may have chosen a different strategy name')
"
```

**Expected:**
- Recent strategies list includes the strategy produced by the agent
- Cross-confirms that save_strategy_config MCP tool was called successfully

### 8. Cleanup

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)

# Clean up test strategy files
# Use the strategy name from the operation result
docker exec "$CONTAINER" bash -c 'rm -f /app/strategies/e2e_design_test_*.yaml /app/strategies/e2e_design_test_*_assessment.json' 2>/dev/null

echo "Cleanup complete"
```

---

## Success Criteria

All must pass for the test to pass:

- [ ] design-agent-1 container is running and healthy (GET /health returns 200)
- [ ] design-agent-1 is registered with backend as `agent_design` worker type
- [ ] POST /designs/start returns `{"success": true, "status": "started", "operation_id": "..."}`
- [ ] Operation completes with status `completed` within 5 minutes
- [ ] result_summary contains non-empty `strategy_name`
- [ ] result_summary contains non-empty `strategy_path`
- [ ] result_summary.turns > 0 (Claude Code actually ran)
- [ ] result_summary.cost_usd > 0 (real API usage confirmed)
- [ ] Strategy file exists at the returned path inside the container
- [ ] Strategy file is valid YAML with v3 format (version: "3.0")
- [ ] Strategy contains required sections: indicators, fuzzy_sets, nn_inputs, model, training_data
- [ ] Fuzzy sets reference declared indicators (no dangling refs)
- [ ] NN inputs reference declared fuzzy sets (no dangling refs)

---

## Sanity Checks

**CRITICAL:** These catch false positives -- scenarios where the test "passes" but the system is actually broken.

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Total duration > 30s | <= 30s fails | Design was cached/stubbed, not real agentic loop |
| Total duration < 300s | >= 300s fails | Agent hung or entered infinite loop |
| turns >= 3 | < 3 fails | Agent did not complete full workflow (discover, design, validate, save) |
| turns < 30 | >= 30 fails | Agent entered runaway loop or repeated failed attempts |
| cost_usd > 0 | <= 0 fails | No real Claude Code API usage -- possibly mocked |
| cost_usd < 5.00 | >= 5.00 fails | Cost explosion -- too many turns or wrong model |
| indicators count >= 1 | 0 fails | Empty strategy produced (no indicators) |
| indicators count <= 10 | > 10 fails | Agent over-designed (brief asks for 2-3 indicators) |
| strategy version == "3.0" | != "3.0" fails | Wrong strategy format version |
| strategy has nn_inputs | missing fails | v3 requires nn_inputs section, agent may have produced v2 |
| operation status != "failed" | "failed" status | Agent crashed or could not produce strategy |

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

# Turns check
turns = result.get('turns', 0)
if turns < 3:
    issues.append(f'SANITY FAIL: Only {turns} turns (expected >= 3)')
if turns >= 30:
    issues.append(f'SANITY FAIL: {turns} turns is excessive (possible runaway)')

# Cost check
cost = result.get('cost_usd', 0)
if cost <= 0:
    issues.append(f'SANITY FAIL: Cost is {cost} (expected > 0)')
if cost >= 5.0:
    issues.append(f'SANITY FAIL: Cost is \${cost:.2f} (expected < \$5.00)')

# Strategy name check
name = result.get('strategy_name', '')
if not name:
    issues.append('SANITY FAIL: No strategy_name in result')

# Strategy path check
path = result.get('strategy_path', '')
if not path:
    issues.append('SANITY FAIL: No strategy_path in result')

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
| design-agent-1 not running | ENVIRONMENT | Run `uv run kinfra sandbox up` or check docker compose config includes design-agent-1 |
| design-agent-1 not in workers registry | ENVIRONMENT | Check worker startup logs: `docker compose logs design-agent-1 --tail 50`; verify KTRDR_API_CLIENT_BASE_URL is correct |
| POST /designs/start returns 4xx/5xx | CODE_BUG | Check DesignStartRequest schema matches payload; check design agent logs |
| Operation stuck in "running" (timeout) | CODE_BUG or ENVIRONMENT | Check design agent container logs for Claude Code errors; verify auth volume is mounted; check if Claude Code hung on permission prompt |
| Operation fails with "did not call save_strategy_config" | CODE_BUG | The system prompt or allowed_tools may be misconfigured; check DESIGN_SYSTEM_PROMPT instructs the agent to use save_strategy_config |
| Operation fails with auth error | ENVIRONMENT | Claude auth volume not provisioned; run `docker exec design-agent-1 claude auth status` to check |
| Strategy file not found after completion | CODE_BUG | Path mismatch between save_strategy_config MCP tool and strategy_path in result; check strategies directory inside container |
| Strategy is v2 format (missing nn_inputs) | CODE_BUG | System prompt not instructing v3 format; or save_strategy_config not validating format |
| Dangling indicator/fuzzy_set references | CODE_BUG | Agent designed inconsistent strategy; save_strategy_config validation should have caught this |
| cost_usd is 0 but turns > 0 | TEST_ISSUE | SDK may not report cost for all auth methods; check if using API key vs OAuth |
| Excessive cost (> $5) | CONFIGURATION | KTRDR_AGENT_MAX_BUDGET or KTRDR_AGENT_MAX_TURNS too high; or model set to opus instead of sonnet |

---

## Cleanup

```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'backend' | head -1)
docker exec "$CONTAINER" bash -c 'rm -f /app/strategies/e2e_design_test_*.yaml /app/strategies/e2e_design_test_*_assessment.json' 2>/dev/null
echo "Cleanup complete"
```

No other state to clean: operations are in-memory and will be garbage collected.

---

## Evidence to Capture

- Design agent health response
- Worker registry entry for agent_design worker
- POST /designs/start response (operation_id)
- All poll snapshots (status progression over time)
- Final operation state (full JSON)
- result_summary fields: strategy_name, strategy_path, cost_usd, turns, session_id
- Full strategy YAML file content
- V3 format validation results (sections present, references valid)
- Design agent container logs (last 50 lines): `docker compose logs design-agent-1 --tail 50`
- Total wall-clock duration

---

## Notes for Implementation

- **This test costs real money.** Each invocation uses Claude Code API credits. Typical cost for a simple design brief is $0.50-2.00. The brief is intentionally simple to keep costs down. Do NOT run this test in rapid succession.
- **The design agent runs inside a container.** It is NOT invoked via `docker run` like the sdk-invocation-in-container test. The design-agent-1 is a long-running service defined in docker-compose.sandbox.yml. The test interacts with it via its HTTP API (POST /designs/start).
- **Polling is against the backend, not the worker.** The operation status is tracked by the backend's OperationsService. Poll `GET /api/v1/operations/{id}` on the backend API port, not the design agent port.
- **The agent's strategy name is non-deterministic.** Claude Code will choose a strategy name based on its design. We cannot predict the exact name. The operation result_summary contains the actual name chosen. Use that for file verification, not a hardcoded name.
- **The task_id becomes the operation_id.** The DesignStartRequest.task_id is used as the operation_id by the worker. This means we control the operation_id format, which makes polling easier.
- **v3 strategy format is required.** The design system prompt instructs Claude to produce v3 format. If it produces v2 (no nn_inputs, no fuzzy_sets), that is a test failure -- the system prompt or MCP validation is wrong.
- **Step 7 (get_recent_strategies) is a soft check.** The agent may choose a strategy name that does not match our test prefix. The primary verification is step 5 (read the file directly). Step 7 is a cross-check.
- **Timeout of 5 minutes is generous but necessary.** Claude Code agentic loops with multiple MCP tool calls (get_available_indicators, get_indicator_details, save_strategy_config) typically take 1-3 minutes. Allow 5 minutes for slow API responses or retries.
- **The design agent needs the ktrdr MCP server.** It runs as a stdio subprocess inside the agent container. If MCP server setup fails, the operation will fail with a message about missing tools. Check that KTRDR_MCP_BACKEND_URL and PYTHONPATH are set correctly in the container.
- **Alternative brief if this one is too complex:** If the agent consistently fails or takes too long, simplify the brief to: "Design a strategy for EURUSD 1h using only RSI. Use the simplest possible design." This reduces the number of MCP tool calls needed.
