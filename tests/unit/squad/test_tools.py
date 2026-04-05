"""Tests for execution tools — validate_strategy + execute_experiment."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

# Ensure .squad/ is on sys.path
_squad_dir = str(Path(__file__).resolve().parents[3] / ".squad")
if _squad_dir not in sys.path:
    sys.path.insert(0, _squad_dir)

from squad_engine.tools import (  # noqa: E402
    ExperimentResult,
    ValidationResult,
    execute_experiment,
    validate_strategy,
)


class TestValidateStrategy:
    @pytest.mark.asyncio
    async def test_valid_strategy_returns_true(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"Strategy is valid"
        mock_proc.stderr = b""

        with patch("squad_engine.tools._run_subprocess", return_value=mock_proc):
            result = await validate_strategy("test_strategy")

        assert isinstance(result, ValidationResult)
        assert result.valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_invalid_strategy_returns_error(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.stdout = b""
        mock_proc.stderr = b"fuzzy_set 'rsi' references unknown indicator"

        with patch("squad_engine.tools._run_subprocess", return_value=mock_proc):
            result = await validate_strategy("bad_strategy")

        assert result.valid is False
        assert "rsi" in result.error

    @pytest.mark.asyncio
    async def test_subprocess_exception_returns_error(self):
        with patch(
            "squad_engine.tools._run_subprocess",
            side_effect=Exception("Process failed"),
        ):
            result = await validate_strategy("broken")

        assert result.valid is False
        assert "Process failed" in result.error


class TestExecuteExperiment:
    @pytest.mark.asyncio
    async def test_successful_execution_returns_results(self):
        executor_output = json.dumps(
            {
                "experiment": "test_strat",
                "training": {"operation_id": "op_123", "summary": {"accuracy": 0.65}},
                "backtest": {
                    "operation_id": "op_456",
                    "summary": {"sharpe": -0.5, "total_trades": 100},
                },
            }
        )
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout = executor_output.encode()
        mock_proc.stderr = b"[executor] Training complete"

        with patch("squad_engine.tools._run_subprocess", return_value=mock_proc):
            result = await execute_experiment(
                strategy="test_strat",
                train_start="2015-01-01",
                train_end="2020-12-31",
                bt_start="2021-01-01",
                bt_end="2025-01-01",
            )

        assert isinstance(result, ExperimentResult)
        assert result.status == "SUCCESS"
        assert result.training["summary"]["accuracy"] == 0.65
        assert result.backtest["summary"]["total_trades"] == 100
        assert result.error is None

    @pytest.mark.asyncio
    async def test_failed_execution_returns_error(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 1
        mock_proc.stdout = b'{"error": "executor_failed", "experiment": "bad_strat"}'
        mock_proc.stderr = b"[executor] ERROR: Training failed"

        with patch("squad_engine.tools._run_subprocess", return_value=mock_proc):
            result = await execute_experiment(
                strategy="bad_strat",
                train_start="2015-01-01",
                train_end="2020-12-31",
                bt_start="2021-01-01",
                bt_end="2025-01-01",
            )

        assert result.status == "FAILED"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_subprocess_timeout_returns_error(self):
        import asyncio

        with patch(
            "squad_engine.tools._run_subprocess",
            side_effect=asyncio.TimeoutError(),
        ):
            result = await execute_experiment(
                strategy="slow_strat",
                train_start="2015-01-01",
                train_end="2020-12-31",
                bt_start="2021-01-01",
                bt_end="2025-01-01",
            )

        assert result.status == "FAILED"
        assert "timeout" in result.error.lower() or "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_malformed_json_returns_error(self):
        mock_proc = AsyncMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b"not valid json at all"
        mock_proc.stderr = b""

        with patch("squad_engine.tools._run_subprocess", return_value=mock_proc):
            result = await execute_experiment(
                strategy="garbled",
                train_start="2015-01-01",
                train_end="2020-12-31",
                bt_start="2021-01-01",
                bt_end="2025-01-01",
            )

        assert result.status == "FAILED"
        assert result.error is not None
