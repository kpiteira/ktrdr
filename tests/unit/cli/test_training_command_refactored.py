"""
Tests for refactored training command using AsyncCLIClient.execute_operation() pattern.

Tests verify that the training command properly:
- Validates strategy files and inputs
- Creates TrainingOperationAdapter with correct parameters
- Calls AsyncCLIClient.execute_operation
- Handles success, failure, and cancellation scenarios

NOTE: These tests were updated as part of M4.5 migration from
AsyncOperationExecutor to AsyncCLIClient.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.cli.operation_adapters import TrainingOperationAdapter


class TestTrainingCommandRefactored:
    """Test refactored training command using AsyncCLIClient pattern."""

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
    def mock_client(self):
        """Mock AsyncCLIClient."""
        client = AsyncMock()
        client.health_check.return_value = True
        client.execute_operation.return_value = {
            "status": "completed",
            "operation_id": "op_test123",
            "result_summary": {"training_metrics": {"epochs_trained": 10}},
        }
        return client

    @pytest.mark.asyncio
    async def test_training_command_creates_adapter_correctly(
        self, mock_strategy_path, mock_strategy_loader, mock_client
    ):
        """Test that training command creates TrainingOperationAdapter with correct parameters."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with pytest.raises(SystemExit) as exc_info:
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
                assert exc_info.value.code == 0

        # Verify execute_operation was called
        assert mock_client.execute_operation.called

        # Get the adapter that was passed to execute_operation
        call_args = mock_client.execute_operation.call_args
        adapter = call_args[0][0]  # First positional arg

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
        self, mock_strategy_path, mock_strategy_loader, mock_client
    ):
        """Test that training command handles successful completion correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock successful execution
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

                with pytest.raises(SystemExit) as exc_info:
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
        assert mock_client.execute_operation.call_count == 1

        # Verify sys.exit was called with 0 (success)
        assert exc_info.value.code == 0

    @pytest.mark.asyncio
    async def test_training_command_handles_failure(
        self, mock_strategy_path, mock_strategy_loader, mock_client
    ):
        """Test that training command handles failure correctly."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        # Mock failed execution
        mock_client.execute_operation.return_value = {
            "status": "failed",
            "operation_id": "op_test123",
            "error_message": "Training failed",
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

                with pytest.raises(SystemExit) as exc_info:
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
        assert mock_client.execute_operation.called

        # Verify sys.exit was called with 1 (failure)
        assert exc_info.value.code == 1

    @pytest.mark.asyncio
    async def test_training_command_dry_run_skips_execution(
        self, mock_strategy_path, mock_strategy_loader, mock_client
    ):
        """Test that dry run mode doesn't execute training."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            # Dry run should not call executor at all
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

            # Verify AsyncCLIClient was NOT called (no context manager entered)
            assert not MockClient.called

    @pytest.mark.asyncio
    async def test_training_command_uses_progress_callback(
        self, mock_strategy_path, mock_strategy_loader, mock_client
    ):
        """Test that training command passes progress callback to execute_operation."""
        from ktrdr.cli.async_model_commands import _train_model_async_impl

        with patch("ktrdr.cli.async_model_commands.AsyncCLIClient") as MockClient:
            MockClient.return_value.__aenter__.return_value = mock_client
            MockClient.return_value.__aexit__.return_value = None

            with patch("ktrdr.cli.async_model_commands.Progress") as MockProgress:
                mock_progress_instance = MagicMock()
                mock_progress_instance.__enter__.return_value = mock_progress_instance
                mock_progress_instance.__exit__.return_value = None
                mock_progress_instance.add_task.return_value = 0
                MockProgress.return_value = mock_progress_instance

                with pytest.raises(SystemExit):
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
        assert mock_client.execute_operation.called
        call_kwargs = mock_client.execute_operation.call_args[1]

        # Should have on_progress and poll_interval
        assert "on_progress" in call_kwargs
        assert "poll_interval" in call_kwargs

        # Progress callback should be callable
        assert callable(call_kwargs["on_progress"])

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
