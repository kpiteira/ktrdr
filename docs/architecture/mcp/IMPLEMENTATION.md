# MCP Response Handling & Documentation - Implementation Plan

**Parent Document**: [Architecture](./ARCHITECTURE.md)

**Status**: Ready for Implementation
**Version**: 1.0
**Date**: 2025-10-05
**Branch**: `feat/mcp-response-handling-and-docstrings`

---

## Overview

This document breaks down the implementation of response handling standardization and docstring enhancements into discrete, testable tasks following strict TDD methodology.

**Scope**:

- ✅ 3 extraction helper methods in BaseAPIClient
- ✅ 6 domain clients updated to use hybrid pattern
- ✅ 12 MCP tool docstrings enhanced to full standard
- ✅ Documentation updates

**TDD Workflow** (Mandatory):

```
RED → GREEN → REFACTOR
Write failing test → Make it pass → Clean up code
```

**Quality Gates** (Before EVERY commit):

```bash
make test-unit   # Must pass (<2s)
make quality     # Must pass (lint + format + typecheck)
```

**Branching Strategy**:

- **Feature Branch**: `feat/mcp-response-handling-and-docstrings` (off `main`)
- **Merge Target**: `main`
- **After Merge**: Delete feature branch

---

## Sprint 1: Response Handling + Docstrings

### TASK-1: Add Extraction Methods to BaseAPIClient

**Objective**: Add three helper methods for hybrid response extraction pattern

**Files**:

- `mcp/src/clients/base.py` (UPDATE)
- `tests/unit/mcp/test_base_client.py` (UPDATE)

**TDD Workflow**:

**RED Phase** - Write failing tests first:

```python
# tests/unit/mcp/test_base_client.py

import pytest
from mcp.src.clients.base import BaseAPIClient, KTRDRAPIError


class TestExtractList:
    """Test _extract_list() method"""

    def test_extract_list_with_data_field(self):
        """Should extract list from 'data' field"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": [{"id": 1}, {"id": 2}]}

        result = client._extract_list(response)

        assert result == [{"id": 1}, {"id": 2}]

    def test_extract_list_missing_field_returns_empty(self):
        """Should return empty list when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_list(response)

        assert result == []

    def test_extract_list_custom_field(self):
        """Should extract from custom field name"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "models": [{"name": "model1"}]}

        result = client._extract_list(response, field="models")

        assert result == [{"name": "model1"}]

    def test_extract_list_custom_default(self):
        """Should use custom default when provided"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_list(response, default=[{"default": True}])

        assert result == [{"default": True}]


class TestExtractDict:
    """Test _extract_dict() method"""

    def test_extract_dict_with_data_field(self):
        """Should extract dict from 'data' field"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": {"key": "value"}}

        result = client._extract_dict(response)

        assert result == {"key": "value"}

    def test_extract_dict_missing_field_returns_empty(self):
        """Should return empty dict when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        result = client._extract_dict(response)

        assert result == {}

    def test_extract_dict_custom_field(self):
        """Should extract from custom field name"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "result": {"status": "ok"}}

        result = client._extract_dict(response, field="result")

        assert result == {"status": "ok"}


class TestExtractOrRaise:
    """Test _extract_or_raise() method"""

    def test_extract_or_raise_success(self):
        """Should extract field when present and success=True"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True, "data": {"operation_id": "op_123"}}

        result = client._extract_or_raise(response, field="data")

        assert result == {"operation_id": "op_123"}

    def test_extract_or_raise_explicit_error_flag(self):
        """Should raise when success=False"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": False, "error": "Not found"}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(response, operation="training start")

        assert "Training start failed: Not found" in str(exc_info.value)

    def test_extract_or_raise_missing_field(self):
        """Should raise when field missing"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": True}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(response, field="operation_id", operation="data loading")

        assert "Data loading response missing 'operation_id' field" in str(exc_info.value)

    def test_extract_or_raise_custom_operation_name(self):
        """Should use operation name in error messages"""
        client = BaseAPIClient("http://localhost", 30.0)
        response = {"success": False, "error": "Timeout"}

        with pytest.raises(KTRDRAPIError) as exc_info:
            client._extract_or_raise(response, operation="model training")

        assert "Model training failed: Timeout" in str(exc_info.value)
```

Run tests (should FAIL):

