# Issue Implementation Command

Implements well-scoped GitHub issues using TDD methodology.

This command is for issues that have been triaged and marked ready. For untriaged issues, run `/kissue-triage` first.

---

## Command Usage

```
/kissue <issue-number>
/kissue              # (no argument - show ready issues and pick one)
```

---

## Prerequisites

Before using this command, the issue should be:

1. **In the GitHub Project** (ktrdr issues, Project #2)
2. **Triaged** (Triaged field has a date)
3. **Not marked "needs-design"** in Subsystems

If the issue hasn't been triaged, run `/kissue-triage <number>` first.

---

## Workflow Overview

```
1. Validate    → Check issue is triaged and ready
2. Setup       → Create branch, classify task type
3. Research    → Read issue, find affected code
4. Implement   → TDD cycle (RED → GREEN → REFACTOR)
5. Verify      → Unit tests, quality, E2E tests
6. Complete    → Create PR with "Closes #N"
```

---

## 1. Validate Issue

### Fetch Issue and Project Data

```bash
# Get issue details
gh issue view <number> --json title,body,labels,state

# Get project item data (for triage fields)
gh project item-list 2 --owner kpiteira --format json | jq '.items[] | select(.content.number == <number>)'
```

### Validation Checks

1. **Is triaged?** Check that Triaged field has a date
   - If not: "Issue #N hasn't been triaged. Run `/kissue-triage N` first."

2. **Needs design?** Check if Subsystems contains "needs-design"
   - If yes: "Issue #N needs design work. Use `/kdesign` instead."

3. **Already in progress?** Check Status field
   - If "In Progress": "Issue #N is already in progress. Continue or reset?"

4. **Is closed?** Check issue state
   - If closed: "Issue #N is already closed."

### Display Issue Summary

Show the issue details:

```markdown
## Issue #N: [Title]

**Priority:** P2 | **Size:** M | **Subsystems:** training, CLI
**E2E Tests:** training/smoke

**Description:**
[Issue body]

**Acceptance Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2
```

---

## 2. Setup

### Create Branch

```bash
# Create branch from issue number and title
git checkout -b issue-<number>-<slug>

# Example: issue-136-workers-clear-cache
```

### Update Project Status

Move the issue to "In Progress":

```bash
gh project item-edit --project-id PVT_kwHOABLkcs4BMzRq --id $ITEM_ID --field-id <status-field-id> --single-select-option-id <in-progress-id>
```

### Classify Task Type

Based on the issue content:

- **CODING**: Implementation work (most issues). TDD is required.
- **RESEARCH**: Investigation, analysis. No TDD.
- **MIXED**: Research first, then TDD for implementation.

State the classification explicitly.

---

## 3. Research Phase

Before writing any code:

1. **Read the issue thoroughly** — Understand what's being asked
2. **Find relevant code** — Locate files mentioned or implied
3. **Identify patterns** — Find similar code for style/conventions
4. **Check for related issues** — Any context from linked issues?
5. **Review triage notes** — Subsystems and E2E tests identified

**Output:** Brief summary (2-4 sentences) covering:
- What the issue is asking for
- Which files will be affected
- Implementation approach

Do not write implementation code during this phase.

---

## 4. Implementation

**Read the shared execution core:** [_execution-core.md](_execution-core.md)

Follow the TDD cycle from the execution core:

### RED: Write Failing Tests

1. Create test files following project conventions
2. Write tests covering acceptance criteria
3. Run `make test-unit` — verify tests fail meaningfully

### GREEN: Minimal Implementation

1. Write just enough code to pass tests
2. Follow existing patterns
3. Run tests frequently

### REFACTOR: Improve Quality

1. Improve clarity
2. Run `make test-unit` + `make quality`

---

## 5. Verification

### Unit & Quality Checks

```bash
make test-unit
make quality
```

Both must pass.

### E2E Test Verification

Check the E2E Tests field from triage. If tests are specified:

1. Use **e2e-tester** agent to run the specified tests
2. All must pass before PR creation

If no E2E tests specified during triage, assess whether the change warrants E2E testing:
- Changes to training/backtest workflows → Run relevant E2E
- Pure refactoring or test changes → Skip E2E

### Acceptance Criteria

Go through each criterion from the issue:

```markdown
- [x] Criterion 1 — VALIDATED
- [x] Criterion 2 — VALIDATED
```

All criteria must be met.

---

## 6. Completion

### Create PR

```bash
gh pr create --title "Fix: [Issue title]" --body "$(cat <<'EOF'
## Summary

[Brief description of the fix]

## Changes

- [List of changes]

## Testing

- Unit tests: [count] added/modified
- E2E tests: [tests run]

## Acceptance Criteria

- [x] Criterion 1
- [x] Criterion 2

Closes #<issue-number>
EOF
)"
```

The `Closes #N` will automatically:
- Link the PR to the issue
- Close the issue when PR is merged
- Move the project item to "Done" (if automation is configured)

### Task Summary

Output the completion summary (format from [_execution-core.md](_execution-core.md)):

```markdown
## Issue Complete: #N

**What was implemented:**
- [Description]

**Files changed:**
- [List]

**Key decisions:**
- [Any non-obvious choices]

**Tests:**
- Unit: X tests added
- E2E: training/smoke passed

**PR:** https://github.com/kpiteira/ktrdr/pull/XXX
```

---

## No Argument Mode

When called without an issue number:

```
/kissue
```

1. Fetch all items from the project with Status = "Todo" and Triaged date set
2. Exclude items with "needs-design" in Subsystems
3. Sort by Priority (P1 first), then Size (S first)
4. Display the top 5:

```markdown
## Ready Issues

| # | Title | Priority | Size | Subsystems |
|---|-------|----------|------|------------|
| 136 | Workers clear cache | P2 | S | workers |
| 204 | CLI result display | P2 | S | CLI |
| 137 | Orphan detector race | P2 | M | workers |

Which issue would you like to implement?
```

5. Wait for user to specify an issue number

---

## Error Handling

If blocked during implementation:

- Do not create a PR
- Document the blocker
- Keep Status as "In Progress"
- Ask for guidance

---

## Quick Reference

| Phase | Key Actions | Output |
|-------|-------------|--------|
| Validate | Check triaged, not needs-design | Issue summary displayed |
| Setup | Create branch, update status | Branch created |
| Research | Read issue, find code | 2-4 sentence summary |
| RED | Write tests, verify fail | "Tests failing as expected" |
| GREEN | Implement, pass tests | "All tests passing" |
| REFACTOR | Clean up, quality | "Quality checks passing" |
| E2E | Run specified tests | "E2E tests passed" |
| Complete | Create PR | PR link |
