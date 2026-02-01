# Configuration Reference

KTRDR uses Pydantic Settings classes for configuration. All settings can be configured via environment variables.

## Environment Variable Naming

All new environment variables use the `KTRDR_` prefix followed by a component prefix:

| Component | Prefix | Example |
|-----------|--------|---------|
| API Server | `KTRDR_API_` | `KTRDR_API_PORT` |
| Authentication | `KTRDR_AUTH_` | `KTRDR_AUTH_JWT_SECRET` |
| Logging | `KTRDR_LOG_` | `KTRDR_LOG_LEVEL` |
| Observability | `KTRDR_OTEL_` | `KTRDR_OTEL_OTLP_ENDPOINT` |
| Database | `KTRDR_DB_` | `KTRDR_DB_HOST` |
| IB Gateway | `KTRDR_IB_` | `KTRDR_IB_PORT` |
| IB Host Service | `KTRDR_IB_HOST_` | `KTRDR_IB_HOST_ENABLED` |
| Training Host Service | `KTRDR_TRAINING_HOST_` | `KTRDR_TRAINING_HOST_ENABLED` |
| Workers | `KTRDR_WORKER_` | `KTRDR_WORKER_PORT` |
| Operations | `KTRDR_OPS_` | `KTRDR_OPS_CACHE_TTL` |
| Orphan Detector | `KTRDR_ORPHAN_` | `KTRDR_ORPHAN_TIMEOUT_SECONDS` |
| Checkpoints | `KTRDR_CHECKPOINT_` | `KTRDR_CHECKPOINT_DIR` |
| Agent | `KTRDR_AGENT_` | `KTRDR_AGENT_MODEL` |
| Agent Gate | `KTRDR_GATE_` | `KTRDR_GATE_MODE` |
| Data Storage | `KTRDR_DATA_` | `KTRDR_DATA_DIR` |
| API Client | `KTRDR_API_CLIENT_` | `KTRDR_API_CLIENT_BASE_URL` |

---

## API Server Settings (`KTRDR_API_*`)

Configuration for the FastAPI backend server.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_API_HOST` | str | `127.0.0.1` | Host to bind the API server |
| `KTRDR_API_PORT` | int | `8000` | Port to bind the API server |
| `KTRDR_API_RELOAD` | bool | `true` | Enable auto-reload for development |
| `KTRDR_API_LOG_LEVEL` | str | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `KTRDR_API_ENVIRONMENT` | str | `development` | Deployment environment (development/staging/production) |
| `KTRDR_API_CORS_ORIGINS` | list | `["*"]` | JSON array of allowed CORS origins |
| `KTRDR_API_CORS_ALLOW_CREDENTIALS` | bool | `true` | Allow credentials for CORS requests |
| `KTRDR_API_CORS_ALLOW_METHODS` | list | `["*"]` | JSON array of allowed HTTP methods |
| `KTRDR_API_CORS_ALLOW_HEADERS` | list | `["*"]` | JSON array of allowed HTTP headers |
| `KTRDR_API_CORS_MAX_AGE` | int | `600` | Max age (seconds) of CORS preflight cache |

**Usage:**
```python
from ktrdr.config.settings import get_api_settings

settings = get_api_settings()
print(settings.port)  # 8000
```

---

## Authentication Settings (`KTRDR_AUTH_*`)

JWT and authentication configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_AUTH_JWT_SECRET` | str | `insecure-dev-secret` | Secret key for JWT signing (MUST change in production) |
| `KTRDR_AUTH_JWT_ALGORITHM` | str | `HS256` | Algorithm used for JWT signing |
| `KTRDR_AUTH_TOKEN_EXPIRE_MINUTES` | int | `60` | Token expiration time in minutes |

**Security Note:** The default `jwt_secret` is intentionally insecure. You MUST set a strong secret in production.

**Usage:**
```python
from ktrdr.config.settings import get_auth_settings

settings = get_auth_settings()
print(settings.jwt_algorithm)  # HS256
```

---

## Logging Settings (`KTRDR_LOG_*`)

Application logging configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_LOG_LEVEL` | str | `INFO` | Log level (DEBUG/INFO/WARNING/ERROR/CRITICAL) |
| `KTRDR_LOG_FORMAT` | str | `%(asctime)s [%(levelname)s] %(name)s: %(message)s` | Log message format |
| `KTRDR_LOG_JSON_OUTPUT` | bool | `false` | Enable JSON structured logging |

**Usage:**
```python
from ktrdr.config.settings import get_logging_settings

