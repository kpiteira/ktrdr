---
design: docs/architecture/checkpoint/DESIGN.md
architecture: docs/architecture/checkpoint/ARCHITECTURE.md
---

# Milestone 3: Training Checkpoint Save

**Branch:** `feature/checkpoint-m3-training-checkpoint-save`
**Depends On:** M1 (Operations Persistence)
**Estimated Tasks:** 9

---

## Capability

When M3 is complete:
- Training saves periodic checkpoints (every N epochs)
- Training saves checkpoint on cancellation (Ctrl+C)
- Training saves checkpoint on caught exceptions
- Checkpoints stored in DB (state) + filesystem (artifacts)
- Checkpoint includes model weights, optimizer state, training history

---

## E2E Test Scenario

```bash
#!/bin/bash
# M3 E2E Test: Training Checkpoint Save

set -e

echo "=== M3 E2E Test: Training Checkpoint Save ==="

# 1. Start training with checkpoint interval of 5 epochs
echo "Step 1: Start training..."
RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/training/start \
    -H "Content-Type: application/json" \
    -d '{
        "strategy_path": "strategies/test.yaml",
        "symbol": "EURUSD",
        "timeframe": "1h",
        "epochs": 20,
        "checkpoint_interval": 5
    }')
OP_ID=$(echo $RESPONSE | jq -r '.data.operation_id')
echo "Started operation: $OP_ID"

# 2. Wait for epoch 5+ (periodic checkpoint)
echo "Step 2: Waiting for periodic checkpoint..."
for i in {1..30}; do
    sleep 2
    PROGRESS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.progress_percent')
    echo "  Progress: $PROGRESS%"
    if (( $(echo "$PROGRESS > 25" | bc -l) )); then
        echo "Past epoch 5, checking for checkpoint..."
        break
    fi
done

# 3. Verify checkpoint exists
echo "Step 3: Verify checkpoint exists..."
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_EXISTS=$(echo $CHECKPOINT | jq -r '.success')
CP_EPOCH=$(echo $CHECKPOINT | jq -r '.data.state.epoch')

if [ "$CP_EXISTS" == "true" ]; then
    echo "OK: Checkpoint exists at epoch $CP_EPOCH"
else
    echo "FAIL: No checkpoint found"
    exit 1
fi

# 4. Verify artifacts on filesystem
echo "Step 4: Verify artifacts..."
ARTIFACTS_PATH=$(echo $CHECKPOINT | jq -r '.data.artifacts_path')
docker exec ktrdr-backend ls -la $ARTIFACTS_PATH

# 5. Cancel training
echo "Step 5: Cancel training..."
curl -s -X DELETE http://localhost:8000/api/v1/operations/$OP_ID/cancel

sleep 3

# 6. Verify cancellation checkpoint
echo "Step 6: Verify cancellation checkpoint..."
CHECKPOINT=$(curl -s http://localhost:8000/api/v1/checkpoints/$OP_ID)
CP_TYPE=$(echo $CHECKPOINT | jq -r '.data.checkpoint_type')

if [ "$CP_TYPE" == "cancellation" ]; then
    echo "OK: Cancellation checkpoint saved"
    echo ""
    echo "=== M3 E2E TEST PASSED ==="
else
    echo "FAIL: Expected checkpoint_type=cancellation, got $CP_TYPE"
    exit 1
fi
```

---

## Tasks

### Task 3.1: Create Checkpoints Database Table

**File(s):**
- `ktrdr/api/models/db/checkpoints.py` (new)
- `alembic/versions/xxx_create_checkpoints_table.py` (new)

**Type:** CODING

**Task Categories:** Persistence

**Description:**
Create the operation_checkpoints table for storing checkpoint metadata and state.

**Schema:**
```python
class CheckpointRecord(Base):
    __tablename__ = "operation_checkpoints"

    operation_id = Column(String(255), ForeignKey("operations.operation_id"), primary_key=True)
    checkpoint_type = Column(String(50), nullable=False)  # periodic, cancellation, failure, shutdown
    created_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    state = Column(JSONB, nullable=False)
    artifacts_path = Column(String(500), nullable=True)
    state_size_bytes = Column(Integer, nullable=True)
    artifacts_size_bytes = Column(BigInteger, nullable=True)
```

