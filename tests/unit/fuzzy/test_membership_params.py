"""
Tests for membership function Params validators.

Task 3.2: Verify each MF has Params with proper validation.
"""

import pytest
from pydantic import ValidationError

from ktrdr.errors import ConfigurationError
from ktrdr.fuzzy.membership import (
    MEMBERSHIP_REGISTRY,
    GaussianMF,
    MembershipFunction,
    TrapezoidalMF,
    TriangularMF,
)


class TestMembershipFunctionParams:
    """Tests for base class Params and _init_from_params."""

    def test_base_class_has_init_from_params(self):
        """MembershipFunction should have abstract _init_from_params method."""
        # Check that _init_from_params exists and is callable
        assert hasattr(MembershipFunction, "_init_from_params")
        method = MembershipFunction._init_from_params
        assert callable(method)


class TestTriangularMFParams:
    """Tests for TriangularMF Params validation."""

    def test_has_params_class(self):
        """TriangularMF should have a Params nested class."""
        assert hasattr(TriangularMF, "Params")
        # Should be a subclass of MembershipFunction.Params
        assert issubclass(TriangularMF.Params, MembershipFunction.Params)

    def test_params_validates_count(self):
        """Params should reject wrong parameter count."""
        with pytest.raises(ValidationError):
            TriangularMF.Params(parameters=[0, 50])  # Too few

        with pytest.raises(ValidationError):
            TriangularMF.Params(parameters=[0, 25, 75, 100])  # Too many

    def test_params_validates_ordering(self):
        """Params should reject invalid parameter ordering."""
        with pytest.raises(ValidationError):
            TriangularMF.Params(parameters=[50, 0, 100])  # a > b

        with pytest.raises(ValidationError):
            TriangularMF.Params(parameters=[0, 100, 50])  # b > c

    def test_params_accepts_valid(self):
        """Params should accept valid parameters."""
        params = TriangularMF.Params(parameters=[0, 50, 100])
        assert params.parameters == [0, 50, 100]

        # Edge cases
        params = TriangularMF.Params(parameters=[50, 50, 50])  # Singleton
        assert params.parameters == [50, 50, 50]

    def test_init_raises_configuration_error(self):
        """TriangularMF.__init__ should raise ConfigurationError for invalid params."""
        with pytest.raises(ConfigurationError) as exc_info:
            TriangularMF([0, 50])  # Wrong count

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_registry_params_schema(self):
        """Registry should return Params schema for triangular."""
        params_class = MEMBERSHIP_REGISTRY.get_params_schema("triangular")
        assert params_class is TriangularMF.Params


class TestTrapezoidalMFParams:
    """Tests for TrapezoidalMF Params validation."""

    def test_has_params_class(self):
        """TrapezoidalMF should have a Params nested class."""
        assert hasattr(TrapezoidalMF, "Params")
        assert issubclass(TrapezoidalMF.Params, MembershipFunction.Params)

    def test_params_validates_count(self):
        """Params should reject wrong parameter count."""
        with pytest.raises(ValidationError):
            TrapezoidalMF.Params(parameters=[0, 25, 75])  # Too few

        with pytest.raises(ValidationError):
            TrapezoidalMF.Params(parameters=[0, 25, 50, 75, 100])  # Too many

    def test_params_validates_ordering(self):
        """Params should reject invalid parameter ordering."""
        with pytest.raises(ValidationError):
            TrapezoidalMF.Params(parameters=[100, 25, 75, 0])  # a > b

        with pytest.raises(ValidationError):
            TrapezoidalMF.Params(parameters=[0, 75, 25, 100])  # b > c

        with pytest.raises(ValidationError):
            TrapezoidalMF.Params(parameters=[0, 25, 100, 75])  # c > d

    def test_params_accepts_valid(self):
        """Params should accept valid parameters."""
        params = TrapezoidalMF.Params(parameters=[0, 25, 75, 100])
        assert params.parameters == [0, 25, 75, 100]

    def test_init_raises_configuration_error(self):
        """TrapezoidalMF.__init__ should raise ConfigurationError for invalid params."""
        with pytest.raises(ConfigurationError) as exc_info:
            TrapezoidalMF([0, 25, 75])  # Wrong count

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_registry_params_schema(self):
        """Registry should return Params schema for trapezoidal."""
        params_class = MEMBERSHIP_REGISTRY.get_params_schema("trapezoidal")
        assert params_class is TrapezoidalMF.Params


class TestGaussianMFParams:
    """Tests for GaussianMF Params validation."""

    def test_has_params_class(self):
        """GaussianMF should have a Params nested class."""
        assert hasattr(GaussianMF, "Params")
        assert issubclass(GaussianMF.Params, MembershipFunction.Params)

    def test_params_validates_count(self):
        """Params should reject wrong parameter count."""
        with pytest.raises(ValidationError):
            GaussianMF.Params(parameters=[50])  # Too few

        with pytest.raises(ValidationError):
            GaussianMF.Params(parameters=[50, 10, 5])  # Too many

    def test_params_validates_sigma(self):
        """Params should reject non-positive sigma."""
        with pytest.raises(ValidationError):
            GaussianMF.Params(parameters=[50, 0])  # sigma = 0

        with pytest.raises(ValidationError):
            GaussianMF.Params(parameters=[50, -5])  # sigma < 0

    def test_params_accepts_valid(self):
        """Params should accept valid parameters."""
        params = GaussianMF.Params(parameters=[50, 10])
        assert params.parameters == [50, 10]

    def test_init_raises_configuration_error(self):
        """GaussianMF.__init__ should raise ConfigurationError for invalid params."""
        with pytest.raises(ConfigurationError) as exc_info:
            GaussianMF([50])  # Wrong count

        assert exc_info.value.error_code == "MF-InvalidParameters"

    def test_registry_params_schema(self):
        """Registry should return Params schema for gaussian."""
        params_class = MEMBERSHIP_REGISTRY.get_params_schema("gaussian")
        assert params_class is GaussianMF.Params


class TestMFParamsIntegration:
    """Integration tests for MF Params with registry."""

    def test_all_mfs_have_params(self):
        """All registered MFs should have Params classes."""
        for type_name in MEMBERSHIP_REGISTRY.list_types():
            mf_class = MEMBERSHIP_REGISTRY.get(type_name)
            assert hasattr(mf_class, "Params"), f"{type_name} missing Params"
            assert issubclass(mf_class.Params, MembershipFunction.Params)

    def test_registry_instantiation_with_validation(self):
        """Should be able to instantiate MFs via registry with validation."""
        mf_class = MEMBERSHIP_REGISTRY.get_or_raise("triangular")
        mf = mf_class([0, 50, 100])
        assert mf.a == 0
        assert mf.b == 50
        assert mf.c == 100

        # Invalid params should raise ConfigurationError
        with pytest.raises(ConfigurationError):
            mf_class([100, 50, 0])  # Invalid ordering
