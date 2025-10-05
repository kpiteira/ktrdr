# MCP Improvements Implementation Plan

**Date:** 2025-10-05
**Context:** Post-PR #74 improvements based on code review feedback

## Overview

This plan addresses two critical improvements to the MCP infrastructure:

1. **Standardize Response Handling Patterns** - Ensure consistent API response processing across all domain clients
2. **OpenAPI Spec Validation** - Automated validation of MCP tool signatures against backend API contracts

---

## Part 1: Response Handling Standardization

### Current State Analysis

The backend uses a **standardized response envelope**:

```python
class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T]
    error: Optional[ErrorResponse]
```

**However, MCP clients handle responses inconsistently:**

| Client | Method | Pattern | Issue |
|--------|--------|---------|-------|
| `DataAPIClient` | `get_symbols()` | `response.get("data", [])` | ✅ Extracts data |
| `DataAPIClient` | `get_cached_data()` | `return response` | ❌ Returns full envelope |
| `IndicatorsAPIClient` | `list_indicators()` | `response.get("data", [])` | ✅ Extracts data |
| `StrategiesAPIClient` | `list_strategies()` | `return response` | ❌ Returns full envelope |
| `TrainingAPIClient` | `list_trained_models()` | `response.get("models", [])` | ❌ Inconsistent key name |

**Problems:**
- MCP tools don't know if they get `{success, data, error}` or just `data`
- Different extraction patterns (`.get("data")` vs `.get("models")`)
- No centralized error handling
- Hard to refactor when backend changes response structure

---

### Option Analysis

#### Option 1: Always Extract Data Field

**Approach:** All client methods extract and return only the `data` field.

**Implementation:**
```python
# BaseAPIClient
class BaseAPIClient:
    def _extract_data(self, response: dict, default: Any = None) -> Any:
        """Extract data field from standardized ApiResponse envelope"""
        return response.get("data", default)

# Usage in clients
class DataAPIClient(BaseAPIClient):
    async def get_symbols(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/symbols")
        return self._extract_data(response, default=[])
```

**Pros:**
- ✅ Simple and predictable
- ✅ MCP tools always get clean data, never envelopes
- ✅ Single method to maintain
- ✅ Easy to understand for new developers

**Cons:**
- ❌ Loses `success` and `error` metadata
- ❌ Can't distinguish between "empty result" and "error with empty data"
- ❌ Harder to implement client-side retry logic based on error types
- ❌ No access to backend warnings/metadata

**Best for:** Simple use cases where errors are exceptions, not data

---

#### Option 2: Typed Response Extractors

**Approach:** Provide type-specific extractors with clear intent.

**Implementation:**
```python
# BaseAPIClient
class BaseAPIClient:
    def _extract_list(self, response: dict) -> list[dict[str, Any]]:
        """Extract list data with standard fallback to empty list"""
        return response.get("data", [])

    def _extract_dict(self, response: dict) -> dict[str, Any]:
        """Extract dict data with standard fallback to empty dict"""
        return response.get("data", {})

    def _extract_optional(self, response: dict) -> Any | None:
        """Extract data that may be None"""
        return response.get("data")

# Usage in clients
class IndicatorsAPIClient(BaseAPIClient):
    async def list_indicators(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/indicators/")
        return self._extract_list(response)

class StrategiesAPIClient(BaseAPIClient):
    async def list_strategies(self) -> dict[str, Any]:
        response = await self._request("GET", "/strategies/")
        return self._extract_dict(response)
```

**Pros:**
- ✅ Type-safe with clear intent (`list` vs `dict`)
- ✅ Consistent fallback values (empty list vs empty dict)
- ✅ Self-documenting code
- ✅ Still simple for MCP tools

**Cons:**
- ❌ Still loses `success` and `error` metadata
- ❌ Multiple methods to remember
- ❌ No access to backend warnings

**Best for:** When you want type safety but still prefer simplicity

---

#### Option 3: Response Objects with Metadata

**Approach:** Return structured response objects that preserve all metadata.

**Implementation:**
```python
# New response wrapper classes
from dataclasses import dataclass
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

@dataclass
class ClientResponse(Generic[T]):
    """Wrapper for API responses preserving all metadata"""
    success: bool
    data: T
    error: Optional[dict[str, Any]] = None

    def unwrap(self) -> T:
        """Get data, raising exception if not successful"""
        if not self.success:
            raise ClientError(self.error)
        return self.data

    def unwrap_or(self, default: T) -> T:
        """Get data or default if not successful"""
        return self.data if self.success else default

# BaseAPIClient
class BaseAPIClient:
    def _wrap_response(self, response: dict, data_key: str = "data") -> ClientResponse:
        """Wrap raw API response in structured ClientResponse"""
        return ClientResponse(
            success=response.get("success", True),
            data=response.get(data_key),
            error=response.get("error")
        )

# Usage in clients
class DataAPIClient(BaseAPIClient):
    async def get_symbols(self) -> ClientResponse[list[dict[str, Any]]]:
        response = await self._request("GET", "/symbols")
        return self._wrap_response(response)

# MCP tools can choose how to handle
async def get_available_symbols():
    response = await client.data.get_symbols()

    # Option A: Just get data (raises on error)
    symbols = response.unwrap()

    # Option B: Get data or default
    symbols = response.unwrap_or([])

    # Option C: Check success explicitly
    if response.success:
        return response.data
    else:
        logger.error("Failed to get symbols", error=response.error)
        return []
```

