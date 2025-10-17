# Error Handling Architecture

## Overview

KTRDR uses a structured error hierarchy to provide clear, actionable error messages across all system layers (data loading, indicators, fuzzy logic, neural networks, API, CLI). The error system is designed with three key principles:

1. **Clarity**: Errors include context about what went wrong and where
2. **Actionability**: Errors provide suggestions for how to fix the problem
3. **Structure**: Errors are serializable for API responses and programmatic handling

## Error Hierarchy

```
Exception (Python built-in)
    │
    └─── KtrdrError (Base class for all KTRDR errors)
            │
            ├─── ConfigurationError (File/config structure issues)
            │       └─── Strategy validation errors
            │       └─── YAML parsing errors
            │       └─── Missing required configuration
            │
            ├─── ValidationError (API request/parameter validation)
            │       └─── Invalid API parameters
            │       └─── Out-of-range values
            │       └─── Type mismatches
            │
            ├─── DataError (Data loading/processing issues)
            │       └─── Missing data
            │       └─── Data format issues
            │       └─── IB Gateway connection problems
            │
            └─── IndicatorError (Indicator calculation issues)
                    └─── Invalid indicator parameters
                    └─── Calculation failures
                    └─── Missing dependencies
```

## When to Use Each Error Type

### ConfigurationError

**Use when**: The problem is with a **configuration file** or **system setup**, not with user input to an API request.

**Examples**:
- Strategy YAML file has missing required fields
- Strategy YAML references non-existent indicators
- Feature IDs are duplicated or invalid format
- Configuration file fails schema validation
- System configuration is incomplete or invalid

**Key characteristic**: The fix requires **editing a file** or **fixing system configuration**, not just changing API parameters.

```python
# Example: Strategy validation
raise ConfigurationError(
    message="Indicator missing required field 'feature_id'",
    error_code="STRATEGY-MissingFeatureId",
    context={
        "file": "strategies/my_strategy.yaml",
        "section": "indicators[0]",
        "indicator_type": "rsi"
    },
    suggestion="Add 'feature_id' to the indicator configuration"
)
```

### ValidationError

**Use when**: The problem is with **API request parameters** or **user input**, not configuration files.

**Examples**:
- API request has invalid parameter value
- Symbol format is incorrect
- Date range is invalid
- Timeframe not supported
- Missing required API parameter

**Key characteristic**: The fix requires **changing request parameters**, not editing files.

```python
# Example: API parameter validation
raise ValidationError(
    message="Invalid timeframe '5x'",
    error_code="VALIDATION-InvalidTimeframe",
    details={
        "provided": "5x",
        "valid_options": ["1m", "5m", "15m", "1h", "1d"]
    }
)
```

### DataError

**Use when**: The problem is with **data availability** or **data processing**.

**Examples**:
- No data available for requested symbol/timeframe
- Data source (IB Gateway) is unreachable
- Data format is corrupted or unexpected
- Insufficient data for calculation
- Data loading timeout

**Key characteristic**: The fix requires **data source action** or **checking data availability**.

```python
# Example: Missing data
raise DataError(
    message="No data available for AAPL 1h",
    error_code="DATA-NoDataAvailable",
    details={
        "symbol": "AAPL",
        "timeframe": "1h",
        "requested_range": "2024-01-01 to 2024-12-31"
    }
)
```

### IndicatorError

**Use when**: The problem is with **indicator calculation** or **indicator configuration**.

**Examples**:
- Indicator calculation fails
- Invalid indicator parameter combination
- Insufficient data points for calculation
- Indicator dependency missing

**Key characteristic**: The fix requires **adjusting indicator parameters** or **providing more data**.

```python
# Example: Calculation failure
raise IndicatorError(
    message="RSI calculation requires at least 14 data points",
    error_code="INDICATOR-InsufficientData",
    details={
        "indicator": "rsi",
        "required_points": 14,
        "available_points": 10
    }
)
```

## Error Flow Through System Layers

### 1. Core Layer (Data, Indicators, Fuzzy, Neural)

**Responsibility**: Raise specific error types with full context

