# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# KTRDR Development Guide

## 🎯 PRIME DIRECTIVE: Think Before You Code

**STOP AND THINK**: Before writing any code, you MUST:

1. Understand the root cause of the problem
2. Consider architectural implications
3. Propose the solution approach and get confirmation
4. Only then implement

## 🚫 ANTI-PATTERNS TO AVOID

### Critical: NEVER Kill the API Server

⛔ **NEVER EVER**: Run `lsof -ti:8000 | xargs kill` or similar commands to kill the API server
⛔ **REASON**: The API runs in Docker. Killing it destroys the entire Docker container system
✅ **DO**: If you need to test API changes, ask the user to restart Docker or just test with curl

### The "Quick Fix" Trap

❌ **DON'T**: Add try/except blocks to suppress errors
✅ **DO**: Understand why the error occurs and fix the root cause

❌ **DON'T**: Add new parameters/flags to work around issues  
✅ **DO**: Refactor the design if current structure doesn't support the need

❌ **DON'T**: Copy-paste similar code with slight modifications
✅ **DO**: Extract common patterns into reusable functions/classes

❌ **DON'T**: Add "bandaid" fixes that make code work but harder to understand
✅ **DO**: Take time to implement clean, maintainable solutions

## 🏗️ ARCHITECTURAL PRINCIPLES

### 1. Separation of Concerns

- Each module has ONE clear responsibility
- Dependencies flow in one direction: UI → API → Core → Data
- No circular dependencies or tight coupling

### 2. Distributed Workers Architecture

KTRDR uses a **distributed workers architecture** where the backend orchestrates operations across a cluster of worker nodes:

```
┌─────────────────────────────────────────────────────────────────┐
│ Backend (Docker Container, Port 8000)                          │
│  ├─ API Layer (FastAPI)                                        │
│  ├─ Service Orchestrators (NEVER execute operations)           │
│  ├─ WorkerRegistry (tracks all workers)                        │
│  └─ OperationsService (tracks all operations)                  │
└─────────────────────────────────────────────────────────────────┘
         │
         ├─ HTTP (Worker Registration & Operation Dispatch)
         │
    ┌────┴────┬──────────┬──────────┬─────────────┐
    │         │          │          │             │
    ▼         ▼          ▼          ▼             ▼
┌───────┐ ┌───────┐ ┌───────┐ ┌───────┐   ┌──────────────┐
│Backtest││Backtest││Training││Training│   │IB Host Service│
│Worker 1││Worker 2││Worker 1││Worker 2│   │(Port 5001)   │
│:5003   ││:5003   ││:5004   ││:5004   │   │Direct IB TCP │
└────────┘└────────┘└────────┘└────────┘   └──────────────┘
CPU-only  CPU-only  CPU-only  CPU-only    Direct IB Gateway

         ┌─────────────────────┐
         │Training Host Service│
         │(Port 5002)          │
         │GPU Access (CUDA/MPS)│
         └─────────────────────┘
         10x-100x faster training
```

**Key Architectural Changes**:

1. **Backend as Orchestrator Only**: Backend NEVER executes operations locally—it only selects workers and dispatches operations
2. **Distributed-Only Execution**: All backtesting and training operations execute on workers (no local fallback)
3. **Self-Registering Workers**: Workers push-register with backend on startup (infrastructure-agnostic)
4. **GPU-First Routing**: Training operations prefer GPU workers (10x-100x faster) with CPU worker fallback
5. **Horizontal Scalability**: Add more workers = more concurrent operations (`docker-compose up --scale backtest-worker=10`)

**Worker Types**:
- **Backtest Workers** (containerized, CPU-only): Execute backtesting operations, horizontally scalable
- **Training Workers** (containerized, CPU-only): Execute training operations (fallback), horizontally scalable
- **Training Host Service** (native, GPU): Execute GPU training (priority), limited by hardware
- **IB Host Service** (native): Direct IB Gateway access (Docker networking limitation)

**For More Details**: See [Distributed Workers Architecture Overview](docs/architecture-overviews/distributed-workers.md)

### 3. Service Orchestrator Pattern

Service managers (DataAcquisitionService, TrainingManager) inherit from `ServiceOrchestrator`:

