"""Execution tools for squad squad_engine.

Wraps strategy validation and experiment execution as Python functions.
These call existing ktrdr infrastructure via subprocess — no LLM involved.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

from ktrdr import get_logger

logger = get_logger(__name__)

# Paths
_SQUAD_DIR = Path(__file__).resolve().parent.parent
_EXECUTOR_PATH = _SQUAD_DIR / "executor.sh"

# Default execution timeout: 2 hours (training can be long)
DEFAULT_TIMEOUT = 7200


@dataclass
class ValidationResult:
    """Result from strategy validation."""

    valid: bool
    error: str | None
    path: str | None = None


@dataclass
class ExperimentResult:
    """Result from experiment execution (training + backtest)."""

    status: str  # "SUCCESS" | "FAILED"
    training: dict | None = None
    backtest: dict | None = None
    error: str | None = None


async def _run_subprocess(
    cmd: list[str],
    timeout: int = DEFAULT_TIMEOUT,
    cwd: str | None = None,
) -> asyncio.subprocess.Process:
    """Run a subprocess and wait for completion."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=cwd,
    )
    proc.stdout, proc.stderr = await asyncio.wait_for(
        proc.communicate(), timeout=timeout
    )
    return proc


async def validate_strategy(name: str) -> ValidationResult:
    """Validate a strategy YAML via `uv run ktrdr validate`.

    Args:
        name: Strategy name (without .yaml extension).

    Returns:
        ValidationResult with valid=True on success, error message on failure.
    """
    cmd = ["uv", "run", "ktrdr", "validate", name]
    try:
        proc = await _run_subprocess(cmd, timeout=30)
        if proc.returncode == 0:
            return ValidationResult(valid=True, error=None)
        else:
            error = proc.stderr.decode().strip() if proc.stderr else "Unknown validation error"
            return ValidationResult(valid=False, error=error)
    except Exception as e:
        return ValidationResult(valid=False, error=str(e))


async def execute_experiment(
    strategy: str,
    train_start: str,
    train_end: str,
    bt_start: str,
    bt_end: str,
) -> ExperimentResult:
    """Execute training + backtest via executor.sh.

    Args:
        strategy: Strategy name.
        train_start: Training start date (YYYY-MM-DD).
        train_end: Training end date.
        bt_start: Backtest start date.
        bt_end: Backtest end date.

    Returns:
        ExperimentResult with training and backtest summaries.
    """
    strategy_path = Path.home() / ".ktrdr" / "shared" / "strategies" / f"{strategy}.yaml"
    cmd = [
        str(_EXECUTOR_PATH),
        str(strategy_path),
        train_start,
        train_end,
        bt_start,
        bt_end,
    ]

    try:
        proc = await _run_subprocess(cmd)
    except asyncio.TimeoutError:
        return ExperimentResult(
            status="FAILED",
            error=f"Timeout after {DEFAULT_TIMEOUT}s",
        )
    except Exception as e:
        return ExperimentResult(status="FAILED", error=str(e))

    stdout = proc.stdout.decode().strip() if proc.stdout else ""

    # Parse JSON output
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return ExperimentResult(
            status="FAILED",
            error=f"Failed to parse executor output as JSON: {stdout[:200]}",
        )

    # Check for executor-reported errors
    if "error" in data:
        return ExperimentResult(
            status="FAILED",
            error=data.get("detail", data.get("error", "Unknown error")),
            training=data.get("training"),
            backtest=data.get("backtest"),
        )

    if proc.returncode != 0:
        return ExperimentResult(
            status="FAILED",
            error=f"executor.sh exited with code {proc.returncode}",
            training=data.get("training"),
            backtest=data.get("backtest"),
        )

    return ExperimentResult(
        status="SUCCESS",
        training=data.get("training"),
        backtest=data.get("backtest"),
    )
