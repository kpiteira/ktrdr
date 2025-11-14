# Observability Debugging Workflows

**Version**: 1.0
**Date**: 2025-11-13
**Phase**: Post Phase 6 (Complete Business Logic Instrumentation)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Query Patterns](#query-patterns)
3. [Debugging Scenarios](#debugging-scenarios)
4. [Span Attribute Reference](#span-attribute-reference)
5. [Common Issues & Solutions](#common-issues--solutions)
6. [Claude Code Integration](#claude-code-integration)

---

## Quick Start

### Accessing Observability Tools

**Jaeger UI** (Distributed Tracing):
```bash
open http://localhost:16686
```

**Grafana** (Unified Dashboards):
```bash
open http://localhost:3000
```

**Prometheus** (Metrics):
```bash
open http://localhost:9090
```

### Basic Workflow

1. **User reports issue**: "Training operation stuck at 45%"
2. **Get operation ID**: From CLI output or API response
3. **Query Jaeger**: Search by `operation.id` tag
4. **Analyze trace**: Check span durations, errors, attributes
5. **Diagnose**: Identify which service/phase is stuck/failing
6. **Fix**: Apply targeted fix based on root cause

---

## Query Patterns

### 1. Query by Operation ID

**Use Case**: User provides operation ID from CLI or API

**Jaeger UI Query**:
```
Service: ktrdr-api (or any service)
Tags: operation.id=op_training_20251113_123456_abc123
```

**Jaeger API (Programmatic)**:
```bash
curl -s "http://localhost:16686/api/traces?tag=operation.id:op_training_20251113_123456_abc123" | jq
```

**What to Look For**:
- Does trace exist? (If no: operation not started, check backend logs)
- Which services appear? (Backend, Worker, Host Service)
- Any ERROR spans?
- Which span has longest duration?

---

### 2. Query by Service

**Use Case**: See all operations from a specific service

**Jaeger UI Query**:
```
Service: ktrdr-api
Lookback: 1h
Limit: 100
```

**Services Available**:
- `ktrdr-api` - Backend API
- `ktrdr-cli` - CLI commands
- `ktrdr-mcp-server` - MCP tools (LLM agent integration)
- `ktrdr-training-worker-{id}` - Training workers
- `ktrdr-backtest-worker-{id}` - Backtesting workers
- `ktrdr-ib-host-service` - IB Gateway integration
- `ktrdr-training-host-service` - GPU training service (if deployed)

---

### 3. Query by Operation Type

**Use Case**: See all training or backtesting operations

**Jaeger UI Query**:
```
Service: ktrdr-api
Tags: operation.type=TRAINING
Lookback: 1h
```

**Operation Types**:
- `DATA_DOWNLOAD`
- `TRAINING`
- `BACKTESTING`
- `MODEL_EVALUATION`
- `INDICATOR_COMPUTATION`
- `STRATEGY_EXECUTION`

---

### 4. Query by Error Status

**Use Case**: Find all failed operations

**Jaeger UI Query**:
```
Service: any
Tags: error=true
Lookback: 1h
```

**Or by specific error type**:
```
Tags: exception.type=ConnectionRefusedError
```

**What to Look For**:
- `exception.type` - Python exception class
- `exception.message` - Error message
- `exception.stacktrace` - Full stack trace
- `otel.status_code` - ERROR (if present)

---

### 5. Query by Business Parameters

**Use Case**: Debug issues for specific symbol/strategy

**Query by Symbol**:
```
Tags: data.symbol=AAPL
```

**Query by Strategy**:
```
Tags: training.strategy=neuro_mean_reversion
```

**Query by Worker**:
```
Tags: worker.id=worker-abc123
```

---

### 6. Query by Time Range

**Use Case**: Investigate issues during specific time window

**Jaeger UI**:
- Use "Lookback" dropdown: 1h, 6h, 12h, 24h, Custom
- Or specify exact timestamps

**Jaeger API**:
```bash
# Start/end times in microseconds since epoch
START=$(date -d "2025-11-13 10:00:00" +%s)000000
END=$(date -d "2025-11-13 11:00:00" +%s)000000

curl -s "http://localhost:16686/api/traces?service=ktrdr-api&start=$START&end=$END" | jq
```

---

### 7. Query by Trace ID

**Use Case**: Jump directly to trace (from logs or operation metadata)

**Jaeger UI**:
```
Paste trace ID in search box: 4bf92f3577b34da6a3ce929d0e0e4736
```

**Jaeger API**:
```bash
TRACE_ID="4bf92f3577b34da6a3ce929d0e0e4736"
curl -s "http://localhost:16686/api/traces/$TRACE_ID" | jq
```

---

### 8. Complex Queries (Multiple Tags)

**Use Case**: Narrow down to specific scenario

**Example**: Failed training operations for AAPL in last hour
```
Service: ktrdr-api
Tags: operation.type=TRAINING AND data.symbol=AAPL AND error=true
Lookback: 1h
```

**Example**: Worker selection issues
```
Service: ktrdr-api
Tags: worker_registry.selection_status=NO_WORKERS_AVAILABLE
```

---

## Debugging Scenarios

### Scenario 1: "Operation Stuck" (No Progress)

**Symptoms**:
- CLI shows operation started but no progress updates
- `ktrdr operations status <id>` shows 0% or low percentage
- Operation not completing after expected time

**Debugging Steps**:

1. **Query Jaeger for operation**:
   ```
   Tags: operation.id=<operation-id>
   ```

2. **Check if trace exists**:
   - **No trace**: Backend never received request
     - Check CLI → API connectivity
     - Check logs: `docker-compose logs backend | grep <operation-id>`
   - **Trace exists**: Proceed to step 3

3. **Analyze span structure**:
   ```
   Expected spans:
   - cli.{command} (if from CLI)
   - operation.register
   - worker_registry.select_worker
   - operation.dispatch
   - worker.{training|backtest}
   - {execution phases}
   ```

4. **Identify missing or stuck spans**:

   **Missing `worker_registry.select_worker`**:
   - Check: `worker_registry.total_workers` attribute
   - If `0`: No workers registered
     - **Fix**: Start workers with `docker-compose up -d`
     - Verify: `curl http://localhost:8000/api/v1/workers | jq`

   **Missing `operation.dispatch`**:
   - Worker selection failed
   - Check: `worker_registry.selection_status`
   - If `NO_WORKERS_AVAILABLE`: No capable workers
     - **Fix**: Check worker capabilities match operation requirements
     - For training: Ensure at least one worker has GPU or CPU capability
     - Restart workers if needed

   **Missing worker spans**:
   - Worker not executing operation
   - Check: `operation.dispatch` span attributes
   - If `dispatch.status=failed`: Network issue or worker crashed
     - **Fix**: Check worker logs: `docker logs ktrdr-training-worker`
     - Check worker health: `curl http://localhost:5004/health`

   **Long-running span without updates**:
   - Check span attributes for `progress.percentage`, `progress.phase`
   - If no progress updates: Check `operations_service.instance_id` in worker vs backend
     - **Fix**: Singleton mismatch - restart worker to re-register

5. **Check progress integration**:
   - Look for `progress.percentage` attribute in active span
   - Should update every few seconds
   - If stuck at same percentage: Check worker logs for exceptions

**Common Root Causes**:
- ❌ Workers not started → Start workers
- ❌ Worker crashed → Check docker logs, restart worker
- ❌ Operations service singleton mismatch → Restart worker
- ❌ Network partition → Check Docker network, firewall rules

---

### Scenario 2: "Operation Slow" (Performance Issue)

**Symptoms**:
- Operation completes but takes longer than expected
- User complains about performance degradation

**Debugging Steps**:

1. **Query Jaeger for operation**:
   ```
   Tags: operation.id=<operation-id>
   ```

2. **View trace timeline**:
   - Click on trace in Jaeger
   - View Gantt chart showing span durations

3. **Identify bottleneck spans**:
   - Sort spans by duration (longest first)
   - Look for spans consuming >50% of total time

4. **Analyze bottleneck by phase**:

   **Data Loading Slow** (`data.fetch`, `data.parse`):
   - Check `data.bars_requested` vs `data.bars_received`
   - Check `ib.latency_ms` (if using IB)
   - Check `data.source` (host service vs local)
   - **Fix**:
     - If IB latency high: Check IB Gateway performance
     - If many bars: Consider caching or reducing date range
     - If parsing slow: Profile data validation logic

   **Training Loop Slow** (`training.training_loop`):
   - Check `model.parameters` - Large models take longer
   - Check `training.epochs.total` - More epochs = more time
   - Check `training.device` - CPU vs GPU
   - **Fix**:
     - If CPU training: Use GPU worker (training-host-service)
     - If GPU utilization low: Check batch size, model architecture
     - If appropriate for model size: Performance is expected

   **Indicator Computation Slow** (`training.indicators`):
   - Check `indicators.count` - Many indicators = more time
   - **Fix**: Optimize indicator calculations, consider caching

   **Worker Selection Slow** (`worker_registry.select_worker`):
   - Should be <10ms
   - If >100ms: Check `worker_registry.total_workers`
   - **Fix**: Reduce number of workers if excessive (>100)

5. **Compare with baseline**:
   - Query historical traces for same operation type
   - Compare durations: `operation.duration_ms`
   - Identify regressions

**Common Root Causes**:
- ❌ CPU training instead of GPU → Use training-host-service
- ❌ IB Gateway slow → Restart IB Gateway
- ❌ Large data volume without caching → Enable caching
- ❌ Inefficient indicator computation → Profile and optimize

---

### Scenario 3: "Operation Failed" (Error)

**Symptoms**:
- Operation status shows `FAILED`
- Error message in CLI or API response
- Exception in logs

**Debugging Steps**:

1. **Query Jaeger for failed operations**:
   ```
   Tags: operation.id=<operation-id>
   OR
   Tags: error=true AND operation.type=TRAINING
   ```

2. **Locate ERROR span**:
   - Spans with errors highlighted in red (Jaeger UI)
   - Check `otel.status_code=ERROR`

3. **Extract error context**:
   ```
   Span attributes to check:
   - exception.type (e.g., ConnectionRefusedError, ValueError)
   - exception.message
   - exception.stacktrace
   - error.symbol (if business logic error)
   - error.strategy
   ```

4. **Analyze error by type**:

   **Connection Errors** (`ConnectionRefusedError`, `ConnectionResetError`):
   - Check `http.url` attribute on failed span
   - Common causes:
     - IB host service not running (port 5001)
     - Training host service not running (port 5002)
     - Worker not reachable
   - **Fix**:
     - Start host service: `cd ib-host-service && ./start.sh`
     - Check Docker network: `docker network inspect ktrdr-network`
     - Verify service health: `curl http://localhost:5001/health`

   **Validation Errors** (`ValueError`, `ValidationError`):
   - Check business parameters in span attributes
   - Common causes:
     - Invalid symbol format
     - Invalid date range
     - Missing required parameters
   - **Fix**: Validate input parameters, check API documentation

   **Data Errors** (`DataNotFoundError`, `InsufficientDataError`):
   - Check `data.symbol`, `data.timeframe`, `data.start_date`, `data.end_date`
   - **Fix**:
     - Verify data exists: `ktrdr data get-range <symbol> <timeframe>`
     - Load data: `ktrdr data load <symbol> <timeframe>`
     - Check IB connectivity: `ktrdr ib test-connection`

   **Worker Errors** (exceptions in worker spans):
   - Check worker logs for full context
   - Look for `operations_service.instance_id` - may indicate singleton issue
   - **Fix**: Restart worker, check configuration

5. **Trace error propagation**:
   - Follow error from origin span to root span
   - Check which service first encountered error
   - Verify error handling (should gracefully fail and update operation status)

**Common Root Causes**:
- ❌ Host service not running → Start service
- ❌ Invalid input parameters → Validate before API call
- ❌ Data not loaded → Load data first
- ❌ Network issue → Check Docker networking
- ❌ Worker crashed → Check logs, restart worker

---

### Scenario 4: "No Workers Selected"

**Symptoms**:
- Operation fails with "No workers available"
- CLI shows "Worker selection failed"

**Debugging Steps**:

1. **Query Jaeger**:
   ```
   Tags: operation.id=<operation-id>
   ```

2. **Find `worker_registry.select_worker` span**:
   - Check attributes:
     ```
     worker_registry.total_workers: 5
     worker_registry.available_workers: 3
     worker_registry.capable_workers: 0  ← Problem!
     worker_registry.selection_status: NO_CAPABLE_WORKERS
     ```

3. **Diagnose worker capability mismatch**:

   **Training operation but no GPU workers**:
   - Backend prefers GPU workers for training
   - If no GPU workers available, falls back to CPU workers
   - If no CPU workers: `NO_CAPABLE_WORKERS`
   - **Fix**:
     - Start CPU workers: `docker-compose up -d --scale training-worker=3`
     - Or start GPU worker: `cd training-host-service && ./start.sh`

   **All workers busy**:
   - `worker_registry.available_workers: 0`
   - All workers have `status=BUSY`
   - **Fix**:
     - Wait for workers to complete current operations
     - Or scale up workers: `docker-compose up -d --scale training-worker=10`

   **No workers registered**:
   - `worker_registry.total_workers: 0`
   - **Fix**:
     - Start workers: `docker-compose up -d`
     - Check worker logs for registration errors
     - Verify backend URL in worker config

4. **Verify worker registration**:
   ```bash
   curl http://localhost:8000/api/v1/workers | jq
   ```

   Expected output:
   ```json
   {
     "workers": [
       {
         "worker_id": "worker-abc123",
         "worker_type": "TRAINING",
         "status": "AVAILABLE",
         "capabilities": ["gpu", "cpu"],
         "url": "http://training-worker:5004"
       }
     ]
   }
   ```

5. **Check worker health**:
   ```bash
   curl http://localhost:5004/health
   ```

**Common Root Causes**:
- ❌ Workers not started → Start workers
- ❌ Worker type mismatch → Start appropriate worker type
- ❌ All workers busy → Scale up or wait
- ❌ Workers failed to register → Check backend URL, restart workers

---

### Scenario 5: "Trace Context Lost" (Distributed Trace Broken)

**Symptoms**:
- Multiple traces instead of one unified trace
- Can't see complete flow from CLI → Backend → Worker
- Missing parent-child relationships in spans

**Debugging Steps**:

1. **Query Jaeger by operation ID**:
   ```
   Tags: operation.id=<operation-id>
   ```

2. **Check number of traces returned**:
   - **Expected**: 1 trace with all spans
   - **If multiple traces**: Trace context not propagated

3. **Identify where context was lost**:
   - Look at last span in partial trace
   - Check if HTTP call exists to next service
   - Check if next service has trace with different `trace_id`

4. **Common break points**:

   **CLI → Backend break**:
   - httpx not instrumented in CLI
   - **Fix**: Add `HTTPXClientInstrumentor().instrument()` in CLI setup
   - Verify: Check for `traceparent` header in HTTP requests

   **Backend → Worker break**:
   - Worker not extracting `traceparent` header
   - **Fix**: Ensure `FastAPIInstrumentor.instrument_app(app)` called on worker
   - Verify: Check worker FastAPI setup

   **Backend → Host Service break**:
   - httpx not instrumented in backend
   - **Fix**: Ensure `HTTPXClientInstrumentor().instrument()` called in backend setup

5. **Verify trace propagation**:
   ```bash
   # Check if traceparent header is sent
   docker-compose logs backend | grep traceparent

   # Check if worker receives traceparent
   docker logs ktrdr-training-worker | grep traceparent
   ```

6. **Manual trace linking** (last resort):
   - Use `operation.id` to correlate traces
   - Query: `Tags: operation.id=<operation-id>` across all services
   - Manually reconstruct flow from timestamps

**Common Root Causes**:
- ❌ Auto-instrumentation not enabled → Enable in all services
- ❌ Trace context not propagated in custom HTTP client → Use instrumented client
- ❌ Service using non-HTTP communication → Add manual context propagation

---

## Span Attribute Reference

### Standard Attributes (All Spans)

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `service.name` | string | Service identifier | `ktrdr-api` |
| `service.version` | string | Application version | `1.0.0` |
| `deployment.environment` | string | Environment | `development`, `production` |
| `otel.status_code` | string | Span status | `OK`, `ERROR` |

---

### HTTP Attributes (Auto-Instrumented)

**FastAPI Endpoints**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `http.method` | string | HTTP method | `POST`, `GET` |
| `http.route` | string | Route pattern | `/api/v1/data/load` |
| `http.status_code` | int | Response status | `200`, `500` |
| `http.url` | string | Full URL | `http://localhost:8000/api/v1/data/load` |
| `http.target` | string | Path + query | `/api/v1/data/load?symbol=AAPL` |
| `net.host.name` | string | Hostname | `localhost` |
| `net.host.port` | int | Port | `8000` |

**httpx Client Requests**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `http.method` | string | HTTP method | `POST` |
| `http.url` | string | Target URL | `http://localhost:5001/download_historical_data` |
| `http.status_code` | int | Response status | `200` (or `null` if failed) |
| `error.type` | string | Error class (on failure) | `ConnectionRefusedError` |
| `net.peer.name` | string | Destination host | `localhost` |
| `net.peer.port` | int | Destination port | `5001` |

---

### Business Logic Attributes

**Operation Attributes** (all operations):

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `operation.id` | string | Unique operation ID | `op_training_20251113_123456_abc123` |
| `operation.type` | string | Operation type | `TRAINING`, `DATA_DOWNLOAD` |
| `operation.status` | string | Current status | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED` |
| `operation.duration_ms` | float | Total duration | `1234567.89` |
| `operations_service.instance_id` | string | OperationsService instance (debugging) | `ops-svc-abc123` |

**Worker Registry Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `worker_registry.total_workers` | int | Total registered workers | `5` |
| `worker_registry.available_workers` | int | Available workers | `3` |
| `worker_registry.capable_workers` | int | Workers matching capabilities | `2` |
| `worker_registry.selected_worker_id` | string | Selected worker ID | `worker-abc123` |
| `worker_registry.selection_status` | string | Selection result | `SUCCESS`, `NO_WORKERS_AVAILABLE`, `NO_CAPABLE_WORKERS` |

**Worker Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `worker.id` | string | Worker instance ID | `worker-abc123` |
| `worker.type` | string | Worker type | `TRAINING`, `BACKTESTING` |
| `worker.capabilities` | list | Worker capabilities | `["gpu", "cpu"]` |
| `worker.status` | string | Worker status | `AVAILABLE`, `BUSY` |

---

**Data Acquisition Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `data.symbol` | string | Trading symbol | `AAPL`, `EURUSD` |
| `data.timeframe` | string | Data timeframe | `1h`, `1d`, `5m` |
| `data.start_date` | string | Start date | `2024-01-01` |
| `data.end_date` | string | End date | `2024-12-31` |
| `data.provider` | string | Data source | `ib_host_service`, `local` |
| `data.bars_requested` | int | Requested bars | `1000` |
| `data.bars_received` | int | Actual bars downloaded | `987` |
| `data.rows` | int | Rows in dataset | `5000` |
| `data.columns` | int | Columns in dataset | `8` |

---

**Training Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `training.strategy` | string | Strategy name | `neuro_mean_reversion` |
| `training.symbol` | string | Training symbol | `AAPL` |
| `training.timeframe` | string | Training timeframe | `1d` |
| `training.epochs.total` | int | Total epochs | `100` |
| `training.epochs.completed` | int | Completed epochs | `45` |
| `training.current_loss` | float | Current loss value | `0.0234` |
| `training.device` | string | Training device | `cuda:0`, `cpu` |
| `model.parameters` | int | Model parameter count | `15234567` |
| `model.path` | string | Saved model path | `/app/models/...` |
| `model.size_mb` | float | Model file size | `123.45` |

---

**Backtesting Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `backtest.strategy` | string | Strategy name | `momentum_strategy` |
| `backtest.symbol` | string | Backtest symbol | `EURUSD` |
| `backtest.timeframe` | string | Backtest timeframe | `1h` |
| `backtest.start_date` | string | Backtest start | `2023-01-01` |
| `backtest.end_date` | string | Backtest end | `2024-12-31` |
| `backtest.trades_executed` | int | Total trades | `234` |
| `backtest.final_pnl` | float | Final P&L | `12345.67` |
| `backtest.sharpe_ratio` | float | Sharpe ratio | `1.85` |

---

**IB Host Service Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `ib.host` | string | IB Gateway host | `localhost` |
| `ib.port` | int | IB Gateway port | `4002` |
| `ib.connection.status` | string | Connection status | `CONNECTED`, `DISCONNECTED` |
| `ib.latency_ms` | float | IB request latency | `234.56` |

---

**Progress Attributes** (real-time updates):

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `progress.percentage` | float | Current progress | `45.6` |
| `progress.phase` | string | Current phase | `training.training_loop` |
| `progress.updated_at` | float | Last update timestamp | `1699876543.123` |

---

**CLI Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `cli.command` | string | CLI command name | `train`, `data_load` |
| `cli.args` | string | Command arguments (JSON) | `{"symbol":"AAPL"}` |
| `cli.status` | string | Command result | `success`, `error` |
| `cli.error` | string | Error message (if failed) | `Connection refused` |

---

**MCP Attributes**:

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `mcp.tool` | string | MCP tool name | `execute_training` |
| `mcp.params` | string | Tool parameters (JSON) | `{"symbol":"AAPL"}` |
| `mcp.result.status` | string | Tool result | `success`, `error` |

---

**Exception Attributes** (on errors):

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `exception.type` | string | Python exception class | `ConnectionRefusedError` |
| `exception.message` | string | Error message | `Connection refused` |
| `exception.stacktrace` | string | Full stack trace | `Traceback...` |

---

**GPU Attributes** (training-host-service):

| Attribute | Type | Description | Example |
|-----------|------|-------------|---------|
| `gpu.device` | string | GPU device | `cuda:0` |
| `gpu.memory_allocated_mb` | float | Allocated GPU memory | `2048.5` |
| `gpu.utilization_percent` | float | GPU utilization | `85.3` |

---

## Common Issues & Solutions

### Issue: "Can't Find Trace"

**Problem**: Query by operation ID returns no results

**Possible Causes**:
1. Operation never started → Check backend logs
2. Tracing not enabled → Verify OTEL setup
3. Trace not exported yet → Wait 5s (BatchSpanProcessor delay)
4. Jaeger not receiving traces → Check OTLP_ENDPOINT env var
5. Wrong service selected → Try "All Services"

**Solutions**:
```bash
# Check if Jaeger is running
curl http://localhost:16686/api/services

# Check backend logs for trace export
docker-compose logs backend | grep -i "trace\|otel"

# Verify OTLP endpoint
docker-compose exec backend env | grep OTLP_ENDPOINT

# Check trace exporter errors
docker-compose logs backend | grep -i "export\|error"
```

---

### Issue: "Trace Shows Only Backend Spans"

**Problem**: Worker/host service spans missing

**Possible Causes**:
1. Worker not instrumented → Enable OTEL in worker
2. Trace context not propagated → Check httpx instrumentation
3. Worker using different trace_id → Check traceparent header
4. Worker crashed before exporting → Check worker logs

**Solutions**:
```bash
# Check if worker is instrumented
docker logs ktrdr-training-worker | grep -i "otel\|instrumentation"

# Check if traceparent header received
docker logs ktrdr-training-worker | grep traceparent

# Verify worker health
curl http://localhost:5004/health

# Check worker trace export
docker logs ktrdr-training-worker | grep -i "trace\|export"
```

---

### Issue: "No Progress Updates in Trace"

**Problem**: `progress.percentage` attribute not updating

**Possible Causes**:
1. Progress integration not implemented → Check Phase 6.6
2. OperationsService singleton mismatch → Check `operations_service.instance_id`
3. Progress callback not called → Check business logic
4. Span not recording → Check `span.is_recording()`

**Solutions**:
```bash
# Check operations service instance ID in trace
# Backend span should match worker span

# Check worker logs for progress updates
docker logs ktrdr-training-worker | grep -i "progress"

# Verify progress callback registration
docker logs ktrdr-training-worker | grep -i "register.*progress"
```

---

### Issue: "High Trace Export Overhead"

**Problem**: Performance degradation after enabling tracing

**Possible Causes**:
1. Using SimpleSpanProcessor (synchronous) → Switch to BatchSpanProcessor
2. Too many custom spans → Reduce span creation frequency
3. Large span attributes → Limit attribute size
4. High sampling rate → Reduce if needed (not typical for KTRDR)

**Solutions**:
```python
# Verify BatchSpanProcessor is used
# In ktrdr/monitoring/setup.py
from opentelemetry.sdk.trace.export import BatchSpanProcessor

processor = BatchSpanProcessor(
    span_exporter=exporter,
    max_queue_size=2048,
    schedule_delay_millis=5000,  # Batch every 5s
    max_export_batch_size=512
)

# Limit attribute length
from opentelemetry.sdk.trace import SpanLimits

limits = SpanLimits(
    max_attribute_length=1024  # Limit attribute strings
)
provider = TracerProvider(span_limits=limits)
```

---

## Claude Code Integration

### When Claude Code Should Use Observability

**Trigger Scenarios**:

1. **User reports "stuck" operation**
   - Query Jaeger by `operation.id`
   - Analyze span durations and attributes
   - Identify stuck phase in FIRST response

2. **User reports "failed" operation**
   - Query Jaeger for ERROR spans
   - Extract `exception.type`, `exception.message`
   - Diagnose root cause in FIRST response

3. **User reports "slow" operation**
   - Query Jaeger for operation trace
   - Identify bottleneck span (longest duration)
   - Recommend optimization in FIRST response

4. **User reports "no workers"**
   - Query Jaeger for `worker_registry.select_worker` span
   - Check `worker_registry.*` attributes
   - Diagnose capability mismatch in FIRST response

5. **User asks about specific operation**
   - Query Jaeger by `operation.id`
   - Provide complete flow summary
   - Show execution phases and timings

---

### Claude Code Query Pattern

```bash
# Template for Claude Code to query Jaeger
curl -s "http://localhost:16686/api/traces?tag={TAG_KEY}:{TAG_VALUE}&limit=1" | jq '
  .data[0].spans[] |
  {
    service: .process.serviceName,
    operation: .operationName,
    duration_ms: (.duration / 1000),
    tags: .tags,
    status: (.tags[] | select(.key == "otel.status_code") | .value)
  }'
```

**Example**: Query operation by ID
```bash
OPERATION_ID="op_training_20251113_123456_abc123"
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID&limit=1" | jq '
  .data[0] |
  {
    trace_id: .traceID,
    total_spans: (.spans | length),
    services: ([.spans[].process.serviceName] | unique),
    duration_ms: (([.spans[].duration] | max) / 1000),
    has_errors: ([.spans[].tags[] | select(.key == "otel.status_code" and .value == "ERROR")] | length > 0)
  }'
```

---

### Diagnostic Workflow for Claude Code

**Step 1: Identify Issue Type**
```bash
# Check if trace exists
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '.data | length'
# 0 = operation not started
# 1+ = operation started, proceed
```

**Step 2: Extract Trace Structure**
```bash
# Get span summary
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  {
    span: .operationName,
    service: .process.serviceName,
    duration_ms: (.duration / 1000),
    error: ([.tags[] | select(.key == "error" and .value == "true")] | length > 0)
  }' | jq -s 'sort_by(.duration_ms) | reverse'
```

**Step 3: Check for Common Issues**
```bash
# Check worker selection
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  select(.operationName == "worker_registry.select_worker") |
  .tags[] |
  select(.key | startswith("worker_registry.")) |
  {key: .key, value: .value}'
```

**Step 4: Extract Error Details (if failed)**
```bash
# Get exception details
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  select(.tags[] | select(.key == "error" and .value == "true")) |
  {
    span: .operationName,
    exception_type: (.tags[] | select(.key == "exception.type") | .value),
    exception_message: (.tags[] | select(.key == "exception.message") | .value)
  }'
```

**Step 5: Provide Diagnosis**

Template response:
```
🔍 Trace Analysis for operation_id: {operation_id}

**Trace Summary**:
- Trace ID: {trace_id}
- Total Duration: {duration_ms}ms
- Services: {services}
- Status: {OK/ERROR}

**Execution Flow**:
1. {span_name} ({service}) - {duration_ms}ms
2. {span_name} ({service}) - {duration_ms}ms
...

**Diagnosis**:
{identified_issue}

**Root Cause**:
{root_cause_explanation}

**Solution**:
{recommended_fix}
```

---

### Example: Claude Code Debugging Session

**User**: "My training operation is stuck at 45%"

**Claude Code** (using observability):

```bash
# Query Jaeger
OPERATION_ID="op_training_20251113_123456_abc123"
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID&limit=1" | jq

# Analysis reveals:
# - Span: training.training_loop (duration: 900000ms = 15 minutes, still running)
# - progress.percentage: 45.0 (not updating)
# - operations_service.instance_id: ops-svc-backend-123 (in backend span)
# - operations_service.instance_id: ops-svc-worker-456 (in worker span)
# ← MISMATCH!
```

**Claude Code Response** (FIRST message):

```
🔍 I found the issue by analyzing the trace:

**Diagnosis**: Operations service singleton mismatch

**Root Cause**:
The backend's OperationsService (instance `ops-svc-backend-123`) is different from the worker's OperationsService (instance `ops-svc-worker-456`). The worker is updating progress in its local instance, but the backend is querying a different instance, so progress appears stuck.

**Solution**:
Restart the training worker to re-register with the backend and sync OperationsService instances:

```bash
docker-compose restart training-worker
```

Then re-submit the training operation.

**Prevention**:
This is a known issue with worker restarts. A fix is planned to use a centralized OperationsService (not singleton per process).
```

**Result**: Issue diagnosed and solved in ONE response (instead of 10+ messages of manual detective work)

---

## Summary

This guide enables:

✅ **Rapid Diagnosis**: Query Jaeger by operation ID, get full context
✅ **First-Response Debugging**: Claude Code identifies root cause immediately
✅ **Systematic Investigation**: Follow structured debugging workflows
✅ **Complete Visibility**: All span attributes documented for reference
✅ **Common Issues Covered**: Known problems and solutions documented

**Key Takeaway**: With Phase 6 instrumentation, every operation is fully traceable from CLI → Backend → Worker → Host Service, with business context at every step.

---

**Document End**
