# MCP Async Operations Integration - Implementation Plan

**Parent Documents**:
- [Requirements](./REQUIREMENTS.md)
- [Architecture](./ARCHITECTURE.md)

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-10-04
**Phase**: 1 - MCP Integration Layer

---

## Overview

This document breaks down the implementation of MCP async operations integration into discrete, testable tasks following the domain-specific client architecture.

**Key Architecture Components**:
- **Domain-Specific API Clients**: Separation of concerns by domain (Data, Training, Operations)
- **Base HTTP Client**: Shared functionality for all domain clients
- **MCP Tools**: Stateless pass-through layer exposing backend capabilities
- **Backend Enhancements**: Minimal changes to support MCP integration

**Scope**:
- ✅ 6 MCP tools (4 new + 2 updated)
- ✅ Domain-specific API client refactor
- ✅ 3 minor backend enhancements (~27 lines total)

**Branching Strategy**:
- **Feature Branch**: `feature/mcp-async-operations` (off `main`)
- **Merge Target**: `main`
- **After Merge**: Delete feature branch

**Migration Philosophy**: Additive changes with backward compatibility, continuous testing

**Testing Strategy**:
- ✅ **Unit tests**: Fast (<1s), mocked dependencies, high coverage (>80%)
- ✅ **Manual verification**: Backend endpoints, MCP tools in Claude Desktop
- ❌ **Integration tests**: Skip (4min runtime, 10% failure rate - not worth the overhead)
- ✅ **make quality**: Run before every commit (lint + format + typecheck)

---

## Phase 1: API Client Refactor (Domain Separation)

**Goal**: Split monolithic `KTRDRAPIClient` into domain-specific clients for scalability

### TASK-1.1: Create Base API Client

**Objective**: Extract shared HTTP logic into reusable base class

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/clients/base.py` (NEW)
- `tests/unit/mcp/test_base_client.py` (NEW)

**What It Does**:
- Manages HTTP client lifecycle (async context manager)
- Provides `_request()` method with error handling
- Handles connection pooling and timeouts
- Converts HTTP errors to `KTRDRAPIError`

**Implementation**:
```python
"""Base HTTP client for KTRDR API communication"""

from typing import Any, Optional
import httpx
import structlog

logger = structlog.get_logger()


