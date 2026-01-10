# CLI Restructure: Architecture

## High-Level Structure

```
ktrdr/cli/
├── app.py                   # Entry point, global flags, lazy command registration
├── state.py                 # CLIState (json_mode, verbose, api_url)
├── output.py                # Human/JSON output formatting
├── operation_runner.py      # Unified start/follow for all operations
├── api_client.py            # Simplified HTTP client
├── telemetry.py             # Lazy telemetry init (not at import time)
│
├── commands/                # Lazy-loaded command implementations
│   ├── train.py
│   ├── backtest.py
│   ├── research.py          # Reuses existing agent monitoring code
│   ├── validate.py
│   ├── show.py
│   ├── status.py
│   ├── follow.py
│   ├── ops.py
│   ├── cancel.py
│   ├── list_cmd.py
│   └── migrate.py
│
└── subgroups/               # Retained as subcommand groups
    ├── sandbox.py
    ├── ib.py
    └── deploy.py
```

## Key Architectural Decisions

1. **Lazy imports** — Heavy dependencies (pandas, OTEL) imported only when command runs, not at startup
2. **Unified operation runner** — Single code path for train/backtest/research start and follow
3. **Preserve research UX** — The nested progress bar with child operations is reused, not rewritten
4. **Strategy names over paths** — CLI sends names to API; backend resolves to files
5. **Global state via callback** — `--json`, `--verbose` captured in Typer callback, passed to commands

## Backend Dependencies

| Endpoint | Status | Notes |
|----------|--------|-------|
| `GET /strategies/` | Exists | Needs v3 format support |
| `GET /strategies/{name}` | Exists | Needs v3 format support |
| `POST /strategies/validate/{name}` | Exists | Works |
| `POST /training/start` | Exists | Accepts `strategy_name` |
| `POST /backtest/start` | Exists | Needs `strategy_name` param |
| `POST /agent/trigger` | Exists | Works |
| `GET /operations/{id}` | Exists | Works |

## Migration Path

1. Create new `app.py` alongside existing `commands.py`
2. Implement commands one at a time, testing each
3. Documentation audit (find all CLI references)
4. Switch entry point from old to new
5. Remove old code
