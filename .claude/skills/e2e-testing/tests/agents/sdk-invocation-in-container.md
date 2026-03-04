# Test: agents/sdk-invocation-in-container

**Purpose:** Validate that Claude Code SDK can invoke inside the ktrdr-agent Docker container, connect to the ktrdr MCP server as a stdio subprocess, and successfully call a real MCP tool that fetches data from the backend API
**Duration:** ~60 seconds (SDK invocation + MCP round-trip)
**Category:** Agents
**Cost:** This test uses REAL Claude Code API credits (typically $0.01-0.05 for a single-turn tool call)

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] `ktrdr-agent:dev` Docker image exists: `docker images ktrdr-agent:dev --format '{{.Repository}}:{{.Tag}}' | grep -q ktrdr-agent:dev`
- [ ] Claude auth available: named Docker volume `ktrdr-agent-claude-auth` exists (`docker volume inspect ktrdr-agent-claude-auth`) OR `ANTHROPIC_API_KEY` is set
- [ ] Backend health check passes from host: `curl -s http://localhost:${KTRDR_API_PORT:-8000}/api/v1/health | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('status')=='ok', f'Backend unhealthy: {d}'; print('Backend healthy')"`
- [ ] Docker network for sandbox exists (needed for container to reach backend): see Step 0

---

## Test Data

This test does not use a custom payload. It invokes Claude Code SDK with a simple prompt that forces a single MCP tool call:

```
Prompt: "Call the get_available_indicators tool and return the results. Do not do anything else."
```

**Why this prompt:**
- Forces exactly one MCP tool call (`get_available_indicators`)
- Minimal turns (1-2) to keep cost and duration low
- The tool returns real data from the backend API, proving the full chain works
- Deterministic enough to validate: the response must contain known indicator names (RSI, MACD, etc.)

**MCP Server Configuration (passed to SDK):**
```json
{
    "ktrdr": {
        "command": "bash",
        "args": ["-c", "cd /mcp && python -m src.main"],
        "env": {
            "KTRDR_API_URL": "http://backend:8000/api/v1",
            "PYTHONPATH": "/app:/mcp"
        }
    }
}
```

**Note:** `McpStdioServerConfig` does not support `cwd`. Use `bash -c "cd /mcp && ..."` instead.

---

## Execution Steps

### 0. Determine Docker Network Name and Build Image If Needed

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${KTRDR_API_PORT:-8000}

# The Docker network name is prefixed by the compose project name.
# For sandbox worktrees, it's the directory name + "_ktrdr-network"
COMPOSE_PROJECT=$(docker compose -f docker-compose.sandbox.yml config --format json 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null)
if [ -z "$COMPOSE_PROJECT" ]; then
  # Fallback: detect from running containers
  COMPOSE_PROJECT=$(docker ps --format '{{.Labels}}' | grep -oP 'com\.docker\.compose\.project=\K[^,]+' | head -1)
fi
NETWORK_NAME="${COMPOSE_PROJECT}_ktrdr-network"

# Verify network exists
docker network inspect "$NETWORK_NAME" > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "FAIL: Docker network $NETWORK_NAME not found"
  echo "Available networks:"
  docker network ls --format '{{.Name}}' | grep ktrdr
  echo ""
  echo "Try: uv run kinfra sandbox up"
  exit 1
fi
echo "Docker network: $NETWORK_NAME"

# Check if ktrdr-agent:dev image exists, build if not
if ! docker images ktrdr-agent:dev --format '{{.Repository}}' | grep -q ktrdr-agent; then
  echo "Building ktrdr-agent:dev image..."
  docker build -f deploy/docker/Dockerfile.agent -t ktrdr-agent:dev .
  BUILD_EXIT=$?
  if [ $BUILD_EXIT -ne 0 ]; then
    echo "FAIL: Docker image build failed with exit code $BUILD_EXIT"
    exit 1
  fi
  echo "Image built successfully"
