"""Tests for LLM-based output interpretation.

These tests verify the LLMInterpreter can:
1. Invoke Claude Code CLI with correct arguments
2. Parse structured JSON responses
3. Handle various failure modes gracefully
4. Truncate large outputs appropriately
"""

import json
from unittest.mock import MagicMock, patch


class TestInterpretationResult:
    """Test the InterpretationResult dataclass."""

    def test_creation_with_all_fields(self):
        """Should create InterpretationResult with all fields."""
        from orchestrator.llm_interpreter import InterpretationResult

        result = InterpretationResult(
            needs_human=True,
            question="Which approach?",
            options=["A", "B"],
            recommendation="A",
            task_completed=False,
            task_failed=False,
            error_message=None,
        )
        assert result.needs_human is True
        assert result.question == "Which approach?"
        assert result.options == ["A", "B"]
        assert result.recommendation == "A"
        assert result.task_completed is False
        assert result.task_failed is False
        assert result.error_message is None

    def test_creation_with_minimal_fields(self):
        """Should create InterpretationResult with minimal fields."""
        from orchestrator.llm_interpreter import InterpretationResult

        result = InterpretationResult(
            needs_human=False,
            question=None,
            options=None,
            recommendation=None,
            task_completed=True,
            task_failed=False,
            error_message=None,
        )
        assert result.needs_human is False
        assert result.task_completed is True

    def test_creation_with_error(self):
        """Should create InterpretationResult with error state."""
        from orchestrator.llm_interpreter import InterpretationResult

        result = InterpretationResult(
            needs_human=False,
            question=None,
            options=None,
            recommendation=None,
            task_completed=False,
            task_failed=True,
            error_message="Module not found",
        )
        assert result.task_failed is True
        assert result.error_message == "Module not found"