```bash
uv run pytest tests/unit/mcp/test_base_client.py::TestExtractList -v
uv run pytest tests/unit/mcp/test_base_client.py::TestExtractDict -v
uv run pytest tests/unit/mcp/test_base_client.py::TestExtractOrRaise -v
# Expected: All tests FAIL (methods don't exist yet)
```

**GREEN Phase** - Implement methods to pass tests:

```python
# mcp/src/clients/base.py

class BaseAPIClient:
    """Shared HTTP client functionality for all domain clients"""

    # ... existing __init__, __aenter__, __aexit__, _request methods ...

    def _extract_list(
        self,
        response: dict[str, Any],
        field: str = "data",
        default: Optional[list] = None
    ) -> list[dict[str, Any]]:
        """
        Extract list from response envelope.

        For non-critical operations where empty list is acceptable.

        Args:
            response: API response dict
            field: Field name to extract (default "data")
            default: Default value if field missing (default [])

        Returns:
            Extracted list or default

        Example:
            response = {"success": true, "data": [...]}
            items = self._extract_list(response)
        """
        if default is None:
            default = []
        return response.get(field, default)

    def _extract_dict(
        self,
        response: dict[str, Any],
        field: str = "data",
        default: Optional[dict] = None
    ) -> dict[str, Any]:
        """
        Extract dict from response envelope.

        For non-critical operations where empty dict is acceptable.

        Args:
            response: API response dict
            field: Field name to extract (default "data")
            default: Default value if field missing (default {})

        Returns:
            Extracted dict or default

        Example:
            response = {"success": true, "data": {...}}
            item = self._extract_dict(response)
        """
        if default is None:
            default = {}
        return response.get(field, default)

    def _extract_or_raise(
        self,
        response: dict[str, Any],
        field: str = "data",
        operation: str = "operation"
    ) -> Any:
        """
        Extract field from response or raise detailed error.

        For critical operations that MUST succeed (training start, data loading).

        Args:
            response: API response dict
            field: Field name to extract
            operation: Operation name for error message

        Returns:
            Extracted value

        Raises:
            KTRDRAPIError: If field missing or response indicates error

        Example:
            response = {"success": true, "data": {...}}
            data = self._extract_or_raise(response, operation="training start")
        """
        # Check explicit error flag
        if not response.get("success", True):
            error_msg = response.get("error", "Unknown error")
            raise KTRDRAPIError(
                f"{operation.capitalize()} failed: {error_msg}",
                details=response
            )

        # Extract field
        if field not in response:
            raise KTRDRAPIError(
                f"{operation.capitalize()} response missing '{field}' field",
                details=response
            )

        return response[field]
```

Run tests (should PASS):

```bash
make test-unit  # All tests must pass
```

**REFACTOR Phase** - Clean up if needed (likely none for this task)

**Quality Gate**:

```bash
make test-unit   # Must pass
make quality     # Must pass (lint + format + typecheck)
```

**Commit**:

```bash
git add mcp/src/clients/base.py tests/unit/mcp/test_base_client.py
git commit -m "feat(mcp): add hybrid response extraction methods to BaseAPIClient

- Add _extract_list() for simple list extraction with defaults
- Add _extract_dict() for simple dict extraction with defaults
- Add _extract_or_raise() for critical operations requiring validation
- Full test coverage for all extraction patterns"
```

---

### TASK-2: Update DataAPIClient with Hybrid Pattern

**Objective**: Apply extraction methods to DataAPIClient

**Files**:

- `mcp/src/clients/data_client.py` (UPDATE)
- `tests/unit/mcp/test_data_client.py` (UPDATE)

**TDD Workflow**:

**RED Phase** - Update existing tests or add new ones:

```python
# tests/unit/mcp/test_data_client.py

async def test_get_symbols_uses_extract_list():
    """Should use _extract_list for symbols response"""
    # Mock _request to return response with data field
    # Verify _extract_list called with correct parameters

async def test_load_data_operation_uses_extract_or_raise():
    """Should use _extract_or_raise for critical data loading"""
    # Mock _request to return response
    # Verify _extract_or_raise called for operation_id extraction
```

**GREEN Phase** - Update implementation:

