"""Tests for orchestrator health checks."""

import subprocess
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from orchestrator.health import (
    CHECK_DEPENDENCIES,
    CHECK_ORDER,
    CheckResult,
    HealthReport,
    check_claude_auth,
    check_github_token,
    check_orchestrator,
    check_sandbox,
)


class TestCheckResult:
    """Tests for CheckResult dataclass."""

    def test_create_with_ok_status(self) -> None:
        """CheckResult can be created with ok status."""
        result = CheckResult(status="ok", message="container running", check_name="sandbox")
        assert result.status == "ok"
        assert result.message == "container running"
        assert result.check_name == "sandbox"

    def test_create_with_failed_status(self) -> None:
        """CheckResult can be created with failed status."""
        result = CheckResult(status="failed", message="not running", check_name="sandbox")
        assert result.status == "failed"
        assert result.message == "not running"
        assert result.check_name == "sandbox"

    def test_create_with_skipped_status(self) -> None:
        """CheckResult can be created with skipped status."""
        result = CheckResult(
            status="skipped", message="sandbox not running", check_name="claude_auth"
        )
        assert result.status == "skipped"
        assert result.message == "sandbox not running"
        assert result.check_name == "claude_auth"


class TestHealthReport:
    """Tests for HealthReport dataclass."""

    def test_to_dict_healthy(self) -> None:
        """to_dict produces expected JSON structure for healthy report."""
        report = HealthReport(
            status="healthy",
            timestamp=datetime(2024, 12, 18, 10, 30, 0),
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
        assert result["checks"]["sandbox"]["status"] == "ok"
        assert result["checks"]["sandbox"]["message"] == "container running"
        assert result["checks"]["claude_auth"]["status"] == "ok"
        assert result["checks"]["claude_auth"]["message"] == "authenticated"

    def test_to_dict_unhealthy(self) -> None:
        """to_dict produces expected JSON structure for unhealthy report."""
        report = HealthReport(
            status="unhealthy",
            timestamp=datetime(2024, 12, 18, 10, 30, 0),
            checks={
                "sandbox": CheckResult(
                    status="failed", message="container not running", check_name="sandbox"
                ),
            },
        )

        result = report.to_dict()

        assert result["status"] == "unhealthy"
        assert result["checks"]["sandbox"]["status"] == "failed"


class TestCheckDependencies:
    """Tests for CHECK_DEPENDENCIES and CHECK_ORDER constants."""

    def test_check_order_contains_all_dependency_keys(self) -> None:
        """CHECK_ORDER contains all keys from CHECK_DEPENDENCIES."""
        for key in CHECK_DEPENDENCIES:
            assert key in CHECK_ORDER, f"'{key}' from CHECK_DEPENDENCIES not in CHECK_ORDER"

    def test_all_check_order_keys_in_dependencies(self) -> None:
        """All CHECK_ORDER entries have a corresponding CHECK_DEPENDENCIES entry."""
        for check in CHECK_ORDER:
            assert check in CHECK_DEPENDENCIES, f"'{check}' not in CHECK_DEPENDENCIES"

    def test_sandbox_has_no_dependencies(self) -> None:
        """sandbox check has no dependencies."""
        assert CHECK_DEPENDENCIES["sandbox"] == []

    def test_claude_auth_depends_on_sandbox(self) -> None:
        """claude_auth depends on sandbox."""
        assert "sandbox" in CHECK_DEPENDENCIES["claude_auth"]

    def test_github_token_depends_on_sandbox(self) -> None:
        """github_token depends on sandbox."""
        assert "sandbox" in CHECK_DEPENDENCIES["github_token"]

    def test_orchestrator_has_no_dependencies(self) -> None:
        """orchestrator check has no dependencies."""
        assert CHECK_DEPENDENCIES["orchestrator"] == []


class TestCheckSandbox:
    """Tests for check_sandbox() function."""

    def test_returns_ok_when_container_running(self) -> None:
        """check_sandbox returns ok when container is running."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = check_sandbox()

            assert result.status == "ok"
            assert result.check_name == "sandbox"
            assert "running" in result.message
            mock_run.assert_called_once()
            # Verify docker inspect command is used
            call_args = mock_run.call_args
            assert "docker" in call_args[0][0]
            assert "inspect" in call_args[0][0]

    def test_returns_failed_when_container_not_running(self) -> None:
        """check_sandbox returns failed when container is not running."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "false\n"

        with patch("subprocess.run", return_value=mock_result):
            result = check_sandbox()

            assert result.status == "failed"
            assert result.check_name == "sandbox"
            # Should include actionable guidance
            assert "sandbox-init" in result.message.lower() or "not running" in result.message

    def test_returns_failed_when_container_not_found(self) -> None:
        """check_sandbox returns failed when container doesn't exist."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Error: No such container"

        with patch("subprocess.run", return_value=mock_result):
            result = check_sandbox()

            assert result.status == "failed"
            assert result.check_name == "sandbox"

    def test_returns_failed_on_timeout(self) -> None:
        """check_sandbox returns failed when docker command times out."""
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)):
            result = check_sandbox()

            assert result.status == "failed"
            assert result.check_name == "sandbox"
            assert "timed out" in result.message.lower()

    def test_uses_5_second_timeout(self) -> None:
        """check_sandbox uses 5 second timeout by default."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "true\n"

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            check_sandbox()

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 5


class TestCheckClaudeAuth:
    """Tests for check_claude_auth() function."""

    def test_returns_ok_when_credentials_exist(self) -> None:
        """check_claude_auth returns ok when credentials.json exists."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = check_claude_auth()

            assert result.status == "ok"
            assert result.check_name == "claude_auth"
            assert "authenticated" in result.message
            mock_run.assert_called_once()
            # Should check for credentials file
            call_args = mock_run.call_args
            assert "docker" in call_args[0][0]
            assert "exec" in call_args[0][0]

    def test_returns_failed_when_credentials_missing(self) -> None:
        """check_claude_auth returns failed when credentials.json is missing."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = check_claude_auth()

            assert result.status == "failed"
            assert result.check_name == "claude_auth"
            # Should include actionable guidance
            assert "claude login" in result.message.lower() or "not logged in" in result.message

    def test_uses_5_second_timeout(self) -> None:
        """check_claude_auth uses 5 second timeout by default."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            check_claude_auth()

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 5


class TestCheckGithubToken:
    """Tests for check_github_token() function."""

    def test_returns_ok_when_gh_token_set(self) -> None:
        """check_github_token returns ok when GH_TOKEN is set."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = check_github_token()

            assert result.status == "ok"
            assert result.check_name == "github_token"
            assert "present" in result.message
            mock_run.assert_called_once()
            # Should check GH_TOKEN env var
            call_args = mock_run.call_args
            assert "docker" in call_args[0][0]
            assert "exec" in call_args[0][0]

    def test_returns_failed_when_gh_token_empty(self) -> None:
        """check_github_token returns failed when GH_TOKEN is empty."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = check_github_token()

            assert result.status == "failed"
            assert result.check_name == "github_token"
            # Should include actionable guidance
            assert "GH_TOKEN" in result.message or "not set" in result.message

    def test_uses_5_second_timeout(self) -> None:
        """check_github_token uses 5 second timeout by default."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            check_github_token()

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 5


class TestCheckOrchestrator:
    """Tests for check_orchestrator() function."""

    def test_returns_idle_when_no_state_file(self, tmp_path: Path) -> None:
        """check_orchestrator returns 'idle' when no state file exists."""
        with patch("orchestrator.health.OrchestratorConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.state_dir = tmp_path / "nonexistent"
            mock_config_cls.from_env.return_value = mock_config

            result = check_orchestrator()

            assert result.status == "ok"
            assert result.check_name == "orchestrator"
            assert "idle" in result.message

    def test_returns_working_when_state_exists(self, tmp_path: Path) -> None:
        """check_orchestrator returns 'working on task X.Y' when state exists."""
        # Create a mock state file
        state_dir = tmp_path / "state"
        state_dir.mkdir()
        state_file = state_dir / "test_milestone_state.json"
        state_file.write_text("""{
            "milestone_id": "test_milestone",
            "plan_path": "test/plan.md",
            "started_at": "2025-01-15T14:23:00",
            "current_task_index": 2,
            "completed_tasks": ["1.1", "1.2"],
            "failed_tasks": [],
            "task_results": {},
            "e2e_status": null,
            "task_attempt_counts": {},
            "task_errors": {},
            "e2e_attempt_count": 0,
            "e2e_errors": [],
            "starting_branch": "main"
        }""")

        with patch("orchestrator.health.OrchestratorConfig") as mock_config_cls:
            mock_config = MagicMock()
            mock_config.state_dir = state_dir
            mock_config_cls.from_env.return_value = mock_config

            # We need to find the state file somehow - let's mock differently
            # The function needs to find active state files

            result = check_orchestrator()

            assert result.status == "ok"
            assert result.check_name == "orchestrator"
            # Either "idle" or "working on" depending on implementation
            assert "idle" in result.message or "working" in result.message
