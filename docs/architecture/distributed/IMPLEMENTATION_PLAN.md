# Distributed Training & Backtesting Implementation Plan

**Version**: 1.0
**Status**: Ready for Implementation
**Date**: 2025-11-08

---

## Overview

This implementation plan uses **Test-Driven Development** with strict quality gates. Each task must:
- Write tests FIRST (TDD)
- Pass ALL unit tests: `make test-unit`
- Pass quality checks: `make quality`
- Result in ONE commit

All work will be done on a single feature branch: `claude/containerize-training-service-*`

---

## Phase Structure

- **Phase**: A complete, integrated feature. System MUST work at end of phase.
- **Task**: A single, testable unit of work. System SHOULD work, but transient breakage acceptable if building infrastructure.

---

## Phase 1: Foundation - Worker Registry Infrastructure

**Goal**: Add worker registry foundation without breaking existing system

**End State**: WorkerRegistry exists, can register workers, select workers. All existing functionality still works.

### Task 1.1: Worker Data Models

**Objective**: Define core data models for workers

**TDD Approach**:
1. Create `tests/unit/api/services/test_worker_models.py`
2. Write tests for:
   - `WorkerType` enum (GPU_HOST, CPU_TRAINING, BACKTESTING)
   - `WorkerStatus` enum (AVAILABLE, BUSY, TEMPORARILY_UNAVAILABLE)
   - `WorkerEndpoint` dataclass (all fields, validation)
   - Serialization/deserialization to/from dict

**Implementation**:
1. Create `ktrdr/api/models/workers.py`
2. Define enums and dataclass
3. Add to/from dict methods for JSON serialization

**Quality Gate**:
```bash
make test-unit  # All tests pass (including existing + new)
make quality    # Lint, format, typecheck pass
```

**Commit**: `feat(workers): add worker data models and types`

**Estimated Time**: 1 hour

---

### Task 1.2: WorkerRegistry - Basic Structure

**Objective**: Create WorkerRegistry class with in-memory storage (no background tasks yet)

**TDD Approach**:
1. Create `tests/unit/api/services/test_worker_registry.py`
2. Write tests for:
   - `__init__()` - initialization
   - `register_worker()` - add worker to registry
   - `get_worker(worker_id)` - retrieve by ID
   - `list_workers()` - list all workers
   - `list_workers(worker_type=...)` - filter by type
   - `list_workers(status=...)` - filter by status

**Implementation**:
1. Create `ktrdr/api/services/worker_registry.py`
2. Implement WorkerRegistry class:
   - In-memory dict storage: `_workers: Dict[str, WorkerEndpoint]`
   - Registration (idempotent - updates if exists)
   - Retrieval and listing methods
3. NO background tasks yet (health checks come later)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add WorkerRegistry with basic registration`

**Estimated Time**: 2 hours

---

### Task 1.3: WorkerRegistry - Worker Selection

**Objective**: Add round-robin worker selection logic

**TDD Approach**:
1. Add tests to `tests/unit/api/services/test_worker_registry.py`:
   - `select_worker(worker_type)` - returns least recently used
   - Round-robin behavior (select 3 workers sequentially, verify order)
   - Filtering by capabilities: `select_worker(worker_type, capabilities={"gpu": True})`
   - Returns None if no workers available
   - Returns None if all workers are BUSY

**Implementation**:
1. Add to WorkerRegistry:
   - `get_available_workers(worker_type, capabilities)` - filter logic
   - `select_worker(worker_type, capabilities)` - round-robin selection
   - Track `last_selected` timestamp in worker metadata
2. Add worker state management:
   - `mark_busy(worker_id, operation_id)`
   - `mark_available(worker_id)`

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add worker selection with round-robin load balancing`

**Estimated Time**: 2 hours

---

### Task 1.4: Worker Registration API Endpoint

**Objective**: Add POST /workers/register endpoint

**TDD Approach**:
1. Create `tests/unit/api/endpoints/test_workers.py`
2. Write tests for:
   - POST `/api/v1/workers/register` - successful registration
   - Returns 200 with worker info
   - Idempotent (re-registration updates existing)
   - Validation errors (missing fields, invalid worker_type)