class TestLLMInterpreter:
    """Test LLM interpreter with mocked subprocess."""

    def test_uses_correct_model(self):
        """Should use claude-haiku-4.5-20251001 model."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("some output")

            call_args = mock_run.call_args[0][0]
            assert "--model" in call_args
            model_idx = call_args.index("--model") + 1
            assert call_args[model_idx] == "claude-haiku-4.5-20251001"

    def test_uses_no_session_persistence(self):
        """Should use --no-session-persistence flag."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("some output")

            call_args = mock_run.call_args[0][0]
            assert "--no-session-persistence" in call_args

    def test_disables_tools(self):
        """Should use --tools '' to disable tools."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("some output")

            call_args = mock_run.call_args[0][0]
            assert "--tools" in call_args
            tools_idx = call_args.index("--tools") + 1
            assert call_args[tools_idx] == ""

    def test_uses_print_flag(self):
        """Should use --print flag for output-only mode."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("some output")

            call_args = mock_run.call_args[0][0]
            assert "--print" in call_args

    def test_interpret_success_needs_human(self):
        """Should parse valid JSON response indicating needs human."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": True,
                "question": "Which approach should I use?",
                "options": ["Redis", "Memcached"],
                "recommendation": "Redis",
                "task_completed": False,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            assert result.needs_human is True
            assert result.question == "Which approach should I use?"
            assert result.options == ["Redis", "Memcached"]
            assert result.recommendation == "Redis"

    def test_interpret_success_completed(self):
        """Should parse valid JSON response indicating task completed."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("Task completed successfully.")

            assert result.needs_human is False
            assert result.task_completed is True
            assert result.task_failed is False

    def test_interpret_success_failed(self):
        """Should parse valid JSON response indicating task failed."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": False,
                "task_failed": True,
                "error_message": "ModuleNotFoundError: No module named 'foo'",
            }
        )

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("Error: module not found")

            assert result.task_failed is True
            assert "ModuleNotFoundError" in result.error_message

    def test_cli_failure_fallback(self):
        """Should fallback gracefully on CLI error (non-zero return code)."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error: connection failed"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            # Fallback: assume task completed
            assert result.needs_human is False
            assert result.task_completed is True
            assert result.task_failed is False
            # Should indicate there was an interpreter error
            assert "Interpreter error" in result.error_message

    def test_json_parse_error_with_embedded_json(self):
        """Should extract embedded JSON from response with extra text."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """
        Here's my analysis:

        {"needs_human": true, "question": "Which one?", "options": ["A", "B"], "recommendation": "A", "task_completed": false, "task_failed": false, "error_message": null}

        That's the result.
        """

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("output")

            assert result.needs_human is True
            assert result.question == "Which one?"

    def test_json_parse_error_fallback(self):
        """Should fallback gracefully when JSON is unparseable."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "This is not valid JSON at all"

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("output")

            # Fallback: assume task completed
            assert result.needs_human is False
            assert result.task_completed is True
            assert "Interpreter error" in result.error_message

    def test_truncates_large_output(self):
        """Should truncate output that exceeds 8000 characters."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        large_output = "x" * 10000

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret(large_output)

            # Check the prompt passed to CLI doesn't contain full output
            call_args = mock_run.call_args[0][0]
            prompt_idx = call_args.index("-p") + 1
            prompt = call_args[prompt_idx]
            # Large output should be truncated in the prompt
            assert len(prompt) < len(large_output) + 500  # Allow for prompt template

    def test_timeout_handling(self):
        """Should handle subprocess timeout gracefully."""
        import subprocess

        from orchestrator.llm_interpreter import LLMInterpreter

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("cmd", 30)):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            # Fallback: assume task completed
            assert result.needs_human is False
            assert result.task_completed is True
            assert "timeout" in result.error_message.lower()

    def test_custom_model(self):
        """Should allow custom model specification."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter(model="claude-3-5-sonnet-20240620")
            interpreter.interpret("output")

            call_args = mock_run.call_args[0][0]
            model_idx = call_args.index("--model") + 1
            assert call_args[model_idx] == "claude-3-5-sonnet-20240620"

    def test_sets_timeout(self):
        """Should set a timeout for the subprocess call."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("output")

            # Check that timeout was set in the call
            assert mock_run.call_args.kwargs.get("timeout") is not None


class TestInterpretationPrompt:
    """Test the interpretation prompt structure."""

    def test_prompt_contains_output(self):
        """Should include the output in the prompt."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        test_output = "Task completed with 5 tests passing."

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret(test_output)

            call_args = mock_run.call_args[0][0]
            prompt_idx = call_args.index("-p") + 1
            prompt = call_args[prompt_idx]
            assert test_output in prompt

    def test_prompt_requests_json(self):
        """Should request JSON output format in the prompt."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps(
            {
                "needs_human": False,
                "question": None,
                "options": None,
                "recommendation": None,
                "task_completed": True,
                "task_failed": False,
                "error_message": None,
            }
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            interpreter = LLMInterpreter()
            interpreter.interpret("output")

            call_args = mock_run.call_args[0][0]
            prompt_idx = call_args.index("-p") + 1
            prompt = call_args[prompt_idx]
            assert "JSON" in prompt or "json" in prompt


class TestLLMInterpreterIntegration:
    """Integration tests that require Claude CLI.

    These tests call the real Claude CLI and are skipped in CI environments
    or when Claude CLI isn't available. Run locally with Claude CLI installed
    to validate end-to-end LLM interpretation.
    """

    import os
    import shutil

    import pytest

    # Check if Claude CLI is available
    _claude_available = shutil.which("claude") is not None
    _skip_reason = (
        "Skip in CI - requires Claude CLI"
        if os.getenv("CI") == "true"
        else "Claude CLI not found in PATH"
    )

    @pytest.mark.skipif(
        os.getenv("CI") == "true" or not _claude_available,
        reason=_skip_reason,
    )
    def test_real_haiku_interpretation_needs_human(self):
        """Test real CLI call for output that needs human input."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter.interpret(
            "The task says to add caching but doesn't specify the type. "
            "Options: A) Redis B) In-memory. I recommend B for simplicity. "
            "What would you prefer?"
        )

        # LLM should recognize this as needing human input
        assert result.needs_human is True
        # Should extract options or at least recognize they exist
        assert result.options is not None or result.question is not None

    @pytest.mark.skipif(
        os.getenv("CI") == "true" or not _claude_available,
        reason=_skip_reason,
    )
    def test_real_haiku_interpretation_completed(self):
        """Test real CLI call for output that indicates task completion."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter.interpret(
            "Task completed successfully. "
            "I created the file and all 15 tests pass. "
            "The implementation follows existing patterns."
        )

        # LLM should recognize this as completed, no human needed
        assert result.needs_human is False
        assert result.task_completed is True
        assert result.task_failed is False

    @pytest.mark.skipif(
        os.getenv("CI") == "true" or not _claude_available,
        reason=_skip_reason,
    )
    def test_real_haiku_interpretation_failed(self):
        """Test real CLI call for output that indicates task failure."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter.interpret(
            "Task failed. "
            "Error: ModuleNotFoundError - No module named 'nonexistent'. "
            "The import on line 5 references a module that doesn't exist."
        )

        # LLM should recognize this as failed
        assert result.task_failed is True
        assert result.needs_human is False
