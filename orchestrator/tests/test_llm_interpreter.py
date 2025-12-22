"""Tests for LLM-based output interpretation.

These tests verify the LLMInterpreter can:
1. Invoke Claude Code CLI with correct arguments
2. Parse structured JSON responses
3. Handle various failure modes gracefully
4. Truncate large outputs appropriately
"""

import json
from unittest.mock import MagicMock, patch


class TestStripMarkdown:
    """Test the strip_markdown utility function."""

    def test_strips_bold_asterisks(self):
        """Should remove **bold** formatting."""
        from orchestrator.llm_interpreter import strip_markdown

        assert strip_markdown("**Hello** world") == "Hello world"
        assert strip_markdown("This is **very important**") == "This is very important"

    def test_strips_bold_underscores(self):
        """Should remove __bold__ formatting."""
        from orchestrator.llm_interpreter import strip_markdown

        assert strip_markdown("__Hello__ world") == "Hello world"

    def test_strips_headers(self):
        """Should remove # header markers."""
        from orchestrator.llm_interpreter import strip_markdown

        assert strip_markdown("# Header") == "Header"
        assert strip_markdown("## Subheader") == "Subheader"
        assert strip_markdown("### Deep header") == "Deep header"

    def test_strips_multiline_headers(self):
        """Should remove headers from each line."""
        from orchestrator.llm_interpreter import strip_markdown

        result = strip_markdown("# Title\n## Section\nPlain text")
        assert result == "Title\nSection\nPlain text"

    def test_handles_none(self):
        """Should return None for None input."""
        from orchestrator.llm_interpreter import strip_markdown

        assert strip_markdown(None) is None

    def test_handles_empty_string(self):
        """Should return empty string for empty input."""
        from orchestrator.llm_interpreter import strip_markdown

        assert strip_markdown("") == ""

    def test_preserves_underscores_in_identifiers(self):
        """Should not break variable names with underscores."""
        from orchestrator.llm_interpreter import strip_markdown

        result = strip_markdown("Use my_variable_name in the code")
        assert "my_variable_name" in result

    def test_complex_markdown(self):
        """Should handle text with mixed markdown."""
        from orchestrator.llm_interpreter import strip_markdown

        text = "**QUESTION:** This task asks for caching but lacks **critical** specs"
        result = strip_markdown(text)
        assert "QUESTION:" in result
        assert "critical" in result
        assert "**" not in result

    def test_strips_orphan_bold_at_start(self):
        """Should remove ** at start of line without closing **."""
        from orchestrator.llm_interpreter import strip_markdown

        # This pattern appears in Claude output: "**QUESTION:" without closing **
        result = strip_markdown("** This task asks for clarification")
        assert result == "This task asks for clarification"
        assert "**" not in result

    def test_strips_orphan_bold_multiline(self):
        """Should remove orphan ** from multiple lines."""
        from orchestrator.llm_interpreter import strip_markdown

        text = "**QUESTION: What approach?\n** Option A\n** Option B"
        result = strip_markdown(text)
        assert "**" not in result
        assert "QUESTION:" in result
        assert "Option A" in result
        assert "Option B" in result


