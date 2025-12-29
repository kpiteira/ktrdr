#!/usr/bin/env python3
"""Bootstrap memory from v1.5 experiment results.

This script seeds the memory system with v1.5 experiment data:
1. Parses strategy YAML files for experiment context
2. Parses RESULTS.md for test accuracy metrics
3. Creates experiment records in memory/experiments/
4. (Task 1.4 will add initial hypotheses)

Usage:
    uv run python scripts/bootstrap_v15_memory.py

The script is idempotent - re-running clears and recreates v1.5 experiment records.
"""

import re
from pathlib import Path

import yaml

from ktrdr.agents.memory import (
    EXPERIMENTS_DIR,
    ExperimentRecord,
    save_experiment,
)


def parse_v15_results() -> dict[str, dict]:
    """Parse results table from RESULTS.md.

    Extracts test accuracy and validation accuracy from the detailed results table.
    The table format is:
        | Rank | Strategy | Test Acc | Val Acc | Gap | Signal |

    Returns:
        Dict mapping strategy name to results dict with test_accuracy, val_accuracy,
        val_test_gap, and signal classification.
    """
    results_file = Path("docs/agentic/v1.5/RESULTS.md")
    content = results_file.read_text()

    results = {}

    # Parse the detailed results table
    # Format: | Rank | Strategy | Test Acc | Val Acc | Gap | Signal |
    # Example: | 1 | **v15_rsi_zigzag_1_5** | **64.2%** | 65.4% | +1.2pp | Strong |
    # Note: Signal column may have bold formatting like **Overfit**
    pattern = r"\|\s*\d+\s*\|\s*\*?\*?(v15_[\w_]+)\*?\*?\s*\|\s*\*?\*?(\d+\.\d+)%\*?\*?\s*\|\s*(\d+\.\d+)%\s*\|\s*\+?(\d+\.\d+)pp\s*\|\s*\*?\*?(\w+)\*?\*?\s*\|"

    for match in re.finditer(pattern, content):
        strategy = match.group(1)
        test_acc = float(match.group(2)) / 100
        val_acc = float(match.group(3)) / 100
        gap = float(match.group(4)) / 100
        signal = match.group(5).lower()

        results[strategy] = {
            "test_accuracy": test_acc,
            "val_accuracy": val_acc,
            "val_test_gap": gap,
            "signal": signal,
        }

    return results


def parse_strategy_file(path: Path) -> dict:
    """Extract context from strategy YAML file.

    Args:
        path: Path to strategy YAML file

    Returns:
        Context dict with indicators, composition, timeframe, symbol, zigzag_threshold,
        nn_architecture, training_epochs, and data_range.
    """
    config = yaml.safe_load(path.read_text())

    # Extract indicator names
    indicators = [ind["name"].upper() for ind in config.get("indicators", [])]

    # Determine composition type
    n_indicators = len(indicators)
    if n_indicators == 1:
        composition = "solo"
    elif n_indicators == 2:
        composition = "pair"
    else:
        composition = "trio"

    # Extract zigzag threshold
    zigzag = config.get("training", {}).get("labels", {}).get("zigzag_threshold", 0.02)

    # Extract timeframe
    timeframes = config.get("training_data", {}).get("timeframes", {})
    timeframe = timeframes.get("list", ["1h"])[0] if timeframes else "1h"

    # Extract symbol
    symbols = config.get("training_data", {}).get("symbols", {})
    symbol = symbols.get("list", ["EURUSD"])[0] if symbols else "EURUSD"

    # Extract NN architecture
    architecture = config.get("model", {}).get("architecture", {})
    hidden_layers = architecture.get("hidden_layers", [64, 32])

    # Extract training params
    training_config = config.get("model", {}).get("training", {})
    epochs = training_config.get("epochs", 100)

    # Extract date range
    date_range_config = config.get("training", {}).get("date_range", {})
    start_date = date_range_config.get("start", "2015-01-01")
    end_date = date_range_config.get("end", "2023-12-31")

    return {
        "indicators": indicators,
        "composition": composition,
        "timeframe": timeframe,
        "symbol": symbol,
        "zigzag_threshold": zigzag,
        "nn_architecture": hidden_layers,
        "training_epochs": epochs,
        "data_range": f"{start_date} to {end_date}",
    }


