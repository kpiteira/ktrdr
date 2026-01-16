---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Docker Run with Volume Mount

## Goal

CodingAgentContainer uses `docker run` with explicit volume mount. Remove docker socket and named volume for workspace. Container mounts code folder directly.

## E2E Validation

**Test:** Claude in container can curl sandbox API using port from `.env.sandbox`

```bash
# Prerequisites: In code folder with sandbox running
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up

# Start container with new approach
docker run -d --name ktrdr-coding-agent \
  -v $(pwd):/workspace \
  --add-host=host.docker.internal:host-gateway \
  ktrdr-coding-agent:latest

# Verify .env.sandbox is accessible
docker exec ktrdr-coding-agent cat /workspace/.env.sandbox

# Verify can reach sandbox API (port from .env.sandbox)
docker exec ktrdr-coding-agent bash -c 'source /workspace/.env.sandbox && curl -s http://host.docker.internal:${KTRDR_API_PORT}/health'

# Cleanup
docker rm -f ktrdr-coding-agent
```

**Success Criteria:**
- [ ] Container starts with code folder mounted as `/workspace`
- [ ] `/workspace/.env.sandbox` is readable
- [ ] Can reach CLI sandbox API from inside container
- [ ] No docker socket mounted (verify with `docker inspect`)

---

## Task 3.1: Update CodingAgentContainer.start() to use docker run

**File:** `orchestrator/coding_agent_container.py`
**Type:** CODING
**Estimated time:** 45 min

**Description:**
Replace the current container startup (which assumes container already exists) with explicit `docker run` that mounts the code folder.

**Changes:**

```python
async def start(self, code_folder: Path) -> None:
    """
    Start container with code folder mounted as /workspace.
    Removes existing container if present.

    Args:
        code_folder: Path to the code folder (repo root with .env.sandbox)
    """
    # Remove existing container if any
    subprocess.run(
        ["docker", "rm", "-f", self.container_name],
        capture_output=True,
    )

    # Start fresh container with volume mount
    result = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", self.container_name,
            "-v", f"{code_folder}:/workspace",
            "--add-host=host.docker.internal:host-gateway",
            self.image_name,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise CodingAgentError(f"Failed to start container: {result.stderr}")

async def stop(self) -> None:
    """Stop and remove the container."""
    subprocess.run(
        ["docker", "rm", "-f", self.container_name],
        capture_output=True,
    )
```

**Also update:**
- Add `image_name: str = "ktrdr-coding-agent:latest"` as class attribute
- Update `container_name` default to `"ktrdr-coding-agent"`

**Acceptance Criteria:**
- [ ] `start()` accepts `code_folder: Path` parameter
- [ ] Uses `docker run` with `-v` flag
- [ ] Includes `--add-host` for host.docker.internal
- [ ] `stop()` removes container
- [ ] Raises `CodingAgentError` on failure

---

## Task 3.2: Update docker-compose.yml to remove docker socket

**File:** `deploy/environments/coding-agent/docker-compose.yml`
**Type:** CODING
**Estimated time:** 20 min

**Description:**
Remove the docker socket mount and named workspace volume. The compose file is now only used for building the image, not for running the container.

**Changes:**

```yaml
services:
  coding-agent:
    build:
      context: ../../../
      dockerfile: deploy/docker/coding-agent/Dockerfile
    image: ktrdr-coding-agent:latest
    # Container is started via `docker run`, not compose
    # This file is kept for building the image only

    # REMOVED: Docker socket mount (security improvement)
    # REMOVED: Named workspace volume (now mounts code folder directly)

    volumes:
      # Keep shared data mount (read-only)
      - ${HOME}/Documents/ktrdr-shared/data:/shared/data:ro
      # Keep Claude credentials persistent
      - coding-agent-claude-credentials:/home/ubuntu/.claude

    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  coding-agent-claude-credentials:
    name: ktrdr-coding-agent-claude-credentials
```

**Acceptance Criteria:**
- [ ] Docker socket mount removed
- [ ] Named workspace volume removed
- [ ] Can still build image: `docker compose build`
- [ ] Comments explain this is for image building only

---

## Task 3.3: Update scripts to use docker run

**Files:** `scripts/coding-agent-init.sh`, `scripts/coding-agent-shell.sh`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Update scripts to match the new container startup approach.

