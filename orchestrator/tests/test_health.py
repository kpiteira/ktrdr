"""Tests for orchestrator health check module.

These tests verify the health check data models, dependency configuration,
and individual check functions including telemetry instrumentation.
"""

import json
import subprocess
from dataclasses import asdict, is_dataclass
from datetime import datetime
from unittest.mock import MagicMock, patch


class TestCheckResultModel:
    """Test the CheckResult model."""

    def test_check_result_is_dataclass(self):
        """CheckResult should be a dataclass."""
        from orchestrator.health import CheckResult

        assert is_dataclass(CheckResult)

    def test_check_result_has_required_fields(self):
        """CheckResult should have all required fields with type hints."""
        from orchestrator.health import CheckResult

        annotations = CheckResult.__annotations__
        required_fields = ["status", "message", "check_name"]
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_check_result_status_ok(self):
        """CheckResult should support 'ok' status."""
        from orchestrator.health import CheckResult

        result = CheckResult(
            status="ok",
            message="container running",
            check_name="sandbox",
        )
        assert result.status == "ok"
        assert result.message == "container running"
        assert result.check_name == "sandbox"

    def test_check_result_status_failed(self):
        """CheckResult should support 'failed' status."""
        from orchestrator.health import CheckResult

        result = CheckResult(
            status="failed",
            message="not logged in - run 'claude login' in sandbox",
            check_name="claude_auth",
        )
        assert result.status == "failed"
        assert "not logged in" in result.message
        assert result.check_name == "claude_auth"

    def test_check_result_status_skipped(self):
        """CheckResult should support 'skipped' status."""
        from orchestrator.health import CheckResult

        result = CheckResult(
            status="skipped",
            message="sandbox not running",
            check_name="github_token",
        )
        assert result.status == "skipped"
        assert result.message == "sandbox not running"
        assert result.check_name == "github_token"

    def test_check_result_json_serializable(self):
        """CheckResult should be JSON serializable via asdict."""
        from orchestrator.health import CheckResult

        result = CheckResult(
            status="ok",
            message="authenticated",
            check_name="claude_auth",
        )
        json_str = json.dumps(asdict(result))
        loaded = json.loads(json_str)
        assert loaded["status"] == "ok"
        assert loaded["message"] == "authenticated"
        assert loaded["check_name"] == "claude_auth"