def determine_verdict(test_acc: float, val_test_gap: float) -> str:
    """Determine verdict from test accuracy and val-test gap.

    Args:
        test_acc: Test accuracy (0-1)
        val_test_gap: Gap between validation and test accuracy

    Returns:
        Verdict string: "strong_signal", "weak_signal", "overfit", or "no_signal"
    """
    # Check for overfitting first (large gap with low test accuracy)
    if val_test_gap > 0.10:  # Gap > 10pp suggests overfitting
        return "overfit"

    if test_acc >= 0.60:
        return "strong_signal"
    elif test_acc >= 0.55:
        return "weak_signal"
    else:
        return "no_signal"


def generate_observations(
    context: dict,
    test_acc: float,
    val_acc: float,
    gap: float,
    verdict: str,
) -> list[str]:
    """Generate contextual observations for an experiment.

    Args:
        context: Experiment context dict
        test_acc: Test accuracy
        val_acc: Validation accuracy
        gap: Validation-test gap
        verdict: Verdict string

    Returns:
        List of observation strings
    """
    observations = []
    indicators_str = " + ".join(context["indicators"])
    composition = context["composition"]
    timeframe = context["timeframe"]
    zigzag = context["zigzag_threshold"]

    # Main result observation
    observations.append(
        f"{indicators_str} ({composition}) achieves {test_acc:.1%} test accuracy "
        f"on {timeframe} {context['symbol']}"
    )

    # Gap observation
    if gap < 0.03:
        observations.append(
            f"Small val-test gap ({gap:.1%}) indicates good generalization"
        )
    elif gap > 0.10:
        observations.append(
            f"Large val-test gap ({gap:.1%}) indicates potential overfitting"
        )

    # Zigzag-specific observations
    if zigzag == 0.015:
        observations.append("Zigzag 1.5% threshold used (more labels)")
    elif zigzag >= 0.035:
        observations.append("Zigzag 3.5% threshold may cause overfitting on 1h data")

    # Verdict-specific
    if verdict == "no_signal":
        observations.append("No predictive signal detected in this configuration")
    elif verdict == "overfit":
        observations.append(
            "High validation accuracy did not generalize to test data"
        )

    return observations


def clear_v15_experiments():
    """Remove existing v1.5 experiment records."""
    if EXPERIMENTS_DIR.exists():
        for f in EXPERIMENTS_DIR.glob("exp_v15_*.yaml"):
            f.unlink()
            print(f"Removed: {f.name}")


def main():
    """Bootstrap memory from v1.5 experiment results."""
    print("=" * 60)
    print("v1.5 Memory Bootstrap")
    print("=" * 60)

    # Clear existing v1.5 data for idempotency
    print("\n1. Clearing existing v1.5 experiments...")
    clear_v15_experiments()

    # Parse results
    print("\n2. Parsing v1.5 results...")
    results = parse_v15_results()
    print(f"   Found {len(results)} strategies with test metrics")

    # Process each strategy
    print("\n3. Creating experiment records...")
    created_count = 0

    for strategy_file in sorted(Path("strategies").glob("v15_*.yaml")):
        strategy_name = strategy_file.stem

        # Skip strategies without test metrics
        if strategy_name not in results:
            print(f"   SKIP: {strategy_name} (no test metrics)")
            continue

        # Parse strategy file for context
        context = parse_strategy_file(strategy_file)

        # Get results
        res = results[strategy_name]
        test_acc = res["test_accuracy"]
        val_acc = res["val_accuracy"]
        gap = res["val_test_gap"]

        # Determine verdict
        verdict = determine_verdict(test_acc, gap)

        # Generate observations
        observations = generate_observations(context, test_acc, val_acc, gap, verdict)

        # Create experiment record
        record = ExperimentRecord(
            id=f"exp_{strategy_name}",
            timestamp="2025-12-27T00:00:00Z",  # v1.5 experiment date
            strategy_name=strategy_name,
            context=context,
            results={
                "test_accuracy": test_acc,
                "val_accuracy": val_acc,
                "val_test_gap": gap,
            },
            assessment={
                "verdict": verdict,
                "observations": observations,
                "hypotheses": [],  # Will be added in Task 1.4
                "limitations": [
                    f"Only tested on {context['timeframe']} {context['symbol']}",
                    f"Only tested in {context['composition']} configuration",
                ],
                "capability_requests": [],
            },
            source="v1.5_bootstrap",
        )

        # Save
        save_experiment(record)
        print(f"   Created: {record.id} (test: {test_acc:.1%}, verdict: {verdict})")
        created_count += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"Bootstrap complete: {created_count} experiment records created")
    print(f"Location: {EXPERIMENTS_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
