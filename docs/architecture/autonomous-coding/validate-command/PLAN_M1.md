---
design: docs/architecture/autonomous-coding/validate-command/DESIGN.md
architecture: docs/architecture/autonomous-coding/validate-command/ARCHITECTURE.md
---

# Milestone 1: Validate Command

**Branch:** `feature/orchestrator-validate-command`
**Estimated Tasks:** 2

---

## Capability

Users can validate milestone plan files before running them, catching structural errors early.

---

## Tasks

### Task 1.1: Create Plan Validator

**File:** `orchestrator/plan_validator.py`
**Type:** CODING

**Description:**
Create a validator that checks milestone plans for required sections and task completeness.

**Implementation Notes:**

```python
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class ValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    task_count: int = 0

def validate_plan(path: Path) -> ValidationResult:
    """Validate a milestone plan file."""
    errors = []
    warnings = []

    # Check file exists
    if not path.exists():
        return ValidationResult(is_valid=False, errors=[f"File not found: {path}"])

    content = path.read_text()

    # Check for task section
    tasks = parse_tasks(content)  # reuse from plan_parser
    if not tasks:
        errors.append("No tasks found in plan")

    # Check each task
    for task in tasks:
        if not task.description:
            errors.append(f"Task {task.id} missing description")
        if not task.acceptance_criteria:
            errors.append(f"Task {task.id} missing acceptance criteria")

    # Check for E2E section
    e2e = parse_e2e_scenario(content)  # reuse from plan_parser
    if not e2e:
        errors.append("No E2E test section found")

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        task_count=len(tasks),
    )
```

**Acceptance Criteria:**

- [ ] Returns ValidationResult with is_valid, errors, warnings
- [ ] Detects missing task section
- [ ] Detects tasks without descriptions
- [ ] Detects tasks without acceptance criteria
- [ ] Detects missing E2E section
- [ ] Unit tests cover all validation rules

---

### Task 1.2: Add Validate CLI Command

**File:** `orchestrator/cli.py`
**Type:** CODING

**Description:**
Add `orchestrator validate <plan.md>` command that runs validation and displays results.

**Implementation Notes:**

```python
@cli.command()
@click.argument("plan_path", type=click.Path(exists=False))
def validate(plan_path: str):
    """Validate a milestone plan file."""
    from orchestrator.plan_validator import validate_plan

    path = Path(plan_path)
    console.print(f"Validating: [cyan]{path}[/cyan]\n")

    result = validate_plan(path)

    # Display results
    if result.task_count > 0:
        console.print(f"[green][OK][/green] Found {result.task_count} tasks")

    for error in result.errors:
        console.print(f"[red][FAIL][/red] {error}")

    for warning in result.warnings:
        console.print(f"[yellow][WARN][/yellow] {warning}")

    console.print()
    if result.is_valid:
        console.print("[bold green]Result: VALID[/bold green]")
        raise SystemExit(0)
    else:
        console.print(f"[bold red]Result: INVALID ({len(result.errors)} errors)[/bold red]")
        raise SystemExit(1)
```

**Acceptance Criteria:**

- [ ] `orchestrator validate <path>` runs validation
- [ ] Shows task count
- [ ] Shows each error with [FAIL] prefix
- [ ] Shows each warning with [WARN] prefix
- [ ] Exits 0 for valid, 1 for invalid
- [ ] Works with relative and absolute paths

---

## E2E Test

```bash
# Create a valid test plan
cat > /tmp/valid_plan.md << 'EOF'
# Test Milestone

## Tasks

### Task 1.1: Do something

**Description:**
A simple task.

**Acceptance Criteria:**
- [ ] It works

---

## E2E Test

```bash
echo "test passes"
```
EOF

# Create an invalid test plan (missing E2E)
cat > /tmp/invalid_plan.md << 'EOF'
# Test Milestone

## Tasks

### Task 1.1: Do something

**Description:**
A simple task.

**Acceptance Criteria:**
- [ ] It works
EOF

# Test valid plan
uv run orchestrator validate /tmp/valid_plan.md
# Expected: exits 0, shows VALID

# Test invalid plan
uv run orchestrator validate /tmp/invalid_plan.md
# Expected: exits 1, shows INVALID, mentions missing E2E
```
