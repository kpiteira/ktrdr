# SDK-Based Agent Workers — Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Evolution Harness                         │
│            (triggers, polls, scores, selects)                │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (trigger/poll)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (dispatcher)                     │
│  Worker Registry │ Operations Service │ Research Orchestrator│
└────────────┬─────────────┬──────────────┬───────────────────┘
             │             │              │
             ▼             ▼              ▼
      ┌─────────┐  ┌─────────┐    ┌─────────┐
      │ Design  │  │Training │    │Backtest │
      │ Agent   │  │ Worker  │    │ Worker  │
      │ Worker  │  │         │    │         │
      │(Claude  │  │(Python) │    │(Python) │
      │ Code +  │  │         │    │         │
      │  MCP)   │  │         │    │         │
      └─────────┘  └─────────┘    └─────────┘
      ┌─────────┐
      │Assess   │
      │ Agent   │
      │ Worker  │
      │(Claude  │
      │ Code +  │
      │  MCP)   │
      └─────────┘
  Agent workers: WorkerAPIBase, Docker, Claude Code + MCP
  Other workers: WorkerAPIBase, Docker, Python
  Research orchestrator: stays in backend (works well, defer extraction)
```

## Worker Types

### All Workers (Common Contract)

Every worker inherits `WorkerAPIBase` and follows this protocol:

| Step | Action | Detail |
|------|--------|--------|
| 1 | Register | POST `/api/v1/workers/register` with worker_type, endpoint_url, capabilities |
| 2 | Accept operation | POST `/{operation_type}/start` with `WorkerOperationMixin` (includes `task_id`) |
| 3 | Execute | Background task, non-blocking response |
| 4 | Report progress | `operations_service.update_operation_progress()` |
| 5 | Report result | `operations_service.complete_operation(result_summary={...})` |
| 6 | Health check | GET `/health` — backend monitors liveness |

### Design Agent Worker

**Purpose**: Receive a research brief, design a trading strategy using Claude Code with MCP access.

**Worker type**: `AGENT_DESIGN`
**Operation type**: `AGENT_DESIGN`

**Input** (via start endpoint):
```
task_id: str              # From backend (operation ID synchronization)
brief: str                # Natural language research brief (from genome)
symbol: str               # Target symbol (e.g., EURUSD)
timeframe: str            # Primary timeframe (e.g., 1h)
experiment_context: str   # Summary of past experiments (optional)
```

**Execution**:
1. Build Claude Code prompt from brief + context
2. Invoke Claude Code with ktrdr MCP config
3. Claude Code autonomously: explores data, designs strategy, validates iteratively
4. Extract strategy_name and strategy_path from session output
5. Report completion

**Output** (result_summary):
```
strategy_name: str        # Name of designed strategy
strategy_path: str        # Path to saved strategy YAML
input_tokens: int         # For tracking (from SDK cost reporting)
output_tokens: int        # For tracking
```

**Claude Code invocation** (via `claude-agent-sdk` Python package):
```python
from claude_agent_sdk import ClaudeAgentOptions, query

options = ClaudeAgentOptions(
    model="claude-sonnet-4-6",
    max_turns=25,
    max_budget_usd=2.0,
    allowed_tools=["mcp__ktrdr__*", "Read", "Glob", "Grep"],
    cwd="/app",
    permission_mode="bypassPermissions",
    system_prompt=DESIGN_SYSTEM_PROMPT,
    mcp_servers={
        "ktrdr": {
            "type": "stdio",
            "command": "python",
            "args": ["-m", "src.main"],
            "cwd": "/mcp",
            "env": {"KTRDR_API_URL": "http://backend:8000/api/v1"}
        }
    },
)

# Critical: remove CLAUDECODE env var to avoid blocking nested SDK calls
saved = os.environ.pop("CLAUDECODE", None)
try:
    async for message in query(prompt=user_prompt, options=options):
        # Process TextBlock, ToolUseBlock, ToolResultBlock
        ...
finally:
    if saved:
        os.environ["CLAUDECODE"] = saved
