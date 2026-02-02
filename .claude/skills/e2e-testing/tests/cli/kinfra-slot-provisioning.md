# Test: cli/kinfra-slot-provisioning

**Purpose:** Validate kinfra sandbox provision creates slot pool infrastructure with correct profiles, files, and registry entries

**Duration:** <30 seconds

**Category:** CLI / Infrastructure

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates CLI file creation, not running services)

**Test-specific checks:**
- [ ] uv is available in PATH
- [ ] Current directory is KTRDR repository root (contains pyproject.toml)
- [ ] ~/.ktrdr/sandboxes/ does not exist OR can be safely removed for test

---

## Test Data

```yaml
# Expected slot configuration
slots:
  - id: 1
    profile: light
    workers: { backtest: 1, training: 1 }
    ports: { api: 8001, db: 5433, grafana: 3001, jaeger_ui: 16687, prometheus: 9091 }
  - id: 2
    profile: light
    workers: { backtest: 1, training: 1 }
    ports: { api: 8002, db: 5434, grafana: 3002, jaeger_ui: 16688, prometheus: 9092 }
  - id: 3
    profile: light
    workers: { backtest: 1, training: 1 }
    ports: { api: 8003, db: 5435, grafana: 3003, jaeger_ui: 16689, prometheus: 9093 }
  - id: 4
    profile: light
    workers: { backtest: 1, training: 1 }
    ports: { api: 8004, db: 5436, grafana: 3004, jaeger_ui: 16690, prometheus: 9094 }
  - id: 5
    profile: standard
    workers: { backtest: 2, training: 2 }
    ports: { api: 8005, db: 5437, grafana: 3005, jaeger_ui: 16691, prometheus: 9095 }
  - id: 6
    profile: heavy
    workers: { backtest: 4, training: 4 }
    ports: { api: 8006, db: 5438, grafana: 3006, jaeger_ui: 16692, prometheus: 9096 }

registry_path: ~/.ktrdr/sandboxes/registry.json
sandboxes_path: ~/.ktrdr/sandboxes/
```

**Why this data:** Tests the documented slot pool specification with correct port offsets (API=8000+slot, DB=5432+slot, etc.) and profile distribution (4 light, 1 standard, 1 heavy).

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Clean up existing sandboxes dir | Directory removed if exists | cleanup_result |
| 2 | Run provision --dry-run | Shows what would be created | dry_run_output |
| 3 | Run provision | Creates 6 slot directories | provision_output |
| 4 | Verify slot directories exist | All 6 slot-{1..6}/ exist | directory_listing |
| 5 | Verify .env.sandbox in each slot | Files exist with correct content | env_files_content |
| 6 | Verify docker-compose.yml in each slot | Files exist and non-empty | compose_files_status |
| 7 | Verify registry.json | Has v2 schema with all slots | registry_content |
| 8 | Run slots command | Shows table with 6 slots | slots_output |
| 9 | Run provision again (idempotent) | Shows "already exists, skipping" | idempotent_output |
| 10 | Clean up | Remove test directories | cleanup_final |

**Detailed Steps:**

### Step 1: Clean Up Existing Sandboxes Directory

**Command:**
```bash
# Remove existing sandboxes directory for clean test
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

if [ -d "$SANDBOXES_DIR" ]; then
  echo "Removing existing $SANDBOXES_DIR for clean test"
  rm -rf "$SANDBOXES_DIR"
  if [ -d "$SANDBOXES_DIR" ]; then
    echo "FAIL: Could not remove $SANDBOXES_DIR"
    exit 1
  fi
  echo "PASS: Cleaned up existing directory"
else
  echo "PASS: No existing directory to clean"
fi
```

**Expected:**
- Exit code 0
- Directory either did not exist or was successfully removed

**Capture:** Cleanup status message

### Step 2: Run Provision with --dry-run

**Command:**
```bash
cd /path/to/ktrdr/repo

OUTPUT=$(uv run kinfra sandbox provision --dry-run 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Verify dry run output mentions what would be created
if echo "$OUTPUT" | grep -q "Would create slot 1"; then
  echo "PASS: Dry run shows slot 1"
else
  echo "FAIL: Dry run does not mention slot 1"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Would create slot 6"; then
  echo "PASS: Dry run shows slot 6"
else
  echo "FAIL: Dry run does not mention slot 6"
  exit 1
fi

# Verify no files were created
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"
if [ -d "$SANDBOXES_DIR/slot-1" ]; then
  echo "FAIL: Dry run created actual files"
  exit 1
else
  echo "PASS: Dry run did not create files"
fi
```