**Changes in coding-agent-init.sh:**
- Build image using docker compose (for the build context)
- Don't start container (that's orchestrator's job now)
- Update comments to explain new workflow

**Changes in coding-agent-shell.sh:**
- Check if container is running, if not give helpful error
- Or: start container with current directory as workspace

```bash
#!/bin/bash
# Interactive shell in the coding agent container
# Usage: ./scripts/coding-agent-shell.sh

CONTAINER_NAME="ktrdr-coding-agent"

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Container not running."
    echo "Start it with: docker run -d --name $CONTAINER_NAME -v \$(pwd):/workspace ktrdr-coding-agent:latest"
    exit 1
fi

docker exec -it -u ubuntu -w /workspace "$CONTAINER_NAME" bash
```

**Acceptance Criteria:**
- [ ] Scripts work with new startup approach
- [ ] Clear error messages when container not running
- [ ] `coding-agent-init.sh` builds image but doesn't start container

---

## Task 3.4: Wire code_folder through orchestrator

**Files:** `orchestrator/milestone_runner.py`, `orchestrator/cli.py`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Pass the `code_folder` from `validate_environment()` to `CodingAgentContainer.start()`.

**Changes in milestone_runner.py:**

```python
async def run_milestone(...):
    code_folder = validate_environment()
    container = CodingAgentContainer(...)

    # Start container with code folder mounted
    await container.start(code_folder)

    try:
        # ... rest of milestone execution
    finally:
        await container.stop()
```

**Changes in cli.py:**

```python
# Similar pattern - start container before invoking Claude
```

**Acceptance Criteria:**
- [ ] `code_folder` passed to `container.start()`
- [ ] Container stopped in finally block
- [ ] Tests updated to mock `start()` and `stop()`

---

## Task 3.5: Update tests for new container lifecycle

**File:** `orchestrator/tests/test_coding_agent_container.py`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Update tests for the new `start()` and `stop()` methods.

**New tests:**

```python
class TestContainerLifecycle:
    """Test container start/stop methods."""

    @pytest.mark.asyncio
    async def test_start_runs_docker_with_volume_mount(self, tmp_path):
        """start() should run docker with code folder mounted."""
        container = CodingAgentContainer()

        with patch("orchestrator.coding_agent_container.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            await container.start(tmp_path)

        # Check docker run was called with correct args
        calls = mock_run.call_args_list
        docker_run_call = [c for c in calls if "run" in c[0][0]][0]
        assert "-v" in docker_run_call[0][0]
        assert f"{tmp_path}:/workspace" in docker_run_call[0][0]

    @pytest.mark.asyncio
    async def test_start_removes_existing_container_first(self, tmp_path):
        """start() should remove any existing container."""
        container = CodingAgentContainer()

        with patch("orchestrator.coding_agent_container.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            await container.start(tmp_path)

        # First call should be docker rm
        first_call = mock_run.call_args_list[0]
        assert "rm" in first_call[0][0]
        assert "-f" in first_call[0][0]

    @pytest.mark.asyncio
    async def test_start_raises_on_failure(self, tmp_path):
        """start() should raise CodingAgentError on docker failure."""
        container = CodingAgentContainer()

        with patch("orchestrator.coding_agent_container.subprocess.run") as mock_run:
            # First call (rm) succeeds, second (run) fails
            mock_run.side_effect = [
                Mock(returncode=0),
                Mock(returncode=1, stderr="Error: port already in use"),
            ]

            with pytest.raises(CodingAgentError) as exc_info:
                await container.start(tmp_path)

            assert "port already in use" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_stop_removes_container(self):
        """stop() should remove the container."""
        container = CodingAgentContainer()

        with patch("orchestrator.coding_agent_container.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)
            await container.stop()

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "rm" in call_args
        assert "-f" in call_args
```

**Acceptance Criteria:**
- [ ] Tests for `start()` with volume mount
- [ ] Tests for container removal before start
- [ ] Tests for error handling
- [ ] Tests for `stop()`
- [ ] All tests pass

---

## Milestone 3 Completion Checklist

- [ ] All 5 tasks complete
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] Manual test: container mounts code folder correctly
- [ ] Manual test: can reach sandbox API from container
- [ ] `docker inspect ktrdr-coding-agent` shows no docker.sock mount
- [ ] Quality gates pass: `make quality`
- [ ] Commit with message: "feat(orchestrator): use docker run with volume mount, remove docker socket"
