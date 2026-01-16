---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Environment Validation

## Goal

Orchestrator validates prerequisites on startup with clear errors. Users see actionable messages when running from wrong context.

## E2E Validation

**Test:** Clear errors when prerequisites missing

```bash
# Test 1: Not in repo root
cd /tmp && uv run python -c "from orchestrator.environment import validate_environment; validate_environment()"
# Expected: OrchestratorError with "Must run from repo root"

# Test 2: No sandbox initialized (in repo without .env.sandbox)
cd ~/some-repo-without-sandbox && uv run python -c "from orchestrator.environment import validate_environment; validate_environment()"
# Expected: OrchestratorError with "Run: ktrdr sandbox init"

# Test 3: Sandbox not running
cd ~/ktrdr--orchestrator-1 && ktrdr sandbox down && uv run python -c "from orchestrator.environment import validate_environment; validate_environment()"
# Expected: OrchestratorError with "Run: ktrdr sandbox up"

# Test 4: Valid context
cd ~/ktrdr--orchestrator-1 && ktrdr sandbox up && uv run python -c "from orchestrator.environment import validate_environment; print(validate_environment())"
# Expected: Returns Path to current directory
```

**Success Criteria:**
- [ ] Each prerequisite failure gives clear, actionable error
- [ ] Valid context returns code folder path
- [ ] Orchestrator CLI refuses to run without valid context

---

## Task 2.1: Create orchestrator/environment.py

**File:** `orchestrator/environment.py` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Create the environment validation module with `validate_environment()` function.

**Implementation:**

```python
"""Environment validation for orchestrator.

Validates that the orchestrator is running in a valid context:
- In a git repository root
- With a CLI sandbox initialized
- With the sandbox running
"""

import subprocess
from pathlib import Path

from orchestrator.errors import OrchestratorError


def validate_environment() -> Path:
    """
    Validate orchestrator is in valid context.

    Returns:
        Path to code folder (current working directory) on success.

    Raises:
        OrchestratorError: With clear message if prerequisites not met.
    """
    cwd = Path.cwd()

    # Check 1: Repo root
    if not (cwd / ".git").exists():
        raise OrchestratorError(
            "Must run from repo root. No .git found.\n"
            "cd to your ktrdr clone first."
        )

    # Check 2: Sandbox initialized
    if not (cwd / ".env.sandbox").exists():
        raise OrchestratorError(
            "No sandbox initialized in this folder.\n"
            "Run: ktrdr sandbox init"
        )

    # Check 3: Sandbox running
    result = subprocess.run(
        ["uv", "run", "ktrdr", "sandbox", "status"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or "running" not in result.stdout.lower():
        raise OrchestratorError(
            "Sandbox not running.\n"
            "Run: ktrdr sandbox up"
        )

    return cwd
```

**Acceptance Criteria:**
- [ ] File created at `orchestrator/environment.py`
- [ ] Three checks implemented with clear error messages
- [ ] Returns `Path` on success
- [ ] Uses `OrchestratorError` (already exists in orchestrator/errors.py or create if needed)

---

## Task 2.2: Create tests for environment validation

**File:** `orchestrator/tests/test_environment.py` (NEW)
**Type:** CODING
**Estimated time:** 30 min

**Description:**
Create unit tests for environment validation. Use mocking to simulate different environments.

**Tests to implement:**

```python
class TestValidateEnvironment:
    """Test validate_environment function."""

    def test_returns_cwd_when_valid(self, tmp_path, monkeypatch):
        """Should return current directory when all checks pass."""
        # Setup: create .git and .env.sandbox
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        # Mock sandbox status check
        with patch("orchestrator.environment.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Status: running")
            result = validate_environment()

        assert result == tmp_path

    def test_raises_when_not_repo_root(self, tmp_path, monkeypatch):
        """Should raise when .git doesn't exist."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OrchestratorError) as exc_info:
            validate_environment()

        assert "repo root" in str(exc_info.value).lower()

    def test_raises_when_sandbox_not_initialized(self, tmp_path, monkeypatch):
        """Should raise when .env.sandbox doesn't exist."""
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        with pytest.raises(OrchestratorError) as exc_info:
            validate_environment()

        assert "sandbox init" in str(exc_info.value).lower()

    def test_raises_when_sandbox_not_running(self, tmp_path, monkeypatch):
        """Should raise when sandbox status check fails."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".env.sandbox").touch()
        monkeypatch.chdir(tmp_path)

        with patch("orchestrator.environment.subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")

            with pytest.raises(OrchestratorError) as exc_info:
                validate_environment()

        assert "sandbox up" in str(exc_info.value).lower()
```

**Acceptance Criteria:**
- [ ] All 4 test cases pass
- [ ] Tests use proper mocking (no real subprocess calls)
- [ ] Tests run fast (<1s total)

---

## Task 2.3: Wire validation into orchestrator startup

**Files:** `orchestrator/cli.py`, `orchestrator/milestone_runner.py`
**Type:** CODING
**Estimated time:** 20 min

**Description:**
Call `validate_environment()` at the start of orchestrator commands. Pass the returned path to `CodingAgentContainer`.

**Changes in cli.py:**

```python
from orchestrator.environment import validate_environment

# In run command (around line 124):
def run(...):
    code_folder = validate_environment()  # Validates and returns path
    container = CodingAgentContainer()
    # ... pass code_folder to container.start() later (M3)
```

**Changes in milestone_runner.py:**

```python
from orchestrator.environment import validate_environment

# In run_milestone (around line 145):
async def run_milestone(...):
    code_folder = validate_environment()
    container = CodingAgentContainer(...)
    # ... pass code_folder to container.start() later (M3)
```

**Acceptance Criteria:**
- [ ] `validate_environment()` called before creating container
- [ ] Orchestrator refuses to proceed if validation fails
- [ ] Error messages displayed to user
- [ ] Existing tests updated to mock `validate_environment`

---

## Milestone 2 Completion Checklist

- [ ] All 3 tasks complete
- [ ] All orchestrator tests pass: `cd orchestrator && uv run pytest tests/ -v`
- [ ] Manual test: running from wrong directory shows clear error
- [ ] Quality gates pass: `make quality`
- [ ] Commit with message: "feat(orchestrator): add environment validation on startup"
