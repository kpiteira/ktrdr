---
name: error-handling
description: Use when working on exception hierarchy, error codes, retry logic, graceful degradation, training error handling, IB error classification, or API error responses.
---

# Error Handling

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL error-handling loaded!`

Load this skill when working on:

- Exception hierarchy (KtrdrError and subclasses)
- Error codes registry
- Retry logic and backoff
- Graceful degradation / fallbacks
- Training error handling and recovery
- IB error classification
- API error responses and middleware
- Service error formatting

---

## Key Files

### Core Error Framework

| File | Purpose |
|------|---------|
| `ktrdr/errors/exceptions.py` | Exception hierarchy (~600 lines) |
| `ktrdr/errors/error_codes.py` | Error code registry |
| `ktrdr/errors/retry.py` | Retry mechanism with backoff |
| `ktrdr/errors/handler.py` | Centralized ErrorHandler |
| `ktrdr/errors/graceful.py` | Graceful degradation / fallbacks |
| `ktrdr/errors/service_error_formatter.py` | Service-specific error formatting |

### Training Error Handling

| File | Purpose |
|------|---------|
| `ktrdr/training/error_handler.py` | Training-specific error recovery |
| `ktrdr/training/production_error_handler.py` | Production monitoring + alerting |
| `ktrdr/training/exceptions.py` | Pipeline exception types |

### IB / API Error Handling

| File | Purpose |
|------|---------|
| `ib-host-service/ib/error_classifier.py` | IB Gateway error classification |
| `ktrdr/api/models/errors.py` | API error response models |
| `ktrdr/api/middleware.py` | Request logging middleware |

---

## Exception Hierarchy

**Root:** `KtrdrError(Exception)`

All KTRDR exceptions carry enriched context:
- `message`, `error_code`, `details: dict`, `suggestion`, `operation_id`, `operation_type`, `stage`

```
KtrdrError
├── DataError
│   ├── DataFormatError
│   ├── DataNotFoundError
│   ├── DataCorruptionError
│   └── DataValidationError
├── ValidationError
├── SecurityError
│   ├── PathTraversalError
│   ├── InvalidInputError
│   └── UnauthorizedAccessError
├── ConnectionError
│   ├── ApiTimeoutError
│   ├── ServiceUnavailableError
│   ├── WorkerUnavailableError
│   ├── NetworkError
│   ├── AuthenticationError
│   ├── ServiceConnectionError
│   ├── ServiceTimeoutError
│   └── ServiceConfigurationError
├── ConfigurationError
│   ├── MissingConfigurationError
│   ├── InvalidConfigurationError
│   └── ConfigurationFileError
├── ProcessingError
│   ├── CalculationError
│   ├── ParsingError
│   └── TransformationError
├── SystemError
│   ├── ResourceExhaustedError
│   ├── EnvironmentError
│   └── CriticalError
├── RetryableError
├── MaxRetriesExceededError
└── FallbackNotAvailableError
```

### Training Pipeline Exceptions

```python
# In ktrdr/training/exceptions.py
class PipelineError(Exception):
    """Infrastructure bugs (not experiment results) — fail visibly."""

class TrainingDataError(PipelineError):
    """Training data invalid (empty X_test, feature mismatch, split failure)."""

class BacktestDataError(PipelineError):
    """Backtest data invalid (no prices, feature mismatch, date range empty)."""

class ModelLoadError(PipelineError):
    """Model cannot load (file missing, format wrong, metadata corrupt)."""