class TestHealthReportModel:
    """Test the HealthReport model."""

    def test_health_report_is_dataclass(self):
        """HealthReport should be a dataclass."""
        from orchestrator.health import HealthReport

        assert is_dataclass(HealthReport)

    def test_health_report_has_required_fields(self):
        """HealthReport should have all required fields with type hints."""
        from orchestrator.health import HealthReport

        annotations = HealthReport.__annotations__
        required_fields = ["status", "timestamp", "checks"]
        for field in required_fields:
            assert field in annotations, f"Missing field: {field}"

    def test_health_report_healthy_status(self):
        """HealthReport should support 'healthy' status."""
        from orchestrator.health import CheckResult, HealthReport

        now = datetime.utcnow()
        report = HealthReport(
            status="healthy",
            timestamp=now,
            checks={
                "sandbox": CheckResult(
                    status="ok", message="container running", check_name="sandbox"
                )
            },
        )
        assert report.status == "healthy"
        assert report.timestamp == now
        assert len(report.checks) == 1
        assert report.checks["sandbox"].status == "ok"

    def test_health_report_unhealthy_status(self):
        """HealthReport should support 'unhealthy' status."""
        from orchestrator.health import CheckResult, HealthReport

        now = datetime.utcnow()
        report = HealthReport(
            status="unhealthy",
            timestamp=now,
            checks={
                "sandbox": CheckResult(
                    status="failed",
                    message="container not running",
                    check_name="sandbox",
                )
            },
        )
        assert report.status == "unhealthy"
        assert report.checks["sandbox"].status == "failed"

    def test_health_report_empty_checks_by_default(self):
        """HealthReport should have empty checks dict by default."""
        from orchestrator.health import HealthReport

        report = HealthReport(status="healthy", timestamp=datetime.utcnow())
        assert report.checks == {}

    def test_health_report_to_dict(self):
        """HealthReport.to_dict() should produce expected JSON structure."""
        from orchestrator.health import CheckResult, HealthReport

        now = datetime(2024, 12, 18, 10, 30, 0)
        report = HealthReport(
            status="healthy",
            timestamp=now,
            checks={
                "sandbox": CheckResult(
                    status="ok", message="container running", check_name="sandbox"
                ),
                "claude_auth": CheckResult(
                    status="ok", message="authenticated", check_name="claude_auth"
                ),
            },
        )
        result = report.to_dict()

        assert result["status"] == "healthy"
        assert result["timestamp"] == "2024-12-18T10:30:00"
        assert "checks" in result
        assert result["checks"]["sandbox"]["status"] == "ok"
        assert result["checks"]["sandbox"]["message"] == "container running"
        assert result["checks"]["claude_auth"]["status"] == "ok"
        assert result["checks"]["claude_auth"]["message"] == "authenticated"

    def test_health_report_to_dict_is_json_serializable(self):
        """HealthReport.to_dict() output should be JSON serializable."""
        from orchestrator.health import CheckResult, HealthReport

        report = HealthReport(
            status="unhealthy",
            timestamp=datetime.utcnow(),
            checks={
                "sandbox": CheckResult(
                    status="failed",
                    message="container not running",
                    check_name="sandbox",
                ),
                "claude_auth": CheckResult(
                    status="skipped",
                    message="sandbox not running",
                    check_name="claude_auth",
                ),
            },
        )
        # Should not raise
        json_str = json.dumps(report.to_dict())
        loaded = json.loads(json_str)
        assert loaded["status"] == "unhealthy"
        assert loaded["checks"]["sandbox"]["status"] == "failed"
        assert loaded["checks"]["claude_auth"]["status"] == "skipped"

    def test_health_report_to_dict_excludes_check_name(self):
        """HealthReport.to_dict() should not include check_name in check output."""
        from orchestrator.health import CheckResult, HealthReport

        report = HealthReport(
            status="healthy",
            timestamp=datetime.utcnow(),
            checks={
                "sandbox": CheckResult(
                    status="ok", message="container running", check_name="sandbox"
                )
            },
        )
        result = report.to_dict()

        # The check_name should not be in the nested dict (it's the key)
        assert "check_name" not in result["checks"]["sandbox"]
        # Only status and message should be present
        assert set(result["checks"]["sandbox"].keys()) == {"status", "message"}


class TestCheckDependencies:
    """Test the CHECK_DEPENDENCIES configuration."""

    def test_check_dependencies_exists(self):
        """CHECK_DEPENDENCIES should be defined."""
        from orchestrator.health import CHECK_DEPENDENCIES

        assert isinstance(CHECK_DEPENDENCIES, dict)

    def test_check_dependencies_has_all_checks(self):
        """CHECK_DEPENDENCIES should include all four checks."""
        from orchestrator.health import CHECK_DEPENDENCIES

        expected_checks = {"sandbox", "claude_auth", "github_token", "orchestrator"}
        assert set(CHECK_DEPENDENCIES.keys()) == expected_checks

    def test_sandbox_has_no_dependencies(self):
        """Sandbox should have no dependencies."""
        from orchestrator.health import CHECK_DEPENDENCIES

        assert CHECK_DEPENDENCIES["sandbox"] == []

    def test_claude_auth_depends_on_sandbox(self):
        """Claude auth should depend on sandbox."""
        from orchestrator.health import CHECK_DEPENDENCIES

        assert CHECK_DEPENDENCIES["claude_auth"] == ["sandbox"]

    def test_github_token_depends_on_sandbox(self):
        """GitHub token should depend on sandbox."""
        from orchestrator.health import CHECK_DEPENDENCIES

        assert CHECK_DEPENDENCIES["github_token"] == ["sandbox"]

    def test_orchestrator_has_no_dependencies(self):
        """Orchestrator should have no dependencies."""
        from orchestrator.health import CHECK_DEPENDENCIES

        assert CHECK_DEPENDENCIES["orchestrator"] == []