settings = get_logging_settings()
log_level_int = settings.get_log_level_int()  # logging.INFO
```

---

## Observability Settings (`KTRDR_OTEL_*`)

OpenTelemetry/Jaeger tracing configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_OTEL_ENABLED` | bool | `true` | Enable OpenTelemetry tracing |
| `KTRDR_OTEL_OTLP_ENDPOINT` | str | `http://jaeger:4317` | OTLP gRPC endpoint for Jaeger |
| `KTRDR_OTEL_SERVICE_NAME` | str | `ktrdr` | Service name for traces |
| `KTRDR_OTEL_CONSOLE_OUTPUT` | bool | `false` | Also output traces to console |

**Deprecated names:** `OTLP_ENDPOINT` → `KTRDR_OTEL_OTLP_ENDPOINT`

**Usage:**
```python
from ktrdr.config.settings import get_observability_settings

settings = get_observability_settings()
if settings.enabled:
    setup_tracing(settings.otlp_endpoint)
```

---

## Database Settings (`KTRDR_DB_*`)

PostgreSQL connection configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_DB_HOST` | str | `localhost` | Database host |
| `KTRDR_DB_PORT` | int | `5432` | Database port |
| `KTRDR_DB_NAME` | str | `ktrdr` | Database name |
| `KTRDR_DB_USER` | str | `ktrdr` | Database user |
| `KTRDR_DB_PASSWORD` | str | `localdev` | Database password |
| `KTRDR_DB_ECHO` | bool | `false` | Enable SQLAlchemy echo mode |

**Deprecated names:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ECHO`

**Computed properties:**
- `url`: Async connection URL for asyncpg (`postgresql+asyncpg://...`)
- `sync_url`: Sync connection URL for psycopg2 (`postgresql+psycopg2://...`)

**Usage:**
```python
from ktrdr.config.settings import get_db_settings

settings = get_db_settings()
async_url = settings.url  # postgresql+asyncpg://ktrdr:localdev@localhost:5432/ktrdr
```

---

## IB Gateway Settings (`KTRDR_IB_*`)

Interactive Brokers Gateway connection configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_IB_HOST` | str | `127.0.0.1` | IB Gateway host |
| `KTRDR_IB_PORT` | int | `4002` | IB Gateway port (4002=paper, 4001=live) |
| `KTRDR_IB_CLIENT_ID` | int | `1` | Client ID for connection |
| `KTRDR_IB_TIMEOUT` | int | `30` | Connection timeout in seconds |
| `KTRDR_IB_READONLY` | bool | `false` | Read-only mode |
| `KTRDR_IB_RATE_LIMIT` | int | `50` | Rate limit (requests per period) |
| `KTRDR_IB_RATE_PERIOD` | int | `60` | Rate period in seconds |
| `KTRDR_IB_MAX_RETRIES` | int | `3` | Maximum retry attempts |
| `KTRDR_IB_RETRY_BASE_DELAY` | float | `2.0` | Base retry delay in seconds |
| `KTRDR_IB_RETRY_MAX_DELAY` | float | `60.0` | Max retry delay in seconds |
| `KTRDR_IB_PACING_DELAY` | float | `0.6` | Pacing delay between requests |
| `KTRDR_IB_MAX_REQUESTS_PER_10MIN` | int | `60` | Max requests per 10 minutes |

**Deprecated names:** `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID`, `IB_TIMEOUT`, `IB_READONLY`, `IB_RATE_LIMIT`, `IB_RATE_PERIOD`, `IB_MAX_RETRIES`, `IB_RETRY_DELAY`, `IB_RETRY_MAX_DELAY`, `IB_PACING_DELAY`, `IB_MAX_REQUESTS_10MIN`

**Usage:**
```python
from ktrdr.config.settings import get_ib_settings

settings = get_ib_settings()
if settings.is_paper_trading():
    print("Using paper trading")
```

---

## IB Host Service Settings (`KTRDR_IB_HOST_*`)

Configuration for the IB Host Service (native process managing IB Gateway connection).

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_IB_HOST_HOST` | str | `localhost` | IB host service hostname |
| `KTRDR_IB_HOST_PORT` | int | `5001` | IB host service port |
| `KTRDR_IB_HOST_ENABLED` | bool | `false` | Enable IB host service |
| `KTRDR_IB_HOST_TIMEOUT` | float | `30.0` | Request timeout in seconds |
| `KTRDR_IB_HOST_HEALTH_CHECK_INTERVAL` | float | `10.0` | Health check interval |
| `KTRDR_IB_HOST_MAX_RETRIES` | int | `3` | Max retry attempts |
| `KTRDR_IB_HOST_RETRY_DELAY` | float | `1.0` | Delay between retries |