else
  echo "ktrdr-agent:dev image already exists"
fi

docker images ktrdr-agent:dev --format 'Image: {{.Repository}}:{{.Tag}}, Size: {{.Size}}, Created: {{.CreatedSince}}'
```

**Expected:**
- Docker network identified (e.g., `ktrdr-impl-sdk-evolution-researchers-m2_ktrdr-network`)
- `ktrdr-agent:dev` image exists (built if needed)
- Build succeeds without errors if needed

### 1. Verify Container Basics (Claude CLI, Python, MCP Server Import)

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

# Determine network (same logic as step 0)
COMPOSE_PROJECT=$(docker ps --format '{{.Labels}}' | grep -oP 'com\.docker\.compose\.project=\K[^,]+' | head -1)
NETWORK_NAME="${COMPOSE_PROJECT}_ktrdr-network"

echo "=== Claude Code CLI ==="
docker run --rm \
  --network "$NETWORK_NAME" \
  ktrdr-agent:dev \
  claude --version 2>&1 | head -5

echo ""
echo "=== Python + ktrdr imports ==="
docker run --rm \
  --network "$NETWORK_NAME" \
  ktrdr-agent:dev \
  python -c "
from ktrdr.agents.runtime.protocol import AgentRuntime, AgentResult, AgentRuntimeConfig
print('AgentRuntime protocol: OK')
print('AgentResult fields:', [f.name for f in AgentResult.__dataclass_fields__.values()])
"

echo ""
echo "=== MCP server import ==="
docker run --rm \
  --network "$NETWORK_NAME" \
  -e PYTHONPATH=/app:/mcp \
  ktrdr-agent:dev \
  python -c "
import sys
sys.path.insert(0, '/mcp')
from src.server import KTRDRMCPServer
print('MCP server import: OK')
"

echo ""
echo "=== claude-agent-sdk import ==="
docker run --rm \
  --network "$NETWORK_NAME" \
  ktrdr-agent:dev \
  python -c "
from claude_agent_sdk import ClaudeAgentOptions
print('claude_agent_sdk: OK')
print('ClaudeAgentOptions available')
"
```

**Expected:**
- Claude Code CLI version prints (e.g., `2.x.x`)
- `AgentRuntime`, `AgentResult`, `AgentRuntimeConfig` import without error
- MCP server imports without error
- `claude_agent_sdk` imports without error

### 2. Verify MCP Server Can Reach Backend From Container

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

COMPOSE_PROJECT=$(docker ps --format '{{.Labels}}' | grep -oP 'com\.docker\.compose\.project=\K[^,]+' | head -1)
NETWORK_NAME="${COMPOSE_PROJECT}_ktrdr-network"

