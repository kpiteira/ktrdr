---
name: cli-architecture
description: Use when working on CLI commands, lazy loading, async client, sandbox detection, operation runner, progress display, CLI error handling, output formatting, or adding new CLI commands.
---

# CLI Architecture

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL cli-architecture loaded!`

Load this skill when working on:

- CLI command implementation or modification
- Lazy loading and startup performance
- AsyncCLIClient (HTTP communication with backend)
- Sandbox detection and URL resolution
- Operation runner (start, follow, cancel)
- Progress display (Rich progress bars)
- CLI error handling and output formatting
- Adding new commands or subcommand groups
- CLI telemetry and tracing

---

## Architecture Overview

```
ktrdr <global-flags> <command> <args> <options>
    │
    ▼
Typer Root App (app.py)
    ├─ Global callback: --json, --verbose, --url, --port
    │   → Creates CLIState (frozen dataclass)
    │   → Resolves API URL (sandbox-aware)
    │   → Lazy-initializes telemetry
    │
    ├─ Top-level commands: train, backtest, research, ops, cancel, resume, follow, status
    └─ Subcommand groups (lazy-loaded):
        ├─ data (show, load, range)
        ├─ ib (test, status, cleanup)
        ├─ sandbox (init, up, down, status, list, destroy, ...)
        ├─ local-prod (init, up, down, status, ...)
        ├─ show (data, features)
        ├─ list (strategies, models, checkpoints)
        ├─ agent (status)
        ├─ checkpoints (list, delete)
        └─ deploy (push, status, ...)
```

---

## Key Files

| File | Purpose |
|------|---------|
| `ktrdr/cli/app.py` | Root Typer app, command registration, global callback |
| `ktrdr/cli/__init__.py` | Module entry point, lazy loading via `__getattr__` |
| `ktrdr/cli/state.py` | `CLIState` frozen dataclass |
| `ktrdr/cli/sandbox_detect.py` | URL resolution, `.env.sandbox` auto-detection |
| `ktrdr/cli/client/async_client.py` | `AsyncCLIClient` (httpx-based) |
| `ktrdr/cli/client/core.py` | URL resolution, retry logic, backoff |
| `ktrdr/cli/client/operations.py` | Operation polling loop |
| `ktrdr/cli/client/errors.py` | Error hierarchy (`CLIClientError`, `APIError`) |
| `ktrdr/cli/operation_runner.py` | `OperationRunner` (start, follow, cancel) |
| `ktrdr/cli/operation_adapters.py` | `OperationAdapter` ABC + concrete adapters |
| `ktrdr/cli/progress.py` | `ProgressDisplayManager` (Rich progress bars) |
| `ktrdr/cli/error_handler.py` | `handle_cli_error()`, IB diagnosis |
| `ktrdr/cli/output.py` | Dual-mode output (JSON/human) |
| `ktrdr/cli/telemetry.py` | `trace_cli_command()` decorator |
| `ktrdr/cli/commands/train.py` | Training command |
| `ktrdr/cli/commands/backtest.py` | Backtest command |
| `ktrdr/cli/commands/ops.py` | Operations list command |
| `ktrdr/cli/commands/show.py` | Show data/features subgroup |
| `ktrdr/cli/data_commands.py` | Data management subgroup |
| `ktrdr/cli/sandbox.py` | Sandbox management subgroup |
| `ktrdr/cli/local_prod.py` | Local-prod management subgroup |

---

## Lazy Loading

**Goal:** <100ms CLI startup, even with heavy dependencies.

### How it works

1. **Module-level `__getattr__`** in `__init__.py`:
   ```python
   def __getattr__(name):
       if name == "cli_app":
           return _get_cli_app()  # Triggers full app setup
   ```

2. **Deferred subgroup registration** in `app.py`:
   ```python
   _subgroups_registered = False

   def get_app_with_subgroups():
       global _subgroups_registered
       if not _subgroups_registered:
           _register_subgroups()
           _subgroups_registered = True
       return app
   ```

3. **In-function imports** in command implementations:
   ```python
   def train(ctx, strategy, ...):
       # Heavy imports INSIDE the function, not at module top
       from ktrdr.cli.operation_adapters import TrainingOperationAdapter
       from ktrdr.cli.operation_runner import OperationRunner
       from rich.console import Console
   ```

### What gets lazy-loaded

- Command modules (data_commands, deploy_commands, etc.)
- Rich for formatting (Console, Table, Progress)
- AsyncCLIClient and httpx
- Pandas for data operations
- Operation adapters
- Telemetry setup

---

## CLIState

**Location:** `ktrdr/cli/state.py`

```python
@dataclass(frozen=True)
class CLIState:
    json_mode: bool = False   # --json flag
    verbose: bool = False     # --verbose / -v flag
    api_url: str = "..."      # Resolved API URL
