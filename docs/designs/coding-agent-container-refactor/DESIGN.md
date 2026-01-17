# Coding Agent Container Refactor: Design

## Problem Statement

The codebase has two unrelated concepts both called "sandbox":

1. **CLI sandbox** (`ktrdr sandbox`) - Testing environment providing isolated KTRDR stacks on dedicated ports
2. **Orchestrator sandbox** (`orchestrator/sandbox.py`) - Docker container where Claude Code runs autonomously

This naming collision causes confusion. Additionally, the orchestrator has its own container-based E2E testing infrastructure that duplicates what the CLI sandbox provides more robustly. We need to:
- Clarify naming so each concept has a distinct identity
- Consolidate to one testing infrastructure (CLI sandbox)
- Have the coding agent connect to CLI sandbox services for validation

## Goals

1. **Naming clarity**: "Sandbox" means one thing - the CLI testing environment
2. **Single testing infrastructure**: E2E validation uses CLI sandbox, not a separate container setup
3. **Clean separation of concerns**:
   - CodingAgentContainer = where Claude Code runs safely
   - CLI Sandbox = where KTRDR services run for testing
4. **Consistency**: Orchestrator's testing workflow mirrors Karl's manual dev workflow

## Non-Goals (Out of Scope)

- Changing how the CLI sandbox works (it's already robust)
- Modifying the orchestrator's task iteration logic
- Adding new features to either system
- Changing how Claude Code itself operates

## User Experience

### Orchestrator Workflow (Before)

```
Orchestrator
└── ktrdr-sandbox container
    ├── Claude Code runs here
    ├── Edits /workspace
    └── Spins up its own services (or unclear how E2E works)
```

### Orchestrator Workflow (After)

```
CLI Sandbox (ktrdr--orchestrator, port 8001)
├── KTRDR services (API, DB, workers)
└── Provides testing environment

CodingAgentContainer (separate container)
├── Claude Code runs here
├── Edits /workspace
├── Unit tests run locally
└── E2E tests hit CLI sandbox at localhost:8001
```

### Scenario: Orchestrator Runs a Milestone

1. Orchestrator checks/creates CLI sandbox (`ktrdr sandbox up` or similar)
2. For each task:
   - Orchestrator invokes Claude in CodingAgentContainer
   - Claude implements the task, runs unit tests locally
   - If task requires E2E validation, Claude hits CLI sandbox services
3. Milestone E2E validation runs against CLI sandbox
4. Results reported, escalations handled as before

### Scenario: Karl's Manual Dev Workflow (Unchanged)

```
~/dev/ktrdr--feature-x/           <-- CLI sandbox folder
├── .env.sandbox                  <-- ports configured
├── code files                    <-- Claude (interactive) edits directly
└── docker-compose services       <-- KTRDR stack

Karl runs Claude Code in terminal.
Tests run against sandbox services.
```

This remains unchanged. The refactor makes the orchestrator's workflow consistent with this pattern.

## Key Decisions

### Decision 1: Rename to "CodingAgentContainer"

**Choice:** `SandboxManager` → `CodingAgentContainer`, container name `ktrdr-sandbox` → `ktrdr-coding-agent`

**Alternatives considered:**
- `AgentContainer` - Too generic, could be any agent
- `ExecutionEnvironment` - Vague, doesn't convey the Claude/coding aspect
- `ClaudeContainer` - Too tied to specific AI, less future-proof

**Rationale:** "CodingAgentContainer" clearly describes purpose: it's where the coding agent (Claude) runs. The "Coding" prefix distinguishes it from other potential agents.

### Decision 2: CodingAgentContainer Connects to CLI Sandbox

**Choice:** The container connects to an external CLI sandbox for KTRDR services rather than running its own.

**Alternatives considered:**
- Container runs its own docker-compose services (current partial approach)
- Container uses host network directly

**Rationale:**
- CLI sandbox already provides robust, tested infrastructure for isolated KTRDR stacks
- Avoids duplicate testing infrastructure
- Mirrors Karl's dev workflow (code edits in one place, services in sandbox)
- Port isolation already solved by CLI sandbox's slot system

### Decision 3: CLI Sandbox Lifecycle Managed by Orchestrator

**Choice:** Orchestrator is responsible for ensuring a CLI sandbox exists and is running before invoking the coding agent.

**Alternatives considered:**
- CodingAgentContainer creates its own sandbox
- Assume sandbox always exists

**Rationale:** The orchestrator already manages the task loop; it makes sense for it to also manage the testing environment lifecycle. This keeps CodingAgentContainer focused on Claude execution only.

### Decision 4: Environment Variable for Sandbox Connection

**Choice:** CodingAgentContainer receives CLI sandbox connection info via environment variables (e.g., `KTRDR_API_URL=http://host.docker.internal:8001`)

**Alternatives considered:**
- Hardcoded ports
- Mount .env.sandbox file
- Service discovery

**Rationale:** Environment variables are simple, explicit, and work well with Docker. The orchestrator knows which sandbox it's using and can pass the appropriate values.

## Resolved Questions

1. **Sandbox naming for orchestrator**: Multiple dedicated CLI sandboxes: `ktrdr--orchestrator-1`, `ktrdr--orchestrator-2`, etc. This allows parallel orchestrator runs and isolation between different work streams.

2. **Workspace location**: CodingAgentContainer's `/workspace` maps directly to the CLI sandbox folder (e.g., `~/dev/ktrdr--orchestrator-1/`). This enables hot reload - Claude edits files, sandbox services pick up changes automatically. This mirrors Karl's manual workflow exactly.

3. **Cleanup policy**: CLI sandboxes are long-lived across multiple features/milestones. No automatic teardown. Sandboxes are reused (e.g., `ktrdr--orchestrator-1` handles many milestones over time).
