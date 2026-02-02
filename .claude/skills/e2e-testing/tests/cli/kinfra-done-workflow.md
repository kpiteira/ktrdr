# Test: cli/kinfra-done-workflow

**Purpose:** Validate the complete kinfra done workflow cleans up worktrees, releases sandbox slots, stops containers, and handles dirty state protection correctly

**Duration:** ~90 seconds (includes setup with container startup)

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
feature_name: "e2e-test-done"
milestone_name: "M1"
feature_milestone: "e2e-test-done/M1"

# Expected paths (relative to repo)
milestone_file: "docs/designs/e2e-test-done/implementation/M1_test.md"
worktree_path: "../ktrdr-impl-e2e-test-done-M1"
worktree_name: "ktrdr-impl-e2e-test-done-M1"
branch_name: "impl/e2e-test-done-M1"

# Slot infrastructure
sandboxes_dir: "~/.ktrdr/sandboxes"
registry_file: "~/.ktrdr/sandbox/instances.json"
```

**Why this data:**
- Uses dedicated test feature name to avoid conflicts with real features
- Name "e2e-test-done" clearly indicates test purpose
- Different from impl-workflow test to allow parallel testing

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Setup: Create test milestone file | File created | file_path |
| 2 | Setup: Run `kinfra impl` to create worktree | Worktree + slot claimed | claimed_slot_id, worktree_path |
| 3 | Verify slot claimed (baseline) | claimed_by = worktree path | registry_before |
| 4 | Test dirty check: Create uncommitted file | File created | dirty_file_path |
| 5 | Run `kinfra done` without --force | Exit 1, uncommitted error | dirty_error_output |
| 6 | Verify slot still claimed | Not released prematurely | registry_after_dirty |
| 7 | Run `kinfra done --force` | Exit 0, cleanup messages | force_output |
| 8 | Verify containers stopped | docker ps shows none for slot | docker_ps_after |
| 9 | Verify slot released in registry | claimed_by = null, status = stopped | registry_after_done |
| 10 | Verify override file removed | File does not exist | override_check |
| 11 | Verify worktree removed | Directory does not exist | worktree_check |
| 12 | Verify branch removed | Branch not in git branch list | branch_check |
| 13 | Test idempotency: Run done again | Exit 1, worktree not found | idempotent_error |
| 14 | Cleanup: Remove test milestone file | File removed | cleanup_status |

---

## Detailed Steps

### Step 1: Setup - Create Test Milestone File

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

FEATURE_NAME="e2e-test-done"
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

# Milestone 1: E2E Test Milestone for Done Workflow

**Branch:** `impl/e2e-test-done-M1`

## Goal

This is a test milestone for E2E testing of the kinfra done workflow.

## Task 1.1: Placeholder

**Type:** CODING

This milestone exists solely for testing purposes.
EOF

if [ -f "$MILESTONE_FILE" ]; then
  echo "PASS: Created milestone file at $MILESTONE_FILE"
else
  echo "FAIL: Could not create milestone file"
  exit 1
fi
```

**Expected:**
- Milestone file created at `docs/designs/e2e-test-done/implementation/M1_test.md`
- Exit code 0

**Capture:** Milestone file path

---

### Step 2: Setup - Run kinfra impl

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

FEATURE_MILESTONE="e2e-test-done/M1"

OUTPUT=$(uv run kinfra impl "$FEATURE_MILESTONE" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: kinfra impl command failed with exit code $EXIT_CODE"
  exit 1
fi

# Extract claimed slot number
CLAIMED_SLOT=$(echo "$OUTPUT" | grep -o "Claimed slot [0-9]" | grep -o "[0-9]")
if [ -n "$CLAIMED_SLOT" ]; then
  echo "Claimed slot: $CLAIMED_SLOT"
  echo "$CLAIMED_SLOT" > /tmp/e2e_done_test_slot
else
  echo "WARNING: Could not extract claimed slot number"
fi

# Verify worktree created
WORKTREE_PATH="../ktrdr-impl-e2e-test-done-M1"
if [ -d "$WORKTREE_PATH" ]; then
  echo "PASS: Worktree created at $WORKTREE_PATH"
  WORKTREE_ABS=$(cd "$WORKTREE_PATH" && pwd)
  echo "$WORKTREE_ABS" > /tmp/e2e_done_test_worktree
else
  echo "FAIL: Worktree not created"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Worktree created at `../ktrdr-impl-e2e-test-done-M1/`
- Slot claimed and containers started
- Health check passed

**Capture:** Full command output, claimed slot ID, worktree absolute path

---

### Step 3: Verify Slot Claimed (Baseline)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
WORKTREE_ABS=$(cat /tmp/e2e_done_test_worktree)

echo "Worktree path: $WORKTREE_ABS"
echo ""
echo "Registry state before done:"

# Find the claimed slot
SLOT_INFO=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)

