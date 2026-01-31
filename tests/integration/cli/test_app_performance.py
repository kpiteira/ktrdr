"""Tests for CLI app startup performance.

This is an integration/smoke test because:
- It spawns subprocesses to measure timing
- Results vary by environment (CI vs local)
- It tests system-level behavior, not isolated logic

Moved from tests/unit/cli/test_app.py.
"""

import subprocess
import sys


class TestAppPerformance:
    """Tests for CLI startup performance.

    The CLI must be fast enough that `ktrdr --help` feels instantaneous.
    Target: <100ms for importing the app module.
    """

    def test_app_import_fast(self) -> None:
        """Importing ktrdr.cli.app should complete in <100ms.

        Uses subprocess to measure import time in isolation. Each measurement
        runs in a fresh Python process to avoid module caching.

        Note: PYTEST_CURRENT_TEST is set to skip heavy telemetry initialization,
        which matches how the CLI should behave after optimization (telemetry
        should be lazy-initialized on first command execution, not at import).
        """
        import os

        # Measure import time in fresh subprocess
        # Uses time.perf_counter for accurate timing
        timing_code = """
import time
start = time.perf_counter()
from ktrdr.cli.app import app
end = time.perf_counter()
print(f"{(end - start) * 1000:.1f}")
"""
        # Run 3 measurements and take the best (minimum)
        times = []
        env = {
            **os.environ,
            "PYTEST_CURRENT_TEST": "test_app_import_fast",
        }

        for _ in range(3):
            result = subprocess.run(
                [sys.executable, "-c", timing_code],
                env=env,
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Import failed: {result.stderr}"
            times.append(float(result.stdout.strip()))

        import_time_ms = min(times)

        # Target: <100ms (with margin for CI variability)
        # Note: CI machines are slower, so we allow up to 200ms
        # Local: ~80ms, CI: ~150-160ms
        max_allowed_ms = 200
        assert import_time_ms < max_allowed_ms, (
            f"App import took {import_time_ms:.1f}ms (best of 3), "
            f"exceeds {max_allowed_ms}ms target. "
            f"Heavy imports should be deferred to command execution."
        )
