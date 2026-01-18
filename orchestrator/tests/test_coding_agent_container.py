"""Tests for coding agent container module.

These tests verify coding agent container interaction via mocked subprocess calls.
"""

import json
import subprocess
from dataclasses import is_dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCodingAgentContainerStructure:
    """Test CodingAgentContainer class structure."""

    def test_coding_agent_container_is_dataclass(self):
        """CodingAgentContainer should be a dataclass."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        assert is_dataclass(CodingAgentContainer)

    def test_coding_agent_container_defaults(self):
        """CodingAgentContainer should have sensible defaults."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()
        assert manager.container_name == "ktrdr-coding-agent"
        assert manager.workspace_path == "/workspace"
        assert manager.image_name == "ktrdr-coding-agent:latest"


class TestCodingAgentContainerExec:
    """Test exec() method for running commands."""

    @pytest.mark.asyncio
    async def test_exec_runs_docker_command(self):
        """exec() should run docker exec with the command."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

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
            assert "ktrdr-coding-agent" in call_args[0][0]
            assert result == "hello world\n"

    @pytest.mark.asyncio
    async def test_exec_raises_on_nonzero_exit(self):
        """exec() should raise CodingAgentError on non-zero exit."""
        from orchestrator.coding_agent_container import (
            CodingAgentContainer,
            CodingAgentError,
        )

        manager = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="command not found",
            )

            with pytest.raises(CodingAgentError) as exc_info:
                await manager.exec("invalid_command")

            assert "command not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_exec_timeout_raises_exception(self):
        """exec() should raise TimeoutError on timeout."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd=["docker", "exec"], timeout=10
            )

            with pytest.raises(subprocess.TimeoutExpired):
                await manager.exec("sleep 100", timeout=10)

    @pytest.mark.asyncio
    async def test_exec_uses_custom_timeout(self):
        """exec() should pass timeout to subprocess."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")

            await manager.exec("echo ok", timeout=120)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 120


class TestCodingAgentContainerInvokeClaude:
    """Test invoke_claude() method."""

    @pytest.mark.asyncio
    async def test_invoke_claude_returns_claude_result(self):
        """invoke_claude() should return parsed ClaudeResult."""
        from orchestrator.coding_agent_container import CodingAgentContainer
        from orchestrator.models import ClaudeResult

        manager = CodingAgentContainer()

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
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

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
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

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
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

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
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

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
        from orchestrator.coding_agent_container import (
            CodingAgentContainer,
            CodingAgentError,
        )

        manager = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="not valid json",
                stderr="",
            )

            with pytest.raises(CodingAgentError) as exc_info:
                await manager.invoke_claude("Do something")

            assert (
                "JSON" in str(exc_info.value) or "parse" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_invoke_claude_timeout(self):
        """invoke_claude() should respect timeout."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout=json.dumps({"is_error": False, "result": "ok"}),
                stderr="",
            )

            await manager.invoke_claude("Do something", timeout=1200)

            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 1200


class TestCodingAgentError:
    """Test CodingAgentError exception."""

    def test_coding_agent_error_exists(self):
        """CodingAgentError should be importable."""
        from orchestrator.coding_agent_container import CodingAgentError

        assert issubclass(CodingAgentError, Exception)

    def test_coding_agent_error_message(self):
        """CodingAgentError should accept message."""
        from orchestrator.coding_agent_container import CodingAgentError

        error = CodingAgentError("Test error message")
        assert "Test error message" in str(error)