3. Add integration test in `tests/integration/api/test_worker_registration.py`:
   - Full API call via TestClient

**Implementation**:
1. Create `ktrdr/api/endpoints/workers.py`
2. Define Pydantic models:
   - `WorkerRegistrationRequest`
   - `WorkerRegistrationResponse`
3. Implement endpoint:
   - Validates input
   - Calls `worker_registry.register_worker()`
   - Returns worker info
4. Add router to `ktrdr/api/main.py`
5. Create dependency injection for WorkerRegistry (singleton pattern)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add worker registration API endpoint`

**Estimated Time**: 2 hours

---

### Task 1.5: Worker List API Endpoint

**Objective**: Add GET /workers endpoint for monitoring

**TDD Approach**:
1. Add tests to `tests/unit/api/endpoints/test_workers.py`:
   - GET `/api/v1/workers` - list all workers
   - Filter by `worker_type` query param
   - Filter by `status` query param
   - Returns correct JSON structure

**Implementation**:
1. Add to `ktrdr/api/endpoints/workers.py`:
   - `WorkerListResponse` Pydantic model
   - GET endpoint with optional filters
   - Calls `worker_registry.list_workers()`

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add worker list API endpoint for monitoring`

**Estimated Time**: 1 hour

---

**Phase 1 Checkpoint**:
- WorkerRegistry exists with registration and selection
- API endpoints for registration and listing
- All existing tests still pass
- System works (no functionality changed, only added)

**Total Phase 1 Time**: ~8 hours

---

## Phase 2: Backtesting Worker Integration

**Goal**: Enable distributed backtesting with containerized workers

**End State**: Backtesting operations can be dispatched to remote workers. Progress tracking works. All existing tests pass.

### Task 2.1: Enhance BacktestingService - Worker Selection

**Objective**: Add worker selection to BacktestingService

**TDD Approach**:
1. Create `tests/unit/api/services/test_backtesting_service_workers.py`
2. Write tests for:
   - `_select_worker(context)` - selects available backtest worker
   - Returns None if no workers available
   - Raises appropriate error if no workers

**Implementation**:
1. Modify `ktrdr/api/services/backtesting_service.py`:
   - Add `worker_registry` parameter to `__init__`
   - Implement `_select_worker()` method (required by ServiceOrchestrator)
   - Implement `_get_required_capabilities()` - returns empty dict (no special needs)
2. Keep existing local execution mode working (backward compatibility)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(backtesting): add worker selection to BacktestingService`

**Estimated Time**: 2 hours

---

### Task 2.2: ServiceOrchestrator - Worker Dispatch Support

**Objective**: Add worker dispatch logic to ServiceOrchestrator base class

**TDD Approach**:
1. Create `tests/unit/async_infrastructure/test_service_orchestrator_dispatch.py`
2. Write tests for:
   - `_dispatch_to_worker(worker, context)` - dispatches operation
   - Retry logic (max 3 attempts)
   - 503 response triggers retry with different worker
   - Returns remote operation_id

**Implementation**:
1. Modify `ktrdr/async_infrastructure/service_orchestrator.py`:
   - Add abstract methods:
     - `_select_worker(operation_context) -> Optional[WorkerEndpoint]`
     - `_get_required_capabilities(operation_context) -> Dict[str, Any]`
   - Add `_dispatch_to_worker(worker, context, max_retries=3)` method
   - Add `worker_registry` to `__init__` (optional, for backward compatibility)
2. Dispatch flow:
   - POST to `worker.endpoint_url/<operation_endpoint>`
   - Parse response for remote operation_id
   - Handle 503 (worker busy) → retry with different worker
   - Handle other errors → fail operation

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(orchestrator): add worker dispatch support to ServiceOrchestrator`

**Estimated Time**: 3 hours

---

### Task 2.3: Enhance Backtest Worker API - Registration on Startup

**Objective**: Make backtest worker self-register with backend

