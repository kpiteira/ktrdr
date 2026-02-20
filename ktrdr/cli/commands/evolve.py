"""Evolve command implementation.

Implements `ktrdr evolve start` to run population-based evolution experiments.
For M1, runs a single generation and displays fitness scores.

PERFORMANCE NOTE: Heavy imports (httpx, evolution module, Rich) are deferred
inside function bodies to keep CLI startup fast.
"""

from __future__ import annotations

import typer

evolve_app = typer.Typer(
    name="evolve",
    help="Population-based evolution experiments.",
)


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
    from pathlib import Path

    import httpx
    from rich.console import Console
    from rich.table import Table

    from ktrdr.evolution.config import EvolutionConfig
    from ktrdr.evolution.harness import GenerationHarness
    from ktrdr.evolution.population import PopulationManager
    from ktrdr.evolution.tracker import EvolutionTracker

    console = Console()

    # Build config
    config = EvolutionConfig(
        population_size=population_size,
        generations=generations,
        symbol=symbol,
        timeframe=timeframe,
        model=model,
        seed=seed,
    )

    # Create run directory
    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir = Path("data/evolution") / run_id
    tracker = EvolutionTracker(run_dir=run_dir)
    tracker.save_config(config)

    console.print(f"\n[bold]Evolution Experiment[/bold]: {run_id}")
    console.print(f"  Population: {population_size}, Generations: {generations}")
    console.print(f"  Symbol: {symbol}, Timeframe: {timeframe}, Model: {model}")
    console.print()

    # Seed initial population
    pm = PopulationManager()
    population = pm.seed(config)
    tracker.save_population(0, population)

    console.print(f"[green]Seeded {len(population)} researchers[/green]")

    async def _run_async() -> list[dict]:
        async with httpx.AsyncClient(timeout=60.0) as client:
            harness = GenerationHarness(
                config=config,
                tracker=tracker,
                http_client=client,
            )
            return await harness.run_generation(0, population)

    # Run generation
    console.print("[yellow]Running generation 0...[/yellow]\n")
    results = asyncio.run(_run_async())

    # Save results
    tracker.save_results(0, results)

    # Display results table
    table = Table(title="Generation 0 Results")
    table.add_column("Researcher", style="cyan")
    table.add_column("Fitness", justify="right", style="green")
    table.add_column("Status")

    for r in sorted(results, key=lambda x: x["fitness"], reverse=True):
        fitness = r["fitness"]
        status = "[red]FAILED[/red]" if fitness <= -999 else "[green]OK[/green]"
        table.add_row(
            r["researcher_id"],
            f"{fitness:.4f}",
            status,
        )

    console.print(table)
    console.print(f"\n[bold]State saved to:[/bold] {run_dir}")


@evolve_app.command("start")
def start(
    population: int = typer.Option(
        12, "--population", "-p", help="Population size (min 2)", min=2
    ),
    generations: int = typer.Option(
        5, "--generations", "-g", help="Number of generations (min 1)", min=1
    ),
    symbol: str = typer.Option(
        "EURUSD", "--symbol", "-s", help="Trading symbol"
    ),
    timeframe: str = typer.Option(
        "1h", "--timeframe", "-t", help="Timeframe"
    ),
    model: str = typer.Option(
        "haiku", "--model", "-m", help="LLM model for research"
    ),
    seed: int | None = typer.Option(
        None, "--seed", help="Random seed for reproducibility"
    ),
) -> None:
    """Start an evolution experiment.

    Seeds a population of researchers with diverse genomes, runs them
    through the research pipeline, and scores their fitness.

    Examples:
        ktrdr evolve start --population 3 --generations 1

        ktrdr evolve start --population 6 --seed 42
    """
    _run_evolution(
        population_size=population,
        generations=generations,
        symbol=symbol,
        timeframe=timeframe,
        model=model,
        seed=seed,
    )
