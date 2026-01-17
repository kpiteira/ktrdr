---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Docker Run with Volume Mount

**Branch:** `docs/coding-agent-container-refactor`
**Builds on:** Milestone 2 (Environment Validation)
**E2E Test:** Claude in container can curl sandbox API using port from .env.sandbox

## Goal

CodingAgentContainer uses `docker run` with explicit volume mount. Remove docker socket and named volume for workspace. Container mounts code folder directly, reads connection info from `/workspace/.env.sandbox`.

---

## Task 3.1: Update CodingAgentContainer.start() to use docker run

**File(s):** `orchestrator/coding_agent_container.py`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** External, Configuration

**Description:**
Add `start()` method that uses `docker run` with volume mount. Add `stop()` method. Update default container_name to `ktrdr-coding-agent`. Add `image_name` attribute. The `start()` method accepts a `code_folder: Path` parameter, removes any existing container, then starts fresh with the code folder mounted as `/workspace`.

**Implementation Notes:**
- Add `image_name: str = "ktrdr-coding-agent:latest"` as class attribute
- Change `container_name` default from `ktrdr-sandbox` to `ktrdr-coding-agent`
- `start()` runs: `docker rm -f {container_name}` then `docker run -d --name {container_name} -v {code_folder}:/workspace --add-host=host.docker.internal:host-gateway {image_name}`
- `stop()` runs: `docker rm -f {container_name}`
- Raise `CodingAgentError` on docker failure

**Testing Requirements:**

*Unit Tests:*
- [ ] start() calls docker run with correct volume mount
- [ ] start() removes existing container first
- [ ] start() raises CodingAgentError on failure
- [ ] stop() removes container

*Integration Tests:*
- [ ] Container actually starts (requires Docker)

*Smoke Test:*
```bash
python -c "
from pathlib import Path
from orchestrator.coding_agent_container import CodingAgentContainer
import asyncio
c = CodingAgentContainer()
asyncio.run(c.start(Path.cwd()))
print('Started')
asyncio.run(c.stop())
print('Stopped')
"
```

**Acceptance Criteria:**
- [ ] `start()` accepts `code_folder: Path` parameter
- [ ] Uses `docker run` with `-v` flag for volume mount
- [ ] Includes `--add-host=host.docker.internal:host-gateway`
- [ ] `stop()` removes container
- [ ] Raises `CodingAgentError` on failure
- [ ] Default container_name is `ktrdr-coding-agent`

---

## Task 3.2: Update docker-compose.yml to remove docker socket

**File(s):** `deploy/environments/coding-agent/docker-compose.yml`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Remove the docker socket mount and named workspace volume. The compose file is now only used for building the image. Add comments explaining this. Keep Claude credentials volume and shared data mount.

**Implementation Notes:**
- Remove: `- /var/run/docker.sock:/var/run/docker.sock`
- Remove: `- sandbox-workspace:/workspace` (now named `coding-agent-workspace`)
- Remove the workspace volume definition
- Keep: `- coding-agent-claude-credentials:/home/ubuntu/.claude`
- Keep: `- ${HOME}/Documents/ktrdr-shared/data:/shared/data:ro`
- Update header comments to explain file is for building only

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A for Docker config

*Integration Tests:*
- [ ] Image still builds successfully

*Smoke Test:*
```bash
docker compose -f deploy/environments/coding-agent/docker-compose.yml config | grep -c "docker.sock"
# Should return 0 (no docker socket mount)
```

**Acceptance Criteria:**
- [ ] Docker socket mount removed
- [ ] Named workspace volume removed
- [ ] Comments explain file is for image building only
- [ ] Image builds: `docker compose -f deploy/environments/coding-agent/docker-compose.yml build`

---

## Task 3.3: Update scripts to use docker run

**File(s):** `scripts/coding-agent-init.sh`, `scripts/coding-agent-shell.sh`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Update init script to only build the image (not start container). Update shell script to check if container is running and give helpful error if not.

**Implementation Notes:**
- coding-agent-init.sh: Remove container startup, just build image
- coding-agent-init.sh: Update instructions to explain orchestrator starts container
- coding-agent-shell.sh: Check `docker ps` for container, error if not running
- coding-agent-shell.sh: Provide example docker run command in error message

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A for scripts

*Integration Tests:*
- [ ] N/A for scripts

*Smoke Test:*
```bash
# After init (image built), shell should error if no container:
docker rm -f ktrdr-coding-agent 2>/dev/null
./scripts/coding-agent-shell.sh 2>&1 | grep -i "not running"
# Should show error about container not running
```

