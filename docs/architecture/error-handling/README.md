# Error Handling Documentation

This directory contains comprehensive documentation for the KTRDR error handling system.

## Overview

KTRDR uses a structured error hierarchy to provide clear, actionable error messages across all system layers. The error system is designed with three key principles:

1. **Clarity**: Errors include context about what went wrong and where
2. **Actionability**: Errors provide suggestions for how to fix the problem
3. **Structure**: Errors are serializable for API responses and programmatic handling

## Documentation Files

### [Error Handling Architecture](error-handling-architecture.md)

**Comprehensive architecture guide** covering:
- Error hierarchy and when to use each type
- Error flow through system layers (Core → API → CLI)
- HTTP status code mapping
- Error serialization (`to_dict()` and `format_user_message()`)
- Logging best practices
- Testing error handling
- Migration guide for ConfigurationError vs ValidationError

**Start here** for understanding the overall error handling design.

### [Error Classes Reference](error-classes.md)

**Detailed reference for each error class** including:
- All error classes in the hierarchy
- When to use each class
- Code examples
- API response examples
- Error code conventions

**Use this** as a reference when deciding which error class to use or when looking up specific error details.

## Quick Reference

### When to Use Each Error Type

| Error Type | Use When | Fix Requires | Example |
|------------|----------|--------------|---------|
| **ConfigurationError** | Configuration file/YAML issues | **Editing a file** | Strategy YAML missing feature_id |
| **ValidationError** | API request parameter issues | **Changing request parameters** | Invalid timeframe in API request |
| **DataError** | Data availability/source issues | **Data source action** | IB Gateway unreachable |
| **IndicatorError** | Indicator calculation issues | **Adjusting parameters/data** | Insufficient data points for RSI |

### Common Error Codes

- `STRATEGY-MissingFeatureId`: Indicator missing feature_id
- `STRATEGY-DuplicateFeatureId`: Duplicate feature_id found
- `STRATEGY-ValidationFailed`: Strategy validation failed
- `VALIDATION-InvalidTimeframe`: Invalid timeframe parameter
- `DATA-NoDataAvailable`: No data for symbol/timeframe
- `SERVICE-ConnectionFailed`: Cannot connect to host service

### HTTP Status Code Mapping

- `ConfigurationError` → **400** Bad Request (configuration/file issue)
- `ValidationError` → **422** Unprocessable Entity (request parameter issue)
- `DataError` → **503** Service Unavailable (data source issue)
- `IndicatorError` → **400** Bad Request (calculation issue)

## Key Design Decisions

### ConfigurationError vs ValidationError

**Decision**: Strategy YAML validation errors use `ConfigurationError`, not `ValidationError`.

**Rationale**: Strategy YAML files are **configuration**, not API request parameters. The fix requires editing the YAML file, not changing request parameters.

**Documentation**: See [ADR-0001: Error Types for API Responses](../decisions/0001-error-types-for-api-responses.md)

## Usage Examples

### Raising a ConfigurationError

```python
from ktrdr.errors import ConfigurationError

# Using factory method
raise ConfigurationError.missing_feature_id(
    indicator_type="rsi",
    indicator_index=0,
    file_path="strategies/my_strategy.yaml"
)

# Manual construction
raise ConfigurationError(
    message="Strategy validation failed: 1 error(s) found",
    error_code="STRATEGY-ValidationFailed",
    context={"strategy_name": "mtf_forex_neural"},
    details={"errors": [...]},
    suggestion="Fix the validation errors:\n..."
)
```

### API Endpoint Error Handling

```python
from ktrdr.errors import ConfigurationError, DataError, ValidationError
from fastapi import HTTPException
from ktrdr.logging import get_logger

logger = get_logger(__name__)

@router.post("/training/start")
async def start_training(...):
    try:
        result = await training_service.start_training(...)
        return result

    except ConfigurationError as e:
        # Log with full context before responding
        logger.error(f"Configuration error: {e.format_user_message()}")
        # Return structured error (400 Bad Request)
        raise HTTPException(status_code=400, detail=e.to_dict()) from e

    except DataError as e:
        logger.error(f"Data error: {e.format_user_message()}")
        # Return structured error (503 Service Unavailable)
        raise HTTPException(status_code=503, detail=e.to_dict()) from e

    except ValidationError as e:
        logger.error(f"Validation error: {e.format_user_message()}")
        # Return structured error (422 Unprocessable Entity)
        raise HTTPException(status_code=422, detail=e.to_dict()) from e
```

