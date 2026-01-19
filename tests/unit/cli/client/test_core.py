"""Unit tests for CLI client core module."""

from unittest.mock import MagicMock, patch

import pytest

from ktrdr.cli.client.core import (
    ClientConfig,
    calculate_backoff,
    enhance_with_ib_diagnostics,
    parse_response,
    resolve_url,
    should_retry,
)
from ktrdr.cli.client.errors import APIError


class TestClientConfig:
    """Tests for ClientConfig dataclass."""

    def test_default_values(self):
        """ClientConfig has sensible defaults."""
        config = ClientConfig(base_url="http://localhost:8000/api/v1")
        assert config.base_url == "http://localhost:8000/api/v1"
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.retry_delay == 1.0

    def test_custom_values(self):
        """ClientConfig accepts custom values."""
        config = ClientConfig(
            base_url="http://custom:9000/api/v1",
            timeout=60.0,
            max_retries=5,
            retry_delay=2.0,
        )
        assert config.base_url == "http://custom:9000/api/v1"
        assert config.timeout == 60.0
        assert config.max_retries == 5
        assert config.retry_delay == 2.0

    def test_is_frozen(self):
        """ClientConfig is immutable."""
        config = ClientConfig(base_url="http://localhost:8000/api/v1")
        with pytest.raises(AttributeError):
            config.timeout = 60.0  # type: ignore[misc]


class TestResolveUrl:
    """Tests for resolve_url function."""

    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_explicit_url_takes_priority(self, mock_base, mock_override):
        """Explicit URL parameter has highest priority."""
        mock_override.return_value = "http://override:8000"
        mock_base.return_value = "http://default:8000/api/v1"

        result = resolve_url("http://explicit:9000/api/v1")
        assert result == "http://explicit:9000/api/v1"

    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_url_flag_override_second_priority(self, mock_base, mock_override):
        """--url flag override has second priority."""
        mock_override.return_value = "http://override:8000"
        mock_base.return_value = "http://default:8000/api/v1"

        result = resolve_url(None)
        # Should auto-append /api/v1 since override doesn't have it
        assert result == "http://override:8000/api/v1"

    @patch("ktrdr.cli.sandbox_detect.find_env_sandbox")
    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_config_default_fallback(self, mock_base, mock_override, mock_find_sandbox):
        """Config default is used when no override and no sandbox."""
        mock_override.return_value = None
        mock_base.return_value = "http://default:8000/api/v1"
        mock_find_sandbox.return_value = None  # No sandbox detected

        result = resolve_url(None)
        assert result == "http://default:8000/api/v1"

    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_auto_appends_api_path_to_override(self, mock_base, mock_override):
        """Auto-appends /api/v1 to override URL without api path."""
        mock_override.return_value = "http://override:8000"
        mock_base.return_value = "http://default:8000/api/v1"

        result = resolve_url(None)
        assert result == "http://override:8000/api/v1"

    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_does_not_append_if_api_path_exists(self, mock_base, mock_override):
        """Does not append /api/v1 if override already has api path."""
        mock_override.return_value = "http://override:8000/api/v2"
        mock_base.return_value = "http://default:8000/api/v1"

        result = resolve_url(None)
        assert result == "http://override:8000/api/v2"

    @patch("ktrdr.cli.sandbox_detect.find_env_sandbox")
    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_strips_trailing_slash(self, mock_base, mock_override, mock_find_sandbox):
        """Trailing slashes are stripped."""
        mock_override.return_value = None
        mock_base.return_value = "http://default:8000/api/v1/"
        mock_find_sandbox.return_value = None  # No sandbox detected

        result = resolve_url(None)
        assert result == "http://default:8000/api/v1"

    def test_sandbox_detection_fallback_when_override_is_none(self, tmp_path):
        """Uses sandbox detection when CLI override returns None.

        This tests the fix for issue #252: M2 commands (research, train, etc.)
        don't set the legacy _cli_state, so get_api_url_override() returns None.
        In this case, resolve_url() should fall back to sandbox detection before
        using the config default.

        Priority order:
        1. explicit_url parameter
        2. get_api_url_override() (--url flag / legacy state)
        3. sandbox detection from .env.sandbox  <-- This test
        4. get_api_base_url() config default
        """
        # Create a sandbox .env file with a custom port
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8001\n")

        # Mock get_api_url_override to return None (simulating M2 commands)
        # Mock sandbox_detect.resolve_api_url to use our temp directory
        with (
            patch("ktrdr.cli.client.core.get_api_url_override") as mock_override,
            patch("ktrdr.cli.sandbox_detect.find_env_sandbox") as mock_find_sandbox,
        ):
            mock_override.return_value = None
            mock_find_sandbox.return_value = env_file

            result = resolve_url(None)

            # Should use sandbox-detected URL, not config default
            assert result == "http://localhost:8001/api/v1"

    @patch("ktrdr.cli.sandbox_detect.find_env_sandbox")
    @patch("ktrdr.cli.client.core.get_api_url_override")
    @patch("ktrdr.cli.client.core.get_api_base_url")
    def test_sandbox_detection_skipped_when_no_sandbox_file(
        self, mock_base, mock_override, mock_find_sandbox
    ):
        """Falls back to config default when no .env.sandbox exists.

        Ensures sandbox detection doesn't break when not in a sandbox directory.
        """
        mock_override.return_value = None
        mock_base.return_value = "http://localhost:8000/api/v1"
        mock_find_sandbox.return_value = None  # No sandbox detected

        result = resolve_url(None)

        # Should fall back to config default
        assert result == "http://localhost:8000/api/v1"