**Deprecated names:** `USE_IB_HOST_SERVICE` → `KTRDR_IB_HOST_ENABLED`

**Computed properties:**
- `base_url`: Service base URL (e.g., `http://localhost:5001`)

**Usage:**
```python
from ktrdr.config.settings import get_ib_host_service_settings

settings = get_ib_host_service_settings()
if settings.enabled:
    health_url = settings.get_health_url()
```

---

## Training Host Service Settings (`KTRDR_TRAINING_HOST_*`)

Configuration for the Training Host Service (native process for GPU training).

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_TRAINING_HOST_HOST` | str | `localhost` | Training host service hostname |
| `KTRDR_TRAINING_HOST_PORT` | int | `5002` | Training host service port |
| `KTRDR_TRAINING_HOST_ENABLED` | bool | `false` | Enable training host service |
| `KTRDR_TRAINING_HOST_TIMEOUT` | float | `30.0` | Request timeout in seconds |
| `KTRDR_TRAINING_HOST_HEALTH_CHECK_INTERVAL` | float | `10.0` | Health check interval |
| `KTRDR_TRAINING_HOST_MAX_RETRIES` | int | `3` | Max retry attempts |
| `KTRDR_TRAINING_HOST_RETRY_DELAY` | float | `1.0` | Delay between retries |

**Deprecated names:** `USE_TRAINING_HOST_SERVICE` → `KTRDR_TRAINING_HOST_ENABLED`

**Computed properties:**
- `base_url`: Service base URL (e.g., `http://localhost:5002`)

**Usage:**
```python
from ktrdr.config.settings import get_training_host_service_settings

settings = get_training_host_service_settings()
if settings.enabled:
    health_url = settings.get_health_url()
```

---

## Worker Settings (`KTRDR_WORKER_*`)

Worker process configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_WORKER_ID` | str | `None` | Worker identifier (auto-generated if not set) |
| `KTRDR_WORKER_PORT` | int | `5003` | Worker service port |
| `KTRDR_WORKER_HEARTBEAT_INTERVAL` | int | `30` | Heartbeat interval in seconds |
| `KTRDR_WORKER_REGISTRATION_TIMEOUT` | int | `10` | Registration timeout in seconds |
| `KTRDR_WORKER_ENDPOINT_URL` | str | `None` | Explicit endpoint URL (auto-detected if not set) |
| `KTRDR_WORKER_PUBLIC_BASE_URL` | str | `None` | Public URL for distributed deployments |

**Deprecated names:** `WORKER_ID`, `WORKER_PORT`, `WORKER_ENDPOINT_URL`, `WORKER_PUBLIC_BASE_URL`

**Note:** Workers should use `get_api_service_settings().base_url` for backend connection URL.

**Usage:**
```python
from ktrdr.config.settings import get_worker_settings

settings = get_worker_settings()
print(settings.port)  # 5003
```

---

## Operations Settings (`KTRDR_OPS_*`)

Operations tracking service configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_OPS_CACHE_TTL` | float | `1.0` | Cache TTL in seconds (0 = no cache) |
| `KTRDR_OPS_MAX_OPERATIONS` | int | `10000` | Maximum operations to track in memory |
| `KTRDR_OPS_CLEANUP_INTERVAL_SECONDS` | int | `3600` | Interval between cleanup runs |
| `KTRDR_OPS_RETENTION_DAYS` | int | `7` | Days to retain completed operations |

**Deprecated names:** `OPERATIONS_CACHE_TTL` → `KTRDR_OPS_CACHE_TTL`

**Usage:**
```python
from ktrdr.config.settings import get_operations_settings

settings = get_operations_settings()
print(settings.retention_days)  # 7
```

---

## Orphan Detector Settings (`KTRDR_ORPHAN_*`)

Orphan operation detection configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_ORPHAN_TIMEOUT_SECONDS` | int | `60` | Time before unclaimed operation is marked FAILED |
| `KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS` | int | `15` | Interval between orphan detection checks |

**Deprecated names:** `ORPHAN_TIMEOUT_SECONDS`, `ORPHAN_CHECK_INTERVAL_SECONDS`

**Usage:**
```python
from ktrdr.config.settings import get_orphan_detector_settings