**Pros:**
- ✅ Preserves all metadata (success, error, warnings)
- ✅ Flexible handling (unwrap, unwrap_or, explicit checks)
- ✅ Can implement retry logic based on error types
- ✅ Type-safe with generics
- ✅ Chainable operations possible
- ✅ Backend can add metadata without breaking clients

**Cons:**
- ❌ More complex for simple cases
- ❌ Requires MCP tools to understand response objects
- ❌ More boilerplate in client code
- ❌ Steeper learning curve

**Best for:** Production systems needing robust error handling and metadata access

---

#### Option 4: Hybrid Approach (Recommended)

**Approach:** Default to simple extraction, but provide access to full response when needed.

**Implementation:**
```python
# BaseAPIClient
class BaseAPIClient:
    # Simple extractors (most common case)
    def _extract_list(self, response: dict, key: str = "data") -> list[dict[str, Any]]:
        """Extract list data from response"""
        data = response.get(key, [])
        if not isinstance(data, list):
            logger.warning(f"Expected list for key '{key}', got {type(data)}")
            return []
        return data

    def _extract_dict(self, response: dict, key: str = "data") -> dict[str, Any]:
        """Extract dict data from response"""
        data = response.get(key, {})
        if not isinstance(data, dict):
            logger.warning(f"Expected dict for key '{key}', got {type(data)}")
            return {}
        return data

    # Advanced: Full response access
    def _check_response(self, response: dict) -> bool:
        """Check if response indicates success"""
        return response.get("success", True)

    def _get_error(self, response: dict) -> Optional[dict[str, Any]]:
        """Extract error from response if present"""
        return response.get("error")

    # Combination: Extract with validation
    def _extract_or_raise(self, response: dict, key: str = "data") -> Any:
        """Extract data, raising exception if response indicates failure"""
        if not self._check_response(response):
            error = self._get_error(response)
            raise KTRDRAPIError(
                f"API request failed: {error.get('message', 'Unknown error')}",
                details=error
            )
        return response.get(key)

# Usage examples
class DataAPIClient(BaseAPIClient):
    # Simple case: just extract data
    async def get_symbols(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/symbols")
        return self._extract_list(response)

    # Critical case: validate before extracting
    async def load_data_operation(self, **kwargs) -> dict[str, Any]:
        response = await self._request("POST", "/data/load", json=kwargs)
        return self._extract_or_raise(response)  # Raises on failure

    # Complex case: need full response
    async def get_cached_data(self, **kwargs) -> dict[str, Any]:
        response = await self._request("GET", f"/data/{kwargs['symbol']}/{kwargs['timeframe']}")

        # Apply client-side limiting if needed
        if limit := kwargs.get('limit'):
            # ... truncation logic ...
            pass

        # Return full response for backward compatibility
        return response
```

**Pros:**
- ✅ Simple for common cases (90% of usage)
- ✅ Power available when needed (10% of usage)
- ✅ Gradual migration path
- ✅ Type validation built-in
- ✅ Clear naming (`_extract` vs `_extract_or_raise`)
- ✅ Backward compatible

**Cons:**
- ❌ Slightly more methods to learn
- ❌ Need to choose right method for use case

**Best for:** Real-world projects with both simple and complex needs

---

### Recommendation: Option 4 (Hybrid)

**Rationale:**
1. **Pragmatic**: Handles 90% of cases simply, 10% with power tools
2. **Migration-friendly**: Can update clients incrementally
3. **Type-safe**: Validates data types at extraction
4. **Flexible**: Tools can choose validation level
5. **Production-ready**: Built-in error handling and logging

---

## Part 2: OpenAPI Spec Validation

### Goal

**Automatically validate that MCP tool signatures match backend API contracts** to prevent bugs like the `start_training` parameter mismatch.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│ Backend API (FastAPI)                                   │
│  └─ Auto-generates OpenAPI spec at /openapi.json       │
└─────────────────────────────────────────────────────────┘
                        │
                        │ HTTP GET
                        ▼