```

**Result extraction**: Parse SDK transcript for `ToolUseBlock` where tool name matches `mcp__ktrdr__save_strategy_config`. Extract `strategy_name` and `strategy_path` from the tool result. This is more reliable than text parsing — the MCP tool call is the agent's explicit "I'm done" signal.

### Assessment Agent Worker

**Purpose**: Assess a completed research cycle (strategy + training + backtest results).

**Worker type**: `AGENT_ASSESSMENT`
**Operation type**: `AGENT_ASSESSMENT`

**Input**:
```
task_id: str
strategy_name: str
strategy_config: dict     # Full strategy YAML content
training_metrics: dict    # Training accuracy, loss, etc.
backtest_results: dict    # Sharpe, drawdown, trades, etc.
experiment_history: str   # Past experiment summaries (optional)
```

**Execution**:
1. Build assessment prompt with all context
2. Invoke Claude Code with ktrdr MCP config
3. Claude Code reasons about results, may query additional metrics via MCP
4. Extract structured assessment from session output
5. Report completion

**Output** (result_summary):
```
verdict: str              # "promising" | "neutral" | "poor"
observations: list[str]   # Key observations
hypotheses: list[dict]    # New hypotheses generated
suggestions: list[str]    # Improvement suggestions
assessment_path: str      # Path to saved assessment JSON
```

### Research Orchestrator Worker

**Purpose**: Orchestrate the full research pipeline (design → train → backtest → assess).

**Worker type**: `AGENT_RESEARCH`
**Operation type**: `AGENT_RESEARCH`

**Input**:
```
task_id: str
model: str                # LLM model for agent phases
brief: str                # Research brief
symbol: str
timeframe: str
start_date: str
end_date: str
```

**Execution** (state machine, same as current AgentResearchWorker):
1. Dispatch design operation to Design Agent Worker via backend API
2. Poll until design complete, extract strategy_name
3. Dispatch training operation to Training Worker via backend API
4. Poll until training complete, extract model_path
5. Dispatch backtest operation to Backtest Worker via backend API
6. Poll until backtest complete, extract metrics
7. Dispatch assessment operation to Assessment Agent Worker via backend API
8. Poll until assessment complete
9. Report completion with aggregated results

**Output** (result_summary):
```
strategy_name: str
model_path: str
backtest_result: dict     # Full backtest metrics
assessment: dict          # Assessment verdict + observations
```

**Key difference from current**: This is Python-only. No LLM invocation. It's a state machine that calls other workers through the backend API. The only change is it runs in a container instead of the backend process.

## Docker Image: Claude Code Agent

Shared base image for Design Agent Worker and Assessment Agent Worker.

```
┌──────────────────────────────────────────┐
│          ktrdr-agent:dev                 │
│                                          │
│  Python 3.12 + Node.js 20 LTS           │
│  ├── Claude Code CLI (@anthropic-ai/    │
│  │   claude-code) + claude-agent-sdk    │
│  ├── ktrdr MCP server (Python, /mcp/)   │
│  ├── Worker HTTP server (FastAPI +      │
│  │   WorkerAPIBase)                      │
│  └── AgentRuntime (protocol + claude    │
│      implementation)                     │
│                                          │
│  Volumes (same shared dirs as all        │
│  other workers):                         │
│  ├── ~/.claude/ → /home/agent/.claude/  │
│  │   (subscription auth, read-only)      │
│  ├── ~/.ktrdr/shared/data → /app/data   │
│  ├── ~/.ktrdr/shared/models → /app/     │
│  │   models                              │
│  ├── ~/.ktrdr/shared/strategies →       │
│  │   /app/strategies                     │
│  └── ./memory → /app/memory             │
│      (experiment history, hypotheses)    │
│                                          │
│  Network: backend (same Docker network)  │
└──────────────────────────────────────────┘
```

Claude Code has access to all shared directories via its built-in filesystem tools (Read, Glob, Grep). The design agent can:
- Read past strategies from `/app/strategies/`
- Read experiment memory from `/app/memory/experiments/`
- Read hypothesis files from `/app/memory/hypotheses.yaml`

**Note**: Agents do NOT use Claude Code's Write tool for output artifacts. Strategy saving goes through `save_strategy_config` MCP tool (validates v3 format, then saves atomically). Assessment saving goes through `save_assessment` MCP tool. This prevents saving invalid artifacts. Experiment context is read-only via filesystem — no MCP tools needed for that.

### MCP Configuration

The MCP server config is passed directly to `ClaudeAgentOptions.mcp_servers` (no separate JSON file needed):

```python
mcp_servers = {
    "ktrdr": {
        "type": "stdio",
        "command": "python",
        "args": ["-m", "src.main"],
        "cwd": "/mcp",
        "env": {
            "KTRDR_API_URL": "http://backend:8000/api/v1",
            "LOG_LEVEL": "WARNING",  # Reduce noise on stderr
        }
    }
}
```

The ktrdr MCP server is Python-based (FastMCP, `mcp[cli]>=1.2.0`). It runs as a stdio subprocess of Claude Code inside the container. It connects to the backend via HTTP on the Docker network. No port exposure needed.

**Critical**: MCP server logging must go to stderr only. The stdio transport uses stdout for JSON-RPC — any logging to stdout breaks the protocol. The ktrdr MCP server already handles this correctly (structlog configured to stderr).

## Data Flow: Design Agent

```
Harness                     Backend                  Design Agent Worker
  │                           │                            │
  ├──POST /agent/trigger──────▶                            │
  │  {brief, model}           │                            │
  │                           ├──POST /designs/start──────▶│
  │                           │  {task_id, brief, symbol}  │
  │                           │                            │
  │                           │◀──{operation_id, started}──┤
  │◀──{operation_id}──────────┤                            │
  │                           │              ┌─────────────┤
  │                           │              │ Claude Code  │
  │                           │              │ + MCP loop:  │
  │                           │              │  explore data│
  │                           │              │  design strat│
  │                           │              │  validate    │
  │                           │              │  iterate     │
  │                           │              │  save final  │
  │                           │              └─────────────┤
  │                           │                            │
  │  GET /operations/{id}     │◀──complete_operation───────┤
  ├──────────────────────────▶│  {strategy_name, path}     │
  │◀──{status: completed}─────┤                            │
