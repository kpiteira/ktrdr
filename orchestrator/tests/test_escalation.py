"""Tests for escalation detection and handling.

These tests verify the escalation module can:
1. Detect when Claude's output indicates human input is needed
2. Extract structured questions, options, and recommendations
3. Fall back to heuristics when output is unstructured
"""

from unittest.mock import MagicMock, patch

import pytest

from ktrdr.llm.haiku_brain import InterpretationResult


# Fixture to mock HaikuBrain for pattern tests
@pytest.fixture
def mock_brain_needs_help():
    """Mock HaikuBrain that returns status=needs_help."""
    result = InterpretationResult(
        status="needs_help",
        summary="Mock summary",
        error=None,
        question="Mock question",
        options=None,
        recommendation=None,
    )
    with patch("orchestrator.runner.get_brain") as mock_get:
        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = result
        mock_get.return_value = mock_brain
        yield mock_brain


@pytest.fixture
def mock_brain_completed():
    """Mock HaikuBrain that returns status=completed (no human needed)."""
    result = InterpretationResult(
        status="completed",
        summary="Task completed successfully",
        error=None,
        question=None,
        options=None,
        recommendation=None,
    )
    with patch("orchestrator.runner.get_brain") as mock_get:
        mock_brain = MagicMock()
        mock_brain.interpret_result.return_value = result
        mock_get.return_value = mock_brain
        yield mock_brain