**Acceptance Criteria:**
- [ ] SQLAlchemy model defined
- [ ] Foreign key to operations table
- [ ] Alembic migration creates table
- [ ] Migration runs successfully
- [ ] Rollback works

**Integration Tests (based on categories):**
- [ ] **DB Verification:** Table exists after migration: `SELECT * FROM operation_checkpoints LIMIT 1`
- [ ] **DB Verification:** Foreign key constraint works (insert with invalid operation_id fails)

**Smoke Test:**
```bash
docker compose exec db psql -U ktrdr -d ktrdr -c "\\d operation_checkpoints"
```

---

### Task 3.2: Create CheckpointService

**File(s):**
- `ktrdr/checkpointing/checkpoint_service.py` (new)
- `tests/unit/checkpointing/test_checkpoint_service.py` (new)

**Type:** CODING

**Task Categories:** Persistence, Wiring/DI

**Description:**
Create the service for checkpoint CRUD operations (DB + filesystem).

**Implementation Notes:**
- UPSERT behavior (one checkpoint per operation)
- Atomic artifact writes (temp dir + rename)
- Best-effort cleanup on DB failure
- Load with optional artifact loading

**Key Methods:**
```python
class CheckpointService:
    async def save_checkpoint(
        self,
        operation_id: str,
        checkpoint_type: str,
        state: dict,
        artifacts: Optional[dict[str, bytes]] = None,
    ) -> None

    async def load_checkpoint(
        self,
        operation_id: str,
        load_artifacts: bool = True,
    ) -> Optional[CheckpointData]

    async def delete_checkpoint(self, operation_id: str) -> bool

    async def list_checkpoints(
        self,
        older_than_days: Optional[int] = None,
    ) -> list[CheckpointSummary]
```

**Acceptance Criteria:**
- [ ] Save writes artifacts atomically
- [ ] Save UPSERTs to DB
- [ ] Save cleans up artifacts on DB failure
- [ ] Load returns CheckpointData with state
- [ ] Load optionally loads artifacts from filesystem
- [ ] Delete removes both DB row and artifacts
- [ ] Unit tests with mocked DB and filesystem

**Integration Tests (based on categories):**
- [ ] **Wiring:** `assert get_checkpoint_service()._session_factory is not None`
- [ ] **DB Verification:** After save, query DB directly to verify row exists
- [ ] **DB Verification:** After delete, query DB directly to verify row removed
- [ ] **Filesystem:** After save, verify artifacts exist at expected path
- [ ] **Filesystem:** After delete, verify artifacts removed

**Smoke Test:**
```bash
# After saving a checkpoint:
docker compose exec db psql -U ktrdr -d ktrdr -c \
  "SELECT operation_id, checkpoint_type FROM operation_checkpoints LIMIT 5"
ls -la data/checkpoints/
```

---

### Task 3.3: Create CheckpointPolicy

**File(s):**
- `ktrdr/checkpointing/checkpoint_policy.py` (new)
- `tests/unit/checkpointing/test_checkpoint_policy.py` (new)

**Type:** CODING

**Description:**
Policy class that decides when to create checkpoints.

**Implementation Notes:**
- Unit-based trigger (every N epochs)
- Time-based trigger (every M seconds)
- Track last checkpoint for both

**Code:**
```python
class CheckpointPolicy:
    def __init__(
        self,
        unit_interval: int = 10,
        time_interval_seconds: int = 300,
    ):
        self._unit_interval = unit_interval
        self._time_interval = time_interval_seconds
        self._last_checkpoint_time: Optional[float] = None
        self._last_checkpoint_unit: int = 0

    def should_checkpoint(self, current_unit: int, force: bool = False) -> bool:
        if force:
            return True

        # Time-based
        now = time.time()
        if self._last_checkpoint_time:
            if now - self._last_checkpoint_time >= self._time_interval:
                return True

        # Unit-based
        if current_unit - self._last_checkpoint_unit >= self._unit_interval:
            return True

        return False

    def record_checkpoint(self, current_unit: int):
        self._last_checkpoint_time = time.time()
        self._last_checkpoint_unit = current_unit
```

