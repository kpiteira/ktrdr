---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Cleanup

**Branch:** `docs/coding-agent-container-refactor`
**Builds on:** Milestone 3 (Docker Run with Volume Mount)
**E2E Test:** Full orchestrator flow works end-to-end with CLI sandbox

## Goal

Remove dead code, update documentation, verify full orchestrator flow works with CLI sandbox.

---

## Task 4.1: Remove orphaned sandbox references

**File(s):** Various files in `orchestrator/`, `scripts/`, `deploy/`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Cross-Component

**Description:**
Search for and remove any remaining "sandbox" references in the orchestrator context. References to "CLI sandbox" or `ktrdr sandbox` command are correct and should remain. Only remove references to the old "orchestrator sandbox" concept.

**Implementation Notes:**
- Search for `SandboxManager`, `orchestrator.sandbox`, `ktrdr-sandbox`
- Check scripts in `scripts/coding-agent-*.sh`
- Check deploy config in `deploy/environments/coding-agent/` and `deploy/docker/coding-agent/`
- CLI sandbox references (`ktrdr sandbox` commands) should remain intact

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A (search and remove task)

*Integration Tests:*
- [ ] N/A

*Smoke Test:*
```bash
# Should return no matches in orchestrator code
grep -r "SandboxManager\|orchestrator\.sandbox\|ktrdr-sandbox" orchestrator/
# Expected: exit code 1 (no matches)

# Check scripts - should find "ktrdr sandbox" but not "ktrdr-sandbox"
grep -r "ktrdr-sandbox" scripts/coding-agent-*.sh
# Expected: exit code 1 (no matches)
```

**Acceptance Criteria:**
- [ ] No `SandboxManager` or `orchestrator.sandbox` references
- [ ] No `ktrdr-sandbox` container name references
- [ ] CLI sandbox references (`ktrdr sandbox` commands) remain intact

---

## Task 4.2: Update autonomous-coding documentation

**File(s):** `docs/architecture/autonomous-coding/*.md`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Update the autonomous coding architecture docs to reflect the new CodingAgentContainer approach. Update class names, container names, and add notes about CLI sandbox integration.

**Implementation Notes:**
- Check `docs/architecture/autonomous-coding/sandbox-orchestrator-handoff.md`
- Check `docs/architecture/autonomous-coding/PLAN_M1_sandbox.md`
- Update `SandboxManager` → `CodingAgentContainer`
- Update `ktrdr-sandbox` → `ktrdr-coding-agent`
- Update architecture diagrams if any exist
- Add note clarifying CLI sandbox vs CodingAgentContainer terminology

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A (documentation)

*Integration Tests:*
- [ ] N/A

*Smoke Test:*
```bash
# Verify no old references in architecture docs
grep -r "SandboxManager\|ktrdr-sandbox" docs/architecture/autonomous-coding/
# Expected: exit code 1 (no matches)
```

**Acceptance Criteria:**
- [ ] All architecture docs updated
- [ ] Terminology is consistent throughout
- [ ] Diagrams updated if present

---

## Task 4.3: Clean up unused Docker artifacts

**File(s):** `deploy/environments/coding-agent/docker-compose.yml`
**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Configuration

**Description:**
Review docker-compose.yml and remove anything that's no longer used. The file should only be used for building the image. Add clear comments explaining the file's purpose.

**Implementation Notes:**
- Remove any unused volume definitions
- Remove any unused network definitions
- Remove outdated comments
- Remove environment variables that are no longer needed
- Add header comment explaining file is for building only:
  ```yaml
  # KTRDR Coding Agent Container
  #
  # This file is used for BUILDING the image only.
  # The container is started via `docker run` by the orchestrator.
  #
  # Build: docker compose -f deploy/environments/coding-agent/docker-compose.yml build
  ```

**Testing Requirements:**

*Unit Tests:*
- [ ] N/A (Docker config)

*Integration Tests:*
- [ ] Image builds successfully

