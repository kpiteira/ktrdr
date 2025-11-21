# Project 3: Observability Dashboards

**Status**: Ready for Implementation
**Estimated Effort**: Medium
**Prerequisites**: Project 1b (Local Dev Environment)

---

## Goal

Create Grafana dashboards that provide meaningful operational visibility using the OTEL telemetry already being collected by the system.

---

## Context

KTRDR already has comprehensive OpenTelemetry instrumentation with traces going to Jaeger and metrics to Prometheus. However, there are currently zero dashboards utilizing this data. This project creates dashboards for local development that will later evolve for pre-prod (Project 5).

---

## Tasks

### Task 3.1: Audit Available Metrics and Spans

**Goal**: Understand what telemetry data is available

**Actions**:
1. Start local dev environment
2. Run some operations (backtests, data downloads)
3. Query Prometheus for available metrics
4. Query Jaeger for available spans/services
5. Document available data for dashboard design

**Prometheus Exploration**:
```bash
# List all metrics
curl -s http://localhost:9090/api/v1/label/__name__/values | jq

# Check specific metric
curl -s 'http://localhost:9090/api/v1/query?query=up' | jq
```

**Jaeger Exploration**:
```bash
# List services
curl -s http://localhost:16686/api/services | jq

# Get operations for a service
curl -s 'http://localhost:16686/api/operations?service=ktrdr-backend' | jq
```

**Acceptance Criteria**:
- [ ] List of available Prometheus metrics documented
- [ ] List of Jaeger services and operations documented
- [ ] Key metrics identified for dashboards

---

### Task 3.2: Design Dashboard Structure

**Goal**: Plan dashboard layout and panels

**Proposed Dashboards**:

1. **System Overview**
   - Service health status
   - Request rates
   - Error rates
   - Resource usage (if available)

2. **Worker Status**
   - Worker registration status
   - Operations per worker
   - Worker availability
   - Queue depth (if available)

3. **Operations**
   - Active operations
   - Operation duration
   - Success/failure rates
   - Operation types breakdown

**Actions**:
1. Sketch dashboard layouts
2. Define panels for each dashboard
3. Identify which metrics feed each panel
4. Plan drill-down from overview to detail

**Acceptance Criteria**:
- [ ] Dashboard structure documented
- [ ] Panels defined with data sources
- [ ] Layout makes operational sense

---

### Task 3.3: Create System Overview Dashboard

**File**: `monitoring/grafana/dashboards/system-overview.json`

**Panels to Include**:
- Service Health (stat panel showing up/down)
- Request Rate (time series)
- Error Rate (time series)
- Response Time P50/P95 (time series)
- Active Services (table)

**Actions**:
1. Create dashboard JSON file
2. Add service health panel using `up` metric
3. Add request rate panel (if HTTP metrics available)
4. Add error rate panel
5. Add response time percentiles
6. Configure auto-refresh (30s)
7. Test in Grafana

**Acceptance Criteria**:
- [ ] Dashboard loads without errors
- [ ] Service health shows backend and workers
- [ ] Panels update with real data
- [ ] Auto-refresh working

---

### Task 3.4: Create Worker Status Dashboard

**File**: `monitoring/grafana/dashboards/worker-status.json`

**Panels to Include**:
- Registered Workers (stat)
- Worker Health Matrix (table)
- Operations by Worker (bar chart)
- Worker Availability Timeline (time series)

**Actions**:
1. Create dashboard JSON file
2. Add registered workers count
3. Add worker health matrix
4. Add operations distribution
5. Test with multiple workers running

**Acceptance Criteria**:
- [ ] Dashboard shows all 4 workers from local dev
- [ ] Health status accurate
- [ ] Operations distribution visible after running tasks

---

### Task 3.5: Create Operations Dashboard

**File**: `monitoring/grafana/dashboards/operations.json`

**Panels to Include**:
- Active Operations (stat)
- Operations by Type (pie chart)
- Operation Duration Distribution (histogram)
- Recent Operations (table with status)
- Success/Failure Rate (time series)

**Actions**:
1. Create dashboard JSON file
2. Add active operations count
3. Add operations breakdown by type
4. Add duration metrics
5. Add recent operations table
6. Test with actual operations

**Acceptance Criteria**:
- [ ] Dashboard shows operation metrics
- [ ] Types breakdown accurate
- [ ] Duration metrics populate after operations
- [ ] Recent operations table updates

---

### Task 3.6: Configure Dashboard Provisioning

**File**: `monitoring/grafana/dashboards.yml`