- Unified async operation handling
- Progress tracking with `GenericProgressManager`
- Cancellation support via `CancellationToken`
- Environment-based adapter routing
- Automatic host service failover

### 4. Data Flow Clarity

```
IB Gateway → IB Host Service → Data Manager → Indicators → Fuzzy → Neural → Decisions
                                     ↓            ↓           ↓        ↓         ↓
                                  Storage    Calculations  Members  Models   Signals
```

### 5. Error Handling Philosophy

- Errors should bubble up with context
- Handle errors at the appropriate level
- Never silently swallow exceptions
- Always log before re-raising

## 🔍 BEFORE MAKING CHANGES

### 1. Understand the Current Code

```python
# Ask yourself:
# - What is this module's responsibility?
# - Who calls this code and why?
# - What assumptions does it make?
# - What would break if I change this?
```

### 2. Trace the Full Flow

Before modifying any function:

- Find all callers (grep/search)
- Understand the data flow
- Check for side effects
- Review related tests

### 3. Consider Architectural Impact

- Will this change make the code more or less maintainable?
- Does it align with existing patterns?
- Should we refactor instead of patching?

## 📝 IMPLEMENTATION CHECKLIST

When implementing features:

1. **Design First**
   - [ ] Write a brief design comment explaining the approach
   - [ ] Identify which modules will be affected
   - [ ] Consider edge cases and error scenarios

2. **Code Quality**
   - [ ] Follow existing patterns in the codebase
   - [ ] Add type hints for all parameters and returns
   - [ ] Write clear docstrings explaining "why", not just "what"
   - [ ] Keep functions focused and under 50 lines

3. **Testing**
   - [ ] Write tests BEFORE implementing
   - [ ] Test both happy path and error cases
   - [ ] Run existing tests to ensure no regression

4. **Integration**
   - [ ] Trace through the full execution path
   - [ ] Verify error handling at each level
   - [ ] Check logs make sense for debugging

## 🛑 WHEN TO STOP AND ASK

You MUST stop and ask for clarification when:

- The fix requires changing core architectural patterns
- You're adding the 3rd try/except block to make something work
- The solution feels like a "hack" or "workaround"
- You need to modify more than 3 files for a "simple" fix
- You're copy-pasting code blocks
- You're unsure about the broader impact

## 💭 THINKING PROMPTS

Before implementing, ask yourself:

1. "What problem am I actually solving?"
2. "Is this the simplest solution that could work?"
3. "Will someone understand this code in 6 months?"
4. "Am I fixing the symptom or the cause?"
5. "Is there a pattern in the codebase I should follow?"

## 🎨 CODE STYLE BEYOND FORMATTING

### Clarity Over Cleverness

```python
# ❌ Clever but unclear
result = [x for x in data if all(f(x) for f in filters)] if filters else data

# ✅ Clear and maintainable
def apply_filters(data: List[Any], filters: List[Callable]) -> List[Any]:
    """Apply multiple filter functions to data."""
    if not filters:
        return data
    
    filtered_data = []
    for item in data:
        if all(filter_func(item) for filter_func in filters):
            filtered_data.append(item)
    return filtered_data
```

### Explicit Over Implicit

```python
# ❌ Implicit behavior
def process_data(data, skip_validation=False):
    if not skip_validation:
        validate(data)  # What does this validate?

# ✅ Explicit behavior  
def process_data(data: pd.DataFrame, validate_schema: bool = True):
    """Process data with optional schema validation."""
    if validate_schema:
        validate_dataframe_schema(data, required_columns=['open', 'high', 'low', 'close'])
```

## 🔧 COMMON ISSUES AND ROOT CAUSES

### Issue: "Function not working in async context"

❌ **Quick Fix**: Wrap in try/except and return None
✅ **Root Cause Fix**: Ensure proper async/await chain from top to bottom

### Issue: "Data not loading correctly"

❌ **Quick Fix**: Add more retries and error suppression
✅ **Root Cause Fix**: Understand data format requirements and validate inputs

### Issue: "Frontend not updating"

❌ **Quick Fix**: Add setTimeout or force refresh
✅ **Root Cause Fix**: Trace Redux action flow and fix state management

## 🏛️ KEY ARCHITECTURAL PATTERNS

