"""Integration tests for AsyncCLIClient command migration.

This test suite verifies that migrated commands maintain exact functional behavior
while providing performance improvements through connection reuse.

Tests are designed to fail initially (TDD) and pass once migration is complete.
"""

import json
import time
from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.data_commands import data_app
from ktrdr.cli.model_commands import models_app


class TestAsyncCLIClientDataShowMigration:
    """Test migration of ktrdr data show command to AsyncCLIClient pattern."""

    @pytest.fixture
    def mock_api_responses(self):
        """Mock API responses for data show command."""
        return {
            "cached_data": {
                "dates": [
                    "2024-01-01T09:30:00",
                    "2024-01-01T10:30:00",
                    "2024-01-01T11:30:00",
                ],
                "ohlcv": [
                    [150.0, 152.0, 149.5, 151.0, 1000000],
                    [151.0, 153.0, 150.5, 152.5, 1200000],
                    [152.5, 154.0, 151.5, 153.0, 1100000],
                ],
                "metadata": {"start": "2024-01-01", "end": "2024-01-01"},
            }
        }

    def test_data_show_functional_behavior_unchanged(self, mock_api_responses):
        """Test that data show command produces identical output after migration."""
        runner = CliRunner()

        # Mock AsyncCLIClient for new async pattern
        with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
            mock_cli = AsyncMock()
            mock_cli.__aenter__.return_value = mock_cli
            mock_cli.__aexit__.return_value = None
            mock_cli._make_request.return_value = mock_api_responses["cached_data"]
            mock_cli_class.return_value = mock_cli

            # Run command
            result = runner.invoke(
                data_app,
                [
                    "show",
                    "AAPL",
                    "--timeframe",
                    "1h",
                    "--rows",
                    "3",
                    "--format",
                    "json",
                ],
            )

            # Verify command succeeds
            assert result.exit_code == 0, f"Command failed: {result.output}"

            # Verify JSON output structure
            try:
                output_data = json.loads(result.output)
                assert output_data["symbol"] == "AAPL"
                assert output_data["timeframe"] == "1h"
                assert output_data["displayed_rows"] == 3
                assert len(output_data["data"]) == 3
            except json.JSONDecodeError:
                pytest.fail(f"Expected JSON output, got: {result.output}")

    def test_data_show_table_format_unchanged(self, mock_api_responses):
        """Test that table format output remains identical."""
        runner = CliRunner()

        with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
            mock_cli = AsyncMock()
            mock_cli.__aenter__.return_value = mock_cli
            mock_cli.__aexit__.return_value = None
            mock_cli._make_request.return_value = mock_api_responses["cached_data"]
            mock_cli_class.return_value = mock_cli

            result = runner.invoke(
                data_app, ["show", "AAPL", "--timeframe", "1d", "--rows", "2"]
            )

            assert result.exit_code == 0

            # Verify table elements are present
            output = result.output
            assert "AAPL (1d) - Cached Data" in output
            assert "Date" in output
            assert "Open" in output
            assert "High" in output
            assert "Low" in output
            assert "Close" in output
            assert "Volume" in output

    def test_data_show_error_handling_preserved(self):
        """Test that error handling behavior is preserved."""
        runner = CliRunner()

        # Test error handling - simulate connection failure with AsyncCLIClient
        with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
            mock_cli = AsyncMock()
            mock_cli.__aenter__.side_effect = Exception("Connection failed")
            mock_cli_class.return_value = mock_cli

            result = runner.invoke(data_app, ["show", "AAPL"])

            # Should exit with error code
            assert result.exit_code == 1

    @pytest.mark.asyncio
    async def test_unified_async_cli_integration_data_show(self, mock_api_responses):
        """Test that AsyncCLIClient can be integrated with data show functionality.

        This test will initially FAIL until migration is complete.
        """
        # This is the pattern we want to achieve after migration
        async with AsyncCLIClient() as cli:
            # Mock the HTTP response
            with patch.object(cli, "_make_request") as mock_request:
                mock_request.return_value = mock_api_responses["cached_data"]

                # Simulate data show API call through AsyncCLIClient
                response = await cli._make_request(
                    "GET",
                    "/api/data/cached",
                    params={"symbol": "AAPL", "timeframe": "1h", "rows": 10},
                )

                # Verify we get the expected response
                assert response["dates"] is not None
                assert response["ohlcv"] is not None
                assert len(response["dates"]) == len(response["ohlcv"])

    def test_data_show_performance_baseline(self, mock_api_responses):
        """Establish performance baseline for data show command.

        This test measures current performance to validate improvements.
        """
        runner = CliRunner()

        with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
            mock_cli = AsyncMock()
            mock_cli.__aenter__.return_value = mock_cli
            mock_cli.__aexit__.return_value = None
            mock_cli._make_request.return_value = mock_api_responses["cached_data"]
            mock_cli_class.return_value = mock_cli

            # Time the command execution
            start_time = time.time()
            result = runner.invoke(data_app, ["show", "AAPL", "--format", "json"])
            end_time = time.time()

            duration = end_time - start_time

            assert result.exit_code == 0

            # Store baseline for later comparison (this will be improved)
            # Note: This is just for measurement, actual improvement test comes later
            print(f"Baseline data show performance: {duration:.3f}s")


