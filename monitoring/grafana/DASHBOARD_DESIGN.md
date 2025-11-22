# KTRDR Dashboard Design

**Date**: 2025-11-22
**Purpose**: Define Grafana dashboard structure and panel specifications

---

## Dashboard Overview

Three dashboards targeting different operational concerns:

| Dashboard | Purpose | Primary Users |
|-----------|---------|---------------|
| System Overview | Health monitoring, quick status | All operators |
| Worker Status | Worker capacity and distribution | DevOps, debugging |
| Operations | Task tracking and performance | Developers, debugging |

---

## 1. System Overview Dashboard

**File**: `dashboards/system-overview.json`
**Refresh**: 30s
**Time Range**: Last 1 hour (default)

### Layout (4 columns)

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Services   │  Request    │   Error     │  Response   │
│   Health    │    Rate     │    Rate     │  Time P95   │
│   (Stat)    │   (Stat)    │   (Stat)    │   (Stat)    │
├─────────────┴─────────────┴─────────────┴─────────────┤
│                                                        │
│              Request Rate (Time Series)                │
│                                                        │
├────────────────────────────┬───────────────────────────┤
│                            │                           │
│   Response Time P50/P95    │      Error Rate           │
│      (Time Series)         │     (Time Series)         │
│                            │                           │
├────────────────────────────┴───────────────────────────┤
│                                                        │
│              Active Services (Table)                   │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Panel Specifications

#### Row 1: Key Metrics (Stat Panels)

**Panel 1: Services Health**
- Type: Stat
- Query: `sum(up{job=~"ktrdr.*"})`
- Thresholds: Green ≥4, Yellow ≥2, Red <2
- Title: "Healthy Services"

**Panel 2: Request Rate**
- Type: Stat
- Query: `sum(rate(http_server_duration_milliseconds_count[5m]))`
- Unit: reqps
- Title: "Requests/sec"

**Panel 3: Error Rate**
- Type: Stat
- Query: `sum(rate(http_server_duration_milliseconds_count{http_status_code=~"5.."}[5m])) / sum(rate(http_server_duration_milliseconds_count[5m])) * 100`
- Unit: percent
- Thresholds: Green <1%, Yellow <5%, Red ≥5%
- Title: "Error Rate"

**Panel 4: Response Time P95**
- Type: Stat
- Query: `histogram_quantile(0.95, sum(rate(http_server_duration_milliseconds_bucket[5m])) by (le))`
- Unit: ms
- Thresholds: Green <100ms, Yellow <500ms, Red ≥500ms
- Title: "P95 Latency"

#### Row 2: Request Rate Time Series

**Panel 5: Request Rate Over Time**
- Type: Time Series
- Query: `sum by (job) (rate(http_server_duration_milliseconds_count[5m]))`
- Legend: `{{job}}`
- Title: "Request Rate by Service"

#### Row 3: Latency and Errors

**Panel 6: Response Time Percentiles**
- Type: Time Series
- Queries:
  - P50: `histogram_quantile(0.50, sum(rate(http_server_duration_milliseconds_bucket[5m])) by (le))`
  - P95: `histogram_quantile(0.95, sum(rate(http_server_duration_milliseconds_bucket[5m])) by (le))`
  - P99: `histogram_quantile(0.99, sum(rate(http_server_duration_milliseconds_bucket[5m])) by (le))`
- Unit: ms
- Title: "Response Time Percentiles"

**Panel 7: Error Rate Over Time**
- Type: Time Series
- Query: `sum by (http_status_code) (rate(http_server_duration_milliseconds_count{http_status_code=~"[45].."}[5m]))`
- Legend: `{{http_status_code}}`
- Title: "Errors by Status Code"

#### Row 4: Service Details

**Panel 8: Active Services Table**
- Type: Table
- Query: `up{job=~"ktrdr.*"}`
- Columns: Service (job), Instance, Status (up), Uptime
- Transform: Add uptime from `process_start_time_seconds`
- Title: "Active Services"

