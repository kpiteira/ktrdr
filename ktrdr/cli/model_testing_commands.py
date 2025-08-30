"""Model testing commands for debugging trained models."""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.data.data_manager import DataManager
from ktrdr.decision.orchestrator import DecisionOrchestrator

# Rich console for formatted output
console = Console()


def test_model_signals(
    strategy: str,
    symbol: str,
    timeframe: str,
    model: Optional[str] = None,
    samples: int = 10,
    data_mode: str = "local",
):
    """
    Test a trained model on recent data to see what signals it generates.

    This helps debug why backtests might show no trades by showing:
    - What signals the model generates on recent data
    - Confidence levels of decisions
    - Fuzzy membership values
    - Any errors in the decision pipeline
    """
    try:
        # Validate arguments
        strategy_path = Path(strategy)
        if not strategy_path.exists():
            console.print(
                f"[red]❌ Error: Strategy file not found: {strategy_path}[/red]"
            )
            raise typer.Exit(1)

        if model and not Path(model).exists():
            console.print(f"[red]❌ Error: Model path not found: {model}[/red]")
            raise typer.Exit(1)

        console.print("[cyan]🧪 KTRDR Model Testing[/cyan]")
        console.print("=" * 50)

        # Load data
        console.print(f"📊 Loading recent data for {symbol} {timeframe}...")
        data_manager = DataManager()
        data = data_manager.load_data(symbol, timeframe, mode=data_mode)

        if data is None or len(data) < samples:
            console.print(
                f"[red]❌ Error: Insufficient data. Need at least {samples} bars, got {len(data) if data is not None else 0}[/red]"
            )
            raise typer.Exit(1)

        # Get recent data
        recent_data = data.tail(samples + 50)  # Extra data for indicator calculation
        test_data = recent_data.tail(samples)  # Last N bars to test

        console.print(
            f"✅ Loaded {len(data)} total bars, testing on last {samples} bars"
        )
        console.print(f"📅 Test period: {test_data.index[0]} to {test_data.index[-1]}")

        # Initialize orchestrator
        console.print("🤖 Initializing decision orchestrator...")
        try:
            orchestrator = DecisionOrchestrator(
                strategy_config_path=str(strategy_path),
                model_path=model,
                mode="backtest",
            )
            console.print(f"✅ Strategy: {orchestrator.strategy_name}")
        except Exception as e:
            console.print(f"[red]❌ Error initializing orchestrator: {str(e)}[/red]")
            raise typer.Exit(1) from e

        # Test each data point
        console.print("\n🔍 Testing model decisions on recent data:")

        # Create results table
        table = Table(title=f"Model Signals - {symbol} {timeframe}")
        table.add_column("Date", style="cyan", width=12)
        table.add_column("Price", style="green", width=8)
        table.add_column("Signal", style="yellow", width=8)
        table.add_column("Confidence", style="magenta", width=10)
        table.add_column("Reasoning", style="white", width=30)

        decisions = []
        portfolio_state = {"total_value": 100000, "available_capital": 100000}

        for i in range(len(test_data)):
            current_bar = test_data.iloc[i]
            historical_data = recent_data.iloc[
                : len(recent_data) - len(test_data) + i + 1
            ]

            try:
                decision = orchestrator.make_decision(
                    symbol=symbol,
                    timeframe=timeframe,
                    current_bar=current_bar,
                    historical_data=historical_data,
                    portfolio_state=portfolio_state,
                )

                decisions.append(decision)

                # Format reasoning for display
                reasoning_text = ""
                if hasattr(decision, "reasoning") and decision.reasoning:
                    if "orchestrator_override" in decision.reasoning:
                        reasoning_text = decision.reasoning["orchestrator_override"]
                    elif "prediction" in decision.reasoning:
                        pred = decision.reasoning["prediction"]
                        reasoning_text = f"Pred: {pred:.3f}"

                # Color code signals
                signal_color = "white"
                if decision.signal.value == "BUY":
                    signal_color = "green"
                elif decision.signal.value == "SELL":
                    signal_color = "red"

                table.add_row(
                    current_bar.name.strftime("%Y-%m-%d"),
                    f"${current_bar['close']:.2f}",
                    f"[{signal_color}]{decision.signal.value}[/{signal_color}]",
                    f"{decision.confidence:.3f}",
                    reasoning_text[:30],
                )

            except Exception as e:
                console.print(
                    f"[red]❌ Error processing {current_bar.name}: {str(e)}[/red]"
                )
                decisions.append(None)

        console.print(table)

        # Summary statistics
        valid_decisions = [d for d in decisions if d is not None]
        if valid_decisions:
            hold_count = sum(1 for d in valid_decisions if d.signal.value == "HOLD")
            buy_count = sum(1 for d in valid_decisions if d.signal.value == "BUY")
            sell_count = sum(1 for d in valid_decisions if d.signal.value == "SELL")
            avg_confidence = sum(d.confidence for d in valid_decisions) / len(
                valid_decisions
            )

            console.print("\n📊 Summary Statistics:")
            console.print(f"   Total decisions: {len(valid_decisions)}")
            console.print(
                f"   HOLD signals: {hold_count} ({hold_count/len(valid_decisions)*100:.1f}%)"
            )
            console.print(
                f"   BUY signals: {buy_count} ({buy_count/len(valid_decisions)*100:.1f}%)"
            )
            console.print(
                f"   SELL signals: {sell_count} ({sell_count/len(valid_decisions)*100:.1f}%)"
            )
            console.print(f"   Average confidence: {avg_confidence:.3f}")

            if buy_count == 0 and sell_count == 0:
                console.print("\n⚠️  [yellow]No trading signals generated![/yellow]")
                console.print("💡 This explains why backtests show 0 trades.")
                console.print("🔧 Consider:")
                console.print("   • Lowering confidence thresholds")
                console.print("   • Retraining with different parameters")
                console.print("   • Adjusting fuzzy membership functions")
            else:
                console.print("\n✅ [green]Model is generating trading signals[/green]")

        # Check for specific issues
        if orchestrator.model is None:
            console.print("\n⚠️  [yellow]Warning: No model loaded![/yellow]")
            console.print(f"   • Model path: {model if model else 'auto-detect'}")
            console.print(f"   • Check if model exists for {symbol} {timeframe}")

    except Exception as e:
        console.print(f"[red]❌ Model test failed: {str(e)}[/red]")
        import traceback

        console.print(traceback.format_exc())
        raise typer.Exit(1) from e
