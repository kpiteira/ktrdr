"""
Unit tests for research agent invoker service.

Tests cover:
- InvokerConfig loading from environment
- Claude CLI subprocess invocation
- Success/failure detection
- Timeout handling
- Output parsing
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from research_agents.services.invoker import (
    ClaudeCodeInvoker,
    InvocationResult,
    InvokerConfig,
)


class TestInvokerConfig:
    """Tests for InvokerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = InvokerConfig()
        assert config.timeout_seconds == 300  # 5 minutes
        assert config.claude_path == "claude"
        assert config.mcp_config_path is not None

    def test_config_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(
            "os.environ",
            {
                "AGENT_INVOKER_TIMEOUT_SECONDS": "600",
                "CLAUDE_PATH": "/custom/claude",
                "AGENT_MCP_CONFIG_PATH": "/custom/mcp.json",
            },
        ):
            config = InvokerConfig.from_env()
            assert config.timeout_seconds == 600
            assert config.claude_path == "/custom/claude"
            assert config.mcp_config_path == "/custom/mcp.json"

    def test_config_from_env_defaults(self):
        """Test that missing env vars use defaults."""
        with patch.dict("os.environ", {}, clear=True):
            config = InvokerConfig.from_env()
            assert config.timeout_seconds == 300
            assert config.claude_path == "claude"


class TestClaudeCodeInvoker:
    """Tests for ClaudeCodeInvoker."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return InvokerConfig(
            timeout_seconds=30,
            claude_path="claude",
            mcp_config_path="/test/mcp.json",
        )

    @pytest.fixture
    def invoker(self, config):
        """Create invoker with test configuration."""
        return ClaudeCodeInvoker(config=config)

    @pytest.mark.asyncio
    async def test_invoke_success(self, invoker):
        """Test successful invocation returns structured result."""
        mock_result = {
            "role": "assistant",
            "content": "I have completed the task.",
            "stop_reason": "end_turn",
        }

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="Test system prompt",
            )

            assert result.success is True
            assert result.exit_code == 0
            assert result.output == mock_result
            assert result.error is None

    @pytest.mark.asyncio
    async def test_invoke_with_session_context(self, invoker):
        """Test invocation with session context in prompt."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
                session_context={"session_id": 42, "phase": "testing"},
            )

            assert result.success is True
            # Verify the context was included in the call
            call_args = mock_exec.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_invoke_non_zero_exit_code(self, invoker):
        """Test that non-zero exit code is detected as failure."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 1
            mock_process.communicate.return_value = (
                b"",
                b"Error: Something went wrong",
            )
            mock_exec.return_value = mock_process

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            assert result.success is False
            assert result.exit_code == 1
            assert "Something went wrong" in result.error

    @pytest.mark.asyncio
    async def test_invoke_timeout(self, invoker):
        """Test that timeout is handled gracefully."""

        async def slow_communicate():
            await asyncio.sleep(100)  # Long enough to timeout
            return (b"", b"")

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate = slow_communicate
            mock_process.kill = MagicMock()
            mock_exec.return_value = mock_process

            # Use a very short timeout for the test
            invoker.config.timeout_seconds = 0.1

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            assert result.success is False
            assert "timeout" in result.error.lower()
            mock_process.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoke_invalid_json_output(self, invoker):
        """Test handling of invalid JSON output from Claude."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                b"This is not valid JSON",
                b"",
            )
            mock_exec.return_value = mock_process

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            # Should still succeed with raw output
            assert result.success is True
            assert result.raw_output == "This is not valid JSON"

    @pytest.mark.asyncio
    async def test_invoke_uses_mcp_config(self, invoker):
        """Test that MCP config is passed to Claude CLI."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            # Verify --mcp-config flag was passed
            call_args = mock_exec.call_args
            args = call_args[0]
            assert "--mcp-config" in args
            assert "/test/mcp.json" in args

    @pytest.mark.asyncio
    async def test_invoke_uses_print_mode(self, invoker):
        """Test that Claude is invoked in print mode (non-interactive)."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            call_args = mock_exec.call_args
            args = call_args[0]
            assert "--print" in args or "-p" in args

    @pytest.mark.asyncio
    async def test_invoke_uses_json_output(self, invoker):
        """Test that Claude is configured for JSON output."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            call_args = mock_exec.call_args
            args = call_args[0]
            assert "--output-format" in args
            assert "json" in args

    @pytest.mark.asyncio
    async def test_invoke_passes_system_prompt(self, invoker):
        """Test that system prompt is passed to Claude."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            await invoker.invoke(
                prompt="User prompt",
                system_prompt="Custom system prompt",
            )

            call_args = mock_exec.call_args
            args = call_args[0]
            assert "--system-prompt" in args

    @pytest.mark.asyncio
    async def test_invoke_without_system_prompt(self, invoker):
        """Test invocation without system prompt."""
        mock_result = {"role": "assistant", "content": "Done"}

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (
                json.dumps(mock_result).encode(),
                b"",
            )
            mock_exec.return_value = mock_process

            result = await invoker.invoke(
                prompt="User prompt",
                system_prompt=None,
            )

            assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_subprocess_exception(self, invoker):
        """Test handling of subprocess creation failure."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.side_effect = OSError("Claude CLI not found")

            result = await invoker.invoke(
                prompt="Test prompt",
                system_prompt="System prompt",
            )

            assert result.success is False
            assert "Claude CLI not found" in result.error


class TestInvocationResult:
    """Tests for InvocationResult dataclass."""

    def test_successful_result(self):
        """Test creating a successful result."""
        result = InvocationResult(
            success=True,
            exit_code=0,
            output={"content": "done"},
            raw_output='{"content": "done"}',
            error=None,
        )
        assert result.success is True
        assert result.exit_code == 0

    def test_failed_result(self):
        """Test creating a failed result."""
        result = InvocationResult(
            success=False,
            exit_code=1,
            output=None,
            raw_output="",
            error="Something failed",
        )
        assert result.success is False
        assert result.error == "Something failed"
