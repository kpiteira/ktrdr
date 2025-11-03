"""
Unit tests for DataAcquisitionService.

Tests the basic structure and initialization of the acquisition service shell.
"""

from unittest.mock import Mock

import pytest

from ktrdr.async_infrastructure.service_orchestrator import ServiceOrchestrator
from ktrdr.data.acquisition.acquisition_service import DataAcquisitionService


class TestDataAcquisitionServiceInitialization:
    """Test suite for DataAcquisitionService initialization."""

    def test_service_inherits_from_service_orchestrator(self):
        """DataAcquisitionService should inherit from ServiceOrchestrator."""
        assert issubclass(DataAcquisitionService, ServiceOrchestrator)

    def test_service_can_be_instantiated(self):
        """DataAcquisitionService should be instantiable."""
        service = DataAcquisitionService()
        assert service is not None
        assert isinstance(service, DataAcquisitionService)
        assert isinstance(service, ServiceOrchestrator)

    def test_service_has_repository_attribute(self):
        """DataAcquisitionService should have a repository attribute."""
        service = DataAcquisitionService()
        assert hasattr(service, "repository")
        assert service.repository is not None

    def test_service_has_provider_attribute(self):
        """DataAcquisitionService should have a provider attribute."""
        service = DataAcquisitionService()
        assert hasattr(service, "provider")
        assert service.provider is not None

    def test_service_accepts_custom_repository(self):
        """DataAcquisitionService should accept custom repository via constructor."""
        mock_repository = Mock()
        service = DataAcquisitionService(repository=mock_repository)
        assert service.repository is mock_repository

    def test_service_accepts_custom_provider(self):
        """DataAcquisitionService should accept custom provider via constructor."""
        mock_provider = Mock()
        service = DataAcquisitionService(provider=mock_provider)
        assert service.provider is mock_provider

    def test_service_uses_default_repository_when_none_provided(self):
        """DataAcquisitionService should create default repository when none provided."""
        service = DataAcquisitionService()
        # Should have a repository instance (not None)
        assert service.repository is not None
        # Check it's the expected type
        from ktrdr.data.repository import DataRepository

        assert isinstance(service.repository, DataRepository)

    def test_service_uses_default_provider_when_none_provided(self):
        """DataAcquisitionService should create default provider when none provided."""
        service = DataAcquisitionService()
        # Should have a provider instance (not None)
        assert service.provider is not None
        # Check it's the expected type
        from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

        assert isinstance(service.provider, IbDataProvider)


class TestDataAcquisitionServiceOrchestrator:
    """Test suite for ServiceOrchestrator-required methods."""

    def test_get_service_name_returns_string(self):
        """_get_service_name should return a string."""
        service = DataAcquisitionService()
        service_name = service._get_service_name()
        assert isinstance(service_name, str)
        assert len(service_name) > 0

    def test_get_default_host_url_returns_string(self):
        """_get_default_host_url should return a string."""
        service = DataAcquisitionService()
        url = service._get_default_host_url()
        assert isinstance(url, str)
        assert url.startswith("http")

    def test_get_env_var_prefix_returns_string(self):
        """_get_env_var_prefix should return uppercase string."""
        service = DataAcquisitionService()
        prefix = service._get_env_var_prefix()
        assert isinstance(prefix, str)
        assert prefix.isupper()
        assert len(prefix) > 0

    def test_initialize_adapter_returns_provider(self):
        """_initialize_adapter should return a provider instance."""
        service = DataAcquisitionService()
        # The adapter should be the provider
        assert service.adapter is not None
        # Should be same as the provider
        assert service.adapter is service.provider


class TestDataAcquisitionServiceConfiguration:
    """Test suite for configuration and health checks."""

    @pytest.mark.asyncio
    async def test_health_check_returns_dict(self):
        """health_check should return a dictionary with health status."""
        service = DataAcquisitionService()
        health = await service.health_check()
        assert isinstance(health, dict)
        assert "orchestrator" in health or "service" in health

    def test_get_configuration_info_returns_dict(self):
        """get_configuration_info should return configuration dictionary."""
        service = DataAcquisitionService()
        config = service.get_configuration_info()
        assert isinstance(config, dict)
        assert "service" in config
        assert "mode" in config

    def test_service_repr_is_informative(self):
        """__repr__ should return informative string representation."""
        service = DataAcquisitionService()
        repr_str = repr(service)
        assert isinstance(repr_str, str)
        assert "DataAcquisitionService" in repr_str or "Acquisition" in repr_str.lower()


class TestDataAcquisitionServiceDependencies:
    """Test suite for service dependencies composition."""

    def test_service_composes_repository_not_inherits(self):
        """DataAcquisitionService should compose (has-a) Repository, not inherit."""
        service = DataAcquisitionService()
        # Has repository as attribute (composition)
        assert hasattr(service, "repository")
        # Does not inherit from DataRepository
        from ktrdr.data.repository import DataRepository

        assert not isinstance(service, DataRepository)

    def test_service_composes_provider_not_inherits(self):
        """DataAcquisitionService should compose (has-a) Provider, not inherit."""
        service = DataAcquisitionService()
        # Has provider as attribute (composition)
        assert hasattr(service, "provider")
        # Does not inherit from IbDataProvider
        from ktrdr.data.acquisition.ib_data_provider import IbDataProvider

        assert not isinstance(service, IbDataProvider)

    def test_repository_and_provider_are_independent(self):
        """Repository and provider should be independent components."""
        mock_repository = Mock()
        mock_provider = Mock()

        service = DataAcquisitionService(
            repository=mock_repository, provider=mock_provider
        )

        # Both should be set
        assert service.repository is mock_repository
        assert service.provider is mock_provider

        # They should be different objects
        assert service.repository is not service.provider


class TestDataAcquisitionServiceEdgeCases:
    """Test edge cases and error handling."""

    def test_service_with_none_repository_creates_default(self):
        """Passing None for repository should create default."""
        service = DataAcquisitionService(repository=None)
        assert service.repository is not None

    def test_service_with_none_provider_creates_default(self):
        """Passing None for provider should create default."""
        service = DataAcquisitionService(provider=None)
        assert service.provider is not None

    def test_multiple_instances_are_independent(self):
        """Multiple service instances should be independent."""
        service1 = DataAcquisitionService()
        service2 = DataAcquisitionService()

        # Should be different instances
        assert service1 is not service2
        assert service1.repository is not service2.repository
        assert service1.provider is not service2.provider
