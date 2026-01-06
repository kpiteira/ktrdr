"""Unit tests for V3 strategy validation.

Tests the validate_v3_strategy function including:
- Indicator reference validation
- Fuzzy set reference validation
- Timeframe validation
- Unused indicator warnings
- Dot notation validation for multi-output indicators
"""

import pytest

from ktrdr.config.models import StrategyConfigurationV3
from ktrdr.config.strategy_validator import (
    StrategyValidationError,
    StrategyValidationWarning,
    validate_v3_strategy,
)


@pytest.fixture
def valid_v3_config():
    """Valid v3 strategy configuration for testing."""
    return StrategyConfigurationV3(
        name="test_strategy",
        version="3.0",
        training_data={
            "symbols": {"mode": "single", "list": ["EURUSD"]},
            "timeframes": {
                "mode": "multi_timeframe",
                "list": ["5m", "1h"],
                "base_timeframe": "1h",
            },
            "history_required": 100,
        },
        indicators={
            "rsi_14": {"type": "rsi", "period": 14},
        },
        fuzzy_sets={
            "rsi_fast": {
                "indicator": "rsi_14",
                "oversold": [0, 25, 40],
                "overbought": [60, 75, 100],
            },
        },
        nn_inputs=[
            {"fuzzy_set": "rsi_fast", "timeframes": ["5m"]},
        ],
        model={"type": "mlp", "architecture": {"hidden_layers": [64, 32]}},
        decisions={"output_format": "classification", "confidence_threshold": 0.6},
        training={"method": "supervised", "labels": {"source": "zigzag"}},
    )


def test_valid_v3_strategy_passes(valid_v3_config):
    """Valid v3 strategy should pass validation with no warnings."""
    warnings = validate_v3_strategy(valid_v3_config)

    assert isinstance(warnings, list)
    assert len(warnings) == 0