settings = get_orphan_detector_settings()
print(settings.timeout_seconds)  # 60
```

---

## Checkpoint Settings (`KTRDR_CHECKPOINT_*`)

Checkpoint saving configuration for long-running operations.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_CHECKPOINT_EPOCH_INTERVAL` | int | `10` | Save checkpoint every N epochs |
| `KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS` | int | `300` | Save checkpoint every M seconds |
| `KTRDR_CHECKPOINT_DIR` | str | `/app/data/checkpoints` | Directory for checkpoint artifacts |
| `KTRDR_CHECKPOINT_MAX_AGE_DAYS` | int | `30` | Auto-cleanup checkpoints older than N days |

**Deprecated names:** `CHECKPOINT_EPOCH_INTERVAL`, `CHECKPOINT_TIME_INTERVAL_SECONDS`, `CHECKPOINT_DIR`, `CHECKPOINT_MAX_AGE_DAYS`

**Usage:**
```python
from ktrdr.config.settings import get_checkpoint_settings

settings = get_checkpoint_settings()
print(settings.dir)  # /app/data/checkpoints
```

---

## Agent Settings (`KTRDR_AGENT_*`)

Agent process configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_AGENT_POLL_INTERVAL` | float | `5.0` | Poll interval in seconds |
| `KTRDR_AGENT_MODEL` | str | `claude-sonnet-4-20250514` | LLM model identifier |
| `KTRDR_AGENT_MAX_TOKENS` | int | `4096` | Maximum output tokens per request |
| `KTRDR_AGENT_TIMEOUT_SECONDS` | int | `300` | Request timeout in seconds |
| `KTRDR_AGENT_MAX_ITERATIONS` | int | `10` | Maximum agentic iterations per task |
| `KTRDR_AGENT_MAX_INPUT_TOKENS` | int | `50000` | Maximum input context tokens |
| `KTRDR_AGENT_DAILY_BUDGET` | float | `5.0` | Daily cost budget in USD (0 = disabled) |
| `KTRDR_AGENT_BUDGET_DIR` | str | `data/budget` | Directory for budget tracking |
| `KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES` | int | `0` | Max concurrent agents (0 = unlimited) |
| `KTRDR_AGENT_CONCURRENCY_BUFFER` | int | `1` | Concurrency buffer |
| `KTRDR_AGENT_TRAINING_START_DATE` | str | `None` | Default training start date (YYYY-MM-DD) |
| `KTRDR_AGENT_TRAINING_END_DATE` | str | `None` | Default training end date (YYYY-MM-DD) |
| `KTRDR_AGENT_BACKTEST_START_DATE` | str | `None` | Default backtest start date (YYYY-MM-DD) |
| `KTRDR_AGENT_BACKTEST_END_DATE` | str | `None` | Default backtest end date (YYYY-MM-DD) |

**Deprecated names:** `AGENT_POLL_INTERVAL`, `AGENT_MODEL`, `AGENT_MAX_TOKENS`, `AGENT_TIMEOUT_SECONDS`, `AGENT_MAX_ITERATIONS`, `AGENT_MAX_INPUT_TOKENS`, `AGENT_DAILY_BUDGET`, `AGENT_BUDGET_DIR`, `AGENT_MAX_CONCURRENT_RESEARCHES`, `AGENT_CONCURRENCY_BUFFER`, `AGENT_TRAINING_START_DATE`, `AGENT_TRAINING_END_DATE`, `AGENT_BACKTEST_START_DATE`, `AGENT_BACKTEST_END_DATE`

**Usage:**
```python
from ktrdr.config.settings import get_agent_settings

settings = get_agent_settings()
print(settings.model)  # claude-sonnet-4-20250514
```

---

## Agent Gate Settings (`KTRDR_GATE_*`)

Safety gate for trade execution.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_GATE_MODE` | str | `simulation` | Execution mode: simulation or live |
| `KTRDR_GATE_DRY_RUN` | bool | `true` | Log trades but don't execute (safe default) |
| `KTRDR_GATE_CONFIRMATION_REQUIRED` | bool | `true` | Require confirmation before trades |
| `KTRDR_GATE_MAX_POSITION_SIZE` | int | `0` | Maximum position size in dollars (0 = no limit) |
| `KTRDR_GATE_MAX_DAILY_TRADES` | int | `0` | Maximum trades per day (0 = no limit) |

**Security Note:** Defaults are intentionally safe (simulation mode, dry_run enabled).

