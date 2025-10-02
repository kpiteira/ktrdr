"""
Operation adapter interface for unified CLI async operations.

This module defines the contract between the generic AsyncOperationExecutor
and domain-specific operation logic. Adapters are lightweight translators
that provide operation-specific knowledge while the executor handles all
infrastructure concerns.
"""

from abc import ABC, abstractmethod
from typing import Any

from httpx import AsyncClient
from rich.console import Console


class OperationAdapter(ABC):
    """
    Abstract interface for operation-specific logic.

    Separates generic async operation infrastructure from domain knowledge.
    Adapters are lightweight translators (~50-100 lines each) that tell the
    executor:
    - Which endpoint to call to start the operation
    - What payload to send
    - How to extract the operation_id from the response
    - How to display final results

    Example:
        class MyOperationAdapter(OperationAdapter):
            def __init__(self, param1: str, param2: int):
                self.param1 = param1
                self.param2 = param2

            def get_start_endpoint(self) -> str:
                return "/api/v1/my-operation/start"

            def get_start_payload(self) -> dict[str, Any]:
                return {"param1": self.param1, "param2": self.param2}

            def parse_start_response(self, response: dict) -> str:
                return response["data"]["operation_id"]

            async def display_results(
                self,
                final_status: dict,
                console: Console,
                http_client: AsyncClient,
            ) -> None:
                console.print(f"[green]Operation completed: {final_status}[/green]")
    """

    @abstractmethod
    def get_start_endpoint(self) -> str:
        """
        Return HTTP endpoint to start this operation.

        This should be the full path relative to the API base URL,
        e.g., "/api/v1/trainings/start" or "/api/v1/data/load"

        Returns:
            Endpoint path string
        """
        pass

    @abstractmethod
    def get_start_payload(self) -> dict[str, Any]:
        """
        Return JSON payload for the start request.

        The adapter constructs this from parameters passed to its constructor.
        It should match what the backend API expects for this operation.

        Returns:
            Dictionary containing the request payload
        """
        pass

    @abstractmethod
    def parse_start_response(self, response: dict) -> str:
        """
        Extract operation_id from the start response.

        The executor calls this to get the operation_id that will be used
        for polling the operations API.

        Args:
            response: Full response dictionary from the start endpoint

        Returns:
            The operation_id string to use for polling

        Raises:
            KeyError: If operation_id cannot be extracted from response
        """
        pass

    @abstractmethod
    async def display_results(
        self,
        final_status: dict,
        console: Console,
        http_client: AsyncClient,
    ) -> None:
        """
        Display final results after operation completes successfully.

        This is called when the operation reaches 'completed' status.
        The adapter can:
        - Fetch additional data using the http_client
        - Format and print results using the Rich console
        - Display domain-specific metrics and summaries

        Args:
            final_status: Final operation status from /operations/{id}
            console: Rich console for formatted output
            http_client: Async HTTP client for additional requests
        """
        pass