### ServiceOrchestrator Base Class

**Location**: [ktrdr/async_infrastructure/service_orchestrator.py](ktrdr/async_infrastructure/service_orchestrator.py)

All service managers inherit from ServiceOrchestrator and follow this pattern:

1. Environment-based configuration (e.g., `USE_IB_HOST_SERVICE`, `USE_TRAINING_HOST_SERVICE`)
2. Adapter initialization (local vs. host service routing)
3. Unified async operations with progress tracking
4. Cancellation token support
5. Operations service integration

**Example Pattern**:

```python
class DataAcquisitionService(ServiceOrchestrator):
    def __init__(self):
        # Reads USE_IB_HOST_SERVICE env var
        self.provider = self._initialize_provider()

    async def download_data(self, ...):
        # Unified async pattern with progress tracking
        return await self._execute_with_progress(...)
```

### Host Service Integration & Worker Deployment

**IB Host Service** (still uses environment variables):
- `USE_IB_HOST_SERVICE=true` → Route data operations to [ib-host-service](ib-host-service/)
- `IB_HOST_SERVICE_URL=http://localhost:5001` (default)
- **Why**: IB Gateway requires direct TCP connection (Docker networking limitation)

**Training & Backtesting** (now uses WorkerRegistry, NO environment flags):
- ❌ **REMOVED**: `USE_TRAINING_HOST_SERVICE`, `REMOTE_BACKTEST_SERVICE_URL` (Phase 5.3)
- ✅ **NOW**: Workers self-register with backend on startup (push-based registration)
- Backend uses WorkerRegistry to select available workers automatically
- GPU training workers register with `gpu: true` capability (prioritized automatically)
- CPU workers register as fallback (always available)

**Starting Workers**:

```bash
# Docker Compose (development)
docker-compose up -d --scale backtest-worker=5 --scale training-worker=3

# Training Host Service (GPU, runs natively)
cd training-host-service && ./start.sh

# Workers self-register at:
# - Backtest: http://localhost:5003
# - Training (CPU): http://localhost:5004
# - Training (GPU): http://localhost:5002
```

**Verification**:

```bash
# Check registered workers
curl http://localhost:8000/api/v1/workers | jq

# Expected: All workers show as AVAILABLE with proper capabilities
```

### WorkerAPIBase Pattern

**Location**: [ktrdr/workers/base.py](ktrdr/workers/base.py)

**Source**: Extracted from training-host-service (~670 lines) to provide proven working infrastructure for all worker types.

All workers inherit from WorkerAPIBase and get these features for free:

1. **OperationsService singleton** - Worker-local operation tracking
2. **Operations proxy endpoints** (374 lines):
   - `GET /api/v1/operations/{id}` - Get operation status
   - `GET /api/v1/operations/{id}/metrics` - Get operation metrics
   - `GET /api/v1/operations` - List operations
   - `DELETE /api/v1/operations/{id}/cancel` - Cancel operation
3. **Health endpoint** - Reports busy/idle status (`GET /health`)
4. **FastAPI app with CORS** - Ready for Docker communication
5. **Self-registration** - Worker registration with backend on startup (automatic)

**Key Pattern Elements**:
- **Operation ID Synchronization**: Accepts optional `task_id` from backend, returns same `operation_id`
- **Progress Tracking**: Workers register progress bridges in their OperationsService
- **Remote Queryability**: Backend can query worker's operations endpoints directly (1s cache TTL)
- **Push-Based Registration**: Workers call `POST /workers/register` on startup (infrastructure-agnostic)

**Worker Implementations**:

- **BacktestWorker** ([ktrdr/backtesting/backtest_worker.py](ktrdr/backtesting/backtest_worker.py)):
  - Adds `/backtests/start` endpoint
  - Calls BacktestingEngine directly via `asyncio.to_thread`
  - Registers BacktestProgressBridge

- **TrainingWorker** ([ktrdr/training/training_worker.py](ktrdr/training/training_worker.py)):
  - Adds `/training/start` endpoint
  - Calls TrainingManager directly (async)
  - Simplified progress tracking

**Code Reuse**: ~570 lines eliminated per worker by using WorkerAPIBase!

