"""
Unit tests for feature_id validation in indicator configuration.

Tests cover:
- feature_id requirement (MANDATORY)
- feature_id format validation
- feature_id reserved words
- feature_id uniqueness
- Various naming patterns (params, semantic)
"""

import pytest
from pydantic import ValidationError

from ktrdr.config.models import IndicatorConfig, StrategyConfigurationV2
from ktrdr.errors.exceptions import ConfigurationError


class TestFeatureIdRequired:
    """Test that feature_id field is mandatory."""

    def test_feature_id_required(self):
        """Missing feature_id should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", params={"period": 14})

        error = exc_info.value
        errors = error.errors()
        assert len(errors) > 0
        assert any(err["loc"] == ("feature_id",) for err in errors)
        assert any(err["type"] == "missing" for err in errors)

    def test_feature_id_cannot_be_none(self):
        """feature_id=None should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", feature_id=None, params={"period": 14})

        error = exc_info.value
        errors = error.errors()
        assert any("feature_id" in str(err["loc"]) for err in errors)

    def test_feature_id_cannot_be_empty_string(self):
        """feature_id='' should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", feature_id="", params={"period": 14})

        error = exc_info.value
        errors = error.errors()
        assert any("feature_id" in str(err["loc"]) for err in errors)


class TestFeatureIdFormat:
    """Test feature_id format validation."""

    @pytest.mark.parametrize(
        "feature_id",
        [
            "rsi_14",  # params-based
            "rsi_fast",  # semantic
            "macd_12_26_9",  # multi-param
            "ema_short",  # semantic
            "RSI_14",  # uppercase
            "my_custom_indicator",  # multiple underscores
            "trend-indicator",  # dash separator
            "a",  # single letter
            "indicator123",  # numbers at end
        ],
    )
    def test_valid_feature_id_formats(self, feature_id):
        """Valid feature_id formats should be accepted."""
        config = IndicatorConfig(
            type="rsi", feature_id=feature_id, params={"period": 14}
        )
        assert config.feature_id == feature_id

    @pytest.mark.parametrize(
        "invalid_feature_id",
        [
            "123rsi",  # starts with number
            "1",  # just a number
            "rsi@14",  # special character @
            "rsi#14",  # special character #
            "rsi.14",  # dot separator
            "rsi 14",  # space
            "rsi$14",  # dollar sign
            "_rsi",  # starts with underscore
            "-rsi",  # starts with dash
            "rsi_14!",  # ends with special char
        ],
    )
    def test_invalid_feature_id_formats(self, invalid_feature_id):
        """Invalid feature_id formats should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(
                type="rsi", feature_id=invalid_feature_id, params={"period": 14}
            )

        error = exc_info.value
        errors = error.errors()
        # Should have validation error on feature_id field
        assert any("feature_id" in str(err["loc"]) for err in errors)
        # Check error message mentions format requirements
        error_msg = str(error)
        assert "letter" in error_msg.lower() or "format" in error_msg.lower()


