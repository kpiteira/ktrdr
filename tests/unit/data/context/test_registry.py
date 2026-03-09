"""Tests for ContextDataProviderRegistry."""

import pytest

from ktrdr.data.context.base import ContextDataProvider
from ktrdr.data.context.registry import ContextDataProviderRegistry


class _StubProvider(ContextDataProvider):
    """Minimal provider for testing registry."""

    async def fetch(self, config, start_date, end_date):
        return []

    async def validate(self, config, **kwargs):
        return []

    def get_source_ids(self, config):
        return []


class _AnotherStubProvider(ContextDataProvider):
    """Another stub for testing multiple registrations."""

    async def fetch(self, config, start_date, end_date):
        return []

    async def validate(self, config, **kwargs):
        return []

    def get_source_ids(self, config):
        return []


class TestRegistryRegistration:
    """Test provider registration and retrieval."""

    def test_register_and_retrieve(self):
        """Should register a provider and retrieve it by name."""
        registry = ContextDataProviderRegistry()
        registry.register("test", _StubProvider)

        provider = registry.get("test")
        assert isinstance(provider, _StubProvider)

    def test_retrieve_unknown_raises_error(self):
        """Should raise KeyError for unknown provider name."""
        registry = ContextDataProviderRegistry()

        with pytest.raises(KeyError, match="test"):
            registry.get("test")

    def test_clear_error_message_for_unknown(self):
        """Error message should list available providers."""
        registry = ContextDataProviderRegistry()
        registry.register("fred", _StubProvider)
        registry.register("ib", _AnotherStubProvider)

        with pytest.raises(KeyError, match="fred"):
            registry.get("unknown")

    def test_register_multiple_providers(self):
        """Should handle multiple registered providers."""
        registry = ContextDataProviderRegistry()
        registry.register("fred", _StubProvider)
        registry.register("ib", _AnotherStubProvider)

        assert isinstance(registry.get("fred"), _StubProvider)
        assert isinstance(registry.get("ib"), _AnotherStubProvider)

    def test_available_providers(self):
        """Should list all registered provider names."""
        registry = ContextDataProviderRegistry()
        registry.register("fred", _StubProvider)
        registry.register("ib", _AnotherStubProvider)

        available = registry.available_providers()
        assert sorted(available) == ["fred", "ib"]

    def test_empty_registry(self):
        """Empty registry should return empty available list."""
        registry = ContextDataProviderRegistry()
        assert registry.available_providers() == []

    def test_get_returns_new_instance_each_call(self):
        """Each get() call should return a new provider instance."""
        registry = ContextDataProviderRegistry()
        registry.register("test", _StubProvider)

        provider1 = registry.get("test")
        provider2 = registry.get("test")
        assert provider1 is not provider2

    def test_overwrite_registration(self):
        """Registering same name twice should overwrite."""
        registry = ContextDataProviderRegistry()
        registry.register("test", _StubProvider)
        registry.register("test", _AnotherStubProvider)

        provider = registry.get("test")
        assert isinstance(provider, _AnotherStubProvider)