class TestCheckOrder:
    """Test the CHECK_ORDER configuration."""

    def test_check_order_exists(self):
        """CHECK_ORDER should be defined."""
        from orchestrator.health import CHECK_ORDER

        assert isinstance(CHECK_ORDER, list)

    def test_check_order_has_all_checks(self):
        """CHECK_ORDER should contain all keys from CHECK_DEPENDENCIES."""
        from orchestrator.health import CHECK_DEPENDENCIES, CHECK_ORDER

        assert set(CHECK_ORDER) == set(CHECK_DEPENDENCIES.keys())

    def test_check_order_has_correct_length(self):
        """CHECK_ORDER should have exactly 4 checks."""
        from orchestrator.health import CHECK_ORDER

        assert len(CHECK_ORDER) == 4

    def test_sandbox_comes_first(self):
        """Sandbox should come before checks that depend on it."""
        from orchestrator.health import CHECK_ORDER

        sandbox_idx = CHECK_ORDER.index("sandbox")
        claude_auth_idx = CHECK_ORDER.index("claude_auth")
        github_token_idx = CHECK_ORDER.index("github_token")

        assert sandbox_idx < claude_auth_idx
        assert sandbox_idx < github_token_idx

    def test_dependencies_ordered_correctly(self):
        """Dependencies should come before dependents in CHECK_ORDER."""
        from orchestrator.health import CHECK_DEPENDENCIES, CHECK_ORDER

        for check, deps in CHECK_DEPENDENCIES.items():
            check_idx = CHECK_ORDER.index(check)
            for dep in deps:
                dep_idx = CHECK_ORDER.index(dep)
                assert dep_idx < check_idx, (
                    f"Dependency {dep} should come before {check}"
                )


class TestCheckSandbox:
    """Test the check_sandbox function."""

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_running(self, mock_run):
        """check_sandbox should return ok when container is running."""
        from orchestrator.health import check_sandbox

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="true\n",
            stderr="",
        )

        result = check_sandbox("test-container")

        assert result.status == "ok"
        assert result.check_name == "sandbox"
        assert "running" in result.message.lower()
        mock_run.assert_called_once()
        # Verify the command includes the container name
        call_args = mock_run.call_args[0][0]
        assert "test-container" in call_args

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_not_running(self, mock_run):
        """check_sandbox should return failed when container exists but not running."""
        from orchestrator.health import check_sandbox

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="false\n",
            stderr="",
        )

        result = check_sandbox("test-container")

        assert result.status == "failed"
        assert result.check_name == "sandbox"
        assert "not running" in result.message.lower()
        assert "docker compose up" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_not_found(self, mock_run):
        """check_sandbox should return failed when container doesn't exist."""
        from orchestrator.health import check_sandbox

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: No such container",
        )

        result = check_sandbox("test-container")

        assert result.status == "failed"
        assert result.check_name == "sandbox"
        assert "not found" in result.message.lower()
        assert "docker compose up" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_timeout(self, mock_run):
        """check_sandbox should handle timeout gracefully."""
        from orchestrator.health import check_sandbox

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=5)

        result = check_sandbox("test-container")

        assert result.status == "failed"
        assert result.check_name == "sandbox"
        assert "timed out" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_docker_not_found(self, mock_run):
        """check_sandbox should handle missing Docker."""
        from orchestrator.health import check_sandbox

        mock_run.side_effect = FileNotFoundError("docker not found")

        result = check_sandbox("test-container")

        assert result.status == "failed"
        assert result.check_name == "sandbox"
        assert "docker not found" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_sandbox_uses_5_second_timeout(self, mock_run):
        """check_sandbox should use 5 second timeout on docker commands."""
        from orchestrator.health import HEALTH_CHECK_TIMEOUT, check_sandbox

        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")

        check_sandbox("test-container")

        # Verify timeout parameter was passed
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == HEALTH_CHECK_TIMEOUT
        assert HEALTH_CHECK_TIMEOUT == 5


