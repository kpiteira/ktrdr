---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Backward-Compatible Merge

**Goal:** Merge sandbox changes into main compose file with guaranteed rollback capability.

**Branch:** `feature/sandbox-m6-merge`

**Builds on:** M1-M5 (all previous milestones)

---

## E2E Test Scenario

**Purpose:** Prove merge maintains backward compatibility and rollback works.

**Prerequisites:**
- M1-M5 complete
- `../ktrdr2` environment working with current compose
- At least one sandbox instance tested

```bash
# 1. Pre-merge verification: ktrdr2 works
cd ../ktrdr2
docker compose down -v
docker compose up -d
sleep 45
curl -f http://localhost:8000/api/v1/health  # MUST succeed
docker compose down

# 2. Create rollback point
cd /path/to/ktrdr
git tag sandbox-merge-rollback-point
cp docker-compose.yml docker-compose.yml.pre-sandbox-backup

# 3. Run merge
./scripts/merge-sandbox-compose.sh

# 4. Post-merge verification: ktrdr2 STILL works
cd ../ktrdr2
docker compose up -d
sleep 45
curl -f http://localhost:8000/api/v1/health  # MUST succeed
curl -f http://localhost:3000/api/health     # Grafana
docker compose down

# 5. Verify sandbox still works
cd ../ktrdr--test-feature
ktrdr sandbox up --no-wait
sleep 45
curl -f http://localhost:8001/api/v1/health  # MUST succeed
ktrdr sandbox down

# 6. Run automated verification
./scripts/verify-sandbox-merge.sh
# Should output: ✓ All checks passed. Merge is safe.

# 7. (Optional) Test rollback
./scripts/sandbox-rollback.sh
cd ../ktrdr2
docker compose up -d
# Should work exactly as before
```

**Success Criteria:**
- [ ] `../ktrdr2` works identically before and after merge
- [ ] Default ports (8000, 5432, 3000, etc.) used when no env vars set
- [ ] Sandbox instances still work
- [ ] Rollback script restores original behavior in <30 seconds
- [ ] Automated verification passes

---

## Tasks

### Task 6.1: Create Merge Script

**File:** `scripts/merge-sandbox-compose.sh` (new)
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Create script that merges `docker-compose.sandbox.yml` changes into `docker-compose.yml`.

**Implementation Notes:**

```bash
#!/bin/bash
# scripts/merge-sandbox-compose.sh
# Merges sandbox compose changes into main compose file

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MAIN_COMPOSE="$PROJECT_ROOT/docker-compose.yml"
SANDBOX_COMPOSE="$PROJECT_ROOT/docker-compose.sandbox.yml"
BACKUP_COMPOSE="$PROJECT_ROOT/docker-compose.yml.pre-sandbox-backup"

echo "=== Sandbox Compose Merge ==="
echo ""

# Check prerequisites
if [ ! -f "$SANDBOX_COMPOSE" ]; then
    echo "Error: $SANDBOX_COMPOSE not found"
    exit 1
fi

# Check for existing backup (indicates previous merge attempt)
if [ -f "$BACKUP_COMPOSE" ]; then
    echo "Warning: Backup already exists at $BACKUP_COMPOSE"
    echo "This may indicate a previous merge. Continuing will overwrite."
    read -p "Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create backup
echo "Creating backup: $BACKUP_COMPOSE"
cp "$MAIN_COMPOSE" "$BACKUP_COMPOSE"

# Create git tag
echo "Creating git tag: sandbox-merge-rollback-point"
git tag -f sandbox-merge-rollback-point

# The actual merge: replace main with sandbox
# (In practice, sandbox compose IS the target state)
echo "Merging sandbox changes into main compose..."
cp "$SANDBOX_COMPOSE" "$MAIN_COMPOSE"

# Optionally remove the sandbox file (no longer needed)
echo ""
echo "Merge complete!"
echo ""
echo "Next steps:"
echo "  1. Run ./scripts/verify-sandbox-merge.sh"
echo "  2. Test in ../ktrdr2 with 'docker compose up'"
echo "  3. If issues: ./scripts/sandbox-rollback.sh"
echo ""
echo "After verification, you can delete:"
echo "  - $SANDBOX_COMPOSE"
echo "  - $BACKUP_COMPOSE"
```