**TDD Approach**:
1. Create `tests/unit/backtesting/test_worker_registration.py`
2. Write tests for:
   - `register_with_backend()` - sends POST to backend
   - Retry logic (max 5 attempts with backoff)
   - Environment variable configuration (BACKEND_URL, WORKER_ID)

**Implementation**:
1. Modify `ktrdr/backtesting/remote_api.py`:
   - Add startup event handler `on_startup()`
   - Implement `register_with_backend()` function
   - Read config from environment:
     - `BACKEND_URL` (required)
     - `WORKER_ID` (default: hostname)
     - `WORKER_TYPE` (default: "backtesting")
   - Send POST to `{BACKEND_URL}/api/v1/workers/register`
2. Add worker state to health endpoint (already exists, enhance):
   - Return `worker_status: "idle" | "busy"`
   - Return `current_operation: str | None`

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(backtesting): add self-registration on worker startup`

**Estimated Time**: 2 hours

---

### Task 2.4: Backtest Worker - Exclusivity Enforcement

**Objective**: Ensure backtest worker rejects requests when busy

**TDD Approach**:
1. Add tests to `tests/unit/backtesting/test_remote_api.py`:
   - POST `/backtests/start` when idle → 200
   - POST `/backtests/start` when busy → 503
   - Worker state transitions: idle → busy → idle

**Implementation**:
1. Modify `ktrdr/backtesting/remote_api.py`:
   - Add module-level worker state:
     ```python
     worker_state = {
         "status": "idle",  # idle | busy
         "current_operation_id": None
     }
     ```
   - Modify `/backtests/start` endpoint:
     - Check if busy → return 503
     - Mark busy before starting operation
     - Mark idle when operation completes (in background task)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(backtesting): enforce worker exclusivity (reject when busy)`

**Estimated Time**: 1.5 hours

---

### Task 2.5: BacktestingService - Remote Dispatch Integration

**Objective**: Wire up BacktestingService to dispatch to workers

**TDD Approach**:
1. Add integration test in `tests/integration/backtesting/test_distributed_backtest.py`:
   - Start mock worker (httpx mock or actual test server)
   - Register worker
   - Start backtest via BacktestingService
   - Verify dispatched to worker
   - Verify proxy registered for progress tracking

**Implementation**:
1. Modify `ktrdr/api/services/backtesting_service.py`:
   - Modify `start_backtest()` method:
     - If `worker_registry` is None: Use local execution (existing code path)
     - If `worker_registry` exists:
       - Select worker via `_select_worker()`
       - Dispatch to worker via `_dispatch_to_worker()`
       - Register proxy via `operations_service.register_remote_proxy()`
       - Mark worker busy via `worker_registry.mark_busy()`
2. Maintain backward compatibility (no worker registry = local mode)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(backtesting): integrate worker dispatch into BacktestingService`

**Estimated Time**: 3 hours

---

### Task 2.6: End-to-End Test - Distributed Backtesting

**Objective**: Full integration test with real worker

**TDD Approach**:
1. Create `tests/e2e/test_distributed_backtesting.py`
2. Test flow:
   - Start backend (FastAPI app)
   - Start backtest worker (separate process)
   - Worker registers with backend
   - Submit backtest via API
   - Poll for progress
   - Verify completion
   - Verify results

**Implementation**:
1. Write comprehensive E2E test
2. May use pytest fixtures to manage processes
3. Verify progress tracking works end-to-end

**Quality Gate**:
```bash
make test-unit
make test-e2e  # This specific E2E test
make quality
```

**Commit**: `test(backtesting): add end-to-end distributed backtesting test`

**Estimated Time**: 2 hours

---

**Phase 2 Checkpoint**:
- Backtesting workers can register with backend
- BacktestingService dispatches to workers
- Progress tracking works remotely
- Worker exclusivity enforced
- All existing tests pass
- E2E test validates entire flow

**Total Phase 2 Time**: ~13.5 hours

---

## Phase 3: Training Worker Support

**Goal**: Enable distributed CPU training with containerized workers

**End State**: Training operations can be dispatched to CPU workers with GPU fallback. All existing tests pass.

### Task 3.1: Training Worker API - New Module

**Objective**: Create new training worker API (similar to backtest worker)

**TDD Approach**:
1. Create `tests/unit/training/test_training_worker_api.py`
2. Write tests for:
   - Health endpoint returns worker status
   - POST `/training/start` - starts training
   - POST `/training/start` when busy → 503
   - Worker state machine (idle → busy → idle)

**Implementation**:
1. Create `ktrdr/training/training_worker_api.py`
2. Implement FastAPI app:
   - Health endpoint
   - POST `/training/start` endpoint
   - Worker state management
   - Exclusivity enforcement (reject if busy)
   - Background task execution (uses existing training code)
3. Registration on startup (similar to backtest worker)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(training): create training worker API for CPU execution`

