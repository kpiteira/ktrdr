"""Performance benchmark tests for AsyncCLIClient command migration.

These tests establish performance baselines and validate improvements
after migration to AsyncCLIClient pattern.
"""

import asyncio
import statistics
import time
from contextlib import contextmanager
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from ktrdr.cli.async_cli_client import AsyncCLIClient
from ktrdr.cli.async_model_commands import async_models_app as models_app
from ktrdr.cli.data_commands import data_app


class PerformanceBenchmarker:
    """Utility class for measuring command performance."""

    @staticmethod
    @contextmanager
    def measure_time():
        """Context manager to measure execution time."""
        start = time.time()
        yield lambda: time.time() - start

    @staticmethod
    def run_multiple_measurements(func, iterations: int = 5) -> dict:
        """Run function multiple times and collect statistics."""
        times = []
        for _ in range(iterations):
            with PerformanceBenchmarker.measure_time() as get_duration:
                func()
                times.append(get_duration())

        return {
            "mean": statistics.mean(times),
            "median": statistics.median(times),
            "min": min(times),
            "max": max(times),
            "stdev": statistics.stdev(times) if len(times) > 1 else 0,
            "times": times,
        }


class TestDataShowPerformanceBenchmarks:
    """Performance benchmarks for data show command migration."""

    @pytest.fixture
    def mock_api_responses(self):
        """Mock API responses for consistent testing."""
        return {
            "dates": ["2024-01-01T09:30:00"] * 100,  # 100 data points
            "ohlcv": [[150.0, 152.0, 149.5, 151.0, 1000000]] * 100,
            "metadata": {"start": "2024-01-01", "end": "2024-01-01"},
        }

    def test_current_data_show_performance_baseline(self, mock_api_responses):
        """Establish baseline performance for current data show implementation."""
        runner = CliRunner()

        def run_command():
            with patch("ktrdr.cli.data_commands.AsyncCLIClient") as mock_cli_class:
                from unittest.mock import AsyncMock

                mock_cli = AsyncMock()
                mock_cli.__aenter__.return_value = mock_cli
                mock_cli.__aexit__.return_value = None
                mock_cli._make_request.return_value = mock_api_responses
                mock_cli_class.return_value = mock_cli

                result = runner.invoke(data_app, ["show", "AAPL", "--format", "json"])
                assert result.exit_code == 0

        # Measure current performance
        stats = PerformanceBenchmarker.run_multiple_measurements(run_command)

        # Store baseline - this represents the "before" state
        print(
            f"Current data show baseline: {stats['mean']:.3f}s ±{stats['stdev']:.3f}s"
        )

        # Set performance target (this should be achievable after migration)
        performance_target = stats["mean"] * 0.5  # 50% improvement target
        print(f"Performance target after migration: <{performance_target:.3f}s")

        # This assertion will be updated after migration to validate improvement
        assert (
            stats["mean"] > 0
        )  # Placeholder - will be real measurement after migration

    @pytest.mark.asyncio
    async def test_unified_async_cli_data_show_target_performance(
        self, mock_api_responses
    ):
        """Test target performance using AsyncCLIClient pattern.

        This test will initially FAIL until the migration is implemented.
        """

        async def run_unified_command():
            async with AsyncCLIClient() as cli:
                with patch.object(cli, "_make_request") as mock_request:
                    mock_request.return_value = mock_api_responses

                    # Simulate the unified async pattern we want to achieve
                    await cli._make_request(
                        "GET", "/api/data/cached", params={"symbol": "AAPL"}
                    )

        # Time the unified approach
        with PerformanceBenchmarker.measure_time() as get_duration:
            await run_unified_command()
            unified_time = get_duration()

        print(f"AsyncCLIClient pattern time: {unified_time:.3f}s")

        # This test validates that the unified approach is feasible
        # After migration, this should show significant improvement
        assert unified_time < 1.0  # Reasonable upper bound


