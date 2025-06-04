"""Strategy configuration commands for the main CLI."""

import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table

from ktrdr.config.strategy_validator import StrategyValidator

# Rich console for formatted output
console = Console()


def validate_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Validate a trading strategy configuration.
    
    Checks if a strategy YAML file has all required sections and valid configuration
    for neuro-fuzzy training.
    """
    validator = StrategyValidator()
    
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)
    
    console.print(f"🔍 Validating strategy: [blue]{strategy_path}[/blue]")
    console.print("=" * 60)
    
    result = validator.validate_strategy(str(strategy_path))
    
    # Print validation results
    if result.is_valid:
        console.print("[green]✅ Strategy configuration is valid![/green]")
    else:
        console.print("[red]❌ Strategy configuration has issues:[/red]")
    
    if result.errors:
        console.print(f"\n[red]🚨 Errors ({len(result.errors)}):[/red]")
        for i, error in enumerate(result.errors, 1):
            console.print(f"  {i}. {error}")
    
    if result.warnings:
        console.print(f"\n[yellow]⚠️  Warnings ({len(result.warnings)}):[/yellow]")
        for i, warning in enumerate(result.warnings, 1):
            console.print(f"  {i}. {warning}")
    
    if result.missing_sections:
        console.print(f"\n[blue]📋 Missing sections ({len(result.missing_sections)}):[/blue]")
        for i, section in enumerate(result.missing_sections, 1):
            console.print(f"  {i}. {section}")
    
    if result.suggestions:
        console.print(f"\n[cyan]💡 Suggestions ({len(result.suggestions)}):[/cyan]")
        for i, suggestion in enumerate(result.suggestions, 1):
            console.print(f"  {i}. {suggestion}")
    
    console.print("\n" + "=" * 60)
    
    if not result.is_valid:
        console.print("[red]❌ Validation failed.[/red]")
        if not quiet:
            console.print("[yellow]💡 Run 'ktrdr strategy-upgrade' to automatically fix issues[/yellow]")
        raise typer.Exit(1)
    else:
        console.print("[green]✅ Strategy is ready for neuro-fuzzy training![/green]")


def upgrade_strategy(
    strategy: str = typer.Argument(..., help="Path to strategy YAML file"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output path for upgraded file"),
    inplace: bool = typer.Option(False, "--inplace", "-i", help="Upgrade in place (overwrites original)"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Minimal output"),
):
    """
    Upgrade a strategy to neuro-fuzzy format.
    
    Adds missing sections with sensible defaults to make old strategies compatible
    with the new neuro-fuzzy training system.
    """
    validator = StrategyValidator()
    
    strategy_path = Path(strategy)
    if not strategy_path.exists():
        console.print(f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]")
        raise typer.Exit(1)
    
    # Determine output path
    output_path = output
    if output_path is None:
        if inplace:
            output_path = str(strategy_path)
        else:
            # Default: add .upgraded before extension
            output_path = str(strategy_path.parent / f"{strategy_path.stem}.upgraded{strategy_path.suffix}")
    
    console.print(f"🔧 Upgrading strategy: [blue]{strategy_path}[/blue]")
    if not inplace:
        console.print(f"📁 Output path: [blue]{output_path}[/blue]")
    console.print("=" * 60)
    
    # First validate to show current issues
    if not quiet:
        console.print("📊 Current validation status:")
        result = validator.validate_strategy(str(strategy_path))
        
        if result.errors:
            console.print(f"  [red]🚨 {len(result.errors)} errors[/red]")
        if result.warnings:
            console.print(f"  [yellow]⚠️  {len(result.warnings)} warnings[/yellow]")
        if result.missing_sections:
            console.print(f"  [blue]📋 {len(result.missing_sections)} missing sections[/blue]")
        console.print()
    
    # Perform upgrade
    success, message = validator.upgrade_strategy(str(strategy_path), output_path)
    
    if success:
        console.print("[green]✅ Strategy upgrade completed![/green]")
        console.print(f"💾 {message}")
        
        if not quiet:
            # Validate upgraded file
            console.print("\n🔍 Validating upgraded strategy...")
            upgraded_result = validator.validate_strategy(output_path)
            
            if upgraded_result.is_valid:
                console.print("[green]✅ Upgraded strategy is valid![/green]")
            else:
                console.print("[yellow]⚠️  Upgraded strategy still has some issues:[/yellow]")
                for error in upgraded_result.errors[:3]:  # Show first 3 errors
                    console.print(f"  • {error}")
                if len(upgraded_result.errors) > 3:
                    console.print(f"  ... and {len(upgraded_result.errors) - 3} more")
        
        console.print("\n" + "=" * 60)
        console.print("[green]🚀 Your strategy is now ready for neuro-fuzzy training![/green]")
        console.print(f"[cyan]💡 Use: uv run python -m ktrdr.training.cli --strategy {output_path}[/cyan]")
        
    else:
        console.print(f"[red]❌ Upgrade failed: {message}[/red]")
        raise typer.Exit(1)


def list_strategies(
    directory: str = typer.Option("strategies", "--directory", "-d", help="Strategies directory"),
    validate: bool = typer.Option(False, "--validate", "-v", help="Validate each strategy"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed validation results"),
):
    """
    List all strategy files in a directory.
    
    Shows strategy names, descriptions, and optionally validates each one.
    """
    strategies_dir = Path(directory)
    
    if not strategies_dir.exists():
        console.print(f"[red]❌ Error: Strategies directory not found: {strategies_dir}[/red]")
        raise typer.Exit(1)
    
    console.print(f"📂 Strategies in [blue]{strategies_dir}[/blue]:")
    console.print("=" * 60)
    
    validator = StrategyValidator()
    strategy_files = list(strategies_dir.glob("*.yaml")) + list(strategies_dir.glob("*.yml"))
    
    if not strategy_files:
        console.print("[yellow]📭 No strategy files found (.yaml or .yml)[/yellow]")
        return
    
    # Create a table for better formatting
    table = Table(title=None, show_header=True, header_style="bold cyan")
    table.add_column("File", style="blue")
    table.add_column("Name", style="white")
    table.add_column("Status", style="green")
    if validate:
        table.add_column("Issues", style="yellow")
    
    for strategy_file in sorted(strategy_files):
        try:
            import yaml
            with open(strategy_file, 'r') as f:
                config = yaml.safe_load(f)
                name = config.get('name', 'Unknown')
                
                if validate:
                    result = validator.validate_strategy(str(strategy_file))
                    if result.is_valid:
                        status = "✅ Valid"
                        issues = ""
                    else:
                        status = "❌ Invalid"
                        issues = f"{len(result.errors)} errors, {len(result.warnings)} warnings"
                    table.add_row(strategy_file.name, name, status, issues)
                else:
                    table.add_row(strategy_file.name, name, "Not validated", "")
                    
        except Exception as e:
            table.add_row(strategy_file.name, "Error reading file", "❌ Error", str(e))
    
    console.print(table)
    
    if validate and verbose:
        console.print("\n[cyan]Detailed validation results:[/cyan]")
        console.print("=" * 60)
        
        for strategy_file in sorted(strategy_files):
            result = validator.validate_strategy(str(strategy_file))
            if not result.is_valid:
                console.print(f"\n📄 [blue]{strategy_file.name}[/blue]")
                if result.errors:
                    console.print(f"  [red]Errors:[/red]")
                    for error in result.errors[:3]:
                        console.print(f"    • {error}")
                    if len(result.errors) > 3:
                        console.print(f"    ... and {len(result.errors) - 3} more")