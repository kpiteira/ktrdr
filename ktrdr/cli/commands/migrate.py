"""Migrate command implementation.

Implements the `ktrdr migrate` command for migrating v2 strategies to v3 format.

Usage:
- `ktrdr migrate ./path.yaml` - Migrate a v2 strategy file to v3 format
- `ktrdr migrate ./path.yaml -o ./output.yaml` - Specify output path
"""

import json
from pathlib import Path

import typer
import yaml
from rich.console import Console

from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()


def _is_v3_format(config: dict) -> bool:
    """Check if a strategy config is v3 format.

    V3 format has:
    - indicators as a dict (not list)
    - nn_inputs section
    """
    return (
        isinstance(config, dict)
        and isinstance(config.get("indicators"), dict)
        and "nn_inputs" in config
    )


@trace_cli_command("migrate")
def migrate_cmd(
    ctx: typer.Context,
    path: str = typer.Argument(..., help="Path to v2 strategy file"),
    output: str = typer.Option(
        None, "--output", "-o", help="Output path (default: {name}_v3.yaml)"
    ),
) -> None:
    """Migrate a v2 strategy to v3 format.

    Converts v2 strategy configurations (list-based indicators) to v3 format
    (dict-based indicators with nn_inputs).

    Examples:
        ktrdr migrate ./old_strategy.yaml
        ktrdr migrate ./old_strategy.yaml -o ./new_strategy.yaml
    """
    state: CLIState = ctx.obj

    try:
        _migrate_strategy(state, path, output)
    except FileNotFoundError as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None
    except yaml.YAMLError as e:
        print_error(f"Invalid YAML: {e}", state)
        raise typer.Exit(1) from None
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


def _migrate_strategy(state: CLIState, path: str, output: str | None) -> None:
    """Migrate a v2 strategy file to v3 format.

    Args:
        state: CLI state for output mode settings
        path: Path to the v2 strategy file
        output: Optional output path (defaults to {name}_v3.yaml)
    """
    from ktrdr.config.strategy_migration import migrate_v2_to_v3

    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Load and parse YAML
    with open(file_path) as f:
        v2_strategy = yaml.safe_load(f)

    if not isinstance(v2_strategy, dict):
        raise ValueError(
            f"Invalid strategy file: expected dict, got {type(v2_strategy).__name__}"
        )

    # Check if already v3
    if _is_v3_format(v2_strategy):
        if state.json_mode:
            print(json.dumps({"status": "skipped", "reason": "already_v3"}))
        else:
            console.print(
                "[yellow]Strategy is already v3 format, no migration needed[/yellow]"
            )
        return

    # Migrate to v3
    v3_strategy = migrate_v2_to_v3(v2_strategy)

    # Determine output path
    if output:
        output_path = Path(output)
    else:
        output_path = file_path.with_name(f"{file_path.stem}_v3.yaml")

    # Create parent directory if needed
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(output_path, "w") as f:
        yaml.dump(v3_strategy, f, default_flow_style=False, sort_keys=False)

    # Report result
    if state.json_mode:
        print(
            json.dumps(
                {
                    "status": "migrated",
                    "input": str(file_path),
                    "output": str(output_path),
                }
            )
        )
    else:
        console.print(f"[green]Migrated: {file_path} -> {output_path}[/green]")
