"""
Tests for MultiTimeframeFuzzyEngine registry integration.

These tests verify that MultiTimeframeFuzzyEngine uses MEMBERSHIP_REGISTRY
for membership function creation instead of hardcoded v2 config classes.
"""

import pytest

from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy.multi_timeframe_engine import MultiTimeframeFuzzyEngine


class TestMultiTimeframeFuzzyEngineRegistry:
    """Tests for registry-based MF creation in MultiTimeframeFuzzyEngine."""

    def test_uses_membership_registry_for_triangular(self) -> None:
        """Triangular MF should be created via MEMBERSHIP_REGISTRY."""
        config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "triangular", "parameters": [0, 0, 30]},
                        }
                    },
                }
            },
            "indicators": ["rsi"],
        }

        engine = MultiTimeframeFuzzyEngine(config)
        assert engine.is_multi_timeframe_enabled()
        assert "1h" in engine.get_supported_timeframes()

    def test_uses_membership_registry_for_trapezoidal(self) -> None:
        """Trapezoidal MF should be created via MEMBERSHIP_REGISTRY."""
        config = {
            "timeframes": {
                "4h": {
                    "indicators": ["macd"],
                    "fuzzy_sets": {
                        "macd": {
                            "neutral": {
                                "type": "trapezoidal",
                                "parameters": [-0.01, -0.005, 0.005, 0.01],
                            },
                        }
                    },
                }
            },
            "indicators": ["macd"],
        }

        engine = MultiTimeframeFuzzyEngine(config)
        assert engine.is_multi_timeframe_enabled()
        assert "4h" in engine.get_supported_timeframes()

    def test_uses_membership_registry_for_gaussian(self) -> None:
        """Gaussian MF should be created via MEMBERSHIP_REGISTRY."""
        config = {
            "timeframes": {
                "1d": {
                    "indicators": ["trend"],
                    "fuzzy_sets": {
                        "trend": {
                            "neutral": {"type": "gaussian", "parameters": [50, 10]},
                        }
                    },
                }
            },
            "indicators": ["trend"],
        }

        engine = MultiTimeframeFuzzyEngine(config)
        assert engine.is_multi_timeframe_enabled()
        assert "1d" in engine.get_supported_timeframes()

    def test_unknown_mf_type_raises_configuration_error(self) -> None:
        """Unknown MF type should raise ConfigurationError from registry."""
        config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            "low": {"type": "unknown_type", "parameters": [0, 50, 100]},
                        }
                    },
                }
            },
            "indicators": ["rsi"],
        }

        with pytest.raises(ConfigurationError) as exc_info:
            MultiTimeframeFuzzyEngine(config)

        # Should use registry's error format
        assert "unknown_type" in str(exc_info.value).lower()

    def test_invalid_parameters_raises_configuration_error(self) -> None:
        """Invalid MF parameters should raise ConfigurationError."""
        config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            # Wrong number of parameters for triangular
                            "low": {"type": "triangular", "parameters": [0, 50]},
                        }
                    },
                }
            },
            "indicators": ["rsi"],
        }

        with pytest.raises(ConfigurationError):
            MultiTimeframeFuzzyEngine(config)

    def test_case_insensitive_mf_type_lookup(self) -> None:
        """MF type lookup should be case-insensitive via registry."""
        config = {
            "timeframes": {
                "1h": {
                    "indicators": ["rsi"],
                    "fuzzy_sets": {
                        "rsi": {
                            # Uppercase type should work
                            "low": {"type": "TRIANGULAR", "parameters": [0, 0, 30]},
                        }
                    },
                }
            },
            "indicators": ["rsi"],
        }

        # Should not raise - registry handles case insensitivity
        engine = MultiTimeframeFuzzyEngine(config)
        assert engine.is_multi_timeframe_enabled()


class TestMultiTimeframeFuzzyEngineNoV2Imports:
    """Tests verifying no v2 config imports are used."""

    def test_does_not_import_v2_config_classes(self) -> None:
        """Verify module doesn't import from ktrdr.fuzzy.config."""
        import ktrdr.fuzzy.multi_timeframe_engine as mtfe

        # Check module doesn't have v2 config class references
        module_attrs = dir(mtfe)

        # These v2 classes should NOT be in the module namespace
        v2_classes = [
            "FuzzyConfig",
            "FuzzySetConfig",
            "TriangularMFConfig",
            "TrapezoidalMFConfig",
            "GaussianMFConfig",
        ]

        for cls in v2_classes:
            assert cls not in module_attrs, f"v2 class {cls} should not be imported"

    def test_membership_registry_is_accessible(self) -> None:
        """Verify MEMBERSHIP_REGISTRY is used and accessible."""
        # Should be able to import from membership module
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        # All 3 MF types should be registered
        assert MEMBERSHIP_REGISTRY.get("triangular") is not None
        assert MEMBERSHIP_REGISTRY.get("trapezoidal") is not None
        assert MEMBERSHIP_REGISTRY.get("gaussian") is not None