**Developer Resources**:
- **Architecture**: [Distributed Workers Architecture Overview](docs/architecture-overviews/distributed-workers.md)
- **Development**: [Distributed Workers Developer Guide](docs/developer/distributed-workers-guide.md) - Creating new worker types
- **Deployment**: [Docker Compose Deployment Guide](docs/user-guides/deployment.md) - Starting and scaling workers

**Example Pattern**:

```python
class BacktestWorker(WorkerAPIBase):
    def __init__(self, worker_port=5003, backend_url="http://backend:8000"):
        super().__init__(
            worker_type=WorkerType.BACKTESTING,
            operation_type=OperationType.BACKTESTING,
            worker_port=worker_port,
            backend_url=backend_url,
        )

        # Register domain-specific endpoint
        @self.app.post("/backtests/start")
        async def start_backtest(request: BacktestStartRequest):
            operation_id = request.task_id or f"worker_backtest_{uuid.uuid4().hex[:12]}"
            result = await self._execute_backtest_work(operation_id, request)
            return {"success": True, "operation_id": operation_id, **result}
```

### Async Operations Pattern (CLI Commands)

**Recent Migration**: All CLI commands migrated from sync to async (commit 8d9ca93)

**Pattern**: CLI commands use `AsyncCLIClient` for API communication:

```python
from ktrdr.cli.helpers.async_cli_client import AsyncCLIClient

async def some_command(symbol: str):
    async with AsyncCLIClient() as client:
        result = await client.post("/endpoint", json=data)
```

**Progress Display**: Use `GenericProgressManager` with `ProgressRenderer` for live updates

### Cancellation Tokens

**Global Coordinator**: [ktrdr/async_infrastructure/cancellation.py](ktrdr/async_infrastructure/cancellation.py)

All long-running operations support cancellation:

- Create tokens with `create_cancellation_token()`
- Check with `token.is_cancelled()`
- Operations service manages tokens globally
- CLI displays cancellation status

## 📚 REQUIRED READING

Before working on specific modules:

- **ServiceOrchestrator Pattern**: [ktrdr/async_infrastructure/service_orchestrator.py](ktrdr/async_infrastructure/service_orchestrator.py)
- **Distributed Workers Architecture** (IMPORTANT):
  - [docs/architecture-overviews/distributed-workers.md](docs/architecture-overviews/distributed-workers.md) - High-level architecture overview
  - [docs/developer/distributed-workers-guide.md](docs/developer/distributed-workers-guide.md) - Developer guide for creating/debugging workers
  - [docs/user-guides/deployment.md](docs/user-guides/deployment.md) - Docker Compose deployment (development)
  - [docs/user-guides/deployment-proxmox.md](docs/user-guides/deployment-proxmox.md) - Proxmox LXC deployment (production)
  - [docs/developer/cicd-operations-runbook.md](docs/developer/cicd-operations-runbook.md) - CI/CD and operations procedures
- **Data Module**:
  - [ktrdr/data/repository/data_repository.py](ktrdr/data/repository/data_repository.py) - Cached data access
  - [ktrdr/data/acquisition/acquisition_service.py](ktrdr/data/acquisition/acquisition_service.py) - Data downloads with ServiceOrchestrator
  - [ktrdr/data/CLAUDE.md](ktrdr/data/CLAUDE.md) - Data module patterns
- **Training Module**: [ktrdr/training/training_manager.py](ktrdr/training/training_manager.py) - Now uses WorkerRegistry (distributed-only)
- **Backtesting Module**: [ktrdr/backtesting/backtesting_service.py](ktrdr/backtesting/backtesting_service.py) - Now uses WorkerRegistry (distributed-only)
- **API Module**: Review FastAPI patterns in [ktrdr/api/](ktrdr/api/)
- **CLI Async Pattern**: [ktrdr/cli/helpers/async_cli_client.py](ktrdr/cli/helpers/async_cli_client.py)
- **Host Services**:
  - [ib-host-service/README.md](ib-host-service/README.md)
  - [training-host-service/README.md](training-host-service/README.md)
- **Testing**: Study existing test patterns in [tests/](tests/)

## ⚡ FINAL REMINDERS

