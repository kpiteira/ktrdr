"""
Tests for FuzzyEngine registry migration (Task 3.3).

These tests validate that FuzzyEngine:
1. Uses MEMBERSHIP_REGISTRY for MF creation
2. Rejects non-dict (v2) config with clear error
3. Has no v2 code paths remaining
"""

import pandas as pd
import pytest

from ktrdr.config.models import FuzzySetDefinition
from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy import FuzzyEngine
from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY


class TestFuzzyEngineRegistry:
    """Tests for registry-based FuzzyEngine (v3-only mode)."""

    def test_uses_registry_for_membership_functions(self) -> None:
        """FuzzyEngine should use MEMBERSHIP_REGISTRY for MF lookup."""
        # Create v3 config with triangular membership functions
        config = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                low={"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                medium={"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
                high={"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            )
        }

        engine = FuzzyEngine(config)

        # Verify engine is in v3 mode
        assert engine.is_v3_mode is True

        # Verify fuzzy set was initialized
        assert "rsi_momentum" in engine._fuzzy_sets

        # Verify registry was used (MF types should match registry)
        mf = engine._fuzzy_sets["rsi_momentum"]["low"]
        registry_cls = MEMBERSHIP_REGISTRY.get("triangular")
        assert isinstance(mf, registry_cls)

    def test_rejects_non_dict_config_with_clear_error(self) -> None:
        """FuzzyEngine should reject non-dict config with ConfigurationError."""
        # Use a non-dict object (e.g., a list or string)
        non_dict_config = ["rsi", "macd"]

        with pytest.raises(ConfigurationError) as exc_info:
            FuzzyEngine(non_dict_config)  # type: ignore[arg-type]

        # Should have clear error message about v2 being unsupported
        assert (
            "v2" in str(exc_info.value).lower() or "dict" in str(exc_info.value).lower()
        )
        assert exc_info.value.error_code == "ENGINE-V2ConfigNotSupported"

    def test_registry_lookup_case_insensitive(self) -> None:
        """Registry lookup should be case-insensitive for MF types."""
        # Test with mixed case type names
        config = {
            "test_set": FuzzySetDefinition(
                indicator="rsi_14",
                upper={"type": "Triangular", "parameters": [50.0, 75.0, 100.0]},
                middle={"type": "GAUSSIAN", "parameters": [50.0, 15.0]},
                lower={"type": "trapezoidal", "parameters": [0.0, 10.0, 20.0, 30.0]},
            )
        }

        # Should succeed - registry lookup is case-insensitive
        engine = FuzzyEngine(config)
        assert "test_set" in engine._fuzzy_sets

    def test_invalid_mf_type_raises_error(self) -> None:
        """Unknown MF type should raise ConfigurationError via registry."""
        config = {
            "test_set": FuzzySetDefinition(
                indicator="rsi_14",
                low={"type": "unknown_type", "parameters": [0.0, 30.0, 50.0]},
            )
        }

        with pytest.raises(ConfigurationError) as exc_info:
            FuzzyEngine(config)

        # Error should mention the membership function that failed
        assert "low" in str(exc_info.value).lower()
        assert exc_info.value.error_code == "ENGINE-MFCreationError"

    def test_fuzzify_v3_mode(self) -> None:
        """Fuzzify should work in v3 mode using registry-created MFs."""
        config = {
            "rsi_momentum": FuzzySetDefinition(
                indicator="rsi_14",
                low={"type": "triangular", "parameters": [0.0, 30.0, 50.0]},
                high={"type": "triangular", "parameters": [50.0, 70.0, 100.0]},
            )
        }

        engine = FuzzyEngine(config)
        values = pd.Series([25.0, 75.0])
        result = engine.fuzzify("rsi_momentum", values)

        # Check result structure
        assert isinstance(result, pd.DataFrame)
        assert "rsi_momentum_low" in result.columns
        assert "rsi_momentum_high" in result.columns

        # Check values make sense
        assert result["rsi_momentum_low"].iloc[0] > result["rsi_momentum_low"].iloc[1]
        assert result["rsi_momentum_high"].iloc[1] > result["rsi_momentum_high"].iloc[0]


class TestNoV2CodePaths:
    """Tests verifying v2 code paths have been removed."""

    def test_no_membership_function_factory_import(self) -> None:
        """MembershipFunctionFactory should not be imported in engine.py."""
        # Read engine.py source and verify no factory import
        import inspect

        from ktrdr.fuzzy import engine as engine_module

        source = inspect.getsource(engine_module)

        # MembershipFunctionFactory should not be imported
        assert "MembershipFunctionFactory" not in source

    def test_no_initialize_membership_functions_method(self) -> None:
        """_initialize_membership_functions method should not exist."""
        assert not hasattr(FuzzyEngine, "_initialize_membership_functions")

    def test_no_validate_config_method(self) -> None:
        """_validate_config method should not exist (v2 validation)."""
        assert not hasattr(FuzzyEngine, "_validate_config")

    def test_no_is_v3_fuzzy_config_function(self) -> None:
        """is_v3_fuzzy_config function should not exist."""
        from ktrdr.fuzzy import engine as engine_module

        assert not hasattr(engine_module, "is_v3_fuzzy_config")

    def test_no_fuzzy_config_import(self) -> None:
        """FuzzyConfig should not be imported in engine.py."""
        import inspect

        from ktrdr.fuzzy import engine as engine_module

        source = inspect.getsource(engine_module)

        # FuzzyConfig import should be removed
        assert "from ktrdr.fuzzy.config import FuzzyConfig" not in source