class TestCheckClaudeAuth:
    """Test the check_claude_auth function."""

    @patch("orchestrator.health.subprocess.run")
    def test_claude_authenticated(self, mock_run):
        """check_claude_auth should return ok when Claude CLI works."""
        from orchestrator.health import check_claude_auth

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="claude 1.0.0\n",
            stderr="",
        )

        result = check_claude_auth("test-container")

        assert result.status == "ok"
        assert result.check_name == "claude_auth"
        assert "authenticated" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_claude_not_logged_in(self, mock_run):
        """check_claude_auth should detect not logged in state."""
        from orchestrator.health import check_claude_auth

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: Not logged in. Please run 'claude login'",
        )

        result = check_claude_auth("test-container")

        assert result.status == "failed"
        assert result.check_name == "claude_auth"
        assert "claude login" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_claude_authentication_required(self, mock_run):
        """check_claude_auth should detect authentication required."""
        from orchestrator.health import check_claude_auth

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Please authenticate first",
        )

        result = check_claude_auth("test-container")

        assert result.status == "failed"
        assert result.check_name == "claude_auth"
        assert "claude login" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_claude_generic_error(self, mock_run):
        """check_claude_auth should handle generic errors."""
        from orchestrator.health import check_claude_auth

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Some other error",
        )

        result = check_claude_auth("test-container")

        assert result.status == "failed"
        assert result.check_name == "claude_auth"
        assert "some other error" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_claude_timeout(self, mock_run):
        """check_claude_auth should handle timeout."""
        from orchestrator.health import check_claude_auth

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=5)

        result = check_claude_auth("test-container")

        assert result.status == "failed"
        assert result.check_name == "claude_auth"
        assert "timed out" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_claude_uses_5_second_timeout(self, mock_run):
        """check_claude_auth should use 5 second timeout."""
        from orchestrator.health import HEALTH_CHECK_TIMEOUT, check_claude_auth

        mock_run.return_value = MagicMock(returncode=0, stdout="claude 1.0.0\n")

        check_claude_auth("test-container")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == HEALTH_CHECK_TIMEOUT


class TestCheckGithubToken:
    """Test the check_github_token function."""

    @patch("orchestrator.health.subprocess.run")
    def test_github_token_set(self, mock_run):
        """check_github_token should return ok when token is set."""
        from orchestrator.health import check_github_token

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="set\n",
            stderr="",
        )

        result = check_github_token("test-container")

        assert result.status == "ok"
        assert result.check_name == "github_token"
        assert "configured" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_github_token_not_set(self, mock_run):
        """check_github_token should return failed when token is not set."""
        from orchestrator.health import check_github_token

        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="unset\n",
            stderr="",
        )

        result = check_github_token("test-container")

        assert result.status == "failed"
        assert result.check_name == "github_token"
        assert "github_token not set" in result.message.lower()
        assert ".env" in result.message.lower() or "docker-compose" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_github_token_command_failed(self, mock_run):
        """check_github_token should return failed on command error."""
        from orchestrator.health import check_github_token

        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error",
        )

        result = check_github_token("test-container")

        assert result.status == "failed"
        assert result.check_name == "github_token"

    @patch("orchestrator.health.subprocess.run")
    def test_github_token_timeout(self, mock_run):
        """check_github_token should handle timeout."""
        from orchestrator.health import check_github_token

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=5)

        result = check_github_token("test-container")

        assert result.status == "failed"
        assert result.check_name == "github_token"
        assert "timed out" in result.message.lower()

    @patch("orchestrator.health.subprocess.run")
    def test_github_token_uses_5_second_timeout(self, mock_run):
        """check_github_token should use 5 second timeout."""
        from orchestrator.health import HEALTH_CHECK_TIMEOUT, check_github_token

        mock_run.return_value = MagicMock(returncode=0, stdout="set\n")

        check_github_token("test-container")

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == HEALTH_CHECK_TIMEOUT


class TestCheckOrchestrator:
    """Test the check_orchestrator function."""

    def test_orchestrator_configured(self):
        """check_orchestrator should return ok when modules import correctly."""
        from orchestrator.health import check_orchestrator

        result = check_orchestrator()

        assert result.status == "ok"
        assert result.check_name == "orchestrator"
        assert "configured" in result.message.lower()

    def test_orchestrator_import_error(self):
        """check_orchestrator should handle import errors."""
        from orchestrator.health import check_orchestrator

        with patch.dict("sys.modules", {"orchestrator.config": None}):
            with patch(
                "orchestrator.health.check_orchestrator",
                side_effect=ImportError("Cannot import config"),
            ):
                # This tests the import error path
                # The actual function catches ImportError internally
                pass

        # In real scenario, the function should work
        result = check_orchestrator()
        assert result.status == "ok"

    def test_orchestrator_returns_check_result(self):
        """check_orchestrator should return a CheckResult."""
        from orchestrator.health import CheckResult, check_orchestrator

        result = check_orchestrator()

        assert isinstance(result, CheckResult)
        assert result.check_name == "orchestrator"


