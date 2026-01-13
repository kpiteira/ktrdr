---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Shell Command

**Goal:** User can run `ktrdr sandbox shell` to open an interactive shell in a sandbox container.

**Branch:** `feature/sandbox-shell`

---

## Task 1.1: Implement Shell Command

**File:** `ktrdr/cli/sandbox.py`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** API Endpoint, Wiring/DI

**Description:**
Add a `shell` subcommand to the existing `sandbox_app` Typer group. The command opens an interactive shell in a specified container (defaulting to `backend`).

**Implementation Notes:**
- Follow the pattern of existing commands like `logs` which also wrap `docker compose`
- Use `load_env_sandbox()` to get environment configuration
- Use `find_compose_file()` to locate the compose file
- Try `bash` first, fall back to `sh` if unavailable (exit code 126)
- Must run interactively (no `-T` flag, unlike migrations in `up` command)

**Testing Requirements:**

*Unit Tests:* `tests/unit/cli/test_sandbox_shell.py`
- [ ] `test_shell_default_service()` — verify default argument is "backend"
- [ ] `test_shell_custom_service()` — verify custom service passed to docker command
- [ ] `test_shell_not_in_sandbox_directory()` — verify error when `.env.sandbox` missing
- [ ] `test_shell_no_compose_file()` — verify error when compose file missing

*Integration Tests:*
- None required (this wraps docker compose, integration is via E2E)

*Smoke Test:*
```bash
# From sandbox directory with running stack
ktrdr sandbox shell
# Should open bash prompt
```

**Acceptance Criteria:**
- [ ] `ktrdr sandbox shell` opens shell in backend container
- [ ] `ktrdr sandbox shell db` opens shell in db container
- [ ] Error message shown when not in sandbox directory
- [ ] Error message shown when service not running
- [ ] Unit tests written and passing

---

## Task 1.2: Execute E2E Test

**Type:** VALIDATION
**Estimated time:** 5 min

**Description:**
Run the E2E test using the e2e-tester agent to validate the shell command works correctly. The test specification is in the E2E Validation section below.

**Implementation Notes:**
- Invoke the e2e-tester agent with the test specification from E2E Validation section
- Requires sandbox to be running
- Test validates both happy path and error handling

**Acceptance Criteria:**
- [ ] E2E test passes (all success criteria met)
- [ ] No regressions in existing sandbox commands

---

## E2E Validation

### Tests to Run

| Test | Purpose | Source |
|------|---------|--------|
| sandbox/shell | Verify shell command opens container shell | New (architect-designed) |

### New Test Specification (from e2e-test-architect)

#### Test: sandbox/shell

**Purpose:** Validate that `ktrdr sandbox shell` opens an interactive shell inside a running sandbox container and properly handles service selection and error cases

**Duration:** ~30 seconds

**Pre-flight:** preflight/common.md

**Prerequisites:**
- Sandbox instance exists and is running
- Current directory is the sandbox directory

---

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| 1 | Verify sandbox context | `.env.sandbox` exists and readable | INSTANCE_ID, KTRDR_API_PORT |
| 2 | Test default shell (backend) | Container hostname returned | container_hostname |
| 3 | Verify inside container filesystem | `/app` directory exists | container_paths |
| 4 | Test custom service (db) | Database container shell works | db_hostname, psql version |
| 5 | Test error outside sandbox | Proper error message | error_output |
| 6 | Verify container environment | Container env vars differ from host | HOME, PWD comparison |

**Key Verification Commands:**

```bash
# Step 2: Test backend shell access (non-interactive)
docker compose -f $COMPOSE_FILE exec -T backend hostname

# Step 4: Test db service
docker compose -f $COMPOSE_FILE exec -T db psql --version

# Step 5: Test error handling (from non-sandbox dir)
cd $(mktemp -d) && uv run ktrdr sandbox shell 2>&1
```

---

**Success Criteria:**
- [ ] Sandbox environment detected (.env.sandbox exists and readable)
- [ ] Backend container shell accessible via docker compose exec
- [ ] Container hostname differs from host hostname
- [ ] Container filesystem has /app directory with project files
- [ ] Custom service argument works (can shell into db)
- [ ] Database container is actually PostgreSQL (psql exists)
- [ ] Proper error message when not in sandbox directory
- [ ] Error exit code is non-zero outside sandbox
- [ ] Container environment (HOME, PWD) differs from host

---

**Sanity Checks:**

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Container hostname != host hostname | Must differ | Running on host, not in container |
| /app directory exists | Must exist | Wrong container or not backend |
| psql in db container | Must exist | Wrong service routed |
| Exit code outside sandbox != 0 | Must be non-zero | Error handling not working |

---

**Failure Categorization:**

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| `.env.sandbox` not found | CONFIGURATION | Run `ktrdr sandbox init` or navigate to sandbox directory |
| `docker compose exec` fails | ENVIRONMENT | Check containers running with `ktrdr sandbox status` |
| Same hostname as host | TEST_ISSUE | Docker exec not entering container properly |
| No error outside sandbox | CODE_BUG | Error handling missing in shell command |

---

**Note:** Since `ktrdr sandbox shell` opens an interactive shell (TTY + stdin), we test the underlying mechanism via `docker compose exec -T <service> <command>` which is what the shell command wraps.

---

## Milestone 1 Verification

### Completion Checklist

- [ ] Task 1.1 complete: Shell command implemented
- [ ] Task 1.2 complete: E2E test specification created
- [ ] Unit tests pass: `pytest tests/unit/cli/test_sandbox_shell.py`
- [ ] Quality gates pass: `make quality`
- [ ] E2E test passes (manual verification with running sandbox)
- [ ] Command appears in `ktrdr sandbox --help`
