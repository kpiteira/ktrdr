# Test: mcp/strategy-save-roundtrip

**Purpose:** Validate MCP tools for strategy save, assessment save, and recent strategy discovery work end-to-end via stdio JSON-RPC transport
**Duration:** ~30 seconds
**Category:** MCP

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] MCP server container is running (the backend container hosts the MCP server code)
- [ ] Identify the correct backend container name: `docker ps --filter name=sdk-evolution --format '{{.Names}}' | grep backend`
- [ ] MCP server can start: `docker exec -i <CONTAINER> /app/.venv/bin/python -c "from mcp.src.server import mcp; print('OK')"` exits 0
- [ ] The strategies directory exists inside the container: `docker exec <CONTAINER> ls /app/strategies/`

---

## Test Data

### Valid V3 Strategy YAML

```yaml
name: e2e_mcp_test_strategy
description: E2E test strategy for MCP round-trip validation
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
```

### Invalid Strategy YAML (missing required `indicators` section)

```yaml
name: e2e_mcp_invalid_strategy
description: Intentionally invalid strategy
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
```

**Why this data:**
- Valid strategy uses the simplest possible v3 format (1 indicator, 1 fuzzy set) to minimize validation complexity while exercising the full save path
- Invalid strategy removes the `indicators` section -- this is a v3 format requirement that the loader should reject
- EURUSD/1h is the standard test pair used throughout the codebase

---

## MCP Protocol Notes

**Transport:** The MCP stdio transport uses **newline-delimited JSON** (one JSON-RPC message per line), NOT Content-Length framing. Each message sent to stdin must be a complete JSON object followed by `\n`. Each response from stdout is a complete JSON object on a single line.

**Session lifecycle:**
1. Send `initialize` request
2. Receive `initialize` response
3. Send `notifications/initialized` notification (no response expected)
4. Now you can send `tools/list`, `tools/call`, etc.

**How to interact:**
```bash
# Start MCP server as background process, pipe stdin/stdout
docker exec -i <CONTAINER> /app/.venv/bin/python -m mcp.src.main
```

Feed JSON-RPC messages on stdin (one per line), read responses from stdout (one per line). Stderr contains log output (safe to ignore for protocol purposes).

---

## Execution Steps

### 0. Identify Container and Clean Up

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# Find the backend container
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)
if [ -z "$CONTAINER" ]; then
  # Fallback: try broader search
  CONTAINER=$(docker ps --format '{{.Names}}' | grep backend | head -1)
fi
echo "Using container: $CONTAINER"

# Clean up any test artifacts from previous runs
docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_test_strategy.yaml
docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_test_strategy_assessment.json
docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_invalid_strategy.yaml

