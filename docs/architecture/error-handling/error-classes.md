# Error Classes Reference

This document provides detailed information about each error class in the KTRDR error hierarchy, including when to use them and examples.

## Table of Contents

- [Base Error Classes](#base-error-classes)
  - [KtrdrError](#ktrdrerror)
- [Configuration Errors](#configuration-errors)
  - [ConfigurationError](#configurationerror)
  - [MissingConfigurationError](#missingconfigurationerror)
  - [InvalidConfigurationError](#invalidconfigurationerror)
  - [ConfigurationFileError](#configurationfileerror)
  - [ServiceConfigurationError](#serviceconfigurationerror)
- [Validation Errors](#validation-errors)
  - [ValidationError](#validationerror)
- [Data Errors](#data-errors)
  - [DataError](#dataerror)
  - [DataFormatError](#dataformaterror)
  - [DataNotFoundError](#datanotfounderror)
  - [DataCorruptionError](#datacorruptionerror)
  - [DataValidationError](#datavalidationerror)
- [Connection Errors](#connection-errors)
  - [ConnectionError](#connectionerror)
  - [NetworkError](#networkerror)
  - [ApiTimeoutError](#apitimeouterror)
  - [ServiceUnavailableError](#serviceunavailableerror)
  - [AuthenticationError](#authenticationerror)
  - [ServiceConnectionError](#serviceconnectionerror)
  - [ServiceTimeoutError](#servicetimeouterror)
- [Processing Errors](#processing-errors)
  - [ProcessingError](#processingerror)
  - [CalculationError](#calculationerror)
  - [ParsingError](#parsingerror)
  - [TransformationError](#transformationerror)
- [Security Errors](#security-errors)
  - [SecurityError](#securityerror)
  - [PathTraversalError](#pathtraversalerror)
  - [InvalidInputError](#invalidinputerror)
  - [UnauthorizedAccessError](#unauthorizedaccesserror)
- [System Errors](#system-errors)
  - [SystemError](#systemerror)
  - [ResourceExhaustedError](#resourceexhaustederror)
  - [EnvironmentError](#environmenterror)
  - [CriticalError](#criticalerror)
- [Retry and Fallback Errors](#retry-and-fallback-errors)
  - [RetryableError](#retryableerror)
  - [MaxRetriesExceededError](#maxretriesexceedederror)
  - [FallbackNotAvailableError](#fallbacknotavailableerror)

---

## Base Error Classes

### KtrdrError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base exception class for all KTRDR application errors. All custom exceptions inherit from this class.

**Attributes**:
- `message` (str): Human-readable error message
- `error_code` (Optional[str]): Optional error code for reference
- `details` (dict[str, Any]): Optional dictionary with additional error details

**When to use**: Never directly - always use a specific subclass.

**Example**:
```python
# Don't do this
raise KtrdrError("Something went wrong")

# Do this instead
raise DataError("No data available for AAPL")
```

---

## Configuration Errors

### ConfigurationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Enhanced configuration error with comprehensive error reporting. Use for issues with configuration files, strategy YAML files, or system setup.

**Attributes**:
- `message` (str): Human-readable error message
- `error_code` (Optional[str]): Machine-readable error code (e.g., `STRATEGY-MissingFeatureId`)
- `context` (dict[str, Any]): Where error occurred (file, section, field)
- `details` (dict[str, Any]): Structured data about the error
- `suggestion` (str): Actionable steps to fix the error

**Methods**:
- `to_dict()`: Serialize to dictionary for API responses
- `format_user_message()`: Format human-readable message for logging
- `missing_feature_id()`: Factory method for missing feature_id errors
- `duplicate_feature_id()`: Factory method for duplicate feature_id errors
- `invalid_feature_id_format()`: Factory method for invalid format errors
- `reserved_feature_id()`: Factory method for reserved word errors

**When to use**:
- Strategy YAML file has structural issues
- Configuration file missing required fields
- System configuration is invalid
- **Fix requires editing a file**

**Example**:
```python
from ktrdr.errors import ConfigurationError

# Manual construction
raise ConfigurationError(
    message="Strategy validation failed: 1 error(s) found",
    error_code="STRATEGY-ValidationFailed",
    context={
        "strategy_name": "mtf_forex_neural",
        "error_count": 1
    },
    details={
        "errors": [
            {
                "category": "fuzzy_sets",
                "message": "Fuzzy sets reference invalid indicators"
            }
        ]
    },
    suggestion="Fix the validation errors:\nfuzzy_sets: ..."
)

# Using factory method
raise ConfigurationError.missing_feature_id(
    indicator_type="rsi",
    indicator_index=0,
    file_path="strategies/my_strategy.yaml"
)
```

**API Response**:
```json
{
  "detail": {
    "message": "Strategy validation failed: 1 error(s) found",
    "error_code": "STRATEGY-ValidationFailed",
    "context": {
      "strategy_name": "mtf_forex_neural",
      "error_count": 1
    },
    "details": {
      "errors": [...]
    },
    "suggestion": "Fix the validation errors:..."
  }
}
```

### MissingConfigurationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Subclass of ConfigurationError for missing required configuration settings.

**When to use**: Required configuration key is absent.

**Example**:
```python
raise MissingConfigurationError(
    message="Required configuration 'API_KEY' not found",
    error_code="CONFIG-MissingRequired"
)
```

### InvalidConfigurationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Subclass of ConfigurationError for invalid configuration values.

**When to use**: Configuration value is present but invalid.

**Example**:
```python
raise InvalidConfigurationError(
    message="Invalid port number: 'abc'",
    error_code="CONFIG-InvalidValue",
    details={"key": "port", "value": "abc"}
)
```

### ConfigurationFileError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Subclass of ConfigurationError for configuration file issues.

**When to use**: Configuration file cannot be read or parsed.

**Example**:
```python
raise ConfigurationFileError(
    message="Cannot read configuration file: config.yaml",
    error_code="CONFIG-FileError",
    details={"file": "config.yaml", "reason": "Permission denied"}
)
```

### ServiceConfigurationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Subclass of ConfigurationError for async service configuration issues.

**When to use**: Host service configuration is invalid or missing.

**Example**:
```python
raise ServiceConfigurationError(
    message="IB Host Service URL not configured",
    error_code="SERVICE-MissingURL",
    details={"service": "ib-host-service"}
)
```

---

## Validation Errors

### ValidationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Exception for API request parameter validation failures. Use for user input validation, not configuration file issues.

**When to use**:
- API request parameter is invalid
- User input is out of range
- Type mismatch in request
- **Fix requires changing request parameters**

**Example**:
```python
from ktrdr.errors import ValidationError

raise ValidationError(
    message="Invalid timeframe '5x'",
    error_code="VALIDATION-InvalidTimeframe",
    details={
        "provided": "5x",
        "valid_options": ["1m", "5m", "15m", "1h", "1d"]
    }
)
```

**API Response** (422 status):
```json
{
  "detail": {
    "message": "Invalid timeframe '5x'",
    "error_code": "VALIDATION-InvalidTimeframe",
    "details": {
      "provided": "5x",
      "valid_options": ["1m", "5m", "15m", "1h", "1d"]
    }
  }
}
```

---

## Data Errors

### DataError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for data operation errors. Covers missing data, corrupt data, or data source issues.

**When to use**:
- Data not available for requested symbol/timeframe
- Data source is unreachable
- Data format issues
- **Fix requires data source action**

**Example**:
```python
from ktrdr.errors import DataError

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

### DataFormatError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Data format is invalid or unexpected.

**Example**:
```python
raise DataFormatError(
    message="Invalid OHLCV data format: missing 'close' column",
    error_code="DATA-InvalidFormat",
    details={"missing_columns": ["close"]}
)
```

### DataNotFoundError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Data file or resource not found.

**Example**:
```python
raise DataNotFoundError(
    message="Data file not found: AAPL_1d.csv",
    error_code="DATA-NotFound",
    details={"file": "AAPL_1d.csv", "path": "/data/stocks/"}
)
```

### DataCorruptionError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Data is corrupt or malformed.

**Example**:
```python
raise DataCorruptionError(
    message="Corrupt data detected: negative prices",
    error_code="DATA-Corruption",
    details={"symbol": "AAPL", "row": 42}
)
```

### DataValidationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Data fails validation checks (e.g., high < low).

**Example**:
```python
raise DataValidationError(
    message="Invalid OHLCV data: high < low",
    error_code="DATA-ValidationFailed",
    details={"row": 15, "high": 100.5, "low": 101.2}
)
```

---

## Connection Errors

### ConnectionError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for network connectivity errors.

**When to use**: Network issues, API timeouts, service unavailability.

### NetworkError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: General network connectivity issues.

**Example**:
```python
raise NetworkError(
    message="Network connection failed",
    error_code="NETWORK-ConnectionFailed"
)
```

### ApiTimeoutError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: API call times out.

**Example**:
```python
raise ApiTimeoutError(
    message="API request timed out after 30s",
    error_code="API-Timeout",
    details={"endpoint": "/data/load", "timeout": 30}
)
```

### ServiceUnavailableError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Required service is unavailable.

**Example**:
```python
raise ServiceUnavailableError(
    message="IB Gateway is not running",
    error_code="SERVICE-Unavailable",
    details={"service": "IB Gateway", "port": 4002}
)
```

### AuthenticationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Authentication with service fails.

**Example**:
```python
raise AuthenticationError(
    message="Failed to authenticate with IB Gateway",
    error_code="AUTH-Failed",
    details={"service": "IB Gateway"}
)
```

### ServiceConnectionError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Connection to host service fails.

**Example**:
```python
raise ServiceConnectionError(
    message="Cannot connect to IB Host Service",
    error_code="SERVICE-ConnectionFailed",
    details={"url": "http://localhost:5001", "service": "ib-host-service"}
)
```

### ServiceTimeoutError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Host service request times out.

**Example**:
```python
raise ServiceTimeoutError(
    message="Training host service request timed out",
    error_code="SERVICE-Timeout",
    details={"url": "http://localhost:5002", "timeout": 60}
)
```

---

## Processing Errors

### ProcessingError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for data processing errors.

### CalculationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Calculation fails (e.g., indicator calculation).

**Example**:
```python
raise CalculationError(
    message="RSI calculation failed: insufficient data",
    error_code="CALC-Failed",
    details={"indicator": "rsi", "required_points": 14, "available": 10}
)
```

### ParsingError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Parsing data fails.

**Example**:
```python
raise ParsingError(
    message="Failed to parse YAML file",
    error_code="PARSE-Failed",
    details={"file": "strategy.yaml", "line": 42}
)
```

### TransformationError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Data transformation fails.

**Example**:
```python
raise TransformationError(
    message="Failed to normalize data",
    error_code="TRANSFORM-Failed",
    details={"column": "close", "method": "min-max"}
)
```

---

## Security Errors

### SecurityError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for security-related errors.

### PathTraversalError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Path traversal attempt detected.

**Example**:
```python
raise PathTraversalError(
    message="Path traversal attempt detected",
    error_code="SECURITY-PathTraversal",
    details={"path": "../../../etc/passwd"}
)
```

### InvalidInputError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Input validation fails for security reasons.

**Example**:
```python
raise InvalidInputError(
    message="Invalid input detected: SQL injection attempt",
    error_code="SECURITY-InvalidInput",
    details={"input": "'; DROP TABLE users;--"}
)
```

### UnauthorizedAccessError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Unauthorized access attempt detected.

**Example**:
```python
raise UnauthorizedAccessError(
    message="Unauthorized access to admin endpoint",
    error_code="SECURITY-Unauthorized",
    details={"endpoint": "/admin/users"}
)
```

---

## System Errors

### SystemError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for system-level errors.

### ResourceExhaustedError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: System resource is exhausted.

**Example**:
```python
raise ResourceExhaustedError(
    message="Out of memory",
    error_code="SYSTEM-OutOfMemory",
    details={"available_mb": 100, "required_mb": 2000}
)
```

### EnvironmentError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Issue with the environment.

**Example**:
```python
raise EnvironmentError(
    message="Required environment variable not set: CUDA_HOME",
    error_code="ENV-MissingVariable",
    details={"variable": "CUDA_HOME"}
)
```

### CriticalError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Critical system failure requiring immediate attention.

**Example**:
```python
raise CriticalError(
    message="Database corruption detected",
    error_code="CRITICAL-DatabaseCorruption"
)
```

---

## Retry and Fallback Errors

### RetryableError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Base class for errors that can be retried.

**Example**:
```python
raise RetryableError(
    message="Temporary network issue, can retry",
    error_code="RETRY-NetworkIssue"
)
```

### MaxRetriesExceededError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: Maximum number of retries exceeded.

**Example**:
```python
raise MaxRetriesExceededError(
    message="Max retries exceeded (3 attempts)",
    error_code="RETRY-MaxExceeded",
    details={"max_retries": 3, "operation": "load_data"}
)
```

### FallbackNotAvailableError

**Location**: `ktrdr/errors/exceptions.py`

**Description**: No fallback strategy available.

**Example**:
```python
raise FallbackNotAvailableError(
    message="No fallback data source available",
    error_code="FALLBACK-NotAvailable",
    details={"primary": "IB Gateway", "attempted_fallback": ["CSV", "Database"]}
)
```

---

## Error Code Conventions

Error codes follow the pattern: `CATEGORY-SpecificError`

### Categories

- `STRATEGY-*`: Strategy configuration errors
- `CONFIG-*`: System configuration errors
- `VALIDATION-*`: API request validation errors
- `DATA-*`: Data loading/processing errors
- `INDICATOR-*`: Indicator calculation errors
- `NETWORK-*`: Network connectivity errors
- `SERVICE-*`: Host service errors
- `SECURITY-*`: Security-related errors
- `SYSTEM-*`: System-level errors
- `CALC-*`: Calculation errors
- `PARSE-*`: Parsing errors
- `TRANSFORM-*`: Transformation errors

### Examples

- `STRATEGY-MissingFeatureId`: Indicator missing feature_id
- `STRATEGY-DuplicateFeatureId`: Duplicate feature_id found
- `STRATEGY-ValidationFailed`: Strategy validation failed
- `VALIDATION-InvalidTimeframe`: Invalid timeframe parameter
- `DATA-NoDataAvailable`: No data for symbol/timeframe
- `SERVICE-ConnectionFailed`: Cannot connect to host service
- `INDICATOR-InsufficientData`: Not enough data for calculation

---

## See Also

- [Error Handling Architecture](error-handling-architecture.md) - Comprehensive architecture guide
- [ADR-0001: Error Types for API Responses](../decisions/0001-error-types-for-api-responses.md) - Decision rationale
- [ktrdr/errors/exceptions.py](../../ktrdr/errors/exceptions.py) - Error class implementations
