# KTRDR Telemetry Audit

**Date**: 2025-11-22
**Purpose**: Document available metrics and spans for Grafana dashboard design

---

## Prometheus Metrics

### HTTP Server Metrics (Backend/Workers)

| Metric | Type | Description | Dashboard Use |
|--------|------|-------------|---------------|
| `http_server_duration_milliseconds_*` | Histogram | Request latency | Response time P50/P95/P99 |
| `http_server_active_requests` | Gauge | Current active requests | Active load indicator |
| `http_server_request_size_bytes_*` | Histogram | Request payload sizes | Bandwidth monitoring |
| `http_server_response_size_bytes_*` | Histogram | Response payload sizes | Bandwidth monitoring |

### HTTP Client Metrics

| Metric | Type | Description | Dashboard Use |
|--------|------|-------------|---------------|
| `http_client_duration_milliseconds_*` | Histogram | Outbound request latency | Worker-to-backend latency |

### Process Metrics

| Metric | Type | Description | Dashboard Use |
|--------|------|-------------|---------------|
| `process_cpu_seconds_total` | Counter | CPU time used | CPU usage rate |
| `process_resident_memory_bytes` | Gauge | Memory usage | Memory monitoring |
| `process_virtual_memory_bytes` | Gauge | Virtual memory | Memory monitoring |
| `process_open_fds` | Gauge | Open file descriptors | Resource exhaustion |
| `process_max_fds` | Gauge | Max file descriptors | Resource limits |
| `process_start_time_seconds` | Gauge | Process start time | Uptime calculation |

### Python Runtime Metrics

| Metric | Type | Description | Dashboard Use |
|--------|------|-------------|---------------|
| `python_gc_collections_total` | Counter | GC collections | Performance insights |
| `python_gc_objects_collected_total` | Counter | Objects collected | Memory pressure |
| `python_gc_objects_uncollectable_total` | Counter | Uncollectable objects | Memory leak detection |
| `python_info` | Info | Python version | System info |

### Scrape Metrics

| Metric | Type | Description | Dashboard Use |
|--------|------|-------------|---------------|
| `up` | Gauge | Target availability | Service health |
| `scrape_duration_seconds` | Gauge | Scrape duration | Prometheus performance |
| `target_info` | Info | Target metadata | Service identification |

---

## Jaeger Services

### ktrdr-api (Backend)

**35 operations** including:

#### HTTP Endpoints
- `GET /api/v1/health` - Health check
- `GET /api/v1/workers` - List workers
- `POST /api/v1/workers/register` - Worker registration
- `POST /api/v1/backtests/start` - Start backtest
- `GET /api/v1/operations/{operation_id}` - Get operation status
- `GET /api/v1/operations/{operation_id}/metrics` - Get operation metrics
- `GET /metrics` - Prometheus metrics
- `POST /backtests/start` - Worker backtest endpoint

#### Internal Operations
- `operation.register` - Operation registration
- `operation.state_transition` - Operation state changes
- `operations.create` - Create new operation
- `operations.list` - List operations
- `workers.list` - List registered workers
- `workers.select` - Select worker for task

#### Backtest Operations
- `backtest.data_loading` - Load market data
- `backtest.strategy_init` - Initialize strategy
- `backtest.simulation` - Run simulation

### ktrdr-cli (CLI)

**3 operations**:
- `cli.backtest_run` - Run backtest from CLI
- `GET` - HTTP client requests
- `POST` - HTTP client requests

---

## Key Metrics for Dashboards

### System Overview Dashboard

**Service Health**
- `up{job=~"ktrdr.*"}` - All KTRDR services health
- Labels: `job`, `instance`

**Request Rates**
- `rate(http_server_duration_milliseconds_count[5m])` - Requests per second
- Filter by `http_method`, `http_route`, `http_status_code`

**Error Rates**
- `rate(http_server_duration_milliseconds_count{http_status_code=~"5.*"}[5m])` - 5xx errors
- `rate(http_server_duration_milliseconds_count{http_status_code=~"4.*"}[5m])` - 4xx errors

**Response Time Percentiles**
- `histogram_quantile(0.50, rate(http_server_duration_milliseconds_bucket[5m]))` - P50
- `histogram_quantile(0.95, rate(http_server_duration_milliseconds_bucket[5m]))` - P95
- `histogram_quantile(0.99, rate(http_server_duration_milliseconds_bucket[5m]))` - P99

**Resource Usage**
- `process_resident_memory_bytes` - Memory per service
- `rate(process_cpu_seconds_total[5m])` - CPU rate per service

### Worker Status Dashboard

**Registered Workers**
- Query Prometheus for `up{job="ktrdr-workers"}` or filter by instance
- Note: Worker count currently tracked via Jaeger spans (workers.list)

**Worker Health**
- `up{instance=~".*:500[3-8]"}` - Worker endpoints health
- Use `target_info` for metadata

**Operations per Worker**
- Need to extract from Jaeger traces or add custom metrics
- Consider: `worker.operation.count` (not currently available)

### Operations Dashboard

**Active Operations**
- Need custom metrics (not currently available in Prometheus)
- Can trace via Jaeger: `operation.register`, `operation.state_transition`

**Operation Duration**
- Jaeger spans: `backtest.simulation`, `backtest.data_loading`
- Consider adding histogram metrics for operation durations

**Success/Failure Rates**
- HTTP status codes from `http_server_duration_milliseconds_count`
- Filter by backtest/training endpoints

---

## Gaps & Recommendations

### Missing Metrics (Recommended to Add)

1. **Worker Registry Metrics**
   - `ktrdr_workers_registered_total` - Total registered workers
   - `ktrdr_workers_available` - Currently available workers

2. **Operation Metrics**
   - `ktrdr_operations_active` - Active operations gauge
   - `ktrdr_operations_total` - Total operations counter (by type, status)
   - `ktrdr_operation_duration_seconds` - Operation duration histogram

3. **Business Metrics**
   - `ktrdr_backtests_completed_total` - Backtests completed
   - `ktrdr_training_runs_total` - Training runs completed
   - `ktrdr_data_downloads_total` - Data downloads completed

### Dashboard Design Notes

1. **Use Labels Effectively**
   - Filter by `job` for service type
   - Filter by `instance` for specific service
   - Filter by `http_route` for endpoint

2. **Time Ranges**
   - Default: Last 1 hour for operational view
   - Last 24h for trend analysis
   - Auto-refresh: 30 seconds

3. **Panel Types**
   - Stat panels for counts (workers, operations)
   - Time series for rates and latencies
   - Tables for detailed breakdowns
   - Pie charts for distribution (operation types)

---

## Next Steps

1. Create System Overview dashboard with available metrics
2. Create Worker Status dashboard (limited by available metrics)
3. Create Operations dashboard (limited by available metrics)
4. Consider adding custom metrics to fill gaps in future iteration

---

**Related Documents**:
- [PLAN_3_OBSERVABILITY.md](../../docs/architecture/pre-prod-deployment/PLAN_3_OBSERVABILITY.md)
- [datasources.yml](datasources.yml)
- [dashboards.yml](dashboards.yml)