**Estimated Time**: 3 hours

---

### Task 3.2: TrainingService - Hybrid Worker Selection

**Objective**: Add GPU-first, CPU-fallback worker selection to TrainingService

**TDD Approach**:
1. Create `tests/unit/api/services/test_training_service_workers.py`
2. Write tests for:
   - `_select_worker()` - tries GPU first, falls back to CPU
   - GPU available → returns GPU host
   - GPU unavailable → returns CPU worker
   - No workers available → returns None

**Implementation**:
1. Modify `ktrdr/api/services/training_service.py`:
   - Add `worker_registry` to `__init__`
   - Implement `_select_worker()`:
     ```python
     def _select_worker(self, context):
         # Try GPU first
         gpu_workers = self.worker_registry.get_available_workers(
             worker_type=WorkerType.GPU_HOST,
             capabilities={"gpu": True}
         )
         if gpu_workers:
             return gpu_workers[0]

         # Fallback to CPU workers
         cpu_workers = self.worker_registry.get_available_workers(
             worker_type=WorkerType.CPU_TRAINING
         )
         return cpu_workers[0] if cpu_workers else None
     ```
   - Implement `_get_required_capabilities()` - returns empty dict
2. Maintain backward compatibility (no worker registry = local mode)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(training): add hybrid GPU/CPU worker selection`

**Estimated Time**: 2 hours

---

### Task 3.3: TrainingService - Remote Dispatch Integration

**Objective**: Wire up TrainingService to dispatch to workers

**TDD Approach**:
1. Add integration test in `tests/integration/training/test_distributed_training.py`:
   - Register CPU training worker
   - Start training via TrainingService
   - Verify dispatched to worker
   - Verify proxy registered

**Implementation**:
1. Modify `ktrdr/api/services/training_service.py`:
   - Modify `start_training()` method:
     - If `worker_registry` is None: Use existing GPU host or local
     - If `worker_registry` exists:
       - Select worker (GPU first, CPU fallback)
       - Dispatch to worker
       - Register proxy
       - Mark worker busy
2. Maintain all existing functionality

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(training): integrate worker dispatch into TrainingService`

**Estimated Time**: 3 hours

---

### Task 3.4: End-to-End Test - Distributed Training

**Objective**: Full integration test with CPU training worker

**TDD Approach**:
1. Create `tests/e2e/test_distributed_training.py`
2. Test flow:
   - Start backend
   - Start CPU training worker
   - Worker registers
   - Submit training via API
   - Poll for progress
   - Verify completion

**Implementation**:
1. Write comprehensive E2E test
2. Verify progress tracking works
3. Verify results are stored correctly

**Quality Gate**:
```bash
make test-unit
make test-e2e
make quality
```

**Commit**: `test(training): add end-to-end distributed training test`

**Estimated Time**: 2 hours

---

**Phase 3 Checkpoint**:
- Training workers can register with backend
- TrainingService dispatches to CPU workers with GPU fallback
- Progress tracking works remotely
- Worker exclusivity enforced
- All existing tests pass
- E2E test validates entire flow

**Total Phase 3 Time**: ~10 hours

---

## Phase 4: Health Monitoring & Reliability

**Goal**: Add health checks, failure detection, and automatic recovery

**End State**: Workers are monitored, dead workers removed, system self-heals. All tests pass.

### Task 4.1: WorkerRegistry - Health Check Infrastructure

