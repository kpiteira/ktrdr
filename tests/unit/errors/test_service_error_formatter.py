"""
Tests for service error message formatter that creates actionable error messages.

This module tests the ServiceErrorFormatter that converts technical service
exceptions into user-friendly, actionable error messages with troubleshooting steps.
"""

from unittest.mock import patch

from ktrdr.errors.exceptions import (
    ServiceConfigurationError,
    ServiceConnectionError,
    ServiceTimeoutError,
)

# Import the service error formatter that we'll implement
from ktrdr.errors.service_error_formatter import ServiceErrorFormatter


class TestServiceErrorFormatter:
    """Tests for the ServiceErrorFormatter class."""

    def test_format_ib_service_connection_error(self):
        """Test formatting of IB Host Service connection errors with troubleshooting."""
        # Create basic connection error
        error = ServiceConnectionError(
            message="Connection refused",
            error_code="CONNECTION_REFUSED",
            details={"service": "ib-host", "endpoint": "http://localhost:5001"},
        )

        # Format with enhanced messaging
        formatted = ServiceErrorFormatter.format_service_error(error)

        # Verify enhanced message includes actionable guidance
        assert "IB Host Service unavailable" in formatted
        assert "./ib-host-service/start.sh" in formatted
        assert "Check if service is running:" in formatted
        assert "tail -f ib-host-service/logs/ib-host-service.log" in formatted
        assert "Verify port 5001 is not blocked" in formatted

    def test_format_training_service_connection_error(self):
        """Test formatting of generic service connection errors."""
        error = ServiceConnectionError(
            message="Connection timed out",
            error_code="CONNECTION_TIMEOUT",
            details={"service": "training-host", "endpoint": "http://localhost:8002"},
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Generic service error formatting (no special Training Host Service)
        assert (
            "Service training-host is unavailable" in formatted
            or "unavailable" in formatted
        )
        assert "service status" in formatted.lower() or "check" in formatted.lower()

    def test_format_configuration_error_invalid_value(self):
        """Test formatting configuration errors with valid options shown."""
        error = ServiceConfigurationError(
            message="Invalid configuration",
            error_code="INVALID_CONFIG",
            details={
                "service": "ib-host",
                "config_key": "USE_IB_HOST_SERVICE",
                "current_value": "invalid_value",
            },
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should show valid options and current value
        assert (
            "Invalid configuration: USE_IB_HOST_SERVICE must be 'true' or 'false'"
            in formatted
        )
        assert "got 'invalid_value'" in formatted

    def test_format_configuration_error_missing_url(self):
        """Test formatting missing URL configuration errors (generic service)."""
        error = ServiceConfigurationError(
            message="Missing URL",
            error_code="MISSING_URL",
            details={
                "service": "training-host",
                "config_key": "TRAINING_HOST_SERVICE_URL",
                "current_value": None,
            },
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Generic configuration error (no special Training Host Service handling)
        assert (
            "Invalid configuration" in formatted or "configuration" in formatted.lower()
        )
        assert "TRAINING_HOST_SERVICE_URL" in formatted

    def test_format_network_timeout_error(self):
        """Test formatting network timeout errors with debugging steps."""
        error = ServiceTimeoutError(
            message="Request timed out after 30 seconds",
            error_code="NETWORK_TIMEOUT",
            details={
                "service": "ib-host",
                "timeout_seconds": 30,
                "endpoint": "http://localhost:5001",
            },
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        assert "IB Host Service request timed out" in formatted
        assert "Check if service is overloaded" in formatted
        assert "Increase timeout" in formatted
        assert "30 seconds" in formatted

    def test_format_unknown_service_error(self):
        """Test formatting errors for unknown/generic services."""
        error = ServiceConnectionError(
            message="Unknown service error",
            error_code="UNKNOWN_ERROR",
            details={"service": "unknown-service", "endpoint": "http://localhost:9999"},
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should provide generic but still helpful guidance
        assert "Service unknown-service is unavailable" in formatted
        assert "http://localhost:9999" in formatted
        assert "Check service status" in formatted

    def test_format_preserves_original_error_context(self):
        """Test that formatting preserves original error details for debugging."""
        error = ServiceConnectionError(
            message="Specific technical error",
            error_code="TECH_ERROR",
            details={
                "service": "ib-host",
                "original_exception": "ConnectionRefusedError: [Errno 111]",
            },
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should include both user-friendly and technical details
        assert "IB Host Service unavailable" in formatted  # User-friendly
        assert "Technical details:" in formatted  # Technical context preserved
        assert "ConnectionRefusedError: [Errno 111]" in formatted

    def test_format_handles_missing_service_details(self):
        """Test formatting when service details are missing or incomplete."""
        error = ServiceConnectionError(
            message="Generic connection error",
            error_code="GENERIC_ERROR",
            details={},  # No service details
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should provide fallback guidance when service details missing
        assert "Service connection failed" in formatted
        assert "Check service configuration" in formatted

    def test_format_multiple_troubleshooting_steps(self):
        """Test that formatted errors include multiple troubleshooting approaches."""
        error = ServiceConnectionError(
            message="Connection failed",
            error_code="CONNECTION_FAILED",
            details={"service": "ib-host", "endpoint": "http://localhost:5001"},
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should include multiple numbered troubleshooting steps
        assert "1." in formatted and "2." in formatted  # Multiple numbered steps
        assert "./ib-host-service/start.sh" in formatted  # Start service
        assert "tail -f" in formatted  # Check logs
        assert "port 5001" in formatted  # Check port

    def test_format_includes_environment_variable_examples(self):
        """Test that configuration errors include example environment variable commands."""
        error = ServiceConfigurationError(
            message="Invalid environment variable",
            error_code="INVALID_ENV_VAR",
            details={
                "service": "ib-host",
                "config_key": "USE_IB_HOST_SERVICE",
                "current_value": "maybe",
            },
        )

        formatted = ServiceErrorFormatter.format_service_error(error)

        # Should include example export commands
        assert "export USE_IB_HOST_SERVICE=true" in formatted
        assert "export USE_IB_HOST_SERVICE=false" in formatted


class TestServiceErrorFormatterIntegration:
    """Integration tests for service error formatting with CLI context."""

    def test_cli_data_command_error_formatting(self):
        """Test error formatting in the context of CLI data commands."""
        # Simulate error that would occur during 'ktrdr data show AAPL' command
        original_error = ServiceConnectionError(
            message="Host service request failed",
            error_code="SERVICE_REQUEST_FAILED",
            details={"service": "ib-host", "operation": "data_load", "symbol": "AAPL"},
        )

        # Format with CLI context
        formatted = ServiceErrorFormatter.format_service_error(
            original_error, operation_context="Data loading failed"
        )

        # Should replace cryptic message with helpful guidance
        assert "Data loading failed" in formatted
        assert "AAPL" in formatted  # Include context from operation
        assert "./ib-host-service/start.sh" in formatted  # Actionable steps
        # Should NOT contain cryptic original message
        assert "Host service request failed" not in formatted

    def test_cli_training_command_error_formatting(self):
        """Test error formatting for training commands (generic service)."""
        original_error = ServiceTimeoutError(
            message="Service timeout",
            error_code="SERVICE_TIMEOUT",
            details={"service": "training-host", "operation": "model_train"},
        )

        formatted = ServiceErrorFormatter.format_service_error(
            original_error, operation_context="Model training failed"
        )

        assert "Model training failed" in formatted
        # Generic service timeout message (no special Training Host Service)
        assert "training-host" in formatted.lower() or "service" in formatted.lower()
        assert "timed out" in formatted.lower() or "timeout" in formatted.lower()

    def test_configuration_validation_on_startup(self):
        """Test configuration validation provides helpful startup guidance."""
        # Test the static method that validates configuration on startup
        with patch.dict("os.environ", {"USE_IB_HOST_SERVICE": "invalid"}):
            validation_errors = ServiceErrorFormatter.validate_service_configuration()

            assert len(validation_errors) > 0
            error_msg = validation_errors[0]
            assert "USE_IB_HOST_SERVICE must be 'true' or 'false'" in error_msg
            assert "got 'invalid'" in error_msg

    def test_configuration_validation_missing_url(self):
        """Test configuration validation for missing service URLs."""
        with patch.dict("os.environ", {"USE_IB_HOST_SERVICE": "true"}, clear=True):
            # USE_IB_HOST_SERVICE=true but no IB_HOST_SERVICE_URL
            validation_errors = ServiceErrorFormatter.validate_service_configuration()

            assert len(validation_errors) > 0
            error_msg = validation_errors[0]
            assert "IB_HOST_SERVICE_URL is required" in error_msg
            assert "export IB_HOST_SERVICE_URL=" in error_msg

    def test_configuration_validation_all_valid(self):
        """Test that valid configuration returns no errors."""
        with patch.dict(
            "os.environ",
            {
                "USE_IB_HOST_SERVICE": "true",
                "IB_HOST_SERVICE_URL": "http://localhost:5001",
                "USE_TRAINING_HOST_SERVICE": "false",
            },
        ):
            validation_errors = ServiceErrorFormatter.validate_service_configuration()

            assert len(validation_errors) == 0


class TestServiceErrorFormatterEdgeCases:
    """Test edge cases and error conditions."""

    def test_format_non_service_error(self):
        """Test formatting non-service errors (should pass through unchanged)."""
        from ktrdr.errors.exceptions import DataError

        regular_error = DataError("Regular data error")

        # Should return original error for non-service errors
        formatted = ServiceErrorFormatter.format_service_error(regular_error)
        assert formatted == str(regular_error)

    def test_format_with_none_error(self):
        """Test formatting with None input."""
        formatted = ServiceErrorFormatter.format_service_error(None)
        assert "Unknown service error occurred" in formatted

    def test_format_with_malformed_details(self):
        """Test formatting with malformed or unexpected details structure."""
        error = ServiceConnectionError(
            message="Connection failed",
            error_code="CONNECTION_FAILED",
            details={"unexpected_key": "unexpected_value"},  # Missing expected keys
        )

        # Should handle gracefully and provide fallback guidance
        formatted = ServiceErrorFormatter.format_service_error(error)
        assert "Service connection failed" in formatted
        assert "Check service configuration" in formatted
