"""Generic type registry with case-insensitive lookup and auto-registration support.

The TypeRegistry provides a unified pattern for registering and looking up types
by name. It supports:
- Case-insensitive lookup
- Aliases (multiple names resolving to the same type)
- Collision detection
- Params schema introspection (for Pydantic-based parameter validation)

Example usage:
    >>> from ktrdr.core.type_registry import TypeRegistry
    >>> registry = TypeRegistry[BaseIndicator]("indicator")
    >>> registry.register(RSIIndicator, "rsi", aliases=["rsiindicator"])
    >>> registry.get("RSI")  # Returns RSIIndicator (case-insensitive)
"""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class TypeRegistry(Generic[T]):
    """Generic registry for types with case-insensitive lookup.

    Attributes:
        _name: Registry name used in error messages (e.g., "indicator", "membership_function")
        _types: Maps lowercase names (both canonical and aliases) to type classes
        _canonical: Set of canonical names (excludes aliases)
    """

    def __init__(self, name: str) -> None:
        """Initialize the registry.

        Args:
            name: Name for this registry, used in error messages
        """
        self._name = name
        self._types: dict[str, type[T]] = {}
        self._canonical: set[str] = set()

    def register(
        self, cls: type[T], canonical: str, aliases: list[str] | None = None
    ) -> None:
        """Register a type with a canonical name and optional aliases.

        All names are stored in lowercase for case-insensitive lookup.

        Args:
            cls: The class to register
            canonical: The primary name for this type
            aliases: Optional alternative names that also resolve to this type

        Raises:
            ValueError: If any name (canonical or alias) is already registered
        """
        all_names = [canonical] + (aliases or [])
        # Check for collisions before registering anything
        for name in all_names:
            key = name.lower()
            if key in self._types:
                existing = self._types[key]
                raise ValueError(
                    f"Cannot register {cls.__name__} as '{name}': "
                    f"already registered to {existing.__name__}"
                )

        # Register canonical name
        canonical_key = canonical.lower()
        self._types[canonical_key] = cls
        self._canonical.add(canonical_key)

        # Register aliases
        for alias in aliases or []:
            self._types[alias.lower()] = cls

    def get(self, name: str) -> type[T] | None:
        """Look up a type by name (case-insensitive).

        Args:
            name: The type name to look up

        Returns:
            The registered type class, or None if not found
        """
        return self._types.get(name.lower())

    def get_or_raise(self, name: str) -> type[T]:
        """Look up a type by name, raising if not found.

        Args:
            name: The type name to look up

        Returns:
            The registered type class

        Raises:
            ValueError: If the type is not registered, with available types listed
        """
        cls = self.get(name)
        if cls is None:
            available = sorted(self._canonical)
            raise ValueError(
                f"Unknown {self._name} type '{name}'. Available: {available}"
            )
        return cls

    def list_types(self) -> list[str]:
        """List all registered canonical type names.

        Returns:
            Sorted list of canonical names (excludes aliases)
        """
        return sorted(self._canonical)

    def get_params_schema(self, name: str) -> type[BaseModel] | None:
        """Get the Params schema for a type.

        Args:
            name: The type name to look up

        Returns:
            The Params class (a Pydantic BaseModel subclass) if the type has one,
            None otherwise
        """
        cls = self.get(name)
        if cls is None:
            return None
        return getattr(cls, "Params", None)

    def __contains__(self, name: str) -> bool:
        """Check if a type name is registered (case-insensitive).

        Args:
            name: The type name to check

        Returns:
            True if the name (or a case variant) is registered
        """
        return self.get(name) is not None