class TestInvokeClaudeStreaming:
    """Tests for invoke_claude_streaming() method."""

    @pytest.mark.asyncio
    async def test_uses_stream_json_output_format(self):
        """invoke_claude_streaming() should use --output-format stream-json."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        # Stream events: assistant with tool_use content, then result
        stream_output = (
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "test.py"}}]}}\n'
            '{"type": "result", "is_error": false, "result": "Done", "total_cost_usd": 0.05, "duration_ms": 1000, "num_turns": 2, "session_id": "test123"}\n'
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            await manager.invoke_claude_streaming(
                "Do something", on_tool_use=lambda n, i: None
            )

            # Verify stream-json format is used
            call_args = mock_popen.call_args[0][0]
            assert "--output-format" in call_args
            format_idx = call_args.index("--output-format")
            assert call_args[format_idx + 1] == "stream-json"

    @pytest.mark.asyncio
    async def test_calls_callback_for_tool_use_events(self):
        """invoke_claude_streaming() should call callback for each tool_use event."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        stream_output = (
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "config.py"}}]}}\n'
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "output.py"}}]}}\n'
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "pytest tests/"}}]}}\n'
            '{"type": "result", "is_error": false, "result": "Done", "total_cost_usd": 0.1, "duration_ms": 5000, "num_turns": 5, "session_id": "test456"}\n'
        )

        tool_calls: list[tuple[str, dict]] = []

        def on_tool(name: str, input_data: dict) -> None:
            tool_calls.append((name, input_data))

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            await manager.invoke_claude_streaming("Do something", on_tool_use=on_tool)

        assert len(tool_calls) == 3
        assert tool_calls[0] == ("Read", {"file_path": "config.py"})
        assert tool_calls[1] == ("Write", {"file_path": "output.py"})
        assert tool_calls[2] == ("Bash", {"command": "pytest tests/"})

    @pytest.mark.asyncio
    async def test_returns_claude_result_from_result_event(self):
        """invoke_claude_streaming() should return ClaudeResult from result event."""
        from orchestrator.coding_agent_container import CodingAgentContainer
        from orchestrator.models import ClaudeResult

        manager = CodingAgentContainer()

        stream_output = (
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "test.py"}}]}}\n'
            '{"type": "result", "is_error": false, "result": "Task completed", "total_cost_usd": 0.08, "duration_ms": 12000, "num_turns": 7, "session_id": "session789"}\n'
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = await manager.invoke_claude_streaming(
                "Do something", on_tool_use=lambda n, i: None
            )

        assert isinstance(result, ClaudeResult)
        assert result.is_error is False
        assert result.result == "Task completed"
        assert result.total_cost_usd == 0.08
        assert result.duration_ms == 12000
        assert result.num_turns == 7
        assert result.session_id == "session789"

    @pytest.mark.asyncio
    async def test_handles_error_result(self):
        """invoke_claude_streaming() should handle error results."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        stream_output = '{"type": "result", "is_error": true, "result": "Something failed", "total_cost_usd": 0.01, "duration_ms": 1000, "num_turns": 1, "session_id": "err123"}\n'

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = await manager.invoke_claude_streaming(
                "Do something", on_tool_use=lambda n, i: None
            )

        assert result.is_error is True
        assert "failed" in result.result

    @pytest.mark.asyncio
    async def test_handles_malformed_json_gracefully(self):
        """invoke_claude_streaming() should skip malformed JSON lines."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        stream_output = (
            "not valid json\n"
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "test.py"}}]}}\n'
            '{"broken json\n'
            '{"type": "result", "is_error": false, "result": "Done", "total_cost_usd": 0.05, "duration_ms": 2000, "num_turns": 2, "session_id": "test"}\n'
        )

        tool_calls: list[tuple[str, dict]] = []

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = await manager.invoke_claude_streaming(
                "Do something",
                on_tool_use=lambda n, i: tool_calls.append((n, i)),
            )

        # Should still work - skipped bad lines
        assert len(tool_calls) == 1
        assert result.result == "Done"

    @pytest.mark.asyncio
    async def test_passes_parameters_correctly(self):
        """invoke_claude_streaming() should pass max_turns and tools."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        stream_output = '{"type": "result", "is_error": false, "result": "Done", "total_cost_usd": 0.01, "duration_ms": 1000, "num_turns": 1, "session_id": "test"}\n'

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            await manager.invoke_claude_streaming(
                "Do something",
                on_tool_use=lambda n, i: None,
                max_turns=100,
                allowed_tools=["Bash", "Read"],
            )

            call_args = mock_popen.call_args[0][0]

            # Verify max-turns
            assert "--max-turns" in call_args
            idx = call_args.index("--max-turns")
            assert call_args[idx + 1] == "100"

            # Verify allowed tools
            assert "--allowedTools" in call_args
            idx = call_args.index("--allowedTools")
            assert "Bash" in call_args[idx + 1]
            assert "Read" in call_args[idx + 1]

    @pytest.mark.asyncio
    async def test_default_result_when_no_result_event(self):
        """invoke_claude_streaming() should return default result if no result event."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        manager = CodingAgentContainer()

        # No result event, just tool uses
        stream_output = (
            '{"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "test.py"}}]}}\n'
            "\n"
        )

        with patch("subprocess.Popen") as mock_popen:
            mock_process = MagicMock()
            mock_process.stdout.__iter__ = MagicMock(
                return_value=iter(stream_output.split("\n"))
            )
            mock_process.wait.return_value = 0
            mock_popen.return_value = mock_process

            result = await manager.invoke_claude_streaming(
                "Do something", on_tool_use=lambda n, i: None
            )

        # Should return a default result
        assert result.is_error is True
        assert "No result" in result.result or result.result == ""