1. **Quality > Speed**: Taking 2 hours to do it right saves 10 hours of debugging
2. **Ask Questions**: Unclear requirements lead to wrong implementations
3. **Refactor Fearlessly**: If the current design doesn't fit, change it
4. **Document Why**: Code shows "what", comments explain "why"
5. **Test Everything**: If it's not tested, it's broken

Remember: You're not just writing code, you're building a system. Every line should make the system better, not just make it work.

## ⚠️ CRITICAL: THIS PROJECT USES UV ⚠️

**NEVER run `python` or `python3` directly!** This project uses `uv` for Python dependency management.

**Always use `uv run` for Python commands:**

```bash
# Correct
uv run python script.py
uv run pytest tests/
uv run ktrdr data show AAPL 1d

# Wrong - will use system Python
python script.py
pytest tests/
```

## 🚀 COMMON DEVELOPMENT COMMANDS

### Running the System

```bash
# Start complete local dev environment (recommended)
docker compose -f docker-compose.dev.yml up

# Start in background
docker compose -f docker-compose.dev.yml up -d

# View logs
docker compose -f docker-compose.dev.yml logs -f

# Stop all services
docker compose -f docker-compose.dev.yml down

# Rebuild after Dockerfile changes
docker compose -f docker-compose.dev.yml build

# Restart specific service
docker compose -f docker-compose.dev.yml restart backend

# Start host services (for IB Gateway / GPU training)
cd ib-host-service && ./start.sh
cd training-host-service && ./start.sh
```

**Service URLs** (when running):

- Backend API: <http://localhost:8000>
- Grafana: <http://localhost:3000>
- Jaeger UI: <http://localhost:16686>
- Prometheus: <http://localhost:9090>

### CLI Usage

```bash
# The main entry point
ktrdr --help

# Data operations
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data load EURUSD 1h --start-date 2024-01-01 --end-date 2024-12-31
ktrdr data get-range AAPL 1d

# Training operations
ktrdr models train --strategy config/strategies/example.yaml
ktrdr models list
ktrdr models test model_v1.0.0 --symbol AAPL

# Operations management
ktrdr operations list
ktrdr operations status <operation-id>
ktrdr operations cancel <operation-id>

# IB Gateway integration
ktrdr ib test-connection
ktrdr ib check-status
```

## 🏭 PROXMOX PRODUCTION DEPLOYMENT

**For production deployments**, KTRDR uses Proxmox LXC containers for better performance and lower overhead than Docker.

### Why Proxmox LXC?

- **5-15% better performance** vs Docker (lower container overhead)
- **Lower memory footprint** per worker
- **Template-based cloning** for rapid worker scaling
- **Full OS environment** with systemd and native tooling
- **Proxmox management tools** (backups, snapshots, monitoring)
- **Multi-host clustering** for high availability

### Quick Start (Production)

```bash
# 1. Create LXC template (one-time setup)
# See: docs/user-guides/deployment-proxmox.md

# 2. Clone and deploy backend LXC
ssh root@proxmox "pct clone 900 100 --hostname ktrdr-backend"
ssh root@proxmox "pct set 100 --cores 4 --memory 8192 --net0 ip=192.168.1.100/24"
ssh root@proxmox "pct start 100"

# 3. Deploy code to backend
./scripts/deploy/deploy-code.sh --target 192.168.1.100

# 4. Clone and deploy worker LXCs (5 workers example)
for i in {1..5}; do
  CTID=$((200 + i))
  IP=$((200 + i))
  ssh root@proxmox "pct clone 900 $CTID --hostname ktrdr-worker-$i"
  ssh root@proxmox "pct set $CTID --cores 4 --memory 8192 --net0 ip=192.168.1.$IP/24"
  ssh root@proxmox "pct start $CTID"
  ./scripts/deploy/deploy-code.sh --target 192.168.1.$IP
done

# 5. Verify deployment
curl http://192.168.1.100:8000/api/v1/workers | jq
# Should show 5 registered workers
```

### Operations & Maintenance

**Automated Deployment**:
```bash
# Deploy new version (rolling update, zero downtime)
./scripts/deploy/deploy-to-proxmox.sh --env production --version v1.5.2
```

**Add Workers During High Load**:
```bash
# Clone from template, deploy code, workers auto-register
./scripts/lxc/provision-worker.sh --count 10 --start-id 211
```

