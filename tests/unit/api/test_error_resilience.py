"""Tests for API error handling resilience (Issue #276).

Verifies that:
1. StrategyValidationError is caught and returns 422 (not 500)
2. Error responses include retryable field
3. Proper status codes for different error types
"""

from unittest.mock import AsyncMock, patch

import pytest

from ktrdr.api.services.agent_service import AgentService
from ktrdr.config.strategy_validator import StrategyValidationError


class TestStrategyValidationErrorHandling:
    """Tests for StrategyValidationError being properly caught."""

    @pytest.fixture
    def mock_ops_service(self):
        """Create mock operations service."""
        service = AsyncMock()
        return service

    @pytest.fixture
    def agent_service(self, mock_ops_service):
        """Create AgentService with mocked dependencies."""
        service = AgentService(operations_service=mock_ops_service)
        return service

    def test_strategy_validation_error_converts_to_value_error(self, agent_service):
        """StrategyValidationError should be caught and converted to ValueError.

        This ensures the endpoint returns 422 instead of 500.
        """
        strategy_name = "invalid_strategy"

        # Mock the modules imported inside _validate_and_resolve_strategy
        with patch(
            "ktrdr.api.services.training.context._resolve_strategy_path"
        ) as mock_resolve:
            mock_resolve.return_value = "/path/to/strategy.yaml"

            # Mock strategy_loader at source
            with patch("ktrdr.config.strategy_loader.strategy_loader") as mock_loader:
                mock_loader.load_v3_strategy.side_effect = StrategyValidationError(
                    "Strategy validation failed:\n  - fuzzy_sets.test.indicator: Invalid output"
                )

                # Should raise ValueError (which endpoint catches for 422)
                with pytest.raises(ValueError) as exc_info:
                    agent_service._validate_and_resolve_strategy(strategy_name)

                # Error message should mention validation failure
                assert "validation" in str(exc_info.value).lower()

    def test_value_error_still_caught(self, agent_service):
        """Regular ValueError from load_v3_strategy should still work."""
        strategy_name = "not_v3_strategy"

        with patch(
            "ktrdr.api.services.training.context._resolve_strategy_path"
        ) as mock_resolve:
            mock_resolve.return_value = "/path/to/strategy.yaml"

            with patch("ktrdr.config.strategy_loader.strategy_loader") as mock_loader:
                mock_loader.load_v3_strategy.side_effect = ValueError(
                    "Strategy is not v3 format"
                )

                with pytest.raises(ValueError) as exc_info:
                    agent_service._validate_and_resolve_strategy(strategy_name)

                assert "v3 format" in str(exc_info.value).lower()

    def test_file_not_found_error_still_caught(self, agent_service):
        """FileNotFoundError from load_v3_strategy should still work."""
        strategy_name = "missing_strategy"

        with patch(
            "ktrdr.api.services.training.context._resolve_strategy_path"
        ) as mock_resolve:
            mock_resolve.return_value = "/path/to/missing.yaml"

            with patch("ktrdr.config.strategy_loader.strategy_loader") as mock_loader:
                mock_loader.load_v3_strategy.side_effect = FileNotFoundError(
                    "Strategy file not found"
                )

                with pytest.raises(ValueError) as exc_info:
                    agent_service._validate_and_resolve_strategy(strategy_name)

                assert "not found" in str(exc_info.value).lower()


class TestAPIErrorRetryable:
    """Tests for APIError retryable field."""

    def test_api_error_has_retryable_attribute(self):
        """APIError should have retryable attribute."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(
            message="Test error", status_code=422, details={"retryable": False}
        )

        # The error should expose retryable status
        assert hasattr(error, "retryable") or "retryable" in error.details

    def test_api_error_422_not_retryable(self):
        """422 errors should be marked as not retryable."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(message="Validation failed", status_code=422, details={})

        # 422 should not be retryable
        assert error.retryable is False

    def test_api_error_500_potentially_retryable(self):
        """500 errors should be potentially retryable (server may recover)."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(message="Internal server error", status_code=500, details={})

        # 500 should be retryable by default (transient errors)
        assert error.retryable is True

    def test_api_error_503_retryable(self):
        """503 errors should be retryable."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(message="Service unavailable", status_code=503, details={})

        assert error.retryable is True

    def test_api_error_explicit_retryable_override(self):
        """Explicit retryable field in details should override default."""
        from ktrdr.cli.client.errors import APIError

        # 500 with explicit retryable=False (e.g., unrecoverable bug)
        error = APIError(
            message="Bug in code", status_code=500, details={"retryable": False}
        )

        assert error.retryable is False


class TestCLIRetryLogic:
    """Tests for CLI client retry logic respecting retryable field."""

    def test_should_retry_respects_retryable_false(self):
        """should_retry should return False when retryable is False."""
        from ktrdr.cli.client.core import should_retry

        # Even on 500, should not retry if marked non-retryable
        result = should_retry(
            status_code=500, attempt=0, max_retries=3, retryable=False
        )

        assert result is False

    def test_should_retry_defaults_to_status_code_based(self):
        """Without explicit retryable, should use status code logic."""
        from ktrdr.cli.client.core import should_retry

        # 500 with retryable=None should retry based on status code
        result = should_retry(status_code=500, attempt=0, max_retries=3, retryable=None)

        assert result is True

    def test_should_retry_422_never_retries(self):
        """422 should never be retried (validation errors)."""
        from ktrdr.cli.client.core import should_retry

        result = should_retry(status_code=422, attempt=0, max_retries=3, retryable=None)

        assert result is False


class TestAPIErrorDisplay:
    """Tests for cleaner API error display."""

    def test_api_error_str_without_status_code_by_default(self):
        """APIError string should not include status code by default."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(
            message="Validation failed: invalid field", status_code=422, details={}
        )

        # String representation should be clean (no status code)
        error_str = str(error)
        assert "(422)" not in error_str
        assert "Validation failed" in error_str

    def test_api_error_verbose_includes_status_code(self):
        """APIError should have method to get verbose string with status code."""
        from ktrdr.cli.client.errors import APIError

        error = APIError(message="Validation failed", status_code=422, details={})

        # Should have way to get verbose representation
        verbose = error.verbose_str()
        assert "422" in verbose
        assert "Validation failed" in verbose
