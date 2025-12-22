# Architecture: Validate Command

## Components

```
orchestrator/
├── cli.py              # Add validate command
├── plan_validator.py   # NEW: Validation logic
└── plan_parser.py      # Existing parser (reuse)
```

## Data Flow

```
CLI (validate command)
    │
    ▼
PlanValidator.validate(path)
    │
    ├── Read file
    ├── Parse structure (reuse plan_parser)
    ├── Check required sections
    ├── Check task completeness
    │
    ▼
ValidationResult
    ├── is_valid: bool
    ├── errors: list[str]
    └── warnings: list[str]
```

## Key Decisions

1. **Reuse plan_parser** — Don't duplicate parsing logic
2. **Return structured result** — Not just bool, but detailed errors
3. **Warnings vs Errors** — Missing E2E is error, missing description is warning
4. **Exit code** — Return 0 for valid, 1 for invalid (CLI scripting friendly)
