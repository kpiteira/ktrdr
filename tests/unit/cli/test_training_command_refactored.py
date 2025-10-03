"""
Tests for refactored training command using AsyncOperationExecutor pattern.

Tests verify that the training command properly:
- Validates strategy files and inputs
- Creates TrainingOperationAdapter with correct parameters
- Calls AsyncOperationExecutor.execute_operation
- Handles success, failure, and cancellation scenarios
"""

from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.cli.operation_adapters import TrainingOperationAdapter
from ktrdr.cli.operation_executor import AsyncOperationExecutor


class TestTrainingCommandRefactored:
    """Test refactored training command using executor pattern."""

    @pytest.fixture
    def mock_strategy_path(self, tmp_path):
        """Create a mock strategy file."""
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(
            """
name: test_strategy
symbols:
  - AAPL
  - GOOGL
timeframes:
  - 1h
  - 1d
epochs: 10
            """
        )
        return strategy_file

    @pytest.fixture
    def mock_strategy_loader(self):
        """Mock strategy loader."""
        with patch("ktrdr.cli.async_model_commands.strategy_loader") as mock_loader:
            mock_loader.load_strategy_config.return_value = (
                {
                    "name": "test_strategy",
                    "symbols": ["AAPL", "GOOGL"],
                    "timeframes": ["1h", "1d"],
                    "epochs": 10,
                },
                True,  # is_v2
            )
            mock_loader.extract_training_symbols_and_timeframes.return_value = (
                ["AAPL", "GOOGL"],
                ["1h", "1d"],
            )
            yield mock_loader

    @pytest.fixture
    def mock_executor(self):
        """Mock AsyncOperationExecutor."""
        executor = AsyncMock(spec=AsyncOperationExecutor)
        executor.execute_operation = AsyncMock(return_value=True)
        return executor

    @pytest.mark.asyncio
    async def test_training_command_creates_adapter_correctly(
        self, mock_strategy_path, mock_strategy_loader, mock_executor
    ):
        """Test that training command creates TrainingOperationAdapter with correct parameters."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock sys.exit to prevent test from exiting
        with patch("ktrdr.cli.async_model_commands.sys.exit"):
            with patch(
                "ktrdr.cli.async_model_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                # Call the async implementation
                await _train_model_async_impl(
                    strategy_file=str(mock_strategy_path),
                    symbols=["AAPL", "GOOGL"],
                    timeframes=["1h", "1d"],
                    start_date="2024-01-01",
                    end_date="2024-06-01",
                    models_dir="models",
                    validation_split=0.2,
                    data_mode="local",
                    dry_run=False,
                    verbose=False,
                    detailed_analytics=True,
                )

                # Verify executor.execute_operation was called
                assert mock_executor.execute_operation.called

                # Get the adapter that was passed to execute_operation
                call_args = mock_executor.execute_operation.call_args
                adapter = call_args[1]["adapter"]  # Keyword arg

                # Verify it's a TrainingOperationAdapter
                assert isinstance(adapter, TrainingOperationAdapter)

                # Verify adapter has correct parameters
                assert adapter.strategy_name == "test_strategy"
                assert adapter.symbols == ["AAPL", "GOOGL"]
                assert adapter.timeframes == ["1h", "1d"]
                assert adapter.start_date == "2024-01-01"
                assert adapter.end_date == "2024-06-01"
                assert adapter.validation_split == 0.2
                assert adapter.detailed_analytics is True

    @pytest.mark.asyncio
    async def test_training_command_handles_success(
        self, mock_strategy_path, mock_strategy_loader, mock_executor
    ):
        """Test that training command handles successful completion correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock successful execution
        mock_executor.execute_operation = AsyncMock(return_value=True)

        # Mock sys.exit to capture the exit code
        with patch("ktrdr.cli.async_model_commands.sys.exit") as mock_exit:
            with patch(
                "ktrdr.cli.async_model_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                await _train_model_async_impl(
                    strategy_file=str(mock_strategy_path),
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

                # Verify execute_operation was called once
                assert mock_executor.execute_operation.call_count == 1

                # Verify sys.exit was called with 0 (success)
                mock_exit.assert_called_once_with(0)

    @pytest.mark.asyncio
    async def test_training_command_handles_failure(
        self, mock_strategy_path, mock_strategy_loader, mock_executor
    ):
        """Test that training command handles failure correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock failed execution
        mock_executor.execute_operation = AsyncMock(return_value=False)

        # Mock sys.exit to capture the exit code
        with patch("ktrdr.cli.async_model_commands.sys.exit") as mock_exit:
            with patch(
                "ktrdr.cli.async_model_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                await _train_model_async_impl(
                    strategy_file=str(mock_strategy_path),
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

                # Verify execute_operation was called
                assert mock_executor.execute_operation.called

                # Verify sys.exit was called with 1 (failure)
                mock_exit.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_training_command_dry_run_skips_execution(
        self, mock_strategy_path, mock_strategy_loader, mock_executor
    ):
        """Test that dry run mode doesn't execute training."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch(
            "ktrdr.cli.async_model_commands.AsyncOperationExecutor",
            return_value=mock_executor,
        ):
            # Dry run should not call executor
            await _train_model_async_impl(
                strategy_file=str(mock_strategy_path),
                symbols=["AAPL"],
                timeframes=["1h"],
                start_date="2024-01-01",
                end_date="2024-06-01",
                models_dir="models",
                validation_split=0.2,
                data_mode="local",
                dry_run=True,  # Dry run!
                verbose=False,
                detailed_analytics=False,
            )

            # Verify execute_operation was NOT called
            assert not mock_executor.execute_operation.called

    @pytest.mark.asyncio
    async def test_training_command_uses_executor_progress_callback(
        self, mock_strategy_path, mock_strategy_loader, mock_executor
    ):
        """Test that training command passes progress callback to executor."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch("ktrdr.cli.async_model_commands.sys.exit"):
            with patch(
                "ktrdr.cli.async_model_commands.AsyncOperationExecutor",
                return_value=mock_executor,
            ):
                await _train_model_async_impl(
                    strategy_file=str(mock_strategy_path),
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

                # Verify execute_operation was called with correct arguments
                assert mock_executor.execute_operation.called
                call_args = mock_executor.execute_operation.call_args

                # Should have adapter, console, progress_callback, and show_progress
                assert "adapter" in call_args[1]
                assert "console" in call_args[1]
                assert "progress_callback" in call_args[1]
                assert "show_progress" in call_args[1]

                # Progress callback should be callable and return a string
                assert callable(call_args[1]["progress_callback"])

                # Test callback returns formatted string
                # Use field names that match TrainingProgressBridge implementation
                test_operation_data = {
                    "status": "running",
                    "progress": {
                        "percentage": 50,
                        "context": {
                            "epoch_index": 5,  # Actual field name from TrainingProgressBridge
                            "batch_number": 100,  # Actual field name from TrainingProgressBridge
                            "batch_total_per_epoch": 200,  # Actual field name
                            "total_epochs": 10,  # Total epochs in context
                        },
                    },
                    "metadata": {"parameters": {"epochs": 10}},
                }
                result = call_args[1]["progress_callback"](test_operation_data)
                assert isinstance(result, str)
                assert "Epoch: 5/10" in result

    @pytest.mark.asyncio
    async def test_training_command_validates_strategy_file_exists(
        self, mock_strategy_loader
    ):
        """Test that training command validates strategy file existence."""
        from ktrdr.cli.async_model_commands import train_model_async

        # Test with non-existent file
        with pytest.raises(SystemExit):
            train_model_async(
                strategy_file="nonexistent_strategy.yaml",
                symbol=None,
                timeframe=None,
                start_date="2024-01-01",
                end_date="2024-06-01",
                models_dir="models",
                validation_split=0.2,
                data_mode="local",
                dry_run=False,
                verbose=False,
                detailed_analytics=False,
            )
