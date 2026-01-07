"""Shared utilities for V3 strategy handling in CLI commands."""

from pathlib import Path

import typer
import yaml
from rich.console import Console

from ktrdr.config.strategy_loader import StrategyConfigurationLoader
from ktrdr.logging import get_logger

logger = get_logger(__name__)
console = Console()


def is_v3_strategy(strategy_path: Path) -> bool:
    """
    Check if a strategy file is v3 format.

    V3 format is identified by:
    - indicators is a dict (not a list)
    - nn_inputs field is present

    Args:
        strategy_path: Path to strategy file

    Returns:
        True if strategy appears to be v3 format
    """
    try:
        with open(strategy_path) as f:
            raw_config = yaml.safe_load(f)

        return (
            isinstance(raw_config, dict)
            and isinstance(raw_config.get("indicators"), dict)
            and "nn_inputs" in raw_config
        )
    except (OSError, yaml.YAMLError) as exc:
        # Expected errors reading or parsing the strategy file - treat as not v3
        logger.debug(
            "Failed to determine v3 strategy format for %s: %s", strategy_path, exc
        )
        return False
    except Exception:
        # Unexpected error - log full details but preserve boolean return contract
        logger.exception(
            "Unexpected error while checking v3 strategy format for %s", strategy_path
        )
        return False


def display_v3_dry_run(strategy_path: Path) -> None:
    """
    Display detailed v3 strategy dry-run information.

    Shows:
    - Strategy name and version
    - Indicators with their types
    - Fuzzy sets with indicator mappings
    - Resolved NN input features

    Args:
        strategy_path: Path to v3 strategy file

    Raises:
        typer.Exit: On any error during v3 analysis
    """
    from ktrdr.config.feature_resolver import FeatureResolver
    from ktrdr.config.strategy_validator import StrategyValidationError

    console.print()
    console.print("[yellow]DRY RUN - V3 Strategy Analysis[/yellow]")
    console.print("=" * 60)

    try:
        # Load v3 strategy
        loader = StrategyConfigurationLoader()
        config = loader.load_v3_strategy(strategy_path)

        # Display strategy info
        console.print(f"\n[cyan]Strategy: {config.name}[/cyan]")
        console.print(f"   Version: {config.version}")
        if config.description:
            console.print(f"   Description: {config.description}")

        # Display indicators
        console.print(f"\n[cyan]Indicators ({len(config.indicators)}):[/cyan]")
        for ind_id, ind_def in config.indicators.items():
            console.print(f"   {ind_id}: {ind_def.type}")

        # Display fuzzy sets
        console.print(f"\n[cyan]Fuzzy Sets ({len(config.fuzzy_sets)}):[/cyan]")
        for fs_id, fs_def in config.fuzzy_sets.items():
            console.print(f"   {fs_id} -> {fs_def.indicator}")

        # Resolve and display features
        resolver = FeatureResolver()
        features = resolver.resolve(config)

        console.print(f"\n[cyan]NN Inputs ({len(features)} features):[/cyan]")
        for feature in features:
            console.print(f"   {feature.feature_id}")

        # Summary
        console.print()
        console.print("=" * 60)
        console.print(
            f"[bold green]V3 config valid - {len(features)} features would be used for training[/bold green]"
        )
        console.print("\n[yellow][Dry run - no training performed][/yellow]")

    except FileNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1) from e
    except StrategyValidationError as e:
        console.print(f"[red]Strategy validation failed: {e}[/red]")
        raise typer.Exit(1) from e
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        logger.exception("Unexpected error during v3 dry-run")
        raise typer.Exit(1) from e