class TestDetectNeedsHuman:
    """Test the detect_needs_human function."""

    def test_detects_explicit_status_needs_human(self):
        """Should detect explicit STATUS: needs_human marker (fast-path)."""
        from orchestrator.runner import detect_needs_human

        output = """
        I've analyzed the task but need clarification.

        STATUS: needs_human

        The requirements are ambiguous.
        """
        # Fast-path: no LLM call needed
        assert detect_needs_human(output) is True

    def test_detects_needs_human_marker(self):
        """Should detect NEEDS_HUMAN: marker (fast-path)."""
        from orchestrator.runner import detect_needs_human

        output = """
        NEEDS_HUMAN: The cache implementation type is not specified.
        """
        # Fast-path: no LLM call needed
        assert detect_needs_human(output) is True

    def test_detects_options_marker(self, mock_brain_needs_help):
        """Should detect OPTIONS: marker via LLM."""
        from orchestrator.runner import detect_needs_human

        output = """
        The task says to add caching but doesn't specify the type.

        OPTIONS:
        A) Redis (distributed, persistent)
        B) In-memory (fast, local only)
        """
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_should_i_pattern(self, mock_brain_needs_help):
        """Should detect 'should I' question pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "The tests are failing. Should I fix them before proceeding?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_would_you_prefer_pattern(self, mock_brain_needs_help):
        """Should detect 'would you prefer' question pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "Would you prefer option A or option B for the implementation?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_im_not_sure_pattern(self, mock_brain_needs_help):
        """Should detect 'I'm not sure' uncertainty pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "I'm not sure whether to use Redis or Memcached for this."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_im_uncertain_pattern(self, mock_brain_needs_help):
        """Should detect 'I'm uncertain' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "I'm uncertain about the best approach here."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_options_are_pattern(self, mock_brain_needs_help):
        """Should detect 'the options are' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "The options are: use a database or a file system."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_recommend_but_pattern(self, mock_brain_needs_help):
        """Should detect 'I recommend X but' pattern (hedging) via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "I recommend using Redis but you might prefer something simpler."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_could_go_either_way_pattern(self, mock_brain_needs_help):
        """Should detect 'could go either way' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "This could go either way - both approaches have merits."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_what_would_you_like_pattern(self, mock_brain_needs_help):
        """Should detect 'what would you like' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "What would you like me to prioritize first?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_do_you_want_me_to_pattern(self, mock_brain_needs_help):
        """Should detect 'do you want me to' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "Do you want me to refactor the entire module or just this function?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_returns_false_for_completed_output(self, mock_brain_completed):
        """Should return False for definitive completed output."""
        from orchestrator.runner import detect_needs_human

        output = """
        Task completed successfully.

        I created the file and ran the tests. All 15 tests pass.
        The implementation follows the existing patterns.
        """
        assert detect_needs_human(output) is False
        mock_brain_completed.interpret_result.assert_called_once()

    def test_returns_false_for_error_output(self, mock_brain_completed):
        """Should return False for error output without uncertainty."""
        from orchestrator.runner import detect_needs_human

        output = """
        Task failed.

        Error: Module 'nonexistent' not found.
        The import statement on line 5 references a module that doesn't exist.
        """
        assert detect_needs_human(output) is False
        mock_brain_completed.interpret_result.assert_called_once()

    def test_case_insensitive_matching(self, mock_brain_needs_help):
        """Patterns should be detected via LLM regardless of case."""
        from orchestrator.runner import detect_needs_human

        output = "SHOULD I proceed with the refactoring?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_markdown_options(self, mock_brain_needs_help):
        """Should detect **Options:** with markdown bold formatting via LLM."""
        from orchestrator.runner import detect_needs_human

        output = """
        The file doesn't exist.

        **Options:**

        1. Did you mean one of these existing files?
        2. Should I create it?
        """
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_lowercase_options(self, mock_brain_needs_help):
        """Should detect options: in lowercase via LLM."""
        from orchestrator.runner import detect_needs_human

        output = """
        options:
        - Use Redis
        - Use Memcached
        """
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_please_clarify(self, mock_brain_needs_help):
        """Should detect 'please clarify' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "Please clarify which implementation plan you'd like me to work with."
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_did_you_mean(self, mock_brain_needs_help):
        """Should detect 'did you mean' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "Did you mean one of these existing files?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()

    def test_detects_which_would_you(self, mock_brain_needs_help):
        """Should detect 'which X would you' pattern via LLM."""
        from orchestrator.runner import detect_needs_human

        output = "Which approach would you like me to take?"
        assert detect_needs_human(output) is True
        mock_brain_needs_help.interpret_result.assert_called_once()


class TestExtractEscalationInfo:
    """Test the extract_escalation_info function."""

    def test_extracts_structured_question(self):
        """Should extract QUESTION: from structured format."""
        from orchestrator.runner import extract_escalation_info

        output = """
        QUESTION: Which caching strategy should I use?
        OPTIONS:
        A) Redis
        B) Memcached
        RECOMMENDATION: A because it's more flexible
        """
        info = extract_escalation_info("4.1", output)
        assert info.task_id == "4.1"
        assert "caching strategy" in info.question

    def test_extracts_structured_options(self):
        """Should extract OPTIONS: from structured format."""
        from orchestrator.runner import extract_escalation_info

        output = """
        QUESTION: Which approach?
        OPTIONS:
        A) First option
        B) Second option
        C) Third option
        """
        info = extract_escalation_info("4.1", output)
        assert info.options is not None
        assert len(info.options) == 3
        assert "First option" in info.options[0]

    def test_extracts_structured_recommendation(self):
        """Should extract RECOMMENDATION: from structured format."""
        from orchestrator.runner import extract_escalation_info

        output = """
        QUESTION: What should I do?
        RECOMMENDATION: Use approach A because it's simpler
        """
        info = extract_escalation_info("4.1", output)
        assert info.recommendation is not None
        assert "approach A" in info.recommendation

    def test_extracts_question_with_question_mark(self):
        """Should extract question ending with ? from unstructured output."""
        from orchestrator.runner import extract_escalation_info

        output = """
        I've looked at the code and there are two paths forward.
        Should I refactor the entire module or just the specific function?
        """
        info = extract_escalation_info("4.1", output)
        assert "?" in info.question
        assert "refactor" in info.question.lower()

    def test_extracts_uncertainty_statement(self):
        """Should extract 'I'm not sure' type statements."""
        from orchestrator.runner import extract_escalation_info

        output = "I'm not sure whether to use the old API or the new one."
        info = extract_escalation_info("4.1", output)
        assert "not sure" in info.question.lower() or "API" in info.question

    def test_fallback_message_when_no_question_found(self):
        """Should provide fallback message when no question found."""
        from orchestrator.runner import extract_escalation_info

        output = "STATUS: needs_human"
        info = extract_escalation_info("4.1", output)
        assert info.question is not None
        assert len(info.question) > 0
        # Fallback should mention reviewing the output
        assert (
            "review" in info.question.lower() or "uncertainty" in info.question.lower()
        )

    def test_preserves_raw_output(self):
        """Should preserve the raw output in the EscalationInfo."""
        from orchestrator.runner import extract_escalation_info

        output = "Some output with QUESTION: What should I do?"
        info = extract_escalation_info("4.1", output)
        assert info.raw_output == output

    def test_options_none_when_not_present(self):
        """Options should be None when not present."""
        from orchestrator.runner import extract_escalation_info

        output = "QUESTION: Should I proceed?"
        info = extract_escalation_info("4.1", output)
        assert info.options is None

    def test_recommendation_none_when_not_present(self):
        """Recommendation should be None when not present."""
        from orchestrator.runner import extract_escalation_info

        output = "QUESTION: Which way?"
        info = extract_escalation_info("4.1", output)
        assert info.recommendation is None


