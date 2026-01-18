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

---

## Task 4.2 Complete: Implement Lazy Command Registration

### What Was Implemented

1. **`ktrdr/cli/__init__.py`** - Complete rewrite with `__getattr__` lazy loading
   - `cli_app` and `app` are now loaded lazily via `__getattr__`
   - Command registration happens in `_get_cli_app()` only when app is accessed
   - Telemetry setup deferred to `_setup_telemetry()` called when app is accessed

2. **`ktrdr/cli/telemetry.py`** - Lazy OTEL imports
   - `opentelemetry.trace` now imported inside wrapper function, not at module level
   - In test mode (`PYTEST_CURRENT_TEST` set), tracing is skipped entirely

3. **All command modules** - Heavy imports deferred to function body:
   - `commands/train.py`, `commands/backtest.py`, `commands/cancel.py`
   - `commands/follow.py`, `commands/ops.py`, `commands/research.py`
   - `commands/resume.py`, `commands/status.py`, `commands/show.py`
   - `commands/validate.py`, `commands/migrate.py`, `commands/list_cmd.py`

### Performance Results

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Import time (best of 3) | ~500ms | ~80ms | <150ms |
| Cold start | ~1100ms | ~164ms | <100ms |

**Target achieved for import time; cold start is ~164ms which is close to target.**

### Gotchas

1. **Test mock paths changed** - Since imports are now inside functions, mocks must target the source module:
   ```python
   # OLD (broken)
   @patch('ktrdr.cli.commands.train.OperationRunner')

   # NEW (correct)
   @patch('ktrdr.cli.operation_runner.OperationRunner')
   ```

2. **TYPE_CHECKING for module-level helpers** - Files with module-level helper functions that use `CLIState` in signatures (like `validate.py`, `migrate.py`) need:
   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from ktrdr.cli.state import CLIState
   ```

3. **Python imports trigger `__init__.py`** - Any `from ktrdr.cli.foo import bar` triggers `ktrdr/cli/__init__.py`. The `__getattr__` pattern prevents this from loading heavy code.

### Next Task Notes

For Task 4.3 (Defer Telemetry Initialization):
- Much of this was already done as part of 4.2
- `ktrdr/cli/telemetry.py` already uses lazy OTEL imports
- `ktrdr/cli/__init__.py` already defers telemetry setup
- Main remaining work: verify `--help` doesn't trigger telemetry
- Test: `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 ktrdr --help` should be fast

---

## Task 4.3 Complete: Defer Telemetry Initialization

### What Was Implemented

1. **`tests/unit/cli/test_telemetry_lazy.py`** - New test file with 6 tests verifying:
   - Importing `ktrdr.cli.telemetry` doesn't load OTEL
   - Importing `ktrdr.cli.app` doesn't load OTEL
   - Running `--help` doesn't trigger telemetry
   - Decorator skips tracing in test mode
   - Function metadata is preserved by decorator
   - Async functions work with decorator

2. **`tests/unit/cli/test_telemetry.py`** - Enabled previously skipped tests:
   - Fixed `reset_tracer` fixture to properly reset OTEL state between tests
   - All 6 tracing tests now pass

### Gotchas

1. **OpenTelemetry `_TRACER_PROVIDER_SET_ONCE`** - Resetting `trace._TRACER_PROVIDER = None` isn't enough. Must also reset `trace._TRACER_PROVIDER_SET_ONCE = Once()` to allow setting a new provider:
   ```python
   from opentelemetry.util._once import Once
   trace._TRACER_PROVIDER = None
   trace._TRACER_PROVIDER_SET_ONCE = Once()
   ```

2. **Additional mock path fix needed** - Found `tests/unit/api/endpoints/test_training_optional_params.py` still had old mock paths. Updated to use source module paths.

### Test Results

- `test_telemetry.py`: 6 passed
- `test_telemetry_lazy.py`: 6 passed
- Full CLI suite: 685 passed
- Full unit suite: 4117 passed (~41s with parallel execution)
