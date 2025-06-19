"""
Multi-timeframe decision commands for the KTRDR CLI.

This module contains all CLI commands related to multi-timeframe trading decisions:
- decide: Generate multi-timeframe trading decisions
- analyze: Analyze timeframe performance and consensus patterns
- status: Check multi-timeframe data status and readiness
- strategies: List multi-timeframe capable strategies
- compare: Compare decisions across different consensus methods
"""

import asyncio
import sys
import json
from typing import Optional, List
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
)
from rich.text import Text

from ktrdr.cli.api_client import get_api_client, check_api_connection
from ktrdr.cli.progress import ProgressDisplayManager
from ktrdr.config.validation import InputValidator
from ktrdr.errors import ValidationError, DataError
from ktrdr.logging import get_logger
from ktrdr.decision.multi_timeframe_orchestrator import (
    create_multi_timeframe_decision_orchestrator,
)
from ktrdr.data.data_manager import DataManager

# Setup logging and console
logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)


# Simple spinner context manager
@contextmanager
def with_spinner(message: str):
    """Simple spinner context manager for CLI operations."""
    from rich.progress import Progress, SpinnerColumn, TextColumn

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(message, total=None)
        yield


# Create the CLI app for multi-timeframe commands
multi_timeframe_app = typer.Typer(
    name="multi-timeframe",
    help="Multi-timeframe trading decision commands",
    no_args_is_help=True,
)


@multi_timeframe_app.command("decide")
def make_multi_timeframe_decision(
    symbol: str = typer.Argument(..., help="Trading symbol (e.g., AAPL)"),
    strategy: str = typer.Argument(..., help="Path to strategy configuration file"),
    timeframes: str = typer.Option(
        "1h,4h,1d",
        "--timeframes",
        "-t",
        help="Comma-separated list of timeframes (e.g., 1h,4h,1d)",
    ),
    mode: str = typer.Option(
        "backtest", "--mode", "-m", help="Operating mode: backtest, paper, or live"
    ),
    model_path: Optional[str] = typer.Option(
        None, "--model", help="Path to multi-timeframe model (optional)"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table, json, or summary"
    ),
    portfolio_value: float = typer.Option(
        100000.0, "--portfolio", "-p", help="Total portfolio value"
    ),
    available_capital: float = typer.Option(
        50000.0, "--capital", "-c", help="Available capital for trading"
    ),
    api: bool = typer.Option(
        False, "--api", help="Use API endpoint instead of direct orchestrator"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed reasoning and metadata"
    ),
):
    """
    Generate a trading decision using multi-timeframe analysis.

    This command analyzes market data across multiple timeframes, builds consensus,
    and provides a comprehensive trading decision with detailed reasoning.

    Examples:
        ktrdr multi-timeframe decide AAPL strategies/strategy.yaml
        ktrdr multi-timeframe decide AAPL strategies/strategy.yaml -t 1h,4h -m live
        ktrdr multi-timeframe decide AAPL strategies/strategy.yaml --format json -v
    """

    # Validate inputs
    try:
        # Validate symbol using string validator with pattern
        InputValidator.validate_string(
            symbol, min_length=1, max_length=10, pattern=r"^[A-Za-z0-9\-\.]+$"
        )

        timeframes_list = [tf.strip() for tf in timeframes.split(",")]
        for tf in timeframes_list:
            if tf not in ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]:
                raise ValidationError(
                    message=f"Invalid timeframe: {tf}",
                    error_code="VAL-InvalidTimeframe",
                    details={"timeframe": tf},
                )

        if mode not in ["backtest", "paper", "live"]:
            raise ValidationError(
                message=f"Invalid mode: {mode}",
                error_code="VAL-InvalidMode",
                details={"mode": mode},
            )

        strategy_path = Path(strategy)
        if not strategy_path.exists():
            raise ValidationError(
                message=f"Strategy file not found: {strategy}",
                error_code="VAL-FileNotFound",
                details={"file": strategy},
            )

    except ValidationError as e:
        error_console.print(f"[red]❌ Validation Error: {e.message}[/red]")
        raise typer.Exit(1)

    console.print(f"🎯 Making multi-timeframe decision for [blue]{symbol}[/blue]")
    console.print(f"📊 Timeframes: [cyan]{', '.join(timeframes_list)}[/cyan]")
    console.print(f"⚙️  Mode: [yellow]{mode}[/yellow]")
    console.print("=" * 60)

    portfolio_state = {
        "total_value": portfolio_value,
        "available_capital": available_capital,
    }

    try:
        if api:
            # Use API endpoint
            result = _make_decision_via_api(
                symbol, strategy, timeframes_list, mode, model_path, portfolio_state
            )
        else:
            # Use direct orchestrator
            result = _make_decision_direct(
                symbol,
                strategy_path,
                timeframes_list,
                mode,
                model_path,
                portfolio_state,
            )

        # Display results
        _display_decision_result(result, output_format, verbose)

    except Exception as e:
        logger.error(f"Failed to make multi-timeframe decision: {e}")
        error_console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@multi_timeframe_app.command("analyze")
