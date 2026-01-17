"""Tests for enhanced error messages with operation-specific context."""

import pytest

from ktrdr.cli.output import print_error
from ktrdr.cli.state import CLIState
from ktrdr.errors.exceptions import (
    ConfigurationError,
    KtrdrError,
    ValidationError,
)


class TestEnhancedErrorMessages:
    """Test suite for enhanced error messages with operation context."""

    @pytest.fixture
    def cli_state_human(self):
        """CLI state for human-readable output."""
        return CLIState(
            json_mode=False,
            verbose=False,
            api_url="http://localhost:8000/api/v1",
        )

    @pytest.fixture
    def cli_state_json(self):
        """CLI state for JSON output."""
        return CLIState(
            json_mode=True,
            verbose=False,
            api_url="http://localhost:8000/api/v1",
        )

    def test_basic_error_without_context(self, cli_state_human, capsys):
        """Test basic error message without operation context."""
        error = KtrdrError(message="Basic error occurred")

        print_error("Basic error occurred", cli_state_human, error)

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Basic error occurred" in captured.err

    def test_error_with_operation_context(self, cli_state_human, capsys):
        """Test error message with operation type and ID."""
        error = KtrdrError(
            message="Operation failed",
            operation_type="training",
            operation_id="op_abc123",
        )

        print_error("Operation failed", cli_state_human, error)

        captured = capsys.readouterr()
        assert "Operation: training (op_abc123)" in captured.err
        assert "Operation failed" in captured.err

    def test_error_with_stage_context(self, cli_state_human, capsys):
        """Test error message with operation stage."""
        error = KtrdrError(
            message="Validation failed",
            operation_type="training",
            stage="validation",
        )

        print_error("Validation failed", cli_state_human, error)

        captured = capsys.readouterr()
        assert "Operation: training" in captured.err
        assert "Stage: validation" in captured.err
        assert "Validation failed" in captured.err

    def test_error_with_suggestion(self, cli_state_human, capsys):
        """Test error message with actionable suggestion."""
        error = KtrdrError(
            message="Invalid configuration",
            operation_type="training",
            suggestion="Check strategy.yaml for required fields",
        )

        print_error("Invalid configuration", cli_state_human, error)

        captured = capsys.readouterr()
        assert "Invalid configuration" in captured.err
        assert "💡 Suggestion:" in captured.err
        assert "Check strategy.yaml" in captured.err

    def test_error_json_output_with_context(self, cli_state_json, capsys):
        """Test JSON error output includes operation context."""
        import json

        error = KtrdrError(
            message="Operation failed",
            operation_type="training",
            operation_id="op_abc123",
            stage="execution",
            error_code="TRAIN-001",
            suggestion="Check logs",
        )

        print_error("Operation failed", cli_state_json, error)

        captured = capsys.readouterr()
        output = json.loads(captured.out)

        assert output["status"] == "error"
        assert output["message"] == "Operation failed"
        assert output["operation_type"] == "training"
        assert output["operation_id"] == "op_abc123"
        assert output["stage"] == "execution"
        assert output["error_code"] == "TRAIN-001"
        assert output["suggestion"] == "Check logs"

    def test_validation_error_with_details(self, cli_state_human, capsys):
        """Test validation error with detailed context."""
        error = ValidationError(
            message="Invalid timeframe '5x'",
            error_code="VALIDATION-InvalidTimeframe",
            details={
                "provided": "5x",
                "valid_options": ["1m", "5m", "15m", "1h", "1d"],
            },
            suggestion="Use one of the valid timeframes: 1m, 5m, 15m, 1h, 1d",
        )

        # handle_cli_error doesn't raise SystemExit, it just prints and returns
        # The caller is responsible for exiting
        from ktrdr.cli.error_handler import handle_cli_error

        handle_cli_error(error, verbose=False, quiet=False)

        captured = capsys.readouterr()
        assert "Validation error:" in captured.err
        assert "Invalid timeframe" in captured.err
        assert "Details:" in captured.err
        assert "💡 Suggestion:" in captured.err

    def test_configuration_error_inheritance(self):
        """Test ConfigurationError properly inherits operation context."""
        error = ConfigurationError(
            message="Strategy validation failed",
            error_code="STRATEGY-ValidationFailed",
            operation_type="training",
            operation_id="op_xyz789",
            stage="validation",
            suggestion="Fix configuration errors",
        )

        assert error.operation_type == "training"
        assert error.operation_id == "op_xyz789"
        assert error.stage == "validation"
        assert error.suggestion == "Fix configuration errors"

    def test_error_without_exception_object(self, cli_state_human, capsys):
        """Test error message when no exception object is provided."""
        print_error("Simple error message", cli_state_human, None)

        captured = capsys.readouterr()
        assert "Error:" in captured.err
        assert "Simple error message" in captured.err
        # Should not crash or show context fields

    def test_error_with_only_operation_type(self, cli_state_human, capsys):
        """Test error message with only operation type (no ID)."""
        error = KtrdrError(
            message="Operation initialization failed",
            operation_type="backtest",
        )

        print_error("Operation initialization failed", cli_state_human, error)

        captured = capsys.readouterr()
        assert "Operation: backtest" in captured.err
        # Should not show operation_id
        assert "(" not in captured.err or "None" not in captured.err
