# Handoff — M2: AgentRuntime Protocol + Container Infrastructure

## Task 2.1 Complete: Port AgentRuntime Protocol

**What was ported from agent-memory:**
- `AgentResult` dataclass (output, cost_usd, turns, transcript, session_id)
- `AgentRuntimeConfig` dataclass (provider, model, max_budget_usd, max_turns)
- `AgentRuntime` Protocol with `invoke()` method

**What was stripped:**
- `PersistentAgentRuntime` — ktrdr agents are ephemeral per-operation
- `resume()` method — no session resumption needed
- `QueryResult` — only needed for persistent sessions
- `transcript_path` field — transcripts stored in operation results

## Task 2.2 Complete: Port ClaudeAgentRuntime

**Gotcha: mcp package shadowing** — `claude_agent_sdk` imports `from mcp.types ...` but ktrdr has a local `mcp/` directory that shadows it. Fix: lazy-import SDK via `_get_sdk()` helper. Tests mock this function. Not an issue inside Docker containers.

**Gotcha: CLIConnectionError re-raise** — `_run()` has a broad `except Exception` for error recovery. Must add `except sdk.CLIConnectionError: raise` before it, otherwise `invoke()` can't catch it for retry.

**Pattern: mock SDK factory** — Tests use `_make_mock_sdk()` which builds a SimpleNamespace with proper class types for isinstance checks. This avoids importing the real SDK in tests.

## Task 2.3 Complete: Adapt SafetyGuard

**Pattern: BudgetChecker Protocol** — Instead of importing BudgetTracker directly (which pulls settings), SafetyGuard uses a `BudgetChecker` Protocol matching `can_spend()`. Keeps safety.py dependency-free; tests use MagicMock.

**Pattern: fnmatch for tool wildcards** — `mcp__ktrdr__*` matches all ktrdr MCP tools via `fnmatch.fnmatch()`. More flexible than set membership.

## Task 2.4 Complete: Add Agent Worker Types

Straightforward — added `AGENT_DESIGN = "agent_design"` and `AGENT_ASSESSMENT = "agent_assessment"` to `WorkerType` enum in `ktrdr/api/models/workers.py`. Registry has no hardcoded type checks — new types work immediately.

## Task 2.5 Complete: Build ktrdr-agent Docker Image

**Location:** `deploy/docker/Dockerfile.agent` (not `docker/` — Dockerfiles live in `deploy/docker/`)

**Verified inside container:**
- Claude Code CLI 2.1.66, Python 3.13, Node.js 20.20
- `from ktrdr.agents.runtime.protocol import AgentRuntime` — OK
- `from claude_agent_sdk import ClaudeAgentOptions` — OK (no mcp shadowing inside container)
- `from src.server import KTRDRMCPServer` (from /mcp/) — OK

**Gotcha:** MCP server deps installed separately via `uv pip install` into the builder venv — MCP server has its own dependencies (fastmcp, structlog, httpx) not in ktrdr's pyproject.toml.

**Image size:** 1.34GB (Node.js + Claude Code CLI are the bulk)

## Task 2.6 Complete: E2E Validation

**E2E test:** `agents/sdk-invocation-in-container` — 7 steps, **PASSED**

**Gotcha: macOS Keychain OAuth not portable to Linux containers** — `~/.claude` mount alone is insufficient. Claude Code CLI on macOS stores OAuth tokens in the Keychain, not in `~/.claude.json`. Containers must use `ANTHROPIC_API_KEY` env var instead. `ClaudeAgentRuntime` accepts `api_key` param → injected into SDK options via `options.env["ANTHROPIC_API_KEY"]`.

**Gotcha: missing .env.sandbox in worktree** — gitignored `.env.sandbox` was missing from worktree (slot containers were running fine). Root cause: no auto-recovery when file is lost. Fix: `load_env_sandbox()` now checks slot registry and regenerates automatically.

**Verified full chain:** SDK invoke → MCP tool call (`mcp__ktrdr__get_available_indicators`) → backend API → 31 indicators returned. Cost: $0.08, turns: 2, duration: 20s.

**Next Milestone Notes (M3):**
- Agent container auth MUST use `ANTHROPIC_API_KEY`, not `~/.claude` mount
- Docker network for sandbox slots: `slot-<N>_ktrdr-network`
- Backend reachable as `http://backend:8000` (internal port) from agent container