**View System Status**:
```bash
# Health check all workers
./scripts/ops/system-status.sh

# View logs across all LXCs
./scripts/ops/view-logs.sh all "1 hour ago"

# Check resource usage
./scripts/ops/check-resources.sh
```

### Documentation

- **Deployment**: [docs/user-guides/deployment-proxmox.md](docs/user-guides/deployment-proxmox.md) - Complete Proxmox deployment guide
- **CI/CD**: [docs/developer/cicd-operations-runbook.md](docs/developer/cicd-operations-runbook.md) - Operations and incident response
- **Development**: [docs/user-guides/deployment.md](docs/user-guides/deployment.md) - Docker Compose for local development

### When to Use Proxmox vs Docker

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Local development | Docker Compose | Quick setup, easy iteration |
| Testing/staging | Docker Compose | Matches dev environment |
| Production | **Proxmox LXC** | Better performance, management tools |
| > 20 workers | **Proxmox LXC** | Lower overhead scales better |
| High-performance | **Proxmox LXC** | 5-15% performance gain matters |

## 🔥 DEVELOPMENT BEST PRACTICES

### Commit Discipline

- **NEVER commit more than 20-30 files at once** - Large commits are unmanageable
- **Make frequent, focused commits** - Each commit should represent one logical change
- **Always run tests before committing** - Use `make test-unit` to catch regressions
- **Always run linting before committing** - Use `make quality` for all quality checks
- **Use merge commits for PRs, NOT squash** - Preserves commit history for debugging

### Testing Discipline  

- **Run unit tests systematically** - Use `make test-unit` for fast feedback (<2s)
- **Run integration tests when needed** - Use `make test-integration` for component interaction tests
- **Never skip failing tests** - Fix or properly skip tests that don't pass
- **Test-driven development** - Write tests for new functionality
- **Proper test categorization**: Unit (fast, mocked), Integration (slower, real components), E2E (full system)

### Standard Testing Commands (Use Makefile)

```bash
# Fast development loop - run on every change
make test-unit          # Unit tests only (<2s)
make test-fast          # Alias for test-unit

# Integration testing - run when testing component interactions  
make test-integration   # Integration tests (<30s)

# Full system testing - run before major commits
make test-e2e          # End-to-end tests (<5min)

# Coverage and reporting
make test-coverage     # Unit tests with HTML coverage report

# Code quality - run before committing
make quality           # Lint + format + typecheck
make lint              # Ruff linting only  
make format            # Black formatting only
make typecheck         # MyPy type checking only

# CI simulation - matches GitHub Actions
make ci                # Run unit tests + quality checks
```

### Pre-Commit Checklist

1. `make test-unit` - All unit tests pass (<2s)
2. `make quality` - Lint, format, and type checking pass
3. Review changed files - No debug code or secrets
4. Write meaningful commit message
5. Keep commits small and focused (< 30 files)

### Test Performance Standards

- **Unit tests**: Must complete in <2 seconds total
- **Integration tests**: Should complete in <30 seconds total
- **E2E tests**: Should complete in <5 minutes total
- **Collection time**: Should be <2 seconds

## 🔍 DEBUGGING TIPS

### Host Services Not Working

```bash
# Check if services are running
lsof -i :5001  # IB Host Service
lsof -i :5002  # Training Host Service

# Test connectivity from Docker
docker exec ktrdr-backend curl http://host.docker.internal:5001/health
docker exec ktrdr-backend curl http://host.docker.internal:5002/health

# Check logs
tail -f ib-host-service/logs/ib-host-service.log
tail -f training-host-service/logs/training-host-service.log
```

### Environment Variable Issues

```bash
# Check what's set in Docker container
docker exec ktrdr-backend env | grep -E "(IB|TRAINING)"

# Common issues:
# - USE_IB_HOST_SERVICE not set → falls back to local (wrong in Docker)
# - URL wrong → connection failures
# - Service not started → timeouts
```

### Progress Not Updating

Check these in order:

1. Is `OperationsService` being used? ([ktrdr/api/services/operations_service.py](ktrdr/api/services/operations_service.py))
2. Is progress callback being passed to ServiceOrchestrator?
3. Is `GenericProgressManager` updating state?
4. Check cancellation token not triggered

