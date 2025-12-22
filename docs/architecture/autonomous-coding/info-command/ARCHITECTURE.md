# Architecture: Info Command

## Components

```
orchestrator/
├── cli.py           # Add info command
├── plan_parser.py   # Reuse existing parser
└── plan_info.py     # NEW: Info extraction
```

## Data Flow

```
CLI (info command)
    │
    ▼
get_plan_info(path)
    │
    ├── Parse plan (reuse plan_parser)
    ├── Extract milestone name
    ├── Count tasks
    ├── Check E2E presence
    ├── Extract file references
    │
    ▼
PlanInfo dataclass
    │
    ▼
Rich table output
```

## Key Decisions

1. **Reuse plan_parser** — Consistent parsing across commands
2. **Rich table output** — Nice formatting for terminal
3. **File extraction** — Parse "File:" lines from task definitions