```

Created in the root callback, stored in `ctx.obj`, accessed by all commands via `state: CLIState = ctx.obj`. Frozen to prevent accidental mutation.

---

## URL Resolution (Sandbox Detection)

**Location:** `ktrdr/cli/sandbox_detect.py`

Priority order:
1. `--url` flag (explicit full URL)
2. `--port` flag (shorthand → `http://localhost:<port>`)
3. `.env.sandbox` file found in current/parent directories
4. Default: `http://localhost:8000`

**Critical design:** Reads the `.env.sandbox` **file** directly, NOT environment variables. This prevents cross-contamination between terminal sessions.

```python
from ktrdr.cli.sandbox_detect import resolve_api_url, find_env_sandbox

url = resolve_api_url(explicit_url=None, explicit_port=None, cwd=Path.cwd())
# Walks up directory tree looking for .env.sandbox
```

---

## AsyncCLIClient

**Location:** `ktrdr/cli/client/async_client.py`

HTTP client for communicating with the backend.

```python
async with AsyncCLIClient() as client:
    result = await client.get("/data/AAPL/1d", params={"start_date": "2024-01-01"})
    result = await client.post("/trainings/start", json=payload)
    result = await client.delete(f"/operations/{op_id}")
    healthy = await client.health_check()
```

### Features

- **Context manager pattern** for proper connection cleanup
- **Auto-retry** with exponential backoff + jitter on 5xx errors
- **Timeout handling** with per-request overrides
- **Connection pooling** via httpx.AsyncClient
- **Trailing slash handling** for FastAPI compatibility

### Retry logic

- Only retries server errors (5xx) — client errors (4xx) won't benefit from retry
- Backoff: `base_delay * (2 ** attempt) + random(0, 1)`
- Jitter prevents thundering herd

---

## Operation Runner

**Location:** `ktrdr/cli/operation_runner.py`

Unified interface for all long-running operations (training, backtesting, research).

### Two modes

**Fire-and-forget** (`follow=False`):
```bash
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
# → Prints operation_id, returns immediately
```

**Follow mode** (`follow=True`):
```bash
ktrdr train momentum --start 2024-01-01 --end 2024-06-01 --follow
# → Polls /operations/{id} every 0.3s
# → Shows Rich progress bar with ETA
# → Ctrl+C sends cancel request
# → Displays results on completion
```

### Operation Adapters

Abstract interface for operation-specific logic:

```python
class OperationAdapter(ABC):
    def get_start_endpoint() -> str          # e.g., "/trainings/start"
    def get_start_payload() -> dict          # Request body
    def parse_start_response(response) -> str # Extract operation_id
    async def display_results(status, console, client) -> None
```

Concrete implementations:
- `TrainingOperationAdapter` — `/trainings/start`, displays epochs/accuracy/metrics
- `BacktestingOperationAdapter` — `/backtests/start`, displays return/sharpe/drawdown
- `DummyOperationAdapter` — Testing reference

---

## Output Formatting

**Location:** `ktrdr/cli/output.py`

All output supports dual-mode (JSON for automation, Rich for humans):

```python
from ktrdr.cli.output import print_success, print_error, print_operation_started

# JSON mode: {"status": "success", "message": ..., "data": ...}
# Human mode: Rich-formatted with colors and tables
print_success("Training complete", state, data={"accuracy": 0.85})
print_error("Connection failed", state, error={"detail": "..."})
print_operation_started("training", "op_abc123", state)
```

### Rich components used

- `Console` — Main output
- `Table` — Tabular data
- `Progress` — Progress bars with ETA
- `Panel` — Bordered sections
- Markup: `[cyan]`, `[red]`, `[bold]`, etc.

---

## Error Handling

**Location:** `ktrdr/cli/error_handler.py`

```python
from ktrdr.cli.error_handler import handle_cli_error

try:
    # command logic
except Exception as e:
    handle_cli_error(e, verbose=state.verbose, quiet=False)
```