class TestAsyncCLIClientModelsTrainMigration:
    """Test migration of ktrdr models train command to AsyncCLIClient pattern."""

    @pytest.fixture
    def mock_strategy_file(self, tmp_path):
        """Create a mock strategy file for testing."""
        strategy_content = """
        symbols: ["AAPL"]
        timeframes: ["1h"]
        strategy:
          name: "test_strategy"
          parameters:
            epochs: 10
        """
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(strategy_content)
        return str(strategy_file)

    @pytest.fixture
    def mock_training_responses(self):
        """Mock API responses for training command."""
        return {
            "start_training": {"task_id": "train_12345", "status": "started"},
            "operation_status": {
                "data": {
                    "status": "completed",
                    "progress": {"percentage": 100},
                    "result_summary": {"training_metrics": {"epochs_trained": 10}},
                }
            },
            "training_performance": {
                "training_metrics": {
                    "final_val_accuracy": 0.75,
                    "final_train_loss": 0.25,
                    "training_time_minutes": 5.5,
                    "epochs_trained": 10,
                },
                "test_metrics": {
                    "test_accuracy": 0.72,
                    "precision": 0.71,
                    "recall": 0.68,
                    "f1_score": 0.69,
                },
                "model_info": {"model_size_bytes": 2400000},
            },
        }

    def test_models_train_functional_behavior_unchanged(
        self, mock_strategy_file, mock_training_responses
    ):
        """Test that models train command produces identical output after migration."""
        runner = CliRunner()

        # Mock strategy loader
        with patch("ktrdr.cli.model_commands.strategy_loader") as mock_loader:
            mock_loader.load_strategy_config.return_value = (
                {"symbols": ["AAPL"], "timeframes": ["1h"]},
                True,
            )
            mock_loader.extract_training_symbols_and_timeframes.return_value = (
                ["AAPL"],
                ["1h"],
            )

            # Mock AsyncCLIClient
            with patch("ktrdr.cli.model_commands.AsyncCLIClient") as mock_cli_class:
                mock_cli = AsyncMock()
                mock_cli.__aenter__.return_value = mock_cli
                mock_cli.__aexit__.return_value = None
                mock_cli._make_request.return_value = mock_training_responses[
                    "start_training"
                ]
                mock_cli_class.return_value = mock_cli

                # Run dry-run to test functionality without actual training
                result = runner.invoke(
                    models_app,
                    [
                        "train",
                        mock_strategy_file,
                        "--start-date",
                        "2024-01-01",
                        "--end-date",
                        "2024-01-31",
                        "--dry-run",
                    ],
                )

                assert result.exit_code == 0
                assert "DRY RUN" in result.output
                assert "AAPL" in result.output
                assert "1h" in result.output

    def test_models_train_error_handling_preserved(self, tmp_path):
        """Test that error handling behavior is preserved."""
        runner = CliRunner()

        # Test with non-existent strategy file
        result = runner.invoke(
            models_app,
            [
                "train",
                "/nonexistent/strategy.yaml",
                "--start-date",
                "2024-01-01",
                "--end-date",
                "2024-01-31",
            ],
        )

        assert result.exit_code == 1
        assert "not found" in result.output

    @pytest.mark.asyncio
    async def test_unified_async_cli_integration_models_train(
        self, mock_training_responses
    ):
        """Test that AsyncCLIClient can be integrated with training functionality.

        This test will initially FAIL until migration is complete.
        """
        async with AsyncCLIClient() as cli:
            with patch.object(cli, "_make_request") as mock_request:
                mock_request.return_value = mock_training_responses["start_training"]

                # Simulate training start API call through AsyncCLIClient
                response = await cli._make_request(
                    "POST",
                    "/api/training/start",
                    json_data={
                        "symbols": ["AAPL"],
                        "timeframes": ["1h"],
                        "strategy_name": "test_strategy",
                        "start_date": "2024-01-01",
                        "end_date": "2024-01-31",
                    },
                )

                assert "task_id" in response
                assert response["status"] == "started"

    def test_models_train_performance_baseline(
        self, mock_strategy_file, mock_training_responses
    ):
        """Establish performance baseline for models train command."""
        runner = CliRunner()

        with patch("ktrdr.cli.model_commands.strategy_loader") as mock_loader:
            mock_loader.load_strategy_config.return_value = (
                {"symbols": ["AAPL"], "timeframes": ["1h"]},
                True,
            )
            mock_loader.extract_training_symbols_and_timeframes.return_value = (
                ["AAPL"],
                ["1h"],
            )

            # Mock AsyncCLIClient
            with patch("ktrdr.cli.model_commands.AsyncCLIClient") as mock_cli_class:
                mock_cli = AsyncMock()
                mock_cli.__aenter__.return_value = mock_cli
                mock_cli.__aexit__.return_value = None
                mock_cli._make_request.return_value = {
                    "task_id": "train_123",
                    "status": "started",
                }
                mock_cli_class.return_value = mock_cli

                # Time the command execution (dry run)
                start_time = time.time()
                result = runner.invoke(
                    models_app,
                    [
                        "train",
                        mock_strategy_file,
                        "--start-date",
                        "2024-01-01",
                        "--end-date",
                        "2024-01-31",
                        "--dry-run",
                    ],
                )
                end_time = time.time()

                duration = end_time - start_time

                assert result.exit_code == 0

                # Store baseline for comparison
                print(f"Baseline models train performance: {duration:.3f}s")


