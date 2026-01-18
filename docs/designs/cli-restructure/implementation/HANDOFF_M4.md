# M4 Performance Optimization Handoff

## Task 4.1 Complete: Profile Current Import Chain

### Import Profile Results

Profiled using `python -X importtime` on 2026-01-17.

| Module | Cumulative Time (ms) | Import Location |
|--------|---------------------|-----------------|
| `pandas` | ~241 | `ktrdr.cli.data_commands` (module-level) |
| `fastapi.openapi.models` | ~95 | Transitive via `opentelemetry.instrumentation.fastapi` |
| `opentelemetry.instrumentation.fastapi` | ~118 | `ktrdr.monitoring.setup` (CLI doesn't use FastAPI) |
| `opentelemetry.instrumentation.httpx` | ~97 | `ktrdr.cli.__init__` (module-level) |
| `httpx` | ~76 | `ktrdr.cli.client` (module-level) |

**Total CLI import time: ~657ms (cumulative), ~1100ms wall-clock**

### Top Offenders (to make lazy)

1. **`ktrdr.cli.__init__` telemetry setup** - Imports OTEL packages at module level, including `FastAPIInstrumentor` which pulls in all of fastapi (~200ms wasted)
2. **`ktrdr.cli.data_commands`** - Imports pandas at module level (~240ms)
3. **`ktrdr.cli.telemetry`** - Imports `opentelemetry.trace` at module level (~40ms)
4. **`ktrdr.cli.client`** - Imports httpx at module level (~70ms)
5. **`ktrdr.monitoring.setup`** - Imports `FastAPIInstrumentor` unnecessarily for CLI (~100ms)

### Baseline Timing

| Metric | Time (ms) |
|--------|-----------|
| `--help` cold start | ~1100ms |
| `--help` warm start | ~620ms |
| Target | <100ms |

### Import Chain Analysis

The CLI loads via this chain:
```
ktrdr.cli.app
  └── ktrdr.cli.commands.train (and other commands)
        └── ktrdr.cli.operation_runner
              └── ktrdr.cli.client (imports httpx)
        └── ktrdr.cli.telemetry (imports opentelemetry.trace)
  └── ktrdr.cli.__init__ (if imported as ktrdr.cli)
        └── ktrdr.monitoring.setup (imports FastAPI instrumentation)
        └── All command modules (data_commands imports pandas)
```

**Key insight:** The `ktrdr/cli/__init__.py` file eagerly imports ALL command modules and sets up telemetry at import time. This is the root cause.

### Plan for Lazy Loading

**Phase 1: Defer Telemetry (Task 4.3)**
- Move OTEL initialization from `ktrdr/cli/__init__.py` module level to lazy getter
- Create `get_tracer()` function that initializes on first call
- CLI `--help` should NOT trigger telemetry initialization
- Split `ktrdr/monitoring/setup.py` to avoid importing FastAPI for CLI

**Phase 2: Lazy Command Registration (Task 4.2)**
- Keep `ktrdr/cli/app.py` as the fast entry point (already lightweight)
- DO NOT import commands at module level in `ktrdr/cli/__init__.py`
- Use `typer.Typer.add_typer()` with callback patterns for lazy loading
- Defer heavy imports (pandas, operation_runner) to command execution time

**Recommended approach:**
```python
# In command files (e.g., data_commands.py)
def show_data(ctx: typer.Context, ...):
    # Heavy imports inside function, not at module level
    import pandas as pd
    from ktrdr.cli.client import AsyncCLIClient
    ...
```

**Why this works:**
- `typer` and `rich.console` are fast (~100ms combined)
- Deferring pandas alone saves ~240ms
- Deferring OTEL saves ~200ms
- Combined: should achieve <100ms target

### Next Task Notes

For Task 4.2 (Lazy Command Registration):
- Focus on `ktrdr/cli/__init__.py` first - it's the main offender
- The `ktrdr/cli/app.py` entry point is already reasonably fast
- Each command file needs to defer its heavy imports inside the command function
- Test with: `time python -c "from ktrdr.cli.app import app"`
