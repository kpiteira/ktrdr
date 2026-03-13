"""Run ensemble backtest inside container for M7 Task 7.6 evaluation.

Usage (inside container):
    python /app/scripts/run_ensemble_backtest.py
"""

import asyncio
import json
import sys

# Fix paths for container environment
sys.path.insert(0, "/app")


def run_ensemble():
    """Run the regime-routed ensemble backtest and print results."""
    from ktrdr.backtesting.engine import BacktestConfig
    from ktrdr.backtesting.ensemble_runner import EnsembleBacktestRunner
    from ktrdr.config.ensemble_config import EnsembleConfiguration

    # Build ensemble config programmatically (container paths)
    config_data = {
        "name": "regime_routed_v1",
        "description": "Regime-routed ensemble for M7 evaluation",
        "models": {
            "regime": {
                "model_path": "/app/models/regime_classifier_seed/1h_latest",
                "output_type": "regime_classification",
            },
            "trend_signal": {
                "model_path": "/app/models/mean_reversion_momentum_v1/1h_latest",
                "output_type": "classification",
            },
            "range_signal": {
                "model_path": "/app/models/bb_stochastic_mean_reversion_eurusd_1h_v1/1h_latest",
                "output_type": "classification",
            },
        },
        "composition": {
            "type": "regime_route",
            "gate_model": "regime",
            "regime_threshold": 0.4,
            "stability_bars": 3,
            "rules": {
                "trending_up": {"model": "trend_signal"},
                "trending_down": {"model": "trend_signal"},
                "ranging": {"model": "range_signal"},
                "volatile": {"action": "FLAT"},
            },
            "on_regime_transition": "close_and_switch",
        },
    }

    ensemble_config = EnsembleConfiguration.from_dict(config_data)
    print(f"Ensemble: {ensemble_config.name} ({len(ensemble_config.models)} models)")

    # Backtest config
    backtest_config = BacktestConfig(
        strategy_config_path="",
        model_path=None,
        symbol="EURUSD",
        timeframe="1h",
        start_date="2024-06-01",
        end_date="2024-09-01",
        initial_capital=100000.0,
    )

    # Run ensemble backtest
    runner = EnsembleBacktestRunner(
        ensemble_config=ensemble_config,
        backtest_config=backtest_config,
    )

    results = asyncio.run(runner.run())

    # Print results
    print("\n=== ENSEMBLE BACKTEST RESULTS ===")
    print(f"Symbol: {results.symbol}")
    print(f"Timeframe: {results.timeframe}")
    print(f"Total bars: {results.total_bars}")
    print(f"Total trades: {len(results.trades)}")
    print(f"Transitions: {results.transition_count}")
    print(f"Execution time: {results.execution_time_seconds:.1f}s")

    print("\n--- Per-Regime Breakdown ---")
    for regime, metrics in results.per_regime_metrics.items():
        print(f"  {regime}: {metrics['bars']} bars, {metrics['trades']} trades")

    print("\n--- Regime Transitions (first 10) ---")
    for t in results.regime_sequence[:10]:
        print(f"  {t['timestamp']}: {t['from']} -> {t['to']}")
    if len(results.regime_sequence) > 10:
        print(f"  ... and {len(results.regime_sequence) - 10} more")

    # Output JSON for comparison
    print("\n=== JSON OUTPUT ===")
    print(json.dumps(results.to_dict(), indent=2))

    return results


def run_baseline():
    """Run a single-model baseline backtest for comparison."""
    from ktrdr.backtesting.engine import BacktestConfig, BacktestEngine

    print("\n=== BASELINE BACKTEST (single model, no regime routing) ===")

    config = BacktestConfig(
        strategy_config_path="",
        model_path="/app/models/mean_reversion_momentum_v1/1h_latest",
        symbol="EURUSD",
        timeframe="1h",
        start_date="2024-06-01",
        end_date="2024-09-01",
        initial_capital=100000.0,
    )

    engine = BacktestEngine(config)
    results = asyncio.run(engine.run())

    print(f"Total bars: {results.total_bars}")
    print(f"Total trades: {results.total_trades}")
    print(f"Execution time: {results.execution_time_seconds:.1f}s")

    return results


if __name__ == "__main__":
    ensemble_results = run_ensemble()

    try:
        baseline_results = run_baseline()
        print("\n=== COMPARISON ===")
        print(f"Ensemble trades: {len(ensemble_results.trades)}")
        print(f"Baseline trades: {baseline_results.total_trades}")
        print(f"Ensemble transitions: {ensemble_results.transition_count}")
    except Exception as e:
        print(f"\nBaseline failed (non-critical): {e}")
        print("Ensemble results are still valid for evaluation.")