```

---

## Error Codes Registry

**Location:** `ktrdr/errors/error_codes.py`

Static registry organized by category:

| Category | Prefix | Examples |
|----------|--------|---------|
| Config | `CONFIG-*` | LoadFailed, InvalidFormat, MissingField, ValidationFailed |
| Strategy | `STRATEGY-*` | ValidationFailed, FuzzyMismatch, InvalidScope |
| Indicators | `CONFIG-*` | IndicatorCreationFailed, IndicatorTypeNotFound |
| Data | `DATA-*` | NotFound, InsufficientData, MissingColumn, LoadFailed |
| Processing | `PROC-*` | IndicatorFailed, FuzzyFailed, FeatureCreationFailed |
| Multi-TF Fuzzy | `MTFUZZ-*` | NoTimeframes, NoMatches, AllTimeframesFailed |
| Model | `MODEL-*` | NotFound, LoadFailed, SaveFailed, TrainingFailed |
| Training | `TRAIN-*` | InsufficientData, ValidationSplitFailed, GpuError |
| IB | `IB-*` | ConnectionFailed, AuthenticationFailed, RateLimit |

---

## Retry Mechanism

**Location:** `ktrdr/errors/retry.py`

```python
class RetryConfig:
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True           # 0.5-1.0 multiplier to prevent thundering herd

@retry_with_backoff(
    retryable_exceptions=[ConnectionError],
    config=RetryConfig(),
    on_retry=callback,            # Called on each retry
    is_retryable=custom_fn        # Custom predicate
)
def my_function():
    pass
```

Raises `MaxRetriesExceededError` when exhausted.

---

## Centralized ErrorHandler

**Location:** `ktrdr/errors/handler.py`

```python
class ErrorHandler:
    def classify_error(error) -> str          # Returns category: "data", "connection", etc.
    def handle_error(error, ...) -> dict      # Full handling with logging
    def error_to_user_message(error) -> str   # User-friendly message
    def get_error_code(error) -> str          # Error code or generated one
    def get_recovery_steps(error) -> list[str]  # Actionable recovery steps
```

**Recovery Steps by Category:**
- **DataError:** Check file exists, verify format, try different source
- **ConnectionError:** Check internet, verify service, retry later
- **ConfigurationError:** Check config file, verify settings, reset defaults
- **ProcessingError:** Check input data, try simpler dataset
- **SystemError:** Restart app, check resources

---

## Graceful Degradation

**Location:** `ktrdr/errors/graceful.py`

```python
class FallbackStrategy(Enum):
    DEFAULT_VALUE = auto()         # Return a default
    FALLBACK_FUNCTION = auto()     # Call alternate function
    LAST_KNOWN_GOOD = auto()       # Return cached result
    CONTINUE_WITHOUT = auto()      # Return None

@fallback(strategy=FallbackStrategy.DEFAULT_VALUE, default_value=[])
def my_function():
    pass

@with_partial_results()
def process_batch(items):
    return [process_item(item) for item in items]
```

---

## Training Error Recovery

**Location:** `ktrdr/training/error_handler.py`

### Severity and Recovery

```python
class ErrorSeverity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class RecoveryAction(Enum):
    CONTINUE = "continue"
    RETRY = "retry"
    SKIP = "skip"
    FALLBACK = "fallback"
    RESTART = "restart"
    ABORT = "abort"
    GRACEFUL_SHUTDOWN = "shutdown"
