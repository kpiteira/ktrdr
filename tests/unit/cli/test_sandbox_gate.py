"""Tests for the sandbox Startability Gate module.

This module tests the health checking system that validates
a sandbox instance is fully operational before declaring ready.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestCheckStatus:
    """Tests for CheckStatus enum."""

    def test_check_status_values(self):
        """Verify CheckStatus has expected values."""
        from ktrdr.cli.sandbox_gate import CheckStatus

        assert CheckStatus.PASSED.value == "passed"
        assert CheckStatus.FAILED.value == "failed"
        assert CheckStatus.SKIPPED.value == "skipped"


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_check_result_fields(self):
        """Verify CheckResult has required fields."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus

        result = CheckResult(
            name="TestCheck",
            status=CheckStatus.PASSED,
            message="Test message",
            details="Test details",
        )

        assert result.name == "TestCheck"
        assert result.status == CheckStatus.PASSED
        assert result.message == "Test message"
        assert result.details == "Test details"

    def test_check_result_default_message(self):
        """Verify CheckResult has default empty message."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus

        result = CheckResult(name="Test", status=CheckStatus.PASSED)

        assert result.message == ""
        assert result.details == ""


class TestGateResult:
    """Tests for GateResult dataclass."""

    def test_gate_result_fields(self):
        """Verify GateResult has required fields."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        check = CheckResult(name="Test", status=CheckStatus.PASSED)
        gate = GateResult(passed=True, checks=[check], duration_seconds=1.5)

        assert gate.passed is True
        assert len(gate.checks) == 1
        assert gate.duration_seconds == 1.5

    def test_gate_result_passed_when_all_pass(self):
        """Gate should pass when all checks pass."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        checks = [
            CheckResult(name="Database", status=CheckStatus.PASSED),
            CheckResult(name="Backend", status=CheckStatus.PASSED),
            CheckResult(name="Workers", status=CheckStatus.PASSED),
            CheckResult(name="Observability", status=CheckStatus.PASSED),
        ]

        # GateResult itself just stores data; the logic is in StartabilityGate
        # This tests that all PASSED checks result in passed=True
        passed = all(c.status == CheckStatus.PASSED for c in checks)
        gate = GateResult(passed=passed, checks=checks, duration_seconds=10.0)

        assert gate.passed is True

    def test_gate_result_failed_when_any_fail(self):
        """Gate should fail when any check fails."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        checks = [
            CheckResult(name="Database", status=CheckStatus.PASSED),
            CheckResult(
                name="Backend", status=CheckStatus.FAILED, message="Connection refused"
            ),
            CheckResult(name="Workers", status=CheckStatus.SKIPPED),
            CheckResult(name="Observability", status=CheckStatus.PASSED),
        ]

        # Skipped checks don't count toward failure
        passed = all(
            c.status == CheckStatus.PASSED
            for c in checks
            if c.status != CheckStatus.SKIPPED
        )
        gate = GateResult(passed=passed, checks=checks, duration_seconds=5.0)

        assert gate.passed is False

    def test_skipped_checks_dont_fail_gate(self):
        """Skipped checks should not cause gate to fail."""
        from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

        checks = [
            CheckResult(name="Database", status=CheckStatus.PASSED),
            CheckResult(name="Backend", status=CheckStatus.PASSED),
            CheckResult(
                name="Workers", status=CheckStatus.SKIPPED, message="Backend not ready"
            ),
            CheckResult(name="Observability", status=CheckStatus.PASSED),
        ]

        # Only non-skipped checks determine pass/fail
        passed = all(
            c.status == CheckStatus.PASSED
            for c in checks
            if c.status != CheckStatus.SKIPPED
        )
        gate = GateResult(passed=passed, checks=checks, duration_seconds=8.0)

        assert gate.passed is True


