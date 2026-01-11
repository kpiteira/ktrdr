"""
Tests for backtest command migration to AsyncCLIClient.execute_operation().

Task 4.2: Verify that backtest commands use client.execute_operation() with
BacktestingOperationAdapter instead of AsyncOperationExecutor.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.backtest_commands import _run_backtest_async_impl


class TestBacktestUsesExecuteOperation:
    """Tests that backtest uses client.execute_operation() pattern."""

    @pytest.mark.asyncio
    async def test_backtest_calls_execute_operation(self):
        """Backtest command uses client.execute_operation() instead of AsyncOperationExecutor."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_backtest_123",
            "result_summary": {"metrics": {"total_return_pct": 0.15}},
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console"):
                await _run_backtest_async_impl(
                    strategy="neuro_mean_reversion",
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    capital=100000,
                    commission=0.001,
                    slippage=0.001,
                    model_path=None,
                    verbose=False,
                )

        # Verify execute_operation was called, not AsyncOperationExecutor
        assert (
            mock_client.execute_operation.called
        ), "Backtest must use client.execute_operation() not AsyncOperationExecutor"
        assert mock_client.execute_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_backtest_uses_backtesting_adapter(self):
        """Backtest command uses BacktestingOperationAdapter."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_backtest_123",
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console"):
                await _run_backtest_async_impl(
                    strategy="momentum",
                    symbol="MSFT",
                    timeframe="4h",
                    start_date="2024-01-01",
                    end_date="2024-06-30",
                    capital=50000,
                    commission=0.002,
                    slippage=0.0015,
                    model_path="models/test.pt",
                    verbose=False,
                )

        # Check the adapter passed to execute_operation
        call_args = mock_client.execute_operation.call_args
        adapter = call_args[0][0]  # First positional arg

        # Verify adapter has correct methods
        assert hasattr(adapter, "get_start_endpoint")
        assert hasattr(adapter, "get_start_payload")
        assert hasattr(adapter, "parse_start_response")

        # Verify adapter is configured correctly
        assert adapter.get_start_endpoint() == "/backtests/start"
        payload = adapter.get_start_payload()
        assert payload["strategy_name"] == "momentum"
        assert payload["symbol"] == "MSFT"
        assert payload["timeframe"] == "4h"
        assert payload["start_date"] == "2024-01-01"
        assert payload["end_date"] == "2024-06-30"
        assert payload["initial_capital"] == 50000
        assert payload["commission"] == 0.002
        assert payload["slippage"] == 0.0015
        assert payload["model_path"] == "models/test.pt"

    @pytest.mark.asyncio
    async def test_backtest_passes_progress_callback(self):
        """Backtest command passes on_progress callback to execute_operation."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_backtest_123",
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console"):
                await _run_backtest_async_impl(
                    strategy="test_strategy",
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    capital=100000,
                    commission=0.001,
                    slippage=0.001,
                    model_path=None,
                    verbose=False,
                )

        # Verify on_progress callback was passed
        call_kwargs = mock_client.execute_operation.call_args[1]
        assert (
            "on_progress" in call_kwargs
        ), "execute_operation must be called with on_progress callback"


class TestBacktestNoOperationExecutorImports:
    """Verify no imports from operation_executor.py."""

    def test_no_import_from_operation_executor(self):
        """backtest_commands.py has no imports from operation_executor.py."""
        import inspect
        import sys

        module = sys.modules["ktrdr.cli.backtest_commands"]

        source = inspect.getsource(module)

        # Should NOT have these imports
        assert (
            "from ktrdr.cli.operation_executor" not in source
        ), "backtest_commands.py must not import from operation_executor"
        assert (
            "import operation_executor" not in source
        ), "backtest_commands.py must not import operation_executor"
        assert (
            "AsyncOperationExecutor" not in source
        ), "backtest_commands.py must not use AsyncOperationExecutor"


class TestBacktestProgressDisplay:
    """Tests for progress callback handling."""

    @pytest.mark.asyncio
    async def test_progress_callback_is_callable(self):
        """Progress callback provided to execute_operation is callable."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_backtest_123",
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.backtest_commands.console"):
                    await _run_backtest_async_impl(
                        strategy="test",
                        symbol="AAPL",
                        timeframe="1d",
                        start_date="2024-01-01",
                        end_date="2024-12-31",
                        capital=100000,
                        commission=0.001,
                        slippage=0.001,
                        model_path=None,
                        verbose=False,
                    )

        call_kwargs = mock_client.execute_operation.call_args[1]
        assert "on_progress" in call_kwargs, "on_progress callback must be provided"
        assert callable(call_kwargs["on_progress"]), "on_progress must be callable"


class TestBacktestCancellation:
    """Tests for backtest cancellation via execute_operation."""

    @pytest.mark.asyncio
    async def test_cancellation_handled_by_execute_operation(self):
        """Cancellation is handled by execute_operation via CancelledError."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        # Simulate cancelled status from execute_operation
        mock_client.execute_operation.return_value = {
            "status": "cancelled",
            "operation_id": "op_backtest_123",
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console") as mock_console:
                await _run_backtest_async_impl(
                    strategy="test",
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    capital=100000,
                    commission=0.001,
                    slippage=0.001,
                    model_path=None,
                    verbose=False,
                )

        # Verify cancellation message was shown
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        cancel_shown = any("cancel" in call.lower() for call in print_calls)
        assert cancel_shown, "Cancellation message should be displayed"


class TestBacktestResultHandling:
    """Tests for backtest result handling."""

    @pytest.mark.asyncio
    async def test_completed_status_displays_success(self):
        """Completed backtest displays success message."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_backtest_123",
            "result_summary": {
                "metrics": {
                    "total_return_pct": 0.15,
                    "sharpe_ratio": 1.5,
                    "max_drawdown_pct": -0.05,
                    "total_trades": 25,
                    "win_rate": 0.6,
                }
            },
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console") as mock_console:
                await _run_backtest_async_impl(
                    strategy="test",
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    capital=100000,
                    commission=0.001,
                    slippage=0.001,
                    model_path=None,
                    verbose=False,
                )

        # Verify success message was shown
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        success_shown = any("completed" in call.lower() for call in print_calls)
        assert success_shown, "Success message should be displayed"

    @pytest.mark.asyncio
    async def test_failed_status_displays_error(self):
        """Failed backtest displays error message."""
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "failed",
            "operation_id": "op_backtest_123",
            "error_message": "Insufficient data for backtest period",
        }

        with patch("ktrdr.cli.backtest_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.backtest_commands.console") as mock_console:
                await _run_backtest_async_impl(
                    strategy="test",
                    symbol="AAPL",
                    timeframe="1d",
                    start_date="2024-01-01",
                    end_date="2024-12-31",
                    capital=100000,
                    commission=0.001,
                    slippage=0.001,
                    model_path=None,
                    verbose=False,
                )

        # Verify error message was shown
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        error_shown = any("failed" in call.lower() for call in print_calls)
        assert error_shown, "Error message should be displayed"