**Objective**: Add background task for worker health checking

**TDD Approach**:
1. Add tests to `tests/unit/api/services/test_worker_registry.py`:
   - `health_check_worker(worker_id)` - performs health check
   - Successful check → resets failure counter
   - Failed check → increments failure counter
   - 3 consecutive failures → marks TEMPORARILY_UNAVAILABLE
   - Mock httpx calls for testing

**Implementation**:
1. Modify `ktrdr/api/services/worker_registry.py`:
   - Add `health_check_worker(worker_id)` method:
     - GET `{worker.endpoint_url}/health`
     - Parse response for worker_status
     - Update worker status (idle → AVAILABLE, busy → BUSY)
     - Update health_check_failures counter
     - Mark TEMPORARILY_UNAVAILABLE after threshold
   - Add configuration:
     - `health_check_interval: int = 10` (seconds)
     - `health_check_timeout: int = 5` (seconds)
     - `health_failure_threshold: int = 3` (failures)
2. No background task yet (next task)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add health check logic to WorkerRegistry`

**Estimated Time**: 2 hours

---

### Task 4.2: WorkerRegistry - Background Health Check Task

**Objective**: Start background asyncio task for continuous health monitoring

**TDD Approach**:
1. Add tests for:
   - `start()` - starts background task
   - `stop()` - stops background task cleanly
   - Background task runs health checks on interval
   - Use asyncio testing utilities (pytest-asyncio)

**Implementation**:
1. Modify WorkerRegistry:
   - Add `start()` method:
     - Creates httpx.AsyncClient
     - Starts `_health_check_loop()` background task
   - Add `stop()` method:
     - Closes httpx client
     - Cancels background task
   - Add `_health_check_loop()`:
     ```python
     async def _health_check_loop(self):
         while True:
             try:
                 for worker_id in list(self._workers.keys()):
                     await self.health_check_worker(worker_id)
                 await asyncio.sleep(self._health_check_interval)
             except Exception as e:
                 logger.error(f"Health check error: {e}")
                 await asyncio.sleep(self._health_check_interval)
     ```
2. Integrate into API startup:
   - Modify `ktrdr/api/main.py`:
     - Start WorkerRegistry on app startup
     - Stop on shutdown

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): add background health check task`

**Estimated Time**: 2.5 hours

---

### Task 4.3: WorkerRegistry - Dead Worker Cleanup

**Objective**: Remove workers that are unavailable for > 5 minutes

**TDD Approach**:
1. Add tests for:
   - Worker unavailable < 5min → kept in registry
   - Worker unavailable >= 5min → removed from registry
   - Timestamp tracking (last_healthy_at)

**Implementation**:
1. Modify WorkerRegistry:
   - Track `last_healthy_at` timestamp
   - Add `_cleanup_dead_workers()` method:
     - Finds workers with TEMPORARILY_UNAVAILABLE status
     - Checks time since last_healthy_at
     - Removes if > removal_threshold (300 seconds)
   - Call `_cleanup_dead_workers()` in health check loop
2. Add configuration:
   - `removal_threshold_seconds: int = 300` (5 minutes)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `feat(workers): auto-remove dead workers after 5 minutes`

**Estimated Time**: 1.5 hours

---

### Task 4.4: Worker Failure Handling - Operation Marking

**Objective**: When worker fails during operation, mark operation as failed

**TDD Approach**:
1. Create `tests/integration/workers/test_worker_failure_handling.py`
2. Test scenarios:
   - Worker crashes mid-operation
   - Health check detects failure
   - Operation marked as failed (or left as running - depends on detection)
   - User sees appropriate error message

**Implementation**:
1. Consider options:
   - **Option A**: Leave operation as RUNNING (worker may have completed before crash)
   - **Option B**: Mark operation as FAILED when worker becomes unavailable
   - **Recommendation**: Option A (simpler, matches existing pattern)
2. Document behavior in user-facing docs
3. May add operation timeout in future (not this phase)

**Quality Gate**:
```bash
make test-unit
make quality
```

**Commit**: `docs(workers): document worker failure behavior for operations`

**Estimated Time**: 1 hour