class TestStartabilityGate:
    """Tests for StartabilityGate class."""

    def test_gate_initialization(self):
        """Verify gate initializes with correct ports and timeout."""
        from ktrdr.cli.sandbox_gate import StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433, timeout=60.0)

        assert gate.api_port == 8001
        assert gate.db_port == 5433
        assert gate.timeout == 60.0

    def test_gate_default_timeout(self):
        """Verify gate has sensible default timeout."""
        from ktrdr.cli.sandbox_gate import StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        assert gate.timeout == 120.0  # 2 minutes default

    @pytest.mark.asyncio
    async def test_check_database_success(self):
        """Database check passes when port accepts connections."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock successful socket connection
        with patch("socket.create_connection") as mock_conn:
            mock_conn.return_value.__enter__ = lambda s: s
            mock_conn.return_value.__exit__ = lambda *args: None

            result = await gate._check_database()

            assert result.status == CheckStatus.PASSED
            assert result.name == "Database"

    @pytest.mark.asyncio
    async def test_check_database_failure(self):
        """Database check fails when connection refused."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock connection refused
        with patch("socket.create_connection") as mock_conn:
            mock_conn.side_effect = ConnectionRefusedError("Connection refused")

            result = await gate._check_database()

            assert result.status == CheckStatus.FAILED
            assert "refused" in result.message.lower()

    @pytest.mark.asyncio
    async def test_check_backend_health_success(self):
        """Backend check passes when /health returns 200."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock successful HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await gate._check_backend_health()

            assert result.status == CheckStatus.PASSED
            assert result.name == "Backend"

    @pytest.mark.asyncio
    async def test_check_backend_health_failure(self):
        """Backend check fails when /health returns non-200."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock failed HTTP response
        mock_response = AsyncMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await gate._check_backend_health()

            assert result.status == CheckStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_workers_registered_success(self):
        """Workers check passes when 4+ workers registered."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock workers endpoint response - use MagicMock for response
        # since json() is synchronous in httpx
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "workers": [
                {"id": "worker-1"},
                {"id": "worker-2"},
                {"id": "worker-3"},
                {"id": "worker-4"},
            ]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await gate._check_workers_registered()

            assert result.status == CheckStatus.PASSED
            assert "4" in result.message

    @pytest.mark.asyncio
    async def test_check_workers_registered_insufficient(self):
        """Workers check fails when fewer than 4 workers."""
        from ktrdr.cli.sandbox_gate import CheckStatus, StartabilityGate

        gate = StartabilityGate(api_port=8001, db_port=5433)

        # Mock workers endpoint with only 2 workers - use MagicMock
        # since json() is synchronous in httpx
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "workers": [{"id": "worker-1"}, {"id": "worker-2"}]
        }

        with patch("httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__.return_value = mock_client

            result = await gate._check_workers_registered()

            assert result.status == CheckStatus.FAILED
            assert "Expected 4" in result.message


class TestRunGate:
    """Tests for run_gate() synchronous wrapper."""

    def test_run_gate_returns_gate_result(self):
        """run_gate() should return a GateResult."""
        from ktrdr.cli.sandbox_gate import GateResult, run_gate

        # Mock the StartabilityGate.check() method
        with patch("ktrdr.cli.sandbox_gate.StartabilityGate") as MockGate:
            from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus

            mock_result = GateResult(
                passed=True,
                checks=[CheckResult(name="Test", status=CheckStatus.PASSED)],
                duration_seconds=1.0,
            )

            mock_instance = MockGate.return_value
            mock_instance.check = AsyncMock(return_value=mock_result)

            result = run_gate(api_port=8001, db_port=5433, timeout=10.0)

            assert isinstance(result, GateResult)
            assert result.passed is True

    def test_run_gate_passes_parameters(self):
        """run_gate() should pass parameters to StartabilityGate."""
        from ktrdr.cli.sandbox_gate import run_gate

        with patch("ktrdr.cli.sandbox_gate.StartabilityGate") as MockGate:
            from ktrdr.cli.sandbox_gate import CheckResult, CheckStatus, GateResult

            mock_result = GateResult(
                passed=True,
                checks=[CheckResult(name="Test", status=CheckStatus.PASSED)],
                duration_seconds=1.0,
            )
            mock_instance = MockGate.return_value
            mock_instance.check = AsyncMock(return_value=mock_result)

            run_gate(api_port=8002, db_port=5434, timeout=30.0)

            MockGate.assert_called_once_with(8002, 5434, 30.0)
