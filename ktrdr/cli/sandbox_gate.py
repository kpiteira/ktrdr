"""Startability Gate for sandbox instances.

This module provides health checking to validate that a sandbox instance
is fully operational before declaring it ready for use.

The gate performs four sequential checks:
1. Database - accepts TCP connections
2. Backend - /api/v1/health returns 200
3. Workers - at least 4 workers registered
4. Observability - Jaeger UI responding

Each check polls with a timeout until it passes or the deadline is reached.
"""

import asyncio
import socket
import time
from dataclasses import dataclass, field
from enum import Enum

import httpx


class CheckStatus(Enum):
    """Status of a health check."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: CheckStatus
    message: str = ""
    details: str = ""


@dataclass
class GateResult:
    """Overall Startability Gate result."""

    passed: bool
    checks: list[CheckResult] = field(default_factory=list)
    duration_seconds: float = 0.0


class StartabilityGate:
    """Validates that a sandbox instance is ready for use.

    The gate runs health checks against the sandbox services:
    - Database: TCP connection acceptance
    - Backend: /api/v1/health endpoint returns 200
    - Workers: /api/v1/workers shows 4+ registered workers
    - Observability: Jaeger UI is responding

    Checks are run sequentially with dependencies:
    - Workers check is skipped if backend check fails
    """

    def __init__(self, api_port: int, db_port: int, timeout: float = 120.0):
        """Initialize the gate with port configuration.

        Args:
            api_port: Port for the backend API (e.g., 8001).
            db_port: Port for the database (e.g., 5433).
            timeout: Maximum time in seconds to wait for all checks.
        """
        self.api_port = api_port
        self.db_port = db_port
        self.timeout = timeout
        self.poll_interval = 2.0

    async def check(self) -> GateResult:
        """Run all health checks.

        Returns:
            GateResult with overall pass/fail and individual check results.
        """
        start = time.time()
        checks: list[CheckResult] = []
        deadline = start + self.timeout

        # Check database first (backend depends on it)
        db_result = await self._poll_until(self._check_database, "Database", deadline)
        checks.append(db_result)

        # Check backend health
        backend_result = await self._poll_until(
            self._check_backend_health, "Backend", deadline
        )
        checks.append(backend_result)

        # Check workers registered (only if backend is up)
        if backend_result.status == CheckStatus.PASSED:
            workers_result = await self._poll_until(
                self._check_workers_registered, "Workers", deadline
            )
            checks.append(workers_result)
        else:
            checks.append(
                CheckResult(
                    name="Workers",
                    status=CheckStatus.SKIPPED,
                    message="Skipped (backend not ready)",
                )
            )

        # Check observability
        obs_result = await self._poll_until(
            self._check_observability, "Observability", deadline
        )
        checks.append(obs_result)

        duration = time.time() - start
        passed = all(
            c.status == CheckStatus.PASSED
            for c in checks
            if c.status != CheckStatus.SKIPPED
        )

        return GateResult(passed=passed, checks=checks, duration_seconds=duration)

    async def _poll_until(
        self,
        check_fn,
        name: str,
        deadline: float,
    ) -> CheckResult:
        """Poll a check until it passes or deadline reached.

        Args:
            check_fn: Async function that returns a CheckResult.
            name: Name for the check (used in timeout error).
            deadline: Unix timestamp when polling should stop.

        Returns:
            CheckResult from the check function, or a timeout failure.
        """
        last_error = ""

        while time.time() < deadline:
            try:
                result = await check_fn()
                if result.status == CheckStatus.PASSED:
                    return result
                last_error = result.message
            except Exception as e:
                last_error = str(e)

            await asyncio.sleep(self.poll_interval)

        return CheckResult(
            name=name,
            status=CheckStatus.FAILED,
            message=f"Timeout after {self.timeout}s",
            details=last_error,
        )

    async def _check_database(self) -> CheckResult:
        """Check if database is ready using TCP connection.

        Returns:
            CheckResult indicating database connectivity status.
        """
        try:
            with socket.create_connection(("localhost", self.db_port), timeout=5):
                return CheckResult(
                    name="Database",
                    status=CheckStatus.PASSED,
                    message="Connection accepted",
                )
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            return CheckResult(
                name="Database",
                status=CheckStatus.FAILED,
                message=str(e),
            )

    async def _check_backend_health(self) -> CheckResult:
        """Check backend /health endpoint.

        Returns:
            CheckResult indicating backend health status.
        """
        url = f"http://localhost:{self.api_port}/api/v1/health"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    return CheckResult(
                        name="Backend",
                        status=CheckStatus.PASSED,
                        message=f"GET {url} → 200",
                    )
                return CheckResult(
                    name="Backend",
                    status=CheckStatus.FAILED,
                    message=f"GET {url} → {resp.status_code}",
                )
        except httpx.ConnectError:
            return CheckResult(
                name="Backend",
                status=CheckStatus.FAILED,
                message="Connection refused",
            )
        except Exception as e:
            return CheckResult(
                name="Backend",
                status=CheckStatus.FAILED,
                message=str(e),
            )

    async def _check_workers_registered(self) -> CheckResult:
        """Check that expected workers are registered.

        Returns:
            CheckResult indicating worker registration status.
        """
        url = f"http://localhost:{self.api_port}/api/v1/workers"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code != 200:
                    return CheckResult(
                        name="Workers",
                        status=CheckStatus.FAILED,
                        message=f"GET {url} → {resp.status_code}",
                    )

                data = resp.json()
                workers = data.get("workers", [])
                count = len(workers)

                if count >= 4:
                    return CheckResult(
                        name="Workers",
                        status=CheckStatus.PASSED,
                        message=f"{count} workers registered",
                    )
                return CheckResult(
                    name="Workers",
                    status=CheckStatus.FAILED,
                    message=f"Expected 4 workers, found {count}",
                )
        except Exception as e:
            return CheckResult(
                name="Workers",
                status=CheckStatus.FAILED,
                message=str(e),
            )

    async def _check_observability(self) -> CheckResult:
        """Check Jaeger UI is responding.

        Returns:
            CheckResult indicating observability status.
        """
        # Calculate Jaeger UI port from API port offset
        # API 8001 → Jaeger 16687, API 8002 → Jaeger 16688, etc.
        jaeger_port = 16686 + (self.api_port - 8000)
        url = f"http://localhost:{jaeger_port}"

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                if resp.status_code in (200, 302):
                    return CheckResult(
                        name="Observability",
                        status=CheckStatus.PASSED,
                        message="Jaeger UI responding",
                    )
                return CheckResult(
                    name="Observability",
                    status=CheckStatus.FAILED,
                    message=f"Jaeger returned {resp.status_code}",
                )
        except httpx.ConnectError:
            return CheckResult(
                name="Observability",
                status=CheckStatus.FAILED,
                message="Jaeger not responding",
            )
        except Exception as e:
            return CheckResult(
                name="Observability",
                status=CheckStatus.FAILED,
                message=str(e),
            )


def run_gate(api_port: int, db_port: int, timeout: float = 120.0) -> GateResult:
    """Synchronous wrapper for running the gate.

    Args:
        api_port: Port for the backend API.
        db_port: Port for the database.
        timeout: Maximum time in seconds to wait for all checks.

    Returns:
        GateResult with overall pass/fail and individual check results.
    """
    gate = StartabilityGate(api_port, db_port, timeout)
    return asyncio.run(gate.check())
