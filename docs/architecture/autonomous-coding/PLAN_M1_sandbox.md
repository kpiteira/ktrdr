# Milestone 1: Sandbox Works

**Branch:** `feature/orchestrator-m1-sandbox`
**Builds on:** Nothing (foundation)
**Estimated Tasks:** 7

---

## Capability

Claude Code runs in isolated Docker container with access to shared market data and environment-local models/strategies. Workspace resets to clean code state while preserving trained artifacts.

---

## E2E Test Scenario

```bash
# Setup
./scripts/sandbox-init.sh
docker compose -f deploy/environments/sandbox/docker-compose.yml up -d

# 1. Verify Claude Code runs
docker exec ktrdr-sandbox claude -p "echo hello" --output-format json
# Expect: JSON with result

# 2. Verify .claude/ commands available (tracked in git, from clone)
docker exec ktrdr-sandbox ls /workspace/.claude/commands/
# Expect: ktask.md, etc.

# 3. Verify shared data accessible
docker exec ktrdr-sandbox ls /shared/data/ | head -3
# Expect: EURUSD_1d.csv, etc.

# 4. Verify env-local volumes work
docker exec ktrdr-sandbox touch /env/models/test-model.pt
docker exec ktrdr-sandbox touch /env/strategies/test-strategy.yaml
docker exec ktrdr-sandbox ls /env/models/ /env/strategies/
# Expect: files exist

# 5. Make a workspace change
docker exec ktrdr-sandbox bash -c "echo 'dirty' > /workspace/dirty.txt"

# 6. Reset workspace
./scripts/sandbox-reset.sh

# 7. Verify reset behavior
docker exec ktrdr-sandbox cat /workspace/dirty.txt        # Should FAIL (cleared)
docker exec ktrdr-sandbox ls /env/models/test-model.pt    # Should EXIST (kept)
docker exec ktrdr-sandbox ls /env/strategies/             # Should EXIST (kept)
docker exec ktrdr-sandbox ls /shared/data/ | head -1      # Should EXIST (RO mount)

# 8. Verify docker-in-docker works (sandbox can run ktrdr services)
docker exec ktrdr-sandbox docker ps
# Expect: Can see host Docker containers
```

---

## Tasks

### Task 1.1: Create Sandbox Dockerfile

**File:** `deploy/docker/sandbox/Dockerfile`
**Type:** CODING

**Description:**
Create the Dockerfile for the sandbox container with all required tooling.

**Implementation Notes:**
- Base: Ubuntu 24.04
- Install: Python 3.11+, Node.js (for Claude CLI), Git, Docker CLI, curl, jq, make
- Install Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
- Install uv for Python dependency management
- Working directory: `/workspace`
- Don't install Docker daemon (uses host's via socket)

**Acceptance Criteria:**
- [ ] Dockerfile builds successfully
- [ ] Container has Python 3.11+, Node.js, Git, Docker CLI
- [ ] Claude Code CLI is installed and in PATH
- [ ] uv is installed

---

### Task 1.2: Create Sandbox Entrypoint

**File:** `deploy/docker/sandbox/entrypoint.sh`
**Type:** CODING

**Description:**
Create entrypoint script that ensures workspace is ready.

**Implementation Notes:**
- Check if `/workspace` has a git repo, if not log warning
- Ensure ANTHROPIC_API_KEY is set, warn if not
- Keep container running (`sleep infinity` or `tail -f /dev/null`)

**Acceptance Criteria:**
- [ ] Entrypoint runs without error
- [ ] Logs warning if workspace empty
- [ ] Logs warning if API key missing
- [ ] Container stays running for exec commands

---

### Task 1.3: Create Sandbox Docker Compose

**File:** `deploy/environments/sandbox/docker-compose.yml`
**Type:** CODING

**Description:**
Create docker-compose configuration for the sandbox environment.

**Implementation Notes:**
- Mount Docker socket from host
- Mount shared data read-only from `~/Documents/ktrdr-shared/data/`
- Create named volumes for workspace, models, strategies, logs
- Pass ANTHROPIC_API_KEY from environment
- Join ktrdr-network for service communication
- Use `host.docker.internal` for host access

**Volume Mounts:**
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - ~/Documents/ktrdr-shared/data:/shared/data:ro
  - sandbox-workspace:/workspace
  - sandbox-models:/env/models
  - sandbox-strategies:/env/strategies
  - sandbox-logs:/env/logs
```

**Acceptance Criteria:**
- [ ] Compose file is valid YAML
- [ ] Container starts successfully
- [ ] All mounts are accessible
- [ ] Can reach Docker daemon from inside container

---

### Task 1.4: Create sandbox-init.sh Script

**File:** `scripts/sandbox-init.sh`
**Type:** CODING

**Description:**
First-time setup script that clones repo into workspace volume.

**Implementation Notes:**
- Build sandbox image if not exists
- Start container temporarily
- Clone ktrdr repo into /workspace (use HTTPS, no auth needed for public)
- For private repo: use SSH key mount or GitHub token
- Create directory structure in /env/
- Stop container (will be started by docker-compose later)

**Flow:**
```bash
#!/bin/bash
set -e

