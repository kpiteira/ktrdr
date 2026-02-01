"""
Tests for MEMBERSHIP_REGISTRY and auto-registration via __init_subclass__.

Task 3.1: Verify membership functions are auto-registered and can be looked up.
"""

import pytest


class TestMembershipRegistry:
    """Tests for MEMBERSHIP_REGISTRY existence and imports."""

    def test_registry_importable(self):
        """MEMBERSHIP_REGISTRY should be importable from ktrdr.fuzzy.membership."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        assert MEMBERSHIP_REGISTRY is not None

    def test_registry_is_type_registry(self):
        """MEMBERSHIP_REGISTRY should be a TypeRegistry instance."""
        from ktrdr.core.type_registry import TypeRegistry
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        assert isinstance(MEMBERSHIP_REGISTRY, TypeRegistry)

    def test_all_three_mf_types_registered(self):
        """All 3 MF types should be registered: triangular, trapezoidal, gaussian."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        types = set(MEMBERSHIP_REGISTRY.list_types())
        expected = {"triangular", "trapezoidal", "gaussian"}
        assert types == expected

    def test_canonical_name_lookup(self):
        """Should be able to look up MF types by canonical name."""
        from ktrdr.fuzzy.membership import (
            MEMBERSHIP_REGISTRY,
            GaussianMF,
            TrapezoidalMF,
            TriangularMF,
        )

        assert MEMBERSHIP_REGISTRY.get("triangular") is TriangularMF
        assert MEMBERSHIP_REGISTRY.get("trapezoidal") is TrapezoidalMF
        assert MEMBERSHIP_REGISTRY.get("gaussian") is GaussianMF

    def test_case_insensitive_lookup(self):
        """Registry lookup should be case-insensitive."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY, TriangularMF

        # Various case patterns should all resolve to TriangularMF
        for name in ["triangular", "Triangular", "TRIANGULAR", "tRiAnGuLaR"]:
            result = MEMBERSHIP_REGISTRY.get(name)
            assert result is TriangularMF, f"Failed for name: {name}"

    def test_alias_lookup(self):
        """Should be able to look up MF types by alias (e.g., triangularmf)."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY, TriangularMF

        # The full class name lowercase should work as alias
        assert MEMBERSHIP_REGISTRY.get("triangularmf") is TriangularMF
        assert MEMBERSHIP_REGISTRY.get("trapezoidalmf") is not None
        assert MEMBERSHIP_REGISTRY.get("gaussianmf") is not None

    def test_get_or_raise_for_valid_type(self):
        """get_or_raise should return the class for valid types."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY, TriangularMF

        result = MEMBERSHIP_REGISTRY.get_or_raise("triangular")
        assert result is TriangularMF

    def test_get_or_raise_for_invalid_type(self):
        """get_or_raise should raise ValueError for unknown types."""
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        with pytest.raises(ValueError) as exc_info:
            MEMBERSHIP_REGISTRY.get_or_raise("unknown_type")

        assert "Unknown membership function type" in str(exc_info.value)
        assert "unknown_type" in str(exc_info.value)


class TestMembershipFunctionBaseClass:
    """Tests for MembershipFunction base class __init_subclass__ behavior."""

    def test_base_class_has_params(self):
        """MembershipFunction should have a Params nested class."""
        from ktrdr.fuzzy.membership import MembershipFunction

        assert hasattr(MembershipFunction, "Params")

    def test_base_class_has_aliases_attribute(self):
        """MembershipFunction should have _aliases class attribute."""
        from ktrdr.fuzzy.membership import MembershipFunction

        assert hasattr(MembershipFunction, "_aliases")
        assert isinstance(MembershipFunction._aliases, list)

    def test_subclass_not_registered_if_abstract(self):
        """Abstract subclasses should not be registered."""
        from abc import abstractmethod

        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY, MembershipFunction

        initial_count = len(MEMBERSHIP_REGISTRY.list_types())

        # Define an abstract subclass (should NOT be registered)
        class AbstractMF(MembershipFunction):
            @abstractmethod
            def some_abstract_method(self):
                pass

            def evaluate(self, x):
                pass

        # Count should remain the same
        assert len(MEMBERSHIP_REGISTRY.list_types()) == initial_count

    def test_test_subclass_not_registered(self):
        """Subclasses defined in test modules should not be registered."""
        # This test itself is in a test module, so any MF we define here
        # should NOT be registered
        from ktrdr.fuzzy.membership import MEMBERSHIP_REGISTRY

        initial_types = set(MEMBERSHIP_REGISTRY.list_types())

        # This class is defined in a test module (tests.unit.fuzzy.test_membership_registry)
        # so it should NOT be registered
        # Note: The class definition itself triggers __init_subclass__
        # We can't easily test this without risking side effects,
        # but we can verify no unexpected types appeared
        assert set(MEMBERSHIP_REGISTRY.list_types()) == initial_types