**Acceptance Criteria:**
- [ ] Unit-based trigger works
- [ ] Time-based trigger works
- [ ] Force flag works
- [ ] Tracks last checkpoint correctly
- [ ] Unit tests cover all trigger conditions

---

### Task 3.4: Define Training Checkpoint State Shape

**File(s):**
- `ktrdr/checkpointing/schemas.py` (new)
- `ktrdr/training/checkpoint_builder.py` (new)

**Type:** CODING

**Description:**
Define the data structure for training checkpoint state and implement state extraction from trainer.

**State Shape:**
```python
@dataclass
class TrainingCheckpointState:
    # Resume point
    epoch: int

    # Progress metrics
    train_loss: float
    val_loss: float
    train_accuracy: Optional[float] = None
    val_accuracy: Optional[float] = None
    learning_rate: float = 0.001
    best_val_loss: float = float('inf')

    # History for plotting
    training_history: dict[str, list[float]] = field(default_factory=dict)

    # Original request for resume
    original_request: dict = field(default_factory=dict)
```

**Artifacts:**
```python
TRAINING_ARTIFACTS = {
    "model.pt": "required",
    "optimizer.pt": "required",
    "scheduler.pt": "optional",
    "best_model.pt": "optional",
}
```

**Acceptance Criteria:**
- [ ] State dataclass defined
- [ ] Artifact manifest defined
- [ ] Builder can extract state from ModelTrainer
- [ ] Builder can extract artifacts from ModelTrainer
- [ ] Validation for required vs optional artifacts

---

### Task 3.5: Integrate Checkpoint Save into Training Worker

**File(s):**
- `ktrdr/training/training_worker.py` (modify)
- `ktrdr/training/model_trainer.py` (modify if needed)

**Type:** CODING

**Task Categories:** Persistence, Cross-Component, Wiring/DI

**Description:**
Integrate checkpoint saving into the training worker for periodic and cancellation checkpoints.

**Implementation Notes:**
- Add CheckpointService and CheckpointPolicy to worker
- Call `maybe_checkpoint(epoch)` after each epoch
- Save checkpoint on cancellation before exiting
- Save checkpoint on caught exceptions

**Integration Points:**
```python
class TrainingWorker(WorkerAPIBase):
    def __init__(self, ...):
        super().__init__(...)
        self.checkpoint_service = CheckpointService(...)
        self.checkpoint_policy = CheckpointPolicy(
            unit_interval=config.checkpoint_epoch_interval,
            time_interval_seconds=config.checkpoint_time_interval,
        )

    async def _run_training(self, operation_id: str, request: TrainingRequest):
        try:
            trainer = ModelTrainer(...)

            for epoch in range(start_epoch, total_epochs):
                await trainer.train_epoch(epoch)

                # Periodic checkpoint
                if self.checkpoint_policy.should_checkpoint(epoch):
                    await self._save_training_checkpoint(operation_id, trainer, "periodic")
                    self.checkpoint_policy.record_checkpoint(epoch)

                # Check cancellation
                if self._cancellation_token.is_cancelled():
                    await self._save_training_checkpoint(operation_id, trainer, "cancellation")
                    raise CancellationError("Training cancelled")

            # Success - delete checkpoint
            await self.checkpoint_service.delete_checkpoint(operation_id)

        except CancellationError:
            raise  # Already saved checkpoint
        except Exception as e:
            # Failure checkpoint
            await self._save_training_checkpoint(operation_id, trainer, "failure")
            raise

    async def _save_training_checkpoint(self, operation_id: str, trainer: ModelTrainer, checkpoint_type: str):
        state = build_training_checkpoint_state(trainer)
        artifacts = build_training_checkpoint_artifacts(trainer)
        await self.checkpoint_service.save_checkpoint(
            operation_id, checkpoint_type, state.to_dict(), artifacts
        )
```

**Acceptance Criteria:**
- [ ] Periodic checkpoint saves every N epochs
- [ ] Cancellation checkpoint saves before exit
- [ ] Failure checkpoint saves on exception
- [ ] Checkpoint deleted on successful completion
- [ ] Integration with existing training flow