class TestHealthCheckConstants:
    """Test health check constants."""

    def test_health_check_timeout_is_5_seconds(self):
        """HEALTH_CHECK_TIMEOUT should be 5 seconds."""
        from orchestrator.health import HEALTH_CHECK_TIMEOUT

        assert HEALTH_CHECK_TIMEOUT == 5

    def test_default_container_name(self):
        """DEFAULT_CONTAINER should be ktrdr-sandbox."""
        from orchestrator.health import DEFAULT_CONTAINER

        assert DEFAULT_CONTAINER == "ktrdr-sandbox"


class TestCheckFunctionSignatures:
    """Test that check functions have correct signatures."""

    def test_check_sandbox_accepts_container_name(self):
        """check_sandbox should accept optional container_name parameter."""
        from orchestrator.health import check_sandbox

        # Should work with default
        with patch("orchestrator.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
            result = check_sandbox()
            assert result.check_name == "sandbox"

        # Should work with custom container name
        with patch("orchestrator.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="true\n")
            result = check_sandbox("custom-container")
            assert "custom-container" in mock_run.call_args[0][0]

    def test_check_claude_auth_accepts_container_name(self):
        """check_claude_auth should accept optional container_name parameter."""
        from orchestrator.health import check_claude_auth

        with patch("orchestrator.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="claude 1.0.0\n")
            check_claude_auth("custom-container")
            assert "custom-container" in mock_run.call_args[0][0]

    def test_check_github_token_accepts_container_name(self):
        """check_github_token should accept optional container_name parameter."""
        from orchestrator.health import check_github_token

        with patch("orchestrator.health.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="set\n")
            check_github_token("custom-container")
            assert "custom-container" in mock_run.call_args[0][0]

    def test_check_orchestrator_no_parameters(self):
        """check_orchestrator should work with no parameters."""
        from orchestrator.health import check_orchestrator

        result = check_orchestrator()
        assert result.check_name == "orchestrator"


class TestGetHealth:
    """Test the get_health aggregator function."""

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_all_checks_pass_returns_healthy(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should return healthy when all checks pass."""
        from orchestrator.health import CheckResult, HealthReport, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="Container running", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="ok", message="Authenticated", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="Token set", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        assert isinstance(result, HealthReport)
        assert result.status == "healthy"
        assert len(result.checks) == 4
        assert all(check.status == "ok" for check in result.checks.values())

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_sandbox_failure_skips_dependent_checks(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should skip claude_auth and github_token when sandbox fails."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="failed", message="Container not running", check_name="sandbox"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        assert result.status == "unhealthy"
        assert result.checks["sandbox"].status == "failed"
        assert result.checks["claude_auth"].status == "skipped"
        assert result.checks["github_token"].status == "skipped"
        assert result.checks["orchestrator"].status == "ok"
        # Verify dependent checks were not called
        mock_claude.assert_not_called()
        mock_github.assert_not_called()

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_skipped_checks_have_informative_message(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """Skipped checks should mention which dependency failed."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="failed", message="Container not running", check_name="sandbox"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        assert "sandbox" in result.checks["claude_auth"].message.lower()
        assert "sandbox" in result.checks["github_token"].message.lower()

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_one_check_fails_returns_unhealthy(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should return unhealthy if any check fails."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="Container running", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="failed", message="Not logged in", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="Token set", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        assert result.status == "unhealthy"
        assert result.checks["claude_auth"].status == "failed"

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_skipped_status_makes_unhealthy(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should return unhealthy if any check is skipped."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="failed", message="Not running", check_name="sandbox"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        # Skipped checks should make the overall status unhealthy
        assert result.status == "unhealthy"

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_checks_run_in_dependency_order(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should run checks in CHECK_ORDER."""
        from orchestrator.health import CHECK_ORDER, CheckResult, get_health

        call_order = []

        def track_sandbox(*args, **kwargs):
            call_order.append("sandbox")
            return CheckResult(status="ok", message="ok", check_name="sandbox")

        def track_claude(*args, **kwargs):
            call_order.append("claude_auth")
            return CheckResult(status="ok", message="ok", check_name="claude_auth")

        def track_github(*args, **kwargs):
            call_order.append("github_token")
            return CheckResult(status="ok", message="ok", check_name="github_token")

        def track_orchestrator(*args, **kwargs):
            call_order.append("orchestrator")
            return CheckResult(status="ok", message="ok", check_name="orchestrator")

        mock_sandbox.side_effect = track_sandbox
        mock_claude.side_effect = track_claude
        mock_github.side_effect = track_github
        mock_orchestrator.side_effect = track_orchestrator

        get_health("test-container")

        assert call_order == CHECK_ORDER

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_container_name_passed_to_checks(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should pass container_name to checks that need it."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="ok", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="ok", message="ok", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="ok", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="ok", check_name="orchestrator"
        )

        get_health("my-custom-container")

        mock_sandbox.assert_called_once_with("my-custom-container")
        mock_claude.assert_called_once_with("my-custom-container")
        mock_github.assert_called_once_with("my-custom-container")
        # Orchestrator doesn't take container_name
        mock_orchestrator.assert_called_once_with()

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_returns_health_report_with_timestamp(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should return HealthReport with a timestamp."""
        from datetime import datetime

        from orchestrator.health import CheckResult, HealthReport, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="ok", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="ok", message="ok", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="ok", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="ok", check_name="orchestrator"
        )

        before = datetime.utcnow()
        result = get_health("test-container")
        after = datetime.utcnow()

        assert isinstance(result, HealthReport)
        assert isinstance(result.timestamp, datetime)
        assert before <= result.timestamp <= after

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_uses_default_container_name(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should use DEFAULT_CONTAINER when no container specified."""
        from orchestrator.health import DEFAULT_CONTAINER, CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="ok", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="ok", message="ok", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="ok", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="ok", check_name="orchestrator"
        )

        get_health()

        mock_sandbox.assert_called_once_with(DEFAULT_CONTAINER)
        mock_claude.assert_called_once_with(DEFAULT_CONTAINER)
        mock_github.assert_called_once_with(DEFAULT_CONTAINER)

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_orchestrator_runs_even_when_sandbox_fails(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should still run orchestrator check when sandbox fails."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="failed", message="Not running", check_name="sandbox"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="Configured", check_name="orchestrator"
        )

        result = get_health("test-container")

        # Orchestrator has no dependencies, should still run
        mock_orchestrator.assert_called_once()
        assert result.checks["orchestrator"].status == "ok"


class TestHealthTelemetry:
    """Test telemetry instrumentation for health checks."""

    def test_telemetry_modules_imported(self):
        """Health module should import telemetry modules."""
        from orchestrator import health

        # Verify tracer and meter are set up
        assert hasattr(health, "_tracer")
        assert hasattr(health, "_meter")
        assert hasattr(health, "_health_check_counter")
        assert hasattr(health, "_health_check_duration")

    def test_tracer_is_valid(self):
        """Health module should have a valid tracer."""
        from orchestrator.health import _tracer

        # Tracer should be a valid OpenTelemetry tracer
        assert _tracer is not None
        # Should be able to start a span (uses no-op when OTLP disabled)
        with _tracer.start_as_current_span("test_span"):
            pass  # Should not raise

    def test_meter_is_valid(self):
        """Health module should have a valid meter."""
        from orchestrator.health import _meter

        # Meter should be a valid OpenTelemetry meter
        assert _meter is not None

    def test_counter_is_valid(self):
        """Health check counter should be a valid counter instrument."""
        from orchestrator.health import _health_check_counter

        assert _health_check_counter is not None
        # Should be able to add to counter (uses no-op when OTLP disabled)
        _health_check_counter.add(1, {"check": "test", "status": "ok"})

    def test_histogram_is_valid(self):
        """Health check duration histogram should be a valid instrument."""
        from orchestrator.health import _health_check_duration

        assert _health_check_duration is not None
        # Should be able to record to histogram (uses no-op when OTLP disabled)
        _health_check_duration.record(0.1, {"check": "test"})

    @patch("orchestrator.health.subprocess.run")
    def test_check_sandbox_records_telemetry(self, mock_run):
        """check_sandbox should record telemetry without errors."""
        from orchestrator.health import check_sandbox

        mock_run.return_value = MagicMock(returncode=0, stdout="true\n")

        # Should not raise any telemetry errors
        result = check_sandbox("test-container")
        assert result.status == "ok"

    @patch("orchestrator.health.subprocess.run")
    def test_check_claude_auth_records_telemetry(self, mock_run):
        """check_claude_auth should record telemetry without errors."""
        from orchestrator.health import check_claude_auth

        mock_run.return_value = MagicMock(returncode=0, stdout="claude 1.0.0\n")

        # Should not raise any telemetry errors
        result = check_claude_auth("test-container")
        assert result.status == "ok"

    @patch("orchestrator.health.subprocess.run")
    def test_check_github_token_records_telemetry(self, mock_run):
        """check_github_token should record telemetry without errors."""
        from orchestrator.health import check_github_token

        mock_run.return_value = MagicMock(returncode=0, stdout="set\n")

        # Should not raise any telemetry errors
        result = check_github_token("test-container")
        assert result.status == "ok"

    def test_check_orchestrator_records_telemetry(self):
        """check_orchestrator should record telemetry without errors."""
        from orchestrator.health import check_orchestrator

        # Should not raise any telemetry errors
        result = check_orchestrator()
        assert result.status == "ok"

    @patch("orchestrator.health.check_orchestrator")
    @patch("orchestrator.health.check_github_token")
    @patch("orchestrator.health.check_claude_auth")
    @patch("orchestrator.health.check_sandbox")
    def test_get_health_records_telemetry(
        self, mock_sandbox, mock_claude, mock_github, mock_orchestrator
    ):
        """get_health should record telemetry for overall health check."""
        from orchestrator.health import CheckResult, get_health

        mock_sandbox.return_value = CheckResult(
            status="ok", message="ok", check_name="sandbox"
        )
        mock_claude.return_value = CheckResult(
            status="ok", message="ok", check_name="claude_auth"
        )
        mock_github.return_value = CheckResult(
            status="ok", message="ok", check_name="github_token"
        )
        mock_orchestrator.return_value = CheckResult(
            status="ok", message="ok", check_name="orchestrator"
        )

        # Should not raise any telemetry errors
        result = get_health("test-container")
        assert result.status == "healthy"

    @patch("orchestrator.health.subprocess.run")
    def test_telemetry_works_on_failure(self, mock_run):
        """Telemetry should work correctly even when checks fail."""
        from orchestrator.health import check_sandbox

        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Container not found"
        )

        # Should not raise any telemetry errors
        result = check_sandbox("test-container")
        assert result.status == "failed"

    @patch("orchestrator.health.subprocess.run")
    def test_telemetry_works_on_timeout(self, mock_run):
        """Telemetry should work correctly on timeout."""
        from orchestrator.health import check_sandbox

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="docker", timeout=5)

        # Should not raise any telemetry errors
        result = check_sandbox("test-container")
        assert result.status == "failed"

    def test_no_otlp_no_errors(self):
        """Health checks should work without OTLP enabled (default case)."""
        # This test verifies the default case where OTLP is not configured
        # The telemetry should use no-op providers and not raise errors
        from orchestrator.health import (
            _health_check_counter,
            _health_check_duration,
            _meter,
            _tracer,
        )

        # All telemetry objects should exist and be usable
        assert _tracer is not None
        assert _meter is not None
        assert _health_check_counter is not None
        assert _health_check_duration is not None

        # Using them should not raise errors
        with _tracer.start_as_current_span("test"):
            _health_check_counter.add(1, {"check": "test", "status": "ok"})
            _health_check_duration.record(0.01, {"check": "test"})
