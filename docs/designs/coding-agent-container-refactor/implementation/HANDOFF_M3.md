# Milestone 3 Handoff: Docker Run with Volume Mount

## Task 3.1 Complete: Update CodingAgentContainer.start() to use docker run

**Summary:** Added `start()` and `stop()` async methods to CodingAgentContainer. Updated default container_name to `ktrdr-coding-agent` and added `image_name` attribute.

### Implementation Notes
- `start(code_folder: Path)` runs `docker rm -f` then `docker run -d -v {path}:/workspace ...`
- `stop()` runs `docker rm -f`
- Both methods raise `CodingAgentError` on failure
- The rm before start silently ignores errors (container may not exist)

### Docker Command Used
```bash
docker run -d --name ktrdr-coding-agent \
  -v /path/to/code:/workspace \
  --add-host=host.docker.internal:host-gateway \
  ktrdr-coding-agent:latest
```

### Next Task Notes (3.2)
- Task 3.2 modifies `docker-compose.yml` to remove docker socket mount
- The compose file is at `deploy/environments/coding-agent/docker-compose.yml`
- Remove workspace volume, keep claude-credentials and shared data volumes

---

## Task 3.2 Complete: Update docker-compose.yml to remove docker socket

**Summary:** Removed docker socket mount and workspace volume. Updated header comments to explain the file is for building only.

### Changes Made
- Removed `/var/run/docker.sock:/var/run/docker.sock` mount
- Removed `coding-agent-workspace:/workspace` mount and volume definition
- Updated header comments: "This file is used for BUILDING THE IMAGE only"
- Added example `docker run` command in comments

### Volumes Kept
- `coding-agent-claude-credentials` — Claude Code credentials
- `coding-agent-models`, `coding-agent-strategies`, `coding-agent-logs` — Persistent data
- Shared data mount (`${HOME}/Documents/ktrdr-shared/data:/shared/data:ro`)

### Next Task Notes (3.3)
- Task 3.3 updates shell scripts to match new container lifecycle
- `scripts/coding-agent-init.sh` — Should only build image, not start container
- `scripts/coding-agent-shell.sh` — Should check if container is running first

---

## Task 3.3 Complete: Update scripts to use docker run

**Summary:** Simplified init script to only build image. Updated shell script with helpful error message including docker run example.

### coding-agent-init.sh Changes
- Removed: Container startup (`docker compose up`)
- Removed: Repository cloning (workspace now mounted at runtime)
- Removed: Workspace ownership fix, env directories, verification steps
- Removed: Claude Code and GitHub CLI authentication checks
- Kept: Docker prerequisite checks, image build, shared data directory creation

### coding-agent-shell.sh Changes
- Updated error message to explain orchestrator starts container
- Added example `docker run` command in error output
- Added pointer to init script for image building

---

## Task 3.4 Complete: Wire code_folder through orchestrator

**Summary:** Wired container lifecycle (start/stop) through both milestone_runner.py and cli.py with try/finally for guaranteed cleanup.

### milestone_runner.py Changes
- Get `code_folder = validate_environment()` before container creation
- Call `await container.start(code_folder)` before task execution
- Wrap all task execution in try/finally with `await container.stop()` in finally
- Container stops regardless of success or failure

### cli.py Changes
- Same pattern: validate → start → try/finally with stop
- Applied to single task execution flow

### Test Updates
- Created `create_mock_container_class()` helper for AsyncMock start/stop methods
- Updated all test patches to use the helper and mock `validate_environment`
- 32 milestone_runner tests passing
- 53 CLI tests passing

### Implementation Pattern
```python
code_folder = validate_environment()
container = CodingAgentContainer()
await container.start(code_folder)
try:
    # ... task execution ...
finally:
    await container.stop()
```

### Next Task Notes (3.5)
- Task 3.5 updates tests for new container lifecycle
- Already completed as part of 3.4 implementation
