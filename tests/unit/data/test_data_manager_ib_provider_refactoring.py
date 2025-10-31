"""
Unit tests for Task 3.3: DataManager IbDataProvider Integration.

Tests that DataManager and DataManagerBuilder correctly use IbDataProvider
instead of IbDataAdapter after the refactoring.
"""

from unittest.mock import Mock, patch

from ktrdr.data.acquisition.ib_data_provider import IbDataProvider
from ktrdr.data.data_manager import DataManager
from ktrdr.data.data_manager_builder import (
    create_default_datamanager_builder,
)


class TestDataManagerUsesIbDataProvider:
    """Test that DataManager uses IbDataProvider instead of IbDataAdapter."""

    @patch("ktrdr.data.data_manager_builder.IbDataProvider")
    def test_data_manager_builder_creates_ib_data_provider(self, mock_provider_class):
        """Test that DataManagerBuilder creates IbDataProvider, not IbDataAdapter."""
        # Setup
        mock_provider_instance = Mock(spec=IbDataProvider)
        mock_provider_class.return_value = mock_provider_instance

        # Execute
        builder = create_default_datamanager_builder()
        builder.build_configuration()

        # Verify - IbDataProvider should be called
        mock_provider_class.assert_called_once()

    @patch.dict("os.environ", {"IB_HOST_SERVICE_URL": "http://test-host:5001"})
    @patch("ktrdr.data.data_manager_builder.IbDataProvider")
    def test_data_manager_uses_correct_host_service_url(self, mock_provider_class):
        """Test that DataManager passes correct host_service_url to IbDataProvider."""
        # Setup
        mock_provider_instance = Mock(spec=IbDataProvider)
        mock_provider_class.return_value = mock_provider_instance

        # Execute
        builder = create_default_datamanager_builder()
        builder.build_configuration()

        # Verify
        # IbDataProvider should be called with host_service_url parameter
        mock_provider_class.assert_called_once_with(
            host_service_url="http://test-host:5001"
        )

    @patch("ktrdr.data.data_manager_builder.IbDataProvider")
    def test_data_manager_initialization_with_ib_provider(self, mock_provider_class):
        """Test that DataManager initializes successfully with IbDataProvider."""
        # Setup
        mock_provider_instance = Mock(spec=IbDataProvider)
        mock_provider_class.return_value = mock_provider_instance

        # Execute - DataManager should initialize without errors
        manager = DataManager()

        # Verify
        assert manager.external_provider is not None
        # External provider should be the mock IbDataProvider instance
        assert manager.external_provider == mock_provider_instance

    def test_data_manager_no_ib_data_adapter_import(self):
        """Test that DataManager does not import IbDataAdapter."""
        import inspect

        from ktrdr.data import data_manager

        # Get the source code of the data_manager module
        source = inspect.getsource(data_manager)

        # Verify no imports from ib_data_adapter
        assert "from ktrdr.data.ib_data_adapter import" not in source
        assert (
            "IbDataAdapter" not in source or "# IbDataAdapter" in source
        )  # Comments OK

    def test_data_manager_builder_no_ib_data_adapter_import(self):
        """Test that DataManagerBuilder does not import IbDataAdapter."""
        import inspect

        from ktrdr.data import data_manager_builder

        # Get the source code of the data_manager_builder module
        source = inspect.getsource(data_manager_builder)

        # Verify no imports from ib_data_adapter
        assert "from ktrdr.data.ib_data_adapter import" not in source
        assert (
            "IbDataAdapter" not in source or "# IbDataAdapter" in source
        )  # Comments OK


class TestIbDataProviderInterface:
    """Test that IbDataProvider provides the expected interface for DataManager."""

    def test_ib_data_provider_has_required_methods(self):
        """Test that IbDataProvider has all methods required by DataManager."""
        provider = IbDataProvider(host_service_url="http://localhost:5001")

        # Verify required methods exist
        assert hasattr(provider, "fetch_historical_data")
        assert hasattr(provider, "validate_symbol")
        assert hasattr(provider, "get_symbol_info")
        assert hasattr(provider, "get_head_timestamp")
        assert hasattr(provider, "health_check")

        # Verify they are callable
        assert callable(provider.fetch_historical_data)
        assert callable(provider.validate_symbol)
        assert callable(provider.get_symbol_info)
        assert callable(provider.get_head_timestamp)
        assert callable(provider.health_check)

    def test_ib_data_provider_http_only_initialization(self):
        """Test that IbDataProvider only accepts host_service_url (HTTP-only)."""
        # Should work with just host_service_url
        provider = IbDataProvider(host_service_url="http://localhost:5001")
        assert provider.host_service_url == "http://localhost:5001"

        # Should not accept use_host_service parameter (that was IbDataAdapter)
        import inspect

        sig = inspect.signature(IbDataProvider.__init__)
        param_names = list(sig.parameters.keys())

        # Should NOT have these IbDataAdapter parameters
        assert "use_host_service" not in param_names
        assert "host" not in param_names
        assert "port" not in param_names
        assert "max_connections" not in param_names

        # Should only have host_service_url
        assert "host_service_url" in param_names