```python
# mcp/src/clients/data_client.py

class DataAPIClient(BaseAPIClient):
    """API client for data operations"""

    async def get_symbols(self) -> list[dict[str, Any]]:
        """Get available trading symbols"""
        response = await self._request("GET", "/api/v1/symbols")
        return self._extract_list(response)  # Simple extraction

    async def load_data_operation(
        self,
        symbol: str,
        timeframe: str = "1h",
        mode: str = "local",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """Trigger data loading operation (MUST return operation_id)"""
        payload = {"symbol": symbol, "timeframe": timeframe, "mode": mode}
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date

        response = await self._request("POST", "/api/v1/data/load", json=payload)

        # CRITICAL: Must have operation_id
        return self._extract_or_raise(response, operation="data loading")
```

**Quality Gate & Commit**:

```bash
make test-unit
make quality
git add mcp/src/clients/data_client.py tests/unit/mcp/test_data_client.py
git commit -m "refactor(mcp): apply hybrid response pattern to DataAPIClient

- Use _extract_list() for get_symbols()
- Use _extract_or_raise() for load_data_operation()
- Maintain backward compatibility"
```

---

### TASK-3: Update TrainingAPIClient with Hybrid Pattern

**Objective**: Apply extraction methods to TrainingAPIClient

**Files**:

- `mcp/src/clients/training_client.py` (UPDATE)
- `tests/unit/mcp/test_training_client.py` (UPDATE)

**Implementation** (following same TDD pattern as TASK-2):

```python
# mcp/src/clients/training_client.py

class TrainingAPIClient(BaseAPIClient):
    """API client for training operations"""

    async def list_trained_models(self) -> list[dict[str, Any]]:
        """List all trained models"""
        response = await self._request("GET", "/api/v1/models")
        # Backend returns {models: [...]} instead of {data: [...]}
        return self._extract_list(response, field="models")

    async def start_neural_training(
        self,
        symbols: list[str],
        timeframes: list[str],
        strategy_name: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        task_id: Optional[str] = None,
        detailed_analytics: bool = False,
    ) -> dict[str, Any]:
        """Start neural network training (MUST return operation_id)"""
        payload = {
            "symbols": symbols,
            "timeframes": timeframes,
            "strategy_name": strategy_name,
            "detailed_analytics": detailed_analytics,
        }
        if start_date:
            payload["start_date"] = start_date
        if end_date:
            payload["end_date"] = end_date
        if task_id:
            payload["task_id"] = task_id

        response = await self._request("POST", "/api/v1/trainings/start", json=payload)

        # CRITICAL: Must succeed
        return self._extract_or_raise(response, operation="training start")
```

**Commit**:

```bash
make test-unit
make quality
git add mcp/src/clients/training_client.py tests/unit/mcp/test_training_client.py
git commit -m "refactor(mcp): apply hybrid response pattern to TrainingAPIClient

- Use _extract_list() for list_trained_models() with custom 'models' field
- Use _extract_or_raise() for start_neural_training()
- Maintain backward compatibility"
```

---

### TASK-4: Update OperationsAPIClient with Hybrid Pattern

**Objective**: Apply extraction methods to OperationsAPIClient

**Files**:

- `mcp/src/clients/operations_client.py` (UPDATE)
- `tests/unit/mcp/test_operations_client.py` (UPDATE)

**Implementation**:

```python
# mcp/src/clients/operations_client.py

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

        # Return full response (includes data, total_count, active_count)
        return await self._request("GET", "/api/v1/operations", params=params)

    async def get_operation_status(self, operation_id: str) -> dict[str, Any]:
        """Get detailed operation status"""
        response = await self._request("GET", f"/api/v1/operations/{operation_id}")
        return self._extract_dict(response)  # Simple extraction
```

**Commit**:

```bash
make test-unit
make quality
git add mcp/src/clients/operations_client.py tests/unit/mcp/test_operations_client.py
git commit -m "refactor(mcp): apply hybrid response pattern to OperationsAPIClient

- Keep full response for list_operations() (needs total_count, active_count)
- Use _extract_dict() for get_operation_status()
- Maintain backward compatibility"
```

---

### TASK-5: Update IndicatorsAPIClient with Hybrid Pattern

**Objective**: Apply extraction methods to IndicatorsAPIClient

**Files**:

- `mcp/src/clients/indicators_client.py` (UPDATE)
- `tests/unit/mcp/test_indicators_client.py` (UPDATE)

**Implementation**:

```python
# mcp/src/clients/indicators_client.py

class IndicatorsAPIClient(BaseAPIClient):
    """API client for indicators operations"""

    async def list_indicators(self) -> list[dict[str, Any]]:
        """List all available indicators"""
        response = await self._request("GET", "/api/v1/indicators/")
        return self._extract_list(response)  # Simple extraction
```

**Commit**:

```bash
make test-unit
make quality
git add mcp/src/clients/indicators_client.py tests/unit/mcp/test_indicators_client.py
git commit -m "refactor(mcp): apply hybrid response pattern to IndicatorsAPIClient

- Use _extract_list() for list_indicators()
- Maintain backward compatibility"
```

---

### TASK-6: Update StrategiesAPIClient with Hybrid Pattern

**Objective**: Apply extraction methods to StrategiesAPIClient

**Files**:

- `mcp/src/clients/strategies_client.py` (UPDATE)
- `tests/unit/mcp/test_strategies_client.py` (UPDATE)

**Implementation**:

```python
# mcp/src/clients/strategies_client.py

class StrategiesAPIClient(BaseAPIClient):
    """API client for strategies operations"""

    async def list_strategies(self) -> dict[str, Any]:
        """List all available strategies"""
        # Return full response (backend may include metadata)
        return await self._request("GET", "/api/v1/strategies/")
```

**Commit**:

```bash
make test-unit
make quality
git add mcp/src/clients/strategies_client.py tests/unit/mcp/test_strategies_client.py
git commit -m "refactor(mcp): apply hybrid response pattern to StrategiesAPIClient

- Keep full response for list_strategies() (may include metadata)
- Maintain backward compatibility"
```

---

### TASK-7: Enhance All MCP Tool Docstrings

**Objective**: Apply comprehensive docstring standard to all 12 MCP tools

**Files**:

- `mcp/src/server.py` (UPDATE - all tool docstrings)

**Standard Template**:

```python
@mcp.tool()
async def tool_name(
    param1: str,
    param2: Optional[str] = None,
) -> dict[str, Any]:
    """
    [One-line summary of what tool does]

    [Extended description explaining behavior, context, and when to use]

    Args:
        param1: Description with valid values:
            - "value1": What this means
            - "value2": What this means
            - Format examples if needed
        param2: Optional parameter description
            - Default behavior when None

    Returns:
        Dict with structure:
        {
            "success": bool,
            "field1": str,
            "field2": {
                "nested": str,
                "fields": int
            },
            "field3": Optional[str]  # Present when...
        }

    Raises:
        KTRDRAPIError: When [specific error scenario]
        KTRDRAPIError: When [another error scenario]

    Examples:
        # Basic usage
        result = await tool_name("value1")
        # Returns: {"success": True, "field1": "..."}

        # Advanced usage
        result = await tool_name("value2", param2="custom")
        # Returns: {"success": True, "field1": "...", "field2": {...}}

    See Also:
        - related_tool1(): What it does and when to use
        - related_tool2(): What it does and when to use

    Notes:
        - Important behavioral detail 1
        - Important behavioral detail 2
        - Performance considerations if relevant
    """
    # Implementation...
```

**Tools to Update** (2 commits for manageability):

**Commit 1** - Core operation tools:

- `list_operations()`
- `get_operation_status()`
- `cancel_operation()`
- `get_operation_results()`
- `trigger_data_loading()`
- `start_training()`

**Commit 2** - Data and configuration tools:

- `get_market_data()`
- `get_symbols()`
- `get_indicators()`
- `get_strategies()`
- `list_trained_models()`
- `health_check()`

**TDD Note**: Docstring changes don't require new tests, but existing tests should still pass.

**Quality Gate & Commits**:

```bash
make test-unit  # Verify no regressions
make quality
git add mcp/src/server.py
git commit -m "docs(mcp): enhance docstrings for core operation tools

Apply comprehensive docstring standard to:
- list_operations
- get_operation_status
- cancel_operation
- get_operation_results
- trigger_data_loading
- start_training

Each docstring now includes:
- Clear one-line summary
- Extended description with context
- Args with valid values and formats
- Returns with complete structure
- Raises with specific scenarios
- Examples with working code
- See Also with related tools
- Notes with behavioral details"

# Second commit
make test-unit
make quality
git add mcp/src/server.py
git commit -m "docs(mcp): enhance docstrings for data and configuration tools

Apply comprehensive docstring standard to:
- get_market_data
- get_symbols
- get_indicators
- get_strategies
- list_trained_models
- health_check

Completes full docstring standardization across all 12 MCP tools."
```