---

## 2. Worker Status Dashboard

**File**: `dashboards/worker-status.json`
**Refresh**: 30s
**Time Range**: Last 1 hour (default)

### Layout

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  Registered │   Healthy   │  Backtest   │  Training   │
│   Workers   │   Workers   │   Workers   │   Workers   │
│   (Stat)    │   (Stat)    │   (Stat)    │   (Stat)    │
├─────────────┴─────────────┴─────────────┴─────────────┤
│                                                        │
│              Worker Health Matrix (Table)              │
│                                                        │
├────────────────────────────┬───────────────────────────┤
│                            │                           │
│   Worker CPU Usage         │   Worker Memory Usage     │
│     (Time Series)          │      (Time Series)        │
│                            │                           │
├────────────────────────────┴───────────────────────────┤
│                                                        │
│          Worker Availability Timeline                  │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Panel Specifications

#### Row 1: Worker Counts (Stat Panels)

**Panel 1: Registered Workers**
- Type: Stat
- Query: `count(up{instance=~".*:500[3-8]"})`
- Title: "Registered Workers"

**Panel 2: Healthy Workers**
- Type: Stat
- Query: `sum(up{instance=~".*:500[3-8]"})`
- Thresholds: Green ≥4, Yellow ≥2, Red <2
- Title: "Healthy Workers"

**Panel 3: Backtest Workers**
- Type: Stat
- Query: `sum(up{instance=~".*:500[37]"})` (ports 5003, 5007)
- Title: "Backtest Workers"

**Panel 4: Training Workers**
- Type: Stat
- Query: `sum(up{instance=~".*:500[568]"})` (ports 5005, 5006, 5008)
- Title: "Training Workers"

#### Row 2: Worker Health Matrix

**Panel 5: Worker Health Matrix**
- Type: Table
- Query: `up{instance=~".*:500[3-8]"}`
- Columns: Instance, Port, Status, Memory, CPU
- Additional queries for memory/CPU per instance
- Title: "Worker Health Matrix"

#### Row 3: Resource Usage

**Panel 6: Worker CPU Usage**
- Type: Time Series
- Query: `rate(process_cpu_seconds_total{instance=~".*:500[3-8]"}[5m]) * 100`
- Legend: `{{instance}}`
- Unit: percent
- Title: "Worker CPU Usage"

**Panel 7: Worker Memory Usage**
- Type: Time Series
- Query: `process_resident_memory_bytes{instance=~".*:500[3-8]"}`
- Legend: `{{instance}}`
- Unit: bytes
- Title: "Worker Memory Usage"

#### Row 4: Availability Timeline

**Panel 8: Worker Availability Timeline**
- Type: State Timeline
- Query: `up{instance=~".*:500[3-8]"}`
- Legend: `{{instance}}`
- Title: "Worker Availability"

---

## 3. Operations Dashboard

**File**: `dashboards/operations.json`
**Refresh**: 30s
**Time Range**: Last 1 hour (default)

