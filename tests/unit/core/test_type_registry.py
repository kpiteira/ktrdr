"""Unit tests for TypeRegistry generic class.

Tests cover:
- Registration and lookup
- Case-insensitive lookup
- Aliases
- Collision detection
- Error messages with available types
- list_types excludes aliases
- get_params_schema
"""

import pytest
from pydantic import BaseModel, Field


class TestTypeRegistry:
    """Tests for TypeRegistry generic class."""

    def test_register_and_lookup(self) -> None:
        """Test that registered types can be looked up."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class MyType:
            pass

        registry.register(MyType, "mytype")

        assert registry.get("mytype") is MyType

    def test_case_insensitive_lookup(self) -> None:
        """Test that lookup is case-insensitive."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class MyType:
            pass

        registry.register(MyType, "mytype")

        # All case variants should resolve to the same type
        assert registry.get("mytype") is MyType
        assert registry.get("MYTYPE") is MyType
        assert registry.get("MyType") is MyType
        assert registry.get("MYTYPE") is MyType

    def test_aliases_work(self) -> None:
        """Test that aliases resolve to the same type as canonical name."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class RSIIndicator:
            pass

        registry.register(
            RSIIndicator, "rsi", aliases=["rsiindicator", "relative_strength"]
        )

        # All should resolve to the same type
        assert registry.get("rsi") is RSIIndicator
        assert registry.get("rsiindicator") is RSIIndicator
        assert registry.get("relative_strength") is RSIIndicator
        # Case variants of aliases should also work
        assert registry.get("RSIIndicator") is RSIIndicator
        assert registry.get("RELATIVE_STRENGTH") is RSIIndicator

    def test_collision_raises(self) -> None:
        """Test that registering a name that's already taken raises ValueError."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("indicator")

        class TypeA:
            pass

        class TypeB:
            pass

        registry.register(TypeA, "mytype")

        with pytest.raises(ValueError, match="Cannot register TypeB as 'mytype'"):
            registry.register(TypeB, "mytype")

    def test_collision_on_alias_raises(self) -> None:
        """Test that alias collision also raises ValueError."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("indicator")

        class TypeA:
            pass

        class TypeB:
            pass

        registry.register(TypeA, "typea", aliases=["shared"])

        with pytest.raises(ValueError, match="Cannot register TypeB as 'shared'"):
            registry.register(TypeB, "typeb", aliases=["shared"])

    def test_get_or_raise_lists_available(self) -> None:
        """Test that get_or_raise error message includes available types."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("indicator")

        class RSI:
            pass

        class MACD:
            pass

        registry.register(RSI, "rsi")
        registry.register(MACD, "macd")

        with pytest.raises(ValueError) as exc_info:
            registry.get_or_raise("unknown")

        error_msg = str(exc_info.value)
        assert "Unknown indicator type 'unknown'" in error_msg
        assert "macd" in error_msg
        assert "rsi" in error_msg

    def test_list_types_excludes_aliases(self) -> None:
        """Test that list_types returns only canonical names, not aliases."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class TypeA:
            pass

        class TypeB:
            pass

        registry.register(TypeA, "alpha", aliases=["a", "first"])
        registry.register(TypeB, "beta", aliases=["b", "second"])

        types = registry.list_types()

        assert types == ["alpha", "beta"]
        assert "a" not in types
        assert "first" not in types
        assert "b" not in types
        assert "second" not in types

    def test_get_params_schema_returns_params_class(self) -> None:
        """Test that get_params_schema returns the Params nested class."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class MyIndicator:
            class Params(BaseModel):
                period: int = Field(default=14, ge=2, le=100)
                source: str = Field(default="close")

        registry.register(MyIndicator, "myind")

        schema = registry.get_params_schema("myind")

        assert schema is MyIndicator.Params
        assert "period" in schema.model_fields
        assert "source" in schema.model_fields

    def test_get_params_schema_returns_none_if_no_params(self) -> None:
        """Test that get_params_schema returns None if class has no Params."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class NoParamsType:
            pass

        registry.register(NoParamsType, "noparams")

        assert registry.get_params_schema("noparams") is None

    def test_get_params_schema_unknown_type_returns_none(self) -> None:
        """Test that get_params_schema returns None for unknown types."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        assert registry.get_params_schema("nonexistent") is None

    def test_contains_operator(self) -> None:
        """Test the 'in' operator works for checking type existence."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        class MyType:
            pass

        registry.register(MyType, "mytype", aliases=["mt"])

        assert "mytype" in registry
        assert "mt" in registry
        assert "MYTYPE" in registry  # case-insensitive
        assert "unknown" not in registry

    def test_get_returns_none_for_unknown(self) -> None:
        """Test that get returns None for unknown types."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("test")

        assert registry.get("nonexistent") is None

    def test_registry_name_used_in_error_messages(self) -> None:
        """Test that the registry name appears in error messages."""
        from ktrdr.core.type_registry import TypeRegistry

        registry: TypeRegistry[object] = TypeRegistry("membership_function")

        with pytest.raises(ValueError, match="Unknown membership_function type"):
            registry.get_or_raise("unknown")
