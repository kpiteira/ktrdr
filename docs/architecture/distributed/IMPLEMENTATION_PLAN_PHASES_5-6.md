# Distributed Training & Backtesting Implementation Plan - Phases 5-6

**Version**: 2.2 - Production Deployment (Reorganized)
**Status**: 🚧 **READY** - Tasks in implementation order
**Date**: 2025-11-09
**Phases Covered**: 5-6 (Pure Distributed + Production Deployment)

---

## 📋 Plan Navigation

- **Previous**: [Phases 1-4](IMPLEMENTATION_PLAN_PHASES_1-4.md) - COMPLETED ✅
- **This Document**: Phases 5-6 (Phase 5 ready to start)
- **Future Work**: [Production Enhancements](../advanced/PRODUCTION_ENHANCEMENTS.md) - Security, observability, load testing

---

## Phase 5: Remove Local Execution Mode (Pure Distributed Architecture)

**Goal**: Eliminate local/remote duality - all operations execute on workers or host services

**Why This Phase**: Clean up architecture, enforce distributed-only execution model

**End State**:

- No `USE_REMOTE_*_SERVICE` flags - always distributed
- Backend is orchestrator only, never executes operations
- BacktestingService always uses WorkerRegistry (no fallback)
- TrainingService always uses workers or host service (no local execution)
- Simplified codebase with single execution path
- **TESTABLE**: All operations require workers, fail gracefully if none available

**Architectural Benefit**: Cleaner separation of concerns - backend orchestrates, workers execute

**Implementation Approach**:
1. **Tasks 5.1-5.5**: Docker-only distributed mode (works on single host) - **DO THESE FIRST**
2. **Task 5.6**: Multi-host networking fixes (OPTIONAL - only for Proxmox/K8s/cloud)

**Phase 5 Timeline**:
- Tasks 5.1-5.5 (Docker-only): ~8 hours
- Task 5.6 (Multi-host - OPTIONAL): ~6 hours
- **Total**: 8 hours (Docker) or 14 hours (Docker + Multi-host)

**Important**: Start with Tasks 5.1-5.5. Only do Task 5.6 if deploying to Proxmox/K8s/cloud.

---

## Tasks 5.1-5.5: Docker-Only Distributed Mode

Complete these tasks to get distributed mode working in Docker Compose (single host).

✅ **Works for**: Development, testing, single-host Docker deployments
❌ **Not sufficient for**: Proxmox LXC, Kubernetes, multi-host cloud deployments (see Task 5.6)

---

### Task 5.1: Remove Local Backtesting Execution

**Objective**: BacktestingService requires WorkerRegistry, removes local execution code path

**TDD Approach**:

1. Update existing tests to expect errors when no workers available
2. Remove tests for local execution mode
3. Verify all tests pass with distributed-only mode

**Implementation**:

1. Modify `ktrdr/backtesting/backtesting_service.py`:

   ```python
   def __init__(self, worker_registry: WorkerRegistry):  # No Optional - required!
       """Initialize backtesting service (distributed-only mode)."""
       super().__init__()
       self.operations_service = get_operations_service()
       self.worker_registry = worker_registry  # Required, not optional
       self._operation_workers: dict[str, str] = {}

       logger.info("Backtesting service initialized (distributed mode)")

   # Remove _use_remote flag
   # Remove _should_use_remote_service() method
   # Remove _run_local_backtest() method
   # Rename _run_remote_backtest() → run_backtest_on_worker()
   ```

2. Update `ktrdr/api/endpoints/backtesting.py`:

   ```python
   async def get_backtesting_service() -> BacktestingService:
       global _backtesting_service
       if _backtesting_service is None:
           worker_registry = get_worker_registry()  # Always required
           _backtesting_service = BacktestingService(worker_registry=worker_registry)
       return _backtesting_service
   ```

3. Remove environment variable handling:
   - Delete `USE_REMOTE_BACKTEST_SERVICE` checks
   - Delete `REMOTE_BACKTEST_SERVICE_URL` (use WorkerRegistry instead)

**Quality Gate**:

