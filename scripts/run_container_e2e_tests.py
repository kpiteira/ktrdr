#!/usr/bin/env python3
"""
Container End-to-End Test Runner

This script orchestrates comprehensive container-based E2E testing including:
- Container startup verification
- API endpoint testing
- CLI functionality testing
- Performance validation
- Integration testing with IB components

Usage:
    python scripts/run_container_e2e_tests.py [options]
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

import requests

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class ContainerE2ETestRunner:
    """Comprehensive container E2E test runner."""

    def __init__(
        self,
        container_name: str = "ktrdr-backend",
        api_base_url: str = "http://localhost:8000",
        wait_timeout: float = 120.0,
    ):
        self.container_name = container_name
        self.api_base_url = api_base_url
        self.wait_timeout = wait_timeout
        self.project_root = Path(__file__).parent.parent

        # Test results
        self.results = {
            "container_status": {},
            "api_tests": {},
            "cli_tests": {},
            "performance_tests": {},
            "overall_success": False,
        }

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
                timeout=10.0,
            )
            return self.container_name in result.stdout
        except Exception as e:
            logger.error(f"Error checking container status: {e}")
            return False

    def wait_for_api_ready(self) -> bool:
        """Wait for API to be ready and responding."""
        logger.info(f"Waiting for API at {self.api_base_url} to be ready...")

        start_time = time.time()
        while time.time() - start_time < self.wait_timeout:
            try:
                response = requests.get(f"{self.api_base_url}/health", timeout=5.0)
                if response.status_code == 200:
                    logger.info("✅ API is ready and responding")
                    return True
            except requests.RequestException:
                pass

            time.sleep(2.0)

        logger.error(f"❌ API not ready after {self.wait_timeout}s")
        return False

    def get_container_logs(self, tail_lines: int = 50) -> str:
        """Get recent container logs."""
        try:
            result = subprocess.run(
                ["docker", "logs", "--tail", str(tail_lines), self.container_name],
                capture_output=True,
                text=True,
                timeout=10.0,
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error getting logs: {e}"

    def run_pytest_command(
        self, test_file: str, markers: list[str], extra_args: list[str] = None
    ) -> tuple[bool, str]:
        """Run a pytest command and return success status and output."""
        cmd = [
            "uv",
            "run",
            "pytest",
            str(self.project_root / test_file),
            "-v",
            "--tb=short",
        ]

        # Add markers
        for marker in markers:
            cmd.append(marker)

        # Add extra arguments
        if extra_args:
            cmd.extend(extra_args)

        logger.info(f"Running: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300.0,  # 5 minutes timeout
                cwd=self.project_root,
            )

            return result.returncode == 0, result.stdout + result.stderr

        except subprocess.TimeoutExpired:
            return False, "Test execution timed out after 5 minutes"
        except Exception as e:
            return False, f"Test execution error: {e}"

    def run_container_status_check(self) -> bool:
        """Run container status validation."""
        logger.info("🔍 Checking container status...")

        # Check if container is running
        if not self.check_container_running():
            logger.error(f"❌ Container {self.container_name} is not running")
            self.results["container_status"]["running"] = False
            return False

        self.results["container_status"]["running"] = True
        logger.info(f"✅ Container {self.container_name} is running")

        # Check if API is responding
        api_ready = self.wait_for_api_ready()
        self.results["container_status"]["api_ready"] = api_ready

        if not api_ready:
            # Get logs for debugging
            logs = self.get_container_logs()
            self.results["container_status"]["logs"] = logs
            logger.error("❌ API is not responding")
            return False

        logger.info("✅ Container status check passed")
        return True

    def run_api_endpoint_tests(self) -> bool:
        """Run API endpoint tests."""
        logger.info("🌐 Running API endpoint tests...")

        success, output = self.run_pytest_command(
            "tests/e2e/test_container_api_endpoints.py",
            ["--run-container-e2e"],
            [f"--api-base-url={self.api_base_url}"],
        )

        self.results["api_tests"]["success"] = success
        self.results["api_tests"]["output"] = output

        if success:
            logger.info("✅ API endpoint tests passed")
        else:
            logger.error("❌ API endpoint tests failed")
            logger.error("Test output:")
            for line in output.split("\n")[-20:]:  # Show last 20 lines
                logger.error(f"  {line}")

        return success

    def run_cli_functionality_tests(self) -> bool:
        """Run CLI functionality tests."""
        logger.info("💻 Running CLI functionality tests...")

        success, output = self.run_pytest_command(
            "tests/e2e/test_container_cli_commands.py",
            ["--run-container-cli"],
            [f"--container-name={self.container_name}"],
        )

        self.results["cli_tests"]["success"] = success
        self.results["cli_tests"]["output"] = output

        if success:
            logger.info("✅ CLI functionality tests passed")
        else:
            logger.error("❌ CLI functionality tests failed")
            logger.error("Test output:")
            for line in output.split("\n")[-20:]:  # Show last 20 lines
                logger.error(f"  {line}")

        return success

    def run_performance_validation(self) -> bool:
        """Run performance validation tests."""
        logger.info("⚡ Running performance validation...")

        # Test API response times
        api_endpoints = ["/health", "/system/status", "/ib/status", "/ib/config"]

        performance_results = {}
        all_passed = True

        for endpoint in api_endpoints:
            try:
                start_time = time.time()
                response = requests.get(f"{self.api_base_url}{endpoint}", timeout=10.0)
                elapsed = time.time() - start_time

                passed = response.status_code == 200 and elapsed < 5.0
                performance_results[endpoint] = {
                    "status_code": response.status_code,
                    "response_time": elapsed,
                    "passed": passed,
                }

                if not passed:
                    all_passed = False

            except Exception as e:
                performance_results[endpoint] = {"error": str(e), "passed": False}
                all_passed = False

        self.results["performance_tests"]["api_endpoints"] = performance_results
        self.results["performance_tests"]["success"] = all_passed

        if all_passed:
            logger.info("✅ Performance validation passed")
        else:
            logger.error("❌ Performance validation failed")
            for endpoint, result in performance_results.items():
                if not result.get("passed", False):
                    logger.error(f"  {endpoint}: {result}")

        return all_passed

    def run_integration_smoke_tests(self) -> bool:
        """Run integration smoke tests."""
        logger.info("🔥 Running integration smoke tests...")

        smoke_tests = []

        # Test 1: IB status endpoint
        try:
            response = requests.get(f"{self.api_base_url}/ib/status", timeout=10.0)
            smoke_tests.append(
                {
                    "name": "IB Status Endpoint",
                    "passed": response.status_code == 200,
                    "details": f"Status: {response.status_code}",
                }
            )
        except Exception as e:
            smoke_tests.append(
                {
                    "name": "IB Status Endpoint",
                    "passed": False,
                    "details": f"Error: {e}",
                }
            )

        # Test 2: System status endpoint
        try:
            response = requests.get(f"{self.api_base_url}/system/status", timeout=10.0)
            smoke_tests.append(
                {
                    "name": "System Status Endpoint",
                    "passed": response.status_code == 200,
                    "details": f"Status: {response.status_code}",
                }
            )
        except Exception as e:
            smoke_tests.append(
                {
                    "name": "System Status Endpoint",
                    "passed": False,
                    "details": f"Error: {e}",
                }
            )

        # Test 3: CLI basic command
        try:
            result = subprocess.run(
                ["docker", "exec", self.container_name, "uv", "run", "ktrdr", "--help"],
                capture_output=True,
                text=True,
                timeout=15.0,
            )
            smoke_tests.append(
                {
                    "name": "CLI Help Command",
                    "passed": result.returncode == 0 and "KTRDR" in result.stdout,
                    "details": f"Return code: {result.returncode}",
                }
            )
        except Exception as e:
            smoke_tests.append(
                {"name": "CLI Help Command", "passed": False, "details": f"Error: {e}"}
            )

        all_passed = all(test["passed"] for test in smoke_tests)
        self.results["integration_smoke_tests"] = smoke_tests

        if all_passed:
            logger.info("✅ Integration smoke tests passed")
        else:
            logger.error("❌ Integration smoke tests failed")
            for test in smoke_tests:
                if not test["passed"]:
                    logger.error(f"  {test['name']}: {test['details']}")

        return all_passed

    def generate_test_report(self) -> str:
        """Generate comprehensive test report."""
        report = []
        report.append("=" * 80)
        report.append("CONTAINER E2E TEST REPORT")
        report.append("=" * 80)
        report.append("")

        # Container status
        report.append("📋 CONTAINER STATUS:")
        status = self.results.get("container_status", {})
        report.append(f"  Container Running: {'✅' if status.get('running') else '❌'}")
        report.append(f"  API Ready: {'✅' if status.get('api_ready') else '❌'}")
        report.append("")

        # API tests
        report.append("🌐 API ENDPOINT TESTS:")
        api_success = self.results.get("api_tests", {}).get("success", False)
        report.append(f"  Status: {'✅ PASSED' if api_success else '❌ FAILED'}")
        report.append("")

        # CLI tests
        report.append("💻 CLI FUNCTIONALITY TESTS:")
        cli_success = self.results.get("cli_tests", {}).get("success", False)
        report.append(f"  Status: {'✅ PASSED' if cli_success else '❌ FAILED'}")
        report.append("")

        # Performance tests
        report.append("⚡ PERFORMANCE VALIDATION:")
        perf_success = self.results.get("performance_tests", {}).get("success", False)
        report.append(f"  Status: {'✅ PASSED' if perf_success else '❌ FAILED'}")

        if (
            "performance_tests" in self.results
            and "api_endpoints" in self.results["performance_tests"]
        ):
            for endpoint, result in self.results["performance_tests"][
                "api_endpoints"
            ].items():
                if "response_time" in result:
                    status = "✅" if result["passed"] else "❌"
                    report.append(
                        f"    {endpoint}: {status} {result['response_time']:.2f}s"
                    )
        report.append("")

        # Integration smoke tests
        if "integration_smoke_tests" in self.results:
            report.append("🔥 INTEGRATION SMOKE TESTS:")
            for test in self.results["integration_smoke_tests"]:
                status = "✅" if test["passed"] else "❌"
                report.append(f"  {test['name']}: {status}")
            report.append("")

        # Overall result
        overall_success = self.results.get("overall_success", False)
        report.append("🎯 OVERALL RESULT:")
        report.append(
            f"  {'🎉 ALL TESTS PASSED' if overall_success else '💥 SOME TESTS FAILED'}"
        )
        report.append("")
        report.append("=" * 80)

        return "\n".join(report)

    def run_all_tests(self) -> bool:
        """Run complete E2E test suite."""
        logger.info("🚀 Starting Container E2E Test Suite...")
        logger.info("=" * 60)

        start_time = time.time()

        # 1. Container status check
        step1_success = self.run_container_status_check()

        # 2. Integration smoke tests (quick validation)
        step2_success = self.run_integration_smoke_tests() if step1_success else False

        # 3. Performance validation
        step3_success = self.run_performance_validation() if step2_success else False

        # 4. API endpoint tests (comprehensive)
        step4_success = self.run_api_endpoint_tests() if step3_success else False

        # 5. CLI functionality tests (comprehensive)
        step5_success = self.run_cli_functionality_tests() if step4_success else False

        # Calculate overall success
        overall_success = all(
            [step1_success, step2_success, step3_success, step4_success, step5_success]
        )

        self.results["overall_success"] = overall_success

        # Generate and display report
        elapsed = time.time() - start_time
        logger.info("")
        logger.info("=" * 60)
        logger.info(f"Container E2E tests completed in {elapsed:.1f}s")
        logger.info("=" * 60)

        report = self.generate_test_report()
        print(report)

        return overall_success


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run container E2E tests")
    parser.add_argument(
        "--container-name",
        default="ktrdr-backend",
        help="Name of the container to test",
    )
    parser.add_argument(
        "--api-base-url",
        default="http://localhost:8000/api/v1",
        help="Base URL for API testing",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=120.0,
        help="Timeout for waiting for services to be ready",
    )
    parser.add_argument("--output-json", help="Output test results to JSON file")

    args = parser.parse_args()

    # Create test runner
    runner = ContainerE2ETestRunner(
        container_name=args.container_name,
        api_base_url=args.api_base_url,
        wait_timeout=args.wait_timeout,
    )

    # Run tests
    success = runner.run_all_tests()

    # Save JSON output if requested
    if args.output_json:
        with open(args.output_json, "w") as f:
            json.dump(runner.results, f, indent=2)
        logger.info(f"Test results saved to {args.output_json}")

    # Exit with appropriate code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
