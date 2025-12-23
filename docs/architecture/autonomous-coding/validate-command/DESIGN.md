# Design: Validate Command

## Problem

Users want to check if a milestone plan is valid before running it. Currently, errors are only discovered at runtime.

## Solution

Add `orchestrator validate <plan.md>` command that checks:
- Plan file exists and is readable
- Has required sections (Tasks, E2E Test)
- Tasks have required fields (description, acceptance criteria)
- Task IDs are unique and properly formatted

## User Experience

```bash
$ orchestrator validate docs/milestones/my-feature.md
Validating: docs/milestones/my-feature.md

[OK] File readable
[OK] Has task section (3 tasks found)
[OK] All tasks have descriptions
[OK] All tasks have acceptance criteria
[OK] Has E2E test section

Result: VALID

$ orchestrator validate docs/milestones/broken.md
Validating: docs/milestones/broken.md

[OK] File readable
[OK] Has task section (2 tasks found)
[FAIL] Task 1.2 missing acceptance criteria
[FAIL] No E2E test section found

Result: INVALID (2 errors)
```

## Out of Scope

- Auto-fixing invalid plans
- Validating that referenced files exist
- Semantic validation of task content