```bash
make test-unit
make quality

# Manual test - should fail gracefully with no workers
docker-compose -f docker/docker-compose.dev.yml up -d backend
# (no workers started)
# Try to start backtest -> Should get clear error: "No workers available"
```

**Commit**: `refactor(backtesting): remove local execution mode, require distributed workers`

**Estimated Time**: 2 hours

---

### Task 5.2: Remove Local Training Execution

**Objective**: TrainingService requires WorkerRegistry, implements GPU-first CPU-fallback selection, removes local execution

**TDD Approach**:

1. Update tests for distributed-only mode with GPU-first CPU-fallback logic
2. Verify worker selection priority: GPU → CPU → Error
3. Remove tests for local execution mode

**Implementation**:

1. Modify `ktrdr/api/services/training_service.py`:

   ```python
   def __init__(self, worker_registry: WorkerRegistry):  # Required, not Optional!
       """Initialize training service (distributed-only mode)."""
       super().__init__()
       self.worker_registry = worker_registry  # Required
       self._operation_workers: dict[str, str] = {}

       logger.info("Training service initialized (distributed mode: GPU-first, CPU-fallback)")

   def _select_training_worker(self, context: dict) -> Optional[WorkerEndpoint]:
       """
       Select training worker with GPU-first, CPU-fallback strategy.

       Priority:
       1. Try GPU workers first (10x-100x faster)
       2. Fallback to CPU workers if no GPU available
       3. Raise error if no workers available
       """
       # Try GPU workers first
       gpu_workers = self.worker_registry.get_available_workers(
           worker_type=WorkerType.TRAINING,
           capabilities={"gpu": True}
       )

       if gpu_workers:
           logger.info("Selected GPU worker for training (10x-100x faster)")
           return gpu_workers[0]

       # Fallback to CPU workers
       cpu_workers = self.worker_registry.get_available_workers(
           worker_type=WorkerType.TRAINING,
           capabilities={"gpu": False}
       )

       if cpu_workers:
           logger.info("Selected CPU worker for training (GPU unavailable)")
           return cpu_workers[0]

       # No workers available
       raise RuntimeError(
           "No training workers available. Start GPU or CPU training workers."
       )

   # Remove _initialize_adapter() - no adapter pattern anymore
   # Remove local execution code
   # Remove USE_TRAINING_HOST_SERVICE environment variable handling
   # Always use WorkerRegistry with GPU-first, CPU-fallback selection
   ```

2. Update `ktrdr/api/endpoints/training.py`:

   ```python
   async def get_training_service() -> TrainingService:
       global _training_service
       if _training_service is None:
           worker_registry = get_worker_registry()  # Always required
           _training_service = TrainingService(worker_registry=worker_registry)
       return _training_service
   ```

3. Remove environment variable handling:
   - Delete `USE_TRAINING_HOST_SERVICE` checks
   - Delete `TRAINING_HOST_SERVICE_URL` usage
   - Workers register themselves with capabilities (gpu: true/false)

**Quality Gate**:

```bash
make test-unit
make quality

# Manual test - should fail gracefully with no workers
docker-compose -f docker/docker-compose.dev.yml up -d backend
# (no workers started)
# Try to start training -> Should get clear error: "No training workers available"
```

**Commit**: `refactor(training): remove local execution, implement GPU-first CPU-fallback worker selection`

**Estimated Time**: 3 hours

---

### Task 5.3: Clean Up Environment Variables

**Objective**: Remove all local/remote toggle environment variables (pure distributed architecture)

**Implementation**:

1. Delete from `docker-compose.yml` and codebase:
   - `USE_REMOTE_BACKTEST_SERVICE` (always use WorkerRegistry now)
   - `REMOTE_BACKTEST_SERVICE_URL` (use WorkerRegistry)
   - `USE_TRAINING_HOST_SERVICE` (always use WorkerRegistry with GPU-first logic)
   - `TRAINING_HOST_SERVICE_URL` (workers register themselves)

2. Keep only IB-specific variables (IB Gateway requires host service):
   - `USE_IB_HOST_SERVICE` (IB Gateway access requires host service)
   - `IB_HOST_SERVICE_URL`

