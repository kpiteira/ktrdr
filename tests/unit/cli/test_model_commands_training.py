"""
Tests for model training command migration to AsyncCLIClient.execute_operation().

Task 4.1: Verify that training commands use client.execute_operation() with
TrainingOperationAdapter instead of inline polling logic.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.model_commands import _train_model_async


class TestTrainingUsesExecuteOperation:
    """Tests that training uses client.execute_operation() pattern."""

    @pytest.mark.asyncio
    async def test_training_calls_execute_operation(self, tmp_path: Path):
        """Training command uses client.execute_operation() instead of inline polling."""
        # Create mock strategy file
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        # Mock client
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
            "result_summary": {"training_metrics": {"epochs_trained": 10}},
        }

        # Patch AsyncCLIClient to return our mock
        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            # Set up async context manager
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            # Suppress console output
            with patch("ktrdr.cli.model_commands.console"):
                await _train_model_async(
                    strategy_file=str(strategy_file),
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=False,
                    verbose=False,
                    detailed_analytics=False,
                )

        # Verify execute_operation was called, not post/get polling
        assert (
            mock_client.execute_operation.called
        ), "Training must use client.execute_operation() not inline polling"
        # execute_operation should be called once
        assert mock_client.execute_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_training_uses_training_adapter(self, tmp_path: Path):
        """Training command uses TrainingOperationAdapter."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.model_commands.console"):
                await _train_model_async(
                    strategy_file=str(strategy_file),
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=False,
                    verbose=False,
                    detailed_analytics=False,
                )

        # Check that the adapter passed to execute_operation is a TrainingOperationAdapter
        call_args = mock_client.execute_operation.call_args
        adapter = call_args[0][0]  # First positional arg

        # Verify adapter has correct methods
        assert hasattr(adapter, "get_start_endpoint")
        assert hasattr(adapter, "get_start_payload")
        assert hasattr(adapter, "parse_start_response")

        # Verify adapter is configured correctly
        assert adapter.get_start_endpoint() == "/trainings/start"
        payload = adapter.get_start_payload()
        assert payload["strategy_name"] == "test_strategy"
        assert payload["symbols"] == ["AAPL"]
        assert payload["timeframes"] == ["1h"]

    @pytest.mark.asyncio
    async def test_training_passes_progress_callback(self, tmp_path: Path):
        """Training command passes on_progress callback to execute_operation."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.model_commands.console"):
                await _train_model_async(
                    strategy_file=str(strategy_file),
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=False,
                    verbose=False,
                    detailed_analytics=False,
                )

        # Verify on_progress callback was passed
        call_kwargs = mock_client.execute_operation.call_args[1]
        assert (
            "on_progress" in call_kwargs
        ), "execute_operation must be called with on_progress callback"


class TestTrainingNoOperationExecutorImports:
    """Verify no imports from operation_executor.py."""

    def test_no_import_from_operation_executor(self):
        """model_commands.py has no imports from operation_executor.py."""
        import inspect

        import ktrdr.cli.model_commands as module

        source = inspect.getsource(module)

        # Should NOT have these imports
        assert (
            "from ktrdr.cli.operation_executor" not in source
        ), "model_commands.py must not import from operation_executor"
        assert (
            "import operation_executor" not in source
        ), "model_commands.py must not import operation_executor"
        assert (
            "AsyncOperationExecutor" not in source
        ), "model_commands.py must not use AsyncOperationExecutor"


class TestTrainingProgressDisplay:
    """Tests for progress callback handling."""

    @pytest.mark.asyncio
    async def test_progress_callback_is_provided(self, tmp_path: Path):
        """Progress callback is provided to execute_operation."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            # Also mock the Progress context to avoid Rich issues in tests
            with patch("ktrdr.cli.model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.model_commands.console"):
                    await _train_model_async(
                        strategy_file=str(strategy_file),
                        symbols=["AAPL"],
                        timeframes=["1h"],
                        start_date="2024-01-01",
                        end_date="2024-06-01",
                        models_dir="models",
                        validation_split=0.2,
                        data_mode="local",
                        dry_run=False,
                        verbose=False,
                        detailed_analytics=False,
                    )

        # Verify execute_operation was called with on_progress callback
        call_kwargs = mock_client.execute_operation.call_args[1]
        assert "on_progress" in call_kwargs, "on_progress callback must be provided"
        assert callable(call_kwargs["on_progress"]), "on_progress must be callable"


class TestTrainingCancellation:
    """Tests for training cancellation via execute_operation."""

    @pytest.mark.asyncio
    async def test_cancellation_handled_by_execute_operation(self, tmp_path: Path):
        """Cancellation is handled by execute_operation via CancelledError."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        # Simulate cancelled status from execute_operation
        mock_client.execute_operation.return_value = {
            "status": "cancelled",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.model_commands.console") as mock_console:
                await _train_model_async(
                    strategy_file=str(strategy_file),
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=False,
                    verbose=False,
                    detailed_analytics=False,
                )

        # Verify cancellation message was shown
        print_calls = [str(call) for call in mock_console.print.call_args_list]
        cancel_shown = any("cancel" in call.lower() for call in print_calls)
        assert cancel_shown, "Cancellation message should be displayed"


class TestTrainingDryRun:
    """Tests for dry run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_execute_operation(self, tmp_path: Path):
        """Dry run mode should not call execute_operation."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text("name: test")

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True

        with patch("ktrdr.cli.model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.model_commands.console"):
                await _train_model_async(
                    strategy_file=str(strategy_file),
                    symbols=["AAPL"],
                    timeframes=["1h"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=True,  # Dry run enabled
                    verbose=False,
                    detailed_analytics=False,
                )

        # Dry run should not call execute_operation
        assert (
            not mock_client.execute_operation.called
        ), "Dry run must not call execute_operation"