**Usage:**
```python
from ktrdr.config.settings import get_agent_gate_settings

settings = get_agent_gate_settings()
if settings.can_execute_trade():
    # Actually execute trade
    pass
```

---

## Data Storage Settings (`KTRDR_DATA_*`)

Data path configuration.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_DATA_DIR` | str | `data` | Base data directory for OHLCV data |
| `KTRDR_DATA_MODELS_DIR` | str | `models` | Directory for trained model storage |
| `KTRDR_DATA_CACHE_DIR` | str | `data/cache` | Directory for cached data |
| `KTRDR_DATA_MAX_SEGMENT_SIZE` | int | `5000` | Maximum data segment size |
| `KTRDR_DATA_PERIODIC_SAVE_INTERVAL` | float | `0.5` | Periodic save interval in minutes |

**Deprecated names:** `DATA_DIR`, `MODELS_DIR`, `DATA_MAX_SEGMENT_SIZE`, `DATA_PERIODIC_SAVE_MIN`

**Usage:**
```python
from ktrdr.config.settings import get_data_settings

settings = get_data_settings()
print(settings.data_dir)  # data
```

---

## API Client Settings (`KTRDR_API_CLIENT_*`)

Configuration for clients connecting to the KTRDR API.

| Env Var | Type | Default | Description |
|---------|------|---------|-------------|
| `KTRDR_API_CLIENT_BASE_URL` | str | `http://localhost:8000/api/v1` | Base URL for API connections |
| `KTRDR_API_CLIENT_TIMEOUT` | float | `30.0` | Request timeout in seconds |
| `KTRDR_API_CLIENT_MAX_RETRIES` | int | `3` | Maximum retry attempts |
| `KTRDR_API_CLIENT_RETRY_DELAY` | float | `1.0` | Delay between retries |
| `KTRDR_API_CLIENT_HEALTH_CHECK_INTERVAL` | float | `10.0` | Seconds between health checks |

**Deprecated names:** `KTRDR_API_URL` → `KTRDR_API_CLIENT_BASE_URL`

**Usage:**
```python
from ktrdr.config.settings import get_api_service_settings, get_api_base_url

# Full settings object
settings = get_api_service_settings()
health_url = settings.get_health_url()

# Quick access to base URL
base_url = get_api_base_url()  # http://localhost:8000/api/v1
```

---

## Deprecated Environment Variable Names

The following environment variables are deprecated but still work. They emit warnings at startup. Migrate to the new names when convenient.

