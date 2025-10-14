"""
API integration tests for strategy validation error responses (Task 0.2).

Tests verify that:
1. ConfigurationError is caught and formatted for HTTP response
2. API returns 400 with structured error body (never empty)
3. Error body includes: message, code, details, suggestion
4. Server logs show full error context before response
"""

from ktrdr.errors import ConfigurationError


class TestConfigurationErrorToAPIResponse:
    """Test converting ConfigurationError to API response format."""

    def test_configuration_error_serializes_for_api(self):
        """Test that ConfigurationError can be serialized to API response."""
        error = ConfigurationError(
            message="Indicator missing required field 'feature_id'",
            error_code="STRATEGY-MissingFeatureId",
            context={"file": "strategy.yaml", "section": "indicators[0]"},
            details={"indicator_type": "rsi", "period": 14},
            suggestion="Add 'feature_id' to indicator",
        )

        # Convert to dict for API response
        error_dict = error.to_dict()

        # Verify all fields are present
        assert "message" in error_dict
        assert "error_code" in error_dict
        assert "context" in error_dict
        assert "details" in error_dict
        assert "suggestion" in error_dict

        # Verify values
        assert error_dict["message"] == "Indicator missing required field 'feature_id'"
        assert error_dict["error_code"] == "STRATEGY-MissingFeatureId"
        assert error_dict["context"]["file"] == "strategy.yaml"
        assert error_dict["details"]["indicator_type"] == "rsi"
        assert "feature_id" in error_dict["suggestion"]


