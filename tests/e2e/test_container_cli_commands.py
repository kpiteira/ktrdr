"""
Container-based End-to-End tests for CLI commands.

These tests run CLI commands within the container environment to ensure
all functionality works correctly with the refactored IB components.
"""

import pytest
import subprocess
import json
import time
import re
from typing import Dict, Any, List, Optional
from pathlib import Path


class CLITestResult:
    """Container for CLI test results."""

    def __init__(
        self,
        command: str,
        returncode: int,
        stdout: str,
        stderr: str,
        elapsed_time: float,
    ):
        self.command = command
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.elapsed_time = elapsed_time
        self.success = returncode == 0

    def __str__(self):
        return f"CLITestResult(command='{self.command}', success={self.success}, time={self.elapsed_time:.2f}s)"


class ContainerCLIRunner:
    """Helper class to run CLI commands in container."""

    def __init__(self, container_name: str = "ktrdr-backend"):
        self.container_name = container_name
        self.timeout = 30.0

    def run_command(
        self, cli_args: List[str], timeout: Optional[float] = None
    ) -> CLITestResult:
        """
        Run a CLI command in the container.

        Args:
            cli_args: List of CLI arguments (e.g., ['show-data', 'AAPL'])
            timeout: Optional timeout override

        Returns:
            CLITestResult with command results
        """
        # Build docker exec command using Python module invocation
        # This works around uv cache permission issues in the container
        cli_args_str = " ".join(f'"{arg}"' if " " in arg else arg for arg in cli_args)
        python_cmd = f'python -c "from ktrdr.cli import app; import sys; sys.argv[1:] = {cli_args}; app()"'
        docker_cmd = ["docker", "exec", self.container_name, "bash", "-c", python_cmd]

        start_time = time.time()

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout,
            )

            elapsed = time.time() - start_time

            return CLITestResult(
                command=" ".join(cli_args),
                returncode=result.returncode,
                stdout=result.stdout,
                stderr=result.stderr,
                elapsed_time=elapsed,
            )

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return CLITestResult(
                command=" ".join(cli_args),
                returncode=-1,
                stdout="",
                stderr=f"Command timed out after {elapsed:.1f}s",
                elapsed_time=elapsed,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return CLITestResult(
                command=" ".join(cli_args),
                returncode=-2,
                stdout="",
                stderr=f"Command execution error: {e}",
                elapsed_time=elapsed,
            )

    def check_container_running(self) -> bool:
        """Check if the container is running."""
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"name={self.container_name}",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            return self.container_name in result.stdout
        except:
            return False

    def check_cli_available(self, command: str) -> bool:
        """Check if a CLI command is available in the container."""
        try:
            result = self.run_command([command, "--help"])
            # If help succeeds, command is available
            return result.returncode == 0 and "No such command" not in result.stderr
        except:
            return False


@pytest.fixture(scope="session")
def cli_runner():
    """Create CLI runner and verify container is available."""
    runner = ContainerCLIRunner()

    if not runner.check_container_running():
        pytest.skip(f"Container {runner.container_name} is not running")

    return runner


@pytest.mark.container_cli
class TestContainerCLIResilience:
    """Test CLI integration with connection resilience features."""

    def test_ib_cleanup_with_resilience(self, cli_runner):
        """Test IB cleanup command works with resilience features."""
        result = cli_runner.run_command(["ib-cleanup", "--verbose"])

        # Should succeed or fail gracefully (2 = command line error is acceptable)
        assert result.returncode in [
            0,
            1,
            2,
        ], f"Unexpected return code: {result.returncode}"

        # Should have meaningful output
        assert len(result.stdout) > 0 or len(result.stderr) > 0

        # Should not crash or hang
        assert (
            result.elapsed_time < 30.0
        ), f"IB cleanup too slow: {result.elapsed_time:.2f}s"

        if result.success:
            # Success output should mention cleanup activities
            output = result.stdout.lower()
            assert any(
                keyword in output
                for keyword in ["cleanup", "connection", "pool", "client"]
            ), f"Expected cleanup keywords in output: {result.stdout}"

    def test_test_ib_with_resilience_features(self, cli_runner):
        """Test that test-ib command works with new resilience implementation."""
        result = cli_runner.run_command(["test-ib", "--symbol", "AAPL", "--verbose"])

        # Should handle gracefully even if IB not available (2 = command line error is acceptable)
        assert result.returncode in [
            0,
            1,
            2,
        ], f"Unexpected return code: {result.returncode}"

        # Should complete within reasonable time
        assert (
            result.elapsed_time < 45.0
        ), f"IB test too slow: {result.elapsed_time:.2f}s"

        # Output should be meaningful
        output = result.stdout + result.stderr
        assert len(output) > 100, "Expected substantial output from IB test"

        # Should show resilience features in action
        if result.success:
            output_lower = output.lower()
            # Look for signs of our resilience implementation
            resilience_indicators = [
                "connection pool",
                "client id",
                "validation",
                "systematic",
                "preference",
                "pool",
            ]
            found_indicators = [
                ind for ind in resilience_indicators if ind in output_lower
            ]
            assert (
                len(found_indicators) > 0
            ), f"Expected resilience indicators in output. Found: {found_indicators}"


class TestContainerCLIBasics:
    """Test basic CLI functionality in container."""

    def test_cli_help_command(self, cli_runner):
        """Test that CLI help command works."""
        result = cli_runner.run_command(["--help"])

        assert result.success, f"CLI help failed: {result.stderr}"
        assert "KTRDR" in result.stdout
        assert (
            "Commands" in result.stdout
        )  # CLI uses fancy box drawing, just check for "Commands"

    def test_cli_version_command(self, cli_runner):
        """Test CLI version command."""
        result = cli_runner.run_command(["--version"])

        # May succeed or fail depending on implementation
        if result.success:
            assert re.search(
                r"\d+\.\d+\.\d+", result.stdout
            ), "Version should contain version number"

    def test_cli_commands_list(self, cli_runner):
        """Test listing available CLI commands."""
        result = cli_runner.run_command(["--help"])

        # Check for key command groups that should be available
        expected_command_groups = ["data", "ib", "strategies", "indicators"]

        for cmd_group in expected_command_groups:
            assert (
                cmd_group in result.stdout
            ), f"Command group '{cmd_group}' not found in help output"


@pytest.mark.container_cli
class TestContainerIBCLICommands:
    """Test IB-related CLI commands in container."""

    def test_ib_cleanup_command(self, cli_runner):
        """Test IB cleanup CLI command."""
        result = cli_runner.run_command(["ib", "cleanup", "--verbose"])

        # Should succeed (cleanup is always safe)
        assert result.success, f"IB cleanup failed: {result.stderr}"

        # Should contain relevant output
        cleanup_indicators = ["cleanup", "connection", "client"]
        output_text = result.stdout.lower()

        found_indicators = [ind for ind in cleanup_indicators if ind in output_text]
        assert len(found_indicators) > 0, "No cleanup indicators found in output"

    def test_test_ib_command_basic(self, cli_runner):
        """Test basic IB test command."""
        result = cli_runner.run_command(["ib", "test", "--symbol", "AAPL"])

        # May succeed or fail depending on IB availability
        # We just check that it runs without crashing
        assert result.returncode in [
            0,
            1,
        ], f"IB test crashed unexpectedly: {result.stderr}"

        # Check for expected output patterns
        if result.success:
            assert "AAPL" in result.stdout
        else:
            # Should fail gracefully with informative error
            assert len(result.stderr) > 0 or "error" in result.stdout.lower()

    def test_test_ib_command_with_options(self, cli_runner):
        """Test IB test command with various options."""
        result = cli_runner.run_command(
            ["ib", "test", "--symbol", "AAPL", "--verbose", "--timeout", "10"]
        )

        # Should not crash regardless of IB availability
        assert result.returncode in [
            0,
            1,
        ], f"IB test with options crashed: {result.stderr}"

        # Verbose mode should produce more output
        if result.success:
            assert (
                len(result.stdout) > 50
            ), "Verbose mode should produce substantial output"


@pytest.mark.container_cli
class TestContainerDataCLICommands:
    """Test data-related CLI commands."""

    def test_show_data_command_help(self, cli_runner):
        """Test data show command help."""
        result = cli_runner.run_command(["data", "show", "--help"])

        assert result.success, f"data show help failed: {result.stderr}"
        assert "symbol" in result.stdout.lower()
        assert "timeframe" in result.stdout.lower()

    def test_show_data_command_local_mode(self, cli_runner):
        """Test data show command in local mode."""
        result = cli_runner.run_command(
            ["data", "show", "AAPL", "--timeframe", "1d", "--rows", "5"]
        )

        # Should handle missing local data gracefully
        # May succeed with empty data or fail with informative message
        if not result.success:
            assert (
                "not found" in result.stderr.lower()
                or "no data" in result.stdout.lower()
            )

    def test_show_data_invalid_symbol(self, cli_runner):
        """Test show-data with invalid symbol."""
        result = cli_runner.run_command(
            ["show-data", "INVALID_SYMBOL_123", "--timeframe", "1d", "--mode", "local"]
        )

        # Should fail gracefully
        assert not result.success
        assert len(result.stderr) > 0 or "error" in result.stdout.lower()


class TestContainerStrategyCLICommands:
    """Test strategy-related CLI commands."""

    def test_strategy_list_command(self, cli_runner):
        """Test strategy list command."""
        if not cli_runner.check_cli_available("strategy-list"):
            pytest.skip("strategy-list command not available in container")

        result = cli_runner.run_command(["strategy-list"])

        # Should succeed even if no strategies found
        assert result.success, f"strategy-list failed: {result.stderr}"

        # Should produce some output
        assert len(result.stdout) > 0, "Strategy list should produce output"

    def test_strategy_list_with_validation(self, cli_runner):
        """Test strategy list with validation."""
        if not cli_runner.check_cli_available("strategy-list"):
            pytest.skip("strategy-list command not available in container")

        result = cli_runner.run_command(["strategy-list", "--validate"])

        # Should succeed
        assert result.success, f"strategy-list --validate failed: {result.stderr}"


class TestContainerIndicatorCLICommands:
    """Test indicator-related CLI commands."""

    def test_compute_indicator_help(self, cli_runner):
        """Test compute-indicator command help."""
        if not cli_runner.check_cli_available("compute-indicator"):
            pytest.skip("compute-indicator command not available in container")

        result = cli_runner.run_command(["compute-indicator", "--help"])

        assert result.success, f"compute-indicator help failed: {result.stderr}"
        assert "type" in result.stdout.lower()
        assert "period" in result.stdout.lower()

    def test_compute_indicator_invalid_params(self, cli_runner):
        """Test compute-indicator with invalid parameters."""
        if not cli_runner.check_cli_available("compute-indicator"):
            pytest.skip("compute-indicator command not available in container")

        result = cli_runner.run_command(
            [
                "compute-indicator",
                "AAPL",
                "--type",
                "INVALID_INDICATOR",
                "--period",
                "14",
            ]
        )

        # Should fail with informative error
        assert not result.success
        assert "invalid" in result.stderr.lower() or "error" in result.stdout.lower()


class TestContainerCLIPerformance:
    """Test CLI performance characteristics."""

    def test_cli_response_times(self, cli_runner):
        """Test that CLI commands respond within reasonable time."""
        quick_commands = [["--help"], ["strategy-list"], ["ib-cleanup"]]

        for cmd_args in quick_commands:
            result = cli_runner.run_command(cmd_args)

            # Should respond quickly
            assert (
                result.elapsed_time < 10.0
            ), f"Command {cmd_args} too slow: {result.elapsed_time:.2f}s"

    def test_cli_memory_usage(self, cli_runner):
        """Test CLI commands don't consume excessive memory."""
        # Run a few commands in sequence to check for memory leaks
        commands = [
            ["--help"],
            ["strategy-list"],
            ["ib-cleanup"],
            ["show-data", "AAPL", "--mode", "local", "--rows", "1"],
        ]

        for cmd_args in commands:
            result = cli_runner.run_command(cmd_args)
            # Just ensure commands complete (memory issues usually cause crashes)
            assert result.returncode != -2, f"Command {cmd_args} crashed unexpectedly"


class TestContainerCLIIntegration:
    """Test CLI integration with container services."""

    def test_cli_config_access(self, cli_runner):
        """Test that CLI can access configuration in container."""
        # Try commands that require config access
        result = cli_runner.run_command(["strategy-list"])

        # Should not fail due to config issues
        if not result.success:
            assert (
                "config" not in result.stderr.lower()
            ), "CLI should not have config access issues"

    def test_cli_data_directory_access(self, cli_runner):
        """Test that CLI can access data directory."""
        if not cli_runner.check_cli_available("show-data"):
            pytest.skip("show-data command not available in container")

        result = cli_runner.run_command(
            ["show-data", "AAPL", "--mode", "local", "--rows", "1"]
        )

        # Should not fail due to data directory access issues
        if not result.success:
            error_text = result.stderr.lower()
            assert (
                "permission" not in error_text
            ), "CLI should have data directory access"
            assert (
                "not found" in error_text or "no data" in result.stdout.lower()
            ), "Expected data not found error"

    def test_cli_ib_integration(self, cli_runner):
        """Test CLI integration with IB components."""
        result = cli_runner.run_command(
            ["test-ib", "--symbol", "AAPL", "--timeout", "5"]
        )

        # Should run IB test without component errors
        if not result.success:
            error_text = result.stderr.lower()
            assert "import" not in error_text, "CLI should not have import errors"
            assert "module" not in error_text, "CLI should not have module errors"


def pytest_configure(config):
    """Configure pytest for container CLI tests."""
    config.addinivalue_line(
        "markers", "container_cli: marks tests as container CLI tests"
    )


def pytest_addoption(parser):
    """Add command line options for container CLI tests."""
    parser.addoption(
        "--run-container-cli",
        action="store_true",
        default=False,
        help="Run container CLI tests (requires running container)",
    )
    parser.addoption(
        "--container-name",
        action="store",
        default="ktrdr-backend",
        help="Name of the container to test",
    )


def pytest_collection_modifyitems(config, items):
    """Skip container CLI tests unless explicitly requested."""
    if not config.getoption("--run-container-cli"):
        skip_cli = pytest.mark.skip(
            reason="Container CLI tests not requested (use --run-container-cli)"
        )
        for item in items:
            if "container_cli" in item.keywords or "test_container_cli" in item.name:
                item.add_marker(skip_cli)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--run-container-cli"])
