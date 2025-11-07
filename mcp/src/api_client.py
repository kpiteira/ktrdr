"""
Unified API Client Facade

Provides both domain-specific access (client.operations.list_operations())
and backward-compatible monolithic access (client.list_operations())
"""

from typing import Any, Optional

import structlog

from .clients import (
    BacktestingAPIClient,
    DataAPIClient,
    IndicatorsAPIClient,
    KTRDRAPIError,
    OperationsAPIClient,
    StrategiesAPIClient,
    SystemAPIClient,
    TrainingAPIClient,
)
from .config import API_TIMEOUT, KTRDR_API_URL

logger = structlog.get_logger()


class KTRDRAPIClient:
    """
    Unified facade combining domain-specific API clients.

    Usage:
        # New domain-specific access (recommended)
        async with KTRDRAPIClient() as client:
            result = await client.operations.list_operations(...)
            data = await client.data.get_cached_data(...)
            training = await client.training.start_neural_training(...)

        # Old monolithic access (backward compatibility)
        async with KTRDRAPIClient() as client:
            result = await client.list_operations(...)  # Delegates to client.operations
    """

    def __init__(self, base_url: str = KTRDR_API_URL, timeout: float = API_TIMEOUT):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        # Domain-specific clients (new pattern)
        self.data = DataAPIClient(base_url, timeout)
        self.training = TrainingAPIClient(base_url, timeout)
        self.backtesting = BacktestingAPIClient(base_url, timeout)
        self.operations = OperationsAPIClient(base_url, timeout)
        self.system = SystemAPIClient(base_url, timeout)
        self.indicators = IndicatorsAPIClient(base_url, timeout)
        self.strategies = StrategiesAPIClient(base_url, timeout)

        logger.info("Unified API client initialized", base_url=self.base_url)

    async def __aenter__(self):
        """Enter async context - initialize all domain clients"""
        await self.data.__aenter__()
        await self.training.__aenter__()
        await self.backtesting.__aenter__()
        await self.operations.__aenter__()
        await self.system.__aenter__()
        await self.indicators.__aenter__()
        await self.strategies.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - cleanup all domain clients"""
        await self.data.__aexit__(exc_type, exc_val, exc_tb)
        await self.training.__aexit__(exc_type, exc_val, exc_tb)
        await self.backtesting.__aexit__(exc_type, exc_val, exc_tb)
        await self.operations.__aexit__(exc_type, exc_val, exc_tb)
        await self.system.__aexit__(exc_type, exc_val, exc_tb)
        await self.indicators.__aexit__(exc_type, exc_val, exc_tb)
        await self.strategies.__aexit__(exc_type, exc_val, exc_tb)

    # ====================
    # Operations Methods (backward compatibility)
    # ====================

    async def list_operations(self, **kwargs) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.list_operations(**kwargs)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.get_operation_status(operation_id)

    async def cancel_operation(
        self, operation_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.cancel_operation(operation_id, reason)

    async def get_operation_results(self, operation_id: str) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.get_operation_results(operation_id)

    # ====================
    # Data Methods (backward compatibility)
    # ====================

    async def get_cached_data(self, **kwargs) -> dict[str, Any]:
        """Delegate to data client (backward compat)"""
        return await self.data.get_cached_data(**kwargs)

    async def load_data_operation(self, **kwargs) -> dict[str, Any]:
        """Delegate to data client (backward compat)"""
        return await self.data.load_data_operation(**kwargs)

    async def get_data_info(self, symbol: str) -> dict[str, Any]:
        """Delegate to data client (backward compat)"""
        return await self.data.get_data_info(symbol)

    async def get_symbols(self) -> list[dict[str, Any]]:
        """Delegate to data client (backward compat)"""
        return await self.data.get_symbols()

    # ====================
    # Indicators Methods (backward compatibility)
    # ====================

    async def get_indicators(self) -> list[dict[str, Any]]:
        """Delegate to indicators client (backward compat)"""
        return await self.indicators.list_indicators()

    # ====================
    # Strategies Methods (backward compatibility)
    # ====================

    async def get_strategies(self) -> dict[str, Any]:
        """Delegate to strategies client (backward compat)"""
        return await self.strategies.list_strategies()

    # ====================
    # Training Methods (backward compatibility)
    # ====================

    async def start_neural_training(self, **kwargs) -> dict[str, Any]:
        """Delegate to training client (backward compat)"""
        return await self.training.start_neural_training(**kwargs)

    async def get_training_status(self, task_id: str) -> dict[str, Any]:
        """Delegate to training client (backward compat)"""
        return await self.training.get_training_status(task_id)

    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Delegate to training client (backward compat)"""
        return await self.training.get_model_performance(task_id)

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """Delegate to training client (backward compat)"""
        return await self.training.list_trained_models()

    # ====================
    # System Methods (backward compatibility)
    # ====================

    async def health_check(self) -> dict[str, Any]:
        """Check backend API health status"""
        return await self.system.health_check()


# Singleton instance for easy access
_api_client: Optional[KTRDRAPIClient] = None


def get_api_client() -> KTRDRAPIClient:
    """Get singleton API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = KTRDRAPIClient()
    return _api_client


# Export for backward compatibility
__all__ = ["KTRDRAPIClient", "KTRDRAPIError", "get_api_client"]