### Data Loading Issues

Common root causes:

1. IB Gateway not running (port 4002)
2. IB Host Service not started or unreachable
3. Symbol format incorrect (use IB format: "AAPL" not "AAPL.US")
4. Date range outside available data
5. Timeframe not supported by data source

### 🔎 Observability-Powered Debugging (RECOMMENDED)

**IMPORTANT**: When users report issues with operations, **ALWAYS use observability first** instead of manual log parsing.

KTRDR has comprehensive OpenTelemetry instrumentation that provides X-ray vision into distributed operations. This enables **first-response diagnosis** instead of iterative detective work.

#### When to Use Observability

**ALWAYS query Jaeger when user reports**:

1. ✅ **"Operation stuck"** - See which phase is stuck and why
2. ✅ **"Operation failed"** - See exact error with full context
3. ✅ **"Operation slow"** - Identify bottleneck span immediately
4. ✅ **"No workers selected"** - See worker selection decision
5. ✅ **"Missing data"** - Trace data flow from IB to cache
6. ✅ **"Service not responding"** - See if HTTP call was attempted and result

#### Quick Start Workflow

**Step 1**: Get operation ID from user (shown in CLI output or API response)

**Step 2**: Query Jaeger API
```bash
OPERATION_ID="op_training_20251113_123456_abc123"
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID&limit=1" | jq
```

**Step 3**: Analyze trace structure
```bash
# Get span summary with durations
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID" | jq '
  .data[0].spans[] |
  {
    span: .operationName,
    service: .process.serviceName,
    duration_ms: (.duration / 1000),
    error: ([.tags[] | select(.key == "error" and .value == "true")] | length > 0)
  }' | jq -s 'sort_by(.duration_ms) | reverse'
```

**Step 4**: Extract relevant attributes
```bash
# Get all span attributes
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OPERATION_ID" | jq '
  .data[0].spans[] |
  {
    span: .operationName,
    attributes: (.tags | map({key: .key, value: .value}) | from_entries)
  }'
```

**Step 5**: Provide diagnosis in FIRST response

#### Common Diagnostic Patterns

**Pattern 1: Operation Stuck**
```bash
# Check for worker selection and dispatch
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  select(.operationName == "worker_registry.select_worker") |
  .tags[] |
  select(.key | startswith("worker_registry.")) |
  {key: .key, value: .value}'

# Look for:
# - worker_registry.total_workers: 0 → No workers started
# - worker_registry.capable_workers: 0 → No capable workers
# - worker_registry.selection_status: NO_WORKERS_AVAILABLE → All busy
```

**Pattern 2: Operation Failed**
```bash
# Extract error details
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  select(.tags[] | select(.key == "error" and .value == "true")) |
  {
    span: .operationName,
    service: .process.serviceName,
    exception_type: (.tags[] | select(.key == "exception.type") | .value),
    exception_message: (.tags[] | select(.key == "exception.message") | .value)
  }'

# Common errors:
# - ConnectionRefusedError → Service not running (check http.url for which service)
# - ValueError → Invalid input parameters (check business attributes)
# - DataNotFoundError → Data not loaded (check data.symbol, data.timeframe)
```

**Pattern 3: Operation Slow**
```bash
# Find bottleneck span (longest duration)
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  {
    span: .operationName,
    duration_ms: (.duration / 1000)
  }' | jq -s 'sort_by(.duration_ms) | reverse | .[0]'

# Common bottlenecks:
# - training.training_loop → Check if GPU vs CPU (training.device attribute)
# - data.fetch → Check ib.latency_ms for IB Gateway performance
# - ib.fetch_historical → Check data.bars_requested (may be too many)
```

**Pattern 4: Service Communication Failure**
```bash
# Check HTTP calls between services
curl -s "http://localhost:16686/api/traces?tag=operation.id:$OP_ID" | jq '
  .data[0].spans[] |
  select(.operationName | startswith("POST") or startswith("GET")) |
  {
    http_call: .operationName,
    url: (.tags[] | select(.key == "http.url") | .value),
    status: (.tags[] | select(.key == "http.status_code") | .value),
    error: (.tags[] | select(.key == "error.type") | .value)
  }'

# Look for:
# - http.status_code: null → Connection failed
# - error.type: ConnectionRefusedError → Target service not running
# - http.url → Shows which service was being called
```