┌─────────────────────────────────────────────────────────┐
│ Validation Script (scripts/validate_mcp_tools.py)      │
│  1. Fetch OpenAPI spec from backend                     │
│  2. Extract MCP tool signatures via introspection       │
│  3. Map tools to endpoints                              │
│  4. Compare signatures                                   │
│  5. Report mismatches                                    │
└─────────────────────────────────────────────────────────┘
                        │
                        │ Exit code
                        ▼
            ┌───────────────────────┐
            │ CI Pipeline           │
            │  - Pre-commit hook    │
            │  - GitHub Actions     │
            └───────────────────────┘
```

### Implementation Phases

#### Phase 1: Core Validation Script

**File:** `scripts/validate_mcp_tools.py`

**Features:**
- Fetch OpenAPI spec from running backend
- Introspect MCP server for `@mcp.tool()` decorated functions
- Map tool names to API endpoints
- Validate parameter names, types, and requirements
- Generate detailed error reports

**Exit codes:**
- `0`: All tools valid
- `1`: Validation errors found
- `2`: Backend unreachable

#### Phase 2: Tool-to-Endpoint Mapping

**File:** `mcp/src/tool_mappings.py`

```python
"""
Mapping between MCP tools and backend API endpoints.

This is the source of truth for validation.
"""

TOOL_ENDPOINT_MAP = {
    'start_training': {
        'method': 'POST',
        'path': '/trainings/start',
        'validate_request_body': True,
    },
    'trigger_data_loading': {
        'method': 'POST',
        'path': '/data/load',
        'validate_request_body': True,
    },
    'get_available_symbols': {
        'method': 'GET',
        'path': '/symbols',
        'validate_request_body': False,
    },
    'get_available_indicators': {
        'method': 'GET',
        'path': '/indicators/',
        'validate_request_body': False,
    },
    'get_available_strategies': {
        'method': 'GET',
        'path': '/strategies/',
        'validate_request_body': False,
    },
    'get_market_data': {
        'method': 'GET',
        'path': '/data/{symbol}/{timeframe}',
        'validate_request_body': False,
        'path_params': ['symbol', 'timeframe'],
    },
}
```

#### Phase 3: Type Validation

**Challenges:**
- OpenAPI types (string, integer, array) vs Python types (str, int, list)
- Generic types (List[str] vs array of strings)
- Optional vs required parameters

**Solution:**
```python
# Type mapping with validation
TYPE_VALIDATORS = {
    'string': (str, lambda x: isinstance(x, str)),
    'integer': (int, lambda x: isinstance(x, int)),
    'number': ((int, float), lambda x: isinstance(x, (int, float))),
    'boolean': (bool, lambda x: isinstance(x, bool)),
    'array': (list, lambda x: isinstance(x, list)),
    'object': (dict, lambda x: isinstance(x, dict)),
}

def validate_type_hint(python_type, openapi_type: str) -> bool:
    """Check if Python type hint matches OpenAPI type"""
    expected_python_type, validator = TYPE_VALIDATORS.get(openapi_type, (None, None))

    if expected_python_type is None:
        return False  # Unknown type

    # Handle typing module types (List[str], Optional[int], etc.)
    origin = get_origin(python_type)
    if origin is list and openapi_type == 'array':
        return True
    if origin is Union:  # Optional is Union[X, None]
        args = get_args(python_type)
        if type(None) in args:
            # It's Optional[X], check the non-None type
            non_none_types = [t for t in args if t is not type(None)]
            return any(validate_type_hint(t, openapi_type) for t in non_none_types)

    return isinstance(expected_python_type, type) and issubclass(python_type, expected_python_type)
```

#### Phase 4: CI Integration

**Pre-commit Hook** (`.pre-commit-config.yaml`):
```yaml
repos:
  - repo: local
    hooks:
      - id: validate-mcp-tools
        name: Validate MCP tool signatures against OpenAPI
        entry: bash -c 'scripts/validate_mcp_pre_commit.sh'
        language: system
        pass_filenames: false
        files: ^(mcp/src/server\.py|mcp/src/clients/.*\.py)$
        stages: [commit]
```

**Pre-commit script** (`scripts/validate_mcp_pre_commit.sh`):
```bash
#!/bin/bash
set -e

echo "🔍 Validating MCP tools against OpenAPI spec..."

# Check if backend is running
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  Backend not running - skipping validation"
    echo "   (Run ./start_ktrdr.sh to enable pre-commit validation)"
    exit 0  # Don't block commit if backend is down
fi

# Run validation
if uv run python scripts/validate_mcp_tools.py; then
    echo "✅ MCP tool validation passed"
    exit 0
else
    echo "❌ MCP tool validation failed"
    echo "   Fix signature mismatches before committing"
    exit 1
fi
```

**GitHub Actions** (`.github/workflows/mcp-validation.yml`):
```yaml
name: MCP Tool Validation

