"""
ktrdr-autoresearch harness.

FIXED — do not modify. This file defines the experiment boundaries:
  - Training window (agent trains on this)
  - Validation window (metric is measured here; agent optimizes against this)
  - Test window (NEVER used during the loop; held for final manual review)
  - The single metric: Sharpe ratio on the validation window

The agent modifies strategy.yaml (strategies/autoresearch.yaml) only.

Prerequisites:
  - ktrdr backend + training worker + backtest worker must be running
  - Use `uv run kinfra sandbox up` or the main stack before running
  - Historical data for the strategy's symbols must be available locally

Usage:
  cd <ktrdr-root>
  python autoresearch/harness.py
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Fixed experiment parameters — do not change during a run
# ---------------------------------------------------------------------------

STRATEGY_NAME = "autoresearch"          # Resolves to strategies/autoresearch.yaml

TRAIN_START = "2020-01-01"
TRAIN_END   = "2023-12-31"

VAL_START   = "2024-01-01"
VAL_END     = "2024-12-31"

# TEST_START = "2025-01-01"  # LOCKED — never used in the autoresearch loop

MAX_TRAIN_SECONDS = 1800   # 30 min hard cap
MAX_BACKTEST_SECONDS = 300  # 5 min hard cap

VALIDATION_SPLIT = "0.2"
COMMISSION = "0.001"   # 0.1% — realistic for CFDs/forex
SLIPPAGE   = "0.0005"  # 0.05%

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_ktrdr(args: list[str], timeout: int, label: str) -> dict:
    """
    Run a ktrdr CLI command with --json flag, return parsed JSON result.
    Raises RuntimeError on non-zero exit or unparseable output.
    """
    cmd = ["uv", "run", "ktrdr", "--json"] + args
    print(f"[harness] {label}: {' '.join(cmd)}", flush=True)
    t0 = time.time()

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"{label} timed out after {timeout}s")

    elapsed = time.time() - t0
    print(f"[harness] {label} completed in {elapsed:.1f}s (exit={result.returncode})", flush=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit {result.returncode}):\n"
            f"STDOUT: {result.stdout[-2000:]}\n"
            f"STDERR: {result.stderr[-2000:]}"
        )

    # Parse JSON output
    # ktrdr --json outputs: {"operation_type": "...", "results": {...}}
    stdout = result.stdout.strip()
    if not stdout:
        raise RuntimeError(
            f"{label} produced no output. "
            f"STDERR: {result.stderr[-1000:]}"
        )

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{label} output is not valid JSON: {e}\n"
            f"Raw output: {stdout[:2000]}"
        )


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------

def run_experiment() -> float:
    """
    Full experiment pipeline:
      1. Train on TRAIN_START → TRAIN_END
      2. Backtest on VAL_START → VAL_END with the trained model
      3. Return Sharpe ratio (higher = better)

    Raises RuntimeError on any failure (crash, timeout, bad output).
    """
    # --- Train ---
    train_result = run_ktrdr(
        [
            "train", STRATEGY_NAME,
            "--start", TRAIN_START,
            "--end", TRAIN_END,
            "--validation-split", VALIDATION_SPLIT,
            "--follow",
        ],
        timeout=MAX_TRAIN_SECONDS,
        label="train",
    )

    results = train_result.get("results", {})
    model_path = results.get("model_path")
    if not model_path:
        raise RuntimeError(
            f"Training completed but no model_path in results. "
            f"Got: {json.dumps(results, indent=2)}"
        )

    print(f"[harness] Model: {model_path}", flush=True)

    # --- Backtest on validation window ---
    backtest_result = run_ktrdr(
        [
            "backtest", STRATEGY_NAME,
            "--start", VAL_START,
            "--end", VAL_END,
            "--model-path", model_path,
            "--commission", COMMISSION,
            "--slippage", SLIPPAGE,
            "--follow",
        ],
        timeout=MAX_BACKTEST_SECONDS,
        label="backtest(val)",
    )

    bt_results = backtest_result.get("results", {})
    sharpe = bt_results.get("sharpe_ratio")

    if sharpe is None:
        raise RuntimeError(
            f"Backtest completed but no sharpe_ratio in results. "
            f"Got: {json.dumps(bt_results, indent=2)}"
        )

    return float(sharpe)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(f"[harness] ktrdr-autoresearch", flush=True)
    print(f"[harness] Strategy: {STRATEGY_NAME}", flush=True)
    print(f"[harness] Train:    {TRAIN_START} → {TRAIN_END}", flush=True)
    print(f"[harness] Val:      {VAL_START} → {VAL_END}", flush=True)
    print(flush=True)

    try:
        sharpe = run_experiment()
        print(flush=True)
        print("---")
        print(f"val_sharpe: {sharpe:.6f}")
        sys.exit(0)

    except subprocess.TimeoutExpired:
        print("\n[harness] TIMEOUT — exceeded time budget", file=sys.stderr)
        sys.exit(2)

    except RuntimeError as e:
        print(f"\n[harness] CRASH — {e}", file=sys.stderr)
        sys.exit(1)
