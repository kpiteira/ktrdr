---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 2: Migrate Sync Commands

**Branch:** `feature/cli-client-consolidation-m2`
**Builds on:** M1
**Goal:** All commands using `KtrdrApiClient` now use `SyncCLIClient`.

## E2E Test Scenario

```bash
# Verify commands work with new client
ktrdr indicators list
ktrdr checkpoints list
ktrdr strategy list
ktrdr ib status
ktrdr operations list

# Verify --url override works
ktrdr indicators list --url http://localhost:8000
```

**Success Criteria:**
- [ ] All commands produce same output as before
- [ ] --url override works
- [ ] No imports from old `api_client.py`

---

## Migration Pattern

```python
# Before
api_client = get_api_client()
result = api_client.get_request("/indicators")

# After
from ktrdr.cli.client import SyncCLIClient

with SyncCLIClient() as client:
    result = client.get("/indicators")
```

---

## Task 2.1: Migrate indicator_commands.py

**File(s):** `ktrdr/cli/indicator_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient` following migration pattern above.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr indicators list
ktrdr indicators list --url http://localhost:8000
```

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`
- [ ] Same output as before

---

## Task 2.2: Migrate checkpoints_commands.py

**File(s):** `ktrdr/cli/checkpoints_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient`.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr checkpoints list
```

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`

---

## Task 2.3: Migrate strategy_commands.py

**File(s):** `ktrdr/cli/strategy_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient`.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr strategy list
```

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`

---

## Task 2.4: Migrate ib_commands.py

**File(s):** `ktrdr/cli/ib_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component, External

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient`. IB diagnostics should still work via core module.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr ib status
# If IB disconnected, verify diagnostic message appears
```

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`
- [ ] IB diagnostics still work

---

## Task 2.5: Migrate fuzzy_commands.py

**File(s):** `ktrdr/cli/fuzzy_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient`.

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`

---

## Task 2.6: Migrate operations_commands.py

**File(s):** `ktrdr/cli/operations_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Replace `KtrdrApiClient` usage with `SyncCLIClient`.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr operations list
```

**Acceptance Criteria:**
- [ ] No imports from `api_client.py`
- [ ] Uses `SyncCLIClient`

---

## Completion Checklist

- [ ] All sync commands migrated
- [ ] No imports from `api_client.py` in migrated files
- [ ] All existing tests pass
- [ ] Manual verification of each command
- [ ] `make quality` passes
