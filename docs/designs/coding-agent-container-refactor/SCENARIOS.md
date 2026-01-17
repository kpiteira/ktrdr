# Coding Agent Container Refactor: Validation Scenarios

**Date:** 2025-01-15
**Documents Validated:**
- Design: DESIGN.md
- Architecture: ARCHITECTURE.md

## Validation Summary

**Scenarios Validated:** 8 scenarios traced through architecture
**Critical Gaps Found:** 3, all resolved
**Interface Contracts:** Defined below

---

## Scenarios

### Happy Paths

1. **Orchestrator runs milestone with existing sandbox**
   - Orchestrator starts from code folder
   - Validates repo root, `.env.sandbox` exists, sandbox running
   - Starts CodingAgentContainer with volume mount
   - Claude executes tasks, reads API URL from `/workspace/.env.sandbox`
   - E2E tests pass against CLI sandbox services

2. **Claude edits code, hot reload picks it up**
   - Claude modifies file in `/workspace`
   - CLI sandbox services detect change, restart
   - E2E test validates the change works

3. **Multiple orchestrator instances in parallel**
   - `ktrdr--orchestrator-1` on port 8001
   - `ktrdr--orchestrator-2` on port 8002
   - Each has its own CodingAgentContainer
   - No interference between instances

### Error Paths

4. **Missing prerequisites**
   - Not in repo root → clear error: "Must run from repo root"
   - No `.env.sandbox` → clear error: "Run 'ktrdr sandbox init' first"
   - Sandbox not running → clear error: "Run 'ktrdr sandbox up' first"