**Expected:**
- Exit code 0
- Output contains "Would create slot X" for each slot
- Output shows port allocations (API, DB)
- No actual files created

**Capture:** Full dry-run output

### Step 3: Run Provision

**Command:**
```bash
cd /path/to/ktrdr/repo

OUTPUT=$(uv run kinfra sandbox provision 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Verify success message
if [ $EXIT_CODE -eq 0 ]; then
  echo "PASS: Provision completed successfully"
else
  echo "FAIL: Provision failed with exit code $EXIT_CODE"
  exit 1
fi

# Verify created message
if echo "$OUTPUT" | grep -q "Created 6 slot"; then
  echo "PASS: Created 6 slots message present"
else
  echo "FAIL: Expected 'Created 6 slot' in output"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Output shows "Created slot X (profile)" for each slot
- Output shows "Created 6 slot(s)" summary

**Capture:** Full provision output

### Step 4: Verify Slot Directories Exist

**Command:**
```bash
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

MISSING=""
for i in 1 2 3 4 5 6; do
  SLOT_DIR="$SANDBOXES_DIR/slot-$i"
  if [ ! -d "$SLOT_DIR" ]; then
    MISSING="$MISSING $i"
  fi
done

if [ -z "$MISSING" ]; then
  echo "PASS: All 6 slot directories exist"
  ls -la "$SANDBOXES_DIR"
else
  echo "FAIL: Missing slot directories:$MISSING"
  exit 1
fi
```

**Expected:**
- All 6 directories exist: slot-1/ through slot-6/
- Each is a valid directory

**Capture:** Directory listing of ~/.ktrdr/sandboxes/

### Step 5: Verify .env.sandbox Files

**Command:**
```bash
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

# Check each slot has correct .env.sandbox
ALL_PASS=true

# Slot 1: light, API=8001
ENV_1="$SANDBOXES_DIR/slot-1/.env.sandbox"
if [ ! -f "$ENV_1" ]; then
  echo "FAIL: slot-1/.env.sandbox missing"
  ALL_PASS=false
else
  if grep -q "SLOT_ID=1" "$ENV_1" && grep -q "KTRDR_API_PORT=8001" "$ENV_1"; then
    echo "PASS: slot-1 has correct SLOT_ID and API_PORT"
  else
    echo "FAIL: slot-1 has wrong values"
    cat "$ENV_1"
    ALL_PASS=false
  fi
fi

# Slot 5: API=8005
ENV_5="$SANDBOXES_DIR/slot-5/.env.sandbox"
if [ ! -f "$ENV_5" ]; then
  echo "FAIL: slot-5/.env.sandbox missing"
  ALL_PASS=false
else
  if grep -q "SLOT_ID=5" "$ENV_5" && grep -q "KTRDR_API_PORT=8005" "$ENV_5"; then
    echo "PASS: slot-5 has correct SLOT_ID and API_PORT"
  else
    echo "FAIL: slot-5 has wrong values"
    cat "$ENV_5"
    ALL_PASS=false
  fi
fi

# Slot 6: API=8006, DB=5438
ENV_6="$SANDBOXES_DIR/slot-6/.env.sandbox"
if [ ! -f "$ENV_6" ]; then
  echo "FAIL: slot-6/.env.sandbox missing"
  ALL_PASS=false
else
  if grep -q "SLOT_ID=6" "$ENV_6" && \
     grep -q "KTRDR_API_PORT=8006" "$ENV_6" && \
     grep -q "KTRDR_DB_PORT=5438" "$ENV_6"; then
    echo "PASS: slot-6 has correct ports"
  else
    echo "FAIL: slot-6 has wrong values"
    cat "$ENV_6"
    ALL_PASS=false
  fi
fi

if $ALL_PASS; then
  echo ""
  echo "PASS: All .env.sandbox files verified"
else
  exit 1
