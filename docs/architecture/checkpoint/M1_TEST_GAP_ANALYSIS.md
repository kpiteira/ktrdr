# M1 Test Gap Analysis

**Date:** 2025-12-22
**Issue Found:** Operations not persisting to database despite all unit tests passing

## Root Cause

The `get_operations_service()` factory function was never updated to inject the repository:
```python
# What was written:
_operations_service = OperationsService()  # No repository!

# What should have been:
repository = OperationsRepository(session_factory)
_operations_service = OperationsService(repository=repository)
```

## Why Tests Didn't Catch It

### Task 1.2 (Repository) Tests
- ✅ Tested repository CRUD with mocked session
- ❌ Never tested that repository is actually instantiated and used

### Task 1.3 (Service Refactor) Tests
- ✅ Tested service with mocked repository injected
- ❌ Never tested that `get_operations_service()` provides a real repository
- ❌ Never tested actual DB write path

### Task 1.11 (Integration Test) Tests
- ✅ Tests exist in `tests/integration/test_m1_operations_persistence.py`
- ❌ Tests mock or bypass actual DB verification
- ❌ No test that queries DB directly after API call

## Missing Tests Identified

### 1. Wiring Smoke Test (CRITICAL)
**Purpose:** Verify that factory functions properly wire dependencies
```python
def test_operations_service_has_repository():
    """Verify get_operations_service() injects repository."""
    service = get_operations_service()
    assert service._repository is not None
```

### 2. DB Write Verification Test (CRITICAL)
**Purpose:** Verify operations actually persist to PostgreSQL
```python
async def test_operation_persists_to_database():
    """Create operation via API, verify in DB directly."""
    # 1. Create operation via API
    response = await client.post("/api/v1/operations/...", ...)
    op_id = response.json()["operation_id"]

    # 2. Query DB directly (not through service)
    async with get_session() as session:
        result = await session.execute(
            select(OperationRecord).where(OperationRecord.operation_id == op_id)
        )
        record = result.scalar_one_or_none()

    # 3. Verify
    assert record is not None, "Operation not found in database!"
    assert record.status == "pending"
```

### 3. Restart Survival Test (E2E)
**Purpose:** Verify operations survive service restart
```python
async def test_operation_survives_restart():
    """Operations should persist across service restarts."""
    # 1. Create operation
    op_id = await create_test_operation()

    # 2. Clear in-memory state (simulate restart)
    _operations_service = None  # Reset singleton

    # 3. Get fresh service
    service = get_operations_service()

    # 4. Verify operation still retrievable
    op = await service.get_operation(op_id)
    assert op is not None, "Operation lost after restart!"
```

### 4. Service Initialization Logging Test
**Purpose:** Verify startup logs indicate DB persistence is enabled
```python
def test_startup_logs_persistence_mode(caplog):
    """Startup should log whether DB persistence is enabled."""
    get_operations_service()
    assert "database persistence" in caplog.text.lower()
```

### 5. Per-Task Smoke Tests

| Task | Missing Smoke Test |
|------|-------------------|
| 1.1 | Verify table exists: `SELECT * FROM operations LIMIT 1` |
| 1.2 | Verify repository can connect: `await repo.list()` returns empty list |
| 1.3 | **CRITICAL:** Verify service._repository is not None |
| 1.5 | Verify reconciliation updates DB, not just cache |
| 1.8 | Verify startup reconciliation queries real DB |
| 1.11 | Query DB directly, not just API responses |

## Test Strategy Recommendations

### After Each Persistence-Related Task
1. **30-second DB smoke test:**
   ```bash
   docker compose exec db psql -U ktrdr -d ktrdr -c "SELECT COUNT(*) FROM operations"
   ```

### For All Integration Tests
2. **Direct DB verification pattern:**
   ```python
   # After API call, ALWAYS verify DB state directly
   async with get_session() as session:
       result = await session.execute(select(OperationRecord))
       # Assert on DB state, not API response
   ```

### For Factory Functions
3. **Wiring verification:**
   ```python
   # Test that dependencies are actually injected
   service = get_operations_service()
   assert service._repository is not None
   assert isinstance(service._repository, OperationsRepository)
   ```

## Tests To Write Now

1. `tests/integration/test_persistence_wiring.py` - Factory wiring tests
2. `tests/integration/test_db_persistence.py` - Direct DB verification tests
3. `tests/e2e/test_m1_persistence.py` - Full E2E with actual DB queries

## Lessons Learned

1. **Unit tests with mocks don't test wiring** - Each component worked, but they weren't connected
2. **Integration tests must verify actual state** - Querying API responses tests the API, not the DB
3. **Factory functions are critical paths** - `get_*_service()` functions must be tested
4. **"It works locally" isn't verification** - Need automated tests that would fail in CI