class KTRDRAPIError(Exception):
    """Custom exception for KTRDR API errors"""
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class BaseAPIClient:
    """Shared HTTP client functionality for all domain clients"""

    def __init__(self, base_url: str, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client: Optional[httpx.AsyncClient] = None
        logger.info("API client initialized", base_url=self.base_url)

    async def __aenter__(self):
        """Async context manager entry"""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={"Content-Type": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.client:
            await self.client.aclose()

    async def _request(
        self, method: str, endpoint: str, **kwargs
    ) -> dict[str, Any]:
        """Make HTTP request with error handling"""
        if not self.client:
            raise KTRDRAPIError(
                "API client not initialized. Use async context manager."
            )

        url = f"{endpoint}" if endpoint.startswith("/") else f"/{endpoint}"

        try:
            logger.debug("API request", method=method, url=url)
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()

            data = response.json()
            logger.debug(
                "API response",
                status=response.status_code,
                data_keys=(
                    list(data.keys())
                    if isinstance(data, dict)
                    else type(data).__name__
                ),
            )
            return data

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error", status=e.response.status_code, url=url)
            try:
                error_data = e.response.json()
            except Exception:
                error_data = {"detail": e.response.text}

            raise KTRDRAPIError(
                f"HTTP {e.response.status_code}: {error_data.get('detail', 'Unknown error')}",
                status_code=e.response.status_code,
                details=error_data,
            ) from e

        except httpx.RequestError as e:
            logger.error("Request error", error=str(e), url=url)
            raise KTRDRAPIError(f"Request failed: {str(e)}") from e
```

**Acceptance Criteria**:
- [ ] Base client handles async context manager lifecycle
- [ ] `_request()` method handles GET, POST with proper params/json
- [ ] HTTP errors converted to `KTRDRAPIError` with status codes
- [ ] Network errors handled gracefully
- [ ] All unit tests pass
- [ ] Code coverage >80%

**Testing Strategy**:
- Mock httpx.AsyncClient for unit tests
- Test successful requests (GET, POST)
- Test HTTP error scenarios (404, 500, etc.)
- Test network errors (connection timeout, etc.)
- Test context manager lifecycle

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add mcp/src/clients/base.py tests/unit/mcp/test_base_client.py
git commit -m "feat(mcp): add BaseAPIClient for domain-specific client refactor"
```

---

### TASK-1.2: Create Operations API Client

**Objective**: Build operations-specific client for async operation management

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/clients/operations_client.py` (NEW)
- `tests/unit/mcp/test_operations_client.py` (NEW)

**What It Does**:
- List operations with filters
- Get operation status
- Cancel operations
- Get operation results

**Implementation**:
```python
"""Operations management API client"""

from typing import Any, Optional
from .base import BaseAPIClient


class OperationsAPIClient(BaseAPIClient):
    """API client for operations management"""

    async def list_operations(
        self,
        operation_type: Optional[str] = None,
        status: Optional[str] = None,
        active_only: bool = False,
        limit: int = 10,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List operations with filters"""
        params = {"limit": limit, "offset": offset}
        if operation_type:
            params["operation_type"] = operation_type
        if status:
            params["status"] = status
        if active_only:
            params["active_only"] = active_only

        return await self._request("GET", "/api/v1/operations", params=params)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Get detailed operation status"""
        return await self._request("GET", f"/api/v1/operations/{operation_id}")

    async def cancel_operation(
        self, operation_id: str, reason: Optional[str] = None
    ) -> dict[str, Any]:
        """Cancel a running operation"""
        payload = {"reason": reason} if reason else {}
        return await self._request(
            "POST", f"/api/v1/operations/{operation_id}/cancel", json=payload
        )

    async def get_operation_results(
        self, operation_id: str
    ) -> dict[str, Any]:
        """Get operation results (summary)"""
        return await self._request(
            "GET", f"/api/v1/operations/{operation_id}/results"
        )
```

**Acceptance Criteria**:
- [ ] All 4 methods implemented correctly
- [ ] Parameters properly serialized (query params, JSON payload)
- [ ] Returns parsed response dicts
- [ ] Inherits error handling from BaseAPIClient
- [ ] All unit tests pass
- [ ] Code coverage >80%

**Testing Strategy**:
- Mock BaseAPIClient._request() for unit tests
- Test each method with various parameter combinations
- Test filter logic in list_operations
- Test optional parameters handled correctly

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add mcp/src/clients/operations_client.py tests/unit/mcp/test_operations_client.py
git commit -m "feat(mcp): add OperationsAPIClient for operation management"
```

---

### TASK-1.3: Create Data API Client

**Objective**: Extract data-specific methods from monolithic client

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/clients/data_client.py` (NEW)
- `tests/unit/mcp/test_data_client.py` (NEW)

**What It Does**:
- Get cached market data (synchronous)
- Trigger data loading (async operation)
- Get data info

**Implementation**:
```python
"""Data API client"""

from typing import Any, Optional
from .base import BaseAPIClient


class DataAPIClient(BaseAPIClient):
    """API client for data operations"""

    async def get_cached_data(
        self,
        symbol: str,
        timeframe: str = "1h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        trading_hours_only: bool = False,
        include_extended: bool = False,
        limit: Optional[int] = None,
    ) -> dict[str, Any]:
        """Get cached OHLCV data (synchronous, local only)"""
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        if trading_hours_only:
            params["trading_hours_only"] = trading_hours_only
        if include_extended:
            params["include_extended"] = include_extended

        response = await self._request(
            "GET", f"/api/v1/data/{symbol}/{timeframe}", params=params
        )

        # Apply client-side limiting for response size
        if limit and "data" in response and "dates" in response["data"]:
            data = response["data"]
            if len(data["dates"]) > limit:
                data["dates"] = data["dates"][-limit:]
                data["ohlcv"] = data["ohlcv"][-limit:] if data["ohlcv"] else []
                if data.get("points"):
                    data["points"] = data["points"][-limit:]
                if "metadata" in data:
                    data["metadata"]["points"] = len(data["dates"])
                    data["metadata"]["limited_by_client"] = True

        return response

    async def load_data_operation(
        self,
        symbol: str,
        timeframe: str = "1h",
        mode: str = "local",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Trigger data loading operation (async, returns operation_id)"""
        payload = {"symbol": symbol, "timeframe": timeframe, "mode": mode}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        return await self._request("POST", "/api/v1/data/load", json=payload)

    async def get_data_info(self, symbol: str) -> dict[str, Any]:
        """Get data information for a symbol"""
        return await self._request("GET", f"/api/v1/data/info/{symbol}")
```

**Acceptance Criteria**:
- [ ] get_cached_data() handles client-side limiting correctly
- [ ] load_data_operation() returns operation_id
- [ ] All methods properly serialize parameters
- [ ] All unit tests pass
- [ ] Code coverage >80%

**Testing Strategy**:
- Test get_cached_data with and without limit
- Test load_data_operation with various modes
- Test parameter serialization

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add mcp/src/clients/data_client.py tests/unit/mcp/test_data_client.py
git commit -m "feat(mcp): add DataAPIClient for data operations"
```

---

### TASK-1.4: Create Training API Client

**Objective**: Extract training-specific methods from monolithic client

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/clients/training_client.py` (NEW)
- `tests/unit/mcp/test_training_client.py` (NEW)

**What It Does**:
- Start neural network training
- Get training status
- Get model performance
- Manage trained models

**Implementation**:
```python
"""Training API client"""

from typing import Any, Optional
from .base import BaseAPIClient


class TrainingAPIClient(BaseAPIClient):
    """API client for training operations"""

    async def start_neural_training(
        self,
        symbols: list[str],
        timeframe: str,
        config: dict[str, Any],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Start neural network training (async, returns operation_id)"""
        payload = {"symbols": symbols, "timeframe": timeframe, "config": config}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if task_id:
            payload["task_id"] = task_id

        return await self._request("POST", "/api/v1/trainings/start", json=payload)

    async def get_training_status(self, task_id: str) -> dict[str, Any]:
        """Get neural network training status"""
        return await self._request("GET", f"/api/v1/trainings/{task_id}")

    async def get_model_performance(self, task_id: str) -> dict[str, Any]:
        """Get trained model performance metrics"""
        return await self._request(
            "GET", f"/api/v1/trainings/{task_id}/performance"
        )

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """List all trained models"""
        response = await self._request("GET", "/api/v1/models")
        return response.get("models", [])
```

**Acceptance Criteria**:
- [ ] start_neural_training() returns operation_id
- [ ] All methods properly serialize complex payloads
- [ ] List methods handle response unwrapping
- [ ] All unit tests pass
- [ ] Code coverage >80%

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add mcp/src/clients/training_client.py tests/unit/mcp/test_training_client.py
git commit -m "feat(mcp): add TrainingAPIClient for training operations"
```

---

### TASK-1.5: Create Unified Facade Client

**Objective**: Provide backward-compatible facade combining all domain clients

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/clients/__init__.py` (NEW)
- `mcp/src/api_client.py` (UPDATE - make facade)
- `tests/unit/mcp/test_facade_client.py` (NEW)

**What It Does**:
- Combines all domain clients into single interface
- Maintains backward compatibility with existing code
- Provides both old monolithic access and new domain access

**Implementation**:
```python
# mcp/src/clients/__init__.py
"""Domain-specific API clients"""

from .base import BaseAPIClient, KTRDRAPIError
from .data_client import DataAPIClient
from .training_client import TrainingAPIClient
from .operations_client import OperationsAPIClient

__all__ = [
    "BaseAPIClient",
    "KTRDRAPIError",
    "DataAPIClient",
    "TrainingAPIClient",
    "OperationsAPIClient",
]
```

```python
# mcp/src/api_client.py (UPDATE)
"""
Unified API Client Facade

Provides both domain-specific access (client.operations.list_operations())
and backward-compatible monolithic access (client.list_operations())
"""

from typing import Any, Optional
from .clients import (
    DataAPIClient,
    TrainingAPIClient,
    OperationsAPIClient,
    KTRDRAPIError,
)
from .config import API_TIMEOUT, KTRDR_API_URL

import structlog

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
        self.operations = OperationsAPIClient(base_url, timeout)

        logger.info("Unified API client initialized", base_url=self.base_url)

    async def __aenter__(self):
        """Enter async context - initialize all domain clients"""
        await self.data.__aenter__()
        await self.training.__aenter__()
        await self.operations.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context - cleanup all domain clients"""
        await self.data.__aexit__(exc_type, exc_val, exc_tb)
        await self.training.__aexit__(exc_type, exc_val, exc_tb)
        await self.operations.__aexit__(exc_type, exc_val, exc_tb)

    # Backward compatibility - delegate to domain clients
    async def list_operations(self, **kwargs) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.list_operations(**kwargs)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.get_operation_status(operation_id)

    async def cancel_operation(self, operation_id: str, reason: Optional[str] = None) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.cancel_operation(operation_id, reason)

    async def get_operation_results(self, operation_id: str) -> dict[str, Any]:
        """Delegate to operations client (backward compat)"""
        return await self.operations.get_operation_results(operation_id)

    async def get_cached_data(self, **kwargs) -> dict[str, Any]:
        """Delegate to data client (backward compat)"""
        return await self.data.get_cached_data(**kwargs)

    async def load_data_operation(self, **kwargs) -> dict[str, Any]:
        """Delegate to data client (backward compat)"""
        return await self.data.load_data_operation(**kwargs)

    async def start_neural_training(self, **kwargs) -> dict[str, Any]:
        """Delegate to training client (backward compat)"""
        return await self.training.start_neural_training(**kwargs)

    # Health check (can stay in facade)
    async def health_check(self) -> dict[str, Any]:
        """Check backend health"""
        return await self.operations._request("GET", "/health")


# Singleton instance for easy access
_api_client: Optional[KTRDRAPIClient] = None


def get_api_client() -> KTRDRAPIClient:
    """Get singleton API client instance"""
    global _api_client
    if _api_client is None:
        _api_client = KTRDRAPIClient()
    return _api_client
```

**Acceptance Criteria**:
- [ ] Facade provides both domain-specific and monolithic access
- [ ] Backward compatibility maintained (existing code works)
- [ ] All domain clients initialized in context manager
- [ ] Delegation methods work correctly
- [ ] All unit tests pass
- [ ] Code coverage >80%

**Testing Strategy**:
- Test both access patterns work
- Test context manager lifecycle
- Test delegation to domain clients
- Test backward compatibility with existing tools

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add mcp/src/clients/__init__.py mcp/src/api_client.py tests/unit/mcp/test_facade_client.py
git commit -m "feat(mcp): add unified facade for domain-specific clients with backward compatibility"
```

---

## Phase 2: Backend Enhancements

**Goal**: Minimal backend changes to support MCP integration

### TASK-2.1: Add operation_id to Training Response

**Objective**: Ensure training endpoint returns operation_id explicitly

**Branch**: `feature/mcp-async-operations`

**Files**:
- `ktrdr/api/services/training_service.py` (UPDATE - 1 line)

**Current Code** ([training_service.py:123-133](../../ktrdr/api/services/training_service.py#L123-L133)):
```python
return {
    "success": True,
    "task_id": operation_id,
    "status": "training_started",
    "message": message,
    "symbols": context.symbols,
    "timeframes": context.timeframes,
    "strategy_name": strategy_name,
    "estimated_duration_minutes": estimated_duration,
    "use_host_service": context.use_host_service,
}
```

**Change**:
```python
return {
    "success": True,
    "operation_id": operation_id,  # ← ADD THIS LINE
    "task_id": operation_id,  # Keep for backward compat
    "status": "training_started",
    "message": message,
    "symbols": context.symbols,
    "timeframes": context.timeframes,
    "strategy_name": strategy_name,
    "estimated_duration_minutes": estimated_duration,
    "use_host_service": context.use_host_service,
}
```

**Acceptance Criteria**:
- [ ] Response includes `operation_id` field
- [ ] `task_id` still present for backward compatibility
- [ ] Both fields have same value
- [ ] Existing tests still pass
- [ ] Integration tests verify operation_id present

**Testing**:
```bash
# Start backend
./start_ktrdr.sh

# Test endpoint
curl -X POST http://localhost:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{"symbols": ["AAPL"], "timeframe": "1h", "strategy_name": "mlp_basic"}'

# Verify response includes both operation_id and task_id
```

---

**Commit After**:
```bash
make test-unit  # Ensure all tests pass
make quality    # Lint + format + typecheck
git add ktrdr/api/services/training_service.py
git commit -m "feat(api): add operation_id to training start response for MCP compatibility"
```

---

### TASK-2.2: Add Operations Results Endpoint

**Objective**: Create new endpoint to get operation results summary

**Branch**: `feature/mcp-async-operations`

**Files**:
- `ktrdr/api/endpoints/operations.py` (UPDATE - ~20 lines)
- `tests/integration/api/test_operations_results.py` (NEW)

**Implementation**:
```python
# Add to ktrdr/api/endpoints/operations.py

from fastapi import HTTPException, status
from ktrdr.api.models.operations import OperationStatus

@router.get("/operations/{operation_id}/results")
async def get_operation_results(
    operation_id: str,
    operations_service: OperationsService = Depends(get_operations_service),
) -> dict[str, Any]:
    """
    Get operation results (summary metrics + analytics paths).

    Only returns results for completed or failed operations.
    For running operations, use GET /operations/{operation_id} for status.
    """
    operation = await operations_service.get_operation(operation_id)

    if not operation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation not found: {operation_id}",
        )

    if operation.status not in [OperationStatus.COMPLETED, OperationStatus.FAILED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Operation not finished (status: {operation.status.value})",
        )

    return {
        "success": True,
        "operation_id": operation_id,
        "operation_type": operation.operation_type.value,
        "status": operation.status.value,
        "results": operation.result_summary or {},
    }
```

**Acceptance Criteria**:
- [ ] Endpoint returns 404 if operation not found
- [ ] Endpoint returns 400 if operation not finished
- [ ] Returns result_summary for completed operations
- [ ] Returns result_summary for failed operations (error details)
- [ ] Unit tests cover all scenarios
- [ ] API docs updated (Swagger/ReDoc)

**Testing Strategy**:
- **Unit tests** with mocked OperationsService (fast, <1s)
- Test error scenarios (not found, not complete, not failed/completed)
- Test response format for completed and failed operations
- **Manual verification** with running backend (curl/Swagger UI)
- **Skip integration tests** (4min, 10% failure rate - not worth it for 20 lines)

**Manual Testing**:
```bash
# Start backend
./start_ktrdr.sh

# Create an operation (e.g., trigger data loading)
curl -X POST http://localhost:8000/api/v1/data/load \
  -H "Content-Type: application/json" \
  -d '{"symbol": "AAPL", "timeframe": "1h", "mode": "local"}'
# Note the operation_id

# Wait for completion, then test results endpoint
curl http://localhost:8000/api/v1/operations/{operation_id}/results

# Test error cases
curl http://localhost:8000/api/v1/operations/invalid_id/results  # → 404
curl http://localhost:8000/api/v1/operations/{running_op_id}/results  # → 400
```

---

**Commit After**:
```bash
make test-unit  # Fast unit tests only
make quality    # Lint + format + typecheck
git add ktrdr/api/endpoints/operations.py tests/unit/api/test_operations_results.py
git commit -m "feat(api): add GET /operations/{id}/results endpoint for MCP integration"
```

---

### TASK-2.3: Update Operations List Default Limit

**Objective**: Change default pagination limit from 100 to 10

**Branch**: `feature/mcp-async-operations`

**Files**:
- `ktrdr/api/endpoints/operations.py` (UPDATE - 1 line)

**Current Code**:
```python
@router.get("/operations")
async def list_operations(
    operation_type: Optional[OperationType] = None,
    status: Optional[OperationStatus] = None,
    active_only: bool = False,
    limit: int = Query(100, ge=1, le=100),  # ← Change default here
    offset: int = Query(0, ge=0),
    operations_service: OperationsService = Depends(get_operations_service)
) -> OperationListResponse:
```

**Change**:
```python
@router.get("/operations")
async def list_operations(
    operation_type: Optional[OperationType] = None,
    status: Optional[OperationStatus] = None,
    active_only: bool = False,
    limit: int = Query(10, ge=1, le=100),  # ← Changed from 100 to 10
    offset: int = Query(0, ge=0),
    operations_service: OperationsService = Depends(get_operations_service)
) -> OperationListResponse:
```

**Acceptance Criteria**:
- [ ] Default limit is 10 (not 100)
- [ ] Can still request up to 100 with explicit parameter
- [ ] Existing tests updated if they rely on default 100
- [ ] API docs reflect new default

**Testing**:
```bash
# Test default limit
curl http://localhost:8000/api/v1/operations
# Should return max 10 operations

# Test explicit limit
curl http://localhost:8000/api/v1/operations?limit=50
# Should return max 50 operations
```

---

**Commit After**:
```bash
make test-unit  # Fast unit tests (update if any rely on default 100)
make quality    # Lint + format + typecheck
git add ktrdr/api/endpoints/operations.py
git commit -m "feat(api): change default operations list limit to 10 for MCP efficiency"
```

---

## Phase 3: MCP Tools Implementation

**Goal**: Implement 6 MCP tools using new domain-specific clients

### TASK-3.1: Add list_operations Tool

**Objective**: New MCP tool to list operations with filters

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - add tool)
- `mcp/src/tools/operations.py` (NEW - optional, for organization)

**Implementation**:
```python
# Add to mcp/src/server.py (or create mcp/src/tools/operations.py)

@mcp.tool()
async def list_operations(
    operation_type: Optional[str] = None,
    status: Optional[str] = None,
    active_only: bool = False,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """
    List operations with optional filters.

    Discover operations without prior knowledge. Filter by type, status,
    or show only active operations.

    Args:
        operation_type: Filter by type ("data_load", "training", "backtesting")
        status: Filter by status ("pending", "running", "completed", "failed", "cancelled")
        active_only: Only show pending + running operations
        limit: Max operations to return (default 10)
        offset: Number of operations to skip for pagination

    Returns:
        Dict with:
        - data: List of operation summaries
        - total_count: Total matching operations
        - active_count: Number of active operations
        - returned_count: Number in this response

    Examples:
        - list_operations(active_only=True) → All running operations
        - list_operations(operation_type="training", status="running") → Active training
        - list_operations(status="failed", limit=5) → Last 5 failed operations
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.list_operations(
                operation_type=operation_type,
                status=status,
                active_only=active_only,
                limit=limit,
                offset=offset,
            )
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool registered with MCP server
- [ ] All parameters work correctly
- [ ] Filters applied properly (type, status, active_only)
- [ ] Pagination works (limit, offset)
- [ ] Error handling for API failures
- [ ] Tool works in Claude Desktop/CLI

**Testing**:
```bash
# Test with MCP inspector or Claude Desktop
mcp dev mcp/src/server.py

# Test filters
list_operations(active_only=True)
list_operations(operation_type="training", status="running")
list_operations(limit=5)
```

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): add list_operations tool for operation discovery"
```

---

### TASK-3.2: Add get_operation_status Tool

**Objective**: New MCP tool to get detailed operation status

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - add tool)

**Implementation**:
```python
@mcp.tool()
async def get_operation_status(operation_id: str) -> dict[str, Any]:
    """
    Get detailed operation status with progress and context.

    Returns rich progress information including domain-specific context
    (e.g., epochs/batches for training, segments for data loading).

    Args:
        operation_id: Operation identifier (e.g., "op_training_20251004_143530_...")

    Returns:
        Dict with:
        - operation_id, operation_type, status
        - progress: percentage, current_step, context (domain-specific)
        - metadata: operation parameters
        - created_at, started_at, completed_at timestamps
        - result_summary (if completed)
        - error_message (if failed)

    Examples:
        get_operation_status("op_training_20251004_143530_b5c6d7e8")
        → {"status": "running", "progress": {"percentage": 65.2, "current_step": "Epoch 32/50"}}
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_status(operation_id)
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool returns detailed operation info
- [ ] Progress context included (domain-specific)
- [ ] Works for all operation types (data, training)
- [ ] Error handling for not found
- [ ] Tool works in Claude Desktop

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): add get_operation_status tool for detailed progress"
```

---

### TASK-3.3: Add cancel_operation Tool

**Objective**: New MCP tool to cancel running operations

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - add tool)

**Implementation**:
```python
@mcp.tool()
async def cancel_operation(
    operation_id: str, reason: Optional[str] = None
) -> dict[str, Any]:
    """
    Cancel a running operation.

    Cancellation propagates to backend → host services → processes.
    Graceful shutdown with checkpoint save is already supported.

    Args:
        operation_id: Operation identifier to cancel
        reason: Optional reason for cancellation

    Returns:
        Dict with:
        - success: bool
        - operation_id: str
        - status: "cancelled"
        - cancelled_at: timestamp
        - cancellation_reason: str
        - task_cancelled: bool (backend task)
        - training_session_cancelled: bool (if training)

    Examples:
        cancel_operation("op_training_...", "User changed strategy")
        → {"success": true, "status": "cancelled"}
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.cancel_operation(operation_id, reason)
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool cancels running operations
- [ ] Cancellation propagates to host services
- [ ] Optional reason parameter works
- [ ] Error handling for already completed/cancelled
- [ ] Tool works in Claude Desktop

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): add cancel_operation tool for operation cancellation"
```

---

### TASK-3.4: Add get_operation_results Tool

**Objective**: New MCP tool to get operation results summary

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - add tool)

**Implementation**:
```python
@mcp.tool()
async def get_operation_results(operation_id: str) -> dict[str, Any]:
    """
    Get operation results (summary metrics + analytics paths).

    Returns lightweight summary metrics and paths to detailed data.
    Works for any operation type (data loading, training, backtesting).

    Args:
        operation_id: Operation identifier

    Returns:
        Dict with:
        - operation_id, operation_type, status
        - results: summary metrics + artifact paths

    Training results include:
        - training_metrics: final losses, epochs completed
        - validation_metrics: accuracy, precision
        - artifacts: model_path, analytics_directory

    Data loading results include:
        - bars_loaded, date_range, gaps_filled
        - data_source, storage_location

    Examples:
        get_operation_results("op_training_...")
        → {"results": {"training_metrics": {...}, "artifacts": {...}}}
    """
    try:
        async with get_api_client() as client:
            result = await client.operations.get_operation_results(operation_id)
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool returns results for completed operations
- [ ] Error handling for not complete/not found
- [ ] Works for different operation types
- [ ] Result structure matches spec
- [ ] Tool works in Claude Desktop

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): add get_operation_results tool for result retrieval"
```

---

### TASK-3.5: Update trigger_data_loading Tool

**Objective**: Rename/update existing data loading tool to return operation_id

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - rename load_data_from_source → trigger_data_loading)

**Implementation**:
```python
@mcp.tool()
async def trigger_data_loading(
    symbol: str,
    timeframe: str = "1h",
    mode: str = "tail",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Trigger async data loading operation (returns operation_id for tracking).

    This does NOT return market data - it initiates a background loading operation.
    Use get_market_data() to retrieve the loaded data after operation completes.

    Args:
        symbol: Trading symbol (e.g., "AAPL", "EURUSD")
        timeframe: Data timeframe ("1m", "5m", "15m", "1h", "1d")
        mode: Loading mode ("local", "tail", "backfill", "full")
        start_date: Start date (ISO format, e.g., "2024-01-01")
        end_date: End date (ISO format)

    Returns:
        Dict with:
        - success: bool
        - operation_id: str (for tracking with get_operation_status)
        - operation_type: "data_load"
        - status: "started"
        - message: Human-readable description

    Examples:
        trigger_data_loading("AAPL", "1h", "tail", "2024-01-01")
        → {"operation_id": "op_data_load_...", "status": "started"}
    """
    try:
        async with get_api_client() as client:
            result = await client.data.load_data_operation(
                symbol=symbol,
                timeframe=timeframe,
                mode=mode,
                start_date=start_date,
                end_date=end_date,
            )
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool renamed from load_data_from_source
- [ ] Returns operation_id for tracking
- [ ] Clear docstring explains it doesn't return data
- [ ] All parameters work correctly
- [ ] Tool works in Claude Desktop

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): rename to trigger_data_loading and ensure returns operation_id"
```

---

### TASK-3.6: Update start_training Tool

**Objective**: Update existing training tool to ensure returns operation_id

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/src/server.py` (UPDATE - ensure start_model_training → start_training, returns operation_id)

**Implementation**:
```python
@mcp.tool()
async def start_training(
    strategy_config_path: str,
    symbols: list[str],
    timeframes: list[str] = ["1h"],
    training_config: Optional[dict] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict[str, Any]:
    """
    Start neural network training (returns operation_id for tracking).

    Initiates async training operation. Use get_operation_status() to monitor
    progress and get_operation_results() to retrieve final metrics.

    Args:
        strategy_config_path: Strategy name (e.g., "mlp_basic", "lstm_advanced")
        symbols: List of trading symbols (e.g., ["AAPL", "MSFT"])
        timeframes: List of timeframes (e.g., ["1h", "4h"])
        training_config: Optional training parameters (epochs, learning_rate, etc.)
        start_date: Training data start date (ISO format)
        end_date: Training data end date (ISO format)

    Returns:
        Dict with:
        - success: bool
        - operation_id: str (for tracking with get_operation_status)
        - task_id: str (same as operation_id, for backward compat)
        - status: "training_started"
        - message: Human-readable description
        - estimated_duration_minutes: int

    Examples:
        start_training("mlp_basic", ["AAPL", "MSFT"], ["1h"])
        → {"operation_id": "op_training_...", "status": "training_started"}
    """
    try:
        async with get_api_client() as client:
            # Backend expects single timeframe currently
            result = await client.training.start_neural_training(
                symbols=symbols,
                timeframe=timeframes[0] if timeframes else "1h",
                config=training_config or {},
                start_date=start_date,
                end_date=end_date,
            )
            return result
    except KTRDRAPIError as e:
        logger.error(f"API error: {e.message}", error=str(e))
        return {
            "success": False,
            "error": e.message,
            "status_code": e.status_code,
            "details": e.details,
        }
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": f"Unexpected error: {str(e)}"}
```

**Acceptance Criteria**:
- [ ] Tool returns operation_id in response
- [ ] Backend returns both operation_id and task_id
- [ ] Clear docstring explains async pattern
- [ ] All parameters work correctly
- [ ] Tool works in Claude Desktop

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/src/server.py
git commit -m "feat(mcp): update start_training to ensure returns operation_id"
```

---

## Phase 4: Integration Testing & Documentation

### TASK-4.1: Manual End-to-End Verification

**⚠️ MANUAL TASK - HUMAN ONLY ⚠️**

**Objective**: Verify complete workflows with MCP tools via manual testing

**Branch**: `feature/mcp-async-operations`

**👤 WHO DOES THIS**: User (Karl) - NOT the coding agent
**🤖 CODING AGENT**: Do NOT attempt to automate this task. Skip to TASK-4.2.

**Why Manual Instead of Automated?**:
- Integration tests: 4min runtime, 10% failure rate
- Not worth the overhead for verification
- Manual testing is faster and more reliable for this use case
- Requires human interaction with Claude Desktop/MCP inspector

**Manual Test Scenarios**:

**1. Data Loading Workflow**:
```bash
# Start backend and MCP server
./start_ktrdr.sh
mcp dev mcp/src/server.py

# Test in Claude Desktop or MCP inspector:
1. trigger_data_loading("AAPL", "1h", "local")
   → Verify returns operation_id
2. list_operations(active_only=True)
   → Verify shows the operation
3. get_operation_status(operation_id)
   → Verify shows progress
4. get_operation_results(operation_id)
   → Verify returns result_summary
5. get_market_data("AAPL", "1h")
   → Verify data is available
```

**2. Training Workflow**:
```bash
# In Claude Desktop/MCP inspector:
1. start_training("mlp_basic", ["AAPL"], ["1h"])
   → Verify returns operation_id
2. get_operation_status(operation_id)
   → Verify shows epoch/batch progress
3. cancel_operation(operation_id, "Testing cancellation")
   → Verify cancellation succeeds
4. get_operation_status(operation_id)
   → Verify status = "cancelled"
```

**3. Discovery Workflow**:
```bash
# Start multiple operations, then:
1. list_operations(active_only=True)
   → Verify shows only running ops
2. list_operations(operation_type="training")
   → Verify filters by type
3. list_operations(status="completed", limit=5)
   → Verify pagination works
```

**Acceptance Criteria**:
- [ ] All 3 workflows verified manually
- [ ] Tools work correctly in Claude Desktop
- [ ] Progress updates visible
- [ ] Cancellation propagates properly
- [ ] Filters and pagination work

**Documentation**:
Create a manual test checklist in `mcp/TESTING.md` for future verification

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add mcp/TESTING.md  # If created
git commit -m "docs(mcp): add manual testing checklist for async operations"
```

---

### TASK-4.2: Update MCP Server Documentation

**Objective**: Document new tools and usage patterns

**Branch**: `feature/mcp-async-operations`

**Files**:
- `mcp/README.md` (UPDATE)
- `mcp/TOOLS.md` (NEW - detailed tool reference)

**Documentation Sections**:
1. **Overview** - Async operations pattern
2. **Available Tools** - List with descriptions
3. **Usage Examples** - Common workflows
4. **Agent Patterns** - Fire-and-forget, discovery, monitoring

**Acceptance Criteria**:
- [ ] All 6 new/updated tools documented
- [ ] Example workflows included
- [ ] Agent usage patterns explained
- [ ] Troubleshooting section added

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck (for any code examples in docs)
git add mcp/README.md mcp/TOOLS.md
git commit -m "docs(mcp): document async operations tools and usage patterns"
```

---

## Phase 5: Final Cleanup & Merge

### TASK-5.1: Remove Old Monolithic Code (If Any)

**Objective**: Clean up any obsolete code from refactor

**Branch**: `feature/mcp-async-operations`

**Review**:
- Check if old `load_data_from_source` tool removed (replaced by `trigger_data_loading`)
- Check if old `start_model_training` tool removed (replaced by `start_training`)
- Verify no dead code in api_client.py

---

**Commit After**:
```bash
make quality  # Lint + format + typecheck
git add <files>
git commit -m "refactor(mcp): remove obsolete tools after async operations migration"
```

---

### TASK-5.2: Final Testing & Quality Checks

**Objective**: Comprehensive testing before merge

**Branch**: `feature/mcp-async-operations`

**Checklist**:
- [ ] All unit tests pass: `make test-unit`
- [ ] All integration tests pass: `make test-integration`
- [ ] Code quality checks pass: `make quality`
- [ ] Type checking passes: `make typecheck`
- [ ] No lint errors: `make lint`
- [ ] Test coverage >80% for new code

---

### TASK-5.3: Merge to Main

**Objective**: Integrate feature branch

**Commands**:
```bash
# Ensure branch is up to date
git checkout main
git pull origin main
git checkout feature/mcp-async-operations
git rebase main

# Final tests
make test-unit
make test-integration
make quality

# Merge
git checkout main
git merge --no-ff feature/mcp-async-operations -m "feat(mcp): integrate async operations with domain-specific clients

BREAKING CHANGES: None (backward compatible)

This PR implements:
- Domain-specific API clients (Data, Training, Operations)
- 4 new MCP tools (list, status, cancel, results)
- 2 updated MCP tools (trigger_data_loading, start_training)
- Backend enhancements (operation_id, results endpoint, pagination)

All changes are additive and maintain backward compatibility.

Closes #XXX"

# Clean up
git branch -d feature/mcp-async-operations
git push origin main
git push origin --delete feature/mcp-async-operations
```

---

## Success Criteria (Phase 1 Complete)

- [x] Domain-specific API clients implemented (Data, Training, Operations)
- [x] Base HTTP client with shared functionality
- [x] Unified facade with backward compatibility
- [x] 4 new MCP tools (list, status, cancel, results)
- [x] 2 updated MCP tools (trigger_data_loading, start_training)
- [x] Training endpoint returns operation_id
- [x] Operations results endpoint created
- [x] Operations list default limit changed to 10
- [x] All unit tests pass (>80% coverage)
- [x] All integration tests pass
- [x] Documentation updated
- [x] Backward compatibility maintained
- [x] Zero breaking changes

---

## Estimated Effort

| Phase | Tasks | Estimated Time |
|-------|-------|----------------|
| Phase 1: API Client Refactor | 5 tasks | 4-6 hours |
| Phase 2: Backend Enhancements | 3 tasks | 1-2 hours |
| Phase 3: MCP Tools | 6 tasks | 3-4 hours |
| Phase 4: Integration & Docs | 2 tasks | 2-3 hours |
| Phase 5: Cleanup & Merge | 3 tasks | 1 hour |
| **Total** | **19 tasks** | **11-16 hours** |

---

## Risk Mitigation

**Risk 1**: Backward compatibility breaks
- **Mitigation**: Facade pattern maintains old interface
- **Testing**: Verify existing tools still work

**Risk 2**: Integration tests flaky
- **Mitigation**: Use proper test isolation, cleanup between tests
- **Testing**: Run tests multiple times

**Risk 3**: Domain client refactor too large
- **Mitigation**: Incremental approach, one client at a time
- **Testing**: Test each client independently

---

**End of Implementation Plan**