found = False
for slot_id, slot in data.get('slots', {}).items():
    claimed = slot.get('claimed_by')
    if claimed and '$WORKTREE_ABS' in claimed:
        print(f'Slot {slot_id}:')
        print(f'  claimed_by: {claimed}')
        print(f'  status: {slot.get(\"status\", \"unknown\")}')
        print(f'  api_port: {slot.get(\"ports\", {}).get(\"api\", \"N/A\")}')
        found = True
        break

if not found:
    print('ERROR: Worktree not found in registry')
    exit(1)
")

echo "$SLOT_INFO"

if echo "$SLOT_INFO" | grep -q "claimed_by:"; then
  echo ""
  echo "PASS: Slot is claimed by worktree (baseline verified)"
else
  echo "FAIL: Slot not claimed"
  exit 1
fi
```

**Expected:**
- Registry shows slot claimed by worktree path
- Status = "running"
- API port assigned

**Capture:** Registry slot entry before done

---

### Step 4: Test Dirty Check - Create Uncommitted File

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-done-M1"

# Create an uncommitted file in the worktree
DIRTY_FILE="$WORKTREE_PATH/UNCOMMITTED_TEST_FILE.txt"
echo "This file was created to test dirty state detection" > "$DIRTY_FILE"

if [ -f "$DIRTY_FILE" ]; then
  echo "PASS: Created dirty file at $DIRTY_FILE"
else
  echo "FAIL: Could not create dirty file"
  exit 1
fi

# Verify git status shows uncommitted changes
GIT_STATUS=$(git -C "$WORKTREE_PATH" status --porcelain)
if [ -n "$GIT_STATUS" ]; then
  echo "PASS: Git status shows uncommitted changes:"
  echo "$GIT_STATUS"
else
  echo "FAIL: Git status is clean (expected dirty)"
  exit 1
fi
```

**Expected:**
- File created in worktree
- git status shows untracked/modified file

**Capture:** Dirty file path, git status output

---

