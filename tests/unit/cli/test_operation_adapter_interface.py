"""
Unit tests for OperationAdapter interface.

Tests verify the adapter interface contract and that concrete implementations
must provide all required methods.
"""

from typing import Any

import httpx
import pytest
from rich.console import Console

from ktrdr.cli.operation_adapters import OperationAdapter


class ConcreteAdapter(OperationAdapter):
    """Valid concrete implementation for testing."""

    def get_start_endpoint(self) -> str:
        return "/api/v1/test/start"

    def get_start_payload(self) -> dict[str, Any]:
        return {"test": "payload"}

    def parse_start_response(self, response: dict) -> str:
        return response["data"]["operation_id"]

    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: httpx.AsyncClient,
    ) -> None:
        console.print("[green]Test completed[/green]")


class IncompleteAdapter(OperationAdapter):
    """Incomplete adapter missing required methods."""

    def get_start_endpoint(self) -> str:
        return "/api/v1/incomplete/start"

    # Missing other required methods


class TestOperationAdapterInterface:
    """Test the OperationAdapter abstract interface."""

    def test_interface_has_required_methods(self):
        """Verify interface defines all required abstract methods."""
        # Check that the interface has the expected abstract methods
        abstract_methods = OperationAdapter.__abstractmethods__
        expected_methods = {
            "get_start_endpoint",
            "get_start_payload",
            "parse_start_response",
            "display_results",
        }
        assert abstract_methods == expected_methods, (
            f"Interface should define exactly these abstract methods: {expected_methods}, "
            f"but found: {abstract_methods}"
        )

    def test_cannot_instantiate_abstract_interface(self):
        """Verify that the abstract interface cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            OperationAdapter()  # type: ignore

    def test_cannot_instantiate_incomplete_implementation(self):
        """Verify that incomplete implementations cannot be instantiated."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IncompleteAdapter()  # type: ignore

    def test_can_instantiate_complete_implementation(self):
        """Verify that complete implementations can be instantiated."""
        adapter = ConcreteAdapter()
        assert adapter is not None
        assert isinstance(adapter, OperationAdapter)

    def test_get_start_endpoint_returns_string(self):
        """Verify get_start_endpoint returns a string."""
        adapter = ConcreteAdapter()
        endpoint = adapter.get_start_endpoint()
        assert isinstance(endpoint, str)
        assert endpoint.startswith("/")

    def test_get_start_payload_returns_dict(self):
        """Verify get_start_payload returns a dictionary."""
        adapter = ConcreteAdapter()
        payload = adapter.get_start_payload()
        assert isinstance(payload, dict)

    def test_parse_start_response_returns_string(self):
        """Verify parse_start_response returns a string."""
        adapter = ConcreteAdapter()
        response = {"data": {"operation_id": "test-op-123"}}
        operation_id = adapter.parse_start_response(response)
        assert isinstance(operation_id, str)
        assert operation_id == "test-op-123"

    @pytest.mark.asyncio
    async def test_display_results_is_async(self):
        """Verify display_results is an async method."""
        adapter = ConcreteAdapter()
        console = Console()

        # Mock AsyncClient to avoid actual HTTP connections
        async with httpx.AsyncClient() as client:
            # Should be able to await this
            result = await adapter.display_results(
                final_status={"status": "completed"},
                console=console,
                http_client=client,
            )
            # display_results returns None
            assert result is None

    def test_interface_method_signatures(self):
        """Verify method signatures match expected types."""
        import inspect

        # Check get_start_endpoint signature
        sig = inspect.signature(OperationAdapter.get_start_endpoint)
        assert sig.return_annotation is str

        # Check get_start_payload signature
        sig = inspect.signature(OperationAdapter.get_start_payload)
        assert sig.return_annotation == dict[str, Any]

        # Check parse_start_response signature
        sig = inspect.signature(OperationAdapter.parse_start_response)
        params = list(sig.parameters.values())
        assert len(params) == 2  # self and response
        assert params[1].annotation is dict
        assert sig.return_annotation is str

        # Check display_results signature
        sig = inspect.signature(OperationAdapter.display_results)
        params = list(sig.parameters.values())
        assert len(params) == 4  # self, final_status, console, http_client
        assert params[1].annotation is dict
        assert params[2].annotation == Console
        assert params[3].annotation == httpx.AsyncClient
        assert sig.return_annotation is None

    def test_adapter_extensibility(self):
        """Verify adapters can add custom attributes and methods."""

        class ExtendedAdapter(OperationAdapter):
            """Adapter with additional functionality."""

            def __init__(self, custom_param: str):
                self.custom_param = custom_param
                self.call_count = 0

            def get_start_endpoint(self) -> str:
                return f"/api/v1/{self.custom_param}/start"

            def get_start_payload(self) -> dict[str, Any]:
                self.call_count += 1
                return {"param": self.custom_param, "count": self.call_count}

            def parse_start_response(self, response: dict) -> str:
                return response["data"]["operation_id"]

            async def display_results(
                self,
                final_status: dict,
                console: Console,
                http_client: httpx.AsyncClient,
            ) -> None:
                console.print(f"[green]{self.custom_param} completed[/green]")

            def custom_method(self) -> str:
                """Custom method specific to this adapter."""
                return f"Custom: {self.custom_param}"

        # Should work fine
        adapter = ExtendedAdapter("custom")
        assert adapter.custom_param == "custom"
        assert adapter.custom_method() == "Custom: custom"

        payload = adapter.get_start_payload()
        assert payload["param"] == "custom"
        assert payload["count"] == 1
