---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Information Commands

**Goal:** User can list strategies/models/checkpoints, show data, validate strategies, and migrate v2→v3.

**Branch:** `feature/cli-restructure-m3`

**Builds on:** Milestone 2 (operation commands)

---

## Preservation Requirements

### List Strategies Command

**`ktrdr list strategies` replaces `ktrdr strategies list` from `strategy_commands.py`.**

**Behavior to preserve:**
- `@trace_cli_command("list_strategies")` telemetry
- Table with name, version, symbols, timeframes
- Handle both v2 and v3 strategy formats

### List Models Command

**`ktrdr list models` is NEW functionality.** No old command, but should match `list strategies` UX.

### List Checkpoints Command

**`ktrdr list checkpoints` relates to `ktrdr operations list --resumable`.**

**Behavior to preserve:**
- Show checkpoint summary (epoch, bar index, etc.)
- Link to operation ID

### Validate Command

**`ktrdr validate` replaces `ktrdr strategies validate` from `strategy_commands.py`.**

| Old Option | New Option | Notes |
|------------|------------|-------|
| `--quiet`, `-q` | `--quiet`, `-q` | Keep as-is |

**Behavior to preserve:**
- `@trace_cli_command("validate")` telemetry
- Support both v2 and v3 strategy formats
- v3: Display resolved NN input features
- v2: Show validation results
- Support both strategy names (via API) and local paths (prefixed with `./` or `/`)

### Show Command

**`ktrdr show` is NEW functionality** combining several capabilities:
- `ktrdr show <symbol> [timeframe]` — Show market data (new)
- `ktrdr show features <strategy>` — Replaces `ktrdr strategies features`

For `show features`:
**Behavior to preserve:**
- `@trace_cli_command("show_features")` telemetry
- Display resolved NN input features for v3 strategies
- Show indicator → fuzzy set → feature mapping

### Migrate Command

**`ktrdr migrate` replaces `ktrdr strategies migrate` from `strategy_commands.py`.**

**Behavior to preserve:**
- `@trace_cli_command("migrate")` telemetry
- Convert v2 strategy to v3 format
- Preserve original file, create new `_v3.yaml` file
- Show migration summary

---

## Task 3.1: Implement List Command

**File:** `ktrdr/cli/commands/list_cmd.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint

**Description:**
Implement `ktrdr list <resource>` where resource is `strategies`, `models`, or `checkpoints`. Each shows a table of the requested resources.

**Implementation Notes:**
```python
import asyncio
from typing import Literal
import typer
from rich.console import Console
from rich.table import Table
from ktrdr.cli.state import CLIState
from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error

console = Console()

# Create a subcommand group
list_app = typer.Typer(name="list", help="List resources")

@list_app.command("strategies")
def list_strategies(ctx: typer.Context):
    """List available strategies."""
    state: CLIState = ctx.obj
    try:
        asyncio.run(_list_strategies(state))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _list_strategies(state: CLIState):
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.get( "/strategies")

    strategies = result.get("data", [])

    if state.json_mode:
        import json
        print(json.dumps(strategies))
    else:
        table = Table(title="Strategies")
        table.add_column("Name", style="cyan")
        table.add_column("Version")
        table.add_column("Symbols")
        table.add_column("Timeframes")

        for s in strategies:
            # Handle v3 format (training_data.symbols) and v2 (data.symbols)
            td = s.get("training_data", s.get("data", {}))
            symbols = ", ".join(td.get("symbols", []))
            timeframes = ", ".join(td.get("timeframes", []))
            table.add_row(
                s.get("name", ""),
                s.get("version", ""),
                symbols,
                timeframes,
            )

        console.print(table)

@list_app.command("models")
def list_models(ctx: typer.Context):
    """List trained models."""
    state: CLIState = ctx.obj
    try:
        asyncio.run(_list_models(state))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _list_models(state: CLIState):
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.get( "/models")

    models = result.get("data", [])

    if state.json_mode:
        import json
        print(json.dumps(models))
    else:
        table = Table(title="Models")
        table.add_column("Name", style="cyan")
        table.add_column("Strategy")
        table.add_column("Created")
        table.add_column("Performance")

        for m in models:
            perf = m.get("performance", {})
            sharpe = perf.get("sharpe_ratio", "N/A")
            table.add_row(
                m.get("name", ""),
                m.get("strategy_name", ""),
                m.get("created_at", "")[:10],
                f"Sharpe: {sharpe}" if sharpe != "N/A" else "N/A",
            )

        console.print(table)