---

### Task 4.5: Integration Test - Health Check & Recovery

**Objective**: Validate health check system end-to-end

**TDD Approach**:
1. Create `tests/integration/workers/test_health_monitoring.py`
2. Test scenarios:
   - Worker registers → shows as AVAILABLE
   - Stop worker → health checks fail → marks TEMPORARILY_UNAVAILABLE
   - Restart worker → re-registers → shows as AVAILABLE
   - Worker down 5min → removed from registry

**Implementation**:
1. Write comprehensive integration tests
2. Use real worker processes or sophisticated mocks
3. Test timing with accelerated intervals (use test config)

**Quality Gate**:
```bash
make test-unit
make test-integration
make quality
```

**Commit**: `test(workers): add health monitoring integration tests`

**Estimated Time**: 2 hours

---

**Phase 4 Checkpoint**:
- Health checks run every 10 seconds
- Failed workers marked TEMPORARILY_UNAVAILABLE after 3 failures
- Dead workers removed after 5 minutes
- Workers can re-register and recover
- All tests pass

**Total Phase 4 Time**: ~9 hours

---

## Phase 5: Development Environment (Docker Compose)

**Goal**: Enable multi-worker scaling in development with Docker Compose

**End State**: Can scale workers in dev environment, test concurrent operations. All tests pass.

### Task 5.1: Docker Compose Configuration

**Objective**: Create docker-compose.dev.yml with backend + workers

**TDD Approach**:
1. Manual testing (no automated tests for Docker Compose itself)
2. Validation checklist:
   - Backend starts and is accessible
   - Workers start and register
   - Can scale workers: `docker-compose up --scale backtest-worker=3`

**Implementation**:
1. Create `docker/docker-compose.dev.yml`:
   ```yaml
   services:
     backend:
       build: ../
       ports: ["8000:8000"]
       environment:
         - WORKER_REGISTRY_ENABLED=true
       networks: [ktrdr-network]

     training-worker:
       build: ../
       command: ["uvicorn", "ktrdr.training.training_worker_api:app", ...]
       environment:
         - BACKEND_URL=http://backend:8000
         - WORKER_TYPE=training
       networks: [ktrdr-network]

     backtest-worker:
       build: ../
       command: ["uvicorn", "ktrdr.backtesting.remote_api:app", ...]
       environment:
         - BACKEND_URL=http://backend:8000
         - WORKER_TYPE=backtesting
       networks: [ktrdr-network]

   networks:
     ktrdr-network:
   ```
2. Update Dockerfile if needed for worker mode

**Quality Gate**:
```bash
docker-compose -f docker/docker-compose.dev.yml up -d
docker-compose -f docker/docker-compose.dev.yml ps  # Verify all running
curl http://localhost:8000/api/v1/workers  # Verify workers registered
docker-compose -f docker/docker-compose.dev.yml down
```

**Commit**: `feat(docker): add Docker Compose configuration for distributed workers`

**Estimated Time**: 2 hours

---

### Task 5.2: Worker Scaling Documentation

**Objective**: Document how to use Docker Compose for development

**Implementation**:
1. Create or update `docker/README.md`:
   - How to start environment
   - How to scale workers
   - How to view logs
   - How to test concurrent operations
2. Add to main README.md

**Quality Gate**:
```bash
make quality  # Markdown linting if configured
```

**Commit**: `docs(docker): add documentation for Docker Compose development`

**Estimated Time**: 1 hour

---

### Task 5.3: Load Testing - Concurrent Operations

**Objective**: Validate system handles concurrent operations

**TDD Approach**:
1. Create `tests/load/test_concurrent_operations.py`
2. Test scenarios:
   - 5 concurrent backtests
   - 3 concurrent training operations
   - All complete successfully
   - Progress tracking works for all

**Implementation**:
1. Write load test script
2. Use asyncio to submit concurrent operations
3. Verify all complete
4. Measure performance (time to completion)

**Quality Gate**:
```bash
# Start Docker Compose with scaled workers first
docker-compose -f docker/docker-compose.dev.yml up -d --scale backtest-worker=5 --scale training-worker=3

# Run load test
pytest tests/load/test_concurrent_operations.py -v

make quality
```

