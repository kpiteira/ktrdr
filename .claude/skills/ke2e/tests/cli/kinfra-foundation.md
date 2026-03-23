# Test: cli/kinfra-foundation

**Purpose:** Validate the new kinfra CLI foundation works correctly with sandbox, local-prod, and deploy subcommands, while ktrdr sandbox shows deprecation warnings

**Duration:** <30 seconds

**Category:** CLI / Infrastructure

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates CLI structure, not running services)

**Test-specific checks:**
- [ ] uv is available in PATH
- [ ] Current directory is KTRDR repository root

---

## Test Data

```yaml
# No external data required - testing CLI structure only
cli_commands:
  - kinfra --help
  - kinfra sandbox --help
  - kinfra local-prod --help
  - kinfra deploy --help
  - ktrdr sandbox status  # deprecated, should warn
expected_subcommands:
  - sandbox
  - local-prod
  - deploy
deprecated_warning_pattern: "deprecated"
```

**Why this data:** Tests the structural completeness of the new kinfra CLI and backward compatibility of deprecated ktrdr sandbox commands.

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Check docker-compose.yml symlink removed | File not found (exit 1) | exit_code, error_message |
| 2 | Run kinfra --help | Shows help with sandbox, local-prod, deploy | help_output |
| 3 | Run kinfra sandbox --help | Shows sandbox subcommands | sandbox_help |
| 4 | Run kinfra sandbox status | Returns status (exit 0 or 1 if not in sandbox) | exit_code, output |
| 5 | Run ktrdr sandbox status | Shows deprecation warning | warning_output |
| 6 | Verify kinfra local-prod available | Shows local-prod help | local_prod_help |
| 7 | Verify kinfra deploy available | Shows deploy help | deploy_help |

**Detailed Steps:**

### Step 1: Verify docker-compose.yml Symlink Removed

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Check that docker-compose.yml symlink is removed
if [ -L docker-compose.yml ]; then
  echo "FAIL: docker-compose.yml symlink still exists"
  ls -la docker-compose.yml
  exit 1
elif [ -f docker-compose.yml ]; then
  echo "FAIL: docker-compose.yml regular file exists (should be removed)"
  ls -la docker-compose.yml
  exit 1
else
  echo "PASS: docker-compose.yml does not exist"
  exit 0
fi
```

**Expected:**
- Exit code 0
- Output: "PASS: docker-compose.yml does not exist"

**Capture:** Exit code, output message

### Step 2: Verify kinfra CLI Installed and Shows Help

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run kinfra --help
OUTPUT=$(uv run kinfra --help 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Verify expected subcommands are present
if echo "$OUTPUT" | grep -q "sandbox" && \
   echo "$OUTPUT" | grep -q "local-prod" && \
   echo "$OUTPUT" | grep -q "deploy"; then
  echo "PASS: All expected subcommands present"
else
  echo "FAIL: Missing expected subcommands"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Help text contains "sandbox", "local-prod", "deploy"
- Help text includes description of kinfra purpose

**Capture:** Full help output, presence of subcommands

### Step 3: Verify kinfra sandbox --help

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run kinfra sandbox --help
OUTPUT=$(uv run kinfra sandbox --help 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Check for key sandbox subcommands
EXPECTED_COMMANDS="create init up down status list destroy"
MISSING=""
for cmd in $EXPECTED_COMMANDS; do
  if ! echo "$OUTPUT" | grep -qw "$cmd"; then
    MISSING="$MISSING $cmd"
  fi
done

if [ -z "$MISSING" ]; then
  echo "PASS: All sandbox subcommands present"
else
  echo "FAIL: Missing sandbox subcommands:$MISSING"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Help text shows sandbox subcommands: create, init, up, down, status, list, destroy

**Capture:** Sandbox help output, list of available commands

### Step 4: Verify kinfra sandbox status Works

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run kinfra sandbox status
# Note: This may exit 1 if not in a sandbox directory, but should not error on CLI structure
OUTPUT=$(uv run kinfra sandbox status 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Exit 1 is acceptable if "Not in a sandbox directory"
# Exit 0 is acceptable if in a sandbox directory
# Any other exit code or Python traceback is a failure
if [ $EXIT_CODE -eq 0 ]; then
  echo "PASS: kinfra sandbox status executed successfully (in sandbox)"
elif [ $EXIT_CODE -eq 1 ]; then
  if echo "$OUTPUT" | grep -qi "not in a sandbox directory\|.env.sandbox"; then
    echo "PASS: kinfra sandbox status executed correctly (not in sandbox)"
  else
    echo "FAIL: Unexpected exit code 1 with unexpected output"
    exit 1
  fi
else
  echo "FAIL: Unexpected exit code $EXIT_CODE"
  exit 1
fi
```

