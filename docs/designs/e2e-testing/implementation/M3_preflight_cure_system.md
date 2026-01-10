---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Pre-Flight Cure System

**Goal:** Add symptom→cure mappings to pre-flight checks so the tester agent can auto-recover from known environment issues.

**Branch:** `feature/e2e-framework-m3`

**Builds On:** M2 (Tester Agent Core)

---

## E2E Test Scenario

**Purpose:** Verify tester agent applies cures and recovers from pre-flight failures.

**Duration:** ~2 minutes

**Prerequisites:**
- M2 complete (tester agent works)
- Docker running

**Test Steps:**

```markdown
1. Stop Docker: `docker compose stop backend`
2. Invoke e2e-tester with "Run tests: training/smoke"
3. Tester detects pre-flight failure (backend not responding)
4. Tester applies cure (restart backend)
5. Tester waits 10 seconds
6. Tester retries pre-flight
7. Pre-flight passes
8. Test continues and passes
```

**Success Criteria:**
- [ ] Pre-flight failure detected correctly
- [ ] Cure applied automatically
- [ ] 10s wait observed
- [ ] Retry succeeds
- [ ] Test completes after recovery

---

## Task 3.1: Add Symptom→Cure Mappings to preflight/common.md

**File:** `.claude/skills/e2e-testing/preflight/common.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Update preflight/common.md to include symptom→cure mappings for each check. These are the known environment issues from E2E_CHALLENGES_ANALYSIS.md.

**Changes to make:**

Replace the placeholder cure table with:

```markdown
## Symptom→Cure Mappings

### Docker Not Running

**Symptom:** "Docker containers not all running" or `docker compose ps` shows stopped containers

**Cause:** Docker daemon stopped, containers crashed, or compose not started

**Cure:**
```bash
# Restart Docker compose
docker compose down
docker compose up -d
# Wait for services to stabilize
sleep 15
```

**Max Retries:** 2
**Wait After Cure:** 15 seconds

---

### Backend API Not Responding

**Symptom:** Health check returns non-200 or connection refused

**Cause:** Backend container not ready, crashed, or wrong port

**Cure:**
```bash
# Check if it's a port issue first
[ -f .env.sandbox ] && source .env.sandbox
API_PORT=${API_PORT:-8000}
echo "Using API_PORT=$API_PORT"

# If still failing, restart backend
docker compose restart backend
sleep 10
```

**Max Retries:** 2
**Wait After Cure:** 10 seconds

---

### Wrong Port (Sandbox Issue)

**Symptom:** Connection refused on port 8000 but sandbox is active

**Cause:** .env.sandbox not loaded, using default port instead of sandbox port

**Cure:**
```bash
# Source sandbox config
if [ -f .env.sandbox ]; then
  source .env.sandbox
  echo "Loaded sandbox config: API_PORT=$API_PORT"
else
  echo "No sandbox detected, using default port 8000"
  export API_PORT=8000
fi
```

**Max Retries:** 1 (if this doesn't work, it's a real problem)
**Wait After Cure:** 0 seconds (just config reload)
```

**Implementation Notes:**
- Cures from E2E_CHALLENGES_ANALYSIS.md
- Conservative timeouts (services need time to stabilize)
- Max 2 retries to prevent infinite loops (from VALIDATION.md decision)

**Acceptance Criteria:**
- [ ] All three cures documented
- [ ] Commands are copy-paste ready
- [ ] Max retries and wait times specified
- [ ] Cures match E2E_CHALLENGES_ANALYSIS.md lessons

---

## Task 3.2: Update e2e-tester Agent with Cure Logic

**File:** `.claude/agents/e2e-tester.md`

**Type:** CODING

**Task Categories:** State Machine, Cross-Component

**Description:**
Update the tester agent to apply cures when pre-flight checks fail. Add the cure loop logic with retry limits.

**Changes to add in the Process section:**

```markdown
#### b. Run Pre-Flight Checks