**Goal**: Auto-provision dashboards on Grafana startup

**Actions**:
1. Update dashboards.yml to point to dashboard directory
2. Configure dashboard provider
3. Test dashboards load on fresh Grafana start
4. Verify dashboards appear in Grafana UI

**Config**:
```yaml
apiVersion: 1

providers:
  - name: 'KTRDR Dashboards'
    orgId: 1
    folder: 'KTRDR'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards
```

**Acceptance Criteria**:
- [ ] Dashboards auto-provision on startup
- [ ] Dashboards appear in KTRDR folder
- [ ] No manual import required

---

### Task 3.7: Update docker-compose.dev.yml for Dashboards

**Goal**: Mount dashboard files into Grafana container

**Actions**:
1. Add volume mount for dashboards directory
2. Ensure dashboards.yml provisioning config is mounted
3. Test fresh start loads dashboards

**Docker Compose Update**:
```yaml
grafana:
  image: grafana/grafana:latest
  volumes:
    - grafana_data:/var/lib/grafana
    - ./monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml
    - ./monitoring/grafana/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
```

**Acceptance Criteria**:
- [ ] Dashboard files mounted correctly
- [ ] Grafana loads dashboards on startup
- [ ] Changes to JSON files reflected after restart

---

### Task 3.8: Test Dashboards with Real Workload

**Goal**: Verify dashboards show meaningful data under load

**Actions**:
1. Start local dev environment
2. Run various operations:
   - Data downloads
   - Backtests
   - Training (if available)
3. Check each dashboard shows expected data
4. Verify drill-down works (if implemented)
5. Check error scenarios display correctly

**Test Scenarios**:
```bash
# Start environment
docker compose -f docker-compose.dev.yml up -d

# Run some operations via CLI
ktrdr data load AAPL 1d --start-date 2024-01-01
ktrdr operations list

# Check dashboards at http://localhost:3000
```

**Acceptance Criteria**:
- [ ] System Overview shows healthy services
- [ ] Worker Status shows 4 workers
- [ ] Operations dashboard populates with tasks
- [ ] Data is accurate and timely

---

### Task 3.9: Document Dashboard Usage

**Goal**: Help users understand and use the dashboards

**Actions**:
1. Document each dashboard's purpose
2. Explain key panels and what they show
3. Document common diagnostic workflows
4. Add screenshots to documentation
5. Update CLAUDE.md debugging section to reference dashboards

**Documentation Content**:
- Dashboard descriptions
- Key metrics explained
- How to use for troubleshooting
- How to customize/extend

**Acceptance Criteria**:
- [ ] Each dashboard documented
- [ ] Diagnostic workflows explained
- [ ] Screenshots included
- [ ] CLAUDE.md updated

---

## Validation

**Final Verification**:
```bash
# 1. Start fresh environment
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d

# 2. Wait for services
sleep 30

# 3. Open Grafana
open http://localhost:3000

# 4. Verify dashboards provisioned
# Check KTRDR folder contains all dashboards

# 5. Run workload
ktrdr data load AAPL 1d --start-date 2024-01-01
# Run a backtest if available

# 6. Check each dashboard shows data
# - System Overview: services healthy
# - Worker Status: 4 workers visible
# - Operations: tasks visible

# 7. Verify auto-refresh works
# Wait 30s and check panels update
```

---

## Success Criteria

- [ ] Three dashboards created (System Overview, Worker Status, Operations)
- [ ] Dashboards auto-provision on Grafana startup
- [ ] Panels show real data from Prometheus/Jaeger
- [ ] Auto-refresh working
- [ ] Documentation complete
- [ ] Useful for actual debugging/monitoring

---

## Dependencies

**Depends on**: Project 1b (Local Dev Environment)
**Blocks**: Project 5 (Pre-prod Deployment) - dashboards will be evolved for pre-prod

---

## Notes

- Start simple - these dashboards can be enhanced over time
- Focus on operationally useful information
- Dashboard JSON can be exported from Grafana UI for easier editing
- Pre-prod will need adjusted targets (different hostnames/IPs)

---

## Future Enhancements

- Alert rules for critical conditions
- More detailed drill-down dashboards
- Database performance dashboard
- Network/latency dashboard
- Log aggregation integration (Loki)

---

**Previous Project**: [Project 2: CI/CD & GHCR](PLAN_2_CICD_GHCR.md)
**Next Project**: [Project 4: Secrets & Deployment CLI](PLAN_4_SECRETS_CLI.md)