### CLI Error Display

```python
import httpx
from rich.console import Console

async def execute_operation(...):
    try:
        operation_id = await start_operation(...)

    except httpx.HTTPStatusError as e:
        # Parse structured error from API response
        try:
            response_json = e.response.json()
            # FastAPI puts error detail in "detail" field
            error_detail = response_json.get("detail", response_json)

            if isinstance(error_detail, dict) and "error_code" in error_detail:
                # Display structured error
                console.print("[red bold]Configuration Error:[/red bold]")
                console.print(f"  {error_detail['message']}")
                console.print(f"  Code: {error_detail['error_code']}")

                if error_detail.get("context"):
                    console.print("  Context:")
                    for key, value in error_detail["context"].items():
                        console.print(f"    {key}: {value}")

                if error_detail.get("suggestion"):
                    console.print("\n[yellow]Suggestion:[/yellow]")
                    console.print(f"  {error_detail['suggestion']}")
        except Exception:
            # Fallback to simple error message
            console.print(f"[red]Error: {e}[/red]")
```

## Testing Error Handling

### Unit Tests - Error Creation

```python
def test_configuration_error_serialization():
    """Test ConfigurationError converts to dict for API responses."""
    error = ConfigurationError(
        message="Missing feature_id",
        error_code="STRATEGY-MissingFeatureId",
        context={"file": "strategy.yaml"},
        suggestion="Add feature_id"
    )

    result = error.to_dict()

    assert result["message"] == "Missing feature_id"
    assert result["error_code"] == "STRATEGY-MissingFeatureId"
    assert "suggestion" in result
```

### Integration Tests - API Error Flow

```python
async def test_api_returns_structured_error():
    """Test API endpoint returns structured ConfigurationError."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "/api/v1/trainings/start",
            json={"strategy": "invalid_strategy.yaml", ...}
        )

        assert response.status_code == 400
        error_detail = response.json()["detail"]
        assert error_detail["error_code"] == "STRATEGY-ValidationFailed"
        assert "suggestion" in error_detail
```

## Related Documentation

### Architecture Decisions

- [ADR-0001: Error Types for API Responses](../decisions/0001-error-types-for-api-responses.md) - ConfigurationError vs ValidationError decision

### Implementation

- [ktrdr/errors/exceptions.py](../../ktrdr/errors/exceptions.py) - Error class implementations
- [ktrdr/api/endpoints/](../../ktrdr/api/endpoints/) - API error handling examples
- [ktrdr/cli/operation_executor.py](../../ktrdr/cli/operation_executor.py) - CLI error display

### Testing

- [tests/unit/test_configuration_error.py](../../tests/unit/test_configuration_error.py) - ConfigurationError tests
- [tests/unit/api/test_strategy_error_responses.py](../../tests/unit/api/test_strategy_error_responses.py) - API error response tests
- [tests/unit/config/test_validation_errors.py](../../tests/unit/config/test_validation_errors.py) - Validation error tests

## Contributing

When adding new error types or modifying error handling:

1. **Update this documentation** with the new error class and examples
2. **Add tests** for error creation, serialization, and API flow
3. **Update ADRs** if the change affects architectural decisions
4. **Update error class docstrings** in `ktrdr/errors/exceptions.py`

## Questions?

For questions about error handling:

1. Check the [Error Handling Architecture](error-handling-architecture.md) guide
2. Review the [Error Classes Reference](error-classes.md)
3. Look at existing tests for examples
4. Check the [ADR-0001](../decisions/0001-error-types-for-api-responses.md) for design rationale
