# Test: cli/kinfra-impl-workflow

**Purpose:** Validate the complete kinfra impl workflow creates an isolated implementation environment with worktree, claimed slot, docker-compose override, and running containers

**Duration:** ~120 seconds (containers take time to start and reach healthy state)

**Category:** CLI / Infrastructure

---

## Pre-Flight Checks

**Required modules:**
- Docker daemon running
- Provisioned slot pool (at least one available slot)

**Test-specific checks:**
- [ ] uv is available in PATH
- [ ] Current directory is KTRDR repository root (contains pyproject.toml)
- [ ] git is available and repository is valid
- [ ] Parent directory is writable (worktrees created there)
- [ ] Docker is running: `docker info > /dev/null 2>&1`
- [ ] Slot pool is provisioned: `~/.ktrdr/sandboxes/slot-1/` exists
- [ ] At least one slot is available (not claimed)
- [ ] No existing worktree with test feature name

---

## Test Data

```yaml
# Test feature/milestone for isolated testing
feature_name: "e2e-test-impl"
milestone_name: "M1"
feature_milestone: "e2e-test-impl/M1"

# Expected paths (relative to repo)
milestone_file: "docs/designs/e2e-test-impl/implementation/M1_test.md"
worktree_path: "../ktrdr-impl-e2e-test-impl-M1"
branch_name: "impl/e2e-test-impl-M1"

# Slot infrastructure
sandboxes_dir: "~/.ktrdr/sandboxes"
registry_file: "~/.ktrdr/sandbox/instances.json"

# Expected container health endpoint pattern
health_endpoint: "/api/v1/health"
```

**Why this data:**
- Uses dedicated test feature name to avoid conflicts with real features
- Milestone file creation ensures the workflow can find a valid target
- Unique naming ensures test isolation and cleanup identification

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Pre-check: verify slot pool provisioned | At least one slot exists | slot_count |
| 2 | Pre-check: verify at least one slot available | Unclaimed slot found | available_slot_id |
| 3 | Setup: create test milestone file | File created in docs/designs | file_path |
| 4 | Run `kinfra impl e2e-test-impl/M1` | Exit 0, success messages | command_output, claimed_slot |
| 5 | Verify worktree directory exists | Directory at expected path | directory_listing |
| 6 | Verify worktree is valid git worktree | Has .git file | git_file_content |
| 7 | Verify branch exists and checked out | Branch matches expected | current_branch |
| 8 | Verify slot claimed in registry | claimed_by = worktree path | registry_slot_entry |
| 9 | Verify docker-compose.override.yml exists | File in slot infrastructure | override_file_content |
| 10 | Verify override contains worktree mounts | Worktree path in volumes | mount_paths |
| 11 | Verify containers running | docker ps shows slot containers | docker_ps_output |
| 12 | Verify health endpoint responds | HTTP 200 on claimed port | health_response |
| 13 | Run `kinfra worktrees` | Shows impl with slot info | worktrees_output |
| 14 | Test idempotency: run impl again | Exit 1 (worktree exists) | error_output |
| 15 | Cleanup: stop containers and release slot | Containers stopped | cleanup_status |
| 16 | Cleanup: remove worktree and branch | Worktree removed | cleanup_final |

---

## Detailed Steps

### Step 1: Pre-Check Slot Pool Provisioned

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

# Check that slot pool exists
if [ ! -d "$SANDBOXES_DIR/slot-1" ]; then
  echo "FAIL: Slot pool not provisioned. Run 'kinfra sandbox provision' first."
  exit 1
fi

SLOT_COUNT=$(ls -d "$SANDBOXES_DIR"/slot-* 2>/dev/null | wc -l | tr -d ' ')
echo "Found $SLOT_COUNT provisioned slots"

if [ "$SLOT_COUNT" -lt 1 ]; then
  echo "FAIL: No slots provisioned"
  exit 1
fi

echo "PASS: Slot pool is provisioned with $SLOT_COUNT slots"
```

**Expected:**
- At least 1 slot directory exists
- Exit code 0

**Capture:** Number of provisioned slots

---

### Step 2: Pre-Check Available Slot

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"

# Check registry for unclaimed slots
if [ ! -f "$REGISTRY_FILE" ]; then
  echo "FAIL: Registry file not found at $REGISTRY_FILE"
  exit 1
fi

# Look for a slot where claimed_by is null
# Using python for JSON parsing since jq may not be available
AVAILABLE_SLOT=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
for slot_id, slot in data.get('slots', {}).items():
    if slot.get('claimed_by') is None:
        print(slot_id)
        break
else:
    print('')
")

if [ -z "$AVAILABLE_SLOT" ]; then
  echo "FAIL: All slots are claimed. Release a slot first."
  echo "Current claims:"
  uv run kinfra sandbox slots
  exit 1
fi

echo "PASS: Found available slot: $AVAILABLE_SLOT"
```