# The MCP server connects to "backend:8000" via the Docker network.
# Verify DNS resolution and HTTP connectivity from inside the agent container.
docker run --rm \
  --network "$NETWORK_NAME" \
  ktrdr-agent:dev \
  bash -c '
    echo "=== DNS resolution ==="
    getent hosts backend || echo "FAIL: Cannot resolve backend hostname"

    echo ""
    echo "=== HTTP health check ==="
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" http://backend:8000/api/v1/health)
    echo "Health check HTTP status: $HEALTH"
    if [ "$HEALTH" = "200" ]; then
      echo "OK: Backend reachable from agent container"
    else
      echo "FAIL: Backend not reachable (HTTP $HEALTH)"
    fi

    echo ""
    echo "=== Indicators endpoint ==="
    INDICATORS=$(curl -s http://backend:8000/api/v1/indicators/ 2>/dev/null | head -c 500)
    echo "Indicators response (first 500 chars): $INDICATORS"
  '
```

**Expected:**
- Backend hostname resolves to an IP address
- Health check returns HTTP 200
- Indicators endpoint returns JSON with indicator data

### 3. Run SDK Invocation Test Script Inside Container

**Command:**
```bash
[ -f .env.sandbox ] && source .env.sandbox

COMPOSE_PROJECT=$(docker ps --format '{{.Labels}}' | grep -oP 'com\.docker\.compose\.project=\K[^,]+' | head -1)
NETWORK_NAME="${COMPOSE_PROJECT}_ktrdr-network"

# Create the test script on the host, then copy it into the container.
# This script invokes ClaudeAgentRuntime.invoke() with a simple prompt
# that forces an MCP tool call.

cat > /tmp/ktrdr_sdk_e2e_test.py << 'TESTSCRIPT'
"""E2E test: Claude Code SDK invocation with MCP tool call inside container."""

import asyncio
import json
import sys
import os

# Ensure MCP path is available
sys.path.insert(0, "/mcp")


async def main():
    from ktrdr.agents.runtime.protocol import AgentRuntimeConfig, AgentResult
    from ktrdr.agents.runtime.claude import ClaudeAgentRuntime

    config = AgentRuntimeConfig(
        provider="claude",
        model="claude-sonnet-4-6",
        max_budget_usd=0.50,
        max_turns=5,
    )

    runtime = ClaudeAgentRuntime(config=config)

    mcp_servers = {
        "ktrdr": {
            "command": "bash",
            "args": ["-c", "cd /mcp && python -m src.main"],
            "env": {
                "KTRDR_API_URL": "http://backend:8000/api/v1",
                "PYTHONPATH": "/app:/mcp",
            },
        }
    }

    prompt = (
        "Call the get_available_indicators tool and return the results. "
        "Do not do anything else — just call the tool and report what it returned."
    )

    print("=== Starting SDK invocation ===", file=sys.stderr)
    print(f"Model: {config.model}", file=sys.stderr)
    print(f"MCP servers: {list(mcp_servers.keys())}", file=sys.stderr)

    result: AgentResult = await runtime.invoke(
        prompt,
        model=config.model,
        max_turns=5,
        max_budget_usd=0.50,
        allowed_tools=["mcp__ktrdr__get_available_indicators"],
        cwd="/app",
        system_prompt="You are a test agent. Call the requested MCP tool and report results. Be concise.",
        mcp_servers=mcp_servers,
    )

    # Output structured result as JSON to stdout
    output = {
        "output": result.output[:2000],  # Truncate for readability
        "cost_usd": result.cost_usd,
        "turns": result.turns,
        "session_id": result.session_id,
        "transcript_length": len(result.transcript),
        "transcript": result.transcript,
    }

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
TESTSCRIPT

echo "Test script created at /tmp/ktrdr_sdk_e2e_test.py"

# Run the test inside the agent container with:
# - Claude auth: named volume (ktrdr-agent-claude-auth) or ANTHROPIC_API_KEY env var
# - Docker network access to backend
# - PYTHONPATH includes both /app and /mcp
START_TIME=$(date +%s)

SDK_OUTPUT=$(docker run --rm \
  --network "$NETWORK_NAME" \
  -v "$HOME/.claude:/home/agent/.claude:ro" \
  -v /tmp/ktrdr_sdk_e2e_test.py:/tmp/test_script.py:ro \
  -e PYTHONPATH=/app:/mcp \
  ktrdr-agent:dev \
  timeout 120 python /tmp/test_script.py 2>/tmp/ktrdr_sdk_e2e_stderr.log)

EXIT_CODE=$?
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "=== SDK Invocation Result ==="
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"
echo ""
echo "=== Stderr (SDK logs) ==="
cat /tmp/ktrdr_sdk_e2e_stderr.log 2>/dev/null | tail -20
echo ""
echo "=== Stdout (structured result) ==="
echo "$SDK_OUTPUT"
```

**Expected:**
- Exit code 0
- Duration between 5 and 120 seconds
- Stdout contains valid JSON with `output`, `cost_usd`, `turns`, `transcript` fields
- Stderr shows SDK startup logs (not errors)

**Capture:** Full stdout JSON, exit code, duration, stderr tail

### 4. Validate Transcript Contains MCP Tool Call

**Command:**
```bash
# Parse the SDK output from step 3
echo "$SDK_OUTPUT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
transcript = data.get('transcript', [])

print(f'Transcript entries: {len(transcript)}')
print()

# Find tool_use entries
tool_calls = [e for e in transcript if e.get('type') == 'tool_use']
tool_results = [e for e in transcript if e.get('type') == 'tool_result']

print(f'Tool calls: {len(tool_calls)}')
print(f'Tool results: {len(tool_results)}')
print()

# Check for the specific MCP tool call
found_indicator_call = False
for tc in tool_calls:
    tool_name = tc.get('tool', '')
    print(f'  Tool call: {tool_name}')
    if 'get_available_indicators' in tool_name:
        found_indicator_call = True
        print(f'    OK: Found get_available_indicators call')
        # The SDK prefixes MCP tools with mcp__<server_name>__
        if tool_name == 'mcp__ktrdr__get_available_indicators':
            print(f'    OK: Correct MCP tool name format (mcp__ktrdr__get_available_indicators)')
        else:
            print(f'    WARNING: Unexpected tool name format: {tool_name}')

if found_indicator_call:
    print()
    print('OK: MCP tool call found in transcript')
else:
    print()
    print('FAIL: No get_available_indicators tool call found in transcript')
    print('All transcript entries:')
    for i, e in enumerate(transcript):
        print(f'  [{i}] type={e.get(\"type\")}, tool={e.get(\"tool\", \"n/a\")}')
"
```

**Expected:**
- At least 1 `tool_use` entry in transcript
- Tool name matches `mcp__ktrdr__get_available_indicators`
- At least 1 `tool_result` entry (the MCP response)

### 5. Validate MCP Tool Returned Real Indicator Data

**Command:**
```bash
# Parse the tool result from the transcript
echo "$SDK_OUTPUT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
transcript = data.get('transcript', [])

# Find the tool_result that corresponds to get_available_indicators
tool_results = [e for e in transcript if e.get('type') == 'tool_result']

if not tool_results:
    print('FAIL: No tool results in transcript')
    sys.exit(1)

# The tool result content may be a string or a list
for tr in tool_results:
    content = tr.get('content', '')
    print(f'Tool result content type: {type(content).__name__}')

    # Try to extract indicator data from the content
    # Content might be a string (JSON), a list of content blocks, or nested
    indicator_text = ''
    if isinstance(content, str):
        indicator_text = content
    elif isinstance(content, list):
        # Content blocks: [{\"type\": \"text\", \"text\": \"...\"}]
        for block in content:
            if isinstance(block, dict) and 'text' in block:
                indicator_text += block['text']
            elif isinstance(block, str):
                indicator_text += block

    # Check for known indicator names
    known_indicators = ['rsi', 'macd', 'sma', 'ema', 'bollinger', 'stochastic', 'atr']
    found_indicators = []
    text_lower = indicator_text.lower()
    for ind in known_indicators:
        if ind in text_lower:
            found_indicators.append(ind)

    print(f'Known indicators found: {found_indicators}')
    print(f'Content length: {len(indicator_text)} chars')

    if len(found_indicators) >= 3:
        print(f'OK: Real indicator data returned ({len(found_indicators)} known indicators found)')
    elif len(found_indicators) >= 1:
        print(f'WARNING: Only {len(found_indicators)} known indicators found — may be partial data')
    else:
        print(f'FAIL: No known indicators found in tool result')
        print(f'Content preview: {indicator_text[:500]}')

# Also check the output field for indicator data (Claude may echo it)
output = data.get('output', '')
output_lower = output.lower()
output_indicators = [ind for ind in known_indicators if ind in output_lower]
print()
print(f'Indicators mentioned in output text: {output_indicators}')
"
```

**Expected:**
- Tool result contains indicator data (not an error message)
- At least 3 known indicators found (RSI, MACD, SMA, EMA, Bollinger, etc.)
- Content length > 100 characters (real data, not a stub)

### 6. Validate Cost Tracking and AgentResult Structure

**Command:**
```bash
echo "$SDK_OUTPUT" | python3 -c "
import sys, json

data = json.load(sys.stdin)

cost_usd = data.get('cost_usd', 0.0)
turns = data.get('turns', 0)
session_id = data.get('session_id')
transcript_length = data.get('transcript_length', 0)
output = data.get('output', '')

print(f'cost_usd: {cost_usd}')
print(f'turns: {turns}')
print(f'session_id: {session_id}')
print(f'transcript_length: {transcript_length}')
print(f'output_length: {len(output)}')
print()

# Validate cost
if cost_usd > 0:
    print(f'OK: Cost tracked ({cost_usd:.4f} USD)')
elif turns > 0:
    print(f'WARNING: turns > 0 but cost_usd = 0 — cost tracking may not be working')
else:
    print(f'FAIL: Both cost_usd and turns are 0 — SDK invocation may have failed silently')

# Validate turns
if turns > 0:
    print(f'OK: Turns tracked ({turns})')
else:
    print(f'FAIL: turns = 0')

# Validate session_id
if session_id:
    print(f'OK: Session ID present ({session_id[:20]}...)')
else:
    print(f'WARNING: No session_id — may be expected for some SDK versions')

# Validate transcript
if transcript_length > 0:
    print(f'OK: Transcript has {transcript_length} entries')
else:
    print(f'FAIL: Empty transcript')

# Validate output
if len(output) > 10:
    print(f'OK: Output text present ({len(output)} chars)')
else:
    print(f'FAIL: Output too short or empty')

# Sanity: cost should be reasonable for a single tool call
if cost_usd > 1.0:
    print(f'WARNING: Cost seems high for a single tool call: \${cost_usd:.4f}')
"
```

**Expected:**
- `cost_usd` > 0 (real API usage occurred)
- `turns` > 0 (at least one turn completed)
- `transcript_length` > 0 (entries were captured)
- `output` is non-empty (Claude produced text)
- Cost is reasonable (< $1.00 for a single tool call)

### 7. Cleanup

**Command:**
```bash
# Remove temporary test script
rm -f /tmp/ktrdr_sdk_e2e_test.py
rm -f /tmp/ktrdr_sdk_e2e_stderr.log

# No container cleanup needed — docker run --rm handles it
echo "Cleanup complete"
```

---

## Success Criteria

All must pass for the test to pass:

- [ ] `ktrdr-agent:dev` Docker image exists (built or pre-existing)
- [ ] Claude Code CLI accessible inside container (`claude --version`)
- [ ] `claude_agent_sdk` importable inside container
- [ ] MCP server importable inside container (`from src.server import KTRDRMCPServer`)
- [ ] `AgentRuntime` protocol and `ClaudeAgentRuntime` importable inside container
- [ ] Backend reachable from inside container via Docker network (`http://backend:8000`)
- [ ] SDK invocation completes without auth errors (exit code 0)
- [ ] Transcript contains at least one `tool_use` entry with `mcp__ktrdr__get_available_indicators`
- [ ] Transcript contains at least one `tool_result` entry with real indicator data
- [ ] At least 3 known indicator types found in tool result (RSI, MACD, SMA, etc.)
- [ ] `cost_usd` > 0 or `turns` > 0 (real API usage confirmed)
- [ ] `AgentResult` fields (output, cost_usd, turns, transcript, session_id) are all populated

---

## Sanity Checks

**CRITICAL:** These catch false positives -- scenarios where the test "passes" but the system is actually broken.

- [ ] **Duration > 5 seconds** -- If the entire SDK invocation completes in < 5s, it likely failed silently or returned a cached/stub response. Real Claude Code SDK invocations with tool calls take 10-60 seconds.
- [ ] **Duration < 120 seconds** -- If it took > 2 minutes, something is hanging (MCP server startup, SDK connection, backend timeout). The `timeout 120` wrapper prevents infinite hangs.
- [ ] **Transcript has tool_use AND tool_result entries** -- If only `tool_use` is present but no `tool_result`, the MCP server accepted the call but didn't return data (broken MCP-to-backend connection).
- [ ] **Tool result content length > 100 chars** -- A very short tool result might be an error message ("connection refused") rather than real indicator data. Real indicator data is substantial (many indicators with descriptions).
- [ ] **Cost < $1.00** -- A single tool call with claude-sonnet-4-6 should cost < $0.10. Costs > $1 suggest runaway turns or retry loops.
- [ ] **Output does not contain "error" or "failed"** -- If Claude's output text mentions errors, the tool call may have failed and Claude is reporting the failure instead of succeeding.
- [ ] **Exit code 0, not 124** -- Exit code 124 means `timeout` killed the process. The invocation hung.

**Quick sanity check script:**
```bash
echo "$SDK_OUTPUT" | python3 -c "
import sys, json

data = json.load(sys.stdin)
cost = data.get('cost_usd', 0)
turns = data.get('turns', 0)
tlen = data.get('transcript_length', 0)
output = data.get('output', '').lower()

issues = []
if cost == 0 and turns == 0:
    issues.append('SANITY FAIL: Both cost and turns are 0')
if cost > 1.0:
    issues.append(f'SANITY FAIL: Cost too high: \${cost:.4f}')
if tlen == 0:
    issues.append('SANITY FAIL: Empty transcript')
if 'error' in output and 'indicators' not in output:
    issues.append('SANITY FAIL: Output contains error without indicator data')

tool_uses = [e for e in data.get('transcript', []) if e.get('type') == 'tool_use']
tool_results = [e for e in data.get('transcript', []) if e.get('type') == 'tool_result']
if tool_uses and not tool_results:
    issues.append('SANITY FAIL: Tool was called but no result returned')

if issues:
    for issue in issues:
        print(issue)
else:
    print('All sanity checks passed')
"
```

---

## Troubleshooting

**If Docker image build fails:**
- **Cause:** Missing source files, npm registry issues, or Python dependency conflicts
- **Cure:** Check build output for the exact error. Common issues: npm timeout for Claude Code CLI install (retry), missing `mcp/` directory in build context, `pyproject.toml` dependency conflicts. Ensure you are in the repo root when building.

**If "backend hostname not found" or DNS resolution fails:**
- **Cause:** The agent container is not on the same Docker network as the backend
- **Cure:** Verify the `--network` flag matches the compose network name. Run `docker network ls | grep ktrdr` to find the correct network name. The pattern is `<compose_project>_ktrdr-network`. Check that the sandbox is running: `uv run kinfra sandbox status`.

**If SDK invocation fails with auth error ("Please log in" / "Not logged in"):**
- **Cause:** No auth credentials available. On macOS, host `~/.claude` does NOT contain OAuth tokens (stored in Keychain).
- **Cure:** Use one of: (1) Named Docker volume provisioned via `claude login`, (2) `ANTHROPIC_API_KEY` env var. See `agent-memory/docker-compose.yml` for the named volume pattern.

**If MCP server fails to start (import error in SDK invocation):**
- **Cause:** Missing MCP dependencies or PYTHONPATH not including `/mcp`. The MCP server has its own deps (fastmcp, structlog, httpx) installed separately in the builder stage.
- **Cure:** Verify deps inside container: `docker run --rm ktrdr-agent:dev python -c "import fastmcp; import structlog; import httpx; print('OK')"`. If missing, rebuild image.

**If MCP tool call returns empty or error data:**
- **Cause:** MCP server cannot reach backend API at `http://backend:8000/api/v1`. The `KTRDR_API_URL` env var in the MCP server config must match the Docker network hostname.
- **Cure:** Test manually from inside the container: `docker run --rm --network <NETWORK> ktrdr-agent:dev curl -s http://backend:8000/api/v1/indicators/`. If this fails, the network configuration is wrong.

**If SDK invocation hangs (timeout after 120s):**
- **Cause:** Claude Code CLI blocking on permission prompt. The container must use `permission_mode="bypassPermissions"` and should NOT be run as root (Claude Code CLI refuses `--dangerously-skip-permissions` as root).
- **Cure:** Verify the container runs as user `agent` (not root): `docker run --rm ktrdr-agent:dev whoami` should return `agent`. Check that `permission_mode` is set correctly in the ClaudeAgentOptions.

**If CLAUDECODE env var error:**
- **Cause:** The SDK spawns a Claude Code CLI subprocess which sets `CLAUDECODE` in the environment. If this env var is present when the SDK starts, it blocks. The `ClaudeAgentRuntime._run()` method handles this by removing and restoring it.
- **Cure:** This should work automatically. If it fails, check that `os.environ.pop("CLAUDECODE", None)` is called before `sdk.query()`.

**If cost_usd is always 0:**
- **Cause:** Some SDK versions report cost differently. The `ResultMessage.total_cost_usd` field may be `None` instead of `0.0`.
- **Cure:** Check `turns > 0` as an alternative signal that the invocation actually ran. If both cost and turns are 0, the invocation did not complete.

**If transcript has only text entries (no tool_use):**
- **Cause:** Claude decided not to use the MCP tool. The `allowed_tools` list may not match the MCP tool name, or the prompt is ambiguous.
- **Cure:** Verify `allowed_tools=["mcp__ktrdr__get_available_indicators"]` matches the exact tool name. Check the output text -- Claude may explain why it didn't call the tool.

---

## Evidence to Capture

- Docker image name and size
- Docker network name used
- Claude Code CLI version inside container
- Full structured JSON output from SDK invocation (stdout)
- SDK invocation stderr logs (last 20 lines)
- Exit code and duration
- Transcript entries (all tool_use and tool_result types)
- MCP tool name format (should be `mcp__ktrdr__get_available_indicators`)
- Indicators found in tool result
- Cost and turns from AgentResult
- Any error messages from the invocation

---

## Notes for Implementation

- **This test costs real money.** Each invocation uses Claude Code API credits. The test is designed to be minimal (single tool call, constrained prompt) to keep costs under $0.10.
- **The container uses user `agent`, not root.** Claude Code CLI refuses `--dangerously-skip-permissions` as root. The Dockerfile creates a non-root `agent` user. Auth volume mounts to `/home/agent/.claude`.
- **MCP server runs as a stdio subprocess.** The SDK spawns it when processing the prompt. It is NOT a long-running service. The SDK starts the MCP process, sends tool calls, reads results, and the process exits when the SDK is done.
- **PYTHONPATH must include both `/app` and `/mcp`.** The MCP server at `/mcp/src/main.py` imports from `ktrdr` (at `/app/ktrdr/`) and from its own modules (at `/mcp/src/`). The env var in the MCP server config handles this.
- **The `mcp` pip package shadowing issue.** In development, ktrdr's local `mcp/` directory shadows the pip `mcp` package. Inside the Docker container this is NOT an issue because the MCP code lives at `/mcp/` (outside `/app/`) and PYTHONPATH is configured correctly.
- **Network name varies by sandbox.** Each sandbox worktree creates a Docker compose project with a unique name. The network name is `<project>_ktrdr-network`. Step 0 dynamically detects this. If detection fails, run `docker network ls | grep ktrdr` to find it manually.
- **Do NOT mount host `~/.claude` directly.** macOS stores OAuth tokens in the Keychain, not the filesystem. Host mounts also risk interfering with running CLI sessions. Use a named Docker volume provisioned via `claude login` (pattern from agent-memory).
- **The `timeout 120` wrapper is critical.** Without it, a hanging SDK invocation will block the test forever. 120 seconds is generous for a single tool call but fast enough to fail early on real problems.
