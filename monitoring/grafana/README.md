# KTRDR Grafana Dashboards

This directory contains Grafana dashboard configurations for monitoring KTRDR operations.

## Available Dashboards

### 1. System Overview

**File**: `dashboards/system-overview.json`
**URL**: http://localhost:3000/d/ktrdr-system-overview

**Purpose**: High-level system health monitoring for quick status checks.

**Panels**:
- **Healthy Services** - Number of services reporting healthy status
- **Requests/sec** - Current request rate across all services
- **Error Rate** - Percentage of 5xx errors
- **P95 Latency** - 95th percentile response time
- **Request Rate by Service** - Time series of requests per service
- **Response Time Percentiles** - P50/P95/P99 latency trends
- **Errors by Status Code** - Error breakdown over time
- **Active Services** - Table of all services with status

**Use Cases**:
- Morning health check
- Initial triage of reported issues
- Verify services are running after deployment

---

### 2. Worker Status

**File**: `dashboards/worker-status.json`
**URL**: http://localhost:3000/d/ktrdr-worker-status

**Purpose**: Monitor distributed worker capacity and health.

**Panels**:
- **Registered Workers** - Total registered worker count (uses `ktrdr_workers_registered_total`)
- **Available Workers** - Workers not currently busy (uses `ktrdr_workers_available`)
- **Backtest Workers** - Registered backtest workers
- **Training Workers** - Registered training workers
- **Worker Health Matrix** - Table with per-worker status
- **Worker CPU Usage** - CPU utilization per worker
- **Worker Memory Usage** - Memory consumption per worker
- **Worker Availability Timeline** - Historical up/down status

**Use Cases**:
- Verify worker scaling worked
- Identify resource-constrained workers
- Debug "no workers available" errors
- Monitor worker stability over time

---

### 3. Operations Dashboard

**File**: `dashboards/operations.json`
**URL**: http://localhost:3000/d/ktrdr-operations

**Purpose**: Track operation execution and performance.

**Panels**:
- **Operations/Hour** - Total operations started
- **Backtests/Hour** - Backtest operations count
- **Training/Hour** - Training operations count
- **Success Rate** - Percentage of successful operations
- **Operations by Type** - Pie chart distribution
- **Operation Duration** - Average backtest duration
- **Success vs Failure Rate** - Success/failure trends
- **HTTP Status Distribution** - Status code breakdown

**Use Cases**:
- Monitor operation throughput
- Track success rates over time
- Identify duration regressions
- Debug operation failures

---

## Diagnostic Workflows

### "Something is slow"

1. **Start**: System Overview dashboard
2. **Check**: P95 Latency panel for current value
3. **Drill down**: Response Time Percentiles for trends
4. **Correlate**: Check Request Rate to see if it's load-related
5. **Next**: If workers involved, check Worker Status → CPU Usage

### "Operation failed"

1. **Start**: Operations Dashboard
2. **Check**: Success Rate panel
3. **Drill down**: Success vs Failure Rate for when it started
4. **Identify**: HTTP Status Distribution for error type
5. **Next**: Check Jaeger traces for detailed error

### "Workers not working"

1. **Start**: Worker Status dashboard
2. **Check**: Healthy Workers count
3. **Drill down**: Worker Health Matrix for specific workers
4. **Identify**: Worker Availability Timeline for when issues started
5. **Check**: CPU/Memory for resource exhaustion

### "Is the system healthy?"

1. **Start**: System Overview dashboard
2. **Verify**: Healthy Services = expected count
3. **Verify**: Error Rate < 1%
4. **Verify**: P95 Latency < 100ms (or baseline)
5. **Done**: If all green, system is healthy

---

## Configuration

### Provisioning

Dashboards are auto-provisioned via `dashboards.yml`:

```yaml
providers:
  - name: 'KTRDR Dashboards'
    folder: 'KTRDR'
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

### Data Sources

- **Prometheus**: Metrics (datasources.yml)
- **Jaeger**: Traces (datasources.yml)

### Auto-Refresh

All dashboards default to:
- Refresh interval: 30 seconds
- Time range: Last 1 hour

---

## Customization

### Adding Panels

1. Edit the dashboard in Grafana UI
2. Export JSON from dashboard settings
3. Replace the file in `dashboards/`
4. Commit to git

### Creating New Dashboards

1. Create dashboard in Grafana UI
2. Export as JSON
3. Save to `dashboards/` directory
4. Add tests to `tests/monitoring/test_dashboards.py`
5. Document in this README

### Key Metrics

Reference for building new panels:

```promql
# Service health
up{job=~"ktrdr.*"}

# Request rate
rate(http_server_duration_milliseconds_count[5m])

# Error rate
rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[5m])

# Latency percentiles
histogram_quantile(0.95, rate(http_server_duration_milliseconds_bucket[5m]) by (le))
```

### Custom Business Metrics

KTRDR exposes custom Prometheus metrics for operational visibility:

```promql
# Worker metrics
ktrdr_workers_registered_total{worker_type="backtesting|training"}  # Registered workers
ktrdr_workers_available{worker_type="backtesting|training"}         # Available (not busy) workers

# Operation metrics
ktrdr_operations_active                                             # Currently active operations
ktrdr_operations_total{operation_type="...", status="..."}          # Total operations counter
ktrdr_operation_duration_seconds{operation_type="...", status="..."} # Duration histogram

# Example queries
sum(ktrdr_workers_registered_total)                                 # Total registered workers
sum(ktrdr_workers_available)                                        # Total available workers
sum(increase(ktrdr_operations_total[1h]))                           # Operations in last hour
sum(ktrdr_operations_total{status="completed"}) / sum(ktrdr_operations_total) * 100  # Success rate
```

---

## Troubleshooting

### Dashboards not loading

1. Check Grafana logs: `docker compose logs grafana`
2. Verify mounts: `docker compose exec grafana ls /var/lib/grafana/dashboards`
3. Check JSON validity: `jq . dashboards/system-overview.json`

### No data in panels

1. Verify Prometheus running: http://localhost:9090
2. Check Prometheus targets: http://localhost:9090/targets
3. Verify data source in Grafana: Settings → Data Sources
4. Run operations to generate data

### Panels show "No data"

1. Check time range (may need to expand)
2. Verify query in panel edit mode
3. Check Prometheus for actual data: http://localhost:9090/graph

---

## Related Documentation

- [TELEMETRY_AUDIT.md](TELEMETRY_AUDIT.md) - Available metrics
- [DASHBOARD_DESIGN.md](DASHBOARD_DESIGN.md) - Panel specifications
- [docs/debugging/observability-debugging-workflows.md](../../docs/debugging/observability-debugging-workflows.md) - Jaeger debugging