**Expected:**
- At least one slot with `claimed_by: null`
- Exit code 0

**Capture:** Available slot ID

---

### Step 3: Setup - Create Test Milestone File

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

FEATURE_NAME="e2e-test-impl"
IMPL_DIR="docs/designs/$FEATURE_NAME/implementation"

# Create implementation directory
mkdir -p "$IMPL_DIR"

# Create milestone file
MILESTONE_FILE="$IMPL_DIR/M1_test.md"
cat > "$MILESTONE_FILE" << 'EOF'
---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: E2E Test Milestone

**Branch:** `impl/e2e-test-impl-M1`

## Goal

This is a test milestone for E2E testing of the kinfra impl workflow.

## Task 1.1: Placeholder

**Type:** CODING

This milestone exists solely for testing purposes.
EOF

if [ -f "$MILESTONE_FILE" ]; then
  echo "PASS: Created milestone file at $MILESTONE_FILE"
  cat "$MILESTONE_FILE"
else
  echo "FAIL: Could not create milestone file"
  exit 1
fi
```

**Expected:**
- Milestone file created at `docs/designs/e2e-test-impl/implementation/M1_test.md`
- File contains valid markdown content

**Capture:** Milestone file path and content

---

### Step 4: Run kinfra impl

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

FEATURE_MILESTONE="e2e-test-impl/M1"

OUTPUT=$(uv run kinfra impl "$FEATURE_MILESTONE" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: kinfra impl command failed with exit code $EXIT_CODE"
  exit 1
fi

# Verify key messages in output
if echo "$OUTPUT" | grep -q "Created worktree at"; then
  echo "PASS: Worktree creation confirmed"
else
  echo "FAIL: No worktree creation message"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Claimed slot"; then
  echo "PASS: Slot claim confirmed"
  # Extract claimed slot number
  CLAIMED_SLOT=$(echo "$OUTPUT" | grep -o "Claimed slot [0-9]" | grep -o "[0-9]")
  echo "Claimed slot: $CLAIMED_SLOT"
else
  echo "FAIL: No slot claim message"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Generated docker-compose.override.yml"; then
  echo "PASS: Override file generation confirmed"
else
  echo "FAIL: No override file message"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Started containers"; then
  echo "PASS: Container start confirmed"
else
  echo "FAIL: No container start message"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Ready!"; then
  echo "PASS: Ready message present"
else
  echo "WARNING: No 'Ready!' message"
fi
```

**Expected:**
- Exit code 0
- Output contains: "Created worktree at", "Claimed slot", "Generated docker-compose.override.yml", "Started containers"
- Output shows API port for the claimed slot

**Capture:** Full command output, claimed slot number, API port

---

### Step 5: Verify Worktree Directory Exists

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-impl-M1"

if [ -d "$WORKTREE_PATH" ]; then
  echo "PASS: Worktree directory exists at $WORKTREE_PATH"
  ls -la "$WORKTREE_PATH" | head -15
else
  echo "FAIL: Worktree directory not found at $WORKTREE_PATH"
  echo "Listing parent directory:"
  ls -la ../ | grep ktrdr-impl
  exit 1
fi
```

**Expected:**
- Directory exists at `../ktrdr-impl-e2e-test-impl-M1/`
- Directory contains KTRDR codebase files

**Capture:** Directory listing

---

### Step 6: Verify Worktree is Valid Git Worktree

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-impl-M1"

# Check for .git file (not directory - worktrees have a file)
if [ -f "$WORKTREE_PATH/.git" ]; then
  echo "PASS: .git file exists (valid worktree marker)"
  echo "Content:"
  cat "$WORKTREE_PATH/.git"
elif [ -d "$WORKTREE_PATH/.git" ]; then
  echo "FAIL: .git is a directory, not a file. This is a clone, not a worktree."
  exit 1
else
  echo "FAIL: No .git file or directory found"
  exit 1
fi
```