# Record pre-existing strategy count
STRATEGY_COUNT_BEFORE=$(docker exec "$CONTAINER" ls /app/strategies/*.yaml 2>/dev/null | wc -l | tr -d ' ')
echo "Strategies before test: $STRATEGY_COUNT_BEFORE"
```

**Expected:**
- CONTAINER is identified (non-empty)
- Cleanup succeeds (files may or may not exist)

### 1. Initialize MCP Session and List Tools

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

# Create a script that sends MCP messages and captures responses
# We use a single docker exec session to maintain the stdio pipe

# Build the message sequence
INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
LIST_TOOLS_MSG='{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

# Send all messages via stdin, collect stdout
# Use timeout to prevent hanging if server doesn't respond
RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$LIST_TOOLS_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

echo "=== Raw Responses ==="
echo "$RESPONSES"
echo "=== End Responses ==="

# Parse the tools/list response (second JSON line -- the init response is first)
TOOLS_RESPONSE=$(echo "$RESPONSES" | grep '"id":2' | head -1)
echo ""
echo "=== Tools List Response ==="
echo "$TOOLS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$TOOLS_RESPONSE"
```

**Expected:**
- MCP server starts without error
- Initialize response returns with server capabilities
- Tools list response contains tool definitions

### 2. Verify New Tools Present

**Command:**
```bash
# Extract tool names from the tools/list response
echo "$TOOLS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
tools = data.get('result', {}).get('tools', [])
tool_names = sorted(t['name'] for t in tools)
print('Tool count:', len(tool_names))
print('Tools:', ', '.join(tool_names))
print()

# Check required tools
required = ['save_strategy_config', 'save_assessment', 'get_recent_strategies']
for name in required:
    if name in tool_names:
        print(f'OK: {name} present')
    else:
        print(f'FAIL: {name} missing')

# Check deprecated tool is gone
if 'get_training_status' in tool_names:
    print('FAIL: get_training_status still present (should be removed)')
else:
    print('OK: get_training_status removed')
"
```

**Expected:**
- `save_strategy_config` is in the tool list
- `save_assessment` is in the tool list
- `get_recent_strategies` is in the tool list
- `get_training_status` is NOT in the tool list
- Total tool count should be approximately 18-20 (existing tools minus removed one plus new ones)

### 3. Call save_strategy_config with Valid Strategy

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

# Strategy YAML content (escaped for JSON embedding)
read -r -d '' STRATEGY_YAML << 'STRATEGY_EOF'
name: e2e_mcp_test_strategy
description: E2E test strategy for MCP round-trip validation
version: "3.0"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

indicators:
  rsi_14:
    type: rsi
    period: 14

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]
    overbought:
      type: triangular
      parameters: [65, 80, 100]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
STRATEGY_EOF

# JSON-encode the YAML string for embedding in the tool call
ESCAPED_YAML=$(python3 -c "import json; print(json.dumps('''$STRATEGY_YAML'''.strip()))")

# Build messages
INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'

# Build tool call using python to handle YAML escaping properly
SAVE_MSG=$(python3 -c "
import json
msg = {
    'jsonrpc': '2.0',
    'id': 3,
    'method': 'tools/call',
    'params': {
        'name': 'save_strategy_config',
        'arguments': {
            'strategy_name': 'e2e_mcp_test_strategy',
            'strategy_yaml': '''$STRATEGY_YAML'''.strip()
        }
    }
}
print(json.dumps(msg))
")

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$SAVE_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

SAVE_RESPONSE=$(echo "$RESPONSES" | grep '"id":3' | head -1)
echo "=== Save Strategy Response ==="
echo "$SAVE_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$SAVE_RESPONSE"
```

**Expected:**
- Response contains `result` (not `error`)
- Result content includes `"success": true`
- Result content includes `strategy_name: "e2e_mcp_test_strategy"`
- Result content includes `strategy_path` pointing to a `.yaml` file

**Capture:** Full save response JSON, strategy_path value

### 4. Verify Strategy File Exists Inside Container

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

# Check the file exists
docker exec "$CONTAINER" ls -la /app/strategies/e2e_mcp_test_strategy.yaml
echo ""

# Verify it is valid YAML and contains expected content
docker exec "$CONTAINER" python3 -c "
import yaml
with open('/app/strategies/e2e_mcp_test_strategy.yaml') as f:
    config = yaml.safe_load(f)
print('name:', config.get('name'))
print('version:', config.get('version'))
print('indicators:', list(config.get('indicators', {}).keys()))
print('has_fuzzy_sets:', 'fuzzy_sets' in config)
print('has_nn_inputs:', 'nn_inputs' in config)
assert config['name'] == 'e2e_mcp_test_strategy', f'Wrong name: {config[\"name\"]}'
assert config['version'] == '3.0', f'Wrong version: {config[\"version\"]}'
assert 'rsi_14' in config.get('indicators', {}), 'Missing rsi_14 indicator'
print('OK: Strategy file is valid')
"
```

**Expected:**
- File exists at `/app/strategies/e2e_mcp_test_strategy.yaml`
- YAML is parseable
- Contains correct name, version, indicators, fuzzy_sets, nn_inputs

### 5. Call get_recent_strategies and Find Saved Strategy

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
RECENT_MSG='{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"get_recent_strategies","arguments":{"limit":5}}}'

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$RECENT_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

RECENT_RESPONSE=$(echo "$RESPONSES" | grep '"id":4' | head -1)
echo "=== Recent Strategies Response ==="
echo "$RECENT_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RECENT_RESPONSE"

# Verify our strategy is in the list
echo ""
echo "$RECENT_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)

# The result may be in data['result']['content'][0]['text'] (MCP tool response format)
# or directly in data['result'] depending on how FastMCP serializes
result = data.get('result', {})

# FastMCP wraps tool results in content array with text type
content = result.get('content', [])
if content and isinstance(content, list):
    # Parse the text content which contains the actual return value
    text = content[0].get('text', '[]')
    strategies = json.loads(text)
else:
    strategies = result if isinstance(result, list) else []

print(f'Strategies returned: {len(strategies)}')
found = False
for s in strategies:
    name = s.get('name', 'unknown')
    indicators = s.get('indicators', [])
    verdict = s.get('assessment_verdict')
    print(f'  - {name}: indicators={indicators}, verdict={verdict}')
    if name == 'e2e_mcp_test_strategy':
        found = True
        assert 'rsi_14' in indicators, f'Expected rsi_14 in indicators: {indicators}'
        print(f'    OK: Found our test strategy with correct indicators')

if found:
    print('OK: e2e_mcp_test_strategy found in recent strategies')
else:
    print('FAIL: e2e_mcp_test_strategy NOT found in recent strategies')
"
```

**Expected:**
- Response contains a list of strategies
- `e2e_mcp_test_strategy` appears in the list
- Its indicators include `rsi_14`
- Its assessment_verdict is null (no assessment saved yet)

### 6. Call save_strategy_config with Invalid Strategy

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'

# Invalid strategy: missing indicators section
INVALID_SAVE_MSG=$(python3 -c "
import json
invalid_yaml = '''
name: e2e_mcp_invalid_strategy
description: Intentionally invalid strategy
version: \"3.0\"

training_data:
  symbols:
    mode: single
    list: [EURUSD]
  timeframes:
    mode: single
    list: [1h]
    base_timeframe: 1h
  history_required: 100

fuzzy_sets:
  rsi_momentum:
    indicator: rsi_14
    oversold:
      type: triangular
      parameters: [0, 20, 35]

nn_inputs:
  - fuzzy_set: rsi_momentum
    timeframes: all

model:
  type: mlp
  architecture:
    hidden_layers: [32]

decisions:
  output_format: classification

training:
  method: supervised
  labels:
    source: zigzag
'''.strip()

msg = {
    'jsonrpc': '2.0',
    'id': 5,
    'method': 'tools/call',
    'params': {
        'name': 'save_strategy_config',
        'arguments': {
            'strategy_name': 'e2e_mcp_invalid_strategy',
            'strategy_yaml': invalid_yaml
        }
    }
}
print(json.dumps(msg))
")

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$INVALID_SAVE_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

INVALID_RESPONSE=$(echo "$RESPONSES" | grep '"id":5' | head -1)
echo "=== Invalid Strategy Response ==="
echo "$INVALID_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$INVALID_RESPONSE"

# Verify no file was created
echo ""
docker exec "$CONTAINER" ls /app/strategies/e2e_mcp_invalid_strategy.yaml 2>&1
INVALID_FILE_EXISTS=$?
if [ $INVALID_FILE_EXISTS -ne 0 ]; then
  echo "OK: Invalid strategy file was NOT created (atomic rejection)"
else
  echo "FAIL: Invalid strategy file was created despite validation failure"
fi

# Verify response indicates failure
echo "$INVALID_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result', {})
content = result.get('content', [])
if content and isinstance(content, list):
    text = content[0].get('text', '{}')
    result_data = json.loads(text)
else:
    result_data = result

success = result_data.get('success', True)
errors = result_data.get('errors', [])
print(f'success: {success}')
print(f'errors: {errors}')
if not success and errors:
    print('OK: Invalid strategy correctly rejected with errors')
else:
    print('FAIL: Expected success=false with errors')
"
```

**Expected:**
- Response indicates `success: false`
- Response contains `errors` list with validation error message
- No file created at `/app/strategies/e2e_mcp_invalid_strategy.yaml`

### 7. Call save_assessment with Valid Assessment

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
ASSESS_MSG='{"jsonrpc":"2.0","id":6,"method":"tools/call","params":{"name":"save_assessment","arguments":{"strategy_name":"e2e_mcp_test_strategy","verdict":"promising","strengths":["Simple single-indicator design","Low parameter count reduces overfitting risk"],"weaknesses":["Only uses RSI, no volume or trend confirmation","Single timeframe limits context"],"suggestions":["Add MACD for trend confirmation","Include volume indicators"]}}}'

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$ASSESS_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

ASSESS_RESPONSE=$(echo "$RESPONSES" | grep '"id":6' | head -1)
echo "=== Save Assessment Response ==="
echo "$ASSESS_RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$ASSESS_RESPONSE"

# Verify assessment file was created
echo ""
docker exec "$CONTAINER" ls -la /app/strategies/e2e_mcp_test_strategy_assessment.json 2>&1

# Verify contents
echo ""
docker exec "$CONTAINER" python3 -c "
import json
with open('/app/strategies/e2e_mcp_test_strategy_assessment.json') as f:
    data = json.load(f)
print('strategy_name:', data.get('strategy_name'))
print('verdict:', data.get('verdict'))
print('strengths count:', len(data.get('strengths', [])))
print('weaknesses count:', len(data.get('weaknesses', [])))
print('suggestions count:', len(data.get('suggestions', [])))
print('has_timestamp:', 'timestamp' in data)
assert data['strategy_name'] == 'e2e_mcp_test_strategy'
assert data['verdict'] == 'promising'
assert len(data['strengths']) == 2
assert len(data['weaknesses']) == 2
assert len(data['suggestions']) == 2
print('OK: Assessment file is valid')
"

# Parse response to verify success
echo "$ASSESS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result', {})
content = result.get('content', [])
if content and isinstance(content, list):
    text = content[0].get('text', '{}')
    result_data = json.loads(text)
else:
    result_data = result

print(f'success: {result_data.get(\"success\")}')
print(f'assessment_path: {result_data.get(\"assessment_path\")}')
if result_data.get('success'):
    print('OK: Assessment saved successfully')
else:
    print(f'FAIL: Assessment save failed: {result_data.get(\"errors\")}')
"
```

**Expected:**
- Response indicates `success: true`
- Response contains `assessment_path`
- File exists at `/app/strategies/e2e_mcp_test_strategy_assessment.json`
- File contains correct strategy_name, verdict, strengths, weaknesses, suggestions, timestamp

### 8. Verify get_recent_strategies Now Shows Assessment Verdict

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

INIT_MSG='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"e2e-test","version":"1.0.0"}}}'
INITIALIZED_NOTIF='{"jsonrpc":"2.0","method":"notifications/initialized"}'
RECENT_MSG='{"jsonrpc":"2.0","id":7,"method":"tools/call","params":{"name":"get_recent_strategies","arguments":{"limit":5}}}'

RESPONSES=$(printf '%s\n%s\n%s\n' "$INIT_MSG" "$INITIALIZED_NOTIF" "$RECENT_MSG" | \
  timeout 15 docker exec -i "$CONTAINER" /app/.venv/bin/python -m mcp.src.main 2>/dev/null)

RECENT_RESPONSE2=$(echo "$RESPONSES" | grep '"id":7' | head -1)
echo "=== Recent Strategies After Assessment ==="
echo "$RECENT_RESPONSE2" | python3 -m json.tool 2>/dev/null || echo "$RECENT_RESPONSE2"

echo ""
echo "$RECENT_RESPONSE2" | python3 -c "
import sys, json
data = json.load(sys.stdin)
result = data.get('result', {})
content = result.get('content', [])
if content and isinstance(content, list):
    text = content[0].get('text', '[]')
    strategies = json.loads(text)
else:
    strategies = result if isinstance(result, list) else []

for s in strategies:
    if s.get('name') == 'e2e_mcp_test_strategy':
        verdict = s.get('assessment_verdict')
        print(f'assessment_verdict: {verdict}')
        if verdict == 'promising':
            print('OK: Assessment verdict visible in recent strategies')
        else:
            print(f'FAIL: Expected verdict \"promising\", got \"{verdict}\"')
        break
else:
    print('FAIL: e2e_mcp_test_strategy not found in recent strategies')
"
```

**Expected:**
- `e2e_mcp_test_strategy` appears in results
- Its `assessment_verdict` is now `"promising"` (was null before step 7)

### 9. Cleanup

**Command:**
```bash
CONTAINER=$(docker ps --format '{{.Names}}' | grep -E 'sdk-evolution.*backend' | head -1)

docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_test_strategy.yaml
docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_test_strategy_assessment.json
docker exec "$CONTAINER" rm -f /app/strategies/e2e_mcp_invalid_strategy.yaml

echo "Cleanup complete"
```

---

## Success Criteria

All must pass for the test to pass:

- [ ] MCP server starts via `docker exec -i` stdio transport without errors
- [ ] `tools/list` includes `save_strategy_config`, `save_assessment`, `get_recent_strategies`
- [ ] `tools/list` does NOT include `get_training_status`
- [ ] `save_strategy_config` with valid v3 YAML returns success + strategy_name + strategy_path
- [ ] Strategy file exists at returned path inside container and contains valid v3 content
- [ ] `get_recent_strategies` returns the saved strategy with correct indicators
- [ ] `save_strategy_config` with invalid YAML returns success=false + errors, no file created
- [ ] `save_assessment` returns success + assessment_path
- [ ] Assessment JSON file exists with correct structure (verdict, strengths, weaknesses, suggestions, timestamp)
- [ ] `get_recent_strategies` after assessment shows the verdict field populated

---

## Sanity Checks

**CRITICAL:** These catch false positives

- [ ] **Tool count >= 15** -- If the tools list has fewer than 15 tools, the MCP server likely failed to register its tool modules. The server has ~18-20 tools total. A very small tool count (e.g., 1-3) means only inline tools loaded and `register_strategy_tools`/`register_assessment_tools` calls failed.
- [ ] **Strategy file size > 100 bytes** -- If the saved file is tiny or empty, the atomic write may have failed silently.
- [ ] **Assessment file has all required fields** -- Check for strategy_name, verdict, strengths, weaknesses, suggestions, and timestamp. A partial write indicates the JSON serialization or atomic rename failed.
- [ ] **get_recent_strategies returns >= 1 result** -- If it returns an empty list despite a strategy being saved, the strategies directory path may be wrong inside the container (e.g., cwd mismatch).
- [ ] **MCP responses have `result` key, not `error` key** -- If tool calls return JSON-RPC errors instead of results, the tool registration may have the wrong function signature.
- [ ] **Each MCP session starts fresh** -- Since we create a new MCP process for each step, there is no state carried between steps. The persistence comes from the filesystem, not the server process.

**Check tool count:**
```bash
echo "$TOOLS_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
count = len(data.get('result', {}).get('tools', []))
print(f'Tool count: {count}')
if count < 15:
    print(f'WARNING: Only {count} tools registered. Expected ~18-20.')
elif count > 25:
    print(f'WARNING: {count} tools seems high. Check for duplicates.')
else:
    print(f'OK: Tool count in expected range')
"
```

---

## Troubleshooting

**If "container not found" (CONTAINER is empty):**
- **Cause:** The sandbox containers are not running, or the naming pattern does not match `sdk-evolution.*backend`
- **Cure:** Run `docker ps` to see actual container names. The pattern may be `ktrdr-impl-sdk-evolution-researchers-M1-backend-1` or similar. Update the grep pattern accordingly. Start sandbox with `cd /Users/karl/Documents/dev/ktrdr-impl-sdk-evolution-researchers-M1 && uv run kinfra sandbox up`.

**If MCP server fails to start (import errors):**
- **Cause:** New service modules (`ktrdr/mcp/strategy_service.py`, `ktrdr/mcp/assessment_service.py`) not in the container image
- **Cure:** Rebuild the container: `cd /Users/karl/Documents/dev/ktrdr-impl-sdk-evolution-researchers-M1 && uv run kinfra sandbox up --build`

**If tools/list is missing new tools:**
- **Cause:** `register_strategy_tools(mcp)` or `register_assessment_tools(mcp)` not called in `server.py`, or import error in tool modules
- **Cure:** Check `mcp/src/server.py` for both `register_*_tools` import and call. Check stderr output from the docker exec for import errors.

**If save_strategy_config returns success but file not found:**
- **Cause:** Strategies directory path mismatch. The service uses `DEFAULT_STRATEGIES_DIR = "strategies"` (relative), which resolves relative to the MCP server's working directory inside the container
- **Cure:** Check what directory the MCP process runs in: `docker exec <CONTAINER> pwd`. The strategies should be at `/app/strategies/` if cwd is `/app/`.

**If get_recent_strategies returns empty list:**
- **Cause:** The strategies directory path resolution differs between save (writes to `strategies/` relative) and list (reads from `strategies/` relative). Or cwd is not `/app/`.
- **Cure:** Verify the saved file path from step 3 response and the directory get_recent_strategies scans are the same.

**If MCP responses are empty or garbled:**
- **Cause:** ktrdr imports print to stdout, corrupting the JSON-RPC stream. The `main.py` has stdout redirection logic, but it may have edge cases.
- **Cure:** Check stderr for Python tracebacks. Try running the MCP server manually: `docker exec -it <CONTAINER> /app/.venv/bin/python -m mcp.src.main` and type the initialize message manually to see what comes back.

**If docker exec hangs:**
- **Cause:** The MCP server's stdin reader blocks waiting for more input. After sending all messages, the pipe needs to be closed (which `printf ... | docker exec -i` handles automatically when printf completes).
- **Cure:** Ensure the `timeout 15` wrapper is in place. If it times out, the MCP server may be stuck during initialization (e.g., waiting for backend health check). Check container logs.

**If save_assessment validation rejects valid assessment:**
- **Cause:** Verdict must be exactly one of "promising", "neutral", "poor". Strengths and weaknesses must each have at least one item.
- **Cure:** Verify the JSON payload matches the expected argument types (lists of strings, not single strings).

---

## Evidence to Capture

- Container name used
- Full tools/list response (tool names and count)
- save_strategy_config response for valid strategy (strategy_path)
- save_strategy_config response for invalid strategy (errors)
- save_assessment response (assessment_path)
- get_recent_strategies response before and after assessment
- Contents of saved strategy YAML file
- Contents of saved assessment JSON file
- Any stderr output from the MCP server (for debugging if failures occur)

---

## Notes for Implementation

- **Each step starts a new MCP process.** The stdio transport means each `docker exec -i` invocation starts a fresh MCP server. This is by design -- we are testing filesystem persistence, not in-memory state. Every step must include the full initialize/initialized handshake.
- **Shell variable escaping is tricky.** The strategy YAML must be embedded inside a JSON string inside a bash command. Using Python to build the JSON message (as shown in step 3) is the most reliable approach. Do not attempt manual escaping of newlines and quotes.
- **FastMCP tool response format.** FastMCP wraps tool return values in a `content` array: `{"result": {"content": [{"type": "text", "text": "<json-encoded-return-value>"}]}}`. The actual tool return dict is JSON-encoded inside the `text` field. Parser code must handle this double-encoding.
- **The `notifications/initialized` notification has no `id` field.** It is a JSON-RPC notification, not a request. The server does not send a response for it. Do not wait for or try to parse a response to this message.
- **Timeout is critical.** Without `timeout`, a hanging MCP server will block the test forever. 15 seconds per step is generous for local filesystem operations.
- **Alternative approach if stdio is unreliable:** If the pipe-based approach proves flaky, consider writing a small Python test script that uses the `mcp` library's client directly. Run it inside the container: `docker exec <CONTAINER> python3 /tmp/mcp_e2e_test.py`. This avoids shell escaping issues entirely.
