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

**Gotcha: container auth requires named Docker volume, not host mount** — `~/.claude` host mount doesn't work: macOS stores OAuth tokens in the Keychain (not filesystem), and mounting the host dir risks interfering with the running CLI session. Solution: use a **named Docker volume** (pattern from agent-memory):
1. `docker volume create ktrdr-agent-claude-auth`
2. Prepare dirs: `docker run --rm --user root -v ktrdr-agent-claude-auth:/home/agent/.claude ktrdr-agent:dev bash -c 'chown -R agent:agent /home/agent/.claude && mkdir -p /home/agent/.claude/{debug,backups,cache}'`
3. Run `claude login` interactively once: `docker run --rm -it -v ktrdr-agent-claude-auth:/home/agent/.claude ktrdr-agent:dev claude login`
4. docker-compose mounts `ktrdr-agent-claude-auth:/home/agent/.claude`
5. Auth persists in the volume across container rebuilds, isolated from host

Reference: `agent-memory/docker-compose.yml` uses `claude-config` named volume (`agent-memory-claude-auth`, external: true).

**Gotcha: `~/.claude.json` is separate from `~/.claude/`** — Claude CLI stores a backup in `~/.claude/backups/`. The entrypoint script (`agent-entrypoint.sh`) restores it automatically on container start. Without this: "Claude configuration file not found" warning (non-blocking but noisy).

**Gotcha: `McpStdioServerConfig` does not support `cwd`** — Use `bash -c "cd /mcp && python -m src.main"` instead. Passing `cwd` silently fails to start the MCP server — tools won't appear.

**Gotcha: missing .env.sandbox in worktree** — gitignored `.env.sandbox` was missing from worktree (slot containers were running fine). Root cause: no auto-recovery when file is lost. Fix: `load_env_sandbox()` now checks slot registry and regenerates automatically.

**Verified full chain (subscription auth):** SDK invoke → MCP tool call → backend API → 21 MCP tools loaded, 31 indicators returned. Cost: $0.10, turns: 1.

**Next Milestone Notes (M3):**
- Container auth: named Docker volume + `claude login` (one-time), NOT `~/.claude` host mount
- Fallback: `ANTHROPIC_API_KEY` env var works but uses API billing, not subscription
- Docker network for sandbox slots: `slot-<N>_ktrdr-network`
- Backend reachable as `http://backend:8000` (internal port) from agent container
- MCP config: use `bash -c "cd /mcp && python -m src.main"` — `McpStdioServerConfig` has no `cwd` field
- Entrypoint script (`agent-entrypoint.sh`) handles `.claude.json` restoration automatically