### Layout

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│   Total     │  Backtest   │  Training   │   Success   │
│   Ops/hr    │   Ops/hr    │   Ops/hr    │    Rate     │
│   (Stat)    │   (Stat)    │   (Stat)    │   (Stat)    │
├─────────────┴─────────────┴─────────────┴─────────────┤
│                                                        │
│         Operations by Type (Pie Chart)                 │
│                                                        │
├────────────────────────────┬───────────────────────────┤
│                            │                           │
│   Operation Duration       │   Success/Failure Rate    │
│   Distribution (Histogram) │      (Time Series)        │
│                            │                           │
├────────────────────────────┴───────────────────────────┤
│                                                        │
│          Recent Operations (Table)                     │
│                                                        │
└────────────────────────────────────────────────────────┘
```

### Panel Specifications

#### Row 1: Operation Counts (Stat Panels)

**Panel 1: Total Operations/Hour**
- Type: Stat
- Query: `sum(increase(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start"}[1h]))`
- Title: "Operations/Hour"

**Panel 2: Backtest Operations/Hour**
- Type: Stat
- Query: `sum(increase(http_server_duration_milliseconds_count{http_route=~".*/backtests/start"}[1h]))`
- Title: "Backtests/Hour"

**Panel 3: Training Operations/Hour**
- Type: Stat
- Query: `sum(increase(http_server_duration_milliseconds_count{http_route=~".*/training/start"}[1h]))`
- Title: "Training/Hour"

**Panel 4: Success Rate**
- Type: Stat
- Query: `sum(rate(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start",http_status_code="200"}[1h])) / sum(rate(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start"}[1h])) * 100`
- Unit: percent
- Thresholds: Green ≥95%, Yellow ≥80%, Red <80%
- Title: "Success Rate"

#### Row 2: Operations Distribution

**Panel 5: Operations by Type**
- Type: Pie Chart
- Query: `sum by (http_route) (increase(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start|.*/data/.*"}[1h]))`
- Legend: `{{http_route}}`
- Title: "Operations by Type"

#### Row 3: Duration and Success

**Panel 6: Operation Duration Distribution**
- Type: Histogram
- Query: `sum(rate(http_server_duration_milliseconds_bucket{http_route=~".*/backtests/start"}[5m])) by (le)`
- Title: "Backtest Duration Distribution"

**Panel 7: Success/Failure Rate Over Time**
- Type: Time Series
- Queries:
  - Success: `sum(rate(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start",http_status_code="200"}[5m]))`
  - Failure: `sum(rate(http_server_duration_milliseconds_count{http_route=~".*/backtests/start|.*/training/start",http_status_code=~"[45].."}[5m]))`
- Title: "Success vs Failure Rate"

#### Row 4: Recent Operations

**Panel 8: Recent Operations Table**
- Type: Table
- Data Source: Jaeger (traces)
- Query: Search for `operation.register` spans
- Columns: Time, Operation ID, Type, Duration, Status
- Title: "Recent Operations"
- Note: May need Jaeger data source plugin or alternative approach

---

## Variables (Dashboard-Wide)

### Time Range Variable
- Name: `timeRange`
- Options: Last 15m, 1h, 6h, 24h, 7d
- Default: 1h

### Service Filter (System Overview)
- Name: `service`
- Query: `label_values(up, job)`
- Multi-select: Yes

### Worker Filter (Worker Status)
- Name: `worker`
- Query: `label_values(up{instance=~".*:500[3-8]"}, instance)`
- Multi-select: Yes

---

## Drill-Down Strategy

1. **System Overview → Worker Status**: Click on worker count to see worker details
2. **System Overview → Operations**: Click on request rate to see operation breakdown
3. **Worker Status → Operations**: Click on worker to filter operations by that worker
4. **Operations → Jaeger**: Click on operation to open trace in Jaeger

Implementation: Use Grafana data links with variable interpolation.

---

## Color Scheme

- **Green**: Healthy, success, normal
- **Yellow**: Warning, degraded
- **Red**: Error, failure, critical
- **Blue**: Informational, neutral

---

## Notes

1. **Limited Operation Metrics**: Current metrics focus on HTTP requests, not operation lifecycle. Future enhancement: add custom operation metrics.

2. **Worker Identification**: Workers identified by port (5003-5008), not worker type. Consider adding labels in future.

3. **Jaeger Integration**: Recent Operations table ideally uses Jaeger traces, but may need alternative approach if Jaeger data source plugin unavailable.

4. **Threshold Tuning**: Initial thresholds are estimates. Tune based on actual workload patterns.

---

## Implementation Order

1. System Overview (most useful for general monitoring)
2. Worker Status (critical for distributed system)
3. Operations (requires more complex queries)

---

**Related Documents**:
- [TELEMETRY_AUDIT.md](TELEMETRY_AUDIT.md) - Available metrics
- [PLAN_3_OBSERVABILITY.md](../../docs/architecture/pre-prod-deployment/PLAN_3_OBSERVABILITY.md)
