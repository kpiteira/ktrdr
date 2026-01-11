"""
Tests for async_model_commands.py migration to AsyncCLIClient.execute_operation().

Task 4.5.1: Verify that async_model_commands uses client.execute_operation() with
TrainingOperationAdapter instead of AsyncOperationExecutor.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAsyncModelCommandsMigration:
    """Tests that async_model_commands uses AsyncCLIClient.execute_operation() pattern."""

    @pytest.mark.asyncio
    async def test_training_calls_execute_operation(self, tmp_path: Path):
        """Training command uses client.execute_operation() instead of AsyncOperationExecutor."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock client
        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
            "result_summary": {"training_metrics": {"epochs_trained": 10}},
        }

        # Patch AsyncCLIClient to return our mock
        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            # Set up async context manager
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            # Also mock Progress to avoid terminal issues
            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                # Suppress console output and catch sys.exit
                with patch("ktrdr.cli.async_model_commands.console"):
                    with pytest.raises(SystemExit) as exc_info:
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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
                    # Should exit with 0 for completed status
                    assert exc_info.value.code == 0

        # Verify execute_operation was called
        assert (
            mock_client.execute_operation.called
        ), "Training must use client.execute_operation()"
        assert mock_client.execute_operation.call_count == 1

    @pytest.mark.asyncio
    async def test_training_uses_training_adapter(self, tmp_path: Path):
        """Training command uses TrainingOperationAdapter."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.async_model_commands.console"):
                    with pytest.raises(SystemExit) as exc_info:
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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
                    assert exc_info.value.code == 0

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
        assert payload["strategy_name"] == "test"  # Extracted from path
        assert payload["symbols"] == ["AAPL"]
        assert payload["timeframes"] == ["1h"]

    @pytest.mark.asyncio
    async def test_training_passes_progress_callback(self, tmp_path: Path):
        """Training command passes on_progress callback to execute_operation."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.async_model_commands.console"):
                    with pytest.raises(SystemExit):
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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
        assert callable(call_kwargs["on_progress"]), "on_progress must be callable"

    @pytest.mark.asyncio
    async def test_training_checks_health_before_operation(self, tmp_path: Path):
        """Training command calls health_check() before execute_operation()."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.async_model_commands.console"):
                    with pytest.raises(SystemExit):
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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

        # Verify health_check was called
        assert (
            mock_client.health_check.called
        ), "health_check() must be called before operation"


class TestAsyncModelCommandsNoOperationExecutorImports:
    """Verify no imports from operation_executor.py."""

    def test_no_import_from_operation_executor(self):
        """async_model_commands.py has no imports from operation_executor.py."""
        import inspect

        from ktrdr.cli import async_model_commands

        source = inspect.getsource(async_model_commands)

        # Should NOT have these imports or usages
        assert not (
            "from ktrdr.cli.operation_executor" in source
            or "import operation_executor" in source
        ), "async_model_commands.py must not import from operation_executor"

        assert (
            "AsyncOperationExecutor" not in source
        ), "async_model_commands.py must not use AsyncOperationExecutor"


class TestAsyncModelCommandsResultHandling:
    """Tests for result handling with new dict-based return value."""

    @pytest.mark.asyncio
    async def test_handles_completed_status(self, tmp_path: Path):
        """Training command handles completed status correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
            "result_summary": {"training_metrics": {"epochs_trained": 10}},
        }

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.async_model_commands.console") as mock_console:
                    with pytest.raises(SystemExit) as exc_info:
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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
                    # Should exit with 0 for completed status
                    assert exc_info.value.code == 0

                    # Verify success message was shown
                    print_calls = [
                        str(call) for call in mock_console.print.call_args_list
                    ]
                    success_shown = any(
                        "completed" in call.lower() or "success" in call.lower()
                        for call in print_calls
                    )
                    assert (
                        success_shown
                    ), "Success message should be displayed for completed status"

    @pytest.mark.asyncio
    async def test_handles_cancelled_status(self, tmp_path: Path):
        """Training command handles cancelled status correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        mock_client = AsyncMock()
        mock_client.health_check.return_value = True
        mock_client.execute_operation.return_value = {
            "status": "cancelled",
            "operation_id": "op_test123",
        }

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with patch("ktrdr.cli.async_model_commands.console") as mock_console:
                    with pytest.raises(SystemExit) as exc_info:
                        await _train_model_async_impl(
                            strategy_file="strategies/test.yaml",
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
                    # Should exit with 0 for cancelled status
                    assert exc_info.value.code == 0

                    # Verify cancellation message was shown
                    print_calls = [
                        str(call) for call in mock_console.print.call_args_list
                    ]
                    cancel_shown = any("cancel" in call.lower() for call in print_calls)
                    assert cancel_shown, "Cancellation message should be displayed"


class TestAsyncModelCommandsDryRun:
    """Tests for dry run mode - should NOT use AsyncCLIClient at all."""

    @pytest.mark.asyncio
    async def test_dry_run_does_not_create_client(self, tmp_path: Path):
        """Dry run mode should not create AsyncCLIClient."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            with patch("ktrdr.cli.async_model_commands.console"):
                await _train_model_async_impl(
                    strategy_file="strategies/test.yaml",
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

        # Dry run should not instantiate client
        assert not MockClient.called, "Dry run must not create AsyncCLIClient"