| Old Name | New Name | Notes |
|----------|----------|-------|
| `DB_HOST` | `KTRDR_DB_HOST` | |
| `DB_PORT` | `KTRDR_DB_PORT` | |
| `DB_NAME` | `KTRDR_DB_NAME` | |
| `DB_USER` | `KTRDR_DB_USER` | |
| `DB_PASSWORD` | `KTRDR_DB_PASSWORD` | |
| `DB_ECHO` | `KTRDR_DB_ECHO` | |
| `IB_HOST` | `KTRDR_IB_HOST` | |
| `IB_PORT` | `KTRDR_IB_PORT` | |
| `IB_CLIENT_ID` | `KTRDR_IB_CLIENT_ID` | |
| `IB_TIMEOUT` | `KTRDR_IB_TIMEOUT` | |
| `IB_READONLY` | `KTRDR_IB_READONLY` | |
| `IB_RATE_LIMIT` | `KTRDR_IB_RATE_LIMIT` | |
| `IB_RATE_PERIOD` | `KTRDR_IB_RATE_PERIOD` | |
| `IB_MAX_RETRIES` | `KTRDR_IB_MAX_RETRIES` | |
| `IB_RETRY_DELAY` | `KTRDR_IB_RETRY_BASE_DELAY` | |
| `IB_RETRY_MAX_DELAY` | `KTRDR_IB_RETRY_MAX_DELAY` | |
| `IB_PACING_DELAY` | `KTRDR_IB_PACING_DELAY` | |
| `IB_MAX_REQUESTS_10MIN` | `KTRDR_IB_MAX_REQUESTS_PER_10MIN` | |
| `USE_IB_HOST_SERVICE` | `KTRDR_IB_HOST_ENABLED` | |
| `USE_TRAINING_HOST_SERVICE` | `KTRDR_TRAINING_HOST_ENABLED` | |
| `WORKER_ID` | `KTRDR_WORKER_ID` | |
| `WORKER_PORT` | `KTRDR_WORKER_PORT` | |
| `WORKER_ENDPOINT_URL` | `KTRDR_WORKER_ENDPOINT_URL` | |
| `WORKER_PUBLIC_BASE_URL` | `KTRDR_WORKER_PUBLIC_BASE_URL` | |
| `OPERATIONS_CACHE_TTL` | `KTRDR_OPS_CACHE_TTL` | |
| `ORPHAN_TIMEOUT_SECONDS` | `KTRDR_ORPHAN_TIMEOUT_SECONDS` | |
| `ORPHAN_CHECK_INTERVAL_SECONDS` | `KTRDR_ORPHAN_CHECK_INTERVAL_SECONDS` | |
| `CHECKPOINT_EPOCH_INTERVAL` | `KTRDR_CHECKPOINT_EPOCH_INTERVAL` | |
| `CHECKPOINT_TIME_INTERVAL_SECONDS` | `KTRDR_CHECKPOINT_TIME_INTERVAL_SECONDS` | |
| `CHECKPOINT_DIR` | `KTRDR_CHECKPOINT_DIR` | |
| `CHECKPOINT_MAX_AGE_DAYS` | `KTRDR_CHECKPOINT_MAX_AGE_DAYS` | |
| `OTLP_ENDPOINT` | `KTRDR_OTEL_OTLP_ENDPOINT` | |
| `AGENT_POLL_INTERVAL` | `KTRDR_AGENT_POLL_INTERVAL` | |
| `AGENT_MODEL` | `KTRDR_AGENT_MODEL` | |
| `AGENT_MAX_TOKENS` | `KTRDR_AGENT_MAX_TOKENS` | |
| `AGENT_TIMEOUT_SECONDS` | `KTRDR_AGENT_TIMEOUT_SECONDS` | |
| `AGENT_MAX_ITERATIONS` | `KTRDR_AGENT_MAX_ITERATIONS` | |
| `AGENT_MAX_INPUT_TOKENS` | `KTRDR_AGENT_MAX_INPUT_TOKENS` | |
| `AGENT_DAILY_BUDGET` | `KTRDR_AGENT_DAILY_BUDGET` | |
| `AGENT_BUDGET_DIR` | `KTRDR_AGENT_BUDGET_DIR` | |
| `AGENT_MAX_CONCURRENT_RESEARCHES` | `KTRDR_AGENT_MAX_CONCURRENT_RESEARCHES` | |
| `AGENT_CONCURRENCY_BUFFER` | `KTRDR_AGENT_CONCURRENCY_BUFFER` | |
| `AGENT_TRAINING_START_DATE` | `KTRDR_AGENT_TRAINING_START_DATE` | |
| `AGENT_TRAINING_END_DATE` | `KTRDR_AGENT_TRAINING_END_DATE` | |
| `AGENT_BACKTEST_START_DATE` | `KTRDR_AGENT_BACKTEST_START_DATE` | |
| `AGENT_BACKTEST_END_DATE` | `KTRDR_AGENT_BACKTEST_END_DATE` | |
| `DATA_DIR` | `KTRDR_DATA_DIR` | |
| `MODELS_DIR` | `KTRDR_DATA_MODELS_DIR` | |
| `DATA_MAX_SEGMENT_SIZE` | `KTRDR_DATA_MAX_SEGMENT_SIZE` | |
| `DATA_PERIODIC_SAVE_MIN` | `KTRDR_DATA_PERIODIC_SAVE_INTERVAL` | |
| `KTRDR_API_URL` | `KTRDR_API_CLIENT_BASE_URL` | |

---

## Configuration Files

### `.env` Files

KTRDR loads environment variables from `.env.local` files. Create a `.env.local` file in the project root:

```bash
# Database
KTRDR_DB_HOST=postgres
KTRDR_DB_PASSWORD=your-secure-password

# Observability
KTRDR_OTEL_OTLP_ENDPOINT=http://jaeger:4317

# IB Gateway
KTRDR_IB_PORT=4002
```

### Docker Compose

The `docker-compose.yml` file sets environment variables for containerized services. All variables use the `KTRDR_*` prefix.

---

## Best Practices

1. **Use new variable names** - Deprecated names work but emit warnings
2. **Never commit secrets** - Use `.env.local` (gitignored) for sensitive values
3. **Change defaults in production** - `jwt_secret` and `db_password` defaults are insecure
4. **Use Settings classes** - Don't read environment variables directly with `os.getenv()`

```python
# Good
from ktrdr.config.settings import get_db_settings
db_host = get_db_settings().host

# Bad
import os
db_host = os.getenv("KTRDR_DB_HOST", "localhost")
```
