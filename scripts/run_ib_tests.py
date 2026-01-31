#!/usr/bin/env python3
"""
Comprehensive IB Test Runner

Runs all IB-related tests in a systematic way with proper setup and teardown.
Provides different test modes for development, CI, and production validation.
"""

import argparse
import asyncio
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

try:
    from ktrdr.config.settings import get_ib_settings
    from ktrdr.logging import get_logger
except ImportError as e:
    print(f"Error importing ktrdr modules: {e}")
    print("Make sure you're running this from the correct directory")
    sys.exit(1)

logger = get_logger(__name__)


class IbTestRunner:
    """
    Comprehensive test runner for IB components.

    Supports different test modes:
    - unit: Run only unit tests (no IB required)
    - integration: Run integration tests (requires IB Gateway)
    - stress: Run stress tests (requires IB Gateway)
    - all: Run all tests
    """

    def __init__(
        self,
        test_mode: str = "unit",
        verbose: bool = False,
        fail_fast: bool = False,
        parallel: bool = False,
        output_file: Optional[str] = None,
    ):
        """
        Initialize test runner.

        Args:
            test_mode: Test mode ('unit', 'integration', 'stress', 'all')
            verbose: Enable verbose output
            fail_fast: Stop on first failure
            parallel: Run tests in parallel where possible
            output_file: File to save test results
        """
        self.test_mode = test_mode
        self.verbose = verbose
        self.fail_fast = fail_fast
        self.parallel = parallel
        self.output_file = output_file

        self.project_root = project_root
        self.test_results: dict[str, Any] = {
            "start_time": datetime.now().isoformat(),
            "test_mode": test_mode,
            "results": {},
            "summary": {},
        }

    async def run_tests(self) -> bool:
        """
        Run tests based on the specified mode.

        Returns:
            True if all tests passed, False otherwise
        """
        logger.info(f"🧪 Starting IB test suite in '{self.test_mode}' mode")

        try:
            # Pre-test setup
            await self._setup_tests()

            # Run tests based on mode
            if self.test_mode == "unit":
                success = await self._run_unit_tests()
            elif self.test_mode == "integration":
                success = await self._run_integration_tests()
            elif self.test_mode == "stress":
                success = await self._run_stress_tests()
            elif self.test_mode == "all":
                success = await self._run_all_tests()
            else:
                raise ValueError(f"Unknown test mode: {self.test_mode}")

            # Post-test cleanup
            await self._cleanup_tests()

            # Generate report
            self._generate_report()

            return success

        except Exception as e:
            logger.error(f"Test runner failed: {e}")
            self.test_results["error"] = str(e)
            return False

    async def _setup_tests(self):
        """Set up test environment."""
        logger.info("🔧 Setting up test environment")

        # Check if IB Gateway is required and available
        if self.test_mode in ["integration", "stress", "all"]:
            await self._check_ib_availability()

        # Clean up any existing test artifacts
        await self._cleanup_test_artifacts()

        # Set up test data directories
        test_data_dir = self.project_root / "test_data"
        test_data_dir.mkdir(exist_ok=True)

        logger.info("✅ Test environment setup complete")

    async def _check_ib_availability(self):
        """Check if IB Gateway/TWS is available."""
        logger.info("🔍 Checking IB Gateway availability")

        try:
            # Try to get IB config
            config = get_ib_settings()
            logger.info(f"IB config found: {config.host}:{config.port}")

            # Try to connect briefly to verify availability
            from ktrdr.data.ib_connection_pool import get_connection_pool

            pool = await get_connection_pool()
            if not pool._running:
                await pool.start()

            # Try to get pool status
            status = pool.get_pool_status()
            if not status.get("running"):
                raise Exception("Connection pool not running")

            logger.info("✅ IB Gateway is available")

        except Exception as e:
            logger.error(f"❌ IB Gateway not available: {e}")
            logger.error(
                "Please ensure IB Gateway/TWS is running before running integration tests"
            )
            raise

    async def _cleanup_test_artifacts(self):
        """Clean up test artifacts from previous runs."""
        logger.debug("🧹 Cleaning up test artifacts")

        # Remove test metrics files
        test_files = ["test_metrics.json", "test_client_ids.json", "test_cache.json"]

        for file_name in test_files:
            file_path = self.project_root / "data" / file_name
            if file_path.exists():
                file_path.unlink()
                logger.debug(f"Removed {file_path}")

    async def _run_unit_tests(self) -> bool:
        """Run unit tests."""
        logger.info("🧪 Running unit tests")

        test_files = [
            "tests/data/test_ib_connection_pool_unified.py",
            "tests/data/test_ib_metrics_collector.py",
            "tests/data/test_ib_client_id_registry.py",
            "tests/data/test_ib_data_fetcher_unified.py",
            "tests/data/test_ib_symbol_validator_unified.py",
            "tests/data/test_ib_pace_manager.py",
        ]

        return await self._run_pytest_tests("unit", test_files)

    async def _run_integration_tests(self) -> bool:
        """Run integration tests."""
        logger.info("🔗 Running integration tests")

        test_files = ["tests/integration/test_ib_unified_integration.py"]

        return await self._run_pytest_tests(
            "integration", test_files, extra_args=["--run-integration"]
        )

    async def _run_stress_tests(self) -> bool:
        """Run stress tests."""
        logger.info("💪 Running stress tests")

        test_files = ["tests/integration/test_ib_unified_integration.py"]

        return await self._run_pytest_tests(
            "stress",
            test_files,
            extra_args=["--run-integration", "--run-stress", "-m", "stress"],
        )

    async def _run_all_tests(self) -> bool:
        """Run all tests in sequence."""
        logger.info("🎯 Running all tests")

        # Run unit tests first
        unit_success = await self._run_unit_tests()
        if not unit_success and self.fail_fast:
            logger.error("❌ Unit tests failed, stopping due to fail-fast mode")
            return False

        # Run integration tests
        integration_success = await self._run_integration_tests()
        if not integration_success and self.fail_fast:
            logger.error("❌ Integration tests failed, stopping due to fail-fast mode")
            return False

        # Run stress tests if requested
        stress_success = True
        if self.test_mode == "all":
            stress_success = await self._run_stress_tests()

        return unit_success and integration_success and stress_success

    async def _run_pytest_tests(
        self,
        test_category: str,
        test_files: list[str],
        extra_args: Optional[list[str]] = None,
    ) -> bool:
        """Run pytest tests for specified files."""
        if extra_args is None:
            extra_args = []

        # Build pytest command
        cmd = ["uv", "run", "pytest"]

        # Add test files
        for test_file in test_files:
            test_path = self.project_root / test_file
            if test_path.exists():
                cmd.append(str(test_path))
            else:
                logger.warning(f"Test file not found: {test_path}")

        # Add pytest options
        cmd.extend(
            [
                "-v",  # Verbose output
                "--tb=short",  # Short traceback format
                "--strict-markers",  # Strict marker checking
            ]
        )

        if self.fail_fast:
            cmd.append("-x")  # Stop on first failure

        if self.parallel:
            cmd.extend(["-n", "auto"])  # Parallel execution

        # Add extra arguments
        cmd.extend(extra_args)

        # Add output file for this test category
        if self.output_file:
            output_path = (
                Path(self.output_file).parent
                / f"{test_category}_{Path(self.output_file).name}"
            )
            cmd.extend(["--junitxml", str(output_path)])

        logger.info(f"Running command: {' '.join(cmd)}")

        # Run tests
        start_time = time.time()

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout per test category
            )

            duration = time.time() - start_time

            # Store results
            self.test_results["results"][test_category] = {
                "success": result.returncode == 0,
                "duration": duration,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "command": " ".join(cmd),
            }

            if result.returncode == 0:
                logger.info(f"✅ {test_category} tests passed ({duration:.2f}s)")
                return True
            else:
                logger.error(f"❌ {test_category} tests failed ({duration:.2f}s)")
                if self.verbose:
                    logger.error(f"STDOUT:\n{result.stdout}")
                    logger.error(f"STDERR:\n{result.stderr}")
                return False

        except subprocess.TimeoutExpired:
            logger.error(f"❌ {test_category} tests timed out")
            self.test_results["results"][test_category] = {
                "success": False,
                "error": "Timeout",
                "duration": 300,
            }
            return False

        except Exception as e:
            logger.error(f"❌ Error running {test_category} tests: {e}")
            self.test_results["results"][test_category] = {
                "success": False,
                "error": str(e),
                "duration": time.time() - start_time,
            }
            return False

    async def _cleanup_tests(self):
        """Clean up after tests."""
        logger.info("🧹 Cleaning up after tests")

        try:
            # Stop any running services
            from ktrdr.data.ib_connection_pool import get_connection_pool
            from ktrdr.data.ib_health_monitor import get_health_monitor

            # Stop connection pool
            try:
                pool = await get_connection_pool()
                if pool._running:
                    await pool.stop()
                    logger.debug("Connection pool stopped")
            except Exception as e:
                logger.debug(f"Error stopping connection pool: {e}")

            # Stop health monitor
            try:
                monitor = get_health_monitor()
                if monitor._running:
                    await monitor.stop()
                    logger.debug("Health monitor stopped")
            except Exception as e:
                logger.debug(f"Error stopping health monitor: {e}")

            # Clean up test artifacts
            await self._cleanup_test_artifacts()

            logger.info("✅ Cleanup complete")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")

    def _generate_report(self):
        """Generate test report."""
        self.test_results["end_time"] = datetime.now().isoformat()

        # Calculate summary
        total_tests = len(self.test_results["results"])
        passed_tests = sum(
            1
            for result in self.test_results["results"].values()
            if result.get("success")
        )
        failed_tests = total_tests - passed_tests
        total_duration = sum(
            result.get("duration", 0)
            for result in self.test_results["results"].values()
        )

        self.test_results["summary"] = {
            "total_test_categories": total_tests,
            "passed_categories": passed_tests,
            "failed_categories": failed_tests,
            "success_rate": (
                (passed_tests / total_tests * 100) if total_tests > 0 else 0
            ),
            "total_duration": total_duration,
        }

        # Print summary
        logger.info("📊 Test Summary:")
        logger.info(f"  Total categories: {total_tests}")
        logger.info(f"  Passed: {passed_tests}")
        logger.info(f"  Failed: {failed_tests}")
        logger.info(
            f"  Success rate: {self.test_results['summary']['success_rate']:.1f}%"
        )
        logger.info(f"  Total duration: {total_duration:.2f}s")

        # Save to file if requested
        if self.output_file:
            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                json.dump(self.test_results, f, indent=2)

            logger.info(f"📄 Test results saved to {output_path}")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="IB Test Runner")

    parser.add_argument(
        "mode",
        choices=["unit", "integration", "stress", "all"],
        help="Test mode to run",
    )

    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )

    parser.add_argument(
        "--fail-fast", "-x", action="store_true", help="Stop on first failure"
    )

    parser.add_argument(
        "--parallel", "-n", action="store_true", help="Run tests in parallel"
    )

    parser.add_argument("--output", "-o", help="Output file for test results")

    args = parser.parse_args()

    # Create test runner
    runner = IbTestRunner(
        test_mode=args.mode,
        verbose=args.verbose,
        fail_fast=args.fail_fast,
        parallel=args.parallel,
        output_file=args.output,
    )

    # Run tests
    success = await runner.run_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
