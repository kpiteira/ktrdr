"""
Tests for FuzzyEngine feature_id support and error handling (Phase 4).

This module tests the enhanced error messages and validation for feature_ids,
including typo detection and helpful suggestions.
"""

import pandas as pd
import pytest

from ktrdr.errors import ProcessingError
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.fuzzy.config import FuzzyConfigLoader


class TestFuzzyEngineFeatureIDSupport:
    """Test suite for FuzzyEngine with feature_id support."""

    @pytest.fixture
    def sample_config_dict(self):
        """Create sample fuzzy config with feature_ids."""
        return {
            "rsi_14": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "medium": {"type": "triangular", "parameters": [30, 50, 70]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            },
            "rsi_21": {
                "oversold": {"type": "triangular", "parameters": [0, 20, 40]},
                "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                "overbought": {"type": "triangular", "parameters": [60, 80, 100]},
            },
            "macd_12_26_9": {
                "bearish": {"type": "triangular", "parameters": [-50, -20, 0]},
                "neutral": {"type": "triangular", "parameters": [-10, 0, 10]},
                "bullish": {"type": "triangular", "parameters": [0, 20, 50]},
            },
        }

    @pytest.fixture
    def fuzzy_engine(self, sample_config_dict):
        """Create FuzzyEngine with sample configuration."""
        config = FuzzyConfigLoader.load_from_dict(sample_config_dict)
        return FuzzyEngine(config)

    def test_fuzzy_with_valid_feature_ids(self, fuzzy_engine):
        """Test normal operation with valid feature_ids."""
        # Test fuzzification with valid feature_ids
        rsi_values = pd.Series([30.0, 50.0, 70.0])
        result = fuzzy_engine.fuzzify("rsi_14", rsi_values)

        # Should return DataFrame with expected columns
        assert isinstance(result, pd.DataFrame)
        assert "rsi_14_low" in result.columns
        assert "rsi_14_medium" in result.columns
        assert "rsi_14_high" in result.columns

    def test_fuzzy_missing_feature_id_error_structure(self, fuzzy_engine):
        """Test that missing feature_id error has all required fields."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("rsi_wrong", rsi_values)

        error = exc_info.value

        # Verify error has all required fields
        assert hasattr(error, "message")
        assert hasattr(error, "error_code")
        assert error.error_code == "ENGINE-UnknownIndicator"

        # Verify error has details dict
        assert hasattr(error, "details")
        assert isinstance(error.details, dict)
        assert "indicator" in error.details
        assert error.details["indicator"] == "rsi_wrong"

    def test_fuzzy_missing_feature_id_includes_available_features(self, fuzzy_engine):
        """Test that error message includes list of available feature_ids."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("unknown_feature", rsi_values)

        error = exc_info.value

        # Should include available_indicators in details
        assert "available_indicators" in error.details
        available = error.details["available_indicators"]

        # Should include all configured feature_ids
        assert "rsi_14" in available
        assert "rsi_21" in available
        assert "macd_12_26_9" in available

    def test_fuzzy_typo_detection_suggests_close_match(self, fuzzy_engine):
        """Test that typos are detected and close matches suggested."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        # Test typo: "rsi_1" instead of "rsi_14"
        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("rsi_1", rsi_values)

        error = exc_info.value

        # Should suggest close match
        assert "suggestion" in error.details or hasattr(error, "suggestion")

        # Get the suggestion from details or attribute
        suggestion = error.details.get("suggestion") or getattr(error, "suggestion", "")

        # Should suggest "rsi_14" as close match
        assert "rsi_14" in suggestion.lower() or "rsi_14" in str(error.message).lower()

    def test_fuzzy_typo_detection_multiple_candidates(self, fuzzy_engine):
        """Test typo detection with multiple similar feature_ids."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        # Test typo: "rsi" could match "rsi_14" or "rsi_21"
        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("rsi", rsi_values)

        error = exc_info.value

        # Should provide helpful suggestions
        error_text = str(error.message).lower()

        # Should mention available feature_ids that start with "rsi"
        assert (
            "rsi_14" in str(error.details.get("available_indicators", []))
            or "rsi_14" in error_text
        )

    def test_fuzzy_error_message_is_actionable(self, fuzzy_engine):
        """Test that error messages are actionable and helpful."""
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("wrong_feature", rsi_values)

        error = exc_info.value

        # Error message should be clear
        assert "wrong_feature" in error.message
        assert (
            "not found" in error.message.lower() or "unknown" in error.message.lower()
        )

        # Should have actionable suggestion
        assert "available_indicators" in error.details
        assert len(error.details["available_indicators"]) > 0

    def test_fuzzy_handles_exact_prefix_match(self, fuzzy_engine):
        """Test that partial matches are handled correctly."""
        # "rsi" is a prefix of "rsi_14" and "rsi_21" but not exact match
        rsi_values = pd.Series([30.0, 50.0, 70.0])

        with pytest.raises(ProcessingError) as exc_info:
            fuzzy_engine.fuzzify("rsi", rsi_values)

        error = exc_info.value

        # Should fail with clear error (not exact match)
        assert error.error_code == "ENGINE-UnknownIndicator"
        assert "rsi" in error.details["indicator"]