on:
  pull_request:
    paths:
      - 'mcp/src/server.py'
      - 'mcp/src/clients/**'
      - 'ktrdr/api/endpoints/**'
  push:
    branches: [main]

jobs:
  validate-mcp-tools:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Start backend
        run: |
          ./start_ktrdr.sh &
          # Wait for backend to be ready
          for i in {1..30}; do
            if curl -s http://localhost:8000/health > /dev/null; then
              echo "Backend ready"
              break
            fi
            echo "Waiting for backend... ($i/30)"
            sleep 2
          done

      - name: Validate MCP tools
        run: |
          uv run python scripts/validate_mcp_tools.py

      - name: Upload validation report
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: mcp-validation-report
          path: mcp-validation-report.json
```

#### Phase 5: Enhanced Error Reporting

**JSON Report Format** (`mcp-validation-report.json`):
```json
{
  "timestamp": "2025-10-05T10:30:00Z",
  "backend_version": "1.0.7.2",
  "total_tools": 12,
  "validated_tools": 10,
  "errors": [
    {
      "tool": "start_training",
      "endpoint": "POST /trainings/start",
      "issues": [
        {
          "type": "type_mismatch",
          "parameter": "timeframes",
          "expected": "array",
          "actual": "str",
          "suggestion": "Change parameter type from 'str' to 'list[str]'"
        },
        {
          "type": "missing_parameter",
          "parameter": "strategy_name",
          "required": true,
          "suggestion": "Add required parameter 'strategy_name: str' to tool signature"
        }
      ]
    }
  ],
  "warnings": [
    {
      "tool": "get_market_data",
      "message": "Tool has extra parameters not used by backend endpoint",
      "extra_params": ["include_extended"]
    }
  ]
}
```

**Terminal Output:**
```
🔍 Validating MCP tools against OpenAPI spec...
📡 Backend: http://localhost:8000 (v1.0.7.2)
📋 Found 12 MCP tools

✅ check_backend_health
✅ get_available_symbols
✅ get_available_indicators
❌ start_training
   └─ POST /trainings/start
      ❌ Type mismatch: 'timeframes'
         Expected: list[str] (array)
         Actual:   str
         Fix: Change parameter type to list[str]

      ❌ Missing parameter: 'strategy_name'
         Required: Yes
         Fix: Add 'strategy_name: str' to tool signature
✅ trigger_data_loading
⚠️  get_market_data
   └─ Has extra parameter 'include_extended' not in backend API
      (This may be intentional for client-side processing)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Summary:
  ✅ 10 tools validated successfully
  ❌ 1 tool has errors
  ⚠️  1 tool has warnings

❌ Validation failed! Please fix errors before committing.
📄 Detailed report: mcp-validation-report.json
```

---

## Implementation Timeline

### Sprint 1: Response Handling (Week 1)

**Day 1-2: Analysis & Design**
- [ ] Audit all current response handling patterns
- [ ] Document all edge cases
- [ ] Choose extraction methods (hybrid approach)
- [ ] Write ADR (Architecture Decision Record)

**Day 3-4: Implementation**
- [ ] Add extraction methods to `BaseAPIClient`
- [ ] Update all domain clients to use new patterns
- [ ] Write comprehensive tests
- [ ] Update facade delegation methods if needed

**Day 5: Testing & Documentation**
- [ ] Run full test suite
- [ ] Add integration tests
- [ ] Update client documentation
- [ ] Update MCP_TOOLS.md with examples

**Deliverables:**
- Updated `BaseAPIClient` with extraction methods
- All clients using consistent patterns
- 100% test coverage for extraction logic
- Documentation updates

---

### Sprint 2: OpenAPI Validation (Week 2)

**Day 1-2: Core Script**
- [ ] Create `scripts/validate_mcp_tools.py`
- [ ] Implement OpenAPI spec fetching
- [ ] Implement tool introspection
- [ ] Implement basic signature validation

**Day 3: Type Validation**
- [ ] Implement Python ↔ OpenAPI type mapping
- [ ] Handle generics (List[str], Optional[int])
- [ ] Add type validation tests
- [ ] Handle edge cases (Union types, etc.)

**Day 4: CI Integration**
- [ ] Create pre-commit hook
- [ ] Create GitHub Actions workflow
- [ ] Test with intentionally broken signature
- [ ] Add validation report generation

**Day 5: Polish & Documentation**
- [ ] Enhance error messages
- [ ] Add suggestions to error reports
- [ ] Write validation documentation
- [ ] Create troubleshooting guide

**Deliverables:**
- Working validation script
- CI pipeline integration
- Comprehensive error reporting
- Documentation and guides

---

## Testing Strategy

### Response Handling Tests

```python
# tests/unit/mcp/test_response_extraction.py
class TestResponseExtraction:
    def test_extract_list_with_valid_data(self):
        """Test extracting list from valid response"""
        response = {"success": True, "data": [{"id": 1}, {"id": 2}]}
        client = BaseAPIClient("http://test:8000")

        result = client._extract_list(response)

        assert result == [{"id": 1}, {"id": 2}]

    def test_extract_list_with_missing_data(self):
        """Test extracting list from response without data field"""
        response = {"success": True}
        client = BaseAPIClient("http://test:8000")

        result = client._extract_list(response)

        assert result == []  # Falls back to empty list

    def test_extract_dict_with_wrong_type(self):
        """Test extracting dict when data is actually a list"""
        response = {"success": True, "data": [1, 2, 3]}
        client = BaseAPIClient("http://test:8000")

        with caplog.at_level(logging.WARNING):
            result = client._extract_dict(response)

        assert result == {}  # Falls back to empty dict
        assert "Expected dict" in caplog.text

    def test_extract_or_raise_with_error_response(self):
        """Test extraction that raises on error response"""
        response = {
            "success": False,
            "error": {"code": "VAL_001", "message": "Invalid input"}
        }
        client = BaseAPIClient("http://test:8000")

        with pytest.raises(KTRDRAPIError) as exc:
            client._extract_or_raise(response)

        assert "Invalid input" in str(exc.value)
