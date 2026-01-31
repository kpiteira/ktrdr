"""Unit tests for StrategyValidator using INDICATOR_REGISTRY.

Task 2.7: Verifies that StrategyValidator uses INDICATOR_REGISTRY exclusively
without any reference to BUILT_IN_INDICATORS.
"""

import ast
import inspect

import pytest

from ktrdr.config.strategy_validator import StrategyValidator


class TestNoBuiltInIndicatorsReference:
    """Tests verifying BUILT_IN_INDICATORS is not used."""

    def test_strategy_validator_has_no_built_in_indicators_import(self) -> None:
        """strategy_validator.py should not import BUILT_IN_INDICATORS."""
        import ktrdr.config.strategy_validator as sv_module

        source = inspect.getsource(sv_module)
        tree = ast.parse(source)

        # Check for any imports referencing BUILT_IN_INDICATORS
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert (
                        alias.name != "BUILT_IN_INDICATORS"
                    ), "strategy_validator.py should not import BUILT_IN_INDICATORS"

    def test_strategy_validator_has_no_built_in_indicators_reference(self) -> None:
        """strategy_validator.py should not reference BUILT_IN_INDICATORS anywhere."""
        import ktrdr.config.strategy_validator as sv_module

        source = inspect.getsource(sv_module)

        # Check source code for any reference to BUILT_IN_INDICATORS
        assert (
            "BUILT_IN_INDICATORS" not in source
        ), "strategy_validator.py should not reference BUILT_IN_INDICATORS"

    def test_strategy_validator_imports_indicator_registry(self) -> None:
        """strategy_validator.py should import INDICATOR_REGISTRY at top level."""
        import ktrdr.config.strategy_validator as sv_module

        source = inspect.getsource(sv_module)

        # Should have top-level import of INDICATOR_REGISTRY
        assert (
            "INDICATOR_REGISTRY" in source
        ), "strategy_validator.py should import INDICATOR_REGISTRY"


class TestIndicatorTypeValidationUsesRegistry:
    """Tests verifying indicator type validation uses INDICATOR_REGISTRY."""

    def test_validator_detects_valid_indicator_types(self) -> None:
        """Validator should accept all registered indicator types."""
        # Import indicator modules to ensure registration

        validator = StrategyValidator()
        names = validator._get_normalized_indicator_names()

        # Should have indicator names from registry
        assert len(names) > 0
        # RSI should be in the list
        assert "rsi" in names or "rsiindicator" in names

    def test_validator_indicator_names_match_registry(self) -> None:
        """Validator's indicator names should come from INDICATOR_REGISTRY."""
        from ktrdr.indicators.base_indicator import INDICATOR_REGISTRY

        validator = StrategyValidator()
        names = validator._get_normalized_indicator_names()

        # Get registry types
        registry_types = set(INDICATOR_REGISTRY.list_types())

        # All registry types should be in validator names
        for reg_type in registry_types:
            assert (
                reg_type in names
            ), f"Registry type '{reg_type}' should be in validator names"

    def test_validator_no_lazy_caching(self) -> None:
        """Validator should not need lazy-loading caching for indicator names."""
        validator = StrategyValidator()

        # Call multiple times - should work without caching mechanism
        names1 = validator._get_normalized_indicator_names()
        names2 = validator._get_normalized_indicator_names()

        assert names1 == names2


class TestV3StrategyValidationUsesRegistry:
    """Tests for v3 strategy validation using INDICATOR_REGISTRY."""

    def test_validate_v3_dot_notation_with_registered_indicator(self) -> None:
        """v3 validation should validate dot notation using INDICATOR_REGISTRY."""
        from ktrdr.config.models import StrategyConfigurationV3
        from ktrdr.config.strategy_validator import (
            validate_v3_strategy,
        )

        # Import indicator to register it
        from ktrdr.indicators.bollinger_bands_indicator import (  # noqa: F401
            BollingerBandsIndicator,
        )

        # Create a valid v3 config with dot notation
        config_dict = {
            "name": "test_dot_notation",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": {
                "bb_20": {"type": "bollingerbands", "period": 20, "multiplier": 2.0},
            },
            "fuzzy_sets": {
                "bb_upper": {
                    "indicator": "bb_20.upper",  # Dot notation
                    "high": {"type": "triangular", "parameters": [0, 50, 100]},
                },
            },
            "nn_inputs": [
                {"fuzzy_set": "bb_upper", "timeframes": "all"},
            ],
            "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
            "decisions": {"output_format": "classification"},
            "training": {"method": "supervised", "labels": {"source": "zigzag"}},
        }

        config = StrategyConfigurationV3(**config_dict)

        # Should not raise - dot notation is valid for multi-output indicator
        validate_v3_strategy(config)
        # Just check it doesn't raise an error

    def test_validate_v3_invalid_dot_notation_output(self) -> None:
        """v3 validation should reject invalid output names in dot notation."""
        from ktrdr.config.models import StrategyConfigurationV3
        from ktrdr.config.strategy_validator import (
            StrategyValidationError,
            validate_v3_strategy,
        )

        # Import indicator to register it
        from ktrdr.indicators.bollinger_bands_indicator import (  # noqa: F401
            BollingerBandsIndicator,
        )

        # Create a v3 config with invalid dot notation output
        config_dict = {
            "name": "test_invalid_dot_notation",
            "training_data": {
                "symbols": {"mode": "single", "symbol": "AAPL"},
                "timeframes": {"mode": "single", "timeframe": "1h"},
            },
            "indicators": {
                "bb_20": {"type": "bollingerbands", "period": 20, "multiplier": 2.0},
            },
            "fuzzy_sets": {
                "bb_invalid": {
                    "indicator": "bb_20.nonexistent_output",  # Invalid output name
                    "high": {"type": "triangular", "parameters": [0, 50, 100]},
                },
            },
            "nn_inputs": [
                {"fuzzy_set": "bb_invalid", "timeframes": "all"},
            ],
            "model": {"type": "mlp", "architecture": {"hidden_layers": [32]}},
            "decisions": {"output_format": "classification"},
            "training": {"method": "supervised", "labels": {"source": "zigzag"}},
        }

        config = StrategyConfigurationV3(**config_dict)

        # Should raise error about invalid output
        with pytest.raises(StrategyValidationError) as exc_info:
            validate_v3_strategy(config)

        assert "nonexistent_output" in str(exc_info.value)
        assert "Valid outputs" in str(exc_info.value)
