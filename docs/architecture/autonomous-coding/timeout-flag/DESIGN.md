# Design: Timeout Flag

## Problem

The default task timeout may not suit all milestones. Some tasks need more time (complex implementations), others should fail faster (simple fixes).

## Solution

Add `--timeout` flag to `orchestrator run` command that overrides the default task timeout.

## User Experience

```bash
# Use default timeout (from config)
orchestrator run plan.md

# Override with 10 minute timeout
orchestrator run plan.md --timeout 600

# Override with 30 minute timeout for complex tasks
orchestrator run plan.md --timeout 1800
```

## Out of Scope

- Per-task timeout overrides in plan files
- Dynamic timeout adjustment based on task complexity