```

## Concurrency Model

- **Long-running containers**: Containers stay alive between operations. No startup/teardown per research.
- **Context clearing**: Each new operation starts a fresh Claude Code session (no `--resume`).
- **Multiple containers**: Scale by adding more containers (e.g., `design-agent-1`, `design-agent-2`).
- **Worker selection**: Backend's existing LRU round-robin selects least-recently-used worker.
- **Concurrency limit**: Controlled by number of deployed containers, not code limits.

## Docker Compose Addition

```yaml
design-agent-1:
  image: ktrdr-agent:dev
  restart: unless-stopped
  stop_grace_period: 60s
  environment:
    - KTRDR_WORKER_TYPE=agent_design
    - KTRDR_WORKER_PORT=5010
    - KTRDR_WORKER_PUBLIC_BASE_URL=http://design-agent-1:5010
    - KTRDR_API_CLIENT_BASE_URL=http://backend:8000/api/v1
    - KTRDR_MCP_BACKEND_URL=http://backend:8000/api/v1
  volumes:
    - ${HOME}/.claude:/home/agent/.claude:ro
    - ./strategies:/app/strategies
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:5010/health"]
    interval: 30s
    timeout: 10s
    retries: 3
  depends_on:
    - backend
  command: /app/.venv/bin/uvicorn ktrdr.agents.design_agent_worker:app --host 0.0.0.0 --port 5010

design-agent-2:
  <<: *design-agent-template  # Scale by duplicating
  environment:
    - KTRDR_WORKER_PORT=5011
    - KTRDR_WORKER_PUBLIC_BASE_URL=http://design-agent-2:5011
```

## Provider Abstraction (AgentRuntime Protocol)

Ported from agent-memory's production implementation. All agent worker code programs against the protocol, not a specific SDK.

```python
@runtime_checkable
class AgentRuntime(Protocol):
    """Abstract interface for any agent backend (Claude, Copilot, etc.)."""

    async def invoke(
        self, prompt: str, *,
        model: str | None = None,
        max_turns: int = 10,
        max_budget_usd: float = 1.0,
        allowed_tools: list[str] | None = None,
        cwd: str | None = None,
        system_prompt: str | None = None,
        mcp_servers: dict[str, object] | None = None,
    ) -> AgentResult: ...

@dataclass
class AgentResult:
    output: str
    cost_usd: float
    turns: int
    transcript: list[dict]    # Standardized: {role, type, content, ...}
    session_id: str | None
```

```
ktrdr/agents/runtime/
├── protocol.py          # AgentRuntime Protocol + AgentResult (provider-agnostic)
├── claude.py            # ClaudeAgentRuntime (claude-agent-sdk)
├── safety.py            # SafetyGuard (budget cap, tool allowlist)
└── copilot.py           # CopilotAgentRuntime (future, single-file addition)
```

**Design and Assessment workers call `runtime.invoke()`**. They never import `claude_agent_sdk` directly. Adding Copilot support means adding `copilot.py` and a config toggle — worker code stays identical.

## Error Handling

| Failure Mode | Detection | Recovery |
|-------------|-----------|----------|
| Claude Code session hangs | Timeout (configurable, default 5 min for design, 3 min for assessment) | Kill session, fail operation, orchestrator retries |
| Claude Code produces no strategy | Result parsing finds no strategy_name | Fail operation with descriptive error |
| MCP server can't reach backend | MCP tool calls return errors | Claude Code sees errors, may retry or fail |
| Auth credentials expired | Claude Code exits with auth error | Fail operation, alert for credential refresh |
| Container OOM | Docker healthcheck fails | Docker restarts container, re-registers |

## Migration Path

The migration is incremental. Each milestone adds capability without removing the old path until M4:

1. **M0**: MCP server gap-fill. Register missing tools, add `save_assessment`. Old agent code untouched.
2. **M1**: AgentRuntime protocol + container image. Foundation verified. Old agent code untouched.
3. **M2**: Design Agent Worker container. Exists alongside old in-backend design. Can test both.
4. **M3**: Assessment Agent Worker container. Exists alongside old in-backend assessment.
5. **M4**: Research orchestrator dispatches to container workers. Old AnthropicInvoker path removed. Evolution uses container workers end-to-end.

At each step through M3, the old path still works. The evolution harness doesn't change — it triggers via the backend API as before. The backend's research orchestrator stays in-process but dispatches to the new container workers instead of calling AnthropicInvoker.