class TestParseOptions:
    """Test the _parse_options helper function."""

    def test_parses_lettered_options(self):
        """Should parse A) B) C) format."""
        from orchestrator.runner import _parse_options

        text = "A) First option B) Second option C) Third option"
        options = _parse_options(text)
        assert len(options) == 3
        assert "First option" in options[0]
        assert "Second option" in options[1]
        assert "Third option" in options[2]

    def test_parses_numbered_options_with_dot(self):
        """Should parse 1. 2. 3. format."""
        from orchestrator.runner import _parse_options

        text = "1. First option 2. Second option 3. Third option"
        options = _parse_options(text)
        assert len(options) == 3

    def test_parses_numbered_options_with_paren(self):
        """Should parse 1) 2) 3) format."""
        from orchestrator.runner import _parse_options

        text = "1) First option 2) Second option"
        options = _parse_options(text)
        assert len(options) == 2

    def test_parses_bullet_options_dash(self):
        """Should parse - bullet format."""
        from orchestrator.runner import _parse_options

        text = "- First option - Second option - Third option"
        options = _parse_options(text)
        assert len(options) == 3

    def test_parses_bullet_options_asterisk(self):
        """Should parse * bullet format."""
        from orchestrator.runner import _parse_options

        text = "* First option * Second option"
        options = _parse_options(text)
        assert len(options) == 2

    def test_returns_single_item_for_unparseable(self):
        """Should return the whole text as single option if unparseable."""
        from orchestrator.runner import _parse_options

        text = "just some plain text without structure"
        options = _parse_options(text)
        assert len(options) == 1
        assert options[0] == "just some plain text without structure"

    def test_strips_whitespace_from_options(self):
        """Should strip whitespace from parsed options."""
        from orchestrator.runner import _parse_options

        text = "A)   Option with spaces   B)  Another option  "
        options = _parse_options(text)
        assert options[0] == "Option with spaces"
        assert options[1] == "Another option"


class TestEscalationInfoDataclass:
    """Test the EscalationInfo dataclass."""

    def test_escalation_info_creation(self):
        """Should be able to create EscalationInfo with all fields."""
        from orchestrator.runner import EscalationInfo

        info = EscalationInfo(
            task_id="4.1",
            question="Which approach?",
            options=["A", "B"],
            recommendation="A",
            raw_output="full output here",
        )
        assert info.task_id == "4.1"
        assert info.question == "Which approach?"
        assert info.options == ["A", "B"]
        assert info.recommendation == "A"
        assert info.raw_output == "full output here"

    def test_escalation_info_optional_fields(self):
        """Options and recommendation should be optional."""
        from orchestrator.runner import EscalationInfo

        info = EscalationInfo(
            task_id="4.1",
            question="Simple question?",
            options=None,
            recommendation=None,
            raw_output="output",
        )
        assert info.options is None
        assert info.recommendation is None