**Expected:**
- `.git` is a file (not directory)
- File contains `gitdir:` reference to main repo

**Capture:** .git file content

---

### Step 7: Verify Branch Exists and Checked Out

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-impl-M1"
EXPECTED_BRANCH="impl/e2e-test-impl-M1"

# Check branch exists in main repo
if git branch --list "$EXPECTED_BRANCH" | grep -q .; then
  echo "PASS: Branch $EXPECTED_BRANCH exists"
else
  echo "FAIL: Branch $EXPECTED_BRANCH not found"
  echo "Listing impl branches:"
  git branch --list "impl/*"
  exit 1
fi

# Check worktree is on correct branch
CURRENT_BRANCH=$(git -C "$WORKTREE_PATH" branch --show-current)
if [ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ]; then
  echo "PASS: Worktree is on branch $CURRENT_BRANCH"
else
  echo "FAIL: Worktree on wrong branch. Expected: $EXPECTED_BRANCH, Got: $CURRENT_BRANCH"
  exit 1
fi
```

**Expected:**
- Branch `impl/e2e-test-impl-M1` exists
- Worktree is checked out to that branch

**Capture:** Branch listing, current branch

---

### Step 8: Verify Slot Claimed in Registry

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)

echo "Looking for worktree: $WORKTREE_PATH"
echo ""
echo "Registry slots:"

# Find the claimed slot
uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)

found = False
for slot_id, slot in data.get('slots', {}).items():
    claimed = slot.get('claimed_by')
    status = slot.get('status', 'stopped')
    profile = slot.get('profile', 'unknown')
    ports = slot.get('ports', {})
    api_port = ports.get('api', 'N/A')

    if claimed and '$WORKTREE_PATH' in claimed:
        print(f'PASS: Slot {slot_id} is claimed by worktree')
        print(f'  Profile: {profile}')
        print(f'  Status: {status}')
        print(f'  API Port: {api_port}')
        print(f'  Claimed by: {claimed}')
        found = True

if not found:
    print('FAIL: No slot found claimed by worktree')
    print('All slots:')
    for slot_id, slot in data.get('slots', {}).items():
        print(f'  Slot {slot_id}: claimed_by={slot.get(\"claimed_by\")}')
    exit(1)
"
```

**Expected:**
- One slot has `claimed_by` = worktree path
- Slot `status` = "running"
- Slot shows correct profile and ports

**Capture:** Registry slot entry for claimed slot

---

### Step 9: Verify docker-compose.override.yml Exists

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)

# Find the claimed slot directory
SLOT_DIR=""
for i in 1 2 3 4 5 6; do
  OVERRIDE_FILE="$SANDBOXES_DIR/slot-$i/docker-compose.override.yml"
  if [ -f "$OVERRIDE_FILE" ]; then
    # Check if this override references our worktree
    if grep -q "$WORKTREE_PATH" "$OVERRIDE_FILE" 2>/dev/null; then
      SLOT_DIR="$SANDBOXES_DIR/slot-$i"
      echo "Found override file in slot-$i"
      break
    fi
  fi
done

if [ -z "$SLOT_DIR" ]; then
  echo "FAIL: No docker-compose.override.yml found for worktree"
  echo "Checking all slots:"
  for i in 1 2 3 4 5 6; do
    echo "  slot-$i:"
    ls -la "$SANDBOXES_DIR/slot-$i/"*.yml 2>/dev/null || echo "    No yml files"
  done
  exit 1
fi

