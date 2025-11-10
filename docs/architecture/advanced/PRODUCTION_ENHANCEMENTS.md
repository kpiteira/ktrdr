# Production Enhancements - Advanced Topics

**Version**: 1.0
**Date**: 2025-11-09
**Status**: Future Work - Post Phase 5
**Priority**: Medium to High (depending on requirements)

---

## Overview

This document covers **4 advanced enhancements** for the distributed workers system. These are **deferred** from Phase 5 because:
1. They're not blocking core functionality
2. They require significant infrastructure/planning
3. They're broader platform-wide concerns (not just workers)
4. Current mitigations are acceptable for initial deployment

However, they **should be implemented** before:
- Exposing system to internet
- Handling sensitive/production data
- Scaling beyond development team
- Running in multi-tenant environments

---

## Table of Contents

1. [Security & Authentication](#1-security--authentication)
2. [Observability & Metrics](#2-observability--metrics)
3. [Performance & Load Testing](#3-performance--load-testing)
4. [Intelligent Scheduling](#4-intelligent-scheduling)

---

# 1. Security & Authentication

**Priority**: 🔴 **HIGH** (Required before production internet exposure)
**Complexity**: High
**Estimated Effort**: 2-3 weeks
**Dependencies**: Platform-wide security strategy

---

## 1.1 Design Goals

### Security Objectives

1. **Authentication**: Verify identity of all services (backend, workers, clients)
2. **Authorization**: Control what operations each identity can perform
3. **Confidentiality**: Encrypt data in transit between services
4. **Integrity**: Prevent tampering with requests/responses
5. **Non-repudiation**: Audit trail of who did what

### Threat Model

**Current Vulnerabilities**:

```
┌─────────────────────────────────────────────────────────────┐
│ Threat: Malicious Worker Registration                      │
├─────────────────────────────────────────────────────────────┤
│ Attacker deploys fake worker at 192.168.1.99:5003          │
│ Registers as legitimate worker: "backtest-worker-1"        │
│ Backend dispatches operations → attacker steals data       │
│                                                             │
│ Impact: HIGH - Data exfiltration, model theft              │
│ Likelihood: MEDIUM - Requires network access               │
│ Current Mitigation: VLAN isolation, firewall               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Threat: Direct Worker API Access                           │
├─────────────────────────────────────────────────────────────┤
│ Attacker discovers worker endpoint: 192.168.1.201:5003     │
│ Calls worker API directly: POST /backtests/start           │
│ Bypasses backend authorization, quotas, logging            │
│                                                             │
│ Impact: MEDIUM - Unauthorized resource use                 │
│ Likelihood: LOW - Requires network access                  │
│ Current Mitigation: Private subnet, firewall rules         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ Threat: Man-in-the-Middle                                  │
├─────────────────────────────────────────────────────────────┤
│ Attacker intercepts traffic between backend and worker     │
│ Steals operation data, training data, model weights        │
│ Or modifies requests/results (data poisoning)              │
│                                                             │
│ Impact: HIGH - Data breach, integrity compromise           │
│ Likelihood: LOW - Requires network access                  │
│ Current Mitigation: Trusted network (VLAN)                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 1.2 Architecture

### Option A: Shared Secret (Simple, Short-term)

**Best for**: Development, trusted internal networks
**Timeline**: 1-2 days
**Production-ready**: No (single point of failure, hard to rotate)

```
┌─────────────┐                           ┌─────────────┐
│   Backend   │                           │   Worker    │
│             │                           │             │
│ Config:     │                           │ Config:     │
│ SECRET=abc  │                           │ SECRET=abc  │
└──────┬──────┘                           └──────┬──────┘
       │                                         │
       │ POST /workers/register                  │
       │ Authorization: Bearer abc               │
       │────────────────────────────────────────>│
       │                                         │
       │ Compare: "abc" == "abc" ✓               │
       │                                         │
       │<────────────────────────────────────────│
       │ 200 OK                                  │
```

**Implementation**:

```python
# ktrdr/api/endpoints/workers.py
WORKER_AUTH_TOKEN = os.getenv("WORKER_AUTH_TOKEN")

@router.post("/workers/register")
async def register_worker(
    request: WorkerRegistrationRequest,
    authorization: str = Header(None)
):
    # Verify token
    if not WORKER_AUTH_TOKEN:
        raise HTTPException(500, "Worker authentication not configured")

    if not authorization or authorization != f"Bearer {WORKER_AUTH_TOKEN}":
        raise HTTPException(403, "Invalid worker authentication token")

    # Register worker...
```

```python
# ktrdr/workers/base.py
async def self_register(self):
    token = os.getenv("WORKER_AUTH_TOKEN")
    if not token:
        raise RuntimeError("WORKER_AUTH_TOKEN required")

    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{self.backend_url}/api/v1/workers/register",
            json=registration_data,
            headers=headers
        )
```

**Pros**: Simple, fast to implement
**Cons**: Shared secret in env vars, hard to rotate, single point of failure

---

### Option B: Mutual TLS (Production-Grade)

**Best for**: Production, compliance requirements
**Timeline**: 1-2 weeks
**Production-ready**: Yes

```
┌─────────────────────────────────────────────────────────────┐
│                   Certificate Authority (CA)                │
│                    ca.crt + ca.key                          │
└─────────────────────────┬───────────────────────────────────┘
                          │
         ┌────────────────┴────────────────┐
         ▼                                 ▼
┌─────────────────┐               ┌─────────────────┐
│    Backend      │               │     Worker      │
│  backend.crt    │◄─────TLS─────►│   worker.crt    │
│  backend.key    │   (mutual)    │   worker.key    │
└─────────────────┘               └─────────────────┘
```

**Certificate Hierarchy**:

```
CA (ca.crt)
├── backend.crt (CN=backend.ktrdr.internal)
├── worker-1.crt (CN=worker-1.ktrdr.internal)
├── worker-2.crt (CN=worker-2.ktrdr.internal)
└── worker-N.crt (CN=worker-N.ktrdr.internal)
```

**Implementation**:

```bash
# scripts/security/generate-certificates.sh

# 1. Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/CN=KTRDR Certificate Authority"

# 2. Generate backend certificate
openssl genrsa -out backend.key 2048
openssl req -new -key backend.key -out backend.csr \
  -subj "/CN=backend.ktrdr.internal"
openssl x509 -req -in backend.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out backend.crt -days 365

# 3. Generate worker certificate (repeat for each worker)
openssl genrsa -out worker-1.key 2048
openssl req -new -key worker-1.key -out worker-1.csr \
  -subj "/CN=worker-1.ktrdr.internal"
openssl x509 -req -in worker-1.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out worker-1.crt -days 365
```

```python
# ktrdr/workers/base.py
async def self_register(self):
    # Use client certificate for mTLS
    async with httpx.AsyncClient(
        cert=("/certs/worker.crt", "/certs/worker.key"),
        verify="/certs/ca.crt"
    ) as client:
        response = await client.post(
            f"{self.backend_url}/api/v1/workers/register",
            json=registration_data,
        )
```

```yaml
# docker-compose.yml
backend:
  volumes:
    - ./certs/ca.crt:/certs/ca.crt:ro
    - ./certs/backend.crt:/certs/backend.crt:ro
    - ./certs/backend.key:/certs/backend.key:ro
  environment:
    - SSL_CERT_FILE=/certs/backend.crt
    - SSL_KEY_FILE=/certs/backend.key
    - SSL_CA_FILE=/certs/ca.crt

worker:
  volumes:
    - ./certs/ca.crt:/certs/ca.crt:ro
    - ./certs/worker-1.crt:/certs/worker.crt:ro
    - ./certs/worker-1.key:/certs/worker.key:ro
```

**Pros**: Industry standard, per-worker identity, certificate rotation
**Cons**: PKI infrastructure required, certificate management overhead

---

### Option C: Service Mesh (Cloud-Native)

**Best for**: Kubernetes, microservices at scale
**Timeline**: 2-4 weeks
**Production-ready**: Yes (with operational overhead)

```
┌─────────────────────────────────────────────────────────────┐
│              Istio / Linkerd Service Mesh                   │
│                                                             │
│  ┌──────────┐  mTLS  ┌──────────┐  mTLS  ┌──────────┐     │
│  │ Backend  │◄──────►│  Envoy   │◄──────►│  Worker  │     │
│  │ (app)    │        │ (sidecar)│        │  (app)   │     │
│  └──────────┘        └──────────┘        └──────────┘     │
│                                                             │
│  Features:                                                  │
│  - Automatic mTLS                                           │
│  - Traffic management                                       │
│  - Observability (tracing, metrics)                         │
│  - Circuit breaking                                         │
└─────────────────────────────────────────────────────────────┘
```

**Pros**: Automatic mTLS, observability, traffic management
**Cons**: Kubernetes required, operational complexity, resource overhead

---

## 1.3 Recommended Approach

### Phase 6A: Shared Secret (Quick Win)
**Timeline**: 1-2 days
**Use for**: Development, internal testing

### Phase 6B: Mutual TLS (Production)
**Timeline**: 1-2 weeks
**Use for**: Production deployment, sensitive data

### Phase 6C: Service Mesh (Optional)
**Timeline**: 2-4 weeks
**Use for**: Kubernetes deployments, large-scale operations

---

## 1.4 Implementation Plan

### Task A.1: Shared Secret Authentication (2 days)

**Objective**: Add token-based authentication to worker registration

**Implementation**:
1. Add `WORKER_AUTH_TOKEN` environment variable
2. Modify worker registration endpoint to check token
3. Modify worker self-registration to send token
4. Add tests for authentication

**Quality Gate**:
```bash
# Without token
curl -X POST http://localhost:8000/api/v1/workers/register
# → 403 Forbidden

# With token
curl -X POST http://localhost:8000/api/v1/workers/register \
  -H "Authorization: Bearer secret123"
# → 200 OK
```

---

### Task A.2: Certificate Infrastructure (1 week)

**Objective**: Set up PKI for mTLS

**Implementation**:
1. Create certificate generation scripts
2. Generate CA certificate
3. Generate backend + worker certificates
4. Document certificate rotation process

---

### Task A.3: Mutual TLS Implementation (1 week)

**Objective**: Enable mTLS between backend and workers

**Implementation**:
1. Configure FastAPI for TLS
2. Update httpx clients to use client certificates
3. Add certificate validation
4. Test with Docker Compose
5. Test with Proxmox LXC

---

# 2. Observability & Metrics

**Priority**: 🟡 **MEDIUM** (Important for operations)
**Complexity**: Medium
**Estimated Effort**: 2 weeks
**Dependencies**: Monitoring infrastructure (Prometheus, Grafana)

---

## 2.1 Design Goals

### Observability Pillars

1. **Metrics**: Quantitative data (CPU, memory, operations/sec)
2. **Logs**: Structured event logs (JSON)
3. **Traces**: Distributed operation tracking (OpenTelemetry)
4. **Alerts**: Proactive issue notification

### Key Questions to Answer

**Operational Questions**:
- How many workers are running?
- What's the current capacity utilization?
- Which workers are healthy/unhealthy?
- What operations are running right now?

**Performance Questions**:
- What's the average operation duration?
- What's the throughput (ops/hour)?
- Which workers are fastest/slowest?
- Where are the bottlenecks?

**Debugging Questions**:
- Why did this operation fail?
- What was the worker doing when it died?
- How long has this worker been unavailable?
- What's the error rate over time?

---

## 2.2 Architecture

### Metrics Collection Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Grafana Dashboards                      │
│              (Visualization + Alerting)                     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ PromQL Queries
                         │
┌────────────────────────▼────────────────────────────────────┐
│                    Prometheus Server                        │
│              (Time-Series Database)                         │
│                                                             │
│  Scrapes metrics every 15s from:                            │
│  - /metrics endpoints (Prometheus format)                   │
└────────────┬───────────────────────┬────────────────────────┘
             │                       │
             │                       │
   ┌─────────▼────────┐    ┌────────▼─────────┐
   │     Backend      │    │     Worker       │
   │  GET /metrics    │    │  GET /metrics    │
   │                  │    │                  │
   │  ktrdr_ops_total │    │  worker_cpu_%    │
   │  ktrdr_ops_active│    │  worker_mem_%    │
   │  ktrdr_workers   │    │  worker_ops_done │
   └──────────────────┘    └──────────────────┘
```

---

## 2.3 Metrics Design

### Worker-Level Metrics

```python
# ktrdr/workers/metrics.py
from prometheus_client import Counter, Gauge, Histogram

# Operation counters
operations_total = Counter(
    'worker_operations_total',
    'Total operations processed',
    ['worker_id', 'operation_type', 'status']
)

# Current state gauges
current_cpu_percent = Gauge(
    'worker_cpu_percent',
    'Current CPU usage percentage',
    ['worker_id']
)

current_memory_percent = Gauge(
    'worker_memory_percent',
    'Current memory usage percentage',
    ['worker_id']
)

worker_status = Gauge(
    'worker_status',
    'Worker status (0=unavailable, 1=available, 2=busy)',
    ['worker_id']
)

# Operation duration histogram
operation_duration_seconds = Histogram(
    'worker_operation_duration_seconds',
    'Operation execution duration',
    ['worker_id', 'operation_type'],
    buckets=[1, 5, 10, 30, 60, 120, 300, 600]
)
```

### Backend-Level Metrics

```python
# ktrdr/api/metrics.py
from prometheus_client import Counter, Gauge

# Worker registry metrics
registered_workers = Gauge(
    'ktrdr_workers_registered',
    'Number of registered workers',
    ['worker_type']
)

available_workers = Gauge(
    'ktrdr_workers_available',
    'Number of available workers',
    ['worker_type']
)

# Operation metrics
operations_dispatched = Counter(
    'ktrdr_operations_dispatched_total',
    'Total operations dispatched to workers',
    ['operation_type', 'worker_type']
)

operations_completed = Counter(
    'ktrdr_operations_completed_total',
    'Total operations completed',
    ['operation_type', 'status']
)
```

---

## 2.4 Implementation Plan

### Task B.1: Prometheus Client Integration (2 days)

```python
# ktrdr/workers/base.py
from prometheus_client import make_asgi_app

class WorkerAPIBase:
    def __init__(self, ...):
        # Add Prometheus metrics endpoint
        metrics_app = make_asgi_app()
        self.app.mount("/metrics", metrics_app)
```

### Task B.2: Worker Metrics Collection (3 days)

```python
@self.app.get("/health")
async def health_check():
    # Update metrics
    current_cpu_percent.labels(worker_id=self.worker_id).set(
        psutil.cpu_percent()
    )
    current_memory_percent.labels(worker_id=self.worker_id).set(
        psutil.virtual_memory().percent
    )

    # Return health status
    return {"healthy": True, ...}
```

### Task B.3: Prometheus Server Setup (1 day)

```yaml
# docker/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['backend:8000']

  - job_name: 'workers'
    static_configs:
      - targets:
        - 'backtest-worker:5003'
        - 'training-worker:5002'
```

### Task B.4: Grafana Dashboards (3 days)

Create dashboards for:
1. **Worker Health**: CPU, memory, disk, status
2. **Operations**: Throughput, duration, success rate
3. **System Overview**: Total workers, capacity, utilization

---

# 3. Performance & Load Testing

**Priority**: 🟢 **LOW** (Nice to have)
**Complexity**: Medium
**Estimated Effort**: 2 weeks
**Dependencies**: Staging environment

---

## 3.1 Design Goals

### Test Objectives

1. **Find Breaking Points**: Maximum load before failures
2. **Measure Throughput**: Operations per hour at capacity
3. **Identify Bottlenecks**: CPU? Memory? Network? Disk?
4. **Validate Resilience**: System behavior under failures
5. **Benchmark Performance**: Baseline for future optimization

---

## 3.2 Load Test Scenarios

### Scenario 1: Baseline Throughput

**Test**: Measure max operations/hour with 10 workers

```python
@pytest.mark.load
async def test_baseline_throughput():
    """Measure baseline throughput with optimal conditions."""

    # Setup
    workers = 10
    duration_minutes = 60

    # Execute
    start_time = time.time()
    completed_ops = await submit_continuous_load(
        duration_minutes=duration_minutes,
        worker_count=workers
    )
    elapsed = time.time() - start_time

    # Measure
    ops_per_hour = (completed_ops / elapsed) * 3600

    # Assert
    assert ops_per_hour >= 100  # Baseline: 100 ops/hour
    assert ops_per_hour >= workers * 10  # Each worker: 10 ops/hour min
```

---

### Scenario 2: Cascading Failures

**Test**: Kill workers one by one under load

```python
@pytest.mark.load
async def test_cascading_worker_failures():
    """System remains operational as workers fail."""

    # Start 5 workers
    workers = await start_workers(count=5)

    # Submit continuous load (100 operations)
    load_task = asyncio.create_task(
        submit_continuous_operations(target_count=100)
    )

    # Kill workers gradually
    for i, worker in enumerate(workers):
        await asyncio.sleep(10)  # Every 10 seconds
        await kill_worker(worker)

        # Verify system still operational
        remaining = 5 - i - 1
        assert await get_available_workers() == remaining

    # All operations should complete (may take longer)
    completed = await load_task
    assert completed == 100
```

---

### Scenario 3: Network Partition

**Test**: Block network between backend and workers

```python
@pytest.mark.load
async def test_network_partition_recovery():
    """Workers recover after network partition."""

    # Start workers
    await start_workers(count=3)

    # Submit operations (some will complete)
    ops_before = await submit_operations(count=10)
    await wait_for_completions(count=5)

    # Simulate network partition
    await block_network_to_workers()

    # Workers marked unavailable after health check failures
    await asyncio.sleep(30)  # 3 failures * 10s interval
    assert await get_available_workers() == 0

    # Restore network
    await restore_network()

    # Workers recover
    await asyncio.sleep(10)  # Health checks pass
    assert await get_available_workers() == 3

    # Remaining operations complete
    await wait_for_completions(count=10)
    assert len(await get_completed_operations()) == 10
```

---

## 3.3 Performance Benchmarks

### Benchmark Suite

```python
# tests/benchmarks/test_worker_performance.py

@pytest.mark.benchmark
class TestWorkerPerformance:

    def test_operation_dispatch_latency(self, benchmark):
        """Measure latency from submit to worker start."""

        def dispatch_operation():
            # Submit operation
            start = time.perf_counter()
            operation_id = submit_backtest(...)

            # Wait for worker to start
            wait_for_worker_start(operation_id)

            return time.perf_counter() - start

        # Benchmark
        latency = benchmark(dispatch_operation)

        # Assert < 100ms dispatch latency
        assert latency < 0.1

    def test_health_check_overhead(self, benchmark):
        """Measure health check impact."""

        # Run with health checks
        with_health = benchmark(run_operations_with_health_checks, count=100)

        # Run without health checks
        without_health = run_operations_without_health_checks(count=100)

        # Overhead should be < 5%
        overhead = (with_health - without_health) / without_health
        assert overhead < 0.05
```

---

## 3.4 Implementation Plan

### Task C.1: Load Test Infrastructure (3 days)
- Set up load test environment (Docker Compose)
- Create test data generators
- Write helper functions for load submission

### Task C.2: Basic Load Tests (3 days)
- Implement Scenario 1 (baseline throughput)
- Implement Scenario 2 (cascading failures)
- Implement Scenario 3 (network partition)

### Task C.3: Performance Benchmarks (2 days)
- Set up pytest-benchmark
- Implement dispatch latency benchmark
- Implement health check overhead benchmark

### Task C.4: Stress Testing (3 days)
- 100 concurrent operations
- 1000 total operations (memory leak detection)
- Mixed operation types (backtesting + training)

---

# 4. Intelligent Scheduling

**Priority**: 🟢 **LOW** (Optimization)
**Complexity**: Low
**Estimated Effort**: 3 days
**Dependencies**: Metrics collection

---

## 4.1 Design Goals

### Scheduling Objectives

1. **Maximize Throughput**: Use powerful workers more
2. **Balance Load**: Don't overload weak workers
3. **Minimize Latency**: Dispatch to fastest available worker
4. **Fair Queuing**: Don't starve any worker

---

## 4.2 Architecture

### Capacity-Aware Scheduling Algorithm

```python
# ktrdr/api/services/worker_registry.py

def select_worker(self, worker_type: WorkerType) -> Optional[WorkerEndpoint]:
    """Select worker using capacity-aware scoring."""

    workers = self.get_available_workers(worker_type)
    if not workers:
        return None

    # Score each worker
    scored_workers = [
        (self._score_worker(w), w) for w in workers
    ]

    # Sort by score (highest first)
    scored_workers.sort(key=lambda x: x[0], reverse=True)

    # Select best worker
    score, worker = scored_workers[0]

    logger.debug(
        f"Selected worker {worker.worker_id} "
        f"(score: {score:.2f}, "
        f"cores: {worker.capabilities.get('cores', 1)}, "
        f"load: {worker.metadata.get('current_load', 0):.1f}%)"
    )

    return worker

def _score_worker(self, worker: WorkerEndpoint) -> float:
    """Score worker based on capacity and current load."""

    # Capacity score (cores * memory)
    cores = worker.capabilities.get("cores", 1)
    memory_gb = worker.capabilities.get("memory_gb", 1)
    capacity = cores * memory_gb

    # Current load (0.0 to 1.0)
    load = worker.metadata.get("current_load", 0.0)

    # Available capacity (higher is better)
    available_capacity = capacity * (1.0 - load)

    # Prefer workers with more available capacity
    return available_capacity
```

---

## 4.3 Load Tracking

### Worker Load Calculation

```python
# Worker reports current load in health endpoint
@app.get("/health")
async def health_check():
    # Calculate load based on active operations
    ops_service = get_operations_service()
    active_ops, _, _ = await ops_service.list_operations(active_only=True)

    # Simple load model: 1 operation = 100% load
    # (Workers are single-threaded, exclusive execution)
    current_load = 1.0 if active_ops else 0.0

    return {
        "healthy": True,
        "worker_status": "busy" if active_ops else "idle",
        "current_load": current_load,  # 0.0 to 1.0
        "active_operations": len(active_ops),
    }
```

### Backend Updates Worker Load

```python
# WorkerRegistry updates load from health checks
async def health_check_worker(self, worker_id: str) -> bool:
    # ... existing health check code ...

    if response.status_code == 200:
        data = response.json()

        # Update worker load
        current_load = data.get("current_load", 0.0)
        worker.metadata["current_load"] = current_load

        # Update status
        worker.status = (
            WorkerStatus.BUSY if current_load > 0.9
            else WorkerStatus.AVAILABLE
        )
```

---

## 4.4 Implementation Plan

### Task D.1: Load Tracking (1 day)

**Objective**: Workers report current load

**Implementation**:
1. Add `current_load` to health endpoint response
2. Update WorkerRegistry to store load in metadata
3. Test load values are updated correctly

---

### Task D.2: Capacity-Aware Selection (1 day)

**Objective**: Backend selects workers by capacity

**Implementation**:
1. Implement `_score_worker()` method
2. Update `select_worker()` to use scoring
3. Test workers selected by capacity

---

### Task D.3: Validation & Testing (1 day)

**Objective**: Verify scheduling improves throughput

**Test**:
```python
async def test_capacity_aware_scheduling():
    """Powerful workers get more work."""

    # Start workers with different capacities
    weak_worker = await start_worker(cores=2, memory_gb=4)
    strong_worker = await start_worker(cores=16, memory_gb=64)

    # Submit 100 operations
    await submit_operations(count=100)

    # Wait for completion
    await wait_for_all_completions()

    # Verify distribution
    weak_count = await get_worker_operation_count(weak_worker)
    strong_count = await get_worker_operation_count(strong_worker)

    # Strong worker should get more work
    ratio = strong_count / weak_count
    assert ratio > 2.0  # At least 2x more operations
```

---

## Summary

### Implementation Priorities

| Enhancement | Priority | Effort | When to Implement |
|-------------|----------|--------|-------------------|
| Security (Shared Secret) | 🔴 HIGH | 2 days | Before internet exposure |
| Security (mTLS) | 🔴 HIGH | 2 weeks | Production deployment |
| Observability | 🟡 MEDIUM | 2 weeks | After Phase 5, before scaling |
| Load Testing | 🟢 LOW | 2 weeks | Before production scaling |
| Intelligent Scheduling | 🟢 LOW | 3 days | After observability (needs metrics) |

### Recommended Timeline

**Phase 6A: Quick Wins** (1 week)
- Shared secret authentication (2 days)
- Basic Prometheus metrics (3 days)
- Intelligent scheduling (2 days)

**Phase 6B: Production Hardening** (3 weeks)
- Mutual TLS (2 weeks)
- Full observability stack (1 week)

**Phase 6C: Scaling Validation** (2 weeks)
- Load testing suite (1 week)
- Performance benchmarking (1 week)

**Total**: ~6 weeks for full production readiness

---

## Current Mitigations

While these enhancements are deferred, current mitigations are in place:

1. **Security**: VLAN isolation, firewall rules, trusted network
2. **Observability**: Health checks, basic logging, operation status API
3. **Performance**: Round-robin works acceptably for same-sized workers
4. **Load Testing**: Basic integration tests verify functionality

These mitigations are **acceptable for**:
- Internal development
- Trusted networks
- Small-scale deployments (<10 workers)
- Same-sized worker fleet

These mitigations are **NOT acceptable for**:
- Internet-facing deployments
- Multi-tenant environments
- Sensitive/production data
- Large-scale operations (>20 workers)

---

**Document Status**: Complete
**Next Steps**: Review with team, prioritize based on deployment timeline
**Owner**: TBD
**Last Updated**: 2025-11-09