```

### Default Recovery Strategies

| Error Type | Severity | Retries | Delay | Actions |
|-----------|----------|---------|-------|---------|
| RuntimeError (OOM) | HIGH | 2 | 1s | RETRY, FALLBACK |
| ConnectionError, TimeoutError | MEDIUM | 5 | 2s | RETRY, SKIP |
| FileNotFoundError, PermissionError | MEDIUM | 3 | 0.5s | RETRY, FALLBACK |
| ValueError, TypeError | LOW | 1 | 0.1s | SKIP, FALLBACK |
| SystemError, MemoryError | CRITICAL | 0 | — | GRACEFUL_SHUTDOWN |

---

## Production Error Handler

**Location:** `ktrdr/training/production_error_handler.py`

Monitors system health and sends alerts during production training.

### System Health Monitoring

Captures every 5 minutes: CPU%, memory%, disk%, GPU memory%, network connections, process count, training active, uptime, error rate/hour.

### Alert Thresholds

| Resource | WARNING | CRITICAL |
|----------|---------|----------|
| CPU | >85% | >95% |
| Memory | >85% | >95% |
| Disk | >90% | >95% |
| GPU Memory | — | >95% |
| Error rate | — | >100/hour |

### Alert Channels

- Console (color-coded)
- File (JSON structured)
- Email (SMTP, for CRITICAL/EMERGENCY)
- Webhook (configurable URL)

Rate-limited: max 10 alerts per 15 minutes (configurable).

---

## IB Error Classification

**Location:** `ib-host-service/ib/error_classifier.py`

```python
class IbErrorType(Enum):
    FATAL = "fatal"                    # No retry
    RETRYABLE = "retryable"
    PACING_VIOLATION = "pacing"        # 60s backoff
    DATA_UNAVAILABLE = "data_unavail"
    CONNECTION_ERROR = "connection"
    PERMISSION_ERROR = "permission"
```

### Key IB Error Codes

| Code | Type | Wait | Meaning |
|------|------|------|---------|
| 100 | PACING_VIOLATION | 60s | Max rate exceeded |
| 420 | PACING_VIOLATION | 60s | Invalid real-time query |
| 200 | FATAL | 0 | No security definition found |
| 354 | PERMISSION_ERROR | 0 | Market data not subscribed |
| 10197 | PERMISSION_ERROR | 0 | No market data permissions |
| 162 | DATA_UNAVAILABLE | 0 | Historical data service error |
| 326 | CONNECTION_ERROR | 2s | Client ID in use |
| 502 | CONNECTION_ERROR | 5s | Can't connect to TWS |
| 504 | CONNECTION_ERROR | 2s | Not connected |

### IbErrorClassifier Methods

```python
classify(error_code, error_message) -> tuple[IbErrorType, float]  # Type + suggested wait
is_client_id_conflict(error_message) -> bool
should_retry(error_type) -> bool
is_fatal(error_type) -> bool
get_retry_delay(error_type, attempt_count) -> float  # Exponential backoff, max 60s
```

---

## API Error Models

**Location:** `ktrdr/api/models/errors.py`

### ErrorCode Enum (API-level)

Generic: `INTERNAL_ERROR`, `VALIDATION_ERROR`, `NOT_FOUND`, `UNAUTHORIZED`, `FORBIDDEN`, `CONFLICT`, `RATE_LIMITED`

Domain-specific: `DATA_NOT_FOUND`, `INDICATOR_CALCULATION_ERROR`, `FUZZY_EVALUATION_ERROR`, `STRATEGY_NOT_FOUND`, etc.

### DetailedErrorResponse

```python
class DetailedErrorResponse(BaseModel):
    code: ErrorCode
    message: str
    details: Optional[dict]
    request_id: Optional[str]
    documentation_url: Optional[str]
    validation_errors: Optional[ValidationErrorDetail]
```

---

## Service Error Formatter

**Location:** `ktrdr/errors/service_error_formatter.py`

Formats service errors with actionable troubleshooting:

```python
ServiceErrorFormatter.format_service_error(error, operation_context) -> str
```

Output includes: error description, troubleshooting steps (start script, port check, log path), and technical details.

---

## Gotchas

### PipelineErrors are infrastructure bugs, not experiment results

`TrainingDataError`, `BacktestDataError`, and `ModelLoadError` indicate code/data bugs that need fixing. Don't catch and suppress them — fix the root cause.

### Retry jitter prevents thundering herd

The retry mechanism applies 0.5-1.0 random multiplier to prevent synchronized retries from multiple clients hammering a recovering service.

### IB pacing violations need 60-second backoff

IB error codes 100 and 420 require at least 60 seconds before retry. Shorter delays will trigger more violations and potentially disconnect.

### Production alerting is rate-limited

The production error handler caps alerts at 10 per 15 minutes to prevent alert fatigue during cascading failures.