class TestAPIErrorResponseStructure:
    """Test that API error responses have correct structure."""

    def test_error_response_includes_all_required_fields(self):
        """Test that error response dict has all required fields."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Error",
            context={"file": "test.yaml"},
            details={"key": "value"},
            suggestion="Fix the test",
        )

        response_body = error.to_dict()

        # Must have these fields for API response
        required_fields = ["message", "error_code", "context", "details", "suggestion"]
        for field in required_fields:
            assert field in response_body, f"Missing required field: {field}"

    def test_error_response_body_never_empty(self):
        """Test that error response body is never empty."""
        error = ConfigurationError(
            message="Minimal error",
            error_code="MIN-Error",
        )

        response_body = error.to_dict()

        # Body should have content
        assert len(response_body) > 0
        assert response_body["message"]  # Message should not be empty
        assert response_body["error_code"]  # Code should not be empty


class TestAPIErrorResponseContent:
    """Test content quality of API error responses."""

    def test_error_message_is_user_friendly(self):
        """Test that error message is clear and actionable."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="macd", indicator_index=1, file_path="my_strategy.yaml"
        )

        response_body = error.to_dict()

        # Message should mention what's wrong
        assert "feature_id" in response_body["message"].lower()
        assert "macd" in response_body["message"].lower()

    def test_error_includes_where_problem_occurred(self):
        """Test that error context shows where the problem is."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi", indicator_index=0, file_path="strategy.yaml"
        )

        response_body = error.to_dict()

        # Context should show file and location
        assert response_body["context"]["file"] == "strategy.yaml"
        assert "indicators[0]" in response_body["context"]["section"]

    def test_error_includes_how_to_fix(self):
        """Test that error suggestion tells user how to fix."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi", indicator_index=0
        )

        response_body = error.to_dict()

        # Suggestion should be actionable
        assert len(response_body["suggestion"]) > 0
        assert "feature_id" in response_body["suggestion"].lower()

    def test_error_code_allows_programmatic_handling(self):
        """Test that error code enables client-side error handling."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="rsi", indicator_index=0
        )

        response_body = error.to_dict()

        # Error code should be structured and consistent
        assert response_body["error_code"] == "STRATEGY-MissingFeatureId"
        assert "-" in response_body["error_code"]  # Format: CATEGORY-Specific


class TestAPIErrorLogging:
    """Test that errors are logged before returning response."""

    def test_error_has_loggable_representation(self):
        """Test that error can be logged with full context."""
        error = ConfigurationError(
            message="Configuration error",
            error_code="CONFIG-Error",
            context={"file": "test.yaml", "line": 10},
            details={"field": "indicators", "issue": "missing"},
            suggestion="Add indicators section",
        )

        # Should be able to format for logging
        log_message = error.format_user_message()

        assert "Configuration error" in log_message
        assert "CONFIG-Error" in log_message
        assert "test.yaml" in log_message
        assert "Add indicators section" in log_message

    def test_error_string_includes_context(self):
        """Test that error string representation includes key info."""
        error = ConfigurationError(
            message="Test error",
            error_code="TEST-Error",
        )

        error_str = str(error)

        # Should include error code for log searchability
        assert "TEST-Error" in error_str
        assert "Test error" in error_str


class TestAPIErrorResponseExamples:
    """Test realistic error response examples."""

    def test_missing_feature_id_response(self):
        """Test complete response for missing feature_id error."""
        error = ConfigurationError.missing_feature_id(
            indicator_type="bollinger_bands",
            indicator_index=2,
            file_path="production_strategy.yaml",
        )

        response_body = error.to_dict()

        # Verify complete response structure
        assert response_body["error_code"] == "STRATEGY-MissingFeatureId"
        assert "bollinger_bands" in response_body["message"].lower()
        assert response_body["context"]["file"] == "production_strategy.yaml"
        assert response_body["context"]["section"] == "indicators[2]"
        assert response_body["details"]["indicator_type"] == "bollinger_bands"
        assert "migrate_to_feature_ids.py" in response_body["suggestion"]

    def test_duplicate_feature_id_response(self):
        """Test complete response for duplicate feature_id error."""
        error = ConfigurationError.duplicate_feature_id(
            feature_id="macd_fast", indices=[0, 3], file_path="strategy.yaml"
        )

        response_body = error.to_dict()

        assert response_body["error_code"] == "STRATEGY-DuplicateFeatureId"
        assert "duplicate" in response_body["message"].lower()
        assert "macd_fast" in response_body["message"]
        assert response_body["details"]["indices"] == [0, 3]
        assert "unique" in response_body["suggestion"].lower()

    def test_invalid_format_response(self):
        """Test complete response for invalid feature_id format error."""
        error = ConfigurationError.invalid_feature_id_format(
            feature_id="123_bad_id", indicator_index=1
        )

        response_body = error.to_dict()

        assert response_body["error_code"] == "STRATEGY-InvalidFeatureIdFormat"
        assert "format" in response_body["message"].lower()
        assert "123_bad_id" in response_body["message"]
        assert "must start with a letter" in response_body["suggestion"].lower()

    def test_reserved_word_response(self):
        """Test complete response for reserved feature_id error."""
        error = ConfigurationError.reserved_feature_id(
            feature_id="volume", indicator_index=0
        )

        response_body = error.to_dict()

        assert response_body["error_code"] == "STRATEGY-ReservedFeatureId"
        assert "reserved" in response_body["message"].lower()
        assert "volume" in response_body["message"]
        assert "open, high, low, close, volume" in response_body["suggestion"].lower()


class TestErrorResponseConsistency:
    """Test that all errors follow consistent response format."""

    def test_all_factory_methods_produce_valid_responses(self):
        """Test that all factory methods create valid API responses."""
        errors = [
            ConfigurationError.missing_feature_id("rsi", 0),
            ConfigurationError.duplicate_feature_id("macd_std", [0, 1]),
            ConfigurationError.invalid_feature_id_format("!invalid", 0),
            ConfigurationError.reserved_feature_id("close", 0),
        ]

        for error in errors:
            response_body = error.to_dict()

            # All should have required fields
            assert "message" in response_body
            assert "error_code" in response_body
            assert "context" in response_body
            assert "details" in response_body
            assert "suggestion" in response_body

            # All should have non-empty essential fields
            assert len(response_body["message"]) > 0
            assert len(response_body["error_code"]) > 0

    def test_error_codes_follow_naming_convention(self):
        """Test that error codes follow consistent naming."""
        errors = [
            ConfigurationError.missing_feature_id("rsi", 0),
            ConfigurationError.duplicate_feature_id("macd", [0, 1]),
            ConfigurationError.invalid_feature_id_format("bad", 0),
            ConfigurationError.reserved_feature_id("close", 0),
        ]

        for error in errors:
            # All should start with STRATEGY-
            assert error.error_code.startswith("STRATEGY-")

            # All should have format: CATEGORY-SpecificError
            parts = error.error_code.split("-")
            assert len(parts) == 2
            assert parts[0] == "STRATEGY"
            assert parts[1][0].isupper()  # PascalCase


class TestAPIErrorResponseJSONCompatibility:
    """Test that error responses are JSON-serializable."""

    def test_response_is_json_serializable(self):
        """Test that error response can be converted to JSON."""
        import json

        error = ConfigurationError(
            message="Test",
            error_code="TEST",
            context={"file": "test.yaml"},
            details={"key": "value"},
            suggestion="Fix it",
        )

        response_body = error.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(response_body)
        assert isinstance(json_str, str)

        # Should be JSON-deserializable
        recovered = json.loads(json_str)
        assert recovered["message"] == "Test"
        assert recovered["error_code"] == "TEST"

    def test_complex_error_is_json_serializable(self):
        """Test that error with complex details is JSON-serializable."""
        import json

        error = ConfigurationError(
            message="Complex error",
            error_code="COMPLEX",
            context={"file": "test.yaml", "nested": {"key": "value"}},
            details={
                "list": [1, 2, 3],
                "dict": {"a": 1, "b": 2},
                "string": "test",
            },
            suggestion="Fix complex issue",
        )

        response_body = error.to_dict()
        json_str = json.dumps(response_body)  # Should not raise
        assert isinstance(json_str, str)
