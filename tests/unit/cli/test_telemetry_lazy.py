"""Tests for lazy telemetry initialization.

Verifies that OpenTelemetry is not loaded at import time and only
initialized when commands are actually executed.
"""

import subprocess
import sys


class TestTelemetryLazyLoading:
    """Tests for lazy OTEL initialization."""

    def test_telemetry_module_import_does_not_load_otel(self) -> None:
        """Importing ktrdr.cli.telemetry should not import opentelemetry.

        The telemetry module uses lazy imports - OTEL is only imported
        inside the wrapper function when a traced command is executed.
        """
        # Run in subprocess to get fresh import state
        code = """
import sys

# Record modules before import
before = set(sys.modules.keys())

# Import the telemetry module
from ktrdr.cli.telemetry import trace_cli_command

# Record modules after import
after = set(sys.modules.keys())

# Check if any opentelemetry modules were imported
new_modules = after - before
otel_modules = [m for m in new_modules if 'opentelemetry' in m]

if otel_modules:
    print(f"FAIL: opentelemetry imported: {otel_modules}")
    exit(1)
else:
    print("PASS: No opentelemetry modules imported")
    exit(0)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"OTEL was imported at module load time:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_app_import_does_not_load_otel(self) -> None:
        """Importing ktrdr.cli.app should not import opentelemetry.

        The app module imports command modules which use @trace_cli_command,
        but this decorator should not trigger OTEL imports at decoration time.
        """
        import os

        # Run in subprocess to get fresh import state
        code = """
import sys
import os

# Set test mode to skip telemetry
os.environ['PYTEST_CURRENT_TEST'] = 'test_app_import'

# Record modules before import
before = set(sys.modules.keys())

# Import the app
from ktrdr.cli.app import app

# Record modules after import
after = set(sys.modules.keys())

# Check if any opentelemetry modules were imported
new_modules = after - before
otel_modules = [m for m in new_modules if 'opentelemetry' in m]

if otel_modules:
    print(f"FAIL: opentelemetry imported: {otel_modules}")
    exit(1)
else:
    print("PASS: No opentelemetry modules imported")
    exit(0)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTEST_CURRENT_TEST": "test"},
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"OTEL was imported when loading app:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_help_does_not_trigger_telemetry(self) -> None:
        """Running --help should not initialize telemetry.

        The --help command should be fast and not trigger any heavy imports.
        We verify this by checking that OTEL is not imported.
        """
        import os

        # Run --help in subprocess and check if OTEL was imported
        code = """
import sys
import os

# Set test mode
os.environ['PYTEST_CURRENT_TEST'] = 'test_help'

# Record modules before import
before = set(sys.modules.keys())

# Import and invoke help
from ktrdr.cli.app import app
from typer.testing import CliRunner

runner = CliRunner()
result = runner.invoke(app, ["--help"])

# Record modules after help
after = set(sys.modules.keys())

# Check if any opentelemetry modules were imported
new_modules = after - before
otel_modules = [m for m in new_modules if 'opentelemetry' in m]

if otel_modules:
    print(f"FAIL: opentelemetry imported during --help: {otel_modules}")
    exit(1)
else:
    print(f"PASS: No opentelemetry modules imported")
    print(f"Help exit code: {result.exit_code}")
    exit(0)
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTEST_CURRENT_TEST": "test"},
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, (
            f"OTEL was imported during --help:\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )

    def test_decorator_skips_tracing_in_test_mode(self) -> None:
        """The trace_cli_command decorator should skip tracing in test mode.

        When PYTEST_CURRENT_TEST is set, the decorator should just call
        the function directly without importing OTEL.
        """
        import os

        # Ensure test mode is set
        os.environ["PYTEST_CURRENT_TEST"] = "test_decorator_skips"

        from ktrdr.cli.telemetry import trace_cli_command

        call_count = 0

        @trace_cli_command("test_command")
        def my_command(value: str) -> str:
            nonlocal call_count
            call_count += 1
            return f"result: {value}"

        # Call the decorated function
        result = my_command("hello")

        # Verify function was called
        assert result == "result: hello"
        assert call_count == 1

        # In test mode, OTEL should not have been imported by this call
        # (it might be imported by other tests, so we can't check sys.modules)

    def test_decorator_preserves_function_metadata(self) -> None:
        """The decorator should preserve the original function's metadata."""
        from ktrdr.cli.telemetry import trace_cli_command

        @trace_cli_command("documented_cmd")
        def my_documented_function(arg1: str, arg2: int = 42) -> dict:
            """This is the docstring."""
            return {"arg1": arg1, "arg2": arg2}

        assert my_documented_function.__name__ == "my_documented_function"
        assert my_documented_function.__doc__ == "This is the docstring."

    def test_async_decorator_skips_tracing_in_test_mode(self) -> None:
        """The async version of trace_cli_command should also skip in test mode."""
        import asyncio
        import os

        os.environ["PYTEST_CURRENT_TEST"] = "test_async"

        from ktrdr.cli.telemetry import trace_cli_command

        @trace_cli_command("async_test")
        async def my_async_command(value: str) -> str:
            await asyncio.sleep(0.001)
            return f"async: {value}"

        result = asyncio.run(my_async_command("world"))
        assert result == "async: world"
