# KDesign Command Improvements

**Date:** 2025-12-22
**Motivation:** M1 had all unit tests passing but operations didn't persist to DB because the factory function wasn't wiring the repository. The kdesign commands need improvements to prevent this class of bug.

---

## Problem Analysis

The existing kdesign commands are excellent at:
- ✅ Design and architecture documentation
- ✅ Scenario-based validation
- ✅ Vertical milestone structure
- ✅ E2E test scenarios per milestone
- ✅ Task-level acceptance criteria

But they miss:
- ❌ **Wiring verification tests** for factory functions / dependency injection
- ❌ **Direct persistence verification** (querying DB, not just API responses)
- ❌ **Per-task smoke tests** for quick manual verification
- ❌ **Integration test patterns** that catch "components work but aren't connected" bugs

---

## Proposed Improvements

### 1. Add "Test Categories" Section to `/kdesign-impl-plan`

**Current:** Tasks have generic "Tests" and "Acceptance Criteria"

**Proposed:** Add explicit test categories per task type:

```markdown
## Task Testing Requirements

### For Persistence Tasks (DB, Repository, Service)

Every task involving persistence MUST include:

1. **Wiring Test** (CRITICAL)
   - Verifies factory function injects dependencies
   - Example: `assert get_operations_service()._repository is not None`

2. **Persistence Verification Test**
   - Queries DB directly, not through service
   - Example: After `service.create()`, verify with `SELECT * FROM table`

3. **30-Second Smoke Test**
   - Manual command to verify DB state
   - Example: `docker compose exec db psql -U user -d db -c "SELECT * FROM table"`

### For Integration Tasks (Cross-Component)

Every task involving component integration MUST include:

1. **Wiring Test**
   - Verifies dependencies are connected

2. **End-to-End Path Test**
   - Traces full flow from entry point to final state
   - Verifies state at each layer, not just final response

### For API Tasks

1. **Response Test** (existing)
2. **State Verification Test** (NEW)
   - Query underlying storage directly
   - Don't trust API response alone
```

### 2. Add "Wiring Verification" Step to Task Template

**Current task template:**
```markdown
## Task N.M: [Title]

**File(s):** ...
**Tests:**
- Unit: ...
- What to test: ...

**Acceptance Criteria:**
- [ ] ...
```

**Proposed addition:**
```markdown
## Task N.M: [Title]

**File(s):** ...

**Dependency Wiring:** (NEW)
- This task creates: [service/repository/component]
- Factory function: `get_X_service()`
- Dependencies to inject: [list]
- Wiring test: `assert service._dependency is not None`

**Tests:**
- Unit: ...
- **Wiring: `test_X_service_has_dependencies()`** (NEW)
- **Persistence: `test_X_persists_to_db()`** (NEW for DB tasks)
- What to test: ...

**Smoke Test:** (NEW)
```bash
# Run after task completion:
docker compose exec db psql -U ktrdr -d ktrdr -c "SELECT * FROM table"
```

**Acceptance Criteria:**
- [ ] ...
- [ ] Wiring test passes (NEW)
- [ ] Smoke test shows expected DB state (NEW)
```

### 3. Add "Persistence Verification" to Milestone E2E Tests

**Current E2E test pattern:**
```bash
# Trigger operation
RESPONSE=$(curl -X POST ...)
OP_ID=$(echo $RESPONSE | jq -r '.operation_id')

# Verify via API
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.status')
```

**Proposed addition:**
```bash
# Trigger operation
RESPONSE=$(curl -X POST ...)
OP_ID=$(echo $RESPONSE | jq -r '.operation_id')

# Verify via API
STATUS=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.status')

# CRITICAL: Verify in DB directly (NEW)
DB_STATUS=$(docker compose exec -T db psql -U ktrdr -d ktrdr -t -c \
    "SELECT status FROM operations WHERE operation_id='$OP_ID'")
if [ "$DB_STATUS" != "$STATUS" ]; then
    echo "FAIL: API status ($STATUS) doesn't match DB status ($DB_STATUS)"
    echo "This indicates the persistence layer is not connected!"
    exit 1
fi
```

### 4. Add "Anti-Pattern Detection" to Consistency Check

**Current consistency check (Step 6):**
```markdown
## Consistency Verification

### Design → Plan Traceability
...

### Architecture → Plan Traceability
...

### Anti-Pattern Check
- [ ] No [anti-pattern 1]
```

**Proposed additions:**
```markdown
## Consistency Verification

### Persistence Anti-Pattern Check (NEW)

For each service that uses a repository:

| Service | Factory Function | Repository Injected? | Verification Test? |
|---------|------------------|---------------------|-------------------|
| OperationsService | get_operations_service() | ⬜ Check | ⬜ Check |

**Red Flags:**
- ❌ Service constructor accepts Optional[Repository] but factory doesn't provide one
- ❌ Integration tests mock the repository but no test uses real DB
- ❌ E2E tests only check API responses, not DB state

### Wiring Anti-Pattern Check (NEW)

For each factory function (get_X_service, get_X_repository):

| Factory | Returns | Dependencies | Test Exists? |
|---------|---------|--------------|--------------|
| get_operations_service | OperationsService | OperationsRepository | ⬜ Check |

**Red Flags:**
- ❌ Factory function creates service without injecting dependencies
- ❌ No unit test verifying dependencies are injected
- ❌ "It works locally" without automated verification
```

### 5. Add "Test Hierarchy" Section to `/kdesign-validate`

In the "Integration with ktask" section, add:

```markdown
## Test Hierarchy for Validated Scenarios

Each validated scenario should have tests at three levels:

### Level 1: Wiring (Fast, Always Run)
- Verify dependencies are connected
- Run in CI on every commit
- Example: `def test_service_has_repository()`

### Level 2: Persistence (Requires DB, Run in CI)
- Verify operations actually persist
- Query DB directly, not through API
- Example: `async def test_operation_persists_to_db()`

### Level 3: E2E (Full Stack, Run Before Merge)
- Verify complete user flow
- Include DB verification step
- Example: The E2E bash script in milestone docs
```

---

## Implementation

### Files to Modify

1. `.claude/commands/kdesign-impl-plan.md`
   - Add test categories section
   - Modify task template
   - Add persistence verification to E2E pattern
   - Expand consistency check

2. `.claude/commands/kdesign-validate.md`
   - Add test hierarchy section
   - Add wiring verification to gap analysis categories

3. `.claude/commands/kdesign.md`
   - Add mention of test requirements in architecture section

### Backward Compatibility

These are additions, not changes. Existing milestone plans remain valid but may benefit from adding:
- Wiring tests for factory functions
- Persistence verification tests
- Smoke test commands

---

## Summary

The key insight from the M1 bug:

> **Unit tests with mocks verify component behavior, not wiring.**

Every persistence-related task needs three things:
1. **Wiring test:** Verify factory function injects dependencies
2. **Persistence test:** Query DB directly after operations
3. **Smoke test:** Quick manual verification command

Adding these to the kdesign templates will prevent future "it passes tests but doesn't actually work" bugs.