**Acceptance Criteria:**
- [ ] coding-agent-init.sh builds image but doesn't start container
- [ ] coding-agent-shell.sh errors clearly when container not running
- [ ] Error message includes example docker run command

---

## Task 3.4: Wire code_folder through orchestrator

**File(s):** `orchestrator/milestone_runner.py`, `orchestrator/cli.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI, Cross-Component

**Description:**
Pass the `code_folder` from `validate_environment()` to `CodingAgentContainer.start()`. Add try/finally to ensure container is stopped. Update the flow to: validate → start container → run tasks → stop container.

**Implementation Notes:**
- In milestone_runner.py: `code_folder = validate_environment()` then `await container.start(code_folder)`
- Wrap task execution in try/finally with `await container.stop()` in finally
- In cli.py: similar pattern for any commands that use the container
- Update tests to mock both `validate_environment` and `container.start()`

**Testing Requirements:**

*Unit Tests:*
- [ ] code_folder passed to container.start()
- [ ] container.stop() called in finally block
- [ ] Tests mock start() and stop()

*Integration Tests:*
- [ ] Wiring test: container started with correct path

*Smoke Test:*
```bash
# Verify the wiring by checking container mounts after orchestrator starts it
# (manual verification during development)
```

**Acceptance Criteria:**
- [ ] `code_folder` passed to `container.start()`
- [ ] Container stopped in finally block (cleanup)
- [ ] Tests updated to mock `start()` and `stop()`
- [ ] No resource leaks (container always stopped)

---

## Task 3.5: Update tests for new container lifecycle

**File(s):** `orchestrator/tests/test_coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Add tests for `start()` and `stop()` methods. Test volume mount arguments, container removal before start, error handling, and stop cleanup.

**Implementation Notes:**
- Use `unittest.mock.patch` for subprocess.run
- Test that docker run includes `-v {path}:/workspace`
- Test that docker rm -f is called before docker run
- Test CodingAgentError raised on non-zero exit
- Follow existing test patterns in the file

**Testing Requirements:**

*Unit Tests:*
- [ ] test_start_runs_docker_with_volume_mount
- [ ] test_start_removes_existing_container_first
- [ ] test_start_raises_on_failure
- [ ] test_stop_removes_container

*Integration Tests:*
- [ ] N/A (mocked)

*Smoke Test:*
```bash
cd orchestrator && uv run pytest tests/test_coding_agent_container.py -v -k "start or stop"
```

**Acceptance Criteria:**
- [ ] All 4 lifecycle tests implemented and passing
- [ ] Tests verify correct docker arguments
- [ ] Tests verify error handling
- [ ] Tests run fast with mocking

---

## Milestone 3 Verification

### E2E Test Scenario

**Purpose:** Verify container mounts code folder and can reach CLI sandbox services
**Duration:** ~1 minute
**Prerequisites:** Docker running, coding-agent image built, CLI sandbox running

**Test Steps:**

```bash
# 1. Setup: Ensure sandbox running
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up

# 2. Start container with volume mount
docker run -d --name ktrdr-coding-agent \
  -v $(pwd):/workspace \
  --add-host=host.docker.internal:host-gateway \
  ktrdr-coding-agent:latest

# 3. Verify .env.sandbox is accessible
docker exec ktrdr-coding-agent cat /workspace/.env.sandbox
# Expected: File contents displayed

# 4. Verify can reach sandbox API
docker exec ktrdr-coding-agent bash -c 'source /workspace/.env.sandbox && curl -s http://host.docker.internal:${KTRDR_API_PORT}/health'
# Expected: Health response from API

# 5. Verify no docker socket mounted
docker inspect ktrdr-coding-agent --format '{{range .Mounts}}{{.Source}}{{"\n"}}{{end}}' | grep -c docker.sock
# Expected: 0 (no docker socket)

# 6. Cleanup
docker rm -f ktrdr-coding-agent
```

**Success Criteria:**
- [ ] Container starts with code folder mounted as `/workspace`
- [ ] `/workspace/.env.sandbox` is readable in container
- [ ] Container can reach CLI sandbox API via host.docker.internal
- [ ] No docker.sock mount present (security)

### Completion Checklist

- [ ] All 5 tasks complete and committed
- [ ] Unit tests pass: `cd orchestrator && uv run pytest tests/test_coding_agent_container.py -v`
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] E2E test passes (above)
- [ ] Previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Commit with message: "feat(orchestrator): use docker run with volume mount, remove docker socket"
