"""Tests for sandbox manager module.

These tests verify sandbox container interaction via mocked subprocess calls.
"""

import json
import subprocess
from dataclasses import is_dataclass
from unittest.mock import MagicMock, patch

import pytest


class TestSandboxManagerStructure:
    """Test SandboxManager class structure."""

    def test_sandbox_manager_is_dataclass(self):
        """SandboxManager should be a dataclass."""
        from orchestrator.sandbox import SandboxManager

        assert is_dataclass(SandboxManager)

    def test_sandbox_manager_defaults(self):
        """SandboxManager should have sensible defaults."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()
        assert manager.container_name == "ktrdr-sandbox"
        assert manager.workspace_path == "/workspace"


class TestSandboxExec:
    """Test exec() method for running commands."""

    @pytest.mark.asyncio
    async def test_exec_runs_docker_command(self):
        """exec() should run docker exec with the command."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="hello world\n",
                stderr="",
            )

            result = await manager.exec("echo hello world")

            mock_run.assert_called_once()
            call_args = mock_run.call_args
            assert "docker" in call_args[0][0]
            assert "exec" in call_args[0][0]
            assert "ktrdr-sandbox" in call_args[0][0]
            assert result == "hello world\n"

    @pytest.mark.asyncio
    async def test_exec_raises_on_nonzero_exit(self):
        """exec() should raise SandboxError on non-zero exit."""
        from orchestrator.sandbox import SandboxError, SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="command not found",
            )

            with pytest.raises(SandboxError) as exc_info:
                await manager.exec("invalid_command")

            assert "command not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exec_timeout_raises_exception(self):
        """exec() should raise TimeoutError on timeout."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["docker", "exec"], timeout=10
            )

            with pytest.raises(subprocess.TimeoutExpired):
                await manager.exec("sleep 100", timeout=10)

    @pytest.mark.asyncio
    async def test_exec_uses_custom_timeout(self):
        """exec() should pass timeout to subprocess."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

            await manager.exec("echo ok", timeout=120)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 120


class TestSandboxInvokeClaude:
    """Test invoke_claude() method."""

    @pytest.mark.asyncio
    async def test_invoke_claude_returns_claude_result(self):
        """invoke_claude() should return parsed ClaudeResult."""
        from orchestrator.models import ClaudeResult
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        claude_output = {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Task completed successfully",
            "total_cost_usd": 0.08,
            "duration_ms": 148000,
            "num_turns": 6,
            "session_id": "abc123-def456",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(claude_output),
                stderr="",
            )

            result = await manager.invoke_claude("Do something")

            assert isinstance(result, ClaudeResult)
            assert result.is_error is False
            assert result.result == "Task completed successfully"
            assert result.total_cost_usd == 0.08
            assert result.num_turns == 6
            assert result.session_id == "abc123-def456"

    @pytest.mark.asyncio
    async def test_invoke_claude_uses_json_output_format(self):
        """invoke_claude() should use --output-format json."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="",
            )

            await manager.invoke_claude("Do something")

            call_args = mock_run.call_args[0][0]
            assert "--output-format" in call_args
            assert "json" in call_args

    @pytest.mark.asyncio
    async def test_invoke_claude_passes_max_turns(self):
        """invoke_claude() should pass max_turns to CLI."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="",
            )

            await manager.invoke_claude("Do something", max_turns=100)

            call_args = mock_run.call_args[0][0]
            assert "--max-turns" in call_args
            # Find position of --max-turns and check next value
            idx = call_args.index("--max-turns")
            assert call_args[idx + 1] == "100"

    @pytest.mark.asyncio
    async def test_invoke_claude_passes_allowed_tools(self):
        """invoke_claude() should pass allowed tools to CLI."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="",
            )

            await manager.invoke_claude(
                "Do something",
                allowed_tools=["Bash", "Read", "Write"],
            )

            call_args = mock_run.call_args[0][0]
            assert "--allowedTools" in call_args
            idx = call_args.index("--allowedTools")
            assert "Bash" in call_args[idx + 1]
            assert "Read" in call_args[idx + 1]

    @pytest.mark.asyncio
    async def test_invoke_claude_handles_error_response(self):
        """invoke_claude() should handle error responses."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        claude_output = {
            "type": "result",
            "subtype": "error",
            "is_error": True,
            "result": "Something went wrong",
            "session_id": "error-session",
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps(claude_output),
                stderr="",
            )

            result = await manager.invoke_claude("Do something")

            assert result.is_error is True
            assert "wrong" in result.result

    @pytest.mark.asyncio
    async def test_invoke_claude_raises_on_invalid_json(self):
        """invoke_claude() should raise on invalid JSON output."""
        from orchestrator.sandbox import SandboxError, SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )

            with pytest.raises(SandboxError) as exc_info:
                await manager.invoke_claude("Do something")

            assert (
                "JSON" in str(exc_info.value) or "parse" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_invoke_claude_timeout(self):
        """invoke_claude() should respect timeout."""
        from orchestrator.sandbox import SandboxManager

        manager = SandboxManager()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="",
            )

            await manager.invoke_claude("Do something", timeout=1200)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 1200


class TestSandboxError:
    """Test SandboxError exception."""

    def test_sandbox_error_exists(self):
        """SandboxError should be importable."""
        from orchestrator.sandbox import SandboxError

        assert issubclass(SandboxError, Exception)

    def test_sandbox_error_message(self):
        """SandboxError should accept message."""
        from orchestrator.sandbox import SandboxError

        error = SandboxError("Test error message")
        assert "Test error message" in str(error)