**Commit**: `test(load): add concurrent operations load test`

**Estimated Time**: 2 hours

---

**Phase 5 Checkpoint**:
- Docker Compose environment works
- Can scale workers dynamically
- Load testing validates concurrent operations
- Documentation complete

**Total Phase 5 Time**: ~5 hours

---

## Phase 6: Configuration & Production Preparation (Optional)

**Goal**: Production-ready configuration, LXC templates, monitoring

**Note**: This phase can be deferred to later sprint. Included for completeness.

### Task 6.1: Configuration Management

**Objective**: Environment-based configuration files

**Implementation**:
1. Create `config/workers.dev.yaml`
2. Create `config/workers.prod.yaml`
3. Add configuration loader: `ktrdr/api/services/worker_config.py`
4. Support environment variable substitution

**Commit**: `feat(config): add environment-based worker configuration`

**Estimated Time**: 2 hours

---

### Task 6.2: LXC Template Scripts

**Objective**: Automation scripts for Proxmox LXC deployment

**Implementation**:
1. Create `scripts/proxmox/create-lxc-template.sh`
2. Create `scripts/proxmox/deploy-lxc-workers.sh`
3. Add systemd service templates
4. Documentation

**Commit**: `feat(proxmox): add LXC deployment automation scripts`

**Estimated Time**: 4 hours

---

### Task 6.3: Monitoring Endpoints

**Objective**: Expose metrics for monitoring

**Implementation**:
1. Add `/metrics` endpoint (Prometheus format)
2. Track worker metrics (count, status distribution)
3. Track operation metrics (dispatch time, completion rate)

**Commit**: `feat(monitoring): add Prometheus metrics endpoints`

**Estimated Time**: 3 hours

---

**Phase 6 Total**: ~9 hours (optional, can be done later)

---

## Summary

### Total Implementation Time

| Phase | Tasks | Time | Status |
|-------|-------|------|--------|
| Phase 1: Foundation | 5 tasks | ~8 hours | Required |
| Phase 2: Backtesting | 6 tasks | ~13.5 hours | Required |
| Phase 3: Training | 4 tasks | ~10 hours | Required |
| Phase 4: Health & Reliability | 5 tasks | ~9 hours | Required |
| Phase 5: Docker Compose | 3 tasks | ~5 hours | Required |
| **Total (Phases 1-5)** | **23 tasks** | **~45.5 hours** | **MVP** |
| Phase 6: Production (Optional) | 3 tasks | ~9 hours | Deferred |

### Quality Standards

Every task must pass:
```bash
make test-unit      # All unit tests (existing + new)
make quality        # Lint + format + typecheck
```

Selected tasks also require:
```bash
make test-integration  # Integration tests
make test-e2e          # End-to-end tests
```

### Git Workflow

- **One branch**: All work on `claude/containerize-training-service-*`
- **One commit per task**: Clear, descriptive commit messages
- **TDD**: Write tests first, then implementation
- **Incremental**: Each task builds on previous

### Risk Mitigation

**Low Risk** (well-understood):
- Data models and basic CRUD
- API endpoints (existing patterns)
- Docker Compose configuration

**Medium Risk** (new patterns):
- Worker dispatch retry logic
- Health check timing and thresholds
- Background asyncio tasks

**Mitigation Strategy**:
- Start with simple implementation
- Add complexity incrementally
- Comprehensive testing at each step
- Manual testing in Docker environment

### Success Criteria

**Phase 1-3**: Distributed backtesting and training work end-to-end
**Phase 4**: System self-heals from worker failures
**Phase 5**: Development environment supports multi-worker scaling

**Overall**: System is production-ready for Proxmox LXC deployment

---

## Next Steps

1. ✅ Review and approve DESIGN.md
2. ✅ Review and approve ARCHITECTURE.md
3. ✅ Review and approve IMPLEMENTATION_PLAN.md (this document)
4. 🚀 Begin Phase 1, Task 1.1

---

**Ready to implement!** 🎯