3. Update `.env.example` with new structure:

   ```bash
   # Pure Distributed Architecture
   # Backend always uses WorkerRegistry for backtesting and training (no local execution)
   # Workers register themselves on startup (push-based registration)

   # IB Data Access (requires ib-host-service for IB Gateway TCP connection)
   USE_IB_HOST_SERVICE=true
   IB_HOST_SERVICE_URL=http://host.docker.internal:5001

   # Worker Configuration (workers register themselves)
   # No backend environment variables needed - workers discover backend via service discovery
   ```

4. Update documentation:
   - Remove references to USE_TRAINING_HOST_SERVICE
   - Document worker registration pattern
   - Explain GPU-first CPU-fallback automatic selection

**Quality Gate**:

```bash
# Verify clean startup
docker-compose up -d
docker-compose logs | grep -i "error\|warning"
# Should be no errors about missing env vars

# Verify workers can register
curl -X POST http://localhost:8000/api/v1/workers/register \
  -H "Content-Type: application/json" \
  -d '{"worker_id":"test","worker_type":"TRAINING","capabilities":{"gpu":true}}'
```

**Commit**: `refactor(config): clean up environment variables for distributed-only mode`

**Estimated Time**: 1 hour

---

### Task 5.4: Update Documentation

**Objective**: Update docs to reflect distributed-only architecture

**Implementation**:

1. Update `CLAUDE.md`:
   - Remove references to local execution mode
   - Update architecture diagrams
   - Document worker requirement

2. Update `README.md`:
   - Add "Starting Workers" section
   - Update docker-compose instructions

3. Update API docs:
   - `/docs` endpoint should mention worker requirement
   - Error responses should be documented

**Quality Gate**:

```bash
# Manual review - docs are accurate and complete
```

**Commit**: `docs(distributed): update documentation for distributed-only architecture`

**Estimated Time**: 1.5 hours

---

### Task 5.5: Integration Test - Pure Distributed Mode

**Objective**: End-to-end test verifying distributed-only operation

**TDD Approach**:

1. Create `tests/e2e/test_distributed_only.py`
2. Test scenarios:
   - Backtest with workers → succeeds
   - Backtest without workers → fails with clear error
   - Training with GPU host → succeeds
   - Training with CPU workers → succeeds
   - Training without either → fails with clear error

**Implementation**:

```python
@pytest.mark.e2e
async def test_backtest_requires_workers():
    """Backtest fails gracefully when no workers available."""
    # Start backend only (no workers)
    # Try to start backtest
    # Expect: RuntimeError("No workers available")

@pytest.mark.e2e
async def test_backtest_with_workers():
    """Backtest succeeds with workers available."""
    # Start backend + workers
    # Start backtest
    # Expect: Success, operation completes
```

**Quality Gate**:

```bash
make test-e2e
make test-unit
make quality
```

**Commit**: `test(e2e): add distributed-only mode integration tests`

**Estimated Time**: 2 hours

---

### Task 5.6: Migrate training-host-service to WorkerAPIBase

**Objective**: Convert training-host-service from standalone FastAPI to WorkerAPIBase pattern for self-registration

