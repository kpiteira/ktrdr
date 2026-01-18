---
design: docs/architecture/autonomous-coding/DESIGN.md
architecture: docs/architecture/autonomous-coding/ARCHITECTURE.md
---

# Milestone 5: E2E Integration + Dashboard

**Branch:** `feature/orchestrator-m5-e2e`
**Builds on:** M4 (escalation works)
**Estimated Tasks:** 9

---

## Capability

Orchestrator runs E2E tests after milestone tasks complete. Claude interprets test scenarios, executes them, diagnoses failures, and proposes fixes. Full Grafana dashboard for observability.

---

## E2E Test Scenario

```bash
# Scenario A: E2E passes on first try
uv run orchestrator run orchestrator/test_plans/e2e_will_pass.md

# Expected:
# [timestamp] Starting milestone: E2E Will Pass
# [timestamp] Task 1.1: Create calculator... COMPLETED
# [timestamp] Task 1.2: Add tests... COMPLETED
# [timestamp] All tasks complete. Running E2E tests...
# [timestamp] Invoking Claude Code for E2E verification...
# [timestamp] E2E: PASSED (45s)
# [timestamp] Milestone COMPLETE
#
# Summary:
#   Tasks: 2/2 completed
#   E2E: PASSED
#   Duration: 2m 15s
#   Cost: $0.05

# ---

# Scenario B: E2E fails, Claude fixes it
uv run orchestrator run orchestrator/test_plans/e2e_will_fail_fixable.md

# Expected:
# [timestamp] Task 1.1: Create endpoint... COMPLETED
# [timestamp] Task 1.2: Add route... COMPLETED
# [timestamp] Running E2E tests...
# [timestamp] E2E: FAILED
#
# Claude's diagnosis:
#   "The endpoint returns 404 because the route wasn't registered.
#
#    ROOT_CAUSE: Missing router.include_router() in main.py
#    FIXABLE: yes
#    FIX_PLAN: Add 'app.include_router(new_router)' to main.py line 45"
#
# Apply fix? [Y/n]: y
#
# [timestamp] Applying fix...
# [timestamp] Re-running E2E...
# [timestamp] E2E: PASSED
# [timestamp] Milestone COMPLETE (with 1 fix applied)

# ---

# Scenario C: E2E fails, not fixable
uv run orchestrator run orchestrator/test_plans/e2e_needs_human.md

# Expected:
# [timestamp] E2E: FAILED
#
# Claude's diagnosis:
#   "The test expects an external API to return data, but the API
#    is returning 503. This appears to be an external service issue.
#
#    FIXABLE: no
#    OPTIONS:
#    A) Mock the external API for testing
#    B) Skip this test temporarily
#    C) Wait for external service to recover
#
#    RECOMMENDATION: A"
#
# [timestamp] NEEDS HUMAN INPUT for E2E failure
# Your response: A

# ---

# Verify Grafana dashboard
open http://localhost:3000/d/orchestrator

# Expected panels:
# - Cost over time (by milestone)
# - Task success rate
# - Escalation frequency
# - Task duration P95
# - E2E pass rate
# - Loop detection events
```

---

## Tasks

### Task 5.1: Create E2E Runner

**File:** `orchestrator/e2e_runner.py`
**Type:** CODING

**Description:**
Execute E2E tests via Claude Code and parse results.

**Implementation Notes:**

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class E2EResult:
    status: Literal["passed", "failed", "unclear"]
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    diagnosis: str | None = None
    fix_suggestion: str | None = None
    is_fixable: bool = False
    raw_output: str = ""