class TestFormatToolCall:
    """Tests for format_tool_call helper function."""

    def test_format_read_shows_filename(self):
        """format_tool_call should show filename for Read."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Read", {"file_path": "/path/to/config.py"})
        assert "config.py" in result
        assert "Reading" in result

    def test_format_write_shows_filename(self):
        """format_tool_call should show filename for Write."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Write", {"file_path": "/path/to/output.py"})
        assert "output.py" in result
        assert "Writing" in result

    def test_format_edit_shows_filename(self):
        """format_tool_call should show filename for Edit."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Edit", {"file_path": "/path/to/module.py"})
        assert "module.py" in result
        assert "Editing" in result

    def test_format_bash_shows_truncated_command(self):
        """format_tool_call should show first 50 chars of Bash command."""
        from orchestrator.coding_agent_container import format_tool_call

        long_command = (
            "pytest tests/unit/ tests/integration/ -v --tb=short --cov=orchestrator"
        )
        result = format_tool_call("Bash", {"command": long_command})

        assert "Running:" in result
        # Should be truncated
        assert len(result) < len(long_command) + 30  # "→ Running: " + cmd + "..."
        assert "..." in result or len(long_command) <= 50

    def test_format_bash_short_command_not_truncated(self):
        """format_tool_call should not truncate short commands."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Bash", {"command": "ls -la"})
        assert "ls -la" in result
        assert "..." not in result

    def test_format_grep_shows_pattern(self):
        """format_tool_call should show pattern for Grep."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Grep", {"pattern": "def test_"})
        assert "def test_" in result
        assert "Searching" in result

    def test_format_glob_shows_pattern(self):
        """format_tool_call should show pattern for Glob."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("Glob", {"pattern": "**/*.py"})
        assert "**/*.py" in result

    def test_format_unknown_tool(self):
        """format_tool_call should handle unknown tools."""
        from orchestrator.coding_agent_container import format_tool_call

        result = format_tool_call("UnknownTool", {"some": "param"})
        assert "UnknownTool" in result
        assert "→" in result


class TestCodingAgentContainerLifecycle:
    """Tests for container start() and stop() lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_runs_docker_with_volume_mount(self):
        """start() should run docker with -v flag for volume mount."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()
        code_folder = Path("/home/user/myproject")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(code_folder)

            # Should have called docker rm first, then docker run
            assert mock_run.call_count == 2

            # Second call should be docker run with volume mount
            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            assert "docker" in cmd
            assert "run" in cmd
            assert "-v" in cmd
            # Check volume mount format: /path:/workspace
            volume_idx = cmd.index("-v")
            volume_arg = cmd[volume_idx + 1]
            assert str(code_folder) in volume_arg
            assert ":/workspace" in volume_arg

    @pytest.mark.asyncio
    async def test_start_includes_host_gateway(self):
        """start() should include --add-host=host.docker.internal:host-gateway."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(Path("/home/user/myproject"))

            # Check docker run call
            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            assert "--add-host=host.docker.internal:host-gateway" in cmd

    @pytest.mark.asyncio
    async def test_start_removes_existing_container_first(self):
        """start() should run docker rm -f before docker run."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(Path("/home/user/myproject"))

            # First call should be docker rm -f
            rm_call = mock_run.call_args_list[0]
            cmd = rm_call[0][0]
            assert "docker" in cmd
            assert "rm" in cmd
            assert "-f" in cmd
            assert "ktrdr-coding-agent" in cmd

    @pytest.mark.asyncio
    async def test_start_raises_on_failure(self):
        """start() should raise CodingAgentError on docker failure."""
        from orchestrator.coding_agent_container import (
            CodingAgentContainer,
            CodingAgentError,
        )

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            # rm succeeds, run fails
            mock_run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),  # rm
                MagicMock(returncode=1, stdout="", stderr="image not found"),  # run
            ]

            with pytest.raises(CodingAgentError) as exc_info:
                await container.start(Path("/home/user/myproject"))

            assert "image not found" in str(exc_info.value) or "docker" in str(
                exc_info.value
            ).lower()

    @pytest.mark.asyncio
    async def test_stop_removes_container(self):
        """stop() should run docker rm -f."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.stop()

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "docker" in cmd
            assert "rm" in cmd
            assert "-f" in cmd
            assert "ktrdr-coding-agent" in cmd

    @pytest.mark.asyncio
    async def test_stop_is_best_effort_on_failure(self):
        """stop() should not raise when container doesn't exist (best-effort cleanup)."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            # Simulate container not existing
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="No such container"
            )

            # Should not raise - best-effort cleanup
            await container.stop()

            # Should still have attempted removal
            mock_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_resolves_to_absolute_path(self):
        """start() should resolve code_folder to absolute path for Docker."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()
        relative_path = Path("relative/path")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(relative_path)

            # docker run call should use absolute path
            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            volume_idx = cmd.index("-v")
            volume_arg = cmd[volume_idx + 1]
            # Should be absolute (starts with /)
            assert volume_arg.startswith("/"), f"Expected absolute path, got: {volume_arg}"

    @pytest.mark.asyncio
    async def test_start_uses_image_name(self):
        """start() should use the image_name attribute."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer(image_name="custom-image:v1")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(Path("/home/user/myproject"))

            # docker run call should use the custom image
            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            assert "custom-image:v1" in cmd

    @pytest.mark.asyncio
    async def test_start_uses_detached_mode(self):
        """start() should use -d flag for detached mode."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(Path("/home/user/myproject"))

            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            assert "-d" in cmd

    @pytest.mark.asyncio
    async def test_start_uses_container_name(self):
        """start() should use --name flag with container_name."""
        from orchestrator.coding_agent_container import CodingAgentContainer

        container = CodingAgentContainer(container_name="my-test-container")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            await container.start(Path("/home/user/myproject"))

            run_call = mock_run.call_args_list[1]
            cmd = run_call[0][0]
            assert "--name" in cmd
            name_idx = cmd.index("--name")
            assert cmd[name_idx + 1] == "my-test-container"
