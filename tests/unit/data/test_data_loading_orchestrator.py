"""
Unit tests for DataLoadingOrchestrator component.

Tests the data loading orchestration logic extracted from DataManager,
focusing on the architecture and integration patterns.
"""

from inspect import signature
from unittest.mock import Mock

from ktrdr.data.data_loading_orchestrator import DataLoadingOrchestrator


class TestDataLoadingOrchestrator:
    """Test the DataLoadingOrchestrator component."""

    def test_initialization(self):
        """Test proper initialization with DataManager reference."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        assert orchestrator.data_manager is mock_data_manager
        assert hasattr(orchestrator, "load_with_fallback")

    def test_load_with_fallback_method_exists(self):
        """Test that load_with_fallback method is properly exposed."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Method should exist and be callable
        assert hasattr(orchestrator, "load_with_fallback")
        assert callable(orchestrator.load_with_fallback)

    def test_dependency_injection_pattern(self):
        """Test that orchestrator properly stores DataManager reference."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should store reference for dependency injection
        assert orchestrator.data_manager is mock_data_manager
        assert hasattr(orchestrator, "data_manager")


class TestDataLoadingOrchestratorArchitecture:
    """Test architectural aspects of the DataLoadingOrchestrator."""

    def test_loose_coupling_pattern(self):
        """Test that orchestrator uses loose coupling via dependency injection."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should store reference without tight coupling
        assert orchestrator.data_manager is mock_data_manager
        assert hasattr(orchestrator, "data_manager")

        # Should not inherit from DataManager or have circular references
        assert not isinstance(orchestrator, type(mock_data_manager))

    def test_orchestrator_as_service_component(self):
        """Test that orchestrator acts as a proper service component."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should have clear service interface
        assert hasattr(orchestrator, "load_with_fallback")

        # Should be a standalone component
        assert orchestrator.__class__.__name__ == "DataLoadingOrchestrator"

    def test_preserved_method_signatures(self):
        """Test that method signatures match expected interface."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Get method signature
        method_sig = signature(orchestrator.load_with_fallback)

        # Should have expected parameters
        param_names = list(method_sig.parameters.keys())
        expected_params = [
            "symbol",
            "timeframe",
            "start_date",
            "end_date",
            "mode",
            "cancellation_token",
            "progress_manager",
        ]

        for param in expected_params:
            assert param in param_names, f"Missing parameter: {param}"

        # Check parameter defaults
        assert method_sig.parameters["start_date"].default is None
        assert method_sig.parameters["end_date"].default is None
        assert method_sig.parameters["mode"].default == "tail"
        assert method_sig.parameters["cancellation_token"].default is None
        assert method_sig.parameters["progress_manager"].default is None

    def test_component_interface(self):
        """Test that the component has the expected interface."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should have constructor that takes data_manager
        assert orchestrator.data_manager is mock_data_manager

        # Should have main orchestration method
        assert hasattr(orchestrator, "load_with_fallback")
        assert callable(orchestrator.load_with_fallback)

    def test_functionality_preservation(self):
        """Test that orchestrator preserves the expected functionality interface."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # The load_with_fallback method should exist and be the main entry point
        method = orchestrator.load_with_fallback
        assert method is not None

        # Method signature should support all the expected parameters
        sig = signature(method)
        params = sig.parameters

        # Test required parameters
        assert "symbol" in params
        assert "timeframe" in params

        # Test optional parameters with defaults
        assert "mode" in params
        assert params["mode"].default == "tail"

        # Test all expected optional parameters exist
        optional_params = [
            "start_date",
            "end_date",
            "cancellation_token",
            "progress_manager",
        ]
        for param in optional_params:
            assert param in params
            assert params[param].default is None


class TestDataLoadingOrchestratorIntegration:
    """Test integration aspects without complex async mocking."""

    def test_datamanager_reference_integrity(self):
        """Test that DataManager reference is maintained correctly."""
        mock_data_manager = Mock()
        mock_data_manager.some_attribute = "test_value"

        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should maintain reference integrity
        assert orchestrator.data_manager is mock_data_manager
        assert orchestrator.data_manager.some_attribute == "test_value"

    def test_orchestrator_isolation(self):
        """Test that orchestrator doesn't modify the DataManager."""
        mock_data_manager = Mock()
        original_attributes = set(dir(mock_data_manager))

        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # DataManager should not be modified by orchestrator creation
        current_attributes = set(dir(mock_data_manager))
        assert original_attributes == current_attributes

        # Orchestrator should be separate
        assert orchestrator is not mock_data_manager

    def test_component_separation(self):
        """Test that orchestrator is properly separated from DataManager."""
        mock_data_manager = Mock()
        orchestrator = DataLoadingOrchestrator(mock_data_manager)

        # Should be separate objects
        assert id(orchestrator) != id(mock_data_manager)

        # Should have different classes
        assert not isinstance(orchestrator, type(mock_data_manager))

        # Orchestrator should have its own specific attributes
        orchestrator_attrs = set(dir(orchestrator))
        assert "load_with_fallback" in orchestrator_attrs
        assert "data_manager" in orchestrator_attrs
