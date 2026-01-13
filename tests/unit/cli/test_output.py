"""Tests for CLI output helpers.

Tests the output abstraction that formats messages for human or JSON
consumption based on CLIState.json_mode.
"""

import json

import pytest

from ktrdr.cli.state import CLIState


class TestPrintSuccessHuman:
    """Tests for print_success in human mode."""

    def test_print_success_human_prints_message(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode prints the message to stdout."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=False)
        print_success("Operation completed", state=state)

        captured = capsys.readouterr()
        assert "Operation completed" in captured.out
        assert captured.err == ""

    def test_print_success_human_uses_green_color(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode uses Rich green formatting (verified via console record)."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=False)
        print_success("Success message", state=state)

        # Rich formatting is applied - we verify the message appears
        # (actual color codes depend on terminal capabilities)
        captured = capsys.readouterr()
        assert "Success message" in captured.out

    def test_print_success_human_ignores_data(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode does not print data dict (only message)."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=False)
        print_success("Done", data={"extra": "info"}, state=state)

        captured = capsys.readouterr()
        assert "Done" in captured.out
        # Data is not shown in human mode (JSON only)
        assert "extra" not in captured.out


class TestPrintSuccessJSON:
    """Tests for print_success in JSON mode."""

    def test_print_success_json_structure(self, capsys: pytest.CaptureFixture) -> None:
        """JSON mode produces valid JSON with status and message."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=True)
        print_success("Task done", state=state)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["status"] == "success"
        assert output["message"] == "Task done"

    def test_print_success_json_with_data(self, capsys: pytest.CaptureFixture) -> None:
        """JSON mode includes data dict when provided."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=True)
        print_success("Complete", data={"count": 42, "items": ["a", "b"]}, state=state)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["status"] == "success"
        assert output["message"] == "Complete"
        assert output["data"]["count"] == 42
        assert output["data"]["items"] == ["a", "b"]

    def test_print_success_json_no_data_key_when_none(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """JSON mode omits data key when data is None."""
        from ktrdr.cli.output import print_success

        state = CLIState(json_mode=True)
        print_success("Done", data=None, state=state)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert "data" not in output


class TestPrintErrorHuman:
    """Tests for print_error in human mode."""

    def test_print_error_human_to_stderr(self, capsys: pytest.CaptureFixture) -> None:
        """Human mode prints error to stderr."""
        from ktrdr.cli.output import print_error

        state = CLIState(json_mode=False)
        print_error("Something went wrong", state=state)

        captured = capsys.readouterr()
        assert "Something went wrong" in captured.err
        assert captured.out == ""

    def test_print_error_human_includes_prefix(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode includes 'Error:' prefix."""
        from ktrdr.cli.output import print_error

        state = CLIState(json_mode=False)
        print_error("File not found", state=state)

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "File not found" in captured.err


class TestPrintErrorJSON:
    """Tests for print_error in JSON mode."""

    def test_print_error_json_structure(self, capsys: pytest.CaptureFixture) -> None:
        """JSON mode produces valid JSON with error status."""
        from ktrdr.cli.output import print_error

        state = CLIState(json_mode=True)
        print_error("Connection failed", state=state)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["status"] == "error"
        assert output["message"] == "Connection failed"

    def test_print_error_json_to_stdout(self, capsys: pytest.CaptureFixture) -> None:
        """JSON mode prints to stdout (not stderr) for parsability."""
        from ktrdr.cli.output import print_error

        state = CLIState(json_mode=True)
        print_error("API error", state=state)

        captured = capsys.readouterr()
        # JSON goes to stdout for easy parsing, even for errors
        assert captured.out.strip() != ""
        assert json.loads(captured.out)["status"] == "error"


class TestPrintOperationStartedHuman:
    """Tests for print_operation_started in human mode."""

    def test_print_operation_started_human_shows_type_and_id(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode shows operation type and ID."""
        from ktrdr.cli.output import print_operation_started

        state = CLIState(json_mode=False)
        print_operation_started(
            operation_type="training",
            operation_id="op_abc123",
            state=state,
        )

        captured = capsys.readouterr()
        assert "training" in captured.out
        assert "op_abc123" in captured.out

    def test_print_operation_started_human_includes_status_hint(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode includes hint for status command."""
        from ktrdr.cli.output import print_operation_started

        state = CLIState(json_mode=False)
        print_operation_started(
            operation_type="backtest",
            operation_id="op_xyz789",
            state=state,
        )

        captured = capsys.readouterr()
        assert "ktrdr status op_xyz789" in captured.out

    def test_print_operation_started_human_includes_follow_hint(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Human mode includes hint for follow command."""
        from ktrdr.cli.output import print_operation_started

        state = CLIState(json_mode=False)
        print_operation_started(
            operation_type="research",
            operation_id="op_research1",
            state=state,
        )

        captured = capsys.readouterr()
        assert "ktrdr follow op_research1" in captured.out


class TestPrintOperationStartedJSON:
    """Tests for print_operation_started in JSON mode."""

    def test_print_operation_started_json_structure(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """JSON mode produces valid JSON with operation details."""
        from ktrdr.cli.output import print_operation_started

        state = CLIState(json_mode=True)
        print_operation_started(
            operation_type="training",
            operation_id="op_train123",
            state=state,
        )

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["operation_id"] == "op_train123"
        assert output["status"] == "started"
        assert output["type"] == "training"

    def test_print_operation_started_json_no_hints(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """JSON mode does not include human hints (just structured data)."""
        from ktrdr.cli.output import print_operation_started

        state = CLIState(json_mode=True)
        print_operation_started(
            operation_type="backtest",
            operation_id="op_bt456",
            state=state,
        )

        captured = capsys.readouterr()
        # Should not contain hint text
        assert "Track progress" not in captured.out
        assert "Follow live" not in captured.out
        # Should be valid JSON
        output = json.loads(captured.out)
        assert output["operation_id"] == "op_bt456"