fi
```

**Expected:**
- Each slot has .env.sandbox file
- SLOT_ID matches slot number
- KTRDR_API_PORT = 8000 + slot_id
- KTRDR_DB_PORT = 5432 + slot_id
- Other ports follow same pattern

**Capture:** Contents of .env.sandbox for slots 1, 5, and 6

### Step 6: Verify docker-compose.yml Files

**Command:**
```bash
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

MISSING=""
EMPTY=""
for i in 1 2 3 4 5 6; do
  COMPOSE_FILE="$SANDBOXES_DIR/slot-$i/docker-compose.yml"
  if [ ! -f "$COMPOSE_FILE" ]; then
    MISSING="$MISSING $i"
  elif [ ! -s "$COMPOSE_FILE" ]; then
    EMPTY="$EMPTY $i"
  fi
done

if [ -z "$MISSING" ] && [ -z "$EMPTY" ]; then
  echo "PASS: All docker-compose.yml files exist and are non-empty"
  # Show first few lines of one file as sample
  echo ""
  echo "Sample (slot-1/docker-compose.yml first 10 lines):"
  head -10 "$SANDBOXES_DIR/slot-1/docker-compose.yml"
else
  if [ -n "$MISSING" ]; then
    echo "FAIL: Missing docker-compose.yml in slots:$MISSING"
  fi
  if [ -n "$EMPTY" ]; then
    echo "FAIL: Empty docker-compose.yml in slots:$EMPTY"
  fi
  exit 1
fi
```

**Expected:**
- Each slot has docker-compose.yml file
- Files are non-empty
- Files contain valid YAML (service definitions)

**Capture:** First 10 lines of slot-1/docker-compose.yml as sample

### Step 7: Verify Registry Schema

**Command:**
```bash
REGISTRY_FILE="$HOME/.ktrdr/sandboxes/registry.json"

if [ ! -f "$REGISTRY_FILE" ]; then
  echo "FAIL: registry.json does not exist"
  exit 1
fi

echo "Registry content:"
cat "$REGISTRY_FILE"
echo ""

# Check version = 2
if grep -q '"version": 2' "$REGISTRY_FILE"; then
  echo "PASS: version = 2"
else
  echo "FAIL: version is not 2"
  exit 1
fi

# Check slots dict exists with 6 entries
SLOT_COUNT=$(grep -o '"slot_id":' "$REGISTRY_FILE" | wc -l | tr -d ' ')
if [ "$SLOT_COUNT" -eq 6 ]; then
  echo "PASS: 6 slots in registry"
else
  echo "FAIL: Expected 6 slots, found $SLOT_COUNT"
  exit 1
fi

# Check profiles are correct
if grep -q '"profile": "light"' "$REGISTRY_FILE"; then
  echo "PASS: Contains light profile"
else
  echo "FAIL: Missing light profile"
  exit 1
fi

if grep -q '"profile": "standard"' "$REGISTRY_FILE"; then
  echo "PASS: Contains standard profile"
else
  echo "FAIL: Missing standard profile"
  exit 1
fi

if grep -q '"profile": "heavy"' "$REGISTRY_FILE"; then
  echo "PASS: Contains heavy profile"
else
  echo "FAIL: Missing heavy profile"
  exit 1
fi

echo ""
echo "PASS: Registry schema verified"
```

**Expected:**
- registry.json exists at ~/.ktrdr/sandboxes/registry.json
- version field = 2
- slots dict contains 6 entries
- Profiles: 4 light, 1 standard, 1 heavy

**Capture:** Full registry.json content

### Step 8: Run slots Command

**Command:**
```bash
cd /path/to/ktrdr/repo

