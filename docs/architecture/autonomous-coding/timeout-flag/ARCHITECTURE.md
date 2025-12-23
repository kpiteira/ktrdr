# Architecture: Timeout Flag

## Components

```
orchestrator/
├── cli.py      # Add --timeout option
└── config.py   # OrchestratorConfig (existing)
```

## Data Flow

```
CLI (--timeout flag)
    │
    ▼
Override config.task_timeout_seconds
    │
    ▼
Pass to milestone_runner
    │
    ▼
Used in sandbox.invoke_claude(timeout=...)
```

## Key Decisions

1. **Override, not replace** — CLI flag takes precedence over env/config
2. **Seconds, not minutes** — Consistent with existing config
3. **Validation** — Minimum 60s, maximum 3600s (1 hour)
