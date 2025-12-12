"""
Agent context provider that fetches data from KTRDR API.

This provides the ContextProvider protocol implementation for the TriggerService,
fetching available indicators and symbols from the local API.
"""

from typing import Any

import httpx

from ktrdr import get_logger

logger = get_logger(__name__)


class AgentMCPContextProvider:
    """Context provider that fetches data from KTRDR API.

    This class implements the ContextProvider protocol expected by TriggerService,
    fetching available indicators and symbols from the API endpoints.
    """

    def __init__(self, base_url: str = "http://localhost:8000/api/v1"):
        """Initialize the context provider.

        Args:
            base_url: Base URL of the KTRDR API.
        """
        self.base_url = base_url

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        """Get list of available indicators from the API.

        Returns:
            List of indicator definitions with name, description, parameters.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/indicators/available",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("indicators", [])
                else:
                    logger.warning(f"Failed to get indicators: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching indicators: {e}")
            return []

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        """Get list of available symbols from the API.

        Returns:
            List of symbol definitions with symbol name and available timeframes.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/data/available",
                    timeout=10.0,
                )
                if response.status_code == 200:
                    data = response.json()
                    # Transform to expected format
                    symbols = []
                    for symbol_info in data.get("symbols", []):
                        symbols.append(
                            {
                                "symbol": symbol_info.get("symbol"),
                                "timeframes": symbol_info.get("timeframes", []),
                            }
                        )
                    return symbols
                else:
                    logger.warning(f"Failed to get symbols: {response.status_code}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching symbols: {e}")
            return []