**Integration Tests (based on categories):**
- [ ] **Wiring:** `assert training_worker.checkpoint_service is not None`
- [ ] **Wiring:** `assert training_worker.checkpoint_policy is not None`
- [ ] **DB Verification:** After training reaches checkpoint epoch, query DB to verify checkpoint exists
- [ ] **Cross-Component:** Checkpoint state matches trainer state (epoch, loss values)

**Smoke Test:**
```bash
# Start training, wait for checkpoint interval, then:
docker compose exec db psql -U ktrdr -d ktrdr -c \
  "SELECT operation_id, checkpoint_type, state->>'epoch' as epoch FROM operation_checkpoints"
```

---

### Task 3.6: Add Checkpoint API Endpoints

**File(s):**
- `ktrdr/api/endpoints/checkpoints.py` (new)
- `ktrdr/api/main.py` (modify to register router)

**Type:** CODING

**Task Categories:** API Endpoint, Persistence

**Description:**
API endpoints for listing and viewing checkpoints.

**Endpoints:**
```python
@router.get("/checkpoints")
async def list_checkpoints(
    operation_id: Optional[str] = None,
    older_than_days: Optional[int] = None,
) -> CheckpointListResponse

@router.get("/checkpoints/{operation_id}")
async def get_checkpoint(operation_id: str) -> CheckpointResponse

@router.delete("/checkpoints/{operation_id}")
async def delete_checkpoint(operation_id: str) -> DeleteResponse
```

**Acceptance Criteria:**
- [ ] List endpoint with filters
- [ ] Get endpoint returns checkpoint details
- [ ] Delete endpoint removes checkpoint
- [ ] Proper error responses (404, etc.)

**Integration Tests (based on categories):**
- [ ] **API:** GET /checkpoints returns list
- [ ] **API:** GET /checkpoints/{id} returns checkpoint details
- [ ] **API:** GET /checkpoints/{id} returns 404 for non-existent
- [ ] **DB Verification:** After DELETE, verify row removed from DB

**Smoke Test:**
```bash
curl http://localhost:8000/api/v1/checkpoints | jq
curl http://localhost:8000/api/v1/checkpoints/<operation_id> | jq
```

---

### Task 3.7: Configuration for Checkpointing

**File(s):**
- `ktrdr/config/settings.py` (modify)
- Environment variables

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Make checkpoint intervals and paths configurable. The checkpoint directory must work across different deployment environments (local, homelab).

**Configuration:**
```python
# Environment variables
CHECKPOINT_EPOCH_INTERVAL=10
CHECKPOINT_TIME_INTERVAL_SECONDS=300
CHECKPOINT_DIR=${SHARED_MOUNT_PATH}/checkpoints  # Or /app/data/checkpoints as default
CHECKPOINT_MAX_AGE_DAYS=30
```

**Implementation Notes:**

- `CHECKPOINT_DIR` defaults to `/app/data/checkpoints` (works with local mounts)
- In homelab, set to `/mnt/ktrdr_data/checkpoints` (NFS share)
- CheckpointService reads this env var for artifact storage path
- All services using checkpoints must have RW access to this path

**Code:**

```python
# In CheckpointService.__init__
self._artifacts_dir = Path(os.getenv("CHECKPOINT_DIR", "/app/data/checkpoints"))
```

**Acceptance Criteria:**

- [ ] Epoch interval configurable
- [ ] Time interval configurable
- [ ] CHECKPOINT_DIR configurable via environment
- [ ] Max age configurable
- [ ] Sensible defaults
- [ ] Works with both local and NFS paths

**Integration Tests (based on categories):**
- [ ] **Config:** Defaults work when env vars not set
- [ ] **Config:** Custom CHECKPOINT_DIR is used when set

**Smoke Test:**
```bash
docker compose exec backend env | grep CHECKPOINT
```

---

### Task 3.8: Integration Test for Checkpoint Save

**File(s):**
- `tests/integration/test_m3_training_checkpoint_save.py` (new)

**Type:** CODING

**Description:**
Integration test that verifies checkpoint saving works.

**Test Scenarios:**
1. Start training, wait for periodic checkpoint
2. Verify checkpoint in DB with correct state
3. Verify artifacts on filesystem
4. Cancel training, verify cancellation checkpoint
5. Verify checkpoint type updated