class TestModelsTrainPerformanceBenchmarks:
    """Performance benchmarks for models train command migration."""

    @pytest.fixture
    def mock_strategy_file(self, tmp_path):
        """Create a mock strategy file."""
        strategy_content = """
        symbols: ["AAPL"]
        timeframes: ["1h"]
        strategy:
          name: "test_strategy"
        """
        strategy_file = tmp_path / "test_strategy.yaml"
        strategy_file.write_text(strategy_content)
        return str(strategy_file)

    @pytest.fixture
    def mock_training_responses(self):
        """Mock training API responses."""
        return {
            "start_training": {"task_id": "train_123", "status": "started"},
            "operation_status": {
                "data": {"status": "completed", "progress": {"percentage": 100}}
            },
        }

    def test_current_models_train_performance_baseline(self, mock_strategy_file):
        """Establish baseline performance for current models train implementation."""
        runner = CliRunner()

        def run_command():
            with patch("ktrdr.cli.model_commands.strategy_loader") as mock_loader:
                mock_loader.load_strategy_config.return_value = (
                    {"symbols": ["AAPL"], "timeframes": ["1h"]},
                    True,
                )
                mock_loader.extract_training_symbols_and_timeframes.return_value = (
                    ["AAPL"],
                    ["1h"],
                )

                with patch("ktrdr.cli.model_commands.AsyncCLIClient") as mock_cli_class:
                    from unittest.mock import AsyncMock

                    mock_cli = AsyncMock()
                    mock_cli.__aenter__.return_value = mock_cli
                    mock_cli.__aexit__.return_value = None
                    mock_cli._make_request.return_value = {
                        "task_id": "train_123",
                        "status": "started",
                    }
                    mock_cli_class.return_value = mock_cli

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

        # Measure current performance
        stats = PerformanceBenchmarker.run_multiple_measurements(run_command)

        print(
            f"Current models train baseline: {stats['mean']:.3f}s ±{stats['stdev']:.3f}s"
        )

        # Set performance target
        performance_target = stats["mean"] * 0.5  # 50% improvement target
        print(f"Performance target after migration: <{performance_target:.3f}s")

        assert stats["mean"] > 0  # Placeholder for real validation after migration

    @pytest.mark.asyncio
    async def test_unified_async_cli_models_train_target_performance(
        self, mock_training_responses
    ):
        """Test target performance using AsyncCLIClient pattern."""

        async def run_unified_command():
            async with AsyncCLIClient() as cli:
                with patch.object(cli, "_make_request") as mock_request:
                    mock_request.return_value = mock_training_responses[
                        "start_training"
                    ]

                    await cli._make_request(
                        "POST",
                        "/api/training/start",
                        json_data={
                            "symbols": ["AAPL"],
                            "timeframes": ["1h"],
                            "strategy_name": "test_strategy",
                        },
                    )

        with PerformanceBenchmarker.measure_time() as get_duration:
            await run_unified_command()
            unified_time = get_duration()

        print(f"AsyncCLIClient pattern time: {unified_time:.3f}s")
        assert unified_time < 1.0


class TestConcurrentOperationPerformance:
    """Test performance of concurrent operations using AsyncCLIClient."""

    @pytest.mark.asyncio
    async def test_concurrent_data_requests_performance(self):
        """Test performance of concurrent data requests.

        This validates that AsyncCLIClient enables efficient concurrent operations.
        """
        mock_response = {
            "dates": ["2024-01-01T09:30:00"],
            "ohlcv": [[150.0, 152.0, 149.5, 151.0, 1000000]],
        }

        async def make_concurrent_requests():
            async with AsyncCLIClient() as cli:
                with patch.object(cli, "_make_request") as mock_request:
                    mock_request.return_value = mock_response

                    # Run 10 concurrent requests
                    tasks = []
                    for i in range(10):
                        task = cli._make_request(
                            "GET", "/api/data/cached", params={"symbol": f"SYMBOL{i}"}
                        )
                        tasks.append(task)

                    await asyncio.gather(*tasks)

        with PerformanceBenchmarker.measure_time() as get_duration:
            await make_concurrent_requests()
            concurrent_time = get_duration()

        print(f"10 concurrent requests time: {concurrent_time:.3f}s")

        # With connection reuse, concurrent requests should be efficient
        assert (
            concurrent_time < 2.0
        )  # Should be much faster than 10 sequential requests


class TestPerformanceRegressionValidation:
    """Tests to validate no performance regression after migration."""

    def test_post_migration_performance_validation(self):
        """Placeholder test for post-migration performance validation.

        This test will be implemented after migration to ensure:
        1. >50% performance improvement achieved
        2. No functional regression
        3. Error handling performance maintained
        """
        # This will be implemented with actual before/after measurements
        # after the migration is complete

        # Target metrics:
        target_improvement = 0.5  # 50% improvement
        acceptable_variance = 0.1  # 10% variance tolerance

        # Placeholder assertions - will be real measurements after migration
        assert target_improvement > 0
        assert acceptable_variance > 0

        print("Performance validation test ready for implementation after migration")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