@list_app.command("checkpoints")
def list_checkpoints(ctx: typer.Context):
    """List available checkpoints."""
    state: CLIState = ctx.obj
    try:
        asyncio.run(_list_checkpoints(state))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _list_checkpoints(state: CLIState):
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.get( "/checkpoints")

    checkpoints = result.get("data", [])

    if state.json_mode:
        import json
        print(json.dumps(checkpoints))
    else:
        table = Table(title="Checkpoints")
        table.add_column("ID", style="cyan")
        table.add_column("Strategy")
        table.add_column("Created")
        table.add_column("Size")

        for c in checkpoints:
            table.add_row(
                c.get("id", "")[:12],
                c.get("strategy_name", ""),
                c.get("created_at", "")[:10],
                c.get("size_mb", ""),
            )

        console.print(table)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_list_strategies_command()` — verify subcommand exists
- [ ] `test_list_models_command()` — verify subcommand exists
- [ ] `test_list_checkpoints_command()` — verify subcommand exists

*Integration Tests:*
- [ ] `test_list_strategies_returns_data()` — with backend
- [ ] `test_list_models_returns_data()` — with backend
- [ ] `test_list_json_output()` — verify JSON structure

*Smoke Test:*
```bash
ktrdr list strategies
ktrdr list models
ktrdr list checkpoints --json
```

**Acceptance Criteria:**
- [ ] `ktrdr list strategies` shows table
- [ ] `ktrdr list models` shows table
- [ ] `ktrdr list checkpoints` shows table
- [ ] `--json` works for all
- [ ] Handles v3 strategy format
- [ ] Unit tests pass

---

## Task 3.2: Implement Show Command

**File:** `ktrdr/cli/commands/show.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint

**Description:**
Implement `ktrdr show <symbol> [timeframe]` for market data and `ktrdr show features <strategy>` for strategy features.

**Implementation Notes:**
```python
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from ktrdr.cli.state import CLIState
from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error

console = Console()

# Main show command with subcommands
show_app = typer.Typer(name="show", help="Show data and details")

@show_app.callback(invoke_without_command=True)
def show_data(
    ctx: typer.Context,
    symbol: Optional[str] = typer.Argument(None, help="Symbol (e.g., AAPL)"),
    timeframe: str = typer.Argument("1h", help="Timeframe (e.g., 1h, 1d)"),
):
    """Show market data for a symbol.

    Examples:
        ktrdr show AAPL
        ktrdr show AAPL 1d
    """
    if ctx.invoked_subcommand is not None:
        return  # Subcommand will handle it

    if not symbol:
        console.print("Usage: ktrdr show <symbol> [timeframe]")
        console.print("       ktrdr show features <strategy>")
        raise typer.Exit(0)

    state: CLIState = ctx.obj

    try:
        asyncio.run(_show_data(state, symbol, timeframe))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _show_data(state: CLIState, symbol: str, timeframe: str):
    """Fetch and display market data."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.get(
            f"/data/{symbol}/{timeframe}",
            params={"limit": 20},  # Last 20 bars
        )

    data = result.get("data", [])

    if state.json_mode:
        import json
        print(json.dumps(data))
    else:
        table = Table(title=f"{symbol} {timeframe}")
        table.add_column("Date", style="cyan")
        table.add_column("Open")
        table.add_column("High")
        table.add_column("Low")
        table.add_column("Close")
        table.add_column("Volume")

        for bar in data[-10:]:  # Last 10 for display
            table.add_row(
                bar.get("timestamp", "")[:16],
                f"{bar.get('open', 0):.2f}",
                f"{bar.get('high', 0):.2f}",
                f"{bar.get('low', 0):.2f}",
                f"{bar.get('close', 0):.2f}",
                f"{bar.get('volume', 0):,.0f}",
            )

        console.print(table)

@show_app.command("features")
def show_features(
    ctx: typer.Context,
    strategy: str = typer.Argument(..., help="Strategy name"),
):
    """Show resolved features for a strategy.

    Examples:
        ktrdr show features momentum
    """
    state: CLIState = ctx.obj

    try:
        asyncio.run(_show_features(state, strategy))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

async def _show_features(state: CLIState, strategy: str):
    """Fetch and display strategy features."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.get( f"/strategies/{strategy}/features")

    features = result.get("data", {}).get("features", [])

    if state.json_mode:
        import json
        print(json.dumps(features))
    else:
        table = Table(title=f"Features: {strategy}")
        table.add_column("Name", style="cyan")
        table.add_column("Type")
        table.add_column("Parameters")

        for f in features:
            params = ", ".join(f"{k}={v}" for k, v in f.get("params", {}).items())
            table.add_row(
                f.get("name", ""),
                f.get("type", ""),
                params or "-",
            )

        console.print(table)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_show_data_command()` — verify symbol arg
