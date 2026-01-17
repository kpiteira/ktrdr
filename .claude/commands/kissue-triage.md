# Issue Triage Command

Evaluates GitHub issues and populates the project backlog with prioritized, well-scoped issues ready for implementation.

This command persists research to GitHub so it's not repeated across sessions.

---

## Command Usage

```
/kissue-triage [issue-number]
```

**Without argument:** Triage all untriaged issues in the project
**With argument:** Triage a specific issue

---

## GitHub Project

Project: **ktrdr issues** (Project #2)
URL: https://github.com/users/kpiteira/projects/2

**Fields:**
- **Status**: Todo, In Progress, Done (default GitHub field)
- **Priority**: P1 (critical), P2 (important), P3 (nice-to-have)
- **Size**: S (< 1 hour), M (1-4 hours), L (> 4 hours)
- **Subsystems**: Affected areas (training, backtest, CLI, data, workers, observability)
- **E2E Tests**: Suggested E2E tests to validate the fix
- **Triaged**: Date when evaluation was completed

---

## Workflow

### Step 1: Fetch Issues to Triage

```bash
# Get all items in the project
gh project item-list 2 --owner kpiteira --format json

# For each item, check if Triaged field is set
# If not set, the issue needs triage
```

If a specific issue number was provided, fetch just that issue:

```bash
gh issue view <number> --json title,body,labels,state
```

### Step 2: Evaluate Each Issue

For each untriaged issue, assess:

#### A. Well-Scoped Check

An issue is **well-scoped** if it has:

1. **Clear acceptance criteria** or definition of done
2. **Contained scope** (not "redesign everything")
3. **Verification method** (tests to run, behavior to check)

If an issue lacks these, mark it as **needs-design**:
- Set Priority to P3
- Add to Subsystems: "needs-design"
- Set Triaged date
- Skip further evaluation

#### B. Priority Assessment

| Priority | Criteria |
|----------|----------|
| **P1** | Blocking functionality, data loss risk, security issue |
| **P2** | Important improvement, notable UX issue, tech debt causing friction |
| **P3** | Nice-to-have, minor improvement, low-impact cleanup |

#### C. Size Estimation

| Size | Criteria |
|------|----------|
| **S** | < 1 hour: Single file, clear fix, minimal testing |
| **M** | 1-4 hours: Multiple files, moderate testing, some investigation |
| **L** | > 4 hours: Significant changes, extensive testing, design decisions |

#### D. Subsystems Identification

Identify which subsystems are affected:
- **training**: Model training, neural networks, training workers
- **backtest**: Backtesting engine, performance metrics
- **CLI**: Command-line interface, output formatting
- **data**: Data loading, IB integration, caching
- **workers**: Worker infrastructure, operation dispatch
- **observability**: Telemetry, logging, Jaeger, Grafana
- **api**: Backend API endpoints, services
- **config**: Configuration, strategy files

#### E. E2E Test Selection

Determine which E2E tests would validate the fix:

1. Use the **e2e-test-designer** agent to search the catalog (if available)
2. Match subsystems to test categories:
   - training → `training/smoke`, `training/resume`
   - backtest → `backtest/smoke`, `backtest/full`
   - data → `data/load`, `data/cache`
3. If no existing test applies, note "None required" or "New test needed"
4. If e2e-test-designer is unavailable, manually check `.claude/skills/e2e-testing/` for test catalog

### Step 3: Update GitHub Project

For each evaluated issue, update the project fields.

**First, get field IDs and option IDs:**

```bash
# Get all field definitions including option IDs
gh project field-list 2 --owner kpiteira --format json | jq '.fields[] | select(.name == "Priority" or .name == "Size" or .name == "Subsystems" or .name == "E2E Tests" or .name == "Triaged") | {name, id, options}'
```

**Then update each field:**

```bash
# Get the item ID for the issue
ITEM_ID=$(gh project item-list 2 --owner kpiteira --format json | jq -r '.items[] | select(.content.number == <issue-number>) | .id')

# Get the project ID
PROJECT_ID=$(gh project list --owner kpiteira --format json | jq -r '.projects[] | select(.number == 2) | .id')

# Update single-select fields (Priority, Size) using option IDs from field-list output
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID --field-id <priority-field-id> --single-select-option-id <P1|P2|P3-option-id>
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID --field-id <size-field-id> --single-select-option-id <S|M|L-option-id>

# Update text fields
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID --field-id <subsystems-field-id> --text "training, CLI"
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID --field-id <e2e-field-id> --text "training/smoke"

# Update date field
gh project item-edit --project-id $PROJECT_ID --id $ITEM_ID --field-id <triaged-field-id> --date $(date +%Y-%m-%d)
```

**Note:** Field IDs and option IDs are project-specific. Use `gh project field-list` to discover them for your project.

### Step 4: Report Results

Output a summary table:

```markdown
## Triage Complete

| # | Title | Priority | Size | Subsystems | E2E Tests | Status |
|---|-------|----------|------|------------|-----------|--------|
| 136 | Workers clear cache... | P2 | S | workers | None | Ready |
| 137 | Orphan detector race | P2 | M | workers | training/smoke | Ready |
| 107 | Cancellation timeout | P3 | L | workers | - | Needs design |

**Summary:**
- 3 issues triaged
- 2 ready for implementation
- 1 needs design work (use /kdesign)

**Recommended next issue:** #136 (P2, Size S, clear scope)
```

---

## Field IDs Reference

To get current field IDs:

```bash
gh project field-list 2 --owner kpiteira --format json | jq '.fields[] | {name, id}'
```

---

## Re-Triage

If an issue has been updated since triage, you can re-triage:

```
/kissue-triage 136
```

This will re-evaluate and update the fields, refreshing the Triaged date.

---

## Integration with kissue

After triage, issues marked as ready can be implemented with:

```
/kissue 136
```

The `kissue` command checks that the issue has been triaged (Triaged field is set) before proceeding with implementation.