1. Load required pre-flight modules (e.g., `preflight/common.md`)
2. Execute each check
3. **If a check fails:**

   **Cure Loop (max 2 attempts per check):**

   ```
   for attempt in 1, 2:
     1. Look up symptom→cure mapping in preflight module
     2. If cure exists:
        - Log: "Applying cure for [symptom] (attempt {attempt}/2)"
        - Execute cure commands
        - Wait specified time (10-15s)
        - Retry the check
        - If check passes: continue to next check
        - If check fails: continue to next attempt
     3. If no cure exists or max attempts reached:
        - Gather diagnostics
        - Report pre-flight failure with:
          - Which check failed
          - What cures were attempted
          - Current system state
          - Escalate to main agent
   ```

4. If all checks pass: proceed to test execution
```

**Add new section:**

```markdown
## Cure Application

### When to Apply Cures

- Pre-flight check fails AND cure is documented
- Max 2 attempts per check (from VALIDATION.md)
- Wait 10-15s after applying cure (services need time)

### Cure Reporting

Include in report:
```markdown
**Pre-flight:** PASSED (after cure)
**Cures Applied:**
- Docker restart (attempt 1/2) → SUCCESS
```

Or if cures fail:
```markdown
**Pre-flight:** FAILED
**Cures Attempted:**
- Docker restart (attempt 1/2) → FAILED
- Docker restart (attempt 2/2) → FAILED
**Diagnostics:**
- `docker compose ps`: [output]
- `docker compose logs backend --tail 20`: [output]
**Escalation:** Pre-flight failure after 2 cure attempts. Manual intervention needed.
```

### Diagnostic Gathering

When escalating, capture:
1. `docker compose ps` output
2. `docker compose logs backend --tail 20`
3. Current port configuration
4. Any error messages from cure attempts
```

**Acceptance Criteria:**
- [ ] Cure loop logic documented
- [ ] Max 2 attempts enforced
- [ ] Wait times specified
- [ ] Diagnostic gathering on escalation
- [ ] Report format updated for cure attempts

---

## Task 3.3: Create Cure Integration Test

**File:** N/A (verification task)

**Type:** MIXED

**Task Categories:** Cross-Component, Background/Async

**Description:**
Verify the cure system works by intentionally breaking the environment and confirming recovery.

**Test Procedure:**

### Test A: Docker Recovery

1. **Break the environment:**
   ```bash
   docker compose stop backend
   ```

2. **Invoke tester:**
   ```
   Use the e2e-tester agent to run: training/smoke
   ```

3. **Expected behavior:**
   - Tester detects "Backend API not responding"
   - Tester applies cure: `docker compose restart backend`
   - Tester waits 10s
   - Tester retries pre-flight
   - Pre-flight passes
   - Test executes

4. **Verify report includes:**
   - "Cures Applied: Docker restart"
   - Final result (PASSED or FAILED based on test itself)

### Test B: Unrecoverable Failure

1. **Break the environment badly:**
   ```bash
   docker compose down
   # Don't restart
   ```

2. **Invoke tester:**
   ```
   Use the e2e-tester agent to run: training/smoke
   ```

3. **Expected behavior:**
   - Tester detects failure
   - Tester attempts cure twice
   - Cure fails both times
   - Tester gathers diagnostics
   - Tester reports pre-flight failure with escalation

4. **Verify report includes:**
   - "Cures Attempted: 2"
   - "Escalation: Manual intervention needed"
   - Diagnostics captured

**Acceptance Criteria:**
- [ ] Test A: Recovery works after cure
- [ ] Test B: Escalation happens after 2 failed attempts
- [ ] Reports are clear and actionable

---

## Milestone 3 Completion Checklist

### All Tasks Complete
- [ ] Task 3.1: Symptom→cure mappings added to preflight/common.md
- [ ] Task 3.2: e2e-tester agent updated with cure logic
- [ ] Task 3.3: Cure integration test passed

### E2E Verification
- [ ] Stop backend → tester applies cure → test recovers
- [ ] Max 2 attempts enforced
- [ ] 10s wait observed between attempts
- [ ] Unrecoverable failure → proper escalation

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed to feature branch
- [ ] Cures tested and verified working