#### Response Template

When diagnosing with observability, use this template:

```
🔍 **Trace Analysis for operation_id: {operation_id}**

**Trace Summary**:
- Trace ID: {trace_id}
- Total Duration: {duration_ms}ms
- Services: {list of services}
- Status: {OK/ERROR}

**Execution Flow**:
1. {span_name} ({service}) - {duration_ms}ms
2. {span_name} ({service}) - {duration_ms}ms
...

**Diagnosis**:
{identified_issue_with_evidence_from_spans}

**Root Cause**:
{root_cause_explanation_with_span_attributes}

**Solution**:
{recommended_fix_with_commands}
```

#### Key Span Attributes to Check

**Operation Attributes**:
- `operation.id` - Operation identifier
- `operation.type` - TRAINING, BACKTESTING, DATA_DOWNLOAD
- `operation.status` - PENDING, RUNNING, COMPLETED, FAILED

**Worker Selection**:
- `worker_registry.total_workers` - Total registered workers
- `worker_registry.available_workers` - Available workers
- `worker_registry.capable_workers` - Capable workers for this operation
- `worker_registry.selected_worker_id` - Which worker was chosen
- `worker_registry.selection_status` - SUCCESS, NO_WORKERS_AVAILABLE, NO_CAPABLE_WORKERS

**Progress Tracking**:
- `progress.percentage` - Current progress (0-100)
- `progress.phase` - Current execution phase
- `operations_service.instance_id` - OperationsService instance (check for mismatches)

**Error Context**:
- `exception.type` - Python exception class
- `exception.message` - Error message
- `exception.stacktrace` - Full stack trace
- `error.symbol`, `error.strategy` - Business context for error

**Performance**:
- `http.status_code` - HTTP response status
- `http.url` - Target URL for HTTP calls
- `ib.latency_ms` - IB Gateway latency
- `training.device` - cuda:0 or cpu
- `gpu.utilization_percent` - GPU usage (if applicable)

#### Full Documentation

For comprehensive debugging workflows, span attribute reference, and detailed scenarios:

📖 **[Observability Debugging Workflows](docs/debugging/observability-debugging-workflows.md)**

This document includes:
- Complete query pattern examples
- Step-by-step debugging scenarios
- Full span attribute reference
- Common issues and solutions
- Claude Code diagnostic templates

#### Benefits of Observability-First Debugging

✅ **Diagnosis in FIRST response** (not 10+ messages later)
✅ **Complete context** (all services, all phases, all attributes)
✅ **Objective evidence** (no guessing or assumptions)
✅ **Distributed visibility** (Backend → Worker → Host Service)
✅ **Performance insights** (identify bottlenecks immediately)
✅ **Root cause analysis** (trace error from source to root)

**Bottom Line**: Always check Jaeger before asking user for logs, environment variables, or service status. The trace contains all this information already.

## 📊 API DEVELOPMENT

### API Documentation

Once server running:

- Swagger UI: <http://localhost:8000/api/v1/docs>
- ReDoc: <http://localhost:8000/api/v1/redoc>

### Adding New Endpoints

1. Create endpoint in [ktrdr/api/endpoints/](ktrdr/api/endpoints/)
2. Define Pydantic models in [ktrdr/api/models/](ktrdr/api/models/)
3. Implement business logic in [ktrdr/api/services/](ktrdr/api/services/)
4. Register router in [ktrdr/api/main.py](ktrdr/api/main.py)
5. Add tests in [tests/api/](tests/api/)

### Async Operation Pattern (for long-running tasks)

```python
from ktrdr.api.services.operations_service import OperationsService

@router.post("/long-operation")
async def start_operation(
    background_tasks: BackgroundTasks,
    operations_service: OperationsService = Depends(get_operations_service)
):
    # Register operation
    operation_id = await operations_service.register_operation(
        operation_type=OperationType.TRAINING,
        description="Training model..."
    )

    # Start background task
    background_tasks.add_task(
        run_operation,
        operation_id,
        operations_service
    )

    return {"operation_id": operation_id}
```