**Acceptance Criteria:**

- [ ] Test verifies periodic checkpoint
- [ ] Test verifies cancellation checkpoint
- [ ] Test verifies DB state
- [ ] Test verifies filesystem artifacts
- [ ] Tests pass: `make test-integration`

---

### Task 3.9: Update Deployment Configurations

**File(s):**

- `deploy/environments/local/docker-compose.yml` (modify)
- `deploy/environments/homelab/docker-compose.core.yml` (modify)
- `deploy/environments/homelab/docker-compose.workers.yml` (modify)

**Type:** CODING

**Description:**
Update deployment configurations to support checkpoint storage across all environments.

**Changes Required:**

**Local Development** (`deploy/environments/local/docker-compose.yml`):

- Change worker data mounts from `:ro` to `:rw` (workers need to write checkpoints)
- Add `CHECKPOINT_DIR` environment variable

```yaml
# Workers need RW access for checkpoints
backtest-worker-1:
  volumes:
    - ./data:/app/data  # Changed from :ro to :rw (or no suffix)
  environment:
    - CHECKPOINT_DIR=/app/data/checkpoints

training-worker-1:
  volumes:
    - ./data:/app/data  # Already RW for model output
  environment:
    - CHECKPOINT_DIR=/app/data/checkpoints
```

**Homelab Core** (`deploy/environments/homelab/docker-compose.core.yml`):

- Add `CHECKPOINT_DIR` to backend environment

```yaml
backend:
  environment:
    - CHECKPOINT_DIR=/mnt/ktrdr_data/checkpoints
```

**Homelab Workers** (`deploy/environments/homelab/docker-compose.workers.yml`):

- Change backtest workers from `:ro` to `:rw` for NFS mount
- Add `CHECKPOINT_DIR` environment variable to all workers

```yaml
backtest-worker-1:
  volumes:
    - /mnt/ktrdr_data:/mnt/ktrdr_data:rw  # Changed from :ro
  environment:
    - CHECKPOINT_DIR=/mnt/ktrdr_data/checkpoints

training-worker-1:
  # Already has :rw
  environment:
    - CHECKPOINT_DIR=/mnt/ktrdr_data/checkpoints
```

**Acceptance Criteria:**

- [ ] Local workers have RW access to data directory
- [ ] All services have CHECKPOINT_DIR environment variable
- [ ] Homelab backtest workers changed to RW mount
- [ ] Local and homelab deployments both work
- [ ] Checkpoint directory created on first use

---

## Milestone 3 Verification Checklist

Before marking M3 complete:

- [ ] All 9 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] Integration tests pass: `make test-integration`
- [ ] E2E test script passes
- [ ] M1 and M2 E2E tests still pass
- [ ] Quality gates pass: `make quality`

---

## Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `ktrdr/api/models/db/checkpoints.py` | Create | 3.1 |
| `alembic/versions/xxx_create_checkpoints_table.py` | Create | 3.1 |
| `ktrdr/checkpointing/checkpoint_service.py` | Create | 3.2 |
| `ktrdr/checkpointing/checkpoint_policy.py` | Create | 3.3 |
| `ktrdr/checkpointing/schemas.py` | Create | 3.4 |
| `ktrdr/training/checkpoint_builder.py` | Create | 3.4 |
| `ktrdr/training/training_worker.py` | Modify | 3.5 |
| `ktrdr/api/endpoints/checkpoints.py` | Create | 3.6 |
| `ktrdr/api/main.py` | Modify | 3.6 |
| `ktrdr/config/settings.py` | Modify | 3.7 |
| `tests/unit/checkpointing/test_checkpoint_service.py` | Create | 3.2 |
| `tests/unit/checkpointing/test_checkpoint_policy.py` | Create | 3.3 |
| `tests/integration/test_m3_training_checkpoint_save.py` | Create | 3.8 |
| `deploy/environments/local/docker-compose.yml` | Modify | 3.9 |
| `deploy/environments/homelab/docker-compose.core.yml` | Modify | 3.9 |
| `deploy/environments/homelab/docker-compose.workers.yml` | Modify | 3.9 |
