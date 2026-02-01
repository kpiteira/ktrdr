"""
M3 E2E Validation: Fuzzy system migration complete.

Tests that:
- v2 config.py and migration.py do not exist
- MEMBERSHIP_REGISTRY importable from ktrdr.fuzzy
- All 3 MF types registered (triangular, trapezoidal, gaussian)
- Case-insensitive lookup works
- Invalid params raise ConfigurationError
- FuzzyEngine v3 mode works
"""

import os

import pytest


class TestV2FilesDeleted:
    """Verify v2 files have been deleted."""

    def test_config_py_does_not_exist(self):
        """config.py should not exist in ktrdr/fuzzy/."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "ktrdr",
            "fuzzy",
            "config.py",
        )
        assert not os.path.exists(
            config_path
        ), "ktrdr/fuzzy/config.py should be deleted"

    def test_migration_py_does_not_exist(self):
        """migration.py should not exist in ktrdr/fuzzy/."""
        migration_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
            "ktrdr",
            "fuzzy",
            "migration.py",
        )
        assert not os.path.exists(
            migration_path
        ), "ktrdr/fuzzy/migration.py should be deleted"


class TestMembershipRegistryExport:
    """Verify MEMBERSHIP_REGISTRY is properly exported."""

    def test_membership_registry_importable_from_ktrdr_fuzzy(self):
        """MEMBERSHIP_REGISTRY should be importable from ktrdr.fuzzy."""
        from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

        assert MEMBERSHIP_REGISTRY is not None

    def test_membership_registry_has_all_mf_types(self):
        """All 3 MF types should be registered."""
        from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

        types = MEMBERSHIP_REGISTRY.list_types()
        assert set(types) == {"triangular", "trapezoidal", "gaussian"}

    @pytest.mark.parametrize(
        "name",
        [
            "triangular",
            "Triangular",
            "TRIANGULAR",
            "triangularmf",
            "TriangularMF",
            "trapezoidal",
            "Trapezoidal",
            "TRAPEZOIDAL",
            "trapezoidalmf",
            "gaussian",
            "Gaussian",
            "GAUSSIAN",
            "gaussianmf",
        ],
    )
    def test_case_insensitive_lookup(self, name: str):
        """Registry should support case-insensitive lookup."""
        from ktrdr.fuzzy import MEMBERSHIP_REGISTRY

        mf_class = MEMBERSHIP_REGISTRY.get(name)
        assert mf_class is not None, f"Lookup failed for '{name}'"


class TestMembershipFunctionValidation:
    """Verify membership function parameter validation."""

    def test_triangular_invalid_param_count_raises_configuration_error(self):
        """TriangularMF with wrong param count raises ConfigurationError."""
        from ktrdr.errors import ConfigurationError
        from ktrdr.fuzzy import TriangularMF

        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([1, 2])  # Wrong count - needs 3

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_triangular_invalid_ordering_raises_configuration_error(self):
        """TriangularMF with invalid ordering raises ConfigurationError."""
        from ktrdr.errors import ConfigurationError
        from ktrdr.fuzzy import TriangularMF

        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([3, 2, 1])  # Must satisfy a <= b <= c

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_trapezoidal_invalid_param_count_raises_configuration_error(self):
        """TrapezoidalMF with wrong param count raises ConfigurationError."""
        from ktrdr.errors import ConfigurationError
        from ktrdr.fuzzy import TrapezoidalMF

        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([1, 2, 3])  # Wrong count - needs 4

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_gaussian_invalid_param_count_raises_configuration_error(self):
        """GaussianMF with wrong param count raises ConfigurationError."""
        from ktrdr.errors import ConfigurationError
        from ktrdr.fuzzy import GaussianMF

        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([1])  # Wrong count - needs 2

        assert exc_info.value.error_code == "MF-InvalidParameters"


class TestNoV2Exports:
    """Verify v2 exports have been removed."""

    def test_fuzzy_config_not_exported(self):
        """FuzzyConfig should not be exported from ktrdr.fuzzy."""
        import ktrdr.fuzzy as fuzzy_module

        assert not hasattr(fuzzy_module, "FuzzyConfig")

    def test_fuzzy_config_loader_not_exported(self):
        """FuzzyConfigLoader should not be exported from ktrdr.fuzzy."""
        import ktrdr.fuzzy as fuzzy_module

        assert not hasattr(fuzzy_module, "FuzzyConfigLoader")

    def test_fuzzy_set_config_not_exported(self):
        """FuzzySetConfig should not be exported from ktrdr.fuzzy."""
        import ktrdr.fuzzy as fuzzy_module

        assert not hasattr(fuzzy_module, "FuzzySetConfig")


class TestFuzzyEngineV3Works:
    """Verify FuzzyEngine works in v3 mode."""

    def test_fuzzy_engine_accepts_v3_config(self):
        """FuzzyEngine should accept dict[str, FuzzySetDefinition]."""
        from ktrdr.config.models import FuzzySetDefinition
        from ktrdr.fuzzy import FuzzyEngine

        fuzzy_sets = {
            "rsi_test": FuzzySetDefinition(
                indicator="rsi_14",
                oversold=[0, 25, 40],
                overbought=[60, 75, 100],
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        assert engine is not None

    def test_fuzzy_engine_uses_registry_for_mf_creation(self):
        """FuzzyEngine should use MEMBERSHIP_REGISTRY for MF creation."""
        import pandas as pd

        from ktrdr.config.models import FuzzySetDefinition
        from ktrdr.fuzzy import FuzzyEngine

        fuzzy_sets = {
            "rsi_test": FuzzySetDefinition(
                indicator="rsi_14",
                oversold={"type": "triangular", "parameters": [0, 25, 40]},
                overbought={"type": "trapezoidal", "parameters": [60, 70, 80, 100]},
                neutral={"type": "gaussian", "parameters": [50, 10]},
            ),
        }

        engine = FuzzyEngine(fuzzy_sets)
        values = pd.Series([30, 50, 70])
        result = engine.fuzzify("rsi_test", values)

        # Should have all membership columns
        assert "rsi_test_oversold" in result.columns
        assert "rsi_test_overbought" in result.columns
        assert "rsi_test_neutral" in result.columns
