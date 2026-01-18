---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 4: Performance Optimization

**Goal:** `ktrdr --help` responds in <100ms (currently ~1000ms).

**Branch:** `feature/cli-restructure-m4`

**Builds on:** Milestone 3 (all commands implemented)

---

## Task 4.1: Profile Current Import Chain

**File:** N/A (research task)
**Type:** RESEARCH
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Profile the current import chain to identify which imports are causing the ~1000ms startup time. This informs what needs to be made lazy.

**Implementation Notes:**

Use Python's `-X importtime` flag to profile imports:

```bash
# Profile current CLI
python -X importtime -c "from ktrdr.cli.app import app" 2>&1 | head -50

# Sort by cumulative time
python -X importtime -c "from ktrdr.cli.app import app" 2>&1 | sort -t'|' -k2 -n | tail -20
```

**Expected heavy imports:**
- `pandas` (~200-400ms)
- `opentelemetry` packages (~100-200ms)
- `numpy` (~100ms)
- `torch` (if imported) (~500ms+)
- `rich` (~50ms)

Document findings in this format:

```markdown
## Import Profile Results

| Module | Cumulative Time (ms) | Notes |
|--------|---------------------|-------|
| pandas | 350 | Imported by data_commands |
| opentelemetry.* | 180 | Imported at CLI init |
| numpy | 120 | Transitive via pandas |
| ... | ... | ... |

## Top Offenders (to make lazy)

1. `ktrdr.cli.telemetry` - imports OTEL at module level
2. `ktrdr.cli.data_commands` - imports pandas at module level
3. ...
```

**Testing Requirements:**

*Unit Tests:*
- None (research task)

*Integration Tests:*
- None (research task)

*Smoke Test:*
```bash
# Baseline measurement
time python -c "from ktrdr.cli.app import app"
# Target: <100ms
```

**Acceptance Criteria:**
- [ ] Import profile documented
- [ ] Top 5 heavy imports identified
- [ ] Baseline timing recorded
- [ ] Plan for lazy loading documented

---

## Task 4.2: Implement Lazy Command Registration

**File:** `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** Configuration, Wiring/DI

**Description:**
Refactor command registration to use lazy loading. Commands should only be imported when invoked, not at CLI startup.

**Implementation Notes:**

Typer supports lazy loading via `add_typer` with `lazy=True` or by deferring imports:

```python
import typer

app = typer.Typer(
    name="ktrdr",
    help="KTRDR - Trading analysis and automation tool.",
    add_completion=False,
)

@app.callback()
def main(ctx: typer.Context, ...):
    """Main callback for global flags."""
    ...

# Lazy command registration using callback pattern
def _lazy_train():
    from ktrdr.cli.commands.train import train
    return train

def _lazy_backtest():
    from ktrdr.cli.commands.backtest import backtest
    return backtest