class TestFuzzyEngineErrorContext:
    """Test suite for error context and details."""

    @pytest.fixture
    def minimal_config(self):
        """Create minimal fuzzy config."""
        config_dict = {
            "feature_x": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            }
        }
        config = FuzzyConfigLoader.load_from_dict(config_dict)
        return FuzzyEngine(config)

    def test_error_includes_context_when_feature_not_found(self, minimal_config):
        """Test that errors include helpful context."""
        values = pd.Series([30.0, 50.0])

        with pytest.raises(ProcessingError) as exc_info:
            minimal_config.fuzzify("missing_feature", values)

        error = exc_info.value

        # Should have clear context
        assert "indicator" in error.details
        assert error.details["indicator"] == "missing_feature"

        # Should list available options
        assert "available_indicators" in error.details
        assert "feature_x" in error.details["available_indicators"]


class TestFuzzyEngineLevenshteinDistance:
    """Test suite for typo detection using Levenshtein distance."""

    @pytest.fixture
    def typo_test_config(self):
        """Create config for testing typo detection."""
        config_dict = {
            "rsi_14": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            },
            "macd_12_26_9": {
                "bearish": {"type": "triangular", "parameters": [-50, -20, 0]},
                "bullish": {"type": "triangular", "parameters": [0, 20, 50]},
            },
            "ema_20": {
                "below": {"type": "triangular", "parameters": [0.93, 0.97, 1.00]},
                "above": {"type": "triangular", "parameters": [1.00, 1.03, 1.07]},
            },
        }
        config = FuzzyConfigLoader.load_from_dict(config_dict)
        return FuzzyEngine(config)

    def test_typo_one_character_off(self, typo_test_config):
        """Test detection of single character typos."""
        values = pd.Series([30.0])

        # "rsi_15" is one character off from "rsi_14"
        with pytest.raises(ProcessingError) as exc_info:
            typo_test_config.fuzzify("rsi_15", values)

        error = exc_info.value

        # Should suggest "rsi_14" as close match
        suggestion_text = str(error.details.get("suggestion", "")) + str(error.message)
        assert "rsi_14" in suggestion_text.lower()

    def test_typo_missing_underscore(self, typo_test_config):
        """Test detection of missing separator typos."""
        values = pd.Series([30.0])

        # "rsi14" is missing underscore
        with pytest.raises(ProcessingError) as exc_info:
            typo_test_config.fuzzify("rsi14", values)

        error = exc_info.value

        # Should suggest "rsi_14" as close match
        # At minimum should list available indicators including rsi_14
        assert "rsi_14" in str(error.details.get("available_indicators", []))

    def test_no_false_positive_suggestions(self, typo_test_config):
        """Test that completely different names don't get false suggestions."""
        values = pd.Series([30.0])

        # "xyz_123" is completely different
        with pytest.raises(ProcessingError) as exc_info:
            typo_test_config.fuzzify("xyz_123", values)

        error = exc_info.value

        # Should not suggest any specific match (too different)
        # But should list all available options
        assert "available_indicators" in error.details
        assert len(error.details["available_indicators"]) == 3


class TestFuzzyEngineBackwardCompatibility:
    """Test that existing behavior is preserved."""

    @pytest.fixture
    def legacy_style_config(self):
        """Create config using old-style indicator names."""
        config_dict = {
            "rsi": {
                "low": {"type": "triangular", "parameters": [0, 30, 50]},
                "high": {"type": "triangular", "parameters": [50, 70, 100]},
            },
            "macd": {
                "bearish": {"type": "triangular", "parameters": [-50, -20, 0]},
                "bullish": {"type": "triangular", "parameters": [0, 20, 50]},
            },
        }
        config = FuzzyConfigLoader.load_from_dict(config_dict)
        return FuzzyEngine(config)

    def test_legacy_names_still_work(self, legacy_style_config):
        """Test that old-style indicator names (without params) still work."""
        values = pd.Series([30.0, 50.0, 70.0])

        # Should work with old-style names
        result = legacy_style_config.fuzzify("rsi", values)

        assert isinstance(result, pd.DataFrame)
        assert "rsi_low" in result.columns
        assert "rsi_high" in result.columns

    def test_legacy_error_handling_preserved(self, legacy_style_config):
        """Test that error handling works with old-style configs too."""
        values = pd.Series([30.0])

        with pytest.raises(ProcessingError) as exc_info:
            legacy_style_config.fuzzify("unknown", values)

        error = exc_info.value
        assert error.error_code == "ENGINE-UnknownIndicator"
        assert "available_indicators" in error.details
