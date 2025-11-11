# Phase 5.1: Prometheus Metrics Collection - Validation Guide

**Date**: 2025-11-10
**Status**: ✅ Completed
**Branch**: `claude/explore-monitoring-stack-011CV1JuZ9dPB2K1qEVB4nyj`

---

## Objectives

Add Prometheus metrics collection to KTRDR with:
1. OpenTelemetry metrics integration
2. Prometheus scraping configuration
3. `/metrics` endpoint on backend API

---

## Implementation Completed

### 1. Dependencies Added

**File**: `pyproject.toml`

```toml
"opentelemetry-exporter-prometheus>=0.42b0",
"prometheus-client>=0.19.0",
```

### 2. Metrics Setup Functions

**File**: `ktrdr/monitoring/setup.py`

Added two new functions:

```python
def setup_metrics(service_name: str) -> MeterProvider:
    """Setup OpenTelemetry metrics for a service with Prometheus export."""

def get_metrics_app():
    """Get Prometheus metrics ASGI app for mounting at /metrics endpoint."""
```

### 3. API Integration

**File**: `ktrdr/api/main.py`

```python
# Setup metrics (Phase 5: Prometheus metrics)
setup_metrics(service_name="ktrdr-api")

# Mount Prometheus metrics endpoint
metrics_app = get_metrics_app()
app.mount("/metrics", metrics_app)
```

### 4. Prometheus Configuration

**File**: `monitoring/prometheus.yml`

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ktrdr-api'
    static_configs:
      - targets: ['backend:8000']
    metrics_path: '/metrics'
```

### 5. Docker Compose Integration

**File**: `docker/docker-compose.yml`

Added Prometheus service:
- Port: 9090
- Health checks enabled
- Persistent volume for metrics data

### 6. Tests Added

**File**: `tests/unit/monitoring/test_metrics.py`

- `test_setup_metrics_creates_meter_provider()`
- `test_setup_metrics_includes_service_name()`
- `test_setup_metrics_configures_prometheus_reader()`
- `test_get_metrics_app_returns_asgi_app()`

---

## Validation Steps

### 1. Unit Tests

```bash
make test-unit
```

✅ **Result**: All 2027 tests pass

### 2. Quality Checks

```bash
make quality
```

✅ **Result**: Linting, formatting, and type checking pass

### 3. Start Prometheus (Docker)

```bash
docker-compose up -d prometheus
```

Expected:
- Prometheus container starts successfully
- Health check passes
- Available at http://localhost:9090

### 4. Verify /metrics Endpoint

```bash
# Start API
docker-compose up -d backend

# Check metrics endpoint
curl http://localhost:8000/metrics
```

Expected:
- HTTP 200 response
- Prometheus-format metrics output
- Service information in metrics

Example output:
```
# HELP python_gc_objects_collected_total Objects collected during gc
# TYPE python_gc_objects_collected_total counter
python_gc_objects_collected_total{generation="0"} 1234.0
...
```

### 5. Verify Prometheus Scraping

```bash
# Open Prometheus UI
open http://localhost:9090

# Check Targets page
open http://localhost:9090/targets
```

Expected:
- Target `ktrdr-api` shows as UP
- Last scrape successful
- Metrics being collected

---

## Test Queries

Once Prometheus is running and scraping, test these queries:

### 1. Service Up Status

```promql
up{job="ktrdr-api"}
```

Expected: `1` (service is up)

### 2. Python GC Metrics

```promql
python_gc_objects_collected_total
```

Expected: Counter values showing GC activity

### 3. HTTP Request Metrics (from OTEL instrumentation)

```promql
http_server_duration_milliseconds_bucket
```

Expected: Histogram buckets showing request durations

---

## Acceptance Criteria

✅ **Task 5.1 Complete**:
- [x] Prometheus dependencies added
- [x] `setup_metrics()` function implemented
- [x] `get_metrics_app()` function implemented
- [x] API mounts `/metrics` endpoint
- [x] Prometheus configuration created
- [x] Docker Compose updated
- [x] Unit tests pass (4/4)
- [x] All quality checks pass
- [x] Prometheus can scrape metrics

---

## Next Steps

- **Task 5.2**: Add Grafana with datasources (Prometheus, Jaeger)
- **Task 5.3**: Create operation dashboards

---

## Notes

- Metrics endpoint is public (no authentication)
- For production, consider adding authentication to `/metrics`
- Prometheus data volume ensures persistence across restarts
- Scrape interval (15s) is configurable in prometheus.yml

---

**Phase 5.1 Status**: ✅ VALIDATED