class TestShouldRetry:
    """Tests for should_retry function."""

    def test_retry_on_500(self):
        """Should retry on 500 Internal Server Error."""
        assert should_retry(500, attempt=0, max_retries=3) is True

    def test_retry_on_502(self):
        """Should retry on 502 Bad Gateway."""
        assert should_retry(502, attempt=0, max_retries=3) is True

    def test_retry_on_503(self):
        """Should retry on 503 Service Unavailable."""
        assert should_retry(503, attempt=0, max_retries=3) is True

    def test_retry_on_504(self):
        """Should retry on 504 Gateway Timeout."""
        assert should_retry(504, attempt=0, max_retries=3) is True

    def test_no_retry_on_400(self):
        """Should not retry on 400 Bad Request."""
        assert should_retry(400, attempt=0, max_retries=3) is False

    def test_no_retry_on_401(self):
        """Should not retry on 401 Unauthorized."""
        assert should_retry(401, attempt=0, max_retries=3) is False

    def test_no_retry_on_404(self):
        """Should not retry on 404 Not Found."""
        assert should_retry(404, attempt=0, max_retries=3) is False

    def test_no_retry_on_200(self):
        """Should not retry on 200 OK (success)."""
        assert should_retry(200, attempt=0, max_retries=3) is False

    def test_no_retry_when_max_attempts_reached(self):
        """Should not retry when max attempts reached."""
        assert should_retry(500, attempt=3, max_retries=3) is False

    def test_retry_when_attempts_remaining(self):
        """Should retry when attempts remaining."""
        assert should_retry(500, attempt=2, max_retries=3) is True


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_first_attempt_backoff(self):
        """First attempt uses base delay with jitter."""
        # base_delay * (2 ** 0) + jitter = 1.0 + [0, 1)
        result = calculate_backoff(attempt=0, base_delay=1.0)
        assert 1.0 <= result < 2.0

    def test_second_attempt_backoff(self):
        """Second attempt doubles the base."""
        # base_delay * (2 ** 1) + jitter = 2.0 + [0, 1)
        result = calculate_backoff(attempt=1, base_delay=1.0)
        assert 2.0 <= result < 3.0

    def test_third_attempt_backoff(self):
        """Third attempt quadruples the base."""
        # base_delay * (2 ** 2) + jitter = 4.0 + [0, 1)
        result = calculate_backoff(attempt=2, base_delay=1.0)
        assert 4.0 <= result < 5.0

    def test_custom_base_delay(self):
        """Custom base delay is respected."""
        # 0.5 * (2 ** 0) + jitter = 0.5 + [0, 1)
        result = calculate_backoff(attempt=0, base_delay=0.5)
        assert 0.5 <= result < 1.5

    def test_backoff_has_randomness(self):
        """Backoff includes random jitter."""
        # Run multiple times and check we get different values
        results = [calculate_backoff(attempt=0, base_delay=1.0) for _ in range(10)]
        # With jitter, we should see variation
        assert len(set(results)) > 1


