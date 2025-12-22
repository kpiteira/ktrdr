# Milestone Test Requirements

**Purpose:** Define mandatory smoke/integration tests for each milestone to catch wiring and persistence bugs early.

**Lesson Learned:** M1 had all unit tests passing but operations didn't persist to DB because the factory function wasn't wiring up the repository. Tests need to verify actual behavior, not just component correctness.

---

## Testing Principles

### 1. Wiring Tests (Per Service)
Every service with injected dependencies needs a test verifying:
```python
def test_service_has_dependencies_injected():
    service = get_service()
    assert service._dependency is not None
```

### 2. Persistence Verification Tests (Per DB Operation)
Every operation that writes to DB needs a test that queries DB directly:
```python
async def test_operation_persists_to_db(db_session):
    # Do operation via service
    await service.create_thing(...)

    # Query DB directly (NOT via service)
    result = await db_session.execute(select(ThingRecord))
    assert result.scalar_one_or_none() is not None
```

### 3. Smoke Tests (Per Task)
Quick 30-second manual verification after implementing each task:
```bash
# Example for persistence tasks
docker compose exec db psql -U ktrdr -d ktrdr -c "SELECT * FROM table_name"
```

---

## M1: Operations Persistence

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 1.1 DB Table | `SELECT * FROM operations LIMIT 1` succeeds | Smoke |
| 1.2 Repository | Repository connects to DB | Integration |
| 1.3 Service | **`get_operations_service()._repository is not None`** | Wiring |
| 1.3 Service | Create operation, query DB directly | Persistence |
| 1.5 Reconciliation | Reconciliation updates DB, not just cache | Persistence |
| 1.8 Startup | Startup queries real DB | Integration |
| 1.11 Integration | **Query DB after API calls, not just API responses** | E2E |

### Critical M1 Tests (Would Have Caught Bug)
```python
# tests/integration/test_persistence_wiring.py
def test_operations_service_has_repository():
    service = get_operations_service()
    assert service._repository is not None

# tests/integration/test_db_persistence.py
async def test_operation_persists_to_db(db_session):
    service = get_operations_service()
    await service.create_operation(...)

    # Query DB directly
    result = await db_session.execute(select(OperationRecord))
    assert result.scalar_one_or_none() is not None
```

---

## M2: Orphan Detection

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 2.1 Detector | Detector service has operations_service injected | Wiring |
| 2.1 Detector | Detector queries DB for orphans | Integration |
| 2.2 Background Task | Task actually starts on backend startup | Smoke |
| 2.3 Timeout | Orphan marked FAILED in DB after timeout | Persistence |
| 2.4 PENDING_RECONCILIATION | State changes persist to DB | Persistence |
| 2.5 Integration | Full flow with DB verification | E2E |

### Critical M2 Tests
```python
def test_orphan_detector_has_operations_service():
    detector = OrphanDetector()
    assert detector._operations_service is not None

async def test_orphan_marked_failed_in_db(db_session):
    # Create orphan operation
    # Trigger detection
    # Query DB directly to verify FAILED status
```

---

## M3: Training Checkpoint Save

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 3.1 DB Schema | Checkpoints table exists | Smoke |
| 3.2 Repository | Repository CRUD works with real DB | Integration |
| 3.3 Service | Service has repository injected | Wiring |
| 3.4 Periodic Save | Checkpoint row exists in DB after save | Persistence |
| 3.5 Artifacts | Files exist on filesystem | Smoke |
| 3.6 Cancellation | Checkpoint saved on cancel, in DB | Persistence |
| 3.7 Exception | Checkpoint saved on exception, in DB | Persistence |
| 3.8 Worker Integration | Worker calls checkpoint service | Integration |
| 3.9 Integration | Full flow with DB + filesystem verification | E2E |

### Critical M3 Tests
```python
def test_checkpoint_service_has_repository():
    service = get_checkpoint_service()
    assert service._repository is not None

async def test_checkpoint_persists_to_db(db_session):
    # Trigger checkpoint save
    # Query checkpoints table directly
```

---

## M4: Training Resume

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 4.1 Checkpoint Load | Load from DB returns correct state | Integration |
| 4.2 Artifacts Load | Load files from filesystem | Integration |
| 4.3 Resume API | Resume operation loads checkpoint from DB | Integration |
| 4.4 Worker Integration | Worker receives and uses checkpoint | Integration |
| 4.5 Integration | Full resume flow with DB verification | E2E |

---

## M5: Backtesting Checkpoint

Same pattern as M3/M4 for backtesting-specific functionality.

---

## M6: Graceful Shutdown

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 6.1 Signal Handler | Handler registered and callable | Unit |
| 6.2 Checkpoint on Shutdown | Checkpoint saved to DB on SIGTERM | Persistence |
| 6.3 Worker Drain | Operations marked appropriately in DB | Persistence |
| 6.4 Integration | Full shutdown with DB verification | E2E |

---

## M7: Backend-Local Operations

| Task | Required Test | Test Type |
|------|--------------|-----------|
| 7.1 Checkpoint Support | Backend-local ops save checkpoints to DB | Persistence |
| 7.2 Resume | Backend-local ops resume from DB checkpoint | Integration |
| 7.3 Integration | Full flow with DB verification | E2E |

---

## M8: Polish

Focus on observability and monitoring - less critical for persistence testing.

---

## Implementation Checklist

For each milestone task involving persistence:

- [ ] Write wiring test before implementation
- [ ] Write persistence test before implementation (TDD)
- [ ] Run 30-second smoke test after implementation
- [ ] Run integration test suite after implementation
- [ ] Query DB directly to verify (not just API responses)

## Test Categories in CI

```yaml
# .github/workflows/ci.yml
test-wiring:
  # Fast tests that verify dependency injection
  # Run on every PR

test-persistence:
  # Tests that verify actual DB writes
  # Require DB_HOST environment
  # Run on every PR (with service containers)

test-e2e:
  # Full end-to-end tests
  # Require full docker-compose stack
  # Run on main branch and releases
```
