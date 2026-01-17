# Coding Agent Container Refactor: Architecture

## Overview

This refactor separates two concerns that were conflated under "sandbox":

1. **CodingAgentContainer**: Docker container providing isolated environment for Claude Code execution. No KTRDR services - purely for safe code editing and command execution.

2. **CLI Sandbox**: Testing environment providing isolated KTRDR stack (API, DB, workers) on dedicated ports. Already exists and works well.

The orchestrator coordinates both: it ensures a CLI sandbox is running, then invokes Claude in the CodingAgentContainer with connection info to reach the sandbox's services.

## Components

### Component: CodingAgentContainer (renamed from SandboxManager)

**Responsibility:** Execute Claude Code in isolated Docker container

**Location:** `orchestrator/coding_agent_container.py` (was `orchestrator/sandbox.py`)

**Dependencies:** Docker, Claude Code CLI

**What changes:**
- Class rename: `SandboxManager` → `CodingAgentContainer`
- Container name: `ktrdr-sandbox` → `ktrdr-coding-agent`
- Remove any service orchestration - this container only runs Claude
- Accept environment variables for CLI sandbox connection

```python
@dataclass
class CodingAgentContainer:
    """Manages the Docker container where Claude Code runs."""

    container_name: str = "ktrdr-coding-agent"
    workspace_path: str = "/workspace"

    async def start(self, sandbox_info: SandboxInfo) -> None:
        """Start the container with workspace mounted from sandbox path."""
        # Mounts sandbox_info.path as /workspace
        # Sets KTRDR_API_URL from sandbox_info.api_url

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        ...
    ) -> ClaudeResult:
        """Invoke Claude Code in the running container."""
```

### Component: CLI Sandbox Integration

**Responsibility:** Orchestrator manages CLI sandbox lifecycle for E2E testing

**Location:** `orchestrator/sandbox_manager.py` (NEW - wraps CLI sandbox commands)

**Dependencies:** `ktrdr sandbox` CLI commands

```python
class SandboxManager:
    """Manages CLI sandbox lifecycle for orchestrator testing needs."""

    def __init__(self, sandbox_name: str = "orchestrator"):
        self.sandbox_name = sandbox_name

    async def ensure_running(self) -> SandboxInfo:
        """Ensure CLI sandbox exists and is running. Returns connection info."""
        # Calls: ktrdr sandbox status / ktrdr sandbox up

    async def get_connection_info(self) -> SandboxInfo:
        """Get API URL, ports for the sandbox."""
        # Reads from .env.sandbox or sandbox status

    async def teardown(self) -> None:
        """Stop the CLI sandbox."""
        # Calls: ktrdr sandbox down
```

```python
@dataclass
class SandboxInfo:
    """Connection info for a CLI sandbox."""
    name: str             # e.g., "orchestrator-1"
    path: Path            # e.g., ~/dev/ktrdr--orchestrator-1/
    api_url: str          # e.g., "http://localhost:8001"
    db_port: int          # e.g., 5433
    grafana_port: int     # e.g., 3001
    jaeger_port: int      # e.g., 16687
```

### Component: Scripts (renamed)

**Location:** `scripts/`

| Before | After |
|--------|-------|
| `scripts/sandbox-init.sh` | `scripts/coding-agent-init.sh` |
| `scripts/sandbox-reset.sh` | `scripts/coding-agent-reset.sh` |
| `scripts/sandbox-shell.sh` | `scripts/coding-agent-shell.sh` |
| `scripts/sandbox-claude.sh` | `scripts/coding-agent-claude.sh` |

### Component: Docker Configuration (renamed)

**Location:** `deploy/environments/`

| Before | After |
|--------|-------|
| `deploy/environments/sandbox/` | `deploy/environments/coding-agent/` |
| `deploy/environments/sandbox/docker-compose.yml` | `deploy/environments/coding-agent/docker-compose.yml` |
| `deploy/docker/sandbox/Dockerfile` | `deploy/docker/coding-agent/Dockerfile` |

**Container changes:**
- Name: `ktrdr-sandbox` → `ktrdr-coding-agent`
- Remove docker socket mount (no longer needs to start services)
- Workspace mounted from CLI sandbox folder (enables hot reload)
- Add environment variable support for sandbox connection

```yaml
services:
  coding-agent:
    container_name: ktrdr-coding-agent
    environment:
      - KTRDR_API_URL=${KTRDR_API_URL:-http://host.docker.internal:8000}
      - KTRDR_DB_PORT=${KTRDR_DB_PORT:-5432}
    volumes:
      # Workspace IS the CLI sandbox folder - enables hot reload
      - ${SANDBOX_PATH:?required}:/workspace
    # No docker socket mount - doesn't manage services
```

**Key insight**: The CodingAgentContainer's `/workspace` is the CLI sandbox folder itself (e.g., `~/dev/ktrdr--orchestrator-1/`). When Claude edits files, the CLI sandbox's services pick up changes via hot reload. This mirrors Karl's manual workflow exactly - just containerized.

### Component: E2E Runner (simplified)

**Responsibility:** Run E2E tests against CLI sandbox services

**Location:** `orchestrator/runner.py` (existing, modified)

**Changes:**
- `run_e2e_tests()` receives sandbox connection info
- No longer assumes services run in same container
- Prompt to Claude includes explicit API URL

```python
async def run_e2e_tests(
    milestone_id: str,
    e2e_scenario: str,
    sandbox: CodingAgentContainer,
    sandbox_info: SandboxInfo,  # NEW: CLI sandbox connection
    config: OrchestratorConfig,
    tracer: Tracer,
) -> E2EResult:
    prompt = f"""
    Run E2E test for milestone {milestone_id}.

    KTRDR API is available at: {sandbox_info.api_url}

    Scenario:
    {e2e_scenario}

    ...
    """
```