class TestParseResponse:
    """Tests for parse_response function."""

    def test_parse_success_response(self):
        """Parses successful JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": "value"}

        result = parse_response(mock_response)
        assert result == {"data": "value"}

    def test_parse_201_response(self):
        """Parses 201 Created response."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 123}

        result = parse_response(mock_response)
        assert result == {"id": 123}

    def test_raises_api_error_on_4xx(self):
        """Raises APIError on 4xx client error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"detail": "Not found"}

        with pytest.raises(APIError) as exc_info:
            parse_response(mock_response)

        assert exc_info.value.status_code == 404
        assert "Not found" in exc_info.value.message

    def test_raises_api_error_on_5xx(self):
        """Raises APIError on 5xx server error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"detail": "Internal server error"}

        with pytest.raises(APIError) as exc_info:
            parse_response(mock_response)

        assert exc_info.value.status_code == 500

    def test_handles_fastapi_detail_format(self):
        """Handles FastAPI's 'detail' error format."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Validation error"}

        with pytest.raises(APIError) as exc_info:
            parse_response(mock_response)

        assert "Validation error" in exc_info.value.message

    def test_handles_custom_message_format(self):
        """Handles custom 'message' error format."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"message": "Custom error"}

        with pytest.raises(APIError) as exc_info:
            parse_response(mock_response)

        assert "Custom error" in exc_info.value.message

    def test_handles_json_parse_error(self):
        """Handles response that isn't valid JSON."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Not JSON"

        with pytest.raises(APIError) as exc_info:
            parse_response(mock_response)

        assert (
            "Invalid JSON" in exc_info.value.message or "JSON" in exc_info.value.message
        )


class TestEnhanceWithIbDiagnostics:
    """Tests for enhance_with_ib_diagnostics function."""

    @patch("ktrdr.cli.client.core.should_show_ib_diagnosis")
    @patch("ktrdr.cli.client.core.detect_ib_issue_from_api_response")
    def test_no_enhancement_when_no_ib_issue(self, mock_detect, mock_should_show):
        """Returns original data when no IB issue detected."""
        mock_should_show.return_value = False
        error_data = {"error": {"message": "Some error"}}

        result = enhance_with_ib_diagnostics(error_data)

        assert result == error_data
        mock_detect.assert_not_called()

    @patch("ktrdr.cli.client.core.should_show_ib_diagnosis")
    @patch("ktrdr.cli.client.core.detect_ib_issue_from_api_response")
    def test_enhances_with_ib_diagnosis(self, mock_detect, mock_should_show):
        """Enhances error data with IB diagnosis when detected."""
        mock_should_show.return_value = True
        mock_detect.return_value = (
            "recoverable",
            "IB issue message",
            {"detail": "info"},
        )
        error_data = {"error": {"message": "Some error"}}

        result = enhance_with_ib_diagnostics(error_data)

        assert "ib_diagnosis" in result
        assert result["ib_diagnosis"]["problem_type"] == "recoverable"
        assert result["ib_diagnosis"]["message"] == "IB issue message"
        assert result["ib_diagnosis"]["details"] == {"detail": "info"}

    @patch("ktrdr.cli.client.core.should_show_ib_diagnosis")
    @patch("ktrdr.cli.client.core.detect_ib_issue_from_api_response")
    def test_preserves_original_data(self, mock_detect, mock_should_show):
        """Preserves original error data when enhancing."""
        mock_should_show.return_value = True
        mock_detect.return_value = ("recoverable", "IB message", {})
        error_data = {"error": {"message": "Original"}, "other": "data"}

        result = enhance_with_ib_diagnostics(error_data)

        assert result["error"] == {"message": "Original"}
        assert result["other"] == "data"
        assert "ib_diagnosis" in result

    def test_handles_empty_error_data(self):
        """Handles empty error data gracefully."""
        result = enhance_with_ib_diagnostics({})
        assert result == {}

    def test_handles_none_error_data(self):
        """Handles None error data gracefully."""
        result = enhance_with_ib_diagnostics(None)  # type: ignore[arg-type]
        assert result is None or result == {}