**Testing Requirements:**

*Smoke Test:*
```bash
./scripts/merge-sandbox-compose.sh
diff docker-compose.yml docker-compose.sandbox.yml  # Should be identical
ls docker-compose.yml.pre-sandbox-backup  # Should exist
git tag -l | grep sandbox-merge  # Should show tag
```

**Acceptance Criteria:**
- [ ] Creates backup of original compose
- [ ] Creates git tag for rollback
- [ ] Replaces main compose with sandbox compose
- [ ] Clear output and next steps

---

### Task 6.2: Create Verification Script

**File:** `scripts/verify-sandbox-merge.sh` (new)
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Configuration, Cross-Component

**Description:**
Create automated verification script that validates the merge didn't break anything.

**Implementation Notes:**

```bash
#!/bin/bash
# scripts/verify-sandbox-merge.sh
# Verifies sandbox merge maintains backward compatibility

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

FAILED=0

check() {
    local name="$1"
    local cmd="$2"

    echo -n "Checking: $name ... "
    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        FAILED=1
    fi
}

echo "=== Sandbox Merge Verification ==="
echo ""

# Find ktrdr2 directory (parent sibling)
KTRDR2_DIR="$(dirname "$PROJECT_ROOT")/ktrdr2"
if [ ! -d "$KTRDR2_DIR" ]; then
    echo "Warning: ktrdr2 not found at $KTRDR2_DIR"
    echo "Skipping ktrdr2-specific checks"
    KTRDR2_DIR=""
fi

echo "Test 1: Compose file validates"
check "compose config valid" "docker compose -f $PROJECT_ROOT/docker-compose.yml config"

echo ""
echo "Test 2: Default ports in compose (no env vars)"
# Unset any sandbox env vars
unset KTRDR_API_PORT KTRDR_DB_PORT KTRDR_GRAFANA_PORT

check "backend defaults to 8000" "docker compose -f $PROJECT_ROOT/docker-compose.yml config | grep -q '8000:8000'"
check "db defaults to 5432" "docker compose -f $PROJECT_ROOT/docker-compose.yml config | grep -q '5432:5432'"
check "grafana defaults to 3000" "docker compose -f $PROJECT_ROOT/docker-compose.yml config | grep -q '3000:3000'"

if [ -n "$KTRDR2_DIR" ]; then
    echo ""
    echo "Test 3: ktrdr2 starts with default ports"

    # Ensure clean state
    (cd "$KTRDR2_DIR" && docker compose down -v 2>/dev/null) || true

    # Start ktrdr2
    echo "Starting ktrdr2..."
    (cd "$KTRDR2_DIR" && docker compose up -d)

    # Wait for health
    echo "Waiting for health (60s timeout)..."
    for i in {1..30}; do
        if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
            break
        fi
        sleep 2
    done

    check "backend health at 8000" "curl -sf http://localhost:8000/api/v1/health"
    check "grafana at 3000" "curl -sf http://localhost:3000/api/health"

    # Cleanup
    echo "Stopping ktrdr2..."
    (cd "$KTRDR2_DIR" && docker compose down)
fi

echo ""
echo "Test 4: Parameterized ports work"
export KTRDR_API_PORT=8001
export KTRDR_DB_PORT=5433
check "backend uses \$KTRDR_API_PORT" "docker compose -f $PROJECT_ROOT/docker-compose.yml config | grep -q '8001:8000'"
check "db uses \$KTRDR_DB_PORT" "docker compose -f $PROJECT_ROOT/docker-compose.yml config | grep -q '5433:5432'"
unset KTRDR_API_PORT KTRDR_DB_PORT

echo ""
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed. Merge is safe.${NC}"
    exit 0
else
    echo -e "${RED}✗ Some checks failed. Review before proceeding.${NC}"
    exit 1
fi
```

**Testing Requirements:**

*Smoke Test:*
```bash
./scripts/verify-sandbox-merge.sh
# Should show all checks passing
```

**Acceptance Criteria:**
- [ ] Validates compose file syntax
- [ ] Verifies default ports work
- [ ] Tests ktrdr2 if available
- [ ] Tests parameterized ports
- [ ] Clear pass/fail output