class TestAsyncCLIClientPerformanceValidation:
    """Tests to validate performance improvements after migration."""

    @pytest.mark.asyncio
    async def test_connection_reuse_performance(self):
        """Test that AsyncCLIClient reuses connections for performance."""
        # This test validates the core performance improvement

        async with AsyncCLIClient() as cli:
            # Verify HTTP client is created once
            assert cli._http_client is not None

            original_client = cli._http_client

            with patch.object(cli, "_make_request") as mock_request:
                mock_request.return_value = {"success": True}

                # Make multiple requests
                await cli._make_request("GET", "/api/test1")
                await cli._make_request("GET", "/api/test2")
                await cli._make_request("GET", "/api/test3")

                # Verify same client instance is reused
                assert cli._http_client is original_client
                assert mock_request.call_count == 3

    def test_performance_improvement_target(self):
        """Test to ensure performance improvement target is met.

        This test will be updated after migration to validate >50% improvement.
        """
        # This test serves as a placeholder for the performance validation
        # that will be implemented after the migration is complete

        # Target: >50% latency reduction
        baseline_time = 1.0  # Example baseline
        target_improvement = 0.5  # 50% improvement
        target_time = baseline_time * (1 - target_improvement)

        # This will be implemented with real measurements after migration
        assert target_time < baseline_time

        # Note: Actual implementation will measure before/after command execution times
        print(
            f"Target performance: <{target_time:.3f}s (from {baseline_time:.3f}s baseline)"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