class TestJsonExtraction:
    """Test the JSON extraction helper."""

    import pytest

    @pytest.fixture(autouse=True)
    def mock_claude_cli(self):
        """Mock find_claude_cli for all tests in this class."""
        with patch(
            "orchestrator.llm_interpreter.find_claude_cli",
            return_value="/usr/bin/claude",
        ):
            yield

    def test_extracts_simple_json(self):
        """Should extract simple JSON object."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter._extract_json_object('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extracts_json_with_surrounding_text(self):
        """Should extract JSON from text with preamble and postamble."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        text = 'Here is the result:\n{"needs_human": true}\nThat is all.'
        result = interpreter._extract_json_object(text)
        assert result == {"needs_human": True}

    def test_handles_nested_json(self):
        """Should handle JSON with nested objects."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = interpreter._extract_json_object(text)
        assert result == {"outer": {"inner": "value"}, "list": [1, 2, 3]}

    def test_handles_braces_in_strings(self):
        """Should correctly handle JSON with braces inside string values."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        text = '{"message": "Use {variable} syntax"}'
        result = interpreter._extract_json_object(text)
        assert result == {"message": "Use {variable} syntax"}

    def test_handles_escaped_quotes(self):
        """Should handle escaped quotes in strings."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        text = r'{"message": "He said \"hello\""}'
        result = interpreter._extract_json_object(text)
        assert result == {"message": 'He said "hello"'}

    def test_returns_none_for_no_json(self):
        """Should return None when no JSON is found."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter._extract_json_object("No JSON here")
        assert result is None

    def test_returns_none_for_invalid_json(self):
        """Should return None for malformed JSON."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        result = interpreter._extract_json_object('{"unclosed": "value"')
        assert result is None


class TestDataCleaning:
    """Test the data cleaning for markdown removal."""

    import pytest

    @pytest.fixture(autouse=True)
    def mock_claude_cli(self):
        """Mock find_claude_cli for all tests in this class."""
        with patch(
            "orchestrator.llm_interpreter.find_claude_cli",
            return_value="/usr/bin/claude",
        ):
            yield

    def test_cleans_string_values(self):
        """Should clean markdown from string values."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        data = {"question": "**QUESTION:** What approach?", "recommendation": "Use **Redis**"}
        result = interpreter._clean_data(data)

        assert "**" not in result["question"]
        assert "QUESTION:" in result["question"]
        assert "**" not in result["recommendation"]
        assert "Redis" in result["recommendation"]

    def test_cleans_list_values(self):
        """Should clean markdown from list items."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        data = {"options": ["**Option A** - first", "__Option B__ - second"]}
        result = interpreter._clean_data(data)

        assert "**" not in result["options"][0]
        assert "Option A" in result["options"][0]
        assert "__" not in result["options"][1]
        assert "Option B" in result["options"][1]

    def test_preserves_boolean_values(self):
        """Should not modify boolean values."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        data = {"needs_human": True, "task_completed": False}
        result = interpreter._clean_data(data)

        assert result["needs_human"] is True
        assert result["task_completed"] is False

    def test_preserves_none_values(self):
        """Should preserve None values."""
        from orchestrator.llm_interpreter import LLMInterpreter

        interpreter = LLMInterpreter()
        data = {"question": None, "options": None}
        result = interpreter._clean_data(data)

        assert result["question"] is None
        assert result["options"] is None


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

    import pytest

    @pytest.fixture(autouse=True)
    def mock_claude_cli(self):
        """Mock find_claude_cli for all tests in this class."""
        with patch(
            "orchestrator.llm_interpreter.find_claude_cli",
            return_value="/usr/bin/claude",
        ):
            yield

    def test_uses_correct_model(self):
        """Should use claude-haiku-4-5-20251001 model."""
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
            assert call_args[model_idx] == "claude-haiku-4-5-20251001"

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
        """Should use --allowedTools '' to disable tools."""
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
            assert "--allowedTools" in call_args
            tools_idx = call_args.index("--allowedTools") + 1
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
        """Should fallback to escalation on CLI error (non-zero return code)."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error: connection failed"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            # Fallback: escalate when uncertain (safer than assuming completed)
            assert result.needs_human is True
            assert result.task_completed is False
            assert result.task_failed is False
            # Should indicate there was an interpreter error
            assert "Interpreter error" in result.error_message

    def test_cli_terms_acceptance_error(self):
        """Should provide clear message when Claude CLI needs terms acceptance."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = (
            "[ACTION REQUIRED] An update to our Consumer Terms and Privacy Policy "
            "has taken effect. You must run `claude` to review the updated terms."
        )
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("some output")

            assert result.needs_human is True
            assert "terms acceptance" in result.error_message.lower()
            assert "run 'claude'" in result.error_message.lower()

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
        """Should fallback to escalation when JSON is unparseable."""
        from orchestrator.llm_interpreter import LLMInterpreter

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "This is not valid JSON at all"

        with patch("subprocess.run", return_value=mock_result):
            interpreter = LLMInterpreter()
            result = interpreter.interpret("output")

            # Fallback: escalate when uncertain (safer than assuming completed)
            assert result.needs_human is True
            assert result.task_completed is False
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

            # Fallback: escalate when uncertain (safer than assuming completed)
            assert result.needs_human is True
            assert result.task_completed is False
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

    import pytest

    @pytest.fixture(autouse=True)
    def mock_claude_cli(self):
        """Mock find_claude_cli for all tests in this class."""
        with patch(
            "orchestrator.llm_interpreter.find_claude_cli",
            return_value="/usr/bin/claude",
        ):
            yield

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