def test_invalid_indicator_reference_raises_error(valid_v3_config):
    """Invalid indicator reference in fuzzy_set should raise StrategyValidationError."""
    from ktrdr.config.models import FuzzySetDefinition

    # Create fuzzy set referencing nonexistent indicator
    valid_v3_config.fuzzy_sets["bad_ref"] = FuzzySetDefinition(
        indicator="nonexistent_indicator",
        low=[0, 25, 50],
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    assert "nonexistent_indicator" in error_msg
    assert "bad_ref" in error_msg
    assert "indicator" in error_msg.lower()


def test_invalid_fuzzy_set_reference_raises_error(valid_v3_config):
    """Invalid fuzzy_set reference in nn_inputs should raise StrategyValidationError."""
    from ktrdr.config.models import NNInputSpec

    # Add nn_input referencing nonexistent fuzzy set
    valid_v3_config.nn_inputs.append(
        NNInputSpec(fuzzy_set="nonexistent_fuzzy_set", timeframes=["5m"])
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    assert "nonexistent_fuzzy_set" in error_msg
    assert "fuzzy_set" in error_msg.lower()


def test_invalid_timeframe_raises_error(valid_v3_config):
    """Invalid timeframe in nn_inputs should raise StrategyValidationError."""
    from ktrdr.config.models import NNInputSpec

    # Add nn_input with invalid timeframe
    valid_v3_config.nn_inputs.append(
        NNInputSpec(fuzzy_set="rsi_fast", timeframes=["invalid_tf"])
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    assert "invalid_tf" in error_msg
    assert "timeframe" in error_msg.lower()


def test_timeframes_all_is_valid(valid_v3_config):
    """Timeframes: 'all' should be valid."""
    from ktrdr.config.models import NNInputSpec

    # Replace nn_inputs with one that uses "all"
    valid_v3_config.nn_inputs = [NNInputSpec(fuzzy_set="rsi_fast", timeframes="all")]

    warnings = validate_v3_strategy(valid_v3_config)
    assert len(warnings) == 0


def test_unused_indicator_produces_warning(valid_v3_config):
    """Unused indicator should produce warning, not error."""
    # Add indicator that's not referenced by any fuzzy set
    valid_v3_config.indicators["unused_sma"] = {"type": "sma", "period": 20}

    warnings = validate_v3_strategy(valid_v3_config)

    assert len(warnings) == 1
    assert isinstance(warnings[0], StrategyValidationWarning)
    assert "unused_sma" in warnings[0].message
    assert warnings[0].location == "indicators.unused_sma"


def test_valid_dot_notation_passes(valid_v3_config):
    """Valid dot notation for multi-output indicator should pass."""
    from ktrdr.config.models import FuzzySetDefinition, IndicatorDefinition

    # Add bbands indicator
    valid_v3_config.indicators["bbands_20_2"] = IndicatorDefinition(
        type="bbands",
        period=20,
        multiplier=2.0,
    )

    # Reference upper output with dot notation
    valid_v3_config.fuzzy_sets["bbands_upper"] = FuzzySetDefinition(
        indicator="bbands_20_2.upper",
        low=[0, 0.3, 0.5],
        high=[0.5, 0.7, 1.0],
    )

    warnings = validate_v3_strategy(valid_v3_config)
    assert len(warnings) == 0


def test_invalid_dot_notation_output_raises_error(valid_v3_config):
    """Invalid output name in dot notation should raise StrategyValidationError."""
    from ktrdr.config.models import FuzzySetDefinition, IndicatorDefinition

    # Add bbands indicator
    valid_v3_config.indicators["bbands_20_2"] = IndicatorDefinition(
        type="bbands",
        period=20,
        multiplier=2.0,
    )

    # Reference invalid output
    valid_v3_config.fuzzy_sets["bbands_invalid"] = FuzzySetDefinition(
        indicator="bbands_20_2.invalid_output",
        low=[0, 0.3, 0.5],
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    assert "invalid_output" in error_msg
    assert "bbands" in error_msg.lower()


def test_dot_notation_on_single_output_raises_error(valid_v3_config):
    """Dot notation on single-output indicator should raise error."""
    from ktrdr.config.models import FuzzySetDefinition

    # Try to use dot notation on RSI (single output)
    valid_v3_config.fuzzy_sets["rsi_fast"] = FuzzySetDefinition(
        indicator="rsi_14.value",
        oversold=[0, 25, 40],
        overbought=[60, 75, 100],
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    assert "rsi" in error_msg.lower()
    assert "single" in error_msg.lower() or "does not have" in error_msg.lower()


def test_error_messages_include_location_context(valid_v3_config):
    """Error messages should include clear location context."""
    from ktrdr.config.models import FuzzySetDefinition

    valid_v3_config.fuzzy_sets["problem_set"] = FuzzySetDefinition(
        indicator="missing_indicator",
        low=[0, 25, 50],
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(valid_v3_config)

    error_msg = str(exc_info.value)
    # Should mention which fuzzy_set has the problem
    assert "problem_set" in error_msg
    # Should mention what field is wrong
    assert "indicator" in error_msg.lower()
    # Should mention what's missing
    assert "missing_indicator" in error_msg


def test_multiple_errors_reported_together():
    """Multiple validation errors should be collected and reported together."""
    config = StrategyConfigurationV3(
        name="multi_error_test",
        version="3.0",
        training_data={
            "symbols": {"mode": "single", "list": ["TEST"]},
            "timeframes": {"mode": "single", "list": ["1h"], "base_timeframe": "1h"},
            "history_required": 100,
        },
        indicators={
            "rsi_14": {"type": "rsi", "period": 14},
        },
        fuzzy_sets={
            "bad_indicator_ref": {
                "indicator": "nonexistent",
                "low": [0, 25, 50],
            },
        },
        nn_inputs=[
            {"fuzzy_set": "bad_fuzzy_ref", "timeframes": ["invalid_tf"]},
        ],
        model={"type": "mlp"},
        decisions={"output_format": "classification"},
        training={"method": "supervised"},
    )

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_v3_strategy(config)

    error_msg = str(exc_info.value)
    # Should mention multiple problems
    assert "nonexistent" in error_msg or "bad_indicator_ref" in error_msg
