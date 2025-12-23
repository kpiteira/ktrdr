---
design: docs/architecture/autonomous-coding/timeout-flag/DESIGN.md
architecture: docs/architecture/autonomous-coding/timeout-flag/ARCHITECTURE.md
---

# Milestone 1: Timeout Flag

**Branch:** `feature/orchestrator-timeout-flag`
**Estimated Tasks:** 2

---

## Capability

Users can override the default task timeout when running milestones.

---

## Tasks

### Task 1.1: Add Timeout Option to CLI

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `--timeout` option to the `run` command that overrides the default task timeout.

**Implementation Notes:**

```python
@cli.command()
@click.argument("plan_path", type=click.Path(exists=True))
@click.option("--timeout", "-t", type=int, default=None,
              help="Task timeout in seconds (60-3600)")
def run(plan_path: str, timeout: int | None):
    """Run a milestone plan."""
    config = OrchestratorConfig.from_env()

    # Override timeout if provided
    if timeout is not None:
        if timeout < 60 or timeout > 3600:
            console.print("[red]Error: timeout must be between 60 and 3600 seconds[/red]")
            raise SystemExit(1)
        config.task_timeout_seconds = timeout
        console.print(f"Using custom timeout: {timeout}s")

    # ... rest of run logic
```

**Acceptance Criteria:**

- [ ] `--timeout` / `-t` option added to run command
- [ ] Validates range (60-3600 seconds)
- [ ] Overrides config.task_timeout_seconds
- [ ] Shows confirmation message when custom timeout used
- [ ] Default behavior unchanged when flag not provided

---

### Task 1.2: Add Timeout Tests

**File:** `orchestrator/tests/test_cli.py`
**Type:** CODING

**Description:**
Add tests for the timeout flag validation and override behavior.

**Acceptance Criteria:**

- [ ] Test timeout below minimum rejected
- [ ] Test timeout above maximum rejected
- [ ] Test valid timeout accepted
- [ ] Test default timeout used when flag omitted

---

## E2E Test

```bash
# Test timeout validation (should fail)
uv run orchestrator run /tmp/valid_plan.md --timeout 30
# Expected: Error message about minimum timeout

uv run orchestrator run /tmp/valid_plan.md --timeout 5000
# Expected: Error message about maximum timeout

# Test valid timeout (should show confirmation)
uv run orchestrator run /tmp/valid_plan.md --timeout 300 --dry-run 2>&1 | head -5
# Expected: Shows "Using custom timeout: 300s"
# Note: --dry-run prevents actual execution (if available), otherwise just verify the message appears
```