5. **CLI sandbox fails to start**
   - `ktrdr sandbox up` fails (port conflict, Docker issue)
   - User sees error before orchestrator proceeds
   - (Sandbox startup is a prerequisite, not orchestrator's job)

6. **E2E test fails due to sandbox connectivity**
   - Claude can't reach sandbox API
   - Claude discovers and reports the issue
   - Orchestrator escalates as normal failure

### Edge Cases

7. **Sandbox running but services unhealthy**
   - `ktrdr sandbox status` says running
   - API returns 500s
   - Claude discovers during E2E test, reports failure
   - No pre-verification needed - Claude handles it

8. **Container already exists**
   - Previous `ktrdr-coding-agent` container exists
   - `start()` removes old container, creates fresh one
   - Clean state for each orchestrator run

---

## Key Decisions

These decisions came from the validation conversation:

### 1. Orchestrator uses current working directory
**Context:** How does orchestrator know which code folder to mount?
**Decision:** Orchestrator must be invoked from the code folder. Uses `pwd`.
**Trade-off:** Requires user to `cd` first, but eliminates path discovery complexity.

### 2. Prerequisites validated on startup
**Context:** What if sandbox isn't set up correctly?
**Decision:** Orchestrator validates three prerequisites before proceeding:
- `.git` exists (repo root)
- `.env.sandbox` exists (sandbox initialized)
- `ktrdr sandbox status` shows running
**Trade-off:** Orchestrator can't auto-fix issues, but errors are clear.

### 3. No environment variables for container
**Context:** How to pass connection info to CodingAgentContainer?
**Decision:** Mount code folder as `/workspace`. Claude reads `/workspace/.env.sandbox`.
**Trade-off:** Claude must know to read that file, but no env var management needed.

### 4. Docker run instead of docker-compose
**Context:** How to start CodingAgentContainer with dynamic volume mount?
**Decision:** Use `docker run -v {pwd}:/workspace` directly.
**Trade-off:** Loses docker-compose orchestration, but simpler and more explicit.

### 5. Remove docker socket mount
**Context:** Container previously had docker socket for starting services.
**Decision:** Remove it. CLI sandbox manages services externally.
**Trade-off:** Container can't manage Docker, but that's now a feature (security).

### 6. No health pre-verification
**Context:** Should orchestrator check API health before invoking Claude?
**Decision:** No. Let Claude discover and report issues.
**Rationale:** Health at start doesn't guarantee health throughout. Claude handles errors anyway.

### 7. Sandboxes are long-lived
**Context:** Should orchestrator create/destroy sandboxes?
**Decision:** No. Sandboxes (`ktrdr--orchestrator-1`, etc.) are pre-created and reused across milestones.
**Trade-off:** Manual setup required, but matches intended workflow.

---

## Interface Contracts

### Environment Validation

```python
def validate_environment() -> Path:
    """
    Validate orchestrator is in valid context.
    Returns code folder path (pwd) on success.
    Raises OrchestratorError with clear message on failure.
    """
    cwd = Path.cwd()

    # Check 1: Repo root
    if not (cwd / ".git").exists():
        raise OrchestratorError(
            "Must run from repo root. No .git found.\n"
            "cd to your ktrdr clone first."
        )

    # Check 2: Sandbox initialized
    if not (cwd / ".env.sandbox").exists():
        raise OrchestratorError(
            "No sandbox initialized in this folder.\n"
            "Run: ktrdr sandbox init"
        )

    # Check 3: Sandbox running
    result = subprocess.run(
        ["ktrdr", "sandbox", "status"],
        capture_output=True, text=True
    )
    if "running" not in result.stdout.lower():
        raise OrchestratorError(
            "Sandbox not running.\n"
            "Run: ktrdr sandbox up"
        )

    return cwd
```

### CodingAgentContainer

```python
@dataclass
class CodingAgentContainer:
    """Manages the Docker container where Claude Code runs."""

    container_name: str = "ktrdr-coding-agent"
    image_name: str = "ktrdr-coding-agent"

    async def start(self, code_folder: Path) -> None:
        """
        Start container with code folder mounted as /workspace.
        Removes existing container if present.
        """
        # Remove existing container if any
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True
        )

        # Start fresh container
        subprocess.run([
            "docker", "run", "-d",
            "--name", self.container_name,
            "-v", f"{code_folder}:/workspace",
            self.image_name
        ], check=True)

    async def stop(self) -> None:
        """Stop and remove the container."""
        subprocess.run(
            ["docker", "rm", "-f", self.container_name],
            capture_output=True
        )

    async def invoke_claude(
        self,
        prompt: str,
        max_turns: int = 50,
        timeout: int = 600,
    ) -> ClaudeResult:
        """
        Invoke Claude Code in the running container.
        Claude reads connection info from /workspace/.env.sandbox.
        """
        # docker exec ktrdr-coding-agent claude --json ...
```

### Reading Connection Info (Inside Container)

```bash
#!/bin/bash
# Inside container, Claude or scripts read connection info:

source /workspace/.env.sandbox

# Now have access to:
# - KTRDR_API_PORT (e.g., 8001)
# - KTRDR_DB_PORT (e.g., 5433)
# etc.

curl "http://host.docker.internal:${KTRDR_API_PORT}/health"
```

---

## Milestones

### Milestone 1: Rename (No Behavior Change)

**Goal:** All "sandbox" references in orchestrator context renamed to "coding-agent".

**Scope:**
- `orchestrator/sandbox.py` → `orchestrator/coding_agent_container.py`
- `SandboxManager` class → `CodingAgentContainer`
- `scripts/sandbox-*.sh` → `scripts/coding-agent-*.sh`
- `deploy/environments/sandbox/` → `deploy/environments/coding-agent/`
- `deploy/docker/sandbox/` → `deploy/docker/coding-agent/`
- Container name: `ktrdr-sandbox` → `ktrdr-coding-agent`
- Update imports, references, docs

**Verify:** Existing orchestrator tests pass with new names.

---

### Milestone 2: Environment Validation

**Goal:** Orchestrator validates prerequisites on startup with clear errors.

**Scope:**
- Add `validate_environment()` function
- Check 1: `.git` exists (repo root)
- Check 2: `.env.sandbox` exists (sandbox initialized)
- Check 3: `ktrdr sandbox status` shows running
- Wire into orchestrator startup
- Clear error messages for each failure

**Verify:**
- In valid context → proceeds normally
- Missing prerequisite → clear error explaining what to do

---

### Milestone 3: Docker Run with Volume Mount

**Goal:** CodingAgentContainer uses `docker run` with explicit volume mount. Remove unnecessary permissions.

**Scope:**
- `start()` method uses `docker run -v {pwd}:/workspace`
- Remove docker-compose dependency for container startup
- **Remove docker socket mount** - no longer needed
- Update Claude prompts to read from `/workspace/.env.sandbox`

**Security improvement:** Container can no longer control Docker on host. Reduced attack surface.

**Verify:** Claude in container can `curl` sandbox API using port from `.env.sandbox`.

---

### Milestone 4: Cleanup

**Goal:** Remove dead code, update docs, end-to-end validation.

**Scope:**
- Delete orphaned docker-compose files for coding-agent if unused
- Update `docs/architecture/autonomous-coding/*.md`
- Remove any remaining "sandbox" references in orchestrator context
- Full orchestrator flow test

**Verify:** Run simple milestone through orchestrator, confirm it uses CLI sandbox for E2E.

---

## Appendix: Terminology

To avoid future confusion:

| Term | Meaning |
|------|---------|
| **CLI Sandbox** | Testing environment created via `ktrdr sandbox init/up`. Provides isolated KTRDR services (API, DB, workers) on dedicated ports. |
| **Code folder** | Directory containing a clone of the repo. May or may not have a CLI sandbox initialized. |
| **CodingAgentContainer** | Docker container where Claude Code runs. Mounts code folder as `/workspace`. Does NOT run KTRDR services. |
| **Orchestrator** | Python process that manages milestone execution. Invokes Claude via CodingAgentContainer. |
