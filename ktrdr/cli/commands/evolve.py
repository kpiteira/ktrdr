"""Evolve command implementation.

Implements `ktrdr evolve start|status|resume` for population-based evolution.

PERFORMANCE NOTE: Heavy imports (httpx, evolution module, Rich) are deferred
inside function bodies to keep CLI startup fast.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

if TYPE_CHECKING:
    from rich.console import Console

    from ktrdr.evolution.config import EvolutionConfig
    from ktrdr.evolution.tracker import EvolutionTracker

evolve_app = typer.Typer(
    name="evolve",
    help="Population-based evolution experiments.",
)


def _get_evolution_dir() -> Path:
    """Get the evolution data directory."""
    return Path("data/evolution")


def _run_evolution(
    population_size: int,
    generations: int,
    symbol: str,
    timeframe: str,
    model: str,
    seed: int | None,
) -> None:
    """Run evolution experiment (sync wrapper around async harness)."""
    import asyncio
    from datetime import datetime

    import httpx
    from rich.console import Console

    from ktrdr.cli.sandbox_detect import resolve_api_url
    from ktrdr.evolution.config import EvolutionConfig
    from ktrdr.evolution.harness import GenerationHarness
    from ktrdr.evolution.population import PopulationManager
    from ktrdr.evolution.tracker import EvolutionTracker

    console = Console()

    config = EvolutionConfig(
        population_size=population_size,
        generations=generations,
        symbol=symbol,
        timeframe=timeframe,
        model=model,
        seed=seed,
    )

    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = _get_evolution_dir() / run_id
    tracker = EvolutionTracker(run_dir=run_dir)
    tracker.save_config(config)

    console.print(f"\n[bold]Evolution Experiment[/bold]: {run_id}")
    console.print(f"  Population: {population_size}, Generations: {generations}")
    console.print(f"  Symbol: {symbol}, Timeframe: {timeframe}, Model: {model}")
    console.print()

    base_url = resolve_api_url()
    console.print(f"  API: {base_url}")

    pm = PopulationManager()

    async def _run_async() -> None:
        async with httpx.AsyncClient(timeout=60.0) as client:
            harness = GenerationHarness(
                config=config,
                tracker=tracker,
                http_client=client,  # type: ignore[arg-type]
                base_url=base_url,
            )
            await harness.run(pm)

    console.print(
        f"[yellow]Running {generations} generation(s) "
        f"with {population_size} researchers...[/yellow]\n"
    )
    asyncio.run(_run_async())

    # Display final summary
    _print_run_summary(console, tracker, config)
    console.print(f"\n[bold]State saved to:[/bold] {run_dir}")


def _print_run_summary(
    console: Console,
    tracker: EvolutionTracker,
    config: EvolutionConfig,
) -> None:
    """Print a summary table for an evolution run."""
    from rich.table import Table

    from ktrdr.evolution.fitness import MINIMUM_FITNESS

    summary = tracker.load_summary()
    gen_stats = summary.get("generations", [])

    if not gen_stats:
        console.print("[yellow]No generation data available.[/yellow]")
        return

    table = Table(title="Evolution Summary")
    table.add_column("Gen", justify="right", style="cyan")
    table.add_column("Pop", justify="right")
    table.add_column("OK", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Mean Fitness", justify="right")
    table.add_column("Max Fitness", justify="right", style="bold")

    for gs in gen_stats:
        mean_f = gs.get("mean_fitness", 0.0)
        max_f = gs.get("max_fitness", MINIMUM_FITNESS)
        table.add_row(
            str(gs["generation"]),
            str(gs["population_size"]),
            str(gs.get("successful", 0)),
            str(gs.get("failed", 0)),
            f"{mean_f:.4f}" if mean_f > MINIMUM_FITNESS else "N/A",
            f"{max_f:.4f}" if max_f > MINIMUM_FITNESS else "N/A",
        )

    console.print(table)

    completed = len(gen_stats)
    total = config.generations
    if completed >= total:
        console.print(f"\n[green]Complete[/green]: {completed}/{total} generations")
    else:
        console.print(
            f"\n[yellow]In progress[/yellow]: {completed}/{total} generations"
        )


@evolve_app.command("start")
def start(
    population: int = typer.Option(
        12, "--population", "-p", help="Population size (min 2)", min=2
    ),
    generations: int = typer.Option(
        5, "--generations", "-g", help="Number of generations (min 1)", min=1
    ),
    symbol: str = typer.Option("EURUSD", "--symbol", "-s", help="Trading symbol"),
    timeframe: str = typer.Option("1h", "--timeframe", "-t", help="Timeframe"),
    model: str = typer.Option("haiku", "--model", "-m", help="LLM model for research"),
    seed: int | None = typer.Option(
        None, "--seed", help="Random seed for reproducibility"
    ),
) -> None:
    """Start an evolution experiment.

    Seeds a population of researchers with diverse genomes and evolves them
    through multiple generations with selection and reproduction.

    Examples:
        ktrdr evolve start --population 6 --generations 3

        ktrdr evolve start --population 12 --seed 42
    """
    _run_evolution(
        population_size=population,
        generations=generations,
        symbol=symbol,
        timeframe=timeframe,
        model=model,
        seed=seed,
    )


@evolve_app.command("status")
def status(
    run_id: str = typer.Argument(None, help="Run ID (default: most recent)"),
) -> None:
    """Show evolution run status and per-generation stats.

    If no run_id is given, shows the most recent run.

    Examples:
        ktrdr evolve status

        ktrdr evolve status run_20260101_120000
    """
    from rich.console import Console

    from ktrdr.evolution.tracker import EvolutionTracker

    console = Console()
    evo_dir = _get_evolution_dir()

    if not evo_dir.exists():
        console.print("[yellow]No evolution runs found.[/yellow]")
        return

    if run_id is None:
        # Find most recent run
        run_dirs = sorted(evo_dir.glob("run_*"))
        if not run_dirs:
            console.print("[yellow]No evolution runs found.[/yellow]")
            return
        run_dir = run_dirs[-1]
        run_id = run_dir.name
    else:
        run_dir = evo_dir / run_id

    if not run_dir.exists():
        console.print(f"[red]Run not found:[/red] {run_id}")
        raise typer.Exit(code=1)

    tracker = EvolutionTracker(run_dir=run_dir)
    config = tracker.load_config()

    if config is None:
        console.print(f"[red]Invalid run directory:[/red] {run_id}")
        raise typer.Exit(code=1)

    console.print(f"\n[bold]Evolution Run[/bold]: {run_id}")
    console.print(
        f"  Population: {config.population_size}, " f"Generations: {config.generations}"
    )
    console.print(f"  Symbol: {config.symbol}, Timeframe: {config.timeframe}")
    console.print()

    _print_run_summary(console, tracker, config)


@evolve_app.command("resume")
def resume_cmd(
    run_id: str = typer.Argument(..., help="Run ID to resume"),
) -> None:
    """Resume a stopped or crashed evolution run.

    Continues from the last completed generation, recovering any
    in-flight operations.

    Examples:
        ktrdr evolve resume run_20260101_120000
    """
    import asyncio

    import httpx
    from rich.console import Console

    from ktrdr.cli.sandbox_detect import resolve_api_url
    from ktrdr.evolution.harness import GenerationHarness
    from ktrdr.evolution.population import PopulationManager
    from ktrdr.evolution.tracker import EvolutionTracker

    console = Console()
    evo_dir = _get_evolution_dir()
    run_dir = evo_dir / run_id

    if not run_dir.exists():
        console.print(f"[red]Run not found:[/red] {run_id}")
        raise typer.Exit(code=1)

    tracker = EvolutionTracker(run_dir=run_dir)
    config = tracker.load_config()

    if config is None:
        console.print(f"[red]Invalid run directory:[/red] {run_id}")
        raise typer.Exit(code=1)

    base_url = resolve_api_url()
    console.print(f"\n[bold]Resuming[/bold]: {run_id}")
    console.print(f"  API: {base_url}")

    last_gen = tracker.get_last_completed_generation()
    if last_gen is not None:
        console.print(f"  Last completed generation: {last_gen}")
    console.print()

    pm = PopulationManager()

    async def _resume_async() -> None:
        async with httpx.AsyncClient(timeout=60.0) as client:
            harness = GenerationHarness(
                config=config,
                tracker=tracker,
                http_client=client,  # type: ignore[arg-type]
                base_url=base_url,
            )
            await harness.resume(pm)

    asyncio.run(_resume_async())

    _print_run_summary(console, tracker, config)
    console.print(f"\n[bold]State saved to:[/bold] {run_dir}")