```

### OpenAPI Validation Tests

```python
# tests/unit/validation/test_openapi_validator.py
class TestSignatureValidation:
    def test_valid_signature_passes(self):
        """Test that matching signatures pass validation"""
        tool_sig = inspect.signature(mock_tool)
        openapi_params = {
            "symbols": {"type": "array", "required": True},
            "timeframes": {"type": "array", "required": True},
        }

        errors = validate_signature(tool_sig, {}, openapi_params)

        assert errors == []

    def test_type_mismatch_detected(self):
        """Test detection of type mismatches"""
        # Tool has str, backend expects array
        tool_sig = inspect.signature(lambda symbols: str: None)
        openapi_params = {
            "symbols": {"type": "array", "required": True}
        }

        errors = validate_signature(tool_sig, {"symbols": str}, openapi_params)

        assert len(errors) == 1
        assert "type mismatch" in errors[0].lower()
        assert "symbols" in errors[0]

    def test_missing_parameter_detected(self):
        """Test detection of missing required parameters"""
        tool_sig = inspect.signature(lambda symbols: None)  # Missing strategy_name
        openapi_params = {
            "symbols": {"type": "array", "required": True},
            "strategy_name": {"type": "string", "required": True},
        }

        errors = validate_signature(tool_sig, {"symbols": list}, openapi_params)

        assert len(errors) == 1
        assert "missing" in errors[0].lower()
        assert "strategy_name" in errors[0]