class TestFeatureIdReservedWords:
    """Test that reserved words are blocked as feature_ids."""

    @pytest.mark.parametrize(
        "reserved_word",
        [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "OPEN",  # case insensitive
            "High",  # case insensitive
            "CLOSE",  # case insensitive
        ],
    )
    def test_reserved_words_blocked(self, reserved_word):
        """Reserved words should raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", feature_id=reserved_word, params={"period": 14})

        error = exc_info.value
        error_msg = str(error)
        assert "reserved" in error_msg.lower()

    @pytest.mark.parametrize(
        "allowed_word",
        [
            "close_sma",  # contains reserved word but not exact match
            "volume_indicator",  # contains reserved word but not exact match
            "my_open",  # contains reserved word but not exact match
        ],
    )
    def test_reserved_words_as_substring_allowed(self, allowed_word):
        """Reserved words as substrings should be allowed."""
        config = IndicatorConfig(
            type="rsi", feature_id=allowed_word, params={"period": 14}
        )
        assert config.feature_id == allowed_word


class TestFeatureIdUniqueness:
    """Test feature_id uniqueness validation in strategy configuration."""

    def test_duplicate_feature_ids_rejected(self):
        """Duplicate feature_ids should raise validation error."""
        strategy_dict = {
            "name": "test_strategy",
            "version": "1.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": [
                {"type": "rsi", "feature_id": "rsi_14", "params": {"period": 14}},
                {
                    "type": "rsi",
                    "feature_id": "rsi_14",  # DUPLICATE
                    "params": {"period": 21},
                },
            ],
            "fuzzy_sets": {},
            "model": {},
            "decisions": {},
            "training": {},
        }

        with pytest.raises((ValidationError, ConfigurationError)) as exc_info:
            StrategyConfigurationV2(**strategy_dict)

        error_msg = str(exc_info.value)
        assert "duplicate" in error_msg.lower() or "unique" in error_msg.lower()
        assert "rsi_14" in error_msg

    def test_unique_feature_ids_accepted(self):
        """Unique feature_ids should be accepted."""
        strategy_dict = {
            "name": "test_strategy",
            "version": "1.0",
            "scope": "universal",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "deployment": {
                "target_symbols": {"mode": "universal"},
                "target_timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": [
                {"type": "rsi", "feature_id": "rsi_14", "params": {"period": 14}},
                {"type": "rsi", "feature_id": "rsi_21", "params": {"period": 21}},
                {"type": "macd", "feature_id": "macd_standard", "params": {}},
            ],
            "fuzzy_sets": {},
            "model": {},
            "decisions": {},
            "training": {},
        }

        config = StrategyConfigurationV2(**strategy_dict)
        assert len(config.indicators) == 3


class TestFeatureIdNamingPatterns:
    """Test various feature_id naming patterns."""

    def test_params_based_naming(self):
        """Test naming with parameters (e.g., rsi_14, macd_12_26_9)."""
        indicators = [
            IndicatorConfig(type="rsi", feature_id="rsi_14", params={"period": 14}),
            IndicatorConfig(type="rsi", feature_id="rsi_21", params={"period": 21}),
            IndicatorConfig(
                type="macd",
                feature_id="macd_12_26_9",
                params={"fast": 12, "slow": 26, "signal": 9},
            ),
        ]

        for ind in indicators:
            assert ind.feature_id
            assert isinstance(ind.feature_id, str)

    def test_semantic_naming(self):
        """Test semantic naming (e.g., rsi_fast, macd_trend)."""
        indicators = [
            IndicatorConfig(type="rsi", feature_id="rsi_fast", params={"period": 7}),
            IndicatorConfig(type="rsi", feature_id="rsi_slow", params={"period": 21}),
            IndicatorConfig(
                type="macd", feature_id="macd_trend", params={"fast": 12, "slow": 26}
            ),
        ]

        for ind in indicators:
            assert ind.feature_id
            assert isinstance(ind.feature_id, str)

    def test_mixed_naming(self):
        """Test mixed naming patterns in same strategy."""
        indicators = [
            IndicatorConfig(type="rsi", feature_id="rsi_14", params={"period": 14}),
            IndicatorConfig(type="macd", feature_id="macd_trend", params={}),
            IndicatorConfig(type="ema", feature_id="ema_short", params={"period": 9}),
        ]

        for ind in indicators:
            assert ind.feature_id
            assert isinstance(ind.feature_id, str)


class TestOldFormatRejection:
    """Test that old format configs (without feature_id) are rejected."""

    def test_old_format_without_feature_id_rejected(self):
        """Old configs without feature_id should raise clear error."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", params={"period": 14})

        error = exc_info.value
        error_msg = str(error)
        # Should mention feature_id is required
        assert "feature_id" in error_msg.lower()

    def test_error_message_suggests_migration(self):
        """Error message should suggest migration tool."""
        with pytest.raises(ValidationError) as exc_info:
            IndicatorConfig(type="rsi", params={"period": 14})

        error = exc_info.value
        # Check if error is informative (ValidationError from Pydantic)
        # The error should at least mention feature_id is missing
        assert any(err["loc"] == ("feature_id",) for err in error.errors())


class TestFeatureIdGetMethod:
    """Test get_feature_id() method on IndicatorConfig."""

    def test_get_feature_id_returns_feature_id(self):
        """get_feature_id() should return the feature_id value."""
        config = IndicatorConfig(type="rsi", feature_id="rsi_14", params={"period": 14})

        # Method should exist and return feature_id
        assert hasattr(config, "get_feature_id")
        assert config.get_feature_id() == "rsi_14"

    def test_get_feature_id_with_various_patterns(self):
        """get_feature_id() should work with all naming patterns."""
        test_cases = [
            ("rsi_14", "rsi_14"),
            ("macd_standard", "macd_standard"),
            ("ema_short", "ema_short"),
        ]

        for feature_id, expected in test_cases:
            config = IndicatorConfig(type="test", feature_id=feature_id, params={})
            assert config.get_feature_id() == expected
