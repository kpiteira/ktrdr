# Design: Info Command

## Problem

Users want to quickly see metadata about a milestone plan without reading the whole file.

## Solution

Add `orchestrator info <plan.md>` command that displays:
- Milestone name
- Task count
- Whether E2E section exists
- List of files that will be created/modified

## User Experience

```bash
$ orchestrator info docs/milestones/my-feature.md

Milestone: My Feature
Tasks: 3
Has E2E: Yes

Files:
  - src/new_module.py (create)
  - src/existing.py (modify)
  - tests/test_new_module.py (create)
```

## Out of Scope

- Estimated duration
- Dependency analysis between tasks