OUTPUT=$(uv run kinfra sandbox slots 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: slots command failed"
  exit 1
fi

# Verify table header
if echo "$OUTPUT" | grep -q "Slot"; then
  echo "PASS: Table header present"
else
  echo "FAIL: Table header missing"
  exit 1
fi

# Verify all slots shown
for i in 1 2 3 4 5 6; do
  if echo "$OUTPUT" | grep -qE "^.*$i.*"; then
    echo "PASS: Slot $i visible in table"
  else
    echo "FAIL: Slot $i not visible"
    exit 1
  fi
done

# Verify profiles visible
if echo "$OUTPUT" | grep -q "light" && \
   echo "$OUTPUT" | grep -q "standard" && \
   echo "$OUTPUT" | grep -q "heavy"; then
  echo "PASS: All profiles visible"
else
  echo "FAIL: Missing profiles in output"
  exit 1
fi

echo ""
echo "PASS: slots command displays correctly"
```

**Expected:**
- Exit code 0
- Table with columns: Slot, Profile, API Port, Claimed By, Status
- All 6 slots shown
- Profiles correct (light/standard/heavy)
- Status shows "stopped" (nothing running)

**Capture:** Full slots command output

### Step 9: Verify Idempotency

**Command:**
```bash
cd /path/to/ktrdr/repo

OUTPUT=$(uv run kinfra sandbox provision 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: Second provision failed"
  exit 1
fi

# Verify skipped message
if echo "$OUTPUT" | grep -q "already exists, skipping"; then
  echo "PASS: Shows 'already exists, skipping'"
else
  echo "FAIL: Does not show skip message"
  exit 1
fi

# Verify no new slots created
if echo "$OUTPUT" | grep -q "Created.*slot"; then
  echo "FAIL: Should not create new slots"
  exit 1
else
  echo "PASS: No new slots created"
fi

if echo "$OUTPUT" | grep -q "Skipped 6"; then
  echo "PASS: Shows 'Skipped 6'"
else
  echo "WARNING: Expected 'Skipped 6' in output"
fi

echo ""
echo "PASS: Provision is idempotent"
```

**Expected:**
- Exit code 0
- Shows "already exists, skipping" for each slot
- Shows "Skipped 6 existing slot(s)"
- Does not show "Created" messages

**Capture:** Second provision output

### Step 10: Clean Up

**Command:**
```bash
SANDBOXES_DIR="$HOME/.ktrdr/sandboxes"

# Remove test directories
if [ -d "$SANDBOXES_DIR" ]; then
  rm -rf "$SANDBOXES_DIR"
  if [ -d "$SANDBOXES_DIR" ]; then
    echo "WARNING: Could not clean up $SANDBOXES_DIR"
  else
    echo "PASS: Cleaned up test directories"
  fi
else
  echo "PASS: Nothing to clean up"
fi
```

**Expected:**
- Test directories removed
- System returned to pre-test state

**Capture:** Cleanup status

---

## Success Criteria

All must pass for test to pass:

- [ ] `kinfra sandbox provision --dry-run` shows all 6 slots without creating files
- [ ] `kinfra sandbox provision` exits 0 and creates 6 slot directories
- [ ] Each slot-{1..6}/ directory contains .env.sandbox and docker-compose.yml
- [ ] .env.sandbox files have correct SLOT_ID and port allocations
- [ ] Port formula correct: API=8000+slot, DB=5432+slot, etc.
- [ ] Slot profiles correct: slots 1-4 light, slot 5 standard, slot 6 heavy
- [ ] registry.json has version=2 and slots dict with 6 entries
- [ ] `kinfra sandbox slots` displays table with all 6 slots
- [ ] Second `kinfra sandbox provision` is idempotent (skips existing)

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| All 6 directories created | <6 fails | Loop or error in provisioning |
| Port offset formula consistent | Any wrong port fails | Port calculation bug |
| Profile distribution 4:1:1 | Different distribution fails | SLOT_PROFILES config wrong |
| Registry version = 2 | version != 2 fails | Schema migration not run |
| docker-compose.yml non-empty | Empty file fails | Template copy failed |
| dry-run creates no files | Files created fails | dry-run not honored |
| Second provision skips all | Creates any fails | Idempotency broken |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| "command not found: kinfra" | CONFIGURATION | Run `uv sync` to install entry points |
| "No module named 'ktrdr.cli.kinfra'" | CODE_BUG | Check kinfra module exists at ktrdr/cli/kinfra/ |
| Permission denied creating directory | ENVIRONMENT | Check ~/.ktrdr/ permissions |
| Wrong port in .env.sandbox | CODE_BUG | Check _get_slot_ports() in sandbox.py |
| Wrong profile for slot | CODE_BUG | Check SLOT_PROFILES dict in sandbox.py |
| registry.json missing | CODE_BUG | Check _update_registry_with_slots() |
| registry.json version != 2 | CODE_BUG | Check REGISTRY_VERSION in sandbox_registry.py |
| docker-compose.yml empty | CODE_BUG | Check get_compose_template() in templates/__init__.py |
| dry-run creates files | CODE_BUG | Check if dry_run flag is checked before file ops |
| "slots" command shows no slots | CODE_BUG | Check registry loading in slots() command |
| Second provision creates new slots | CODE_BUG | Check slot_path.exists() check |

---

## Cleanup

Remove test artifacts:
```bash
rm -rf ~/.ktrdr/sandboxes/
```

Note: This removes the entire sandboxes directory. If there are real sandboxes in use, back them up first. The test is designed to run on a clean system or one where sandboxes can be safely removed.

---

## Troubleshooting

**If "command not found: kinfra":**
- **Cause:** Entry point not installed after adding to pyproject.toml
- **Cure:** Run `uv sync` to reinstall package with new entry points

**If "Permission denied" creating directories:**
- **Cause:** ~/.ktrdr/ owned by different user or has restrictive permissions
- **Cure:** Check ownership: `ls -la ~/.ktrdr/`, fix with `chown` if needed

**If ports are wrong (e.g., slot 1 has API=8002):**
- **Cause:** Off-by-one error in _get_slot_ports()
- **Cure:** Verify formula: port = base_port + slot_id

**If profiles are wrong (e.g., slot 5 is "light"):**
- **Cause:** SLOT_PROFILES dict has wrong mapping
- **Cure:** Check ktrdr/cli/kinfra/sandbox.py SLOT_PROFILES constant

**If registry.json has version=1:**
- **Cause:** _update_registry_with_slots() not setting version
- **Cure:** Check Registry class and save_registry()

**If docker-compose.yml is empty:**
- **Cause:** Template file missing or get_compose_template() returns empty
- **Cure:** Check ktrdr/cli/kinfra/templates/docker-compose.base.yml exists

**If "slots" command shows "No slots provisioned":**
- **Cause:** Registry not being read from correct path, or slots dict empty
- **Cure:** Check load_registry() and slots() command

---

## Evidence to Capture

- dry-run output (full)
- provision output (full)
- Directory listing: `ls -la ~/.ktrdr/sandboxes/`
- .env.sandbox contents for slots 1, 5, 6
- docker-compose.yml first 10 lines for slot-1
- registry.json full content
- slots command output (full)
- Second provision output (idempotency check)

---

## Notes for Implementation

**Key Files:**
- `/Users/karl/Documents/dev/ktrdr--indicator-std/ktrdr/cli/kinfra/sandbox.py` - provision and slots commands
- `/Users/karl/Documents/dev/ktrdr--indicator-std/ktrdr/cli/sandbox_registry.py` - Registry and SlotInfo classes
- `/Users/karl/Documents/dev/ktrdr--indicator-std/ktrdr/cli/kinfra/templates/__init__.py` - get_compose_template()
- `/Users/karl/Documents/dev/ktrdr--indicator-std/ktrdr/cli/kinfra/templates/docker-compose.base.yml` - compose template

**Port Allocation Scheme:**
```
Slot 1: API=8001, DB=5433, Grafana=3001, Jaeger=16687, Prometheus=9091
Slot 2: API=8002, DB=5434, Grafana=3002, Jaeger=16688, Prometheus=9092
...
Slot 6: API=8006, DB=5438, Grafana=3006, Jaeger=16692, Prometheus=9096
```

**Profile Distribution:**
- Slots 1-4: light (1 backtest worker, 1 training worker each)
- Slot 5: standard (2 of each)
- Slot 6: heavy (4 of each)

**Registry Location:**
- Old (v1): ~/.ktrdr/sandbox/instances.json
- New (v2): ~/.ktrdr/sandboxes/registry.json (note: sandboxes with 's')

The registry may be in either location. The provision command creates infrastructure at ~/.ktrdr/sandboxes/ but registry loading checks ~/.ktrdr/sandbox/. Verify which path is actually used.

**Alternative Approaches:**
- If cleanup fails due to permissions, skip and document as prerequisite
- If slots command fails to show table (rich not available), check for plain text output
- Test can be run from any KTRDR repository directory, not just main repo