# Register with lazy loading
# Option 1: Custom lazy loader
class LazyGroup(typer.Typer):
    """Typer subclass that loads commands lazily."""

    def __init__(self, *args, lazy_commands: dict = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._lazy_commands = lazy_commands or {}

    def __call__(self, *args, **kwargs):
        # Load lazy commands on first invocation
        for name, loader in self._lazy_commands.items():
            if name not in [c.name for c in self.registered_commands]:
                cmd = loader()
                self.command(name=name)(cmd)
        return super().__call__(*args, **kwargs)

# Option 2: Use typer's native lazy loading (if available in version)
# Check Typer docs for version-specific approach

# Option 3: Import only in command body (simplest)
# Each command file handles its own heavy imports inside the function
```

**Simpler approach — defer heavy imports inside commands:**

```python
# In commands/train.py
def train(ctx: typer.Context, ...):
    """Train command."""
    # Heavy imports happen here, not at module level
    from ktrdr.cli.operation_runner import OperationRunner
    from ktrdr.cli.operation_adapters import TrainingOperationAdapter

    # ... rest of implementation
```

This approach is simpler and sufficient for our needs.

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_app_import_fast()` — verify `from ktrdr.cli.app import app` < 100ms

*Integration Tests:*
- [ ] `test_command_still_works()` — verify commands execute after lazy refactor

*Smoke Test:*
```bash
time python -c "from ktrdr.cli.app import app"
# Should be <100ms
```

**Acceptance Criteria:**
- [ ] App imports in <100ms
- [ ] All commands still work
- [ ] No regression in functionality
- [ ] Unit tests pass

---

## Task 4.3: Defer Telemetry Initialization

**File:** `ktrdr/cli/telemetry.py`, `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration, Background/Async

**Description:**
Move telemetry (OpenTelemetry) initialization from import time to first command execution. The `--help` command should not initialize telemetry.

**Implementation Notes:**

Current problem in `ktrdr/cli/__init__.py` or telemetry:
```python
# BAD: Initializes at import time
from opentelemetry import trace
tracer = trace.get_tracer(__name__)  # This triggers OTEL setup
```

Solution — lazy initialization:
```python
# ktrdr/cli/telemetry.py

_tracer = None
_initialized = False

def get_tracer():
    """Get tracer, initializing on first call."""
    global _tracer, _initialized
    if not _initialized:
        from opentelemetry import trace
        from ktrdr.telemetry import setup_telemetry
        setup_telemetry()  # Only called when needed
        _tracer = trace.get_tracer(__name__)
        _initialized = True
    return _tracer

def trace_cli_command(name: str):
    """Decorator that traces CLI commands (lazy init)."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(f"cli.{name}"):
                return func(*args, **kwargs)
        return wrapper
    return decorator
```

Update commands to use lazy tracer:
```python
# In command files
from ktrdr.cli.telemetry import trace_cli_command

@trace_cli_command("train")
def train(...):
    ...
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_telemetry_not_init_on_import()` — verify OTEL not loaded at import
- [ ] `test_telemetry_init_on_first_use()` — verify lazy init works

*Integration Tests:*
- [ ] `test_help_fast()` — verify `--help` doesn't init telemetry
- [ ] `test_command_has_tracing()` — verify traces generated

*Smoke Test:*
```bash
# Should be fast (no telemetry)
time python -m ktrdr.cli.app --help

# Should init telemetry
python -m ktrdr.cli.app train --help
```

**Acceptance Criteria:**
- [ ] `--help` doesn't initialize telemetry
- [ ] Commands still generate traces when executed
- [ ] Import time reduced significantly
- [ ] Unit tests pass

---

## Milestone 4 Verification

### E2E Test Scenario

**E2E Test Recipe:** [cli/performance](../../../../.claude/skills/e2e-testing/tests/cli/performance.md)

**Purpose:** Prove CLI startup is <100ms.

**Duration:** ~30 seconds (including cache clearing)

**Prerequisites:**
- Clean Python environment
- All commands implemented (M1-M3)

**Test Steps:**

```bash
# 1. Clear bytecode cache for accurate measurement
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null

# 2. Measure cold start --help
time python -m ktrdr.cli.app --help
# Target: real < 0.1s (100ms)

# 3. Measure warm start --help (bytecode cached)
time python -m ktrdr.cli.app --help
# Should be even faster

# 4. Verify commands still work
python -m ktrdr.cli.app train --help
python -m ktrdr.cli.app backtest --help
python -m ktrdr.cli.app list strategies

# 5. Verify telemetry works when needed
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317 \
python -m ktrdr.cli.app train momentum --start 2024-01-01 --end 2024-06-01
# Check Jaeger for trace
```

**Success Criteria:**
- [ ] `--help` responds in <100ms (cold start)
- [ ] All commands still work correctly
- [ ] Telemetry traces generated when commands execute
- [ ] No regressions from M1-M3

### Performance Metrics

| Metric | Baseline | Target | Actual |
|--------|----------|--------|--------|
| Import time | ~500ms | <100ms | **~80ms** ✅ |
| `--help` cold start | ~1000ms | <100ms | ~450ms ⚠️ |
| `--help` warm start | ~800ms | <50ms | ~300ms |
| Telemetry on import | Yes | No | **No** ✅ |

**Note:** `--help` target not fully met due to Typer requiring command imports to display help. See HANDOFF_M4.md for details.

### Completion Checklist

- [ ] All 3 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Performance target met (<100ms)
- [ ] M1-M3 E2E tests still pass
- [ ] Quality gates pass: `make quality`