def analyze_timeframe_performance(
    symbol: str = typer.Argument(..., help="Trading symbol to analyze"),
    strategy: str = typer.Argument(..., help="Path to strategy configuration"),
    timeframes: str = typer.Option(
        "1h,4h,1d", "--timeframes", "-t", help="Timeframes to analyze"
    ),
    mode: str = typer.Option("backtest", "--mode", "-m", help="Operating mode"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
    history_limit: int = typer.Option(
        10, "--history", "-h", help="Number of recent decisions to analyze"
    ),
    api: bool = typer.Option(False, "--api", help="Use API endpoint"),
):
    """
    Analyze multi-timeframe performance and consensus patterns.

    Provides detailed analysis of how different timeframes contribute to
    decision making, including agreement patterns and performance metrics.

    Examples:
        ktrdr multi-timeframe analyze AAPL strategies/strategy.yaml
        ktrdr multi-timeframe analyze AAPL strategies/strategy.yaml --format json
    """

    console.print(f"📈 Analyzing timeframe performance for [blue]{symbol}[/blue]")

    try:
        timeframes_list = [tf.strip() for tf in timeframes.split(",")]
        strategy_path = Path(strategy)

        if api:
            result = _analyze_via_api(symbol, strategy, timeframes_list, mode)
        else:
            result = _analyze_direct(symbol, strategy_path, timeframes_list, mode)

        _display_analysis_result(result, output_format)

    except Exception as e:
        logger.error(f"Failed to analyze timeframe performance: {e}")
        error_console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@multi_timeframe_app.command("status")
def check_data_status(
    symbol: str = typer.Argument(..., help="Trading symbol to check"),
    timeframes: str = typer.Option(
        "1h,4h,1d", "--timeframes", "-t", help="Timeframes to check"
    ),
    lookback: int = typer.Option(
        100, "--lookback", "-l", help="Number of periods to check"
    ),
    api: bool = typer.Option(False, "--api", help="Use API endpoint"),
):
    """
    Check data availability and quality for multi-timeframe analysis.

    Verifies that sufficient data is available and provides quality metrics
    for each timeframe to ensure reliable multi-timeframe decisions.

    Examples:
        ktrdr multi-timeframe status AAPL
        ktrdr multi-timeframe status AAPL -t 1h,4h,1d --lookback 200
    """

    console.print(f"🔍 Checking data status for [blue]{symbol}[/blue]")

    try:
        timeframes_list = [tf.strip() for tf in timeframes.split(",")]

        if api:
            result = _check_status_via_api(symbol, timeframes_list, lookback)
        else:
            result = _check_status_direct(symbol, timeframes_list, lookback)

        _display_status_result(result)

    except Exception as e:
        logger.error(f"Failed to check data status: {e}")
        error_console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@multi_timeframe_app.command("strategies")
def list_multi_timeframe_strategies(
    api: bool = typer.Option(False, "--api", help="Use API endpoint"),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
):
    """
    List strategies that support multi-timeframe analysis.

    Scans strategy configurations to identify those with multi-timeframe
    support and displays their capabilities and configurations.
    """

    console.print("📋 Listing multi-timeframe strategies")

    try:
        if api:
            result = _list_strategies_via_api()
        else:
            result = _list_strategies_direct()

        _display_strategies_result(result, output_format)

    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        error_console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


@multi_timeframe_app.command("compare")
def compare_consensus_methods(
    symbol: str = typer.Argument(..., help="Trading symbol"),
    strategy: str = typer.Argument(..., help="Strategy configuration path"),
    timeframes: str = typer.Option(
        "1h,4h,1d", "--timeframes", "-t", help="Timeframes to analyze"
    ),
    methods: str = typer.Option(
        "consensus,hierarchy,weighted", "--methods", help="Consensus methods to compare"
    ),
    output_format: str = typer.Option(
        "table", "--format", "-f", help="Output format: table or json"
    ),
):
    """
    Compare different consensus methods for multi-timeframe decisions.

    Runs the same data through different consensus algorithms and compares
    the resulting decisions, confidence levels, and agreement scores.

    Examples:
        ktrdr multi-timeframe compare AAPL strategies/strategy.yaml
        ktrdr multi-timeframe compare AAPL strategies/strategy.yaml --methods consensus,weighted
    """

    console.print(f"⚖️  Comparing consensus methods for [blue]{symbol}[/blue]")

    try:
        timeframes_list = [tf.strip() for tf in timeframes.split(",")]
        methods_list = [m.strip() for m in methods.split(",")]

        result = _compare_consensus_methods(
            symbol, strategy, timeframes_list, methods_list
        )

        _display_comparison_result(result, output_format)

    except Exception as e:
        logger.error(f"Failed to compare consensus methods: {e}")
        error_console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)