- [ ] `test_show_features_command()` — verify strategy arg

*Integration Tests:*
- [ ] `test_show_data_returns_ohlcv()` — with backend and data
- [ ] `test_show_features_returns_list()` — with backend and strategy

*Smoke Test:*
```bash
ktrdr show AAPL
ktrdr show AAPL 1d
ktrdr show features momentum
```

**Acceptance Criteria:**
- [ ] `ktrdr show <symbol>` shows OHLCV data
- [ ] `ktrdr show <symbol> <timeframe>` works
- [ ] `ktrdr show features <strategy>` shows features
- [ ] `--json` works for both
- [ ] Unit tests pass

---

## Task 3.3: Implement Validate Command

**File:** `ktrdr/cli/commands/validate.py`
**Type:** CODING
**Estimated time:** 1.5 hours

**Task Categories:** API Endpoint, Configuration

**Description:**
Implement `ktrdr validate <name|./path>`. For strategy names, validate via API. For local paths (starting with `./` or `/`), validate locally.

**Implementation Notes:**
```python
import asyncio
from pathlib import Path
import typer
from rich.console import Console
from ktrdr.cli.state import CLIState
from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error, print_success

console = Console()

def validate(
    ctx: typer.Context,
    target: str = typer.Argument(..., help="Strategy name or ./path to local file"),
):
    """Validate a strategy.

    Validate a deployed strategy by name:
        ktrdr validate momentum

    Validate a local file (for development):
        ktrdr validate ./my_strategy.yaml
    """
    state: CLIState = ctx.obj

    try:
        if target.startswith("./") or target.startswith("/"):
            _validate_local(state, target)
        else:
            asyncio.run(_validate_api(state, target))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

def _validate_local(state: CLIState, path: str):
    """Validate a local strategy file."""
    import yaml
    from ktrdr.strategy.v3.loader import validate_v3_strategy

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(file_path) as f:
        strategy_dict = yaml.safe_load(f)

    # Use existing v3 validation
    errors = validate_v3_strategy(strategy_dict)

    if errors:
        if state.json_mode:
            import json
            print(json.dumps({"valid": False, "errors": errors}))
        else:
            console.print("[red]Strategy is invalid:[/red]")
            for error in errors:
                console.print(f"  - {error}")
        raise typer.Exit(1)
    else:
        version = strategy_dict.get("version", "unknown")
        if state.json_mode:
            import json
            print(json.dumps({"valid": True, "version": version}))
        else:
            console.print(f"[green]Strategy is valid (v{version} format)[/green]")

async def _validate_api(state: CLIState, name: str):
    """Validate a deployed strategy via API."""
    async with AsyncCLIClient(base_url=state.api_url) as client:
        result = await client.post(f"/strategies/validate/{name}")

    valid = result.get("valid", False)
    errors = result.get("errors", [])

    if state.json_mode:
        import json
        print(json.dumps({"valid": valid, "errors": errors}))
    elif valid:
        console.print(f"[green]Strategy '{name}' is valid[/green]")
        if result.get("features_count"):
            console.print(f"Resolved features: {result['features_count']}")
    else:
        console.print(f"[red]Strategy '{name}' is invalid:[/red]")
        for error in errors:
            console.print(f"  - {error}")
        raise typer.Exit(1)
```

**Note:** Local validation is an intentional exception to "thin CLI" — it enables pre-deployment testing.

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_validate_detects_local_path()` — `./` and `/` paths
- [ ] `test_validate_detects_name()` — plain names go to API

*Integration Tests:*
- [ ] `test_validate_api_valid_strategy()` — with deployed strategy
- [ ] `test_validate_api_invalid_strategy()` — verify error handling
- [ ] `test_validate_local_file()` — with local yaml file

*Smoke Test:*
```bash
ktrdr validate momentum
ktrdr validate ./strategies/momentum.yaml
```

**Acceptance Criteria:**
- [ ] `ktrdr validate <name>` validates via API
- [ ] `ktrdr validate ./path` validates locally
- [ ] Invalid strategies show errors
- [ ] `--json` works
- [ ] Unit tests pass

---

## Task 3.4: Implement Migrate Command

**File:** `ktrdr/cli/commands/migrate.py`
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Configuration

**Description:**
Implement `ktrdr migrate <./path>` to migrate a local v2 strategy to v3 format.

**Implementation Notes:**
```python
from pathlib import Path
import typer
from rich.console import Console
from ktrdr.cli.state import CLIState
from ktrdr.cli.output import print_error, print_success

console = Console()