OVERRIDE_FILE="$SLOT_DIR/docker-compose.override.yml"
echo "PASS: Override file exists at $OVERRIDE_FILE"
echo ""
echo "Content:"
cat "$OVERRIDE_FILE"
```

**Expected:**
- `docker-compose.override.yml` exists in claimed slot directory
- File contains reference to worktree path

**Capture:** Override file path and content

---

### Step 10: Verify Override Contains Worktree Mounts

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)

# Find and validate override file
for i in 1 2 3 4 5 6; do
  OVERRIDE_FILE="$SANDBOXES_DIR/slot-$i/docker-compose.override.yml"
  if [ -f "$OVERRIDE_FILE" ] && grep -q "$WORKTREE_PATH" "$OVERRIDE_FILE"; then
    echo "Validating override in slot-$i"

    # Check for required mount paths
    REQUIRED_MOUNTS="ktrdr research_agents tests config"
    MISSING=""
    for mount in $REQUIRED_MOUNTS; do
      if grep -q "$WORKTREE_PATH/$mount" "$OVERRIDE_FILE"; then
        echo "PASS: Mount for $mount found"
      else
        MISSING="$MISSING $mount"
      fi
    done

    if [ -n "$MISSING" ]; then
      echo "FAIL: Missing mounts:$MISSING"
      exit 1
    fi

    # Check for services
    if grep -q "backend:" "$OVERRIDE_FILE"; then
      echo "PASS: backend service defined"
    else
      echo "FAIL: backend service not defined"
      exit 1
    fi

    if grep -q "backtest-worker:" "$OVERRIDE_FILE"; then
      echo "PASS: backtest-worker service defined"
    else
      echo "WARNING: backtest-worker service not defined"
    fi

    if grep -q "training-worker:" "$OVERRIDE_FILE"; then
      echo "PASS: training-worker service defined"
    else
      echo "WARNING: training-worker service not defined"
    fi

    echo ""
    echo "PASS: Override file contains correct worktree mounts"
    exit 0
  fi
done

echo "FAIL: Could not find override file for worktree"
exit 1
```

**Expected:**
- Override file contains volumes for: ktrdr/, research_agents/, tests/, config/
- Services defined: backend, backtest-worker, training-worker

**Capture:** Verified mount paths

---

### Step 11: Verify Containers Running

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Get claimed slot API port from registry
REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)

API_PORT=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
for slot_id, slot in data.get('slots', {}).items():
    if slot.get('claimed_by') and '$WORKTREE_PATH' in slot.get('claimed_by', ''):
        print(slot.get('ports', {}).get('api', ''))
        break
")

if [ -z "$API_PORT" ]; then
  echo "FAIL: Could not determine API port from registry"
  exit 1
fi

echo "Expected API port: $API_PORT"

# Check docker ps for containers
DOCKER_PS=$(docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}")
echo ""
echo "Docker containers:"
echo "$DOCKER_PS"
echo ""

# Look for containers with our port
if echo "$DOCKER_PS" | grep -q "$API_PORT"; then
  echo "PASS: Found container(s) using port $API_PORT"
else
  echo "WARNING: No container explicitly showing port $API_PORT in docker ps"
  echo "Checking for slot containers..."
fi

# Count running containers for this slot (backend at minimum)
RUNNING_COUNT=$(docker ps --format "{{.Names}}" | grep -c "slot" || echo "0")
if [ "$RUNNING_COUNT" -gt 0 ]; then
  echo "PASS: Found $RUNNING_COUNT running slot container(s)"
else
  echo "FAIL: No slot containers running"
  docker ps -a | tail -10
  exit 1
fi
```

**Expected:**
- At least one container running for the claimed slot
- Container shows healthy/running status

**Capture:** docker ps output

---

### Step 12: Verify Health Endpoint Responds

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Get API port from registry
REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)

API_PORT=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
for slot_id, slot in data.get('slots', {}).items():
    if slot.get('claimed_by') and '$WORKTREE_PATH' in slot.get('claimed_by', ''):
        print(slot.get('ports', {}).get('api', ''))
        break
")

if [ -z "$API_PORT" ]; then
  echo "FAIL: Could not determine API port"
  exit 1
fi

HEALTH_URL="http://localhost:$API_PORT/api/v1/health"
echo "Checking health endpoint: $HEALTH_URL"

# Try health check with retries (containers may still be starting)
MAX_RETRIES=10
RETRY_DELAY=5
HEALTHY=false

for i in $(seq 1 $MAX_RETRIES); do
  echo "Attempt $i/$MAX_RETRIES..."
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" 2>/dev/null)

  if [ "$RESPONSE" = "200" ]; then
    HEALTHY=true
    echo "PASS: Health endpoint returned 200"
    break
  else
    echo "  Got HTTP $RESPONSE, waiting ${RETRY_DELAY}s..."
    sleep $RETRY_DELAY
  fi
done

if [ "$HEALTHY" = false ]; then
  echo "FAIL: Health endpoint did not respond 200 after $MAX_RETRIES attempts"
  echo "Last response code: $RESPONSE"
  echo ""
  echo "Checking container logs:"
  docker logs $(docker ps --format "{{.Names}}" | grep backend | head -1) 2>&1 | tail -20
  exit 1
fi

# Get full health response
echo ""
echo "Full health response:"
curl -s "$HEALTH_URL" | head -20
```