**Why Needed**:
- **Current**: training-host-service runs as standalone service, no worker registration
- **Problem**: GPU host service invisible to WorkerRegistry (doesn't show in `/api/v1/workers`)
- **Solution**: Migrate to WorkerAPIBase → automatic registration with `gpu: true` capability

**Critical for**:
- GPU-first worker selection (TrainingService can't find GPU workers)
- Unified worker management (all workers visible via WorkerRegistry)
- Consistent worker pattern (BacktestWorker and TrainingWorker already use WorkerAPIBase)

**TDD Approach**:

1. Create `tests/unit/training_host/test_gpu_worker_registration.py`
2. Test scenarios:
   - Worker registers with `gpu: true` capability
   - Worker reports GPU type (CUDA vs MPS)
   - Worker health check includes GPU availability
   - OperationsService endpoints work via WorkerAPIBase

**Implementation**:

**Step 1: Convert training-host-service/main.py** (~2 hours)

```python
# training-host-service/main.py
import sys
from pathlib import Path
import torch

sys.path.insert(0, str(Path(__file__).parent.parent))

from ktrdr.workers.base import WorkerAPIBase
from ktrdr.api.models.workers import WorkerType
from ktrdr.api.models.operations import OperationType

class TrainingHostWorker(WorkerAPIBase):
    """Training host service using WorkerAPIBase pattern."""

    def __init__(
        self,
        worker_port: int = 5002,
        backend_url: str = "http://localhost:8000",
    ):
        # Detect GPU capabilities
        capabilities = self._detect_gpu_capabilities()

        super().__init__(
            worker_type=WorkerType.TRAINING,
            operation_type=OperationType.TRAINING,
            worker_port=worker_port,
            backend_url=backend_url,
            capabilities=capabilities,
        )

        # Import and register domain-specific endpoints
        from endpoints.training import router as training_router
        self.app.include_router(training_router)

    def _detect_gpu_capabilities(self) -> dict:
        """Detect GPU type and availability."""
        cuda_available = torch.cuda.is_available()
        mps_available = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

        if cuda_available:
            return {
                "gpu": True,
                "gpu_type": "CUDA",
                "gpu_count": torch.cuda.device_count(),
            }
        elif mps_available:
            return {
                "gpu": True,
                "gpu_type": "MPS",
                "gpu_count": 1,
            }
        else:
            return {"gpu": False}

# Create worker instance
worker = TrainingHostWorker()
app = worker.app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=5002,
        reload=True,
    )
```

**Step 2: Remove duplicate OperationsService setup** (~30 min)

- Remove manual OperationsService initialization from `startup_event`
- WorkerAPIBase already provides this
- Remove duplicate operations router inclusion

**Step 3: Test GPU worker shows in registry** (~30 min)

```bash
# Start training-host-service
cd training-host-service && ./start.sh

# Verify registration
curl http://localhost:8000/api/v1/workers | jq '.[] | select(.worker_type=="TRAINING")'
# Should show worker with gpu:true, gpu_type:"CUDA" or "MPS"
```

**Acceptance Criteria**:

1. ✅ training-host-service shows in `/api/v1/workers` with `gpu: true`
2. ✅ GPU type correctly reported (CUDA or MPS)
3. ✅ TrainingService._select_training_worker() finds GPU worker
4. ✅ Training requests route to GPU worker first
5. ✅ All existing training endpoints still work
6. ✅ OperationsService endpoints work (`/api/v1/operations`)

**Quality Gate**:

```bash
# Start training-host-service
cd training-host-service && ./start.sh

# Verify worker registration
curl http://localhost:8000/api/v1/workers | grep -q "gpu.*true" || echo "FAIL: GPU worker not registered"

# Verify training works
ktrdr models train --strategy neuro_mean_reversion --symbol EURUSD --timeframe 1d

# Verify tests pass
make test-unit
make quality
```

**Commit**: `feat(training-host): migrate to WorkerAPIBase for GPU worker registration`

**Estimated Time**: 3 hours

---

**Phase 5 (Docker-Only) Checkpoint**:
✅ No local execution mode in BacktestingService
✅ No local execution mode in TrainingService
✅ Backend is orchestrator-only (never executes operations)
✅ GPU training-host-service registers as worker with gpu:true
✅ Simplified codebase with single execution path
✅ Clear error messages when workers unavailable
✅ **TESTABLE**: All operations require workers/host services

**Total Phase 5 (Tasks 5.1-5.6) Time**: ~11.5 hours

**Architectural Achievement**: Clean separation - Backend orchestrates, Workers execute. All workers self-register!

**Next Step**: Deploy to Docker Compose and test! (Or continue to Task 5.7 for multi-host support)

---

### Task 5.7: Multi-Host Network Configuration (OPTIONAL)

⚠️ **Only complete this task if deploying to Proxmox LXC, Kubernetes, or cloud!**

**Skip this task if**:
- You're only using Docker Compose on a single host
- You're in development/testing phase
- You don't need multi-host deployment yet

**Complete this task if**:
- Deploying to Proxmox LXC containers
- Deploying to Kubernetes
- Deploying to cloud (AWS, GCP, Azure)
- Workers are on different physical machines

---

**Objective**: Fix worker endpoint URL discovery and backend URL configuration for multi-host deployments

**Why Needed**:
- **Current**: Workers use `hostname:port` (e.g., `http://ktrdr-backtest-1:5003`)
- **Problem**: Hostnames don't resolve across different hosts/networks
- **Solution**: IP-based endpoint URLs with environment variable overrides

**Critical Gaps Fixed**:
1. Worker endpoint URL discovery (hostname doesn't work cross-network)
2. Backend URL configuration (no hardcoded Docker hostnames)
3. Port conflicts in Proxmox (bind to specific IP, not 0.0.0.0)

**TDD Approach**:

1. Create `tests/unit/workers/test_network_config.py`
2. Test IP detection logic
3. Test environment variable overrides
4. Test failures when KTRDR_API_URL missing

**Implementation**:

**Step 1: Update WorkerRegistration** (~2 hours)

```python
# ktrdr/backtesting/worker_registration.py (and training version)

from urllib.parse import urlparse

class WorkerRegistration:
    def __init__(self, worker_type: str = "backtesting", ...):
        self.worker_type = worker_type
        self.port = int(os.getenv("WORKER_PORT", "5003"))

        # Backend URL is REQUIRED (no default)
        self.backend_url = os.getenv("KTRDR_API_URL")
        if not self.backend_url:
            raise RuntimeError(
                "KTRDR_API_URL environment variable is required for worker registration. "
                "Example: KTRDR_API_URL=http://192.168.1.100:8000"
            )

    def get_endpoint_url(self) -> str:
        """
        Get endpoint URL - IP-based for cross-network compatibility.

        Priority:
        1. WORKER_ENDPOINT_URL env var (explicit configuration)
        2. Auto-detected IP address (for multi-host)
        3. Hostname (for Docker Compose fallback)
        """
        # 1. Explicit configuration (Proxmox/cloud deployments)
        if endpoint_url := os.getenv("WORKER_ENDPOINT_URL"):
            return endpoint_url

        # 2. Auto-detect IP address (for multi-host deployments)
        if ip_address := self._detect_ip_address():
            return f"http://{ip_address}:{self.port}"

        # 3. Fallback to hostname (for Docker Compose)
        hostname = socket.gethostname()
        logger.warning(
            f"Using hostname for endpoint URL: {hostname}. "
            f"This may not work in multi-host deployments. "
            f"Set WORKER_ENDPOINT_URL=http://<IP>:{self.port} for production."
        )
        return f"http://{hostname}:{self.port}"

    def _detect_ip_address(self) -> Optional[str]:
        """
        Detect worker's IP address visible to backend.

        Uses dummy socket connection to backend to discover which
        local IP address would be used for communication.
        """
        try:
            # Parse backend host from URL
            backend_host = urlparse(self.backend_url).hostname or "8.8.8.8"

            # Create dummy socket to backend
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((backend_host, 80))

            # Get local IP used for connection
            ip = s.getsockname()[0]
            s.close()

            logger.info(f"Auto-detected worker IP address: {ip}")
            return ip

        except Exception as e:
            logger.warning(f"Failed to auto-detect IP address: {e}")
            return None
```

**Step 2: Update WorkerAPIBase** (~1 hour)

```python
# ktrdr/workers/base.py

class WorkerAPIBase:
    def __init__(
        self,
        worker_type: WorkerType,
        operation_type: OperationType,
        worker_port: int,
        backend_url: str,
    ):
        # Backend URL validation (no defaults allowed)
        if not backend_url:
            raise RuntimeError(
                f"backend_url is required for {worker_type.value} worker. "
                f"Set KTRDR_API_URL environment variable."
            )

        self.backend_url = backend_url

        # Get worker IP for binding
        self.worker_ip = os.getenv("WORKER_IP", "0.0.0.0")

        # Worker ID (from environment or generate)
        self.worker_id = os.getenv(
            "WORKER_ID", f"{worker_type.value}-worker-{os.urandom(4).hex()}"
        )

        # ... rest of init ...
```

**Step 3: Update Docker Worker Startup** (~1 hour)

```python
# ktrdr/backtesting/backtest_worker.py

# Remove hardcoded default
backend_url = os.getenv("KTRDR_API_URL")
if not backend_url:
    raise RuntimeError(
        "KTRDR_API_URL environment variable is required. "
        "Example: KTRDR_API_URL=http://backend:8000"
    )

worker = BacktestWorker(
    worker_port=int(os.getenv("WORKER_PORT", "5003")),
    backend_url=backend_url,  # No default!
)
```

**Step 4: Environment-Specific Configuration** (~1 hour)

```yaml
# config/workers.docker.yaml
backend_url: http://backend:8000  # Docker DNS
worker_endpoint_mode: hostname     # Hostname OK in Docker
health_check_interval: 10

# config/workers.proxmox.yaml
backend_url: http://192.168.1.100:8000  # Explicit IP
worker_endpoint_mode: ip                 # IP required for multi-host
health_check_interval: 10
network:
  subnet: 192.168.1.0/24
  backend_ip: 192.168.1.100
  worker_ip_range: 192.168.1.201-250
```

**Step 5: Update docker-compose.yml** (~0.5 hour)

```yaml
# docker/docker-compose.yml
backend:
  environment:
    - KTRDR_API_URL=http://backend:8000  # Explicit (no default in code)

backtest-worker:
  environment:
    - KTRDR_API_URL=http://backend:8000  # Explicit (no default in code)
    - WORKER_PORT=5003
    - WORKER_IP=0.0.0.0  # Bind to all interfaces (Docker default)
    # WORKER_ENDPOINT_URL not set - will auto-detect via hostname
```

**Step 6: Proxmox Deployment Configuration** (~0.5 hour)

```bash
# Proxmox LXC worker configuration
# /opt/ktrdr/.env on worker LXC

KTRDR_API_URL=http://192.168.1.100:8000
WORKER_ENDPOINT_URL=http://192.168.1.201:5003  # Explicit IP
WORKER_IP=192.168.1.201  # Bind to this IP only (not 0.0.0.0)
WORKER_PORT=5003  # Same port OK, different IPs
WORKER_ID=ktrdr-backtest-1
```

**Quality Gate**:

```bash
# Test 1: Docker Compose (hostname-based)
docker-compose up -d
curl http://localhost:8000/api/v1/workers | jq '.workers[0].endpoint_url'
# Expected: "http://backtest-worker:5003" or "http://172.18.0.5:5003"

# Test 2: Explicit IP configuration
WORKER_ENDPOINT_URL=http://192.168.1.201:5003 \
KTRDR_API_URL=http://192.168.1.100:8000 \
python -m ktrdr.backtesting.backtest_worker &

curl http://192.168.1.100:8000/api/v1/workers | jq '.workers[0].endpoint_url'
# Expected: "http://192.168.1.201:5003"

# Test 3: Missing KTRDR_API_URL (should fail)
python -m ktrdr.backtesting.backtest_worker
# Expected: RuntimeError with clear message

make test-unit
make quality
```

**Commit**: `fix(workers): add IP-based endpoint URL discovery for multi-host deployments`

**Estimated Time**: 6 hours

---

**Phase 5 (Complete) Checkpoint**:
✅ Docker-only distributed mode (Tasks 5.1-5.5)
✅ Multi-host networking support (Task 5.6 - if completed)
✅ Backend is orchestrator-only
✅ Clean architecture with single execution path
✅ **READY FOR**: Proxmox, Kubernetes, cloud deployments

**Total Phase 5 Time**: 8.5 hours (Docker) or 14.5 hours (Docker + Multi-host)

---

## Phase 6: Production Deployment & Continuous Delivery

**Goal**: Production-ready deployment with continuous delivery pipeline

**Why This Phase**: Architecture is clean, now make it production-ready with automated deployment

**End State**:

- LXC template for base environment (OS, Python, dependencies)
- Automated code deployment (separate from template - enables CD!)
- Configuration management (dev/prod environments)
- Monitoring and observability
- **TESTABLE**: Deploy code update to all workers with one command

**Key Insight**: Template = environment (changes rarely). Code = deployed separately (changes frequently). This enables continuous deployment without template rebuilding!

---

### Task 6.1: LXC Base Template Creation

**Objective**: Create reusable LXC template with base environment (NOT code!)

**Why Template Doesn't Include Code**:

- Template changes are slow (rebuild, redeploy all workers)
- Code changes are frequent (multiple times per day)
- Separation enables continuous deployment

**Template Contains**:
- Ubuntu 22.04 LTS
- Python 3.13
- `uv` package manager
- System dependencies
- Base directory structure

**Template Does NOT Contain**:
- KTRDR code
- Configuration files
- Environment variables
- Models or data

**Implementation**:

1. Create LXC template script (`scripts/lxc/create-template.sh`):

   ```bash
   #!/bin/bash
   # Create base LXC template for KTRDR workers

   # Create LXC container
   pct create 999 local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst \
     --hostname ktrdr-template \
     --memory 2048 \
     --cores 2 \
     --rootfs local-lvm:8 \
     --net0 name=eth0,bridge=vmbr0,ip=dhcp

   # Start container
   pct start 999

   # Install system dependencies
   pct exec 999 -- bash -c "
     apt-get update
     apt-get install -y python3.13 python3.13-venv curl git
     curl -LsSf https://astral.sh/uv/install.sh | sh
   "

   # Create base directory structure
   pct exec 999 -- bash -c "
     mkdir -p /opt/ktrdr
     mkdir -p /opt/ktrdr/logs
     mkdir -p /opt/ktrdr/data
     mkdir -p /opt/ktrdr/models
   "

   # Stop container
   pct stop 999

   # Convert to template
   vzdump 999 --mode stop --dumpdir /var/lib/vz/template/cache/
   mv /var/lib/vz/template/cache/vzdump-lxc-999-*.tar.zst \
      /var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst

   # Delete original container
   pct destroy 999
   ```

2. Document template creation process

**Quality Gate**:

```bash
# Create worker from template
pct create 201 local:vztmpl/ktrdr-worker-base-v1.tar.zst

# Verify base environment
pct start 201
pct exec 201 -- python3.13 --version
pct exec 201 -- uv --version
pct exec 201 -- ls -la /opt/ktrdr
```

**Commit**: `feat(lxc): create base template for KTRDR workers`

**Estimated Time**: 3 hours

---

### Task 6.2: Code Deployment Scripts (CD-Friendly!)

**Objective**: Deploy code to workers without template rebuild

**Key Concept**: Code is deployed separately from template, enabling continuous delivery

**Implementation**:

1. Create deployment script (`scripts/deploy/deploy-code.sh`):

   ```bash
   #!/bin/bash
   # Deploy KTRDR code to worker(s)

   WORKER_IDS=${1:-"201 202 203"}  # Default to workers 201-203
   GIT_REF=${2:-"main"}            # Default to main branch

   for WORKER_ID in $WORKER_IDS; do
     echo "Deploying to worker $WORKER_ID..."

     # Clone/update code
     pct exec $WORKER_ID -- bash -c "
       cd /opt/ktrdr
       if [ -d .git ]; then
         git fetch origin
         git checkout $GIT_REF
         git pull origin $GIT_REF
       else
         git clone https://github.com/your-org/ktrdr.git .
         git checkout $GIT_REF
       fi
     "

     # Install dependencies
     pct exec $WORKER_ID -- bash -c "
       cd /opt/ktrdr
       uv sync
     "

     # Restart worker service
     pct exec $WORKER_ID -- systemctl restart ktrdr-worker
   done
   ```

2. Create systemd service for worker:

   ```ini
   # /etc/systemd/system/ktrdr-worker.service
   [Unit]
   Description=KTRDR Worker
   After=network.target

   [Service]
   Type=simple
   User=ktrdr
   WorkingDirectory=/opt/ktrdr
   Environment="PATH=/opt/ktrdr/.venv/bin:/usr/bin"
   ExecStart=/opt/ktrdr/.venv/bin/uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

**Quality Gate**:

```bash
# Deploy to test worker
./scripts/deploy/deploy-code.sh 201 main

# Verify deployment
pct exec 201 -- systemctl status ktrdr-worker
curl http://192.168.1.201:5003/health
```

**Commit**: `feat(deploy): add code deployment scripts for continuous delivery`

**Estimated Time**: 3 hours

---

### Task 6.3: Worker Provisioning Automation

**Objective**: Automate worker creation from template

**Implementation**:

1. Create provisioning script (`scripts/lxc/provision-worker.sh`):

   ```bash
   #!/bin/bash
   # Provision new worker from template

   WORKER_ID=$1
   WORKER_IP=$2
   WORKER_TYPE=${3:-"backtesting"}  # backtesting or training

   # Create from template
   pct clone 999 $WORKER_ID --hostname ktrdr-$WORKER_TYPE-$WORKER_ID

   # Configure network
   pct set $WORKER_ID --net0 name=eth0,bridge=vmbr0,ip=$WORKER_IP/24,gw=192.168.1.1

   # Start worker
   pct start $WORKER_ID

   # Configure environment
   pct exec $WORKER_ID -- bash -c "
     echo 'KTRDR_API_URL=http://192.168.1.100:8000' >> /opt/ktrdr/.env
     echo 'WORKER_ENDPOINT_URL=http://$WORKER_IP:5003' >> /opt/ktrdr/.env
     echo 'WORKER_TYPE=$WORKER_TYPE' >> /opt/ktrdr/.env
   "

   echo "Worker $WORKER_ID provisioned at $WORKER_IP"
   ```

**Quality Gate**:

```bash
# Provision new worker
./scripts/lxc/provision-worker.sh 204 192.168.1.204 backtesting

# Verify
pct list | grep 204
curl http://192.168.1.204:5003/health
```

**Commit**: `feat(lxc): add worker provisioning automation`

**Estimated Time**: 2 hours

---

### Task 6.4: Configuration Management

**Objective**: Manage environment-specific configuration

**Implementation**:

1. Create configuration files:

   ```bash
   config/
   ├── workers.dev.yaml
   ├── workers.prod.yaml
   └── deploy/
       ├── dev.env
       └── prod.env
   ```

2. Update deployment script to use environment configs

**Commit**: `feat(config): add environment-specific configuration management`

**Estimated Time**: 2 hours

---

### Task 6.5: Monitoring Endpoints

**Objective**: Health checks and monitoring for production

**Implementation**:

1. Enhance health endpoints with detailed metrics
2. Add Prometheus metrics endpoint
3. Create monitoring dashboard

**Commit**: `feat(monitoring): add production monitoring endpoints`

**Estimated Time**: 3 hours

---

### Task 6.6: CI/CD Pipeline Documentation

**Objective**: Document deployment process and automation

**Implementation**:

1. Create deployment runbook
2. Document rollback procedures
3. Create troubleshooting guide

**Commit**: `docs(deploy): add CI/CD pipeline documentation`

**Estimated Time**: 2 hours

---

**Phase 6 Complete**:
✅ LXC template for base environment
✅ Automated code deployment
✅ Worker provisioning automation
✅ Configuration management
✅ Production monitoring
✅ **READY FOR**: Production deployment!

**Total Phase 6 Time**: ~15 hours

---

## Summary

### Phase 5: Distributed-Only Architecture
- **Tasks 5.1-5.5** (Docker): 8.5 hours
- **Task 5.6** (Multi-host - OPTIONAL): 6 hours
- **Total**: 8.5-14.5 hours

### Phase 6: Production Deployment
- **Tasks 6.1-6.6**: 15 hours

### Grand Total: 23.5-29.5 hours

---

**Final Architecture**: Clean, distributed, production-ready system with continuous delivery pipeline!