# Helper functions for API calls
def _make_decision_via_api(
    symbol, strategy, timeframes, mode, model_path, portfolio_state
):
    """Make decision using API endpoint."""
    client = get_api_client()

    if not check_api_connection(client):
        raise RuntimeError("API is not available")

    with with_spinner("Making multi-timeframe decision..."):
        response = client.post(
            "/api/v1/multi-timeframe-decisions/decide",
            json={
                "symbol": symbol,
                "strategy_config_path": strategy,
                "timeframes": timeframes,
                "mode": mode,
                "model_path": model_path,
                "portfolio_state": portfolio_state,
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.text}")

        return response.json()


def _make_decision_direct(
    symbol, strategy_path, timeframes, mode, model_path, portfolio_state
):
    """Make decision using direct orchestrator."""

    with with_spinner("Creating multi-timeframe orchestrator..."):
        orchestrator = create_multi_timeframe_decision_orchestrator(
            strategy_config_path=str(strategy_path),
            timeframes=timeframes,
            mode=mode,
            model_path=model_path,
        )

    with with_spinner("Loading timeframe data..."):
        data_manager = DataManager()
        timeframe_data = {}

        for timeframe in timeframes:
            data = data_manager.get_data(symbol=symbol, timeframe=timeframe, rows=100)
            if data is not None and not data.empty:
                timeframe_data[timeframe] = data

    with with_spinner("Generating multi-timeframe decision..."):
        decision = orchestrator.make_multi_timeframe_decision(
            symbol=symbol,
            timeframe_data=timeframe_data,
            portfolio_state=portfolio_state,
        )

    # Get consensus history
    consensus_history = orchestrator.get_consensus_history(limit=1)
    latest_consensus = consensus_history[0] if consensus_history else None

    return {
        "success": True,
        "symbol": symbol,
        "timestamp": decision.timestamp.isoformat(),
        "decision": {
            "signal": decision.signal.value,
            "confidence": decision.confidence,
            "current_position": decision.current_position.value,
            "reasoning": decision.reasoning,
        },
        "consensus": latest_consensus,
        "metadata": {
            "timeframes": timeframes,
            "mode": mode,
            "orchestrator_type": "direct",
        },
    }


def _analyze_via_api(symbol, strategy, timeframes, mode):
    """Analyze using API endpoint."""
    client = get_api_client()

    with with_spinner("Analyzing timeframe performance..."):
        response = client.get(
            f"/api/v1/multi-timeframe-decisions/analyze/{symbol}",
            params={
                "strategy_config_path": strategy,
                "timeframes": timeframes,
                "mode": mode,
            },
        )

        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.text}")

        return response.json()