```

---

## Success Criteria

### Response Handling
- [ ] All domain clients use consistent extraction patterns
- [ ] 100% test coverage for extraction methods
- [ ] Zero breaking changes to MCP tool interfaces
- [ ] Documentation updated with examples
- [ ] All existing tests pass

### OpenAPI Validation
- [ ] Validation script detects all parameter mismatches
- [ ] Validation script detects all type mismatches
- [ ] CI pipeline fails when signatures diverge
- [ ] Pre-commit hook provides helpful error messages
- [ ] Validation runs in <5 seconds
- [ ] False positive rate <5%

---

## Risk Assessment

### Response Handling

**Low Risk:**
- Adding new methods to `BaseAPIClient` (backward compatible)
- Updating clients one at a time (incremental)

**Medium Risk:**
- Changing return types of existing methods (breaking change)
- Mitigation: Use deprecation warnings, update in phases

**High Risk:**
- None identified

### OpenAPI Validation

**Low Risk:**
- Running validation in CI (doesn't affect runtime)
- Pre-commit hook (can be bypassed if needed)

**Medium Risk:**
- False positives blocking commits
- Mitigation: Whitelist mechanism for known exceptions

**High Risk:**
- Backend not running during CI (validation fails)
- Mitigation: Graceful fallback, clear error messages

---

## Future Enhancements

1. **Auto-generate MCP tools from OpenAPI spec**
   - Eliminate manual implementation entirely
   - Generate type-safe client code
   - Keep tools always in sync

2. **Runtime validation in MCP server**
   - Validate requests before sending to backend
   - Fail fast with clear errors
   - Reduce backend load

3. **Contract testing**
   - Pact-style contract tests
   - Test MCP server against recorded API responses
   - Detect backend breaking changes early

4. **OpenAPI spec versioning**
   - Track OpenAPI spec changes over time
   - Detect breaking changes automatically
   - Generate migration guides

---

## References

- Backend API: `ktrdr/api/models/base.py` - Standard response envelope
- MCP Clients: `mcp/src/clients/*.py` - Domain-specific API clients
- OpenAPI Spec: `http://localhost:8000/api/v1/openapi.json`
- FastAPI Docs: https://fastapi.tiangolo.com/advanced/extending-openapi/

---

## IMPLEMENTATION WORKFLOW (UPDATED)

### Branch & Development Requirements

**Branch Name:** `feat/mcp-response-handling-and-docstrings`

**TDD Workflow (MANDATORY):**
- ✅ Write tests FIRST for every change (RED phase)
- ✅ Implement minimal code to pass tests (GREEN phase)
- ✅ Run `make test-unit` before EVERY commit
- ✅ Run `make quality` before EVERY commit
- ✅ One logical change per commit
- ✅ NEVER commit failing tests or quality checks

---

### Sprint 1 Detailed: Response Handling + Docstrings (5-6 days)

#### Setup (30 minutes)

```bash
git checkout main
git pull origin main
git checkout -b feat/mcp-response-handling-and-docstrings
git status  # Verify clean
```

#### Day 1: Planning & Test Design

**No commits - design phase only**

Tasks:
- [ ] Audit current response handling in all clients
- [ ] Design extraction method signatures
- [ ] Write test plan for each extraction method
- [ ] Design docstring template with all required sections

Deliverable: Test plan document (no code changes)

#### Day 2: Extraction Methods (TDD)

**Commit 1: Add extraction methods to BaseAPIClient**

**RED Phase:**
```bash
# Create test file
touch tests/unit/mcp/test_base_client_extraction.py

# Write comprehensive tests (see plan for full list):
# - _extract_list() with valid/invalid/missing data
# - _extract_dict() with all scenarios  
# - _check_response() 
# - _get_error()
# - _extract_or_raise() with errors

# Run tests - should FAIL
uv run pytest tests/unit/mcp/test_base_client_extraction.py -v
# Expected: All tests FAIL (no implementation yet)
```

**GREEN Phase:**
```bash
# Implement methods in mcp/src/clients/base.py
# Add:
# - _extract_list(response, key="data")
# - _extract_dict(response, key="data")
# - _check_response(response)
# - _get_error(response)
# - _extract_or_raise(response, key="data")

# Run tests - should PASS
uv run pytest tests/unit/mcp/test_base_client_extraction.py -v
# Expected: All tests PASS

# Verify no regressions
make test-unit
# Expected: 1472+ tests pass

# Quality checks
make quality
# Expected: All checks pass
```

**Commit:**
```bash
git add mcp/src/clients/base.py tests/unit/mcp/test_base_client_extraction.py
git commit -m "feat(mcp): add hybrid response extraction methods to BaseAPIClient

- Add _extract_list() with type validation and empty list fallback
- Add _extract_dict() with type validation and empty dict fallback  
- Add _check_response() to validate success field
- Add _get_error() to extract error information
- Add _extract_or_raise() for critical operations that should fail fast
- Include comprehensive unit tests with 100% coverage
- All methods include type validation and logging
- Follows TDD methodology - tests written first

Tests: 25 new tests added, all passing
Quality: lint ✓ format ✓ typecheck ✓"
```

#### Day 3: Update Domain Clients (TDD - 4 commits)

**For EACH client (DataAPIClient, IndicatorsAPIClient, StrategiesAPIClient, TrainingAPIClient):**

**Pattern (repeat 4 times):**

**RED Phase:**
```bash
# Update tests/unit/mcp/test_<client>.py
# Add tests verifying:
# - Methods use _extract_list() or _extract_dict()
# - Critical operations use _extract_or_raise()
# - Proper error handling

uv run pytest tests/unit/mcp/test_<client>.py -v
# Expected: New tests FAIL
```

**GREEN Phase:**
```bash
# Update mcp/src/clients/<client>.py
# Replace manual extraction with helper methods

uv run pytest tests/unit/mcp/test_<client>.py -v
# Expected: All tests PASS

make test-unit
# Expected: All tests pass

make quality  
# Expected: All checks pass
```

**Commit (one per client):**
```bash
git add mcp/src/clients/<client>.py tests/unit/mcp/test_<client>.py
git commit -m "refactor(mcp): standardize <ClientName> response handling

- Use _extract_list() for list endpoints (get_symbols, list_indicators, etc.)
- Use _extract_dict() for dict endpoints (get_strategies, etc.)
- Use _extract_or_raise() for critical operations
- Update tests to verify consistent extraction patterns
- All existing tests continue to pass

Tests: Updated <N> tests, added <M> new assertions
Quality: lint ✓ format ✓ typecheck ✓"
```

**Result: 4 commits total (one per client)**

#### Day 4-5: Enhance ALL MCP Tool Docstrings (TDD)

**Commit 5: Add docstring validation tests**

**RED Phase:**
```bash
# Create tests/unit/mcp/test_tool_docstrings.py
# Write tests that verify each tool has:
# - Non-empty docstring
# - Args section with all parameters documented
# - Returns section with structure description
# - Raises section for error handling
# - Example section with working code
# - See Also section (optional but encouraged)

uv run pytest tests/unit/mcp/test_tool_docstrings.py -v
# Expected: Tests FAIL (docstrings incomplete)
```

**GREEN Phase:**
```bash
# Already implemented - docstrings exist
# But tests verify completeness

uv run pytest tests/unit/mcp/test_tool_docstrings.py -v
# Will FAIL for incomplete docstrings
```

**Commit:**
```bash
git add tests/unit/mcp/test_tool_docstrings.py
git commit -m "test(mcp): add docstring completeness validation tests

- Verify all MCP tools have comprehensive docstrings
- Check for required sections (Args, Returns, Raises, Example)
- Validate parameter documentation completeness
- These tests will guide docstring improvements

Tests: 12 tool docstring validation tests
Currently failing - will fix in next commit"
```

**Commit 6: Enhance all docstrings**

**GREEN Phase:**
```bash
# Update mcp/src/server.py
# Enhance ALL 12 tool docstrings using template:
# 1. check_backend_health
# 2. list_operations  
# 3. get_operation_status
# 4. cancel_operation
# 5. get_operation_results
# 6. get_available_symbols
# 7. get_market_data
# 8. get_data_summary
# 9. get_available_indicators
# 10. get_available_strategies
# 11. trigger_data_loading
# 12. start_training

# Each must have:
# - Clear one-line summary
# - Detailed description
# - Complete Args with examples
# - Structured Returns documentation
# - Raises section
# - Working Example code
# - See Also references

uv run pytest tests/unit/mcp/test_tool_docstrings.py -v
# Expected: All tests PASS

make test-unit
# Expected: All tests pass

make quality
# Expected: All checks pass
```

**Commit:**
```bash
git add mcp/src/server.py
git commit -m "docs(mcp): massively improve all MCP tool docstrings for LLM usage

Enhanced all 12 MCP tools with comprehensive docstrings:

Structure (for each tool):
- One-line imperative summary
- Detailed description with use cases  
- Args: Full parameter documentation with type examples
- Returns: Exact structure with field descriptions
- Raises: Error conditions and types
- Example: Complete working code showing typical usage
- See Also: Related tools and workflow guidance

LLM Benefits:
- Exact parameter formats (e.g., timeframes is list not string)
- Complete return structure for accessing nested data
- Clear error handling patterns (exceptions vs response codes)
- End-to-end usage workflows
- Progressive learning (simple to complex)

Tools enhanced:
✓ check_backend_health - System health checking
✓ list_operations - Async operation monitoring  
✓ get_operation_status - Detailed operation tracking
✓ cancel_operation - Operation cancellation
✓ get_operation_results - Result retrieval
✓ get_available_symbols - Symbol discovery
✓ get_market_data - Historical data fetching
✓ get_data_summary - Quick data overview
✓ get_available_indicators - Indicator listing
✓ get_available_strategies - Strategy discovery
✓ trigger_data_loading - Async data loading
✓ start_training - Neural network training

Tests: All docstring validation tests pass
Quality: lint ✓ format ✓ typecheck ✓"
```

#### Day 6: Documentation & Final Testing

**Commit 7: Update documentation**

```bash
# Update mcp/README.md
# - Add "Response Handling Patterns" section
# - Document extraction methods
# - Show when to use each method

# Update mcp/MCP_TOOLS.md  
# - Add "For LLM Developers" section
# - Show docstring quality standards
# - Reference example tools

# Create docs/mcp/RESPONSE_HANDLING_GUIDE.md
# - Detailed guide for developers
# - Examples of each pattern
# - Troubleshooting common issues

make quality
# Expected: All checks pass (markdown formatting)

git add mcp/README.md mcp/MCP_TOOLS.md docs/mcp/
git commit -m "docs(mcp): add response handling and LLM usage guides

- Add Response Handling Patterns to README
- Document extraction method usage and patterns
- Add LLM Developer Guide to MCP_TOOLS.md
- Create comprehensive RESPONSE_HANDLING_GUIDE.md
- Include troubleshooting section

Guides help developers:
- Choose correct extraction method
- Write LLM-friendly docstrings  
- Handle errors consistently
- Debug response parsing issues

Quality: lint ✓ format ✓ typecheck ✓"
```

#### Final PR Creation

```bash
# Push branch
git push -u origin feat/mcp-response-handling-and-docstrings

# Create PR
gh pr create --title "feat(mcp): standardize response handling and enhance docstrings" --body "$(cat <<'PRBODY'
## Summary

Implements Option 4 (Hybrid) response handling pattern and massively improves MCP tool docstrings for LLM usage.

## Changes

### Part 1: Response Handling Standardization

**Problem:** Inconsistent response extraction across domain clients
- Some return full envelope `{success, data, error}`
- Some extract `response["data"]`  
- Some use different keys `response["models"]`
- No standard error handling

**Solution:** Hybrid extraction pattern in BaseAPIClient
- Simple cases: `_extract_list()`, `_extract_dict()`
- Critical cases: `_extract_or_raise()`
- Advanced cases: `_check_response()`, `_get_error()`

**Benefits:**
- ✅ 90% of code stays simple
- ✅ 10% gets robust error handling
- ✅ Type validation built-in
- ✅ Consistent fallback behavior
- ✅ Clear logging for debugging

### Part 2: Massively Improved Docstrings

**Problem:** Minimal docstrings don't teach LLMs how to use tools
- Missing parameter examples
- No return structure documentation
- Unclear error handling
- No usage examples

**Solution:** Comprehensive docstring template applied to all 12 tools

**Each docstring now includes:**
- ✅ Clear one-line summary
- ✅ Detailed description with use cases
- ✅ Args with type examples ("1h", ["AAPL"])
- ✅ Returns with exact structure documentation
- ✅ Raises section for error handling
- ✅ Example with working code
- ✅ See Also for workflow guidance

**LLM Benefits:**
- Knows exact parameter formats (timeframes is list)
- Understands return value structure
- Learns error handling patterns
- Sees complete workflows
- Discovers related tools

## Implementation Methodology

**TDD Workflow:**
- ✅ Tests written FIRST for every change (RED phase)
- ✅ Code implemented to pass tests (GREEN phase)
- ✅ `make test-unit` before every commit (1472+ tests)
- ✅ `make quality` before every commit (lint + format + typecheck)
- ✅ 7 focused commits, one logical change each

**Quality Metrics:**
- ✅ 25+ new tests for extraction methods
- ✅ 12 docstring validation tests
- ✅ All existing tests pass
- ✅ 100% test coverage for new code
- ✅ Zero linting errors
- ✅ Zero type errors

## Testing

### Unit Tests
```bash
make test-unit
# 1472+ tests passing
# New: test_base_client_extraction.py (25 tests)
# New: test_tool_docstrings.py (12 tests)
```

### Manual Verification
```bash
# Start backend
./start_ktrdr.sh

# Test with MCP client/Claude Desktop
# Verify:
# - All tools work as documented
# - Error handling matches docstrings
# - Examples from docstrings execute correctly
```

## Files Changed

**Core Implementation:**
- `mcp/src/clients/base.py` - Extraction methods added
- `mcp/src/clients/data_client.py` - Standardized extraction
- `mcp/src/clients/indicators_client.py` - Standardized extraction
- `mcp/src/clients/strategies_client.py` - Standardized extraction
- `mcp/src/clients/training_client.py` - Standardized extraction
- `mcp/src/server.py` - Enhanced all 12 tool docstrings

**Tests:**
- `tests/unit/mcp/test_base_client_extraction.py` - New (25 tests)
- `tests/unit/mcp/test_tool_docstrings.py` - New (12 tests)
- `tests/unit/mcp/test_data_client.py` - Updated
- `tests/unit/mcp/test_indicators_client.py` - Updated
- `tests/unit/mcp/test_strategies_client.py` - Updated

**Documentation:**
- `mcp/README.md` - Added response handling patterns
- `mcp/MCP_TOOLS.md` - Added LLM developer guide
- `docs/mcp/RESPONSE_HANDLING_GUIDE.md` - New comprehensive guide

## Commits

1. feat(mcp): add hybrid response extraction methods
2. refactor(mcp): standardize DataAPIClient response handling
3. refactor(mcp): standardize IndicatorsAPIClient response handling
4. refactor(mcp): standardize StrategiesAPIClient response handling
5. refactor(mcp): standardize TrainingAPIClient response handling
6. test(mcp): add docstring completeness validation tests
7. docs(mcp): massively improve all MCP tool docstrings
8. docs(mcp): add response handling and LLM usage guides

## Breaking Changes

None - all changes are backward compatible:
- New extraction methods added (not changed)
- Docstrings enhanced (not changed signatures)
- Clients refactored internally (same interface)

## Future Work

- OpenAPI validation (separate PR) - validate signatures automatically
- Response wrapper objects (if needed) - for advanced error handling
- Auto-generate tools from OpenAPI - eliminate manual sync

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
PRBODY
)"
```

**End Result:**
- ✅ 7-8 commits following TDD
- ✅ All tests passing
- ✅ All quality checks passing
- ✅ Comprehensive PR description
- ✅ Ready for review and merge