# Build image
docker compose -f deploy/environments/sandbox/docker-compose.yml build

# Start container
docker compose -f deploy/environments/sandbox/docker-compose.yml up -d

# Clone repo (first time only)
docker exec ktrdr-sandbox bash -c '
  if [ ! -d /workspace/.git ]; then
    git clone https://github.com/kpiteira/ktrdr2.git /workspace
  fi
'

# Create env directories
docker exec ktrdr-sandbox mkdir -p /env/models /env/strategies /env/logs

echo "Sandbox initialized successfully"
```

**Acceptance Criteria:**
- [ ] Script is executable
- [ ] Clones repo on first run
- [ ] Idempotent (safe to run multiple times)
- [ ] Creates all required directories

---

### Task 1.5: Create sandbox-reset.sh Script

**File:** `scripts/sandbox-reset.sh`
**Type:** CODING

**Description:**
Reset workspace to clean state while preserving models/strategies.

**Implementation Notes:**
- Use `git clean -fdx` to remove untracked files
- Use `git checkout .` to restore modified files
- Clear /env/logs/ but keep /env/models/ and /env/strategies/
- Should complete in < 30 seconds
- Add timing output

**Flow:**
```bash
#!/bin/bash
set -e

START_TIME=$(date +%s)

echo "Resetting sandbox workspace..."

# Reset git state
docker exec ktrdr-sandbox bash -c '
  cd /workspace
  git clean -fdx
  git checkout .
  git status
'

# Clear logs only
docker exec ktrdr-sandbox bash -c 'rm -rf /env/logs/* 2>/dev/null || true'

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "Sandbox reset complete in ${DURATION}s"
```

**Acceptance Criteria:**
- [ ] Script is executable
- [ ] Workspace returns to clean git state
- [ ] Models and strategies preserved
- [ ] Logs cleared
- [ ] Completes in < 30 seconds

---

### Task 1.6: Create sandbox-shell.sh Script

**File:** `scripts/sandbox-shell.sh`
**Type:** CODING

**Description:**
Interactive shell access to sandbox for debugging.

**Implementation Notes:**
- Simple wrapper around docker exec
- Default to bash
- Allow passing custom command

```bash
#!/bin/bash
docker exec -it ktrdr-sandbox "${@:-bash}"
```

**Acceptance Criteria:**
- [ ] Script is executable
- [ ] Opens interactive bash by default
- [ ] Can pass custom commands

---

### Task 1.7: Create sandbox-claude.sh Script

**File:** `scripts/sandbox-claude.sh`
**Type:** CODING

**Description:**
Run Claude Code command in sandbox.

**Implementation Notes:**
- Wrapper that calls claude CLI in sandbox
- Pass all arguments through
- Ensure working directory is /workspace

```bash
#!/bin/bash
docker exec -it -w /workspace ktrdr-sandbox claude "$@"
```

**Acceptance Criteria:**
- [ ] Script is executable
- [ ] Can run `./scripts/sandbox-claude.sh -p "hello"`
- [ ] Working directory is /workspace

---

## Milestone Verification

**Full E2E Test Script:**
```bash
#!/bin/bash
set -e

echo "=== M1 Verification ==="

# Setup
./scripts/sandbox-init.sh
docker compose -f deploy/environments/sandbox/docker-compose.yml up -d
sleep 5  # Wait for container

# Test 1: Claude runs
echo "Test 1: Claude Code runs..."
docker exec ktrdr-sandbox claude -p "say hello" --output-format json | jq '.result'

# Test 2: .claude/ available
echo "Test 2: .claude/ commands available..."
docker exec ktrdr-sandbox ls /workspace/.claude/commands/ktask.md

# Test 3: Shared data accessible
echo "Test 3: Shared data accessible..."
docker exec ktrdr-sandbox ls /shared/data/ | head -3

# Test 4: Env volumes work
echo "Test 4: Env volumes work..."
docker exec ktrdr-sandbox touch /env/models/test.pt
docker exec ktrdr-sandbox touch /env/strategies/test.yaml

# Test 5: Reset behavior
echo "Test 5: Reset preserves artifacts..."
docker exec ktrdr-sandbox touch /workspace/dirty.txt
./scripts/sandbox-reset.sh
docker exec ktrdr-sandbox test ! -f /workspace/dirty.txt  # Should not exist
docker exec ktrdr-sandbox test -f /env/models/test.pt     # Should exist

# Test 6: Docker-in-docker
echo "Test 6: Docker-in-docker works..."
docker exec ktrdr-sandbox docker ps

echo "=== M1 Verification PASSED ==="
```

**Checklist:**
- [ ] All tasks complete
- [ ] Unit tests pass: N/A (no Python code yet)
- [ ] E2E test passes: verification script above
- [ ] Quality gates pass: `make quality` (for shell scripts: shellcheck)