---

### TASK-8: Update Documentation

**Objective**: Document response handling pattern and docstring standards

**Files**:

- `mcp/MCP_TOOLS.md` (UPDATE - add docstring standard section)
- `mcp/README.md` (UPDATE - mention response handling)

**Content**:

**MCP_TOOLS.md** additions:

```markdown
## Docstring Standards

All MCP tools follow a comprehensive docstring standard to ensure AI agents
can understand and use them correctly.

### Required Sections

1. **One-line summary** - What the tool does
2. **Extended description** - Context and behavior
3. **Args** - Parameter formats with valid values
4. **Returns** - Complete structure with field descriptions
5. **Raises** - Error scenarios
6. **Examples** - Working code showing common use cases
7. **See Also** - Related tools for discovery
8. **Notes** - Important behavioral details

### Example

[Include full example from architecture doc]

## Response Handling Pattern

API clients use a hybrid response handling pattern:

- **Simple extractors** for common operations (_extract_list, _extract_dict)
- **Strict validation** for critical operations (_extract_or_raise)
- **Backward compatibility** maintained throughout

See [Architecture](../docs/architecture/mcp/ARCHITECTURE.md) for details.
```

**Commit**:

```bash
git add mcp/MCP_TOOLS.md mcp/README.md
git commit -m "docs(mcp): document response handling pattern and docstring standards

- Add comprehensive docstring standard with examples
- Document hybrid response extraction pattern
- Link to architecture documentation"
```

---

## Final Checklist

Before creating PR:

- [ ] All 8 tasks completed
- [ ] All commits follow TDD workflow (RED-GREEN-REFACTOR)
- [ ] All commits passed `make test-unit` and `make quality`
- [ ] All 12 MCP tool docstrings enhanced
- [ ] All 6 domain clients use hybrid pattern
- [ ] Documentation updated
- [ ] No breaking changes introduced
- [ ] Backward compatibility verified

---

## Create Pull Request

```bash
# Ensure branch up to date
git checkout main
git pull origin main
git checkout feat/mcp-response-handling-and-docstrings
git rebase main

# Final quality checks
make test-unit
make quality

# Push and create PR
git push origin feat/mcp-response-handling-and-docstrings

# Create PR with gh CLI
gh pr create \
  --title "feat(mcp): standardize response handling and enhance docstrings" \
  --body "## Summary

This PR implements Option 4 (Hybrid) response handling pattern and massively
improves MCP tool docstrings for better LLM interaction.

## Changes

### Response Handling (Hybrid Pattern)
- Added 3 extraction helpers to BaseAPIClient:
  - \`_extract_list()\` - Simple list extraction with defaults
  - \`_extract_dict()\` - Simple dict extraction with defaults
  - \`_extract_or_raise()\` - Strict validation for critical operations
- Updated 6 domain clients to use hybrid pattern:
  - DataAPIClient
  - TrainingAPIClient
  - OperationsAPIClient
  - IndicatorsAPIClient
  - StrategiesAPIClient
  - SystemAPIClient

### Docstring Enhancements
- Enhanced all 12 MCP tools with comprehensive docstrings:
  - Clear one-line summaries
  - Extended descriptions with context
  - Args with valid values and format examples
  - Returns with complete structure documentation
  - Raises with specific error scenarios
  - Examples with working code
  - See Also with related tools for discovery
  - Notes with behavioral details

### Documentation
- Updated MCP_TOOLS.md with docstring standards
- Updated README with response handling pattern
- Linked to architecture documentation

## Testing
- ✅ All unit tests pass
- ✅ All quality checks pass
- ✅ No breaking changes
- ✅ Backward compatibility maintained

## Related
- Addresses code review feedback from PR #74
- Implements Option 4 (Hybrid) approach from improvement plan"
```

---

## Success Criteria

- [x] 3 extraction methods added to BaseAPIClient
- [x] 6 domain clients updated with hybrid pattern
- [x] 12 MCP tool docstrings enhanced to full standard
- [x] All unit tests pass
- [x] All quality checks pass
- [x] Documentation updated
- [x] Backward compatibility maintained
- [x] Zero breaking changes
- [x] PR created and ready for review

---

**End of Implementation Plan**