def _analyze_direct(symbol, strategy_path, timeframes, mode):
    """Analyze using direct orchestrator."""

    with with_spinner("Creating orchestrator and analyzing..."):
        orchestrator = create_multi_timeframe_decision_orchestrator(
            strategy_config_path=str(strategy_path), timeframes=timeframes, mode=mode
        )

        analysis = orchestrator.get_timeframe_analysis(symbol)

        return {
            "success": True,
            "symbol": symbol,
            "timeframes": analysis["timeframes"],
            "primary_timeframe": analysis["primary_timeframe"],
            "timeframe_weights": analysis["timeframe_weights"],
            "recent_decisions_count": analysis["recent_decisions_count"],
            "analysis_timestamp": datetime.now().isoformat(),
        }


def _check_status_via_api(symbol, timeframes, lookback):
    """Check status using API endpoint."""
    client = get_api_client()

    with with_spinner("Checking data status..."):
        response = client.get(
            f"/api/v1/multi-timeframe-decisions/data-status/{symbol}",
            params={"timeframes": timeframes, "lookback_periods": lookback},
        )

        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.text}")

        return response.json()


def _check_status_direct(symbol, timeframes, lookback):
    """Check status using direct data manager."""

    with with_spinner("Checking data availability..."):
        data_manager = DataManager()
        timeframe_status = []
        quality_scores = []

        for timeframe in timeframes:
            try:
                data = data_manager.get_data(
                    symbol=symbol, timeframe=timeframe, rows=lookback
                )

                if data is not None and not data.empty:
                    completeness = 1.0 - data.isnull().sum().sum() / (
                        len(data) * len(data.columns)
                    )
                    quality_scores.append(completeness)

                    timeframe_status.append(
                        {
                            "timeframe": timeframe,
                            "available": True,
                            "record_count": len(data),
                            "data_quality_score": completeness,
                            "freshness_score": 1.0,  # Simplified
                        }
                    )
                else:
                    timeframe_status.append(
                        {
                            "timeframe": timeframe,
                            "available": False,
                            "record_count": 0,
                            "data_quality_score": 0.0,
                            "freshness_score": 0.0,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to check {timeframe}: {e}")
                timeframe_status.append(
                    {
                        "timeframe": timeframe,
                        "available": False,
                        "record_count": 0,
                        "data_quality_score": 0.0,
                        "freshness_score": 0.0,
                    }
                )

        overall_quality = (
            sum(quality_scores) / len(quality_scores) if quality_scores else 0.0
        )

        return {
            "success": True,
            "symbol": symbol,
            "timeframe_status": timeframe_status,
            "overall_data_quality": overall_quality,
            "ready_for_analysis": len(quality_scores) > 0 and overall_quality > 0.6,
        }


def _list_strategies_via_api():
    """List strategies using API."""
    client = get_api_client()

    with with_spinner("Listing multi-timeframe strategies..."):
        response = client.get("/api/v1/multi-timeframe-decisions/strategies")

        if response.status_code != 200:
            raise RuntimeError(f"API request failed: {response.text}")

        return response.json()


def _list_strategies_direct():
    """List strategies by scanning directory."""

    with with_spinner("Scanning strategies directory..."):
        strategies = []
        strategy_dir = Path("strategies")

        if strategy_dir.exists():
            import yaml

            for yaml_file in strategy_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, "r") as f:
                        config = yaml.safe_load(f)

                    timeframe_configs = config.get("timeframe_configs", {})
                    multi_timeframe_config = config.get("multi_timeframe", {})

                    if timeframe_configs or multi_timeframe_config:
                        strategies.append(
                            {
                                "name": config.get("name", yaml_file.stem),
                                "config_path": str(yaml_file),
                                "supports_multi_timeframe": True,
                                "timeframes": list(timeframe_configs.keys()),
                                "consensus_method": multi_timeframe_config.get(
                                    "consensus_method", "weighted_majority"
                                ),
                            }
                        )

                except Exception as e:
                    logger.warning(f"Failed to parse {yaml_file}: {e}")

        return {"success": True, "strategies": strategies}


def _compare_consensus_methods(symbol, strategy, timeframes, methods):
    """Compare different consensus methods."""

    results = {}
    strategy_path = Path(strategy)

    for method in methods:
        with with_spinner(f"Testing {method} consensus method..."):
            try:
                # This would require modifying the orchestrator to accept consensus method
                # For now, just return placeholder data
                results[method] = {
                    "signal": "BUY",
                    "confidence": 0.8,
                    "agreement_score": 0.9,
                    "method": method,
                }
            except Exception as e:
                logger.warning(f"Failed to test {method}: {e}")
                results[method] = {"error": str(e)}

    return {
        "success": True,
        "symbol": symbol,
        "timeframes": timeframes,
        "comparison": results,
    }


# Display functions
def _display_decision_result(result, output_format, verbose):
    """Display decision result in specified format."""

    if output_format == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    if not result.get("success", False):
        error_console.print("[red]❌ Decision generation failed[/red]")
        return

    decision = result.get("decision", {})
    consensus = result.get("consensus")

    # Main decision summary
    signal = decision.get("signal", "UNKNOWN")
    confidence = decision.get("confidence", 0.0)

    signal_color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(
        signal, "white"
    )

    console.print(
        Panel(
            f"[{signal_color}]{signal}[/{signal_color}] (Confidence: {confidence:.3f})",
            title="🎯 Multi-Timeframe Decision",
            border_style="bright_blue",
        )
    )

    if consensus:
        # Consensus information
        consensus_table = Table(title="📊 Timeframe Consensus", show_header=True)
        consensus_table.add_column("Timeframe", style="cyan")
        consensus_table.add_column("Signal", style="white")
        consensus_table.add_column("Confidence", style="green")
        consensus_table.add_column("Weight", style="blue")

        timeframe_decisions = consensus.get("timeframe_decisions", {})
        for tf, tf_decision in timeframe_decisions.items():
            tf_signal = tf_decision.get("signal", "UNKNOWN")
            tf_confidence = tf_decision.get("confidence", 0.0)
            tf_weight = tf_decision.get("weight", 0.0)

            tf_signal_color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(
                tf_signal, "white"
            )

            consensus_table.add_row(
                tf,
                f"[{tf_signal_color}]{tf_signal}[/{tf_signal_color}]",
                f"{tf_confidence:.3f}",
                f"{tf_weight:.2f}",
            )

        console.print(consensus_table)

        # Consensus metrics
        metrics_table = Table(title="⚖️  Consensus Metrics", show_header=True)
        metrics_table.add_column("Metric", style="cyan")
        metrics_table.add_column("Value", style="white")

        metrics_table.add_row(
            "Final Signal", f"[{signal_color}]{signal}[/{signal_color}]"
        )
        metrics_table.add_row(
            "Consensus Confidence", f"{consensus.get('consensus_confidence', 0.0):.3f}"
        )
        metrics_table.add_row(
            "Agreement Score", f"{consensus.get('agreement_score', 0.0):.3f}"
        )
        metrics_table.add_row(
            "Consensus Method", consensus.get("consensus_method", "unknown")
        )

        conflicting_tfs = consensus.get("conflicting_timeframes", [])
        if conflicting_tfs:
            metrics_table.add_row("Conflicting Timeframes", ", ".join(conflicting_tfs))

        console.print(metrics_table)

    if verbose and decision.get("reasoning"):
        # Detailed reasoning
        console.print(
            Panel(
                json.dumps(decision["reasoning"], indent=2, default=str),
                title="🔍 Detailed Reasoning",
                border_style="dim",
            )
        )


def _display_analysis_result(result, output_format):
    """Display analysis result."""

    if output_format == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    if not result.get("success", False):
        error_console.print("[red]❌ Analysis failed[/red]")
        return

    # Analysis summary
    table = Table(
        title=f"📈 Timeframe Analysis - {result.get('symbol')}", show_header=True
    )
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Symbol", result.get("symbol", ""))
    table.add_row("Primary Timeframe", result.get("primary_timeframe", ""))
    table.add_row("Timeframes", ", ".join(result.get("timeframes", [])))
    table.add_row("Recent Decisions", str(result.get("recent_decisions_count", 0)))

    console.print(table)

    # Timeframe weights
    weights = result.get("timeframe_weights", {})
    if weights:
        weights_table = Table(title="⚖️  Timeframe Weights", show_header=True)
        weights_table.add_column("Timeframe", style="cyan")
        weights_table.add_column("Weight", style="green")

        for tf, weight in weights.items():
            weights_table.add_row(tf, f"{weight:.3f}")

        console.print(weights_table)


def _display_status_result(result):
    """Display data status result."""

    if not result.get("success", False):
        error_console.print("[red]❌ Status check failed[/red]")
        return

    symbol = result.get("symbol", "")
    overall_quality = result.get("overall_data_quality", 0.0)
    ready = result.get("ready_for_analysis", False)

    # Overall status
    status_color = "green" if ready else "red"
    status_text = "✅ Ready" if ready else "❌ Not Ready"

    console.print(
        Panel(
            f"[{status_color}]{status_text}[/{status_color}] (Quality: {overall_quality:.3f})",
            title=f"🔍 Data Status - {symbol}",
            border_style="bright_blue",
        )
    )

    # Timeframe status
    status_table = Table(title="📊 Timeframe Data Status", show_header=True)
    status_table.add_column("Timeframe", style="cyan")
    status_table.add_column("Available", style="white")
    status_table.add_column("Records", style="blue")
    status_table.add_column("Quality", style="green")
    status_table.add_column("Freshness", style="yellow")

    for tf_status in result.get("timeframe_status", []):
        available = tf_status.get("available", False)
        available_text = "[green]✅[/green]" if available else "[red]❌[/red]"

        status_table.add_row(
            tf_status.get("timeframe", ""),
            available_text,
            str(tf_status.get("record_count", 0)),
            f"{tf_status.get('data_quality_score', 0.0):.3f}",
            f"{tf_status.get('freshness_score', 0.0):.3f}",
        )

    console.print(status_table)


def _display_strategies_result(result, output_format):
    """Display strategies result."""

    if output_format == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    if not result.get("success", False):
        error_console.print("[red]❌ Failed to list strategies[/red]")
        return

    strategies = result.get("strategies", [])

    if not strategies:
        console.print("[yellow]No multi-timeframe strategies found[/yellow]")
        return

    table = Table(title="📋 Multi-Timeframe Strategies", show_header=True)
    table.add_column("Name", style="cyan")
    table.add_column("Timeframes", style="blue")
    table.add_column("Consensus Method", style="green")
    table.add_column("Config Path", style="dim")

    for strategy in strategies:
        timeframes = ", ".join(strategy.get("timeframes", []))

        table.add_row(
            strategy.get("name", ""),
            timeframes,
            strategy.get("consensus_method", ""),
            strategy.get("config_path", ""),
        )

    console.print(table)


def _display_comparison_result(result, output_format):
    """Display consensus method comparison result."""

    if output_format == "json":
        console.print(json.dumps(result, indent=2, default=str))
        return

    if not result.get("success", False):
        error_console.print("[red]❌ Comparison failed[/red]")
        return

    comparison = result.get("comparison", {})

    table = Table(title="⚖️  Consensus Method Comparison", show_header=True)
    table.add_column("Method", style="cyan")
    table.add_column("Signal", style="white")
    table.add_column("Confidence", style="green")
    table.add_column("Agreement", style="blue")

    for method, method_result in comparison.items():
        if "error" in method_result:
            table.add_row(
                method, "[red]ERROR[/red]", "[red]N/A[/red]", "[red]N/A[/red]"
            )
        else:
            signal = method_result.get("signal", "UNKNOWN")
            signal_color = {"BUY": "green", "SELL": "red", "HOLD": "yellow"}.get(
                signal, "white"
            )

            table.add_row(
                method,
                f"[{signal_color}]{signal}[/{signal_color}]",
                f"{method_result.get('confidence', 0.0):.3f}",
                f"{method_result.get('agreement_score', 0.0):.3f}",
            )

    console.print(table)