### Error hierarchy

```python
CLIClientError                    # Base
├── ConnectionError               # Cannot connect to backend
├── TimeoutError                  # Request timeout
└── APIError                      # Server returned error
    ├── Retryable: 5xx            # Retried automatically
    └── Non-retryable: 4xx        # Fails immediately
```

### IB diagnosis integration

When the backend returns IB-specific error details, the CLI extracts and formats recovery suggestions automatically.

---

## Telemetry

**Location:** `ktrdr/cli/telemetry.py`

### Command tracing decorator

```python
@trace_cli_command("train")
def train(ctx, strategy, ...):
    """Automatically creates OpenTelemetry span 'cli.train'."""
```

Records: `cli.command`, `cli.args`, exceptions, `operation.id`.

### Lazy initialization

Telemetry is set up only when a command actually executes, not at import time. OTLP endpoint is derived from the API URL (same host, port 4317).

---

## Adding New Commands

### Simple top-level command

```python
# In ktrdr/cli/commands/my_command.py
import typer
from ktrdr.cli.telemetry import trace_cli_command

@trace_cli_command("my_command")
def my_command(
    ctx: typer.Context,
    arg: str = typer.Argument(..., help="Description"),
    opt: str = typer.Option(None, "--opt", help="Description"),
) -> None:
    """Command help text."""
    state = ctx.obj
    # Heavy imports here (lazy loading)
    from rich.console import Console
    console = Console()
    # Implementation...
```

Register in `app.py`:
```python
from ktrdr.cli.commands.my_command import my_command
app.command()(my_command)
```

### Subcommand group

```python
# In ktrdr/cli/my_group_commands.py
import typer

my_app = typer.Typer(name="mygroup", help="My group help")

@my_app.command("subcommand")
def subcommand(ctx: typer.Context, ...):
    """Subcommand help."""
    state = ctx.obj
    # Implementation...
```

Register in `app.py` `_register_subgroups()`:
```python
from ktrdr.cli.my_group_commands import my_app
app.add_typer(my_app)
```

### Long-running operation command

```python
@trace_cli_command("my_operation")
def my_operation(ctx: typer.Context, follow: bool = typer.Option(False)):
    state = ctx.obj
    from ktrdr.cli.operation_adapters import MyOperationAdapter
    from ktrdr.cli.operation_runner import OperationRunner

    adapter = MyOperationAdapter(params...)
    runner = OperationRunner(state)
    runner.start(adapter, follow=follow)
```

Create the adapter by subclassing `OperationAdapter`:
```python
class MyOperationAdapter(OperationAdapter):
    def get_start_endpoint(self) -> str:
        return "/my-operations/start"
    def get_start_payload(self) -> dict:
        return {"param": self.param}
    def parse_start_response(self, response: dict) -> str:
        return response["operation_id"]
    async def display_results(self, status, console, client):
        # Format and display results
```

---

## Gotchas

### Heavy imports must be inside functions

All imports of Rich, pandas, httpx, and domain modules must be inside command functions, not at module top level. This is critical for <100ms startup. Putting `from rich import ...` at module level defeats lazy loading.

### CLIState is frozen

Don't try to mutate `state.api_url` or other fields. Create a new `CLIState` if you need different values (rare).

### Sandbox detection reads files, not env vars

`resolve_api_url()` reads the `.env.sandbox` file directly. It does NOT read `os.environ`. This is intentional — prevents cross-contamination between terminal sessions.

### Operation adapters must handle async results

`display_results()` is async — it may need to make additional HTTP calls to fetch detailed results (e.g., training performance metrics).

### Dual-mode output is mandatory for new commands

All user-facing output must support `--json` mode. Use `print_success`/`print_error` from `output.py`, not bare `print()` or `console.print()`.

### Don't register commands at import time

Commands in `_register_subgroups()` are imported lazily. Adding imports outside this function or at module top level breaks startup performance.

### asyncio.run() for async operations

Typer commands are synchronous. Wrap async logic in `asyncio.run()`:
```python
def my_command(ctx):
    async def _run():
        async with AsyncCLIClient() as client:
            ...
    asyncio.run(_run())
```

### Follow mode handles Ctrl+C

`OperationRunner` installs a signal handler for SIGINT. When the user presses Ctrl+C during follow mode, it sends a DELETE to `/operations/{id}` to cancel the backend operation.