async def run_e2e_tests(
    milestone_id: str,
    e2e_scenario: str,
    sandbox: CodingAgentContainer,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
) -> E2EResult:
    """Execute E2E tests via Claude Code."""

    prompt = f"""
Execute the following E2E test scenario for milestone {milestone_id}.
Run each command, observe results, and determine if the test passes.

{e2e_scenario}

After executing, report:
- E2E_STATUS: passed | failed
- If failed: DIAGNOSIS: <root cause analysis>
- If failed: FIXABLE: yes | no
- If fixable: FIX_PLAN: <specific changes to make>
- If not fixable: OPTIONS: <options> RECOMMENDATION: <recommendation>
"""

    with tracer.start_as_current_span("orchestrator.e2e_test") as span:
        span.set_attribute("milestone.id", milestone_id)

        start_time = time.time()
        claude_result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=30,  # E2E tests may need fewer turns
            timeout=config.task_timeout_seconds,
        )
        duration = time.time() - start_time

        # Parse result
        output = claude_result.result
        status = _parse_e2e_status(output)
        diagnosis = _extract_diagnosis(output) if status == "failed" else None
        is_fixable = "FIXABLE: yes" in output
        fix_suggestion = _extract_fix_plan(output) if is_fixable else None

        span.set_attribute("e2e.status", status)
        span.set_attribute("e2e.is_fixable", is_fixable)

        e2e_tests_counter.add(1, {"milestone": milestone_id, "status": status})

        return E2EResult(
            status=status,
            duration_seconds=duration,
            tokens_used=estimate_tokens(claude_result),
            cost_usd=claude_result.total_cost_usd,
            diagnosis=diagnosis,
            fix_suggestion=fix_suggestion,
            is_fixable=is_fixable,
            raw_output=output,
        )

def _parse_e2e_status(output: str) -> Literal["passed", "failed", "unclear"]:
    if "E2E_STATUS: passed" in output:
        return "passed"
    if "E2E_STATUS: failed" in output:
        return "failed"
    # Heuristics
    if "all tests pass" in output.lower() or "✓" in output:
        return "passed"
    if "test failed" in output.lower() or "error" in output.lower():
        return "failed"
    return "unclear"
```

**Acceptance Criteria:**

- [ ] Executes E2E scenario via Claude
- [ ] Parses passed/failed status
- [ ] Extracts diagnosis for failures
- [ ] Detects if fixable
- [ ] Extracts fix plan
- [ ] Records trace and metrics

---

### Task 5.2: Create E2E Fix Handler

**File:** `orchestrator/e2e_runner.py`
**Type:** CODING

**Description:**
Apply fixes suggested by Claude and re-run E2E.

**Implementation Notes:**

```python
async def apply_e2e_fix(
    fix_plan: str,
    sandbox: CodingAgentContainer,
    config: OrchestratorConfig,
    tracer: trace.Tracer,
) -> bool:
    """Apply a fix suggested by Claude."""

    prompt = f"""
Apply the following fix:

{fix_plan}

Make the specific changes described. Do not make additional changes.
Report when complete:
- FIX_APPLIED: yes | no
- If no: REASON: <why it couldn't be applied>
"""

    with tracer.start_as_current_span("orchestrator.e2e_fix") as span:
        span.set_attribute("fix.plan", fix_plan[:200])

        result = await sandbox.invoke_claude(
            prompt=prompt,
            max_turns=20,
            timeout=300,
        )

        success = "FIX_APPLIED: yes" in result.result
        span.set_attribute("fix.success", success)

        e2e_fix_counter.add(1, {"success": str(success).lower()})

        return success