**Expected:**
- Exit code 0 (if in sandbox) or 1 (if not in sandbox with appropriate message)
- No Python traceback or import errors
- Recognizes environment correctly

**Capture:** Command output, exit code

### Step 5: Verify ktrdr sandbox Shows Deprecation Warning

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run ktrdr sandbox status and capture both stdout and stderr
OUTPUT=$(uv run ktrdr sandbox status 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Check for deprecation warning (case insensitive)
if echo "$OUTPUT" | grep -iq "deprecated"; then
  echo "PASS: Deprecation warning present"
else
  echo "FAIL: No deprecation warning found in output"
  echo "Expected output to contain 'deprecated'"
  exit 1
fi

# Also verify it suggests using kinfra instead
if echo "$OUTPUT" | grep -iq "kinfra"; then
  echo "PASS: Suggests using kinfra"
else
  echo "WARNING: Does not explicitly suggest using kinfra"
fi
```

**Expected:**
- Output contains "deprecated" (case insensitive)
- Output suggests using "kinfra sandbox" instead
- Command still functions (backward compatible)

**Capture:** Full output including deprecation warning

### Step 6: Verify kinfra local-prod Available

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run kinfra local-prod --help
OUTPUT=$(uv run kinfra local-prod --help 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
  echo "PASS: kinfra local-prod --help succeeded"
else
  echo "FAIL: kinfra local-prod --help failed with exit code $EXIT_CODE"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Help text for local-prod subcommand displayed

**Capture:** local-prod help output

### Step 7: Verify kinfra deploy Available

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Run kinfra deploy --help
OUTPUT=$(uv run kinfra deploy --help 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
  echo "PASS: kinfra deploy --help succeeded"
else
  echo "FAIL: kinfra deploy --help failed with exit code $EXIT_CODE"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Help text for deploy subcommand displayed

**Capture:** deploy help output

### Step 8: Verify Entry Points in pyproject.toml

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Check pyproject.toml for kinfra entry point
if grep -q 'kinfra = "ktrdr.cli.kinfra.main:main"' pyproject.toml; then
  echo "PASS: kinfra entry point correctly defined"
else
  echo "FAIL: kinfra entry point not found in pyproject.toml"
  exit 1
fi

# Verify ktrdr entry point still exists (backward compatibility)
if grep -q 'ktrdr = "ktrdr.cli:main"' pyproject.toml; then
  echo "PASS: ktrdr entry point still exists (backward compatible)"
else
  echo "FAIL: ktrdr entry point missing from pyproject.toml"
  exit 1
fi
```

**Expected:**
- Both entry points exist in pyproject.toml
- kinfra points to ktrdr.cli.kinfra.main:main
- ktrdr points to ktrdr.cli:main

**Capture:** Entry point definitions

---

## Success Criteria

All must pass for test to pass:

- [ ] docker-compose.yml symlink does not exist in repository root
- [ ] `uv run kinfra --help` exits 0 and shows sandbox, local-prod, deploy
- [ ] `uv run kinfra sandbox --help` exits 0 and shows sandbox subcommands
- [ ] `uv run kinfra sandbox status` executes without Python errors (exit 0 or 1 with message)
- [ ] `uv run ktrdr sandbox status` output contains "deprecated" warning
- [ ] `uv run kinfra local-prod --help` exits 0
- [ ] `uv run kinfra deploy --help` exits 0
- [ ] pyproject.toml contains kinfra entry point

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| kinfra --help shows 3+ subcommands | < 3 fails | CLI not fully wired |
| No Python tracebacks in output | Any traceback fails | Import or runtime error |
| Deprecation warning is visible | Not visible fails | Deprecation callback not registered |
| ktrdr sandbox still works | Exits with error fails | Backward compatibility broken |
| Help text is not empty | Empty output fails | CLI not installed correctly |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| "command not found: kinfra" | CONFIGURATION | Run `uv sync` to install entry points |
| "No module named 'ktrdr.cli.kinfra'" | CODE_BUG | Check kinfra module exists at ktrdr/cli/kinfra/ |
| docker-compose.yml still exists | CODE_BUG | Remove symlink from repository |
| No deprecation warning | CODE_BUG | Check _sandbox_deprecation_callback in ktrdr/cli/sandbox.py |
| Missing subcommand in help | CODE_BUG | Check app.add_typer() calls in ktrdr/cli/kinfra/main.py |
| Python traceback | CODE_BUG | Check import statements and dependencies |
| Entry point missing | CONFIGURATION | Add kinfra entry to pyproject.toml [project.scripts] |

---

## Cleanup

None required - this test only reads CLI help output and does not modify state.

---

## Troubleshooting

**If "command not found: kinfra":**
- **Cause:** Entry point not installed after adding to pyproject.toml
- **Cure:** Run `uv sync` to reinstall package with new entry points

**If "No module named 'ktrdr.cli.kinfra'":**
- **Cause:** kinfra package not created or __init__.py missing
- **Cure:** Verify ktrdr/cli/kinfra/__init__.py exists and imports main.py

**If docker-compose.yml symlink exists:**
- **Cause:** Symlink not removed as part of M1 migration
- **Cure:** Remove symlink: `rm docker-compose.yml`

**If no deprecation warning in ktrdr sandbox output:**
- **Cause:** Deprecation callback not registered in sandbox_app
- **Cure:** Check `@sandbox_app.callback(invoke_without_command=True)` decorator

**If subcommand missing from kinfra --help:**
- **Cause:** Typer subapp not registered with main app
- **Cure:** Check `app.add_typer()` calls in ktrdr/cli/kinfra/main.py

---

## Evidence to Capture

- docker-compose.yml check output (file presence/absence)
- kinfra --help output
- kinfra sandbox --help output
- kinfra sandbox status output
- ktrdr sandbox status output (with deprecation warning)
- kinfra local-prod --help output
- kinfra deploy --help output
- pyproject.toml entry points section
- All exit codes

---

## Notes for Implementation

**Key Files:**
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/main.py` - kinfra CLI main entry point
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/sandbox.py` - kinfra sandbox commands (new)
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/sandbox.py` - ktrdr sandbox commands (deprecated)
- `/Users/karl/Documents/dev/ktrdr--stream-b/pyproject.toml` - Entry points definition

**Deprecation Warning Format:**
The ktrdr sandbox commands show:
```
Warning: 'ktrdr sandbox <cmd>' is deprecated. Use 'kinfra sandbox <cmd>' instead.
```

**kinfra CLI Structure:**
```
kinfra
  sandbox    - Manage isolated development sandbox instances
  local-prod - Manage local-prod production-like environment
  deploy     - Deploy KTRDR services to pre-production environment
```

**Alternative Approaches:**
- If kinfra sandbox status fails in non-sandbox directory, that is expected behavior
- The test accepts both exit 0 (in sandbox) and exit 1 (not in sandbox with message)
- For CI environments without sandbox, focus on --help tests which don't require sandbox state