```python
# In ktrdr/config/strategy_validator.py
def _validate_strategy_config(config: dict) -> list[ValidationIssue]:
    """Validate strategy and return issues (no exceptions)."""
    issues = []
    # ... validation logic ...
    return issues

# In ktrdr/api/services/training/context.py
def _validate_strategy(config: dict, name: str) -> None:
    """Validate strategy and raise ConfigurationError on failure."""
    issues = _validate_strategy_config(config, name)
    error_issues = [i for i in issues if i.severity == "error"]

    if error_issues:
        raise ConfigurationError(
            message=f"Strategy validation failed: {len(error_issues)} error(s)",
            error_code="STRATEGY-ValidationFailed",
            context={"strategy_name": name},
            details={"errors": [...]},
            suggestion="Fix the validation errors:\n..."
        )
```

### 2. API Layer (FastAPI Endpoints)

**Responsibility**: Catch errors, log them, convert to HTTP responses

```python
# In ktrdr/api/endpoints/training.py
from ktrdr.errors import ConfigurationError, DataError, ValidationError
from fastapi import HTTPException

@router.post("/start")
async def start_training(...):
    try:
        # Business logic
        result = await training_service.start_training(...)
        return result

    except ConfigurationError as e:
        # Log error with full context before responding
        logger.error(f"Configuration error: {e.format_user_message()}")
        # Return structured error response with all details
        raise HTTPException(status_code=400, detail=e.to_dict()) from e

    except DataError as e:
        logger.error(f"Data error: {e.format_user_message()}")
        raise HTTPException(status_code=503, detail=e.to_dict()) from e

    except ValidationError as e:
        logger.error(f"Validation error: {e.format_user_message()}")
        raise HTTPException(status_code=422, detail=e.to_dict()) from e
```

**HTTP Status Code Mapping**:
- `ConfigurationError` → 400 Bad Request (configuration/file issue)
- `ValidationError` → 422 Unprocessable Entity (request parameter issue)
- `DataError` → 503 Service Unavailable (data source issue)
- `IndicatorError` → 400 Bad Request (calculation issue)

### 3. CLI Layer (Click Commands)

**Responsibility**: Parse structured errors and display user-friendly messages

```python
# In ktrdr/cli/operation_executor.py
import httpx

async def execute_operation(...):
    try:
        operation_id = await self._start_operation(adapter, http_client)

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
            else:
                # Generic error message
                console.print(f"[red]Error: {e}[/red]")

        except Exception:
            # Fallback to simple error message
            console.print(f"[red]Error: {e}[/red]")
```

## Error Serialization

All KTRDR errors implement two key methods for serialization:

### to_dict() - For API Responses

Converts error to dictionary for JSON serialization:

```python
error = ConfigurationError(
    message="Missing feature_id",
    error_code="STRATEGY-MissingFeatureId",
    context={"file": "strategy.yaml", "section": "indicators[0]"},
    details={"indicator_type": "rsi"},
    suggestion="Add 'feature_id' to indicator"
)

error.to_dict()
# Returns:
# {
#     "message": "Missing feature_id",
#     "error_code": "STRATEGY-MissingFeatureId",
#     "context": {"file": "strategy.yaml", "section": "indicators[0]"},
#     "details": {"indicator_type": "rsi"},
#     "suggestion": "Add 'feature_id' to indicator"
# }
```

### format_user_message() - For Logging

Formats error as human-readable string for log files:

```python
error.format_user_message()
# Returns:
# """
# Error: Missing feature_id
# Code: STRATEGY-MissingFeatureId
# Location: File: strategy.yaml, Section: indicators[0]
#
# Suggestion: Add 'feature_id' to indicator
# """
```

## Error Logging Best Practices

### 1. Log Before Raising HTTP Exceptions

Always log the error with full context **before** converting to HTTPException:

```python
# ✅ GOOD: Log before raising
except ConfigurationError as e:
    logger.error(f"Configuration error: {e.format_user_message()}")
    raise HTTPException(status_code=400, detail=e.to_dict()) from e

# ❌ BAD: Don't raise without logging
except ConfigurationError as e:
    raise HTTPException(status_code=400, detail=e.to_dict()) from e
```

