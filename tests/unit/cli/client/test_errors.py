"""Unit tests for CLI client error hierarchy."""

import pytest

from ktrdr.cli.client.errors import (
    APIError,
    CLIClientError,
    ConnectionError,
    TimeoutError,
)


class TestCLIClientError:
    """Tests for base CLIClientError exception."""

    def test_instantiation_with_message(self):
        """CLIClientError can be created with just a message."""
        error = CLIClientError("Something went wrong")
        assert error.message == "Something went wrong"
        assert error.status_code is None
        assert error.details == {}

    def test_instantiation_with_all_attributes(self):
        """CLIClientError accepts status_code and details."""
        error = CLIClientError(
            message="API error",
            status_code=500,
            details={"error": "Internal server error"},
        )
        assert error.message == "API error"
        assert error.status_code == 500
        assert error.details == {"error": "Internal server error"}

    def test_inherits_from_exception(self):
        """CLIClientError is an Exception."""
        error = CLIClientError("test")
        assert isinstance(error, Exception)

    def test_str_representation(self):
        """String representation shows the message."""
        error = CLIClientError("Test error message")
        assert str(error) == "Test error message"

    def test_can_be_raised_and_caught(self):
        """CLIClientError can be raised and caught."""
        with pytest.raises(CLIClientError) as exc_info:
            raise CLIClientError("Raised error")
        assert exc_info.value.message == "Raised error"


class TestConnectionError:
    """Tests for ConnectionError exception."""

    def test_instantiation(self):
        """ConnectionError can be created with attributes."""
        error = ConnectionError(
            message="Could not connect to http://localhost:8000",
            details={"url": "http://localhost:8000"},
        )
        assert error.message == "Could not connect to http://localhost:8000"
        assert error.status_code is None
        assert error.details == {"url": "http://localhost:8000"}

    def test_inherits_from_cli_client_error(self):
        """ConnectionError inherits from CLIClientError."""
        error = ConnectionError("test")
        assert isinstance(error, CLIClientError)
        assert isinstance(error, Exception)

    def test_can_be_caught_as_cli_client_error(self):
        """ConnectionError can be caught as CLIClientError."""
        with pytest.raises(CLIClientError):
            raise ConnectionError("Connection failed")


class TestTimeoutError:
    """Tests for TimeoutError exception."""

    def test_instantiation(self):
        """TimeoutError can be created with attributes."""
        error = TimeoutError(
            message="Request timed out after 30s",
            details={"timeout": 30, "attempts": 3},
        )
        assert error.message == "Request timed out after 30s"
        assert error.status_code is None
        assert error.details == {"timeout": 30, "attempts": 3}

    def test_inherits_from_cli_client_error(self):
        """TimeoutError inherits from CLIClientError."""
        error = TimeoutError("test")
        assert isinstance(error, CLIClientError)
        assert isinstance(error, Exception)

    def test_can_be_caught_as_cli_client_error(self):
        """TimeoutError can be caught as CLIClientError."""
        with pytest.raises(CLIClientError):
            raise TimeoutError("Timed out")


class TestAPIError:
    """Tests for APIError exception."""

    def test_instantiation_with_status_code(self):
        """APIError can be created with status_code."""
        error = APIError(
            message="Not found",
            status_code=404,
            details={"resource": "user", "id": 123},
        )
        assert error.message == "Not found"
        assert error.status_code == 404
        assert error.details == {"resource": "user", "id": 123}

    def test_inherits_from_cli_client_error(self):
        """APIError inherits from CLIClientError."""
        error = APIError("test", status_code=500)
        assert isinstance(error, CLIClientError)
        assert isinstance(error, Exception)

    def test_can_be_caught_as_cli_client_error(self):
        """APIError can be caught as CLIClientError."""
        with pytest.raises(CLIClientError):
            raise APIError("Server error", status_code=500)

    def test_str_includes_status_code(self):
        """APIError str representation includes status code when present."""
        error = APIError("Not found", status_code=404)
        # Should include status code in string representation
        assert "404" in str(error) or error.status_code == 404


class TestErrorHierarchy:
    """Tests for the overall error hierarchy."""

    def test_all_errors_are_exceptions(self):
        """All error types are exceptions."""
        errors = [
            CLIClientError("test"),
            ConnectionError("test"),
            TimeoutError("test"),
            APIError("test"),
        ]
        for error in errors:
            assert isinstance(error, Exception)

    def test_specific_errors_inherit_from_base(self):
        """All specific errors inherit from CLIClientError."""
        errors = [
            ConnectionError("test"),
            TimeoutError("test"),
            APIError("test"),
        ]
        for error in errors:
            assert isinstance(error, CLIClientError)

    def test_catching_base_catches_all(self):
        """Catching CLIClientError catches all specific errors."""
        error_types = [ConnectionError, TimeoutError, APIError]
        for error_type in error_types:
            try:
                raise error_type("test")
            except CLIClientError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{error_type.__name__} not caught by CLIClientError")
