# KTRDR Deployment Guide (Docker Compose)

**Version**: 1.0
**Date**: 2025-11-10
**Audience**: Operators, DevOps, users deploying KTRDR
**Deployment Target**: Docker Compose (development and single-host deployments)

---

## Table of Contents

1. [Deployment Options](#deployment-options)
2. [Docker Compose Deployment](#docker-compose-deployment)
3. [Worker Configuration](#worker-configuration)
4. [Verifying Deployment](#verifying-deployment)
5. [Monitoring Workers](#monitoring-workers)
6. [Troubleshooting](#troubleshooting)
7. [Operations Guide](#operations-guide)

---

## Deployment Options

KTRDR supports two primary deployment models:

### Docker Compose (This Guide)

**Best For**:
- Local development
- Testing and integration
- Single-host deployments
- Multi-host Docker deployments
- Small-scale production (< 50 workers)

**Characteristics**:
- Quick setup (`docker-compose up`)
- Dynamic worker scaling
- DNS-based service discovery (single-host) or IP-based (multi-host)
- Runs on Mac, Windows, Linux
- Flexible deployment: single machine or distributed across multiple machines

**Deployment Modes**:
- **Single-Host**: All containers on one machine (simplest, for development)
- **Multi-Host**: Backend and workers on separate machines (more scalable)
- **Hybrid**: Mix of Docker and native workers (maximum flexibility)

**Limitations**:
- Docker overhead for CPU-intensive workloads
- Network configuration required for multi-host setups

**When to Use**: Development, testing, small-to-medium deployments

### Proxmox LXC (Production)

**Best For**:
- Production deployments
- Large-scale operations (> 20 workers)
- Multi-host distributed deployment
- Lower overhead for CPU-intensive workloads

**Characteristics**:
- Lower overhead than Docker (LXC containers)
- Multi-host distribution across Proxmox cluster
- Proxmox management tools (backups, snapshots)
- Full OS environment in each container

**Documentation**: See [Proxmox Deployment Guide](deployment-proxmox.md) (Phase 6, coming soon)

**When to Use**: Production environments, high-performance requirements

---

## Docker Compose Deployment

### Prerequisites

**Required Software**:
- Docker Desktop 4.x or later (Mac/Windows) or Docker Engine 20.x+ (Linux)
- Docker Compose 2.x or later (included in Docker Desktop)
- `uv` package manager (for local development)
- Git (for cloning repository)

**System Requirements**:
- **Backend**: 2 cores, 4GB RAM minimum
- **Per Worker**: 2-4 cores, 4-8GB RAM (depends on workload)
- **Total Minimum**: 8 cores, 16GB RAM for functional system (backend + 3 workers)

**Verify Prerequisites**:

```bash
# Check Docker
docker --version
# Expected: Docker version 24.0.0 or higher

# Check Docker Compose
docker-compose --version
# Expected: Docker Compose version 2.x.x or higher

# Check uv
uv --version
# Expected: uv 0.x.x or higher
```

### Starting the System

#### Option 1: Default Configuration (Quick Start)

```bash
# Clone repository
git clone https://github.com/your-org/ktrdr.git
cd ktrdr

# Start backend + default workers (1 of each type)
docker-compose -f docker/docker-compose.yml up -d

# View logs
docker-compose -f docker/docker-compose.yml logs -f

# Expected output:
# - backend_1: "✅ Backend started on port 8000"
# - backtest-worker_1: "✅ Worker registered successfully"
# - training-worker_1: "✅ Worker registered successfully"
```

**What Gets Started**:
- Backend (port 8000): Orchestration and API
- 1x Backtest Worker (port 5003): Backtesting operations
- 1x Training Worker (port 5004): Training operations (CPU fallback)

#### Option 2: Scaled Configuration (Production-Like)

```bash
# Start with multiple workers for parallel execution
docker-compose -f docker/docker-compose.yml up -d \
  --scale backtest-worker=5 \
  --scale training-worker=3

# View scaled workers
docker ps | grep worker

# Expected output:
# backtest-worker_1 ... Up
# backtest-worker_2 ... Up
# backtest-worker_3 ... Up
# backtest-worker_4 ... Up
# backtest-worker_5 ... Up
# training-worker_1 ... Up
# training-worker_2 ... Up
# training-worker_3 ... Up
```

**Capacity**:
- 5 concurrent backtesting operations
- 3 concurrent training operations (CPU)

#### Option 3: With GPU Training (Host Service)

```bash
# Start GPU training host service (outside Docker)
cd training-host-service
./start.sh

# Start Docker Compose (backend + CPU workers)
docker-compose -f docker/docker-compose.yml up -d \
  --scale backtest-worker=5 \
  --scale training-worker=2

# Verify GPU host registered
curl http://localhost:8000/api/v1/workers | \
  jq '.[] | select(.capabilities.gpu==true)'

# Expected:
# {
#   "worker_id": "training-host-1",
#   "worker_type": "training",
#   "capabilities": {"gpu": true, "gpu_type": "CUDA"},
#   "status": "AVAILABLE"
# }
```

**Capacity**:
- 1 GPU training operation (10x-100x faster)
- 2 CPU training operations (fallback)
- 5 concurrent backtesting operations

### Scaling Workers Dynamically

**Add More Workers** (without downtime):

```bash
# Scale up backtesting workers from 5 to 10
docker-compose -f docker/docker-compose.yml up -d \
  --scale backtest-worker=10

# New workers automatically register with backend
# No backend restart required
```

**Scale Down Workers**:

```bash
# Scale down from 10 to 5
docker-compose -f docker/docker-compose.yml up -d \
  --scale backtest-worker=5

# Docker stops excess workers gracefully
# Backend detects via health check failures
# Workers removed from registry after 5 minutes
```

### Stopping the System

**Graceful Shutdown**:

```bash
# Stop all containers (graceful, waits for operations to complete)
docker-compose -f docker/docker-compose.yml down

# Expected:
# - Workers finish current operations (up to 2 minutes timeout)
# - Backend waits for workers to shutdown
# - All containers stopped cleanly
```

**Force Shutdown** (not recommended):

```bash
# Force stop (kills running operations)
docker-compose -f docker/docker-compose.yml down --timeout 0
```

**Stop Individual Services**:

```bash
# Stop only training workers
docker-compose -f docker/docker-compose.yml stop training-worker

# Stop and remove
docker-compose -f docker/docker-compose.yml rm -f training-worker
```

---

## Multi-Host Docker Deployment

**When to Use Multi-Host**:
- Scale beyond single machine capacity
- Distribute workers across multiple physical machines
- Mix Docker workers on different hosts
- Hybrid deployments (Docker + native workers)

**Key Concept**: Each machine configures its own `KTRDR_API_URL` based on where the backend is located. Workers use IP addresses (not hostnames) to register themselves so the backend can reach them back.

### Architecture Overview

```
Machine A (192.168.1.100) - Backend Host
├─ Backend Container (port 8000) ← Main orchestrator
└─ Local Workers (optional) → Use http://backend:8000

Machine B (192.168.1.101) - Remote Workers
└─ Worker Containers → Use http://192.168.1.100:8000

Machine C (192.168.1.102) - More Remote Workers
└─ Worker Containers → Use http://192.168.1.100:8000
```

### Step 1: Backend Machine Configuration

**Machine A (192.168.1.100)** - Runs backend + optional local workers:

```yaml
# docker-compose.yml on Machine A
services:
  backend:
    build:
      context: ..
      dockerfile: docker/backend/Dockerfile.dev
    ports:
      - "8000:8000"  # ← CRITICAL: Expose to host network!
    environment:
      - KTRDR_API_URL=http://backend:8000  # ← DNS works within this Docker network
    networks:
      - ktrdr-network

  # OPTIONAL: Local workers on same machine
  backtest-worker:
    image: ktrdr-backend:dev
    ports:
      - "5003:5003"  # Expose for external health checks
    environment:
      - KTRDR_API_URL=http://backend:8000  # ← Same Docker network, DNS works
      - WORKER_PORT=5003
    command: ["uvicorn", "ktrdr.backtesting.backtest_worker:app", "--host", "0.0.0.0", "--port", "5003"]
    networks:
      - ktrdr-network

networks:
  ktrdr-network:
    driver: bridge
```

**Start Backend**:
```bash
# On Machine A
cd /path/to/ktrdr
docker-compose -f docker/docker-compose.yml up -d backend

# Verify backend is accessible from host network
curl http://localhost:8000/api/v1/health
curl http://192.168.1.100:8000/api/v1/health  # From another machine
```

### Step 2: Remote Worker Machine Configuration

**Machine B (192.168.1.101)** - Runs only workers:

```yaml
# docker-compose.yml on Machine B
services:
  backtest-worker-1:
    image: ktrdr-backend:dev
    ports:
      - "5003:5003"
    environment:
      - KTRDR_API_URL=http://192.168.1.100:8000  # ← Backend's IP address!
      - WORKER_PORT=5003
      - WORKER_ID=machine-b-backtest-1
    command: ["uvicorn", "ktrdr.backtesting.backtest_worker:app", "--host", "0.0.0.0", "--port", "5003"]

  backtest-worker-2:
    image: ktrdr-backend:dev
    ports:
      - "5004:5003"  # Different host port, same container port
    environment:
      - KTRDR_API_URL=http://192.168.1.100:8000  # ← Backend's IP address!
      - WORKER_PORT=5003  # Container port
      - WORKER_ID=machine-b-backtest-2
    command: ["uvicorn", "ktrdr.backtesting.backtest_worker:app", "--host", "0.0.0.0", "--port", "5003"]
```

**Start Remote Workers**:
```bash
# On Machine B
docker-compose up -d

# Verify workers can reach backend
docker exec backtest-worker-1 curl http://192.168.1.100:8000/api/v1/health
```

### Step 3: Verify Multi-Host Setup

**Check Worker Registration** (from any machine):
```bash
# Query backend for registered workers
curl http://192.168.1.100:8000/api/v1/workers | jq

# Expected output:
# {
#   "workers": [
#     {
#       "worker_id": "machine-a-backtest-1",
#       "worker_type": "backtesting",
#       "endpoint_url": "http://172.18.0.3:5003",  # Auto-detected IP
#       "status": "available"
#     },
#     {
#       "worker_id": "machine-b-backtest-1",
#       "worker_type": "backtesting",
#       "endpoint_url": "http://192.168.1.101:5003",  # Auto-detected IP
#       "status": "available"
#     }
#   ]
# }
```

### Network Requirements

**Firewall Rules** (Machine A - Backend Host):
```bash
# Allow incoming connections on port 8000 (backend API)
sudo ufw allow 8000/tcp

# Allow incoming health checks from backend to workers (if needed)
sudo ufw allow from 192.168.1.0/24 to any port 5003:5010
```

**Firewall Rules** (Machine B, C - Worker Hosts):
```bash
# Allow incoming connections on worker ports
sudo ufw allow 5003:5010/tcp  # Worker port range

# Allow outgoing to backend
# (Usually allowed by default)
```

**Network Connectivity Test**:
```bash
# From worker machine, test backend reachability
curl http://192.168.1.100:8000/api/v1/health

# From backend machine, test worker reachability (after registration)
curl http://192.168.1.101:5003/health
```

### Hybrid Deployment (Docker + Native)

You can mix Docker workers with native workers (LXC, bare metal):

**Machine C (192.168.1.102)** - Native Worker (LXC/Bare Metal):
```bash
# /opt/ktrdr/.env
KTRDR_API_URL=http://192.168.1.100:8000  # Backend IP
WORKER_ENDPOINT_URL=http://192.168.1.102:5003  # Explicit worker IP
WORKER_PORT=5003
WORKER_ID=machine-c-native-1

# Start worker
cd /opt/ktrdr
uv run uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003
```

**Result**: Backend orchestrates operations across:
- Local Docker workers (Machine A)
- Remote Docker workers (Machine B)
- Native workers (Machine C)

All workers register automatically and appear in the WorkerRegistry!

### Troubleshooting Multi-Host

**Problem**: Workers not registering with backend

```bash
# Check worker logs
docker logs backtest-worker-1

# Look for:
# - "RuntimeError: KTRDR_API_URL environment variable is required"
#   → Fix: Set KTRDR_API_URL in docker-compose.yml
#
# - "Connection refused" to backend
#   → Fix: Check firewall, verify backend port 8000 is exposed and accessible
#
# - "Failed to register worker... after 5 attempts"
#   → Fix: Check network connectivity, DNS resolution
```

**Problem**: Backend can't reach workers for health checks

```bash
# From backend machine, test worker endpoint
curl http://192.168.1.101:5003/health

# If fails:
# - Check worker port is exposed (5003:5003 in docker-compose.yml)
# - Check firewall allows incoming on port 5003
# - Check worker is actually running: docker ps
```

**Problem**: Worker registering with wrong IP address

Workers auto-detect their IP by connecting to the backend. If the wrong IP is detected:

```bash
# Force explicit worker endpoint URL
# In docker-compose.yml:
environment:
  - KTRDR_API_URL=http://192.168.1.100:8000
  - WORKER_ENDPOINT_URL=http://192.168.1.101:5003  # ← Explicit IP
  - WORKER_PORT=5003
```

### Performance Considerations

**Network Latency**:
- Local workers (same machine): ~1ms latency
- Remote workers (same LAN): ~1-5ms latency
- Remote workers (WAN/cloud): 20-100ms+ latency

**Recommendation**: Keep backend and workers on same LAN for production deployments.

**Bandwidth**: Minimal - worker registration and health checks are lightweight (<1KB/s per worker).

---

## Worker Configuration

### Environment Variables

Workers are configured via environment variables in `docker-compose.yml`:

```yaml
services:
  backtest-worker:
    environment:
      # REQUIRED: Backend URL for registration
      - KTRDR_API_URL=http://backend:8000

      # OPTIONAL: Worker identification
      - WORKER_ID=${HOSTNAME}  # Defaults to container hostname

      # OPTIONAL: Worker port (default per worker type)
      - WORKER_PORT=5003  # Backtest: 5003, Training: 5004

      # OPTIONAL: Log level
      - LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

**KTRDR_API_URL** (required):
- URL where backend is reachable
- Docker Compose: `http://backend:8000` (DNS-based)
- External backend: `http://192.168.1.100:8000` (IP-based)

**WORKER_ID** (optional):
- Unique identifier for this worker
- Defaults to container hostname (Docker generates unique names)
- Custom example: `WORKER_ID=backtest-worker-prod-1`

**WORKER_PORT** (optional):
- Port worker listens on inside container
- Defaults: Backtest=5003, Training=5004
- Only change if port conflicts occur

### Worker Capabilities

Workers report capabilities during registration. Capabilities determine which operations can be dispatched to which workers.

**Backtest Worker Capabilities** (default):

```json
{
    "worker_type": "backtesting",
    "cores": 4,  // Auto-detected or from WORKER_CORES env var
    "memory_gb": 8,  // Auto-detected
    "gpu": false
}
```

**Training Worker Capabilities** (CPU):

```json
{
    "worker_type": "training",
    "cores": 8,
    "memory_gb": 16,
    "gpu": false
}
```

**Training Host Service Capabilities** (GPU):

```json
{
    "worker_type": "training",
    "cores": 16,
    "memory_gb": 64,
    "gpu": true,
    "gpu_type": "CUDA",  // or "MPS" for Mac
    "gpu_count": 2,
    "gpu_memory_gb": 24
}
```

**Override Capabilities**:

```yaml
# docker-compose.yml
backtest-worker:
  environment:
    - WORKER_CORES=8  # Override auto-detection
    - WORKER_MEMORY_GB=16
```

### Docker Compose Service Definitions

**Complete Example** (`docker/docker-compose.yml`):

```yaml
version: '3.8'

services:
  # Backend (orchestrator)
  backend:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - KTRDR_API_URL=http://backend:8000
      - USE_IB_HOST_SERVICE=true
      - IB_HOST_SERVICE_URL=http://host.docker.internal:5001
    networks:
      - ktrdr-network
    volumes:
      - ../data:/app/data
      - ../models:/app/models
    command: ["uv", "run", "python", "scripts/run_api_server.py"]

  # Backtest workers (scalable)
  backtest-worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker
    environment:
      - KTRDR_API_URL=http://backend:8000
      - WORKER_PORT=5003
      - WORKER_TYPE=backtesting
      - LOG_LEVEL=INFO
    networks:
      - ktrdr-network
    volumes:
      - ../data:/app/data:ro  # Read-only access to data
      - ../models:/app/models:ro
    command: [
      "uv", "run", "python", "-m",
      "ktrdr.backtesting.backtest_worker"
    ]
    # Scale: docker-compose up -d --scale backtest-worker=5

  # Training workers (scalable, CPU fallback)
  training-worker:
    build:
      context: ..
      dockerfile: docker/Dockerfile.worker
    environment:
      - KTRDR_API_URL=http://backend:8000
      - WORKER_PORT=5004
      - WORKER_TYPE=training
      - LOG_LEVEL=INFO
    networks:
      - ktrdr-network
    volumes:
      - ../data:/app/data:ro
      - ../models:/app/models  # Read-write for saving trained models
    command: [
      "uv", "run", "python", "-m",
      "ktrdr.training.training_worker"
    ]
    # Scale: docker-compose up -d --scale training-worker=3

networks:
  ktrdr-network:
    driver: bridge
```

**Worker Dockerfile** (`docker/Dockerfile.worker`):

```dockerfile
FROM python:3.11-slim

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.cargo/bin:$PATH"

# Set working directory
WORKDIR /app

# Copy project files
COPY . /app/

# Install dependencies
RUN uv sync

# Default command (overridden in docker-compose.yml)
CMD ["uv", "run", "python", "-m", "ktrdr.backtesting.backtest_worker"]
```

---

## Verifying Deployment

### 1. Check Worker Registration

**View All Workers**:

```bash
curl http://localhost:8000/api/v1/workers | jq

# Expected output:
# [
#   {
#     "worker_id": "backtest-worker_1",
#     "worker_type": "backtesting",
#     "endpoint_url": "http://backtest-worker_1:5003",
#     "status": "AVAILABLE",
#     "capabilities": {"cores": 4, "memory_gb": 8, "gpu": false},
#     "last_health_check": "2025-11-10T10:30:00Z",
#     "health_check_failures": 0
#   },
#   ...
# ]
```

**Verify Expected Count**:

```bash
# Count workers by type
curl http://localhost:8000/api/v1/workers | \
  jq 'group_by(.worker_type) | map({type: .[0].worker_type, count: length})'

# Expected (for --scale backtest-worker=5 training-worker=3):
# [
#   {"type": "backtesting", "count": 5},
#   {"type": "training", "count": 3}
# ]
```

### 2. Check Worker Health

**Backend Health Aggregation**:

```bash
curl http://localhost:8000/api/v1/workers/health | jq

# Expected:
# {
#   "total_workers": 8,
#   "available": 8,
#   "busy": 0,
#   "temporarily_unavailable": 0,
#   "by_type": {
#     "backtesting": {"available": 5, "busy": 0},
#     "training": {"available": 3, "busy": 0}
#   }
# }
```

**Individual Worker Health**:

```bash
# Get worker endpoint from registry
WORKER_URL=$(curl -s http://localhost:8000/api/v1/workers | \
  jq -r '.[0].endpoint_url')

# Query worker health directly
curl "http://${WORKER_URL}/health" | jq

# Expected:
# {
#   "healthy": true,
#   "service": "backtest-worker",
#   "timestamp": "2025-11-10T10:30:00Z",
#   "status": "operational",
#   "worker_status": "idle",
#   "current_operation": null
# }
```

### 3. Test Backtest Execution

**Start Test Backtest**:

```bash
# Start backtest via CLI
docker exec ktrdr-backend uv run ktrdr backtests start \
  --model neuro_mean_reversion/1d_v21 \
  --symbol EURUSD \
  --timeframe 1d \
  --start-date 2024-01-01 \
  --end-date 2024-12-31

# Or via API
OPERATION_ID=$(curl -X POST http://localhost:8000/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/app/models/neuro_mean_reversion/1d_v21",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }' | jq -r '.operation_id')

echo "Operation ID: $OPERATION_ID"
```

**Monitor Progress**:

```bash
# Poll operation status
watch -n 1 "curl -s http://localhost:8000/api/v1/operations/$OPERATION_ID | jq '.progress'"

# Expected progression:
# {"percentage": 0, "current_step": "Initializing..."}
# {"percentage": 25, "current_step": "Processing bar 250/1000"}
# {"percentage": 50, "current_step": "Processing bar 500/1000"}
# {"percentage": 100, "current_step": "Completed"}
```

**Verify Completion**:

```bash
# Check final status
curl http://localhost:8000/api/v1/operations/$OPERATION_ID | jq

# Expected:
# {
#   "operation_id": "...",
#   "status": "completed",
#   "progress": {"percentage": 100},
#   "result": {
#     "total_trades": 42,
#     "profit_factor": 1.85,
#     "sharpe_ratio": 2.1
#   }
# }
```

### 4. Test Training Execution

**Start CPU Training** (automatically uses CPU workers if no GPU):

```bash
docker exec ktrdr-backend uv run ktrdr models train \
  --strategy neuro_mean_reversion \
  --symbol EURUSD \
  --timeframe 1d

# Backend automatically selects:
# 1. GPU worker if available (10x-100x faster)
# 2. CPU worker if GPU busy/unavailable (always works)
```

**Verify Worker Selection**:

```bash
# Check which worker was selected
curl http://localhost:8000/api/v1/operations | \
  jq '.operations[0] | {operation_id, worker_id}'

# Expected:
# {
#   "operation_id": "op_training_...",
#   "worker_id": "training-worker_1"  // CPU worker
# }
```

---

## Monitoring Workers

### 1. Worker Status Endpoints

**Real-Time Worker Status**:

```bash
# Get all workers with status
curl http://localhost:8000/api/v1/workers | jq '.[] | {
  worker_id,
  worker_type,
  status,
  worker_status: (.metadata.worker_status // "unknown"),
  current_operation: (.metadata.current_operation // null)
}'

# Example output:
# {
#   "worker_id": "backtest-worker_1",
#   "worker_type": "backtesting",
#   "status": "AVAILABLE",
#   "worker_status": "idle",
#   "current_operation": null
# }
# {
#   "worker_id": "backtest-worker_2",
#   "worker_type": "backtesting",
#   "status": "AVAILABLE",
#   "worker_status": "busy",
#   "current_operation": "op_backtest_20251110_103000_abc123"
# }
```

### 2. Operation Progress Tracking

**List Active Operations**:

```bash
# Get all running operations
curl "http://localhost:8000/api/v1/operations?status=running" | jq

# Group by worker
curl "http://localhost:8000/api/v1/operations?status=running" | \
  jq 'group_by(.worker_id) | map({worker: .[0].worker_id, operations: map(.operation_id)})'
```

**Track Operation Across Workers**:

```bash
# Get operation with worker details
OPERATION_ID="op_backtest_..."

curl "http://localhost:8000/api/v1/operations/$OPERATION_ID" | \
  jq '{
    operation_id,
    status,
    progress: .progress.percentage,
    worker_id,
    started_at: .created_at
  }'
```

### 3. Health Check Monitoring

**Monitor Health Check Status**:

```bash
# Watch health check failures
watch -n 5 'curl -s http://localhost:8000/api/v1/workers | \
  jq ".[] | select(.health_check_failures > 0) | {
    worker_id,
    status,
    failures: .health_check_failures,
    last_check: .last_health_check
  }"'

# Healthy workers show no output
# Unhealthy workers appear with failure count
```

**Health Check Logs** (Backend):

```bash
# View backend health check logs
docker logs ktrdr-backend 2>&1 | grep -i "health check"

# Expected output:
# [INFO] Health check passed: backtest-worker_1
# [INFO] Health check passed: training-worker_1
# [WARNING] Health check failed: backtest-worker_3 (1/3 failures)
# [ERROR] Worker marked unavailable: backtest-worker_3 (3/3 failures)
```

### 4. Dead Worker Detection and Removal

**Detection Timeline**:

```
T+0s:  Worker healthy, responding to health checks
T+10s: Health check #1 fails (worker crashed/network issue)
       → Worker remains AVAILABLE (grace period)
T+20s: Health check #2 fails
       → Worker remains AVAILABLE (grace period)
T+30s: Health check #3 fails
       → Worker marked TEMPORARILY_UNAVAILABLE
       → Excluded from new operations
T+5m:  Cleanup task runs
       → Worker removed from registry entirely
```

**Monitor Dead Worker Removal**:

```bash
# Check for temporarily unavailable workers
curl http://localhost:8000/api/v1/workers | \
  jq '.[] | select(.status=="TEMPORARILY_UNAVAILABLE") | {
    worker_id,
    status,
    unavailable_duration: (.metadata.unavailable_since // "unknown"),
    will_be_removed_at: "5 minutes from unavailable_since"
  }'
```

---

## Troubleshooting

### Issue 1: Workers Not Registering

**Symptoms**:
- Workers start successfully
- Workers don't appear in `GET /api/v1/workers`
- No errors in worker logs

**Diagnosis**:

```bash
# Step 1: Check worker logs
docker logs backtest-worker_1

# Look for:
# "✅ Worker registered successfully" → Registration worked
# "❌ Failed to register with backend" → Registration failed

# Step 2: Check backend logs
docker logs ktrdr-backend | grep -i register

# Look for:
# "Worker registered: backtest-worker_1" → Backend received registration
```

**Common Causes & Solutions**:

**Cause 1: Wrong KTRDR_API_URL**

```bash
# Check worker environment
docker exec backtest-worker_1 env | grep KTRDR_API_URL

# Should be: KTRDR_API_URL=http://backend:8000 (Docker Compose)

# Fix: Update docker-compose.yml
# backtest-worker:
#   environment:
#     - KTRDR_API_URL=http://backend:8000  # ← Correct for Docker Compose
```

**Cause 2: Network connectivity**

```bash
# Test from worker to backend
docker exec backtest-worker_1 curl -I http://backend:8000/health

# Expected: HTTP/1.1 200 OK

# If fails: Check Docker network
docker network inspect ktrdr-network

# Verify backend and workers are on same network
```

**Cause 3: Backend not ready**

```bash
# Check backend status
curl http://localhost:8000/health

# Should return: {"healthy": true}

# If backend not ready, wait and retry
# Workers retry registration automatically every 30 seconds
```

### Issue 2: Workers Showing as Dead (TEMPORARILY_UNAVAILABLE)

**Symptoms**:
- Worker appears in registry
- Status: TEMPORARILY_UNAVAILABLE
- Worker seems to be running

**Diagnosis**:

```bash
# Check worker health endpoint directly
WORKER_ID="backtest-worker_1"
WORKER_URL=$(curl -s http://localhost:8000/api/v1/workers | \
  jq -r ".[] | select(.worker_id==\"$WORKER_ID\") | .endpoint_url")

curl "$WORKER_URL/health"

# Expected: {"healthy": true, "worker_status": "idle"}

# If fails: Worker crashed or health endpoint broken
```

**Common Causes & Solutions**:

**Cause 1: Worker overloaded**

```bash
# Check worker resource usage
docker stats backtest-worker_1 --no-stream

# If CPU > 90% or Memory near limit:
# → Worker too busy to respond to health checks within 5-second timeout

# Solution: Scale up (add more workers)
docker-compose up -d --scale backtest-worker=10
```

**Cause 2: Worker crashed but container still running**

```bash
# Check worker process
docker exec backtest-worker_1 ps aux | grep python

# If no Python process: Worker crashed

# Check logs for crash reason
docker logs backtest-worker_1 --tail 100

# Solution: Restart worker
docker-compose restart backtest-worker_1
```

**Cause 3: Network partition**

```bash
# Test connectivity from backend to worker
docker exec ktrdr-backend curl -I "$WORKER_URL/health"

# If fails: Network issue

# Solution: Restart both containers
docker-compose restart backend backtest-worker
```

### Issue 3: Operations Failing to Dispatch

**Symptoms**:
- Backend returns "No workers available"
- Workers shown as AVAILABLE in registry
- Health checks passing

**Diagnosis**:

```bash
# Step 1: Verify workers exist for operation type
curl http://localhost:8000/api/v1/workers | \
  jq '.[] | select(.worker_type=="backtesting")'

# Should return at least one worker

# Step 2: Check worker status
curl http://localhost:8000/api/v1/workers | \
  jq '.[] | select(.worker_type=="backtesting") | {worker_id, status}'

# Status should be "AVAILABLE" (not "BUSY" or "TEMPORARILY_UNAVAILABLE")
```

**Common Causes & Solutions**:

**Cause 1: All workers busy**

```bash
# Check how many workers are busy
curl http://localhost:8000/api/v1/workers | \
  jq '[.[] | select(.worker_type=="backtesting")] |
      map({worker_id, status, current_operation: .metadata.current_operation}) |
      group_by(.status) |
      map({status: .[0].status, count: length})'

# If all BUSY: Need more workers

# Solution: Scale up
docker-compose up -d --scale backtest-worker=10
```

**Cause 2: Worker type mismatch**

```bash
# Check exact worker_type
curl http://localhost:8000/api/v1/workers | jq '.[].worker_type' | sort -u

# Expected: "backtesting", "training"

# If wrong (e.g., "backtest" instead of "backtesting"):
# → Worker registered with wrong type

# Solution: Fix worker_type in worker code or environment variable
```

### Issue 4: Connection Errors

**Symptoms**:
- Backend can't reach workers
- Operations fail with connection errors
- Health checks timing out

**Diagnosis**:

```bash
# Test connectivity
docker exec ktrdr-backend curl -v http://backtest-worker_1:5003/health

# Look for:
# "Could not resolve host" → DNS issue
# "Connection refused" → Worker not listening
# "Connection timed out" → Network issue
```

**Common Causes & Solutions**:

**Cause 1: DNS resolution failure**

```bash
# Check Docker DNS
docker exec ktrdr-backend nslookup backtest-worker_1

# Should resolve to container IP

# If fails: Docker network issue

# Solution: Recreate network
docker-compose down
docker-compose up -d
```

**Cause 2: Worker port not listening**

```bash
# Check worker port
docker exec backtest-worker_1 netstat -tlnp | grep 5003

# Should show: 0.0.0.0:5003 ... LISTEN

# If not listening: Worker failed to start

# Solution: Check worker logs and fix startup issue
docker logs backtest-worker_1
```

---

## Operations Guide

### Starting/Stopping Workers Without Affecting Backend

**Stop Workers Only**:

```bash
# Stop all workers (backend keeps running)
docker-compose stop backtest-worker training-worker

# Backend continues running
# New operations will fail with "No workers available"
```

**Start Workers Only**:

```bash
# Start workers (backend already running)
docker-compose start backtest-worker training-worker

# Workers re-register automatically
# Operations can now be dispatched
```

### Adding Workers Dynamically

**Scenario**: System is running, need more capacity

```bash
# Current state: 5 backtest workers
# Add 5 more (total 10)

docker-compose up -d --scale backtest-worker=10

# New workers:
# 1. Start immediately
# 2. Register with backend automatically
# 3. Begin accepting operations
# No backend restart required
```

**Verify New Workers**:

```bash
# Should show 10 workers
curl http://localhost:8000/api/v1/workers | \
  jq '[.[] | select(.worker_type=="backtesting")] | length'

# Expected: 10
```

### Removing Workers Gracefully

**Scenario**: Reducing capacity, want to drain workers first

**Step 1: Identify workers to remove**:

```bash
# List workers with current operations
curl http://localhost:8000/api/v1/workers | \
  jq '.[] | select(.worker_type=="backtesting") | {
    worker_id,
    status,
    current_operation: .metadata.current_operation
  }'

# Remove idle workers (current_operation == null)
```

**Step 2: Scale down**:

```bash
# Scale from 10 to 5
docker-compose up -d --scale backtest-worker=5

# Docker stops workers gracefully:
# 1. Sends SIGTERM to container
# 2. Waits for current operation to complete (up to 2 min timeout)
# 3. Stops container
# 4. Backend detects via health check failure
# 5. Backend removes worker from registry (after 5 min)
```

**Step 3: Verify**:

```bash
# Should show 5 workers
curl http://localhost:8000/api/v1/workers | \
  jq '[.[] | select(.worker_type=="backtesting")] | length'

# Expected: 5
```

### Viewing Worker Logs

**Real-Time Logs** (single worker):

```bash
# Follow logs for specific worker
docker logs -f backtest-worker_1

# Look for:
# "Starting operation: op_backtest_..." → Operation started
# "Progress: 45.5% ..." → Operation progress
# "Operation completed: op_backtest_..." → Operation finished
```

**Real-Time Logs** (all workers of a type):

```bash
# Follow logs for all backtest workers
docker-compose logs -f backtest-worker

# Shows interleaved logs from all backtest workers
```

**Historical Logs**:

```bash
# Last 100 lines
docker logs backtest-worker_1 --tail 100

# Since timestamp
docker logs backtest-worker_1 --since 2025-11-10T10:00:00

# Between timestamps
docker logs backtest-worker_1 \
  --since 2025-11-10T10:00:00 \
  --until 2025-11-10T11:00:00
```

**Search Logs**:

```bash
# Find operations
docker logs backtest-worker_1 2>&1 | grep "op_backtest_"

# Find errors
docker logs backtest-worker_1 2>&1 | grep -i error

# Find specific operation
OPERATION_ID="op_backtest_20251110_103000_abc123"
docker logs backtest-worker_1 2>&1 | grep "$OPERATION_ID"
```

### Graceful System Shutdown

**Scenario**: Need to shut down entire system without losing work

**Step 1: Stop accepting new operations**:

```bash
# Option A: Stop backend (existing operations continue on workers)
docker-compose stop backend

# Option B: Mark backend as "draining" (if implemented)
# curl -X POST http://localhost:8000/api/v1/admin/drain
```

**Step 2: Wait for operations to complete**:

```bash
# Monitor active operations
watch -n 5 'curl -s http://localhost:8000/api/v1/operations?status=running | jq ".operations | length"'

# Wait for: 0 active operations
```

**Step 3: Shutdown**:

```bash
# Graceful shutdown (waits up to 2 minutes per container)
docker-compose down

# Force shutdown (after manual verification)
docker-compose down --timeout 0
```

---

## Summary

This deployment guide covered:

1. **Deployment Options**: Docker Compose (dev/testing) vs Proxmox LXC (production)
2. **Docker Compose Deployment**: Prerequisites, starting system, scaling workers, stopping
3. **Worker Configuration**: Environment variables, capabilities, Docker Compose service definitions
4. **Verifying Deployment**: Worker registration, health checks, testing backtests/training
5. **Monitoring Workers**: Status endpoints, progress tracking, health monitoring, dead worker detection
6. **Troubleshooting**: Common issues (registration failures, dead workers, dispatch failures, connection errors)
7. **Operations Guide**: Starting/stopping workers, dynamic scaling, viewing logs, graceful shutdown

**Key Takeaways**:

- Docker Compose provides quick setup for development and single-host deployments
- Workers self-register automatically (no manual configuration)
- Dynamic scaling: `docker-compose up -d --scale backtest-worker=10`
- Backend never executes operations (pure orchestrator)
- Health monitoring detects and removes dead workers automatically (5-minute threshold)

**Next Steps**:
- **For Architecture**: See [Architecture Overview](../architecture-overviews/distributed-workers.md)
- **For Development**: See [Developer Guide](../developer/distributed-workers-guide.md)
- **For Production**: Proxmox LXC deployment guide (Phase 6, coming soon)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-10
