"""Validate command implementation.

Implements the `ktrdr validate` command for validating strategies via API or locally.

Usage:
- `ktrdr validate <name>` - Validate deployed strategy via API
- `ktrdr validate ./path` - Validate local strategy file (paths starting with ./ or /)
"""

import asyncio
import json
from pathlib import Path

import typer
import yaml
from rich.console import Console

from ktrdr.cli.client import AsyncCLIClient
from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.cli.telemetry import trace_cli_command

console = Console()


def _is_local_path(target: str) -> bool:
    """Check if target is a local file path (starts with ./ or /)."""
    return target.startswith("./") or target.startswith("/")


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


@trace_cli_command("validate")
def validate_cmd(
    ctx: typer.Context,
    target: str = typer.Argument(
        ..., help="Strategy name or path to local file (./path or /path)"
    ),
) -> None:
    """Validate a strategy configuration.

    Validate a deployed strategy by name:
        ktrdr validate momentum

    Validate a local file (for development):
        ktrdr validate ./my_strategy.yaml
        ktrdr validate /absolute/path/strategy.yaml
    """
    state: CLIState = ctx.obj

    try:
        if _is_local_path(target):
            _validate_local(state, target)
        else:
            asyncio.run(_validate_api(state, target))
    except Exception as e:
        print_error(str(e), state)
        raise typer.Exit(1) from None


def _validate_local(state: CLIState, path: str) -> None:
    """Validate a local strategy file.

    Detects v3 vs v2 format and uses appropriate validation.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    # Load raw YAML to detect format
    with open(file_path) as f:
        raw_config = yaml.safe_load(f)

    if _is_v3_format(raw_config):
        # V3 validation path
        _validate_v3_local(state, file_path, raw_config)
    else:
        # V2 validation path
        _validate_v2_local(state, file_path, raw_config)


def _validate_v3_local(state: CLIState, file_path: Path, raw_config: dict) -> None:
    """Validate a v3 strategy file locally."""
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_loader import StrategyConfigurationLoader
    from ktrdr.config.strategy_validator import StrategyValidationError

    try:
        # Load and validate v3 strategy
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(file_path)

        # Resolve features
        resolver = FeatureResolver()
        features = resolver.resolve(config)

        strategy_name = config.name

        if state.json_mode:
            print(
                json.dumps(
                    {
                        "valid": True,
                        "name": strategy_name,
                        "version": "3.0",
                        "features_count": len(features),
                    }
                )
            )
        else:
            console.print(
                f"[green]✓ Strategy '{strategy_name}' is valid (v3 format)[/green]"
            )
            console.print(f"  Resolved features: {len(features)}")

    except StrategyValidationError as e:
        if state.json_mode:
            print(
                json.dumps(
                    {
                        "valid": False,
                        "errors": [str(e)],
                    }
                )
            )
        else:
            console.print("[red]✗ Strategy is invalid:[/red]")
            console.print(f"  {e}")
        raise typer.Exit(1) from None


def _validate_v2_local(state: CLIState, file_path: Path, raw_config: dict) -> None:
    """Validate a v2 strategy file locally."""
    from ktrdr.config.strategy_validator import StrategyValidator

    validator = StrategyValidator()
    result = validator.validate_strategy(str(file_path))

    strategy_name = raw_config.get("name", file_path.stem)
    version = raw_config.get("version", "unknown")

    if state.json_mode:
        print(
            json.dumps(
                {
                    "valid": result.is_valid,
                    "name": strategy_name,
                    "version": version,
                    "errors": result.errors,
                    "warnings": result.warnings,
                }
            )
        )
        if not result.is_valid:
            raise typer.Exit(1) from None
    else:
        if result.is_valid:
            console.print(
                f"[green]✓ Strategy '{strategy_name}' is valid (v{version})[/green]"
            )
            if result.warnings:
                console.print(f"  Warnings: {len(result.warnings)}")
                for warning in result.warnings:
                    console.print(f"    - {warning}")
        else:
            console.print(f"[red]✗ Strategy '{strategy_name}' is invalid:[/red]")
            for error in result.errors:
                console.print(f"  - {error}")
            raise typer.Exit(1) from None


async def _validate_api(state: CLIState, name: str) -> None:
    """Validate a deployed strategy via API."""
    async with AsyncCLIClient() as client:
        result = await client.post(f"/strategies/validate/{name}")

    valid = result.get("valid", False)
    strategy_name = result.get("strategy_name", name)
    issues = result.get("issues", [])
    message = result.get("message", "")

    if state.json_mode:
        # Return structured JSON response
        print(
            json.dumps(
                {
                    "valid": valid,
                    "strategy_name": strategy_name,
                    "issues": issues,
                    "message": message,
                }
            )
        )
        if not valid:
            raise typer.Exit(1) from None
    else:
        if valid:
            console.print(f"[green]✓ Strategy '{strategy_name}' is valid[/green]")
            # Show warnings if any
            warnings = [i for i in issues if i.get("severity") == "warning"]
            if warnings:
                console.print(f"  Warnings: {len(warnings)}")
                for w in warnings:
                    console.print(f"    - {w.get('message', '')}")
        else:
            console.print(f"[red]✗ Strategy '{strategy_name}' is invalid:[/red]")
            for issue in issues:
                severity = issue.get("severity", "error")
                msg = issue.get("message", "Unknown error")
                if severity == "error":
                    console.print(f"  [red]✗[/red] {msg}")
                else:
                    console.print(f"  [yellow]![/yellow] {msg}")
            raise typer.Exit(1) from None
