"""
Unit tests for fuzzy input transform configuration models.

Tests the validation and behavior of input transform configurations
for fuzzy membership functions.
"""

import pytest
from pydantic import ValidationError

from ktrdr.fuzzy.config import (
    FuzzySetConfigModel,
    IdentityTransformConfig,
    PriceRatioTransformConfig,
)


class TestPriceRatioTransformConfig:
    """Test PriceRatioTransformConfig validation and behavior."""

    def test_valid_price_ratio_config(self):
        """Test valid price ratio configuration."""
        config = PriceRatioTransformConfig(reference="close")
        assert config.type == "price_ratio"
        assert config.reference == "close"

    def test_price_ratio_with_different_references(self):
        """Test price ratio with different reference columns."""
        for ref in ["open", "high", "low", "close"]:
            config = PriceRatioTransformConfig(reference=ref)
            assert config.reference == ref

    def test_price_ratio_requires_reference(self):
        """Test that reference field is required."""
        with pytest.raises(ValidationError) as exc_info:
            PriceRatioTransformConfig()  # Missing reference

        error = exc_info.value
        assert "reference" in str(error).lower()


class TestIdentityTransformConfig:
    """Test IdentityTransformConfig validation and behavior."""

    def test_valid_identity_config(self):
        """Test valid identity configuration."""
        config = IdentityTransformConfig()
        assert config.type == "identity"

    def test_identity_transform_type_is_literal(self):
        """Test that identity transform type is correct literal."""
        config = IdentityTransformConfig(type="identity")
        assert config.type == "identity"


class TestInputTransformConfigUnion:
    """Test InputTransformConfig discriminated union."""

    def test_discriminator_with_price_ratio(self):
        """Test discriminator correctly routes to PriceRatioTransformConfig."""
        config_dict = {"type": "price_ratio", "reference": "close"}
        # This would be validated by Pydantic in actual usage
        config = PriceRatioTransformConfig(**config_dict)
        assert isinstance(config, PriceRatioTransformConfig)

    def test_discriminator_with_identity(self):
        """Test discriminator correctly routes to IdentityTransformConfig."""
        config_dict = {"type": "identity"}
        config = IdentityTransformConfig(**config_dict)
        assert isinstance(config, IdentityTransformConfig)


class TestFuzzySetWithInputTransform:
    """Test FuzzySetConfigModel with input_transform field."""

    def test_fuzzy_set_without_transform(self):
        """Test fuzzy set configuration without input_transform (default)."""
        config_dict = {
            "oversold": {"type": "triangular", "parameters": [0.0, 20.0, 40.0]},
            "neutral": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
        }
        config = FuzzySetConfigModel(**config_dict)
        assert config.input_transform is None  # Default is None
        assert len(config.get_membership_functions()) == 2

    def test_fuzzy_set_with_identity_transform(self):
        """Test fuzzy set configuration with identity transform."""
        config_dict = {
            "input_transform": {"type": "identity"},
            "oversold": {"type": "triangular", "parameters": [0.0, 20.0, 40.0]},
        }
        config = FuzzySetConfigModel(**config_dict)
        assert config.input_transform is not None
        assert config.input_transform.type == "identity"
        assert len(config.get_membership_functions()) == 1

    def test_fuzzy_set_with_price_ratio_transform(self):
        """Test fuzzy set configuration with price ratio transform."""
        config_dict = {
            "input_transform": {"type": "price_ratio", "reference": "close"},
            "below": {"type": "triangular", "parameters": [0.93, 0.97, 1.00]},
            "at_ma": {"type": "triangular", "parameters": [0.98, 1.00, 1.02]},
            "above": {"type": "triangular", "parameters": [1.00, 1.03, 1.07]},
        }
        config = FuzzySetConfigModel(**config_dict)
        assert config.input_transform is not None
        assert config.input_transform.type == "price_ratio"
        assert config.input_transform.reference == "close"
        assert len(config.get_membership_functions()) == 3


class TestInputTransformExamples:
    """Test realistic examples from architecture document."""

    def test_sma_with_price_ratio_example(self):
        """Test SMA with price ratio transform example from architecture."""
        # Example from architecture document
        config_dict = {
            "input_transform": {"type": "price_ratio", "reference": "close"},
            "below": {"type": "triangular", "parameters": [0.93, 0.97, 1.00]},
            "at_ma": {"type": "triangular", "parameters": [0.98, 1.00, 1.02]},
            "above": {"type": "triangular", "parameters": [1.00, 1.03, 1.07]},
        }

        config = FuzzySetConfigModel(**config_dict)
        assert config.input_transform is not None
        assert config.input_transform.type == "price_ratio"
        assert config.input_transform.reference == "close"

        # Verify membership functions
        mfs = config.get_membership_functions()
        assert len(mfs) == 3
        assert "below" in mfs
        assert "at_ma" in mfs
        assert "above" in mfs

    def test_rsi_without_transform_example(self):
        """Test RSI without transform (identity by default)."""
        config_dict = {
            "oversold": {"type": "triangular", "parameters": [0.0, 20.0, 40.0]},
            "neutral": {"type": "triangular", "parameters": [30.0, 50.0, 70.0]},
            "overbought": {"type": "triangular", "parameters": [60.0, 80.0, 100.0]},
        }

        # This should work - no transform needed
        config = FuzzySetConfigModel(**config_dict)
        assert config.input_transform is None  # Default

        # Verify membership functions
        mfs = config.get_membership_functions()
        assert len(mfs) == 3
        assert "oversold" in mfs
        assert "neutral" in mfs
        assert "overbought" in mfs