---

### Task 6.3: Create Rollback Script

**File:** `scripts/sandbox-rollback.sh` (new)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Create script for emergency rollback if merge breaks things.

**Implementation Notes:**

```bash
#!/bin/bash
# scripts/sandbox-rollback.sh
# Emergency rollback for sandbox merge

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

MAIN_COMPOSE="$PROJECT_ROOT/docker-compose.yml"
BACKUP_COMPOSE="$PROJECT_ROOT/docker-compose.yml.pre-sandbox-backup"

echo "=== Sandbox Rollback ==="
echo ""

# Method 1: Use backup file
if [ -f "$BACKUP_COMPOSE" ]; then
    echo "Restoring from backup: $BACKUP_COMPOSE"
    cp "$BACKUP_COMPOSE" "$MAIN_COMPOSE"
    echo "Done! Backup restored."
    echo ""
    echo "Verify with: docker compose up -d"
    exit 0
fi

# Method 2: Use git tag
if git rev-parse sandbox-merge-rollback-point >/dev/null 2>&1; then
    echo "No backup file found. Using git tag..."
    git checkout sandbox-merge-rollback-point -- docker-compose.yml
    echo "Done! Restored from git tag."
    echo ""
    echo "Verify with: docker compose up -d"
    exit 0
fi

# No rollback option available
echo "Error: No rollback option available"
echo ""
echo "Options:"
echo "  1. git checkout <commit> -- docker-compose.yml"
echo "  2. Restore from your own backup"
exit 1
```

**Testing Requirements:**

*Smoke Test:*
```bash
# After merge
./scripts/sandbox-rollback.sh
docker compose config  # Should be original
```

**Acceptance Criteria:**
- [ ] Restores from backup file if available
- [ ] Falls back to git tag
- [ ] Clear error if no rollback option

---

### Task 6.4: Update Documentation

**File:** `docs/designs/Sandbox/MERGE_CHECKLIST.md` (new)
**Type:** CODING
**Estimated time:** 30 minutes

**Task Categories:** Configuration

**Description:**
Document the merge process and checklist.

**Implementation Notes:**

```markdown
# Sandbox Merge Checklist

## Pre-Merge

- [ ] All M1-M5 milestones complete
- [ ] At least 2 sandbox instances tested end-to-end
- [ ] `../ktrdr2` working with current compose
- [ ] No uncommitted changes in working directory

## Merge Process

1. Create rollback point:
   ```bash
   git tag sandbox-merge-rollback-point
   cp docker-compose.yml docker-compose.yml.pre-sandbox-backup
   ```

2. Run merge:
   ```bash
   ./scripts/merge-sandbox-compose.sh
   ```

3. Verify:
   ```bash
   ./scripts/verify-sandbox-merge.sh
   ```

4. Manual verification:
   ```bash
   cd ../ktrdr2
   docker compose up -d
   # Wait, check health, check Grafana
   docker compose down
   ```

## Post-Merge

- [ ] Verification script passes
- [ ] Manual ktrdr2 test passes
- [ ] Sandbox still works
- [ ] PR created and merged
- [ ] Delete `docker-compose.sandbox.yml`
- [ ] Delete `docker-compose.yml.pre-sandbox-backup`

## Rollback

If anything breaks:

```bash
./scripts/sandbox-rollback.sh
```

This restores the original compose file in <30 seconds.
```

**Acceptance Criteria:**
- [ ] Clear checklist format
- [ ] All steps documented
- [ ] Rollback instructions prominent

---

## Completion Checklist

- [ ] All 4 tasks complete and committed
- [ ] Merge script created and tested
- [ ] Verification script passes
- [ ] Rollback script tested
- [ ] Documentation complete
- [ ] ktrdr2 works after merge
- [ ] At least one sandbox works after merge

---

## Architecture Alignment

| Architecture Decision | How This Milestone Implements It |
|-----------------------|----------------------------------|
| Two-file strategy | Merge only after validation |
| Backward compatibility | Verification script confirms default ports |
| Easy rollback | Script + git tag + backup file |
| Defaults match current | `${VAR:-default}` pattern with current values |