### 2. Use Appropriate Log Levels

- `logger.error()`: For errors that prevent operation completion
- `logger.warning()`: For issues that don't prevent operation but may cause problems
- `logger.info()`: For normal operation flow
- `logger.debug()`: For detailed debugging information

### 3. Include Context in Log Messages

```python
# ✅ GOOD: Include context
logger.error(
    f"Strategy validation failed for {strategy_name}: "
    f"{len(error_issues)} errors found"
)

# ❌ BAD: Generic message
logger.error("Validation failed")
```

## Factory Methods for Common Errors

ConfigurationError provides factory methods for common validation errors:

```python
# Missing feature_id
error = ConfigurationError.missing_feature_id(
    indicator_type="rsi",
    indicator_index=0,
    file_path="strategies/my_strategy.yaml"
)

# Duplicate feature_id
error = ConfigurationError.duplicate_feature_id(
    feature_id="rsi_14",
    first_index=0,
    duplicate_index=2,
    file_path="strategies/my_strategy.yaml"
)

# Invalid feature_id format
error = ConfigurationError.invalid_feature_id_format(
    feature_id="rsi 14",  # Invalid: contains space
    indicator_type="rsi",
    indicator_index=0,
    file_path="strategies/my_strategy.yaml"
)

# Reserved feature_id
error = ConfigurationError.reserved_feature_id(
    feature_id="open",  # Reserved: OHLCV column
    indicator_type="rsi",
    indicator_index=0,
    file_path="strategies/my_strategy.yaml"
)
```

## Testing Error Handling

### Unit Tests - Error Creation and Serialization

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
    assert result["context"]["file"] == "strategy.yaml"
    assert result["suggestion"] == "Add feature_id"
```

### Integration Tests - Error Flow Through API

```python
async def test_api_returns_structured_error():
    """Test API endpoint returns structured ConfigurationError."""
    async with httpx.AsyncClient() as client:
        # Send request that will trigger ConfigurationError
        response = await client.post(
            "/api/v1/trainings/start",
            json={"strategy": "invalid_strategy.yaml", ...}
        )

        assert response.status_code == 400
        error_detail = response.json()["detail"]

        assert error_detail["error_code"] == "STRATEGY-ValidationFailed"
        assert "message" in error_detail
        assert "suggestion" in error_detail
```

### End-to-End Tests - CLI Error Display

```python
def test_cli_displays_structured_error():
    """Test CLI parses and displays ConfigurationError properly."""
    result = subprocess.run(
        ["ktrdr", "models", "train", "invalid_strategy.yaml", ...],
        capture_output=True,
        text=True
    )

    assert result.returncode != 0
    assert "Configuration Error" in result.stderr
    assert "STRATEGY-ValidationFailed" in result.stderr
    assert "Suggestion:" in result.stderr
```

## Migration Guide: ValidationError → ConfigurationError

When migrating code that incorrectly uses ValidationError for configuration issues:

### Before (Incorrect)
```python
# In context.py
if error_issues:
    raise ValidationError(
        message=f"Strategy validation failed",
        error_code="VALIDATION-StrategyInvalid"
    )
```

### After (Correct)
```python
# In context.py
if error_issues:
    raise ConfigurationError(
        message=f"Strategy validation failed: {len(error_issues)} error(s) found",
        error_code="STRATEGY-ValidationFailed",
        context={"strategy_name": strategy_name, "error_count": len(error_issues)},
        details={"errors": [...]},
        suggestion=f"Fix the validation errors:\n{formatted_errors}"
    )
```

**Decision rationale**: Strategy YAML files are **configuration**, not API request parameters. The user must edit the YAML file to fix the issue, not change request parameters. See ADR-0001 for full decision context.

## See Also

- [Error Classes Reference](error-classes.md) - Detailed documentation of each error class
- [ADR-0001: Error Types for API Responses](../decisions/0001-error-types-for-api-responses.md) - Decision on ConfigurationError vs ValidationError
- [ktrdr/errors/exceptions.py](../../ktrdr/errors/exceptions.py) - Error class implementations