class TestEscalateAndWait:
    """Test the escalate_and_wait function."""

    def test_returns_user_response(self):
        """Should return the user's response."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification"),
        ):
            mock_prompt.ask.return_value = "Use option A"

            # Create mock tracer
            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Which approach?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            result = asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))
            assert result == "Use option A"

    def test_skip_uses_recommendation(self):
        """When user enters 'skip', should use recommendation."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification"),
        ):
            mock_prompt.ask.return_value = "skip"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Which approach?",
                options=["A", "B"],
                recommendation="Use A because it's simpler",
                raw_output="output",
            )

            result = asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))
            assert result == "Use A because it's simpler"

    def test_sends_notification_when_notify_true(self):
        """Should send notification when notify=True."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification") as mock_notify,
        ):
            mock_prompt.ask.return_value = "response"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Which approach should I use for the caching layer?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            asyncio.run(escalate_and_wait(info, mock_tracer, notify=True))

            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            # Check title contains "Orchestrator" (positional or keyword arg)
            title = call_args.kwargs.get("title") or call_args.args[0]
            assert "Orchestrator" in title

    def test_no_notification_when_notify_false(self):
        """Should not send notification when notify=False."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification") as mock_notify,
        ):
            mock_prompt.ask.return_value = "response"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Question?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))

            mock_notify.assert_not_called()

    def test_records_wait_time_in_span(self):
        """Should record wait_seconds attribute in the trace span."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification"),
        ):
            mock_prompt.ask.return_value = "response"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Question?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))

            # Check that span attributes were set
            set_attribute_calls = mock_span.set_attribute.call_args_list
            attribute_names = [call[0][0] for call in set_attribute_calls]
            assert "escalation.wait_seconds" in attribute_names

    def test_records_task_id_in_span(self):
        """Should record task.id attribute in the trace span."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification"),
        ):
            mock_prompt.ask.return_value = "response"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Question?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))

            # Check that task.id was set
            set_attribute_calls = mock_span.set_attribute.call_args_list
            task_id_calls = [
                call for call in set_attribute_calls if call[0][0] == "task.id"
            ]
            assert len(task_id_calls) == 1
            assert task_id_calls[0][0][1] == "4.1"

    def test_creates_span_with_correct_name(self):
        """Should create a span named 'orchestrator.escalation'."""
        import asyncio
        from unittest.mock import MagicMock, patch

        from orchestrator.runner import EscalationInfo, escalate_and_wait

        with (
            patch("orchestrator.runner.Prompt") as mock_prompt,
            patch("orchestrator.runner.send_notification"),
        ):
            mock_prompt.ask.return_value = "response"

            mock_tracer = MagicMock()
            mock_span = MagicMock()
            mock_tracer.start_as_current_span.return_value.__enter__ = MagicMock(
                return_value=mock_span
            )
            mock_tracer.start_as_current_span.return_value.__exit__ = MagicMock(
                return_value=False
            )

            info = EscalationInfo(
                task_id="4.1",
                question="Question?",
                options=None,
                recommendation=None,
                raw_output="output",
            )

            asyncio.run(escalate_and_wait(info, mock_tracer, notify=False))

            mock_tracer.start_as_current_span.assert_called_once_with(
                "orchestrator.escalation"
            )