**Expected:**
- HTTP 200 from health endpoint
- Response contains valid JSON

**Capture:** Health response status and body

---

### Step 13: Verify kinfra worktrees Shows Slot Info

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

OUTPUT=$(uv run kinfra worktrees 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: kinfra worktrees command failed"
  exit 1
fi

# Verify our worktree appears
if echo "$OUTPUT" | grep -q "ktrdr-impl-e2e-test-impl-M1"; then
  echo "PASS: Worktree appears in list"
else
  echo "FAIL: Worktree not found in list"
  exit 1
fi

# Verify type is impl
if echo "$OUTPUT" | grep "ktrdr-impl-e2e-test-impl-M1" | grep -q "impl"; then
  echo "PASS: Type is 'impl'"
else
  echo "FAIL: Type not 'impl'"
  exit 1
fi

# Verify slot info is shown
if echo "$OUTPUT" | grep "ktrdr-impl-e2e-test-impl-M1" | grep -q "slot"; then
  echo "PASS: Slot info visible"
else
  echo "FAIL: Slot info not visible"
  exit 1
fi

# Verify running status shown
if echo "$OUTPUT" | grep "ktrdr-impl-e2e-test-impl-M1" | grep -qi "running"; then
  echo "PASS: Running status visible"
else
  echo "WARNING: Running status not visible in output"
fi

# Verify port shown
if echo "$OUTPUT" | grep "ktrdr-impl-e2e-test-impl-M1" | grep -qE ":[0-9]{4}"; then
  echo "PASS: Port visible"
else
  echo "WARNING: Port not visible in output"
fi
```

**Expected:**
- Exit code 0
- Table contains `ktrdr-impl-e2e-test-impl-M1`
- Type column shows "impl"
- Sandbox column shows slot number, status, and port

**Capture:** Full worktrees output

---

### Step 14: Test Idempotency (Duplicate Creation Fails)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Attempt to create same worktree again
OUTPUT=$(uv run kinfra impl "e2e-test-impl/M1" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Should fail with exit 1
if [ $EXIT_CODE -eq 1 ]; then
  echo "PASS: Duplicate creation correctly rejected (exit 1)"
else
  echo "FAIL: Expected exit code 1, got $EXIT_CODE"
  exit 1
fi

# Should have error message about existing worktree
if echo "$OUTPUT" | grep -qi "already exists"; then
  echo "PASS: Error message mentions existing worktree"
else
  echo "FAIL: Expected error about existing worktree"
  exit 1
fi
```

**Expected:**
- Exit code 1 (failure)
- Error message indicates worktree already exists
- Original worktree unchanged

**Capture:** Error output, exit code

---

### Step 15: Cleanup - Stop Containers and Release Slot

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"
WORKTREE_PATH=$(cd ../ktrdr-impl-e2e-test-impl-M1 && pwd)
REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"

# Find claimed slot
SLOT_ID=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
for slot_id, slot in data.get('slots', {}).items():
    if slot.get('claimed_by') and '$WORKTREE_PATH' in slot.get('claimed_by', ''):
        print(slot_id)
        break
")

if [ -z "$SLOT_ID" ]; then
  echo "WARNING: Could not find claimed slot, skipping container cleanup"
else
  echo "Stopping containers in slot $SLOT_ID..."
  SLOT_DIR="$SANDBOXES_DIR/slot-$SLOT_ID"

  # Stop containers
  docker compose -f "$SLOT_DIR/docker-compose.yml" -f "$SLOT_DIR/docker-compose.override.yml" down 2>/dev/null || \
  docker compose -f "$SLOT_DIR/docker-compose.yml" down 2>/dev/null || \
  echo "WARNING: Could not stop containers"

  # Release slot in registry
  uv run python3 -c "
import json
with open('$REGISTRY_FILE', 'r') as f:
    data = json.load(f)
if '$SLOT_ID' in data.get('slots', {}):
    data['slots']['$SLOT_ID']['claimed_by'] = None
    data['slots']['$SLOT_ID']['claimed_at'] = None
    data['slots']['$SLOT_ID']['status'] = 'stopped'
    with open('$REGISTRY_FILE', 'w') as f:
        json.dump(data, f, indent=2)
    print('Slot released')
else:
    print('Slot not found in registry')
"

  # Remove override file
  rm -f "$SLOT_DIR/docker-compose.override.yml"
  echo "Removed override file"
fi

echo "PASS: Container cleanup complete"
```

**Expected:**
- Containers stopped
- Slot released in registry
- Override file removed

**Capture:** Cleanup status

---

### Step 16: Cleanup - Remove Worktree and Branch

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-impl-M1"
BRANCH_NAME="impl/e2e-test-impl-M1"
FEATURE_DIR="docs/designs/e2e-test-impl"

# Remove worktree
echo "Removing worktree at $WORKTREE_PATH..."
if [ -d "$WORKTREE_PATH" ]; then
  git worktree remove "$WORKTREE_PATH" --force 2>/dev/null || {
    echo "Force remove failed, trying manual cleanup..."
    rm -rf "$WORKTREE_PATH"
    git worktree prune
  }
  echo "Worktree removed"
else
  echo "Worktree already removed"
fi

# Remove branch
echo "Removing branch $BRANCH_NAME..."
git branch -D "$BRANCH_NAME" 2>/dev/null || echo "Branch already removed or not found"

# Remove test feature directory
echo "Removing test feature directory..."
if [ -d "$FEATURE_DIR" ]; then
  rm -rf "$FEATURE_DIR"
  echo "Feature directory removed"
else
  echo "Feature directory already removed"
fi

# Verify cleanup
if [ -d "$WORKTREE_PATH" ]; then
  echo "WARNING: Worktree directory still exists"
else
  echo "PASS: Worktree directory removed"
fi

if git branch --list "$BRANCH_NAME" | grep -q .; then
  echo "WARNING: Branch still exists"
else
  echo "PASS: Branch removed"
fi

if [ -d "$FEATURE_DIR" ]; then
  echo "WARNING: Feature directory still exists"
else
  echo "PASS: Feature directory removed"
fi

echo ""
echo "PASS: Cleanup complete"
```

**Expected:**
- Worktree removed successfully
- Branch deleted successfully
- Test feature directory removed
- No residual files or branches

**Capture:** Cleanup exit codes and status

---

## Success Criteria

All must pass for test to pass:

- [ ] `uv run kinfra impl e2e-test-impl/M1` exits 0
- [ ] Output shows "Created worktree at", "Claimed slot", "Generated docker-compose.override.yml", "Started containers"
- [ ] Worktree directory created at `../ktrdr-impl-e2e-test-impl-M1/`
- [ ] Worktree is valid git worktree (has .git file, not directory)
- [ ] Branch `impl/e2e-test-impl-M1` exists and is checked out in worktree
- [ ] Registry shows slot claimed by worktree path with status "running"
- [ ] docker-compose.override.yml exists in claimed slot infrastructure directory
- [ ] Override file contains volume mounts for worktree code paths (ktrdr/, research_agents/, tests/, config/)
- [ ] At least one container running for the claimed slot
- [ ] Health endpoint responds HTTP 200 on claimed slot's API port
- [ ] `uv run kinfra worktrees` shows worktree with type "impl" and slot info (slot number, status, port)
- [ ] Duplicate `kinfra impl` fails with exit 1 and "already exists" message
- [ ] Cleanup removes worktree, branch, and releases slot

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Total duration > 30s | <= 30s fails | Container startup skipped |
| Health endpoint returns 200 | Non-200 fails | Backend not running |
| Slot claimed_by matches worktree path | Mismatch fails | Wrong slot claimed |
| Override file references worktree | No reference fails | Override not generated correctly |
| Containers visible in docker ps | None visible fails | Docker compose failed |
| Worktree .git is file not directory | Directory fails | Clone instead of worktree |
| Registry status = "running" | Not "running" fails | Status not updated |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| "command not found: kinfra" | CONFIGURATION | Run `uv sync` to install entry points |
| "No milestone matching" | TEST_ISSUE | Verify test milestone file was created |
| "All 6 slots in use" | ENVIRONMENT | Release a slot with `kinfra done` or manually |
| "Not in a git repository" | ENVIRONMENT | Run from KTRDR repo root |
| "Worktree already exists" | TEST_ISSUE | Clean up from previous failed run |
| "Failed to create git worktree" | ENVIRONMENT | Check git status, disk space |
| "Failed to start containers" | ENVIRONMENT | Check Docker daemon, available ports |
| "Backend not healthy after 120s" | CODE_BUG | Check container logs, port conflicts |
| Override file missing | CODE_BUG | Check generate_override() in override.py |
| Wrong mounts in override | CODE_BUG | Check OVERRIDE_TEMPLATE in override.py |
| Slot not shown in worktrees | CODE_BUG | Check get_slot_for_worktree() in worktrees.py |
| Registry not updated | CODE_BUG | Check claim_slot() in sandbox_registry.py |

---

## Cleanup

Cleanup is **critical** for this test. Always execute cleanup even if test fails.

**Automatic cleanup in Steps 15-16:**
1. Stop containers for claimed slot
2. Release slot in registry
3. Remove docker-compose.override.yml
4. Remove git worktree
5. Delete git branch
6. Remove test feature directory

**Manual cleanup if automatic fails:**
```bash
# Find and stop containers
docker ps | grep slot
docker compose -f ~/.ktrdr/sandboxes/slot-*/docker-compose.yml down

# Remove worktree
rm -rf ../ktrdr-impl-e2e-test-impl-*
git worktree prune

# Remove branch
git branch -D impl/e2e-test-impl-M1

# Remove test feature
rm -rf docs/designs/e2e-test-impl

# Reset registry (edit manually)
# Remove claimed_by and set status to "stopped" for affected slot
```

---

## Troubleshooting

**If "command not found: kinfra":**
- **Cause:** Entry point not installed
- **Cure:** Run `uv sync` to reinstall package

**If "No milestone matching" error:**
- **Cause:** Milestone file not created in Step 3
- **Cure:** Manually create `docs/designs/e2e-test-impl/implementation/M1_test.md`

**If "All 6 slots in use":**
- **Cause:** Previous test runs didn't clean up, or slots legitimately in use
- **Cure:** Run `uv run kinfra sandbox slots` to see claims, manually release with registry edit

**If "Failed to start containers":**
- **Cause:** Docker issues, port conflicts, missing images
- **Cure:** Check `docker info`, look for port conflicts, run `docker compose pull`

**If health check fails after containers start:**
- **Cause:** Backend startup slow, missing dependencies
- **Cure:** Check container logs: `docker logs <backend-container-name>`

**If worktree created but slot not claimed:**
- **Cause:** Slot claiming failed, registry not saved
- **Cure:** Check sandbox_registry.py claim_slot() method

**If override file missing or wrong:**
- **Cause:** generate_override() failed
- **Cure:** Check slot.infrastructure_path is correct, check file permissions

**If kinfra worktrees doesn't show slot info:**
- **Cause:** get_slot_for_worktree() path matching issue
- **Cure:** Compare worktree path in registry vs actual worktree path (symlinks, etc.)

---

## Evidence to Capture

- Slot pool check (slot count)
- Available slot before test
- Created milestone file content
- Full `kinfra impl` command output
- Worktree directory listing
- .git file content
- Branch listing and current branch
- Registry slot entry (JSON)
- docker-compose.override.yml content
- docker ps output
- Health endpoint response
- `kinfra worktrees` output
- Duplicate creation error output
- Cleanup status messages
- All exit codes

---

## Notes for Implementation

**Key Files:**
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/impl.py` - Main impl command
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/override.py` - Override file generation
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/slots.py` - Container management
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/worktrees.py` - Worktrees listing
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/sandbox_registry.py` - Slot registry

**Order of Operations in impl:**
1. Parse feature/milestone
2. Find milestone file
3. Check slot availability (fail fast - GAP-6)
4. Create git worktree
5. Claim slot in registry
6. Generate docker-compose.override.yml
7. Start containers with override
8. Wait for health
9. On failure: release slot, keep worktree (GAP-7)

**Port Allocation:**
- Slot 1: API=8001, DB=5433
- Slot 2: API=8002, DB=5434
- etc.

**Health Check:**
- Uses httpx with 120s timeout
- Polls every 2s until healthy
- Endpoint: `/api/v1/health`

**State Persistence:**
The tester must maintain these variables across steps:
- `WORKTREE_PATH` - Absolute path to created worktree
- `SLOT_ID` - Claimed slot number
- `API_PORT` - API port for health checks

**Parallel Execution:**
Using dedicated `e2e-test-impl` feature name ensures isolation. However, this test should not run in parallel with itself due to the unique feature name.

**Alternative Approaches:**
- If health check times out, increase timeout or check container logs
- If slot pool not provisioned, run `kinfra sandbox provision` as prerequisite
- If cleanup fails, manual intervention may be needed
