"""Evolve command implementation.

Implements `ktrdr evolve start|status|resume|report` for population-based evolution.

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
    run_id: str | None = typer.Argument(None, help="Run ID (default: most recent)"),
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


@evolve_app.command("report")
def report_cmd(
    run_id: str | None = typer.Argument(None, help="Run ID (default: most recent)"),
) -> None:
    """Show a detailed evolution experiment report.

    Renders fitness trends, genome distribution, lineage of top performer,
    monoculture warnings, and experiment summary.

    Examples:
        ktrdr evolve report

        ktrdr evolve report run_20260101_120000
    """
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table

    from ktrdr.evolution.fitness import MINIMUM_FITNESS
    from ktrdr.evolution.report import (
        compute_genome_diversity,
        compute_trait_convergence,
        trace_lineage,
    )
    from ktrdr.evolution.tracker import EvolutionTracker

    console = Console()
    evo_dir = _get_evolution_dir()

    if not evo_dir.exists():
        console.print("[yellow]No evolution runs found.[/yellow]")
        return

    if run_id is None:
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

    summary = tracker.load_summary()
    gen_stats = summary.get("generations", [])

    # --- Run Summary ---
    console.print(
        Panel(
            f"[bold]{run_id}[/bold]\n"
            f"Population: {config.population_size}  |  "
            f"Generations: {config.generations}  |  "
            f"Symbol: {config.symbol}  |  "
            f"Timeframe: {config.timeframe}\n"
            f"Kill rate: {config.kill_rate}  |  "
            f"Model: {config.model}  |  "
            f"Seed: {config.seed or 'random'}",
            title="Run Summary",
        )
    )

    if not gen_stats:
        console.print("[yellow]No generation data available.[/yellow]")
        return

    # --- Fitness Trend ---
    ft_table = Table(title="Fitness Trend")
    ft_table.add_column("Gen", justify="right", style="cyan")
    ft_table.add_column("Pop", justify="right")
    ft_table.add_column("OK", justify="right", style="green")
    ft_table.add_column("Failed", justify="right", style="red")
    ft_table.add_column("Mean", justify="right")
    ft_table.add_column("Max", justify="right", style="bold")
    ft_table.add_column("Min", justify="right")

    for gs in gen_stats:
        mean_f = gs.get("mean_fitness", 0.0)
        max_f = gs.get("max_fitness", MINIMUM_FITNESS)
        min_f = gs.get("min_fitness", MINIMUM_FITNESS)
        ft_table.add_row(
            str(gs["generation"]),
            str(gs["population_size"]),
            str(gs.get("successful", 0)),
            str(gs.get("failed", 0)),
            f"{mean_f:.4f}" if mean_f > MINIMUM_FITNESS else "N/A",
            f"{max_f:.4f}" if max_f > MINIMUM_FITNESS else "N/A",
            f"{min_f:.4f}" if min_f > MINIMUM_FITNESS else "N/A",
        )

    console.print(ft_table)

    # --- Genome Distribution (last generation) ---
    last_gen_num = gen_stats[-1]["generation"]
    last_population = tracker.load_population(last_gen_num)

    if last_population:
        convergence = compute_trait_convergence(last_population)
        gd_table = Table(title=f"Genome Distribution (Gen {last_gen_num})")
        gd_table.add_column("Trait", style="cyan")
        gd_table.add_column("Dominant", style="bold")
        gd_table.add_column("Fraction", justify="right")
        gd_table.add_column("Distribution")

        for trait_name, info in convergence.items():
            dist_str = ", ".join(
                f"{v}: {c}" for v, c in sorted(info["distribution"].items())
            )
            gd_table.add_row(
                trait_name,
                info["dominant_value"],
                f"{info['fraction']:.0%}",
                dist_str,
            )

        console.print(gd_table)

        # --- Diversity per generation ---
        diversity_table = Table(title="Diversity Across Generations")
        diversity_table.add_column("Gen", justify="right", style="cyan")
        diversity_table.add_column("Unique Genomes", justify="right")
        diversity_table.add_column("Diversity", justify="right")
        diversity_table.add_column("Warning", style="yellow")

        for gs in gen_stats:
            gen_num = gs["generation"]
            pop = tracker.load_population(gen_num)
            if pop:
                div_result = compute_genome_diversity(pop)
                warning_text = div_result.warning.message if div_result.warning else ""
                diversity_table.add_row(
                    str(gen_num),
                    f"{div_result.unique_genomes}/{div_result.population_size}",
                    f"{div_result.diversity:.2f}",
                    warning_text,
                )

        console.print(diversity_table)

    # --- Lineage of top performer ---
    last_results = tracker.load_results(last_gen_num)
    if last_results:
        # Find best researcher
        best = max(last_results, key=lambda r: r.get("fitness", MINIMUM_FITNESS))
        best_id = best.get("researcher_id", "")
        best_fitness = best.get("fitness", MINIMUM_FITNESS)

        if best_id and best_fitness > MINIMUM_FITNESS:
            lineage = trace_lineage(tracker, best_id, last_gen_num)
            if lineage:
                lineage_lines = [
                    f"[bold]Best performer:[/bold] {best_id} "
                    f"(fitness: {best_fitness:.4f})"
                ]
                for entry in lineage:
                    genome = entry["genome"]
                    genome_str = "/".join(genome.values())
                    mutation_str = (
                        f" [{entry['mutation']}]" if entry["mutation"] else ""
                    )
                    fit_str = (
                        f" → fitness: {entry['fitness']:.4f}"
                        if entry["fitness"] is not None
                        else ""
                    )
                    lineage_lines.append(
                        f"  Gen {entry['generation']}: {entry['researcher_id']} "
                        f"({genome_str}){mutation_str}{fit_str}"
                    )
                console.print(Panel("\n".join(lineage_lines), title="Lineage"))

    # --- Experiment summary ---
    completed = len(gen_stats)
    total_experiments = sum(gs.get("population_size", 0) for gs in gen_stats)
    if completed >= config.generations:
        status_str = f"[green]Complete[/green]: {completed}/{config.generations}"
    else:
        status_str = f"[yellow]In progress[/yellow]: {completed}/{config.generations}"

    console.print(
        f"\n{status_str} generations | " f"{total_experiments} total experiments"
    )
