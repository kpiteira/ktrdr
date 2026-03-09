"""Context data provider registry.

Maps provider names to their implementation classes. New providers
register here and become available to the strategy grammar's
context_data section.
"""

from .base import ContextDataProvider


class ContextDataProviderRegistry:
    """Registry of available context data providers.

    Providers register by name (e.g., "fred", "ib", "cftc_cot") and are
    instantiated on retrieval. This allows strategies to reference providers
    by name in YAML without importing specific classes.
    """

    def __init__(self) -> None:
        self._providers: dict[str, type[ContextDataProvider]] = {}

    def register(self, name: str, provider_class: type[ContextDataProvider]) -> None:
        """Register a provider class by name.

        Args:
            name: Provider name as used in strategy YAML (e.g., "fred").
            provider_class: The provider class to instantiate on get().
        """
        self._providers[name] = provider_class

    def get(self, name: str) -> ContextDataProvider:
        """Get a new provider instance by name.

        Args:
            name: Registered provider name.

        Returns:
            New instance of the registered provider class.

        Raises:
            KeyError: If no provider is registered with the given name.
                Error message includes available provider names.
        """
        if name not in self._providers:
            available = sorted(self._providers.keys())
            raise KeyError(
                f"Unknown context data provider '{name}'. "
                f"Available providers: {available}"
            )
        return self._providers[name]()

    def available_providers(self) -> list[str]:
        """List all registered provider names.

        Returns:
            Sorted list of registered provider names.
        """
        return sorted(self._providers.keys())