def migrate(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to v2 strategy file"),
    output: str = typer.Option(None, "--output", "-o", help="Output path (default: {name}_v3.yaml)"),
):
    """Migrate a v2 strategy to v3 format.

    Examples:
        ktrdr migrate ./old_strategy.yaml
        ktrdr migrate ./old_strategy.yaml -o ./new_strategy.yaml
    """
    state: CLIState = ctx.obj

    try:
        _migrate_strategy(state, path, output)
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1)

def _migrate_strategy(state: CLIState, path: str, output: str | None):
    """Migrate a v2 strategy file to v3 format."""
    import yaml
    from ktrdr.strategy.migration import migrate_v2_to_v3

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with open(file_path) as f:
        v2_strategy = yaml.safe_load(f)

    # Check if already v3
    if v2_strategy.get("version") == "3.0":
        if state.json_mode:
            import json
            print(json.dumps({"status": "skipped", "reason": "already_v3"}))
        else:
            console.print("[yellow]Strategy is already v3 format, no migration needed[/yellow]")
        return

    # Migrate
    v3_strategy = migrate_v2_to_v3(v2_strategy)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = file_path.with_name(f"{file_path.stem}_v3.yaml")

    # Write output
    with open(output_path, "w") as f:
        yaml.dump(v3_strategy, f, default_flow_style=False, sort_keys=False)

    if state.json_mode:
        import json
        print(json.dumps({
            "status": "migrated",
            "input": str(file_path),
            "output": str(output_path),
        }))
    else:
        console.print(f"[green]Migrated: {file_path} -> {output_path}[/green]")
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_migrate_requires_path()` — verify required arg
- [ ] `test_migrate_output_option()` — verify `-o` option

*Integration Tests:*
- [ ] `test_migrate_v2_file()` — with v2 yaml, verify output
- [ ] `test_migrate_already_v3()` — verify skip behavior

*Smoke Test:*
```bash
ktrdr migrate ./strategies/old_v2.yaml
ls ./strategies/old_v2_v3.yaml
```

**Acceptance Criteria:**
- [ ] `ktrdr migrate <path>` creates v3 file
- [ ] `-o` option specifies output path
- [ ] Already-v3 strategies handled gracefully
- [ ] `--json` works
- [ ] Unit tests pass

---

## Task 3.5: Wire Up Information Commands

**File:** `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Wiring/DI

**Description:**
Register all M3 commands in the app entry point.

**Implementation Notes:**
```python
from ktrdr.cli.commands.list_cmd import list_app
from ktrdr.cli.commands.show import show_app
from ktrdr.cli.commands.validate import validate
from ktrdr.cli.commands.migrate import migrate

# Add subcommand groups
app.add_typer(list_app)
app.add_typer(show_app)

# Add direct commands
app.command()(validate)
app.command()(migrate)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_list_subcommands_registered()` — verify in --help
- [ ] `test_show_subcommands_registered()` — verify in --help

*Integration Tests:*
- [ ] Full workflow test: list strategies → show features → validate

*Smoke Test:*
```bash
ktrdr --help
# Should show: list, show, validate, migrate
ktrdr list --help
# Should show: strategies, models, checkpoints
```

**Acceptance Criteria:**
- [ ] All commands appear in `--help`
- [ ] Subcommands (list, show) work correctly
- [ ] M1 and M2 tests still pass

---

## Milestone 3 Verification

### E2E Test Scenario

**E2E Test Recipe:** [cli/information-commands](../../../../.claude/skills/e2e-testing/tests/cli/information-commands.md)

**Purpose:** Prove all information commands work correctly.

**Duration:** ~1 minute

**Prerequisites:**
- Backend running
- At least one strategy deployed
- Some market data available

**Test Steps:**

```bash
# 1. List strategies
ktrdr list strategies
# Should show table with strategy name, version, symbols

# 2. List models
ktrdr list models
# Should show table (may be empty)

# 3. Show market data
ktrdr show AAPL 1h
# Should show OHLCV table

# 4. Show features
ktrdr show features momentum
# Should show feature list

# 5. Validate deployed strategy
ktrdr validate momentum
# Should say "valid"

# 6. Validate local file
ktrdr validate ./strategies/momentum.yaml
# Should say "valid"

# 7. JSON output
ktrdr list strategies --json | jq
```

**Success Criteria:**
- [ ] All commands execute without errors
- [ ] Tables display correctly
- [ ] JSON output valid
- [ ] Local validation works

### Completion Checklist

- [ ] All 5 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes
- [ ] M1 and M2 E2E tests still pass
- [ ] Quality gates pass: `make quality`
