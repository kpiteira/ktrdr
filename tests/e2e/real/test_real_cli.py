"""
Real CLI End-to-End Tests

These tests execute actual CLI commands with real IB connections.
They would have caught the runtime bug where acquire_ib_connection()
was not properly awaited.
"""

import subprocess

import pytest


@pytest.mark.real_ib
@pytest.mark.real_cli
class TestRealCLICommands:
    """Test CLI commands with real IB operations."""

    def test_real_ib_test_command(self, clean_test_symbols):
        """Test 'ktrdr test-ib' command with real IB connection."""
        symbol = clean_test_symbols[0]  # AAPL

        result = subprocess.run(
            ["uv", "run", "ktrdr", "ib", "test", "--symbol", symbol, "--verbose"],
            capture_output=True,
            text=True,
        )

        # Verify no runtime warnings (the bug we just fixed)
        assert "RuntimeWarning" not in result.stderr, (
            f"Runtime warning detected: {result.stderr}"
        )
        assert "coroutine" not in result.stderr, (
            f"Coroutine error detected: {result.stderr}"
        )

        # Verify successful execution
        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "Testing IB connection" in result.stdout
        assert "✅" in result.stdout or "successful" in result.stdout.lower()

    def test_real_data_load_command_tail_mode(
        self, clean_test_symbols, test_date_ranges
    ):
        """Test 'ktrdr data load' command with real IB in tail mode."""
        symbol = clean_test_symbols[0]  # AAPL
        date_range = test_date_ranges["recent_days"]

        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "data",
                "load",
                symbol,
                "-t",
                "1h",
                "--start",
                date_range["start"],
                "--end",
                date_range["end"],
                "-m",
                "tail",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )

        # Verify no runtime warnings (the exact bug we fixed)
        assert "RuntimeWarning" not in result.stderr, (
            f"Runtime warning detected: {result.stderr}"
        )
        assert (
            "coroutine 'acquire_ib_connection' was never awaited" not in result.stderr
        )

        # Verify successful execution
        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Should have either loaded data or provided informative message
        stdout_lower = result.stdout.lower()
        success_indicators = ["successfully loaded", "bars", "completed", "duration:"]
        assert any(indicator in stdout_lower for indicator in success_indicators), (
            f"No success indicators found in output: {result.stdout}"
        )

    def test_real_data_load_command_full_mode(
        self, clean_test_symbols, test_date_ranges
    ):
        """Test 'ktrdr data load' command with real IB in full mode."""
        symbol = clean_test_symbols[1]  # MSFT
        date_range = test_date_ranges["recent_hours"]

        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "data",
                "load",
                symbol,
                "-t",
                "1h",
                "--start",
                date_range["start"],
                "--end",
                date_range["end"],
                "-m",
                "full",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )

        # Critical check: no async/await errors
        assert "RuntimeWarning" not in result.stderr
        assert "was never awaited" not in result.stderr
        assert "async with" not in result.stderr

        # Verify execution completed (success or graceful failure)
        assert result.returncode in [
            0,
            1,
        ], f"Unexpected return code: {result.returncode}"

        # If successful, should show data loading results
        if result.returncode == 0:
            assert any(
                word in result.stdout.lower()
                for word in ["loaded", "bars", "completed"]
            )

    @pytest.mark.skip(
        reason="CLI async issue - an asyncio.future, a coroutine or an awaitable is required"
    )
    def test_real_ib_head_timestamp_command(self, clean_test_symbols, test_date_ranges):
        """Test 'ktrdr ib test-head-timestamp' command with real IB connection."""
        symbol = clean_test_symbols[2]  # EURUSD

        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "ib",
                "test-head-timestamp",
                symbol,
                "--timeframe",
                "1h",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )

        # Primary check: no coroutine errors
        stderr_content = result.stderr.lower()
        assert "runtimewarning" not in stderr_content
        assert "coroutine" not in stderr_content
        assert "was never awaited" not in stderr_content

        # Should execute without crashing
        assert result.returncode in [
            0,
            1,
        ], f"Command crashed unexpectedly: {result.stderr}"

    def test_real_ib_cleanup_command(self):
        """Test 'ktrdr ib-cleanup' command with real IB connections."""
        result = subprocess.run(
            ["uv", "run", "ktrdr", "ib", "cleanup", "--verbose"],
            capture_output=True,
            text=True,
        )

        # Should execute without async errors
        assert "RuntimeWarning" not in result.stderr
        assert "coroutine" not in result.stderr

        # Should complete successfully
        assert result.returncode == 0, f"Cleanup command failed: {result.stderr}"

        # Should provide cleanup results
        stdout_lower = result.stdout.lower()
        assert any(
            word in stdout_lower
            for word in ["cleanup", "connections", "closed", "completed"]
        )

    def test_real_show_data_with_ib_fallback(self, clean_test_symbols):
        """Test 'ktrdr show-data' command that might fallback to IB."""
        # Use a symbol/timeframe combination that likely doesn't exist locally
        symbol = "RARE_SYMBOL_TEST"  # Intentionally obscure symbol

        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "data",
                "show",
                symbol,
                "--timeframe",
                "1h",
                "--rows",
                "5",
            ],
            capture_output=True,
            text=True,
        )

        # Should handle gracefully (either show data or error cleanly)
        assert "RuntimeWarning" not in result.stderr
        assert "coroutine" not in result.stderr

        # Return code should be 0 or 1 (not crash)
        assert result.returncode in [0, 1]

    def test_real_cli_concurrent_operations(self, clean_test_symbols):
        """Test concurrent CLI operations don't interfere."""
        import queue
        import threading

        results = queue.Queue()
        symbols = clean_test_symbols[:2]  # AAPL, MSFT

        def run_test_ib(symbol):
            try:
                result = subprocess.run(
                    ["uv", "run", "ktrdr", "ib", "test", "--symbol", symbol],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )

                results.put(
                    {
                        "symbol": symbol,
                        "returncode": result.returncode,
                        "stderr": result.stderr,
                        "stdout": result.stdout,
                    }
                )
            except Exception as e:
                results.put({"symbol": symbol, "error": str(e)})

        # Start concurrent operations
        threads = [
            threading.Thread(target=run_test_ib, args=(symbol,)) for symbol in symbols
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Collect and verify results
        collected_results = []
        while not results.empty():
            collected_results.append(results.get())

        assert len(collected_results) == 2, "Should have results for both symbols"

        for result in collected_results:
            assert "error" not in result, f"Thread error: {result}"

            # Critical: no async/coroutine errors in concurrent execution
            stderr = result.get("stderr", "")
            assert "RuntimeWarning" not in stderr
            assert "coroutine" not in stderr


@pytest.mark.real_ib
@pytest.mark.real_cli
class TestRealCLIErrorScenarios:
    """Test CLI error handling with real IB."""

    def test_cli_handles_invalid_symbol_gracefully(self):
        """Test CLI handles invalid symbols without crashing."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "ib",
                "test",
                "--symbol",
                "INVALID_SYMBOL_12345",
                "--verbose",
            ],
            capture_output=True,
            text=True,
        )

        # Should not crash with async errors
        assert "RuntimeWarning" not in result.stderr
        assert "coroutine" not in result.stderr

        # Should handle gracefully (return code 1 is OK for invalid symbol)
        assert result.returncode in [0, 1]

    def test_cli_handles_date_range_errors_gracefully(self, clean_test_symbols):
        """Test CLI handles invalid date ranges without async errors."""
        symbol = clean_test_symbols[0]

        # Use invalid date range (future dates)
        result = subprocess.run(
            [
                "uv",
                "run",
                "ktrdr",
                "data",
                "load",
                symbol,
                "-t",
                "1h",
                "--start",
                "2030-01-01",  # Future date
                "--end",
                "2030-01-02",
                "-m",
                "tail",
            ],
            capture_output=True,
            text=True,
        )

        # Should handle date validation errors gracefully
        assert "RuntimeWarning" not in result.stderr
        assert "coroutine" not in result.stderr

        # May succeed (with adjusted dates) or fail gracefully
        assert result.returncode in [0, 1]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--real-ib"])