class TestHaikuBrainIntegration:
    """Test HaikuBrain-based detection integration."""

    def test_explicit_marker_skips_brain_by_default(self):
        """Explicit STATUS: needs_human should not call HaikuBrain in default mode."""
        from unittest.mock import patch

        from orchestrator.runner import configure_interpreter, detect_needs_human

        # Reset to default mode
        configure_interpreter(llm_only=False)

        with patch("orchestrator.runner.get_brain") as mock_get:
            output = "STATUS: needs_human\nI need clarification."
            result = detect_needs_human(output)

            assert result is True
            mock_get.assert_not_called()  # Fast path, no LLM

    def test_needs_human_marker_skips_brain(self):
        """NEEDS_HUMAN: marker should not call HaikuBrain in default mode."""
        from unittest.mock import patch

        from orchestrator.runner import configure_interpreter, detect_needs_human

        configure_interpreter(llm_only=False)

        with patch("orchestrator.runner.get_brain") as mock_get:
            output = "NEEDS_HUMAN: Please clarify the caching type."
            result = detect_needs_human(output)

            assert result is True
            mock_get.assert_not_called()

    def test_no_explicit_marker_calls_brain(self):
        """Output without explicit markers should use HaikuBrain interpretation."""
        from unittest.mock import MagicMock, patch

        from ktrdr.llm.haiku_brain import InterpretationResult
        from orchestrator.runner import configure_interpreter, detect_needs_human

        configure_interpreter(llm_only=False)

        mock_result = InterpretationResult(
            status="needs_help",
            summary="Needs clarification",
            error=None,
            question="Which approach?",
            options=["A", "B"],
            recommendation="A",
        )

        with patch("orchestrator.runner.get_brain") as mock_get:
            mock_brain = MagicMock()
            mock_brain.interpret_result.return_value = mock_result
            mock_get.return_value = mock_brain

            output = "Task completed. Some ambiguous text here."
            result = detect_needs_human(output)

            assert result is True
            mock_get.assert_called_once()
            mock_brain.interpret_result.assert_called_once_with(output)

    def test_brain_returns_false_for_completed_task(self):
        """HaikuBrain saying task completed should return False."""
        from unittest.mock import MagicMock, patch

        from ktrdr.llm.haiku_brain import InterpretationResult
        from orchestrator.runner import configure_interpreter, detect_needs_human

        configure_interpreter(llm_only=False)

        mock_result = InterpretationResult(
            status="completed",
            summary="Task completed successfully",
            error=None,
            question=None,
            options=None,
            recommendation=None,
        )

        with patch("orchestrator.runner.get_brain") as mock_get:
            mock_brain = MagicMock()
            mock_brain.interpret_result.return_value = mock_result
            mock_get.return_value = mock_brain

            output = "Task completed successfully. All tests pass."
            result = detect_needs_human(output)

            assert result is False

    def test_llm_only_mode_ignores_explicit_markers(self):
        """--llm-only mode should always use HaikuBrain, even with explicit markers."""
        from unittest.mock import MagicMock, patch

        from ktrdr.llm.haiku_brain import InterpretationResult
        from orchestrator.runner import configure_interpreter, detect_needs_human

        # Enable LLM-only mode
        configure_interpreter(llm_only=True)

        try:
            mock_result = InterpretationResult(
                status="needs_help",
                summary="Needs help",
                error=None,
                question="Q",
                options=None,
                recommendation=None,
            )

            with patch("orchestrator.runner.get_brain") as mock_get:
                mock_brain = MagicMock()
                mock_brain.interpret_result.return_value = mock_result
                mock_get.return_value = mock_brain

                output = "STATUS: needs_human"  # Has explicit marker
                result = detect_needs_human(output)

                # Should call HaikuBrain despite marker
                mock_get.assert_called_once()
                mock_brain.interpret_result.assert_called_once()
                assert result is True
        finally:
            # Reset to default
            configure_interpreter(llm_only=False)

    def test_llm_only_mode_skips_fast_path(self):
        """--llm-only mode should skip fast-path check entirely."""
        from unittest.mock import MagicMock, patch

        from ktrdr.llm.haiku_brain import InterpretationResult
        from orchestrator.runner import configure_interpreter, detect_needs_human

        configure_interpreter(llm_only=True)

        try:
            mock_result = InterpretationResult(
                status="completed",
                summary="Task completed",
                error=None,
                question=None,
                options=None,
                recommendation=None,
            )

            with patch("orchestrator.runner.get_brain") as mock_get:
                mock_brain = MagicMock()
                mock_brain.interpret_result.return_value = mock_result
                mock_get.return_value = mock_brain

                output = "NEEDS_HUMAN: But HaikuBrain says no."
                result = detect_needs_human(output)

                # HaikuBrain says status=completed, so return False
                assert result is False
                mock_brain.interpret_result.assert_called_once()
        finally:
            configure_interpreter(llm_only=False)

    def test_get_brain_singleton(self):
        """get_brain should return the same instance on repeated calls."""
        from orchestrator.runner import get_brain

        brain1 = get_brain()
        brain2 = get_brain()
        assert brain1 is brain2

    def test_configure_interpreter_resets_state(self):
        """configure_interpreter should set the llm_only flag."""
        from orchestrator.runner import configure_interpreter

        # Just verify no exception
        configure_interpreter(llm_only=True)
        configure_interpreter(llm_only=False)
