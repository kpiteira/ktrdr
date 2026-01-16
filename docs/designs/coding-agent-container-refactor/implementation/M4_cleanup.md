---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Cleanup

## Goal

Remove dead code, update documentation, verify full orchestrator flow works with CLI sandbox.

## E2E Validation

**Test:** Run simple task through orchestrator, verify it uses CLI sandbox for testing

```bash
# Prerequisites
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up

# Run a simple orchestrator task (or dry-run)
uv run python -m orchestrator.cli run --milestone test-milestone --dry-run

# Verify:
# 1. Orchestrator validates environment
# 2. Container starts with code folder mounted
# 3. Claude can access /workspace/.env.sandbox
# 4. E2E tests (if any) hit the CLI sandbox API
```

**Success Criteria:**
- [ ] Full orchestrator flow works end-to-end
- [ ] No orphaned "sandbox" references in orchestrator code
- [ ] Documentation updated to reflect new architecture
- [ ] No dead docker-compose configuration

---

## Task 4.1: Remove orphaned sandbox references

**Files:** Various
**Type:** CODING
**Estimated time:** 20 min

**Description:**
Search for and remove any remaining "sandbox" references in the orchestrator context.

**Search and verify:**

```bash
# Should return no matches in orchestrator code (except CLI sandbox references which are correct)
grep -r "SandboxManager\|orchestrator.sandbox\|ktrdr-sandbox" orchestrator/

# Check scripts
grep -r "sandbox" scripts/coding-agent-*.sh

# Check deploy config
grep -r "sandbox" deploy/environments/coding-agent/
grep -r "sandbox" deploy/docker/coding-agent/
```

**Note:** References to "CLI sandbox" or `ktrdr sandbox` command are correct and should remain. Only remove references to the old "orchestrator sandbox" concept.

**Acceptance Criteria:**
- [ ] No `SandboxManager` or `orchestrator.sandbox` references
- [ ] No `ktrdr-sandbox` container name references
- [ ] CLI sandbox references (the testing environment) remain intact

---

## Task 4.2: Update autonomous-coding documentation

**Files:** `docs/architecture/autonomous-coding/*.md`
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Update the autonomous coding architecture docs to reflect the new CodingAgentContainer approach.

**Files to check:**
- `docs/architecture/autonomous-coding/sandbox-orchestrator-handoff.md`
- `docs/architecture/autonomous-coding/PLAN_M1_sandbox.md`
- Any other files referencing the sandbox

**Changes:**
- `SandboxManager` → `CodingAgentContainer`
- `ktrdr-sandbox` → `ktrdr-coding-agent`
- Update architecture diagrams if any
- Add note about CLI sandbox integration
- Clarify terminology (CLI sandbox vs CodingAgentContainer)

**Acceptance Criteria:**
- [ ] All architecture docs updated
- [ ] Terminology is consistent
- [ ] Diagrams updated if present

---

## Task 4.3: Clean up unused Docker artifacts

**Files:** `deploy/environments/coding-agent/docker-compose.yml`
**Type:** CODING
**Estimated time:** 15 min

**Description:**
Review docker-compose.yml and remove anything that's no longer used. The file should only be used for building the image.

**Check for:**
- Unused volume definitions
- Unused network definitions
- Outdated comments
- Environment variables that are no longer needed

**Update comments:**

```yaml
# KTRDR Coding Agent Container
#
# This file is used for BUILDING the image only.
# The container is started via `docker run` by the orchestrator.
#
# Build: docker compose -f deploy/environments/coding-agent/docker-compose.yml build
```

**Acceptance Criteria:**
- [ ] File clearly states it's for building only
- [ ] No unused configuration
- [ ] Can still build image successfully

---

## Task 4.4: Add integration test for full flow

**File:** `orchestrator/tests/test_integration.py` (NEW or existing)
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Add an integration test that verifies the full orchestrator flow with mocked Claude responses.

**Test scenario:**

```python
@pytest.mark.integration
class TestOrchestratorIntegration:
    """Integration tests for orchestrator flow."""

    @pytest.mark.asyncio
    async def test_full_flow_with_valid_environment(self, tmp_path, monkeypatch):
        """
        Test complete orchestrator flow:
        1. validate_environment() succeeds
        2. Container starts with code folder
        3. Claude invoked
        4. Container stopped
        """
        # Setup fake environment
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").write_text("KTRDR_API_PORT=8001\n")
        monkeypatch.chdir(tmp_path)

        with patch("orchestrator.environment.subprocess.run") as mock_status:
            mock_status.return_value = Mock(returncode=0, stdout="running")

            with patch.object(CodingAgentContainer, "start") as mock_start:
                with patch.object(CodingAgentContainer, "stop") as mock_stop:
                    with patch.object(CodingAgentContainer, "invoke_claude") as mock_claude:
                        mock_claude.return_value = ClaudeResult(
                            is_error=False,
                            result="Task completed",
                            total_cost_usd=0.01,
                            duration_ms=1000,
                            num_turns=1,
                            session_id="test-session",
                        )

                        # Run orchestrator (simplified)
                        code_folder = validate_environment()
                        container = CodingAgentContainer()
                        await container.start(code_folder)
                        result = await container.invoke_claude("Test prompt")
                        await container.stop()

                        # Verify
                        mock_start.assert_called_once_with(tmp_path)
                        mock_claude.assert_called_once()
                        mock_stop.assert_called_once()
                        assert not result.is_error
```

**Acceptance Criteria:**
- [ ] Test verifies full flow
- [ ] Uses proper mocking
- [ ] Marked as integration test (can be skipped in unit test runs)

---

## Milestone 4 Completion Checklist

- [ ] All 4 tasks complete
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] No orphaned sandbox references: `grep -r "SandboxManager\|orchestrator.sandbox" orchestrator/`
- [ ] Documentation updated and consistent
- [ ] Manual test: full orchestrator flow works
- [ ] Quality gates pass: `make quality`
- [ ] Commit with message: "chore(orchestrator): cleanup and documentation for coding-agent-container refactor"

---

## Final Verification

After all milestones complete:

```bash
# 1. Verify no old references
grep -r "SandboxManager\|orchestrator.sandbox\|ktrdr-sandbox" orchestrator/ scripts/ deploy/

# 2. Run all tests
cd orchestrator && uv run pytest tests/ -v

# 3. Build image
docker compose -f deploy/environments/coding-agent/docker-compose.yml build

# 4. Manual E2E test
cd ~/ktrdr--orchestrator-1
ktrdr sandbox up
# Run orchestrator command and verify it works
```
