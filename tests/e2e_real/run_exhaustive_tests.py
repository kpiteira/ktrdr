#!/usr/bin/env python3
"""
Exhaustive Real IB Connection Resilience Test Runner

This script runs comprehensive, exhaustive tests of the connection resilience
implementation with real IB Gateway connections. These tests validate that
our system is bulletproof under all conditions.

Usage:
    python run_exhaustive_tests.py [options]

Options:
    --ib-host HOST      IB Gateway host (default: 127.0.0.1)
    --ib-port PORT      IB Gateway port (default: 4003)
    --test-level LEVEL  Test level: basic, standard, exhaustive (default: standard)
    --verbose           Verbose output
    --report            Generate detailed test report
"""

import sys
import argparse
import subprocess
import time
import json
import httpx
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


class ExhaustiveTestRunner:
    """Runner for exhaustive resilience tests."""

    def __init__(
        self,
        ib_host: str = "127.0.0.1",
        ib_port: int = 4003,
        api_base_url: str = "http://localhost:8000",
        verbose: bool = False,
    ):
        self.ib_host = ib_host
        self.ib_port = ib_port
        self.api_base_url = api_base_url
        self.verbose = verbose
        self.test_results = []

    def check_prerequisites(self) -> Dict[str, Any]:
        """Check that all prerequisites are met for testing."""
        print("🔍 Checking prerequisites...")

        results = {
            "api_server": False,
            "ib_gateway": False,
            "backend_container": False,
            "test_environment": False,
        }

        # Check API server
        try:
            client = httpx.Client(base_url=self.api_base_url, timeout=10.0)
            response = client.get("/api/v1/health")
            results["api_server"] = response.status_code == 200
            client.close()
            print(
                f"  ✅ API server: {'running' if results['api_server'] else 'not available'}"
            )
        except Exception as e:
            print(f"  ❌ API server: not available ({e})")

        # Check IB Gateway connectivity
        try:
            client = httpx.Client(base_url=self.api_base_url, timeout=10.0)
            response = client.get("/api/v1/ib/health")

            if response.status_code == 200:
                data = response.json()
                results["ib_gateway"] = data.get("data", {}).get("healthy", False)
            else:
                results["ib_gateway"] = False

            client.close()
            print(
                f"  {'✅' if results['ib_gateway'] else '⚠️ '} IB Gateway: {'connected' if results['ib_gateway'] else 'not connected'}"
            )
        except Exception as e:
            print(f"  ❌ IB Gateway: not available ({e})")

        # Check backend container
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    "name=ktrdr-backend",
                    "--format",
                    "{{.Names}}",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            results["backend_container"] = "ktrdr-backend" in result.stdout
            print(
                f"  {'✅' if results['backend_container'] else '❌'} Backend container: {'running' if results['backend_container'] else 'not running'}"
            )
        except Exception as e:
            print(f"  ❌ Backend container: cannot check ({e})")

        # Check test environment
        test_dir = Path(__file__).parent
        required_files = [
            "test_exhaustive_resilience.py",
            "test_exhaustive_api_cli_resilience.py",
            "conftest.py",
        ]

        missing_files = []
        for file in required_files:
            if not (test_dir / file).exists():
                missing_files.append(file)

        results["test_environment"] = len(missing_files) == 0
        print(
            f"  {'✅' if results['test_environment'] else '❌'} Test environment: {'ready' if results['test_environment'] else f'missing {missing_files}'}"
        )

        return results

    def run_test_suite(self, test_level: str = "standard") -> Dict[str, Any]:
        """Run the appropriate test suite based on level."""
        print(f"\n🚀 Running {test_level} resilience tests...")

        test_configs = {
            "basic": {
                "markers": "not exhaustive_resilience",
                "description": "Basic resilience tests (IB available/unavailable)",
            },
            "standard": {
                "markers": "real_ib",
                "description": "Standard real IB tests with resilience validation",
            },
            "exhaustive": {
                "markers": "exhaustive_resilience",
                "description": "Exhaustive stress tests with real IB (comprehensive)",
            },
        }

        config = test_configs.get(test_level, test_configs["standard"])

        # Build pytest command
        cmd = [
            "uv",
            "run",
            "pytest",
            str(Path(__file__).parent),
            "--real-ib",
            f"--ib-host={self.ib_host}",
            f"--ib-port={self.ib_port}",
            f"--api-base-url={self.api_base_url}",
            "-v",
        ]

        if test_level != "basic":
            cmd.extend(["-m", config["markers"]])

        if self.verbose:
            cmd.append("-s")

        print(f"📋 Test configuration: {config['description']}")
        print(f"🔧 Command: {' '.join(cmd)}")

        start_time = time.time()

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=1800
            )  # 30 minute timeout
            elapsed = time.time() - start_time

            # Parse pytest output for results
            test_results = self._parse_pytest_output(result.stdout, result.stderr)

            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "elapsed": elapsed,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_results": test_results,
            }

        except subprocess.TimeoutExpired:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "returncode": -1,
                "elapsed": elapsed,
                "error": "Test suite timed out after 30 minutes",
                "test_results": {"timeout": True},
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "success": False,
                "returncode": -2,
                "elapsed": elapsed,
                "error": str(e),
                "test_results": {"error": str(e)},
            }

    def _parse_pytest_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """Parse pytest output to extract test results."""
        results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "warnings": 0,
            "async_errors_detected": False,
            "failed_tests": [],
            "warning_tests": [],
        }

        # Look for test summary
        lines = stdout.split("\n")

        for line in lines:
            # Parse test results summary
            if "passed" in line and (
                "failed" in line or "error" in line or "skipped" in line
            ):
                # Parse summary line like "5 failed, 10 passed, 2 skipped in 45.2s"
                words = line.split()
                for i, word in enumerate(words):
                    if word == "passed" and i > 0:
                        results["passed"] = int(words[i - 1])
                    elif word == "failed" and i > 0:
                        results["failed"] = int(words[i - 1])
                    elif word == "skipped" and i > 0:
                        results["skipped"] = int(words[i - 1])
                    elif word == "error" and i > 0:
                        results["errors"] = int(words[i - 1])

            # Check for async/coroutine errors (critical)
            if any(
                term in line.lower()
                for term in ["runtimewarning", "coroutine", "was never awaited"]
            ):
                results["async_errors_detected"] = True

            # Collect failed test names
            if "FAILED" in line and "::" in line:
                test_name = line.split("FAILED")[0].strip()
                results["failed_tests"].append(test_name)

            # Count warnings
            if "warning" in line.lower():
                results["warnings"] += 1

        results["total_tests"] = (
            results["passed"]
            + results["failed"]
            + results["skipped"]
            + results["errors"]
        )

        return results

    def generate_report(
        self, test_results: Dict[str, Any], output_file: str = None
    ) -> str:
        """Generate a detailed test report."""
        report_time = datetime.now().isoformat()

        report = f"""
# Exhaustive IB Connection Resilience Test Report

**Report Generated:** {report_time}
**Test Configuration:**
- IB Host: {self.ib_host}:{self.ib_port}
- API Base URL: {self.api_base_url}

## Test Results Summary

**Overall Result:** {'✅ PASSED' if test_results['success'] else '❌ FAILED'}
**Execution Time:** {test_results['elapsed']:.2f} seconds
**Return Code:** {test_results['returncode']}

### Test Statistics
"""

        if "test_results" in test_results and isinstance(
            test_results["test_results"], dict
        ):
            stats = test_results["test_results"]

            report += f"""
- **Total Tests:** {stats.get('total_tests', 0)}
- **Passed:** {stats.get('passed', 0)} ✅
- **Failed:** {stats.get('failed', 0)} {'❌' if stats.get('failed', 0) > 0 else '✅'}
- **Skipped:** {stats.get('skipped', 0)}
- **Errors:** {stats.get('errors', 0)} {'❌' if stats.get('errors', 0) > 0 else '✅'}
- **Warnings:** {stats.get('warnings', 0)}

### Critical Checks
- **Async/Coroutine Errors:** {'❌ DETECTED' if stats.get('async_errors_detected') else '✅ NONE DETECTED'}
"""

            if stats.get("failed_tests"):
                report += f"""
### Failed Tests
"""
                for test in stats["failed_tests"]:
                    report += f"- {test}\n"

        if test_results.get("error"):
            report += f"""
### Error Details
```
{test_results['error']}
```
"""

        # Add recommendations
        report += """
## Recommendations

### If Tests Passed ✅
Your IB connection resilience implementation is working correctly:
1. All 6 phases of resilience are functioning
2. No async/coroutine errors detected
3. Connection pool is handling stress appropriately
4. System recovers gracefully from connection issues

### If Tests Failed ❌
Review the following areas:
1. **Async Errors:** Check for RuntimeWarning or coroutine errors in logs
2. **Connection Pool:** Verify pool configuration and lifecycle management
3. **IB Gateway:** Ensure IB Gateway is running and accessible
4. **Network:** Check network connectivity and firewall settings

### Next Steps
1. **Production Deployment:** Tests validate production readiness
2. **Monitoring:** Set up monitoring for resilience score endpoint
3. **Alerting:** Configure alerts for connection pool health
4. **Documentation:** Update operational procedures
"""

        if output_file:
            with open(output_file, "w") as f:
                f.write(report)
            print(f"📄 Report saved to: {output_file}")

        return report

    def run_comprehensive_test(
        self, test_level: str = "standard", generate_report: bool = False
    ) -> bool:
        """Run comprehensive test suite with full validation."""
        print("🎯 EXHAUSTIVE IB CONNECTION RESILIENCE TESTING")
        print("=" * 60)

        # Step 1: Prerequisites
        prereqs = self.check_prerequisites()

        critical_prereqs = ["api_server", "test_environment"]
        missing_critical = [k for k in critical_prereqs if not prereqs[k]]

        if missing_critical:
            print(f"\n❌ Critical prerequisites missing: {missing_critical}")
            print("Cannot proceed with testing.")
            return False

        if not prereqs["ib_gateway"]:
            print("\n⚠️  IB Gateway not connected - will test graceful handling")
            if test_level == "exhaustive":
                print("❌ Exhaustive tests require IB Gateway connection")
                return False
        else:
            print("\n✅ IB Gateway connected - will test full resilience")

        # Step 2: Run tests
        print(f"\n🚀 Starting {test_level} test suite...")
        test_results = self.run_test_suite(test_level)

        # Step 3: Analyze results
        print("\n📊 RESULTS ANALYSIS")
        print("-" * 30)

        success = test_results["success"]
        elapsed = test_results["elapsed"]

        print(f"Overall Result: {'✅ PASSED' if success else '❌ FAILED'}")
        print(f"Execution Time: {elapsed:.2f} seconds")

        if "test_results" in test_results:
            stats = test_results["test_results"]
            if isinstance(stats, dict):
                total = stats.get("total_tests", 0)
                passed = stats.get("passed", 0)
                failed = stats.get("failed", 0)

                if total > 0:
                    success_rate = (passed / total) * 100
                    print(f"Success Rate: {success_rate:.1f}% ({passed}/{total})")

                # CRITICAL: Check for async errors
                if stats.get("async_errors_detected"):
                    print("🚨 CRITICAL: Async/coroutine errors detected!")
                    print("This indicates the original bug may still exist.")
                    success = False
                else:
                    print("✅ No async/coroutine errors detected")

        # Step 4: Generate report
        if generate_report:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"resilience_test_report_{timestamp}.md"
            self.generate_report(test_results, report_file)

        # Step 5: Final validation
        if success:
            print("\n🎉 RESILIENCE VALIDATION SUCCESSFUL!")
            print("Your IB connection implementation is bulletproof.")
        else:
            print("\n❌ RESILIENCE VALIDATION FAILED!")
            print("Review test output and fix issues before production deployment.")

        return success


def main():
    parser = argparse.ArgumentParser(description="Run exhaustive IB resilience tests")
    parser.add_argument("--ib-host", default="127.0.0.1", help="IB Gateway host")
    parser.add_argument("--ib-port", type=int, default=4003, help="IB Gateway port")
    parser.add_argument(
        "--api-base-url", default="http://localhost:8000", help="API base URL"
    )
    parser.add_argument(
        "--test-level",
        choices=["basic", "standard", "exhaustive"],
        default="standard",
        help="Test level",
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--report", action="store_true", help="Generate test report")

    args = parser.parse_args()

    runner = ExhaustiveTestRunner(
        ib_host=args.ib_host,
        ib_port=args.ib_port,
        api_base_url=args.api_base_url,
        verbose=args.verbose,
    )

    success = runner.run_comprehensive_test(
        test_level=args.test_level, generate_report=args.report
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