```

**Acceptance Criteria:**

- [ ] Applies fix via Claude
- [ ] Reports success/failure
- [ ] Records fix attempt in trace
- [ ] Updates metrics

---

### Task 5.3: Parse E2E Scenarios from Plan

**File:** `orchestrator/plan_parser.py`
**Type:** CODING

**Description:**
Extract E2E test scenarios from milestone markdown.

**Implementation Notes:**

```python
def parse_e2e_scenario(plan_content: str) -> str | None:
    """Extract E2E test scenario from plan."""

    # Look for ## E2E Test section
    match = re.search(
        r"##\s*E2E\s*Test.*?\n(```.*?```)",
        plan_content,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        # Extract content inside code block
        code_block = match.group(1)
        # Remove ``` markers
        scenario = re.sub(r"```\w*\n?", "", code_block)
        return scenario.strip()

    # Alternative: look for E2E section without code block
    match = re.search(
        r"##\s*E2E\s*Test.*?\n(.+?)(?=\n##|\Z)",
        plan_content,
        re.DOTALL | re.IGNORECASE
    )

    if match:
        return match.group(1).strip()

    return None
```

**Acceptance Criteria:**

- [ ] Extracts E2E from code blocks
- [ ] Extracts E2E from plain text
- [ ] Returns None if no E2E section
- [ ] Unit tests for various formats

---

### Task 5.4: Integrate E2E into Milestone Runner

**File:** `orchestrator/milestone_runner.py`
**Type:** CODING

**Description:**
Run E2E after tasks complete, handle fix cycle.

**Implementation Notes:**

```python
async def run_milestone(plan_path: str, ...) -> MilestoneResult:
    # ... existing task loop ...

    # All tasks complete - run E2E
    e2e_scenario = parse_e2e_scenario(plan_content)

    if e2e_scenario:
        console.print("\n[bold]Running E2E tests...[/bold]")

        while True:
            e2e_result = await run_e2e_tests(
                milestone_id, e2e_scenario, sandbox, config, tracer
            )

            if e2e_result.status == "passed":
                console.print(f"E2E: [bold green]PASSED[/bold] ({e2e_result.duration_seconds:.0f}s)")
                state.e2e_status = "passed"
                break

            elif e2e_result.status == "failed":
                console.print(f"E2E: [bold red]FAILED[/bold]")

                # Check loop detection
                loop_detector.record_e2e_failure(e2e_result.diagnosis or "Unknown")
                should_stop, reason = loop_detector.should_stop_e2e()

                if should_stop:
                    console.print(f"[bold red]LOOP DETECTED:[/bold] {reason}")
                    state.e2e_status = "failed"
                    return MilestoneResult(status="e2e_failed", state=state)

                # Show diagnosis
                if e2e_result.diagnosis:
                    console.print(Panel(
                        e2e_result.diagnosis,
                        title="Claude's Diagnosis",
                        border_style="red",
                    ))

                if e2e_result.is_fixable:
                    # Prompt for fix
                    apply = Prompt.ask("Apply fix?", choices=["y", "n"], default="y")

                    if apply == "y":
                        console.print("Applying fix...")
                        success = await apply_e2e_fix(
                            e2e_result.fix_suggestion, sandbox, config, tracer
                        )

                        if success:
                            console.print("Fix applied. Re-running E2E...")
                            continue  # Re-run E2E
                        else:
                            console.print("[red]Fix could not be applied[/red]")

                # Not fixable or fix declined - escalate
                info = EscalationInfo(
                    task_id="e2e",
                    question=e2e_result.diagnosis or "E2E test failed",
                    options=_extract_options(e2e_result.raw_output),
                    recommendation=_extract_recommendation(e2e_result.raw_output),
                    raw_output=e2e_result.raw_output,
                )
                response = await escalate_and_wait(info, tracer, notify)

                # Apply human guidance as fix
                # ... continue loop

            else:  # unclear
                console.print(f"E2E: [bold yellow]UNCLEAR[/bold]")
                # Escalate for human interpretation
                # ...

    return MilestoneResult(status="completed", state=state)
```

**Acceptance Criteria:**

- [ ] Runs E2E after tasks complete
- [ ] Handles passed/failed/unclear
- [ ] Fix cycle with user confirmation
- [ ] Loop detection for E2E
- [ ] Escalation for unfixable failures
- [ ] State tracks E2E status

---

### Task 5.5: Add E2E Metrics

**File:** `orchestrator/telemetry.py`
**Type:** CODING

**Description:**
Add metrics for E2E tests and fixes.

**Implementation Notes:**

```python
e2e_tests_counter: metrics.Counter
e2e_fix_counter: metrics.Counter

def create_metrics(meter: metrics.Meter):
    global e2e_tests_counter, e2e_fix_counter
    # ... existing ...

    e2e_tests_counter = meter.create_counter(
        "orchestrator_e2e_tests_total",
        description="Total E2E tests run",
    )

    e2e_fix_counter = meter.create_counter(
        "orchestrator_e2e_fix_attempts_total",
        description="Total E2E fix attempts",
    )
```

**Acceptance Criteria:**

- [ ] E2E test counter with status label
- [ ] Fix attempt counter with success label
- [ ] Queryable in Prometheus

---

### Task 5.6: Create E2E Test Plans

**Files:**

- `orchestrator/test_plans/e2e_will_pass.md`
- `orchestrator/test_plans/e2e_will_fail_fixable.md`

**Type:** CODING

**Description:**
Test plans with E2E scenarios for validation.

**e2e_will_pass.md:**

```markdown
# Test Milestone: E2E Will Pass

## Task 1.1: Create calculator module

**File:** `calculator.py`

**Description:**
Create a simple calculator with add, subtract functions.

**Acceptance Criteria:**
- [ ] add(a, b) returns a + b
- [ ] subtract(a, b) returns a - b

---

## Task 1.2: Create calculator tests

**File:** `test_calculator.py`

**Description:**
Create pytest tests for calculator.

**Acceptance Criteria:**
- [ ] Tests for add function
- [ ] Tests for subtract function

---

## E2E Test

```bash
# Run calculator tests
cd /workspace
python -m pytest test_calculator.py -v

# Expected: All tests pass
```

```

**e2e_will_fail_fixable.md:**
```markdown
# Test Milestone: E2E Will Fail (Fixable)

## Task 1.1: Create greeting module

**File:** `greeting.py`

**Description:**
Create a greeting function that returns "Hello, {name}!"

NOTE: Intentionally create with a bug (missing comma in f-string)
to test the fix flow.

**Implementation Notes:**
When implementing, "accidentally" write:
`return f"Hello {name}!"` instead of `return f"Hello, {name}!"`

**Acceptance Criteria:**
- [ ] greet(name) returns greeting string

---

## E2E Test

```bash
# Test greeting
cd /workspace
python -c "from greeting import greet; assert greet('World') == 'Hello, World!'"

# Expected: Should fail initially due to missing comma
# Claude should diagnose and fix
```

```

**Acceptance Criteria:**
- [ ] e2e_will_pass.md has passing E2E
- [ ] e2e_will_fail_fixable.md has failing but fixable E2E
- [ ] Both are parseable by plan_parser

---

### Task 5.7: Create Grafana Dashboard

**File:** `deploy/shared/grafana/dashboards/orchestrator.json`
**Type:** CODING

**Description:**
Full Grafana dashboard for orchestrator observability.

**Panels:**
1. **Cost Over Time** — `sum(increase(orchestrator_cost_usd_total[1d])) by (milestone)`
2. **Task Success Rate** — `sum(rate(orchestrator_tasks_total{status="completed"}[1h])) / sum(rate(orchestrator_tasks_total[1h]))`
3. **Escalation Frequency** — `sum(orchestrator_escalations_total) by (milestone)`
4. **Task Duration P95** — `histogram_quantile(0.95, rate(orchestrator_task_duration_seconds_bucket[1h]))`
5. **E2E Pass Rate** — `sum(orchestrator_e2e_tests_total{status="passed"}) / sum(orchestrator_e2e_tests_total)`
6. **Loop Detection Events** — `sum(orchestrator_loops_detected_total) by (type)`
7. **Tokens Used** — `sum(increase(orchestrator_tokens_total[1d])) by (milestone)`
8. **Active Milestones** — Table of recent runs with status

**Implementation Notes:**
- Use existing KTRDR dashboard patterns
- JSON format compatible with Grafana provisioning
- Variables for milestone selection

**Acceptance Criteria:**
- [ ] Dashboard loads in Grafana
- [ ] All panels show data
- [ ] Milestone variable filter works
- [ ] Time range selector works

---

### Task 5.8: Add History Command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator history` command to show past runs.

**Implementation Notes:**
```python
@cli.command()
@click.option("--milestone", "-m", help="Filter by milestone")
@click.option("--limit", "-n", default=10, help="Number of runs to show")
def history(milestone: str | None, limit: int):
    """Show history of milestone runs."""
    config = OrchestratorConfig.from_env()

    # Find all state files
    state_files = list(config.state_dir.glob("*_state.json"))

    # Load and sort by date
    runs = []
    for path in state_files:
        state = OrchestratorState.load(config.state_dir, path.stem.replace("_state", ""))
        if state and (milestone is None or milestone in state.milestone_id):
            runs.append(state)

    runs.sort(key=lambda s: s.started_at, reverse=True)
    runs = runs[:limit]

    # Display table
    table = Table(title="Milestone History")
    table.add_column("Milestone")
    table.add_column("Started")
    table.add_column("Tasks")
    table.add_column("E2E")
    table.add_column("Cost")

    for run in runs:
        total_cost = sum(r.get("cost_usd", 0) for r in run.task_results.values())
        table.add_row(
            run.milestone_id,
            run.started_at.strftime("%Y-%m-%d %H:%M"),
            f"{len(run.completed_tasks)}/{len(run.completed_tasks) + len(run.failed_tasks)}",
            run.e2e_status or "-",
            f"${total_cost:.2f}",
        )

    console.print(table)
```

**Acceptance Criteria:**

- [ ] `orchestrator history` shows past runs
- [ ] --milestone filters by milestone
- [ ] --limit controls number shown
- [ ] Shows tasks completed, E2E status, cost

---

### Task 5.9: Add Costs Command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator costs` command to show cost summary.

**Implementation Notes:**

```python
@cli.command()
@click.option("--since", help="Show costs since date (YYYY-MM-DD)")
@click.option("--by-milestone/--total", default=True)
def costs(since: str | None, by_milestone: bool):
    """Show cost summary."""
    config = OrchestratorConfig.from_env()

    since_date = datetime.fromisoformat(since) if since else datetime.min

    # Aggregate costs from state files
    costs_by_milestone = defaultdict(float)
    total_cost = 0.0

    for path in config.state_dir.glob("*_state.json"):
        state = OrchestratorState.load(config.state_dir, path.stem.replace("_state", ""))
        if state and state.started_at >= since_date:
            cost = sum(r.get("cost_usd", 0) for r in state.task_results.values())
            costs_by_milestone[state.milestone_id] += cost
            total_cost += cost

    if by_milestone:
        table = Table(title="Costs by Milestone")
        table.add_column("Milestone")
        table.add_column("Cost", justify="right")

        for milestone, cost in sorted(costs_by_milestone.items()):
            table.add_row(milestone, f"${cost:.2f}")

        table.add_row("[bold]Total[/bold]", f"[bold]${total_cost:.2f}[/bold]")
        console.print(table)
    else:
        console.print(f"Total cost: ${total_cost:.2f}")
```

**Acceptance Criteria:**

- [ ] `orchestrator costs` shows total cost
- [ ] --since filters by date
- [ ] --by-milestone breaks down by milestone
- [ ] Reads from state files

---

## Milestone Verification

**Test with e2e_will_pass.md:**

```bash
./scripts/sandbox-reset.sh
uv run orchestrator run orchestrator/test_plans/e2e_will_pass.md

# Should complete with E2E: PASSED
```

**Test with e2e_will_fail_fixable.md:**

```bash
./scripts/sandbox-reset.sh
uv run orchestrator run orchestrator/test_plans/e2e_will_fail_fixable.md

# Should:
# 1. Complete tasks
# 2. Fail E2E
# 3. Show diagnosis
# 4. Prompt for fix
# 5. Apply fix
# 6. Pass E2E on retry
```

**Test with real feature:**

```bash
# Run Orchestrator Enhancements feature with E2E
uv run orchestrator run docs/milestones/orchestrator_enhancements_m1.md

# Full flow including E2E
```

**Verify Grafana dashboard:**

```bash
open http://localhost:3000/d/orchestrator

# All panels should show data from test runs
```

**Checklist:**

- [ ] All tasks complete
- [ ] Unit tests pass
- [ ] E2E pass flow works
- [ ] E2E fail + fix flow works
- [ ] E2E escalation works
- [ ] Dashboard loads with data
- [ ] history command works
- [ ] costs command works
- [ ] Quality gates pass