*Smoke Test:*
```bash
docker compose -f deploy/environments/coding-agent/docker-compose.yml build
# Expected: Build succeeds

docker compose -f deploy/environments/coding-agent/docker-compose.yml config | head -10
# Expected: Shows clear header comments
```

**Acceptance Criteria:**
- [ ] File clearly states it's for building only
- [ ] No unused configuration remains
- [ ] Can still build image successfully

---

## Task 4.4: Add integration test for full flow

**File(s):** `orchestrator/tests/test_integration.py` (NEW or existing)
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Cross-Component

**Description:**
Add an integration test that verifies the full orchestrator flow with mocked Claude responses. Test validates environment, starts container, invokes Claude, and stops container.

**Implementation Notes:**
- Use `pytest.mark.integration` decorator
- Use `tmp_path` fixture and `monkeypatch.chdir()` for isolated test
- Mock `subprocess.run` for sandbox status check
- Mock `CodingAgentContainer.start()`, `stop()`, and `invoke_claude()`
- Verify the complete flow: validate → start → invoke → stop

**Testing Requirements:**

*Unit Tests:*
- [ ] test_full_flow_with_valid_environment
- [ ] Test verifies validate_environment called
- [ ] Test verifies container.start() called with correct path
- [ ] Test verifies container.stop() called in cleanup

*Integration Tests:*
- [ ] N/A (this IS the integration test)

*Smoke Test:*
```bash
cd orchestrator && uv run pytest tests/test_integration.py -v -k "full_flow" -m integration
```

**Acceptance Criteria:**
- [ ] Test verifies full flow (validate → start → invoke → stop)
- [ ] Uses proper mocking (no real subprocess or Docker calls)
- [ ] Marked as integration test (can be skipped in unit test runs)
- [ ] Test runs fast (<1s)

---

## Milestone 4 Verification

### E2E Test Scenario

**Purpose:** Verify full orchestrator flow works with CLI sandbox integration
**Duration:** ~2 minutes
**Prerequisites:** Docker running, coding-agent image built, CLI sandbox running

**Test Steps:**

```bash
# 1. Setup: Ensure sandbox running in test repo
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up

# 2. Verify no orphaned references
grep -r "SandboxManager\|orchestrator\.sandbox\|ktrdr-sandbox" orchestrator/
# Expected: No matches (exit code 1)

# 3. Verify Docker config is clean
docker compose -f deploy/environments/coding-agent/docker-compose.yml config > /dev/null
# Expected: Valid config, no errors

# 4. Run integration tests
cd orchestrator && uv run pytest tests/test_integration.py -v -m integration
# Expected: All tests pass

# 5. Run full orchestrator command (dry-run)
cd ~/ktrdr--orchestrator-1
uv run python -m orchestrator.cli run --milestone test-milestone --dry-run 2>&1 | head -20
# Expected: Orchestrator validates environment and shows it would start container
```

**Success Criteria:**
- [ ] No orphaned "sandbox" references in orchestrator code
- [ ] Docker config is valid and minimal
- [ ] Integration tests pass
- [ ] Full orchestrator flow works end-to-end

### Completion Checklist

- [ ] All 4 tasks complete and committed
- [ ] No orphaned sandbox references: `grep -r "SandboxManager\|orchestrator.sandbox" orchestrator/`
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] Integration test added and passing
- [ ] Documentation updated and consistent
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Commit with message: "chore(orchestrator): cleanup and documentation for coding-agent-container refactor"

---

## Final Verification (Post-M4)

After all milestones complete, run this comprehensive verification:

```bash
# 1. Verify no old references anywhere
grep -r "SandboxManager\|orchestrator\.sandbox\|ktrdr-sandbox" orchestrator/ scripts/ deploy/
# Expected: No matches

# 2. Run all orchestrator tests
cd orchestrator && uv run pytest tests/ -v
# Expected: All pass

# 3. Build image
docker compose -f deploy/environments/coding-agent/docker-compose.yml build
# Expected: Build succeeds

# 4. Manual E2E test
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up
# Run orchestrator command and verify it works
```