## Data Flow

### Milestone Execution Flow

```
┌─────────────────┐
│   Orchestrator  │
└────────┬────────┘
         │
         │ 1. Ensure CLI sandbox running
         ▼
┌─────────────────┐
│  SandboxManager │──────► ktrdr sandbox up
└────────┬────────┘        (CLI sandbox on port 8001)
         │
         │ 2. Get connection info
         │    SandboxInfo(api_url="http://localhost:8001", ...)
         │
         │ 3. For each task: invoke Claude
         ▼
┌─────────────────────────┐
│  CodingAgentContainer   │
│  (ktrdr-coding-agent)   │
│                         │
│  ┌───────────────────┐  │
│  │   Claude Code     │  │
│  │   - Edit code     │  │
│  │   - Run tests     │──┼──► Unit tests run locally
│  │   - E2E tests     │──┼──► Hit CLI sandbox API
│  └───────────────────┘  │
└─────────────────────────┘
         │
         │ 4. Results back to orchestrator
         ▼
┌─────────────────┐
│   Orchestrator  │
│   - Log results │
│   - Escalate?   │
└─────────────────┘
```

### Container Network Access and Workspace Sharing

```
┌─────────────────────────────────────────────────────────────────────┐
│ Host Machine                                                        │
│                                                                     │
│  ~/dev/ktrdr--orchestrator-1/  ◄──────────────────────────────┐    │
│  (CLI Sandbox folder)                                          │    │
│  ├── .env.sandbox                                              │    │
│  ├── ktrdr/                                                    │    │
│  ├── tests/                    mounted as /workspace ──────────┤    │
│  └── ...                                                       │    │
│                                                                │    │
│  ┌──────────────────────┐    ┌─────────────────────────────┐  │    │
│  │ CLI Sandbox Services │    │ CodingAgentContainer        │  │    │
│  │ (docker-compose)     │    │                             │  │    │
│  │                      │    │  /workspace ◄───────────────┘  │    │
│  │  API :8001 ◄─────────┼────┼── (same files, hot reload)     │    │
│  │  DB  :5433           │    │                             │       │
│  │  ...                 │    │  Claude Code edits here     │       │
│  └──────────────────────┘    └─────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────┘
```

Both the CLI sandbox services and the CodingAgentContainer mount the same folder:
- CLI sandbox services mount it for hot reload (code changes → services restart)
- CodingAgentContainer mounts it as `/workspace` (Claude edits files here)

The CodingAgentContainer uses `host.docker.internal` to reach services bound to host ports by the CLI sandbox's docker-compose.

## File Changes Summary

### Renames

| Before | After |
|--------|-------|
| `orchestrator/sandbox.py` | `orchestrator/coding_agent_container.py` |
| `orchestrator/tests/test_sandbox.py` | `orchestrator/tests/test_coding_agent_container.py` |
| `scripts/sandbox-*.sh` | `scripts/coding-agent-*.sh` |
| `deploy/environments/sandbox/` | `deploy/environments/coding-agent/` |
| `deploy/docker/sandbox/` | `deploy/docker/coding-agent/` |

### New Files

| File | Purpose |
|------|---------|
| `orchestrator/sandbox_manager.py` | Wraps CLI sandbox commands for orchestrator use |
| `orchestrator/tests/test_sandbox_manager.py` | Tests for SandboxManager |

### Modified Files

| File | Changes |
|------|---------|
| `orchestrator/runner.py` | Accept `SandboxInfo`, pass to E2E tests |
| `orchestrator/milestone_runner.py` | Initialize SandboxManager, ensure sandbox running |
| `orchestrator/config.py` | Add sandbox name config option |
| `docs/architecture/autonomous-coding/*.md` | Update references |

### Deleted/Simplified

| File | Reason |
|------|--------|
| Docker socket mount in coding-agent compose | No longer manages services |

## Migration Path

### Phase 1: Rename (No Behavior Change)

1. Rename files and classes
2. Update all imports and references
3. Rename container and Docker artifacts
4. Update documentation
5. **Verify**: Existing orchestrator tests pass with new names

### Phase 2: Add SandboxManager

1. Create `orchestrator/sandbox_manager.py`
2. Add CLI sandbox lifecycle methods
3. Unit test with mocked CLI commands
4. **Verify**: Can call `ensure_running()` and get connection info

### Phase 3: Wire Integration

1. Modify `milestone_runner.py` to use SandboxManager
2. Pass `SandboxInfo` through to E2E tests
3. Update CodingAgentContainer to accept/pass sandbox URL
4. Remove docker socket mount from coding-agent container
5. **Verify**: E2E tests hit CLI sandbox services

### Phase 4: Cleanup

1. Remove any dead code from old approach
2. Update all documentation
3. Test full orchestrator flow end-to-end

## Verification Strategy

### CodingAgentContainer (Rename)
**Type:** Wiring/Rename
**Unit Test Focus:** Methods still work (exec, invoke_claude)
**Integration Test:** Container starts, Claude runs
**Smoke Test:** `./scripts/coding-agent-shell.sh` opens shell

### SandboxManager (New)
**Type:** External CLI integration
**Unit Test Focus:** Correct CLI commands generated
**Integration Test:** Actually creates/starts CLI sandbox
**Smoke Test:** `uv run python -c "from orchestrator.sandbox_manager import SandboxManager; ..."`

### E2E Integration
**Type:** Cross-component wiring
**Unit Test Focus:** Prompts include correct URLs
**Integration Test:** Claude in container can reach CLI sandbox API
**Smoke Test:** Run simple E2E scenario, verify hits correct port