### Step 5: Run kinfra done Without --force

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run done without --force - should fail due to dirty state
OUTPUT=$(uv run kinfra done "e2e-test-done-M1" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Should fail with exit code 1
if [ $EXIT_CODE -eq 1 ]; then
  echo "PASS: Command correctly rejected (exit 1)"
else
  echo "FAIL: Expected exit code 1, got $EXIT_CODE"
  exit 1
fi

# Should mention uncommitted changes
if echo "$OUTPUT" | grep -qi "uncommitted"; then
  echo "PASS: Error message mentions uncommitted changes"
else
  echo "FAIL: Error message does not mention uncommitted changes"
  exit 1
fi

# Should suggest --force
if echo "$OUTPUT" | grep -q "\-\-force"; then
  echo "PASS: Error message suggests --force option"
else
  echo "FAIL: Error message does not suggest --force"
  exit 1
fi
```

**Expected:**
- Exit code 1
- Error message mentions "uncommitted changes"
- Error message suggests using --force

**Capture:** Full error output

---

### Step 6: Verify Slot Still Claimed After Dirty Rejection

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
WORKTREE_ABS=$(cat /tmp/e2e_done_test_worktree)

echo "Registry state after dirty rejection:"

# Verify slot is still claimed
STILL_CLAIMED=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)

for slot_id, slot in data.get('slots', {}).items():
    claimed = slot.get('claimed_by')
    if claimed and '$WORKTREE_ABS' in claimed:
        print('CLAIMED')
        exit(0)

print('NOT_CLAIMED')
")

if [ "$STILL_CLAIMED" = "CLAIMED" ]; then
  echo "PASS: Slot is still claimed (not released prematurely)"
else
  echo "FAIL: Slot was released despite dirty rejection"
  exit 1
fi

# Verify worktree still exists
WORKTREE_PATH="../ktrdr-impl-e2e-test-done-M1"
if [ -d "$WORKTREE_PATH" ]; then
  echo "PASS: Worktree still exists"
else
  echo "FAIL: Worktree was removed despite dirty rejection"
  exit 1
fi

# Verify containers still running
CLAIMED_SLOT=$(cat /tmp/e2e_done_test_slot 2>/dev/null || echo "")
if [ -n "$CLAIMED_SLOT" ]; then
  # Get API port for the slot
  API_PORT=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
slot = data.get('slots', {}).get('$CLAIMED_SLOT', {})
print(slot.get('ports', {}).get('api', ''))
")

  if [ -n "$API_PORT" ]; then
    # Check if backend still responds
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$API_PORT/api/v1/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
      echo "PASS: Containers still running (health check passed)"
    else
      echo "WARNING: Health check returned $HTTP_CODE (containers may have stopped)"
    fi
  fi
fi
```

**Expected:**
- Slot still claimed in registry
- Worktree directory still exists
- Containers still running

**Capture:** Registry state, container health status

---

### Step 7: Run kinfra done with --force

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

START_TIME=$(date +%s)

# Run done with --force - should succeed despite dirty state
OUTPUT=$(uv run kinfra done --force "e2e-test-done-M1" 2>&1)
EXIT_CODE=$?

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"
echo "Duration: ${DURATION}s"

# Should succeed
if [ $EXIT_CODE -eq 0 ]; then
  echo "PASS: Command succeeded with --force"
else
  echo "FAIL: Expected exit code 0, got $EXIT_CODE"
  exit 1
fi

# Verify expected messages in output
if echo "$OUTPUT" | grep -qi "stopping containers"; then
  echo "PASS: Output mentions stopping containers"
else
  echo "WARNING: Output does not mention stopping containers"
fi

if echo "$OUTPUT" | grep -qi "removing override"; then
  echo "PASS: Output mentions removing override"
else
  echo "WARNING: Output does not mention removing override"
fi

if echo "$OUTPUT" | grep -qi "released slot"; then
  echo "PASS: Output mentions releasing slot"
else
  echo "WARNING: Output does not mention releasing slot"
fi

if echo "$OUTPUT" | grep -qi "removing worktree"; then
  echo "PASS: Output mentions removing worktree"
else
  echo "WARNING: Output does not mention removing worktree"
fi

if echo "$OUTPUT" | grep -qi "done!"; then
  echo "PASS: Output shows completion message"
else
  echo "WARNING: Output does not show completion message"
fi
```

**Expected:**
- Exit code 0
- Output shows: "Stopping containers", "Removing override", "Released slot", "Removing worktree", "Done!"
- Duration should be < 30s

**Capture:** Full command output, duration

---

### Step 8: Verify Containers Stopped

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

CLAIMED_SLOT=$(cat /tmp/e2e_done_test_slot 2>/dev/null || echo "")
REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"

echo "Checking docker containers for slot $CLAIMED_SLOT..."

# Get API port that was used by the slot
API_PORT=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)
# Note: slot may be released now, but we still have the port from before
# Slots 1-6 use ports 8001-8006
slot_num = int('$CLAIMED_SLOT') if '$CLAIMED_SLOT' else 0
print(8000 + slot_num)
")

echo "Was using API port: $API_PORT"

# Check if any containers are running on that port
DOCKER_OUTPUT=$(docker ps --format "{{.Names}}\t{{.Ports}}" 2>/dev/null || echo "")
echo ""
echo "Docker ps output:"
echo "$DOCKER_OUTPUT"
echo ""

# Health check should fail now
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:$API_PORT/api/v1/health" 2>/dev/null || echo "000")

if [ "$HTTP_CODE" = "000" ] || [ "$HTTP_CODE" = "502" ] || [ "$HTTP_CODE" = "503" ]; then
  echo "PASS: Backend is not responding on port $API_PORT (containers stopped)"
else
  echo "WARNING: Backend returned HTTP $HTTP_CODE (containers may still be running)"
fi

# Look for containers with slot identifier
SLOT_CONTAINERS=$(docker ps --format "{{.Names}}" | grep -i "slot.*$CLAIMED_SLOT" || echo "")
if [ -z "$SLOT_CONTAINERS" ]; then
  echo "PASS: No containers found for slot $CLAIMED_SLOT"
else
  echo "WARNING: Found containers that may belong to slot:"
  echo "$SLOT_CONTAINERS"
fi
```

**Expected:**
- Health check fails (connection refused or timeout)
- No containers running for the released slot

**Capture:** docker ps output, health check response

---

### Step 9: Verify Slot Released in Registry

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
CLAIMED_SLOT=$(cat /tmp/e2e_done_test_slot 2>/dev/null || echo "")

echo "Registry state after done:"
echo ""

# Check the slot status
SLOT_STATE=$(uv run python3 -c "
import json
with open('$REGISTRY_FILE') as f:
    data = json.load(f)

slot = data.get('slots', {}).get('$CLAIMED_SLOT', {})
claimed_by = slot.get('claimed_by')
status = slot.get('status', 'unknown')

print(f'Slot $CLAIMED_SLOT:')
print(f'  claimed_by: {claimed_by}')
print(f'  status: {status}')

# Verify expectations
if claimed_by is not None:
    print('ERROR: claimed_by should be null')
    exit(1)
if status != 'stopped':
    print(f'ERROR: status should be stopped, got {status}')
    exit(1)

print('')
print('VERIFIED: Slot is released and stopped')
")

echo "$SLOT_STATE"

if echo "$SLOT_STATE" | grep -q "VERIFIED"; then
  echo ""
  echo "PASS: Slot correctly released in registry"
else
  echo "FAIL: Slot not correctly released"
  echo "Full registry content:"
  cat "$REGISTRY_FILE"
  exit 1
fi
```

**Expected:**
- `claimed_by` = null
- `status` = "stopped"

**Capture:** Registry slot entry after done

---

### Step 10: Verify Override File Removed

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"
CLAIMED_SLOT=$(cat /tmp/e2e_done_test_slot 2>/dev/null || echo "")

OVERRIDE_FILE="$SANDBOXES_DIR/slot-$CLAIMED_SLOT/docker-compose.override.yml"

echo "Checking for override file: $OVERRIDE_FILE"

if [ -f "$OVERRIDE_FILE" ]; then
  echo "FAIL: Override file still exists"
  echo "Content:"
  cat "$OVERRIDE_FILE"
  exit 1
else
  echo "PASS: Override file was removed"
fi

# List remaining files in slot directory (should have base compose but no override)
echo ""
echo "Remaining files in slot-$CLAIMED_SLOT:"
ls -la "$SANDBOXES_DIR/slot-$CLAIMED_SLOT/"

# Verify docker-compose.yml still exists (base infrastructure)
if [ -f "$SANDBOXES_DIR/slot-$CLAIMED_SLOT/docker-compose.yml" ]; then
  echo ""
  echo "PASS: Base docker-compose.yml preserved"
else
  echo "WARNING: Base docker-compose.yml missing (infrastructure may be broken)"
fi
```

**Expected:**
- `docker-compose.override.yml` does NOT exist
- `docker-compose.yml` (base) still exists

**Capture:** Directory listing, override file check

---

### Step 11: Verify Worktree Removed

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-impl-e2e-test-done-M1"
WORKTREE_NAME="ktrdr-impl-e2e-test-done-M1"

echo "Checking for worktree directory: $WORKTREE_PATH"

if [ -d "$WORKTREE_PATH" ]; then
  echo "FAIL: Worktree directory still exists"
  ls -la "$WORKTREE_PATH"
  exit 1
else
  echo "PASS: Worktree directory was removed"
fi

# Verify worktree is not in git worktree list
WORKTREE_LIST=$(git worktree list 2>/dev/null || echo "")
echo ""
echo "Git worktree list:"
echo "$WORKTREE_LIST"

if echo "$WORKTREE_LIST" | grep -q "$WORKTREE_NAME"; then
  echo "FAIL: Worktree still appears in git worktree list"
  exit 1
else
  echo "PASS: Worktree removed from git worktree list"
fi
```

**Expected:**
- Worktree directory does not exist
- Worktree not in `git worktree list`

**Capture:** Directory check, git worktree list

---

### Step 12: Verify Branch Removed

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

BRANCH_NAME="impl/e2e-test-done-M1"

echo "Checking for branch: $BRANCH_NAME"

# Check if branch exists
BRANCH_EXISTS=$(git branch --list "$BRANCH_NAME")
if [ -n "$BRANCH_EXISTS" ]; then
  echo "WARNING: Branch still exists: $BRANCH_EXISTS"
  echo "Note: git worktree remove may not delete the branch automatically"
  echo "Manually removing branch..."
  git branch -D "$BRANCH_NAME" 2>/dev/null || echo "Could not delete branch"
else
  echo "PASS: Branch was removed"
fi

# List impl branches to verify cleanup
echo ""
echo "Remaining impl branches:"
git branch --list "impl/*" || echo "(none)"
```

**Expected:**
- Branch `impl/e2e-test-done-M1` does not exist
- Note: `git worktree remove` removes the worktree; branch may need separate deletion

**Capture:** Branch list

---

### Step 13: Test Idempotency - Run Done Again

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Attempt to run done again - should fail gracefully
OUTPUT=$(uv run kinfra done "e2e-test-done-M1" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Should fail with exit 1
if [ $EXIT_CODE -eq 1 ]; then
  echo "PASS: Command correctly failed for non-existent worktree (exit 1)"
else
  echo "FAIL: Expected exit code 1, got $EXIT_CODE"
  exit 1
fi

# Should mention worktree not found
if echo "$OUTPUT" | grep -qi "no worktree found\|not found\|does not exist"; then
  echo "PASS: Error message indicates worktree not found"
else
  echo "WARNING: Error message does not clearly indicate worktree not found"
fi
```

**Expected:**
- Exit code 1
- Error message indicates worktree not found

**Capture:** Error output

---

### Step 14: Cleanup - Remove Test Milestone File

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

FEATURE_DIR="docs/designs/e2e-test-done"

# Remove test feature directory
if [ -d "$FEATURE_DIR" ]; then
  rm -rf "$FEATURE_DIR"
  if [ -d "$FEATURE_DIR" ]; then
    echo "WARNING: Could not remove feature directory"
  else
    echo "PASS: Feature directory removed"
  fi
else
  echo "PASS: Feature directory already removed"
fi

# Clean up temp files
rm -f /tmp/e2e_done_test_slot
rm -f /tmp/e2e_done_test_worktree

echo ""
echo "PASS: Cleanup complete"
```

**Expected:**
- Test feature directory removed
- Temp files cleaned up

**Capture:** Cleanup status

---

## Success Criteria

All must pass for test to pass:

- [ ] Setup: kinfra impl creates worktree and claims slot
- [ ] Baseline: Registry shows slot claimed with status "running"
- [ ] Dirty check: Creating uncommitted file makes worktree "dirty"
- [ ] Dirty rejection: `kinfra done` without --force exits 1 with "uncommitted" error
- [ ] No premature cleanup: After dirty rejection, slot still claimed and worktree exists
- [ ] Force override: `kinfra done --force` exits 0 despite dirty state
- [ ] Containers stopped: Health check fails on slot's API port after done
- [ ] Slot released: Registry shows claimed_by = null, status = "stopped"
- [ ] Override removed: docker-compose.override.yml no longer exists
- [ ] Worktree removed: Directory no longer exists, not in git worktree list
- [ ] Idempotency: Running done again on removed worktree exits 1 with clear error

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Slot was claimed before done | claimed_by != null | Setup failed |
| Force duration < 30s | > 30s warns | Container shutdown slow |
| Health check fails after done | HTTP 200 fails | Containers not stopped |
| Registry shows status "stopped" | != "stopped" fails | Status not updated |
| Override file removed | File exists fails | Cleanup incomplete |
| Worktree directory removed | Directory exists fails | git worktree remove failed |
| Dirty check blocks without --force | Exit 0 fails | Dirty protection broken |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| "command not found: kinfra" | CONFIGURATION | Run `uv sync` to install entry points |
| "No worktree found matching" | TEST_ISSUE | Verify impl setup succeeded |
| "No sandbox slot claimed" | CODE_BUG | Check get_slot_for_worktree() path matching |
| Containers still running after done | CODE_BUG | Check stop_slot_containers() in slots.py |
| Slot still claimed after done | CODE_BUG | Check release_slot() in sandbox_registry.py |
| Override file still exists | CODE_BUG | Check remove_override() in override.py |
| Worktree still exists | CODE_BUG | Check git worktree remove call |
| Dirty check not working | CODE_BUG | Check _has_uncommitted_changes() |
| --force not bypassing dirty check | CODE_BUG | Check force parameter handling in done() |
| Permission denied on cleanup | ENVIRONMENT | Check file permissions |

---

## Cleanup

Cleanup is embedded in Step 14. If test fails early, run manual cleanup:

```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Stop any containers for claimed slot (if known)
CLAIMED_SLOT=$(cat /tmp/e2e_done_test_slot 2>/dev/null || echo "")
if [ -n "$CLAIMED_SLOT" ]; then
  SLOT_DIR="$HOME/.ktrdr/sandboxes/slot-$CLAIMED_SLOT"
  docker compose -f "$SLOT_DIR/docker-compose.yml" down 2>/dev/null || true
  rm -f "$SLOT_DIR/docker-compose.override.yml"
fi

# Release slot in registry
REGISTRY_FILE="$HOME/.ktrdr/sandbox/instances.json"
if [ -n "$CLAIMED_SLOT" ] && [ -f "$REGISTRY_FILE" ]; then
  uv run python3 -c "
import json
with open('$REGISTRY_FILE', 'r') as f:
    data = json.load(f)
if '$CLAIMED_SLOT' in data.get('slots', {}):
    data['slots']['$CLAIMED_SLOT']['claimed_by'] = None
    data['slots']['$CLAIMED_SLOT']['claimed_at'] = None
    data['slots']['$CLAIMED_SLOT']['status'] = 'stopped'
    with open('$REGISTRY_FILE', 'w') as f:
        json.dump(data, f, indent=2)
    print('Slot released')
"
fi

# Remove worktree
WORKTREE_PATH="../ktrdr-impl-e2e-test-done-M1"
if [ -d "$WORKTREE_PATH" ]; then
  git worktree remove "$WORKTREE_PATH" --force 2>/dev/null || rm -rf "$WORKTREE_PATH"
  git worktree prune
fi

# Remove branch
git branch -D "impl/e2e-test-done-M1" 2>/dev/null || true

# Remove test feature directory
rm -rf "docs/designs/e2e-test-done"

# Clean temp files
rm -f /tmp/e2e_done_test_slot
rm -f /tmp/e2e_done_test_worktree

echo "Manual cleanup complete"
```

---

## Troubleshooting

**If "command not found: kinfra":**
- **Cause:** Entry point not installed
- **Cure:** Run `uv sync` to reinstall package

**If impl setup fails:**
- **Cause:** No slots available or slot pool not provisioned
- **Cure:** Run `uv run kinfra sandbox provision` or release existing slots

**If dirty check doesn't trigger:**
- **Cause:** File created outside worktree or git not tracking
- **Cure:** Verify file path is inside worktree directory

**If --force doesn't bypass dirty check:**
- **Cause:** Flag not being passed correctly
- **Cure:** Check done.py force parameter handling

**If containers not stopped:**
- **Cause:** docker compose down failed
- **Cure:** Check slots.py stop_slot_containers(), verify docker compose file paths

**If slot not released:**
- **Cause:** Registry save failed, wrong slot lookup
- **Cure:** Check release_slot() in sandbox_registry.py

**If worktree not removed:**
- **Cause:** git worktree remove failed (maybe still dirty)
- **Cure:** The --force flag should allow removal; check for lock files

**If branch still exists:**
- **Cause:** git worktree remove doesn't delete branches by default
- **Cure:** This is expected behavior; branch deletion is optional

---

## Evidence to Capture

- Setup impl output with claimed slot ID
- Registry state before done (baseline)
- Git status showing dirty file
- Dirty rejection error output
- Registry state after dirty rejection
- Force done output with timing
- Docker ps output after done
- Registry state after done (slot released)
- Slot directory listing (override removed)
- Worktree directory check
- Git worktree list
- Branch list
- Idempotency error output
- All exit codes

---

## Notes for Implementation

**Key Files:**
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/done.py` - Main done command
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/override.py` - remove_override()
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/slots.py` - stop_slot_containers()
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/sandbox_registry.py` - release_slot()

**Order of Operations in done:**
1. Find worktree by name (partial match supported)
2. Check if spec worktree (reject - no slot to release)
3. Check dirty state (unless --force)
   - Uncommitted changes: `git status --porcelain`
   - Unpushed commits: `git log @{u}..HEAD`
4. Find claimed slot via registry
5. Stop containers: `docker compose down`
6. Remove override file
7. Release slot in registry
8. Remove worktree: `git worktree remove`

**Dirty State Checks:**
- `_has_uncommitted_changes()` - Uses git status --porcelain
- `_has_unpushed_commits()` - Uses git log @{u}..HEAD

**Worktree Name Matching:**
- Supports partial match: "genome-M1" finds "ktrdr-impl-genome-M1"
- Checks both impl and spec prefixes

**Spec Worktree Handling:**
- Spec worktrees (ktrdr-spec-*) are rejected with instruction to use git worktree remove directly
- They don't have sandbox slots

**State Persistence:**
The tester must maintain these variables across steps:
- `CLAIMED_SLOT` - Slot ID from impl setup
- `WORKTREE_ABS` - Absolute path to worktree

**Alternative Approaches:**
- If dirty check testing is problematic, create a committed but unpushed change instead
- If container stop times out, increase timeout or check docker daemon
- If worktree removal fails, try --force flag on git worktree remove
