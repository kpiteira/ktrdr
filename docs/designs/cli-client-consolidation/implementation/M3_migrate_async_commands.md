---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 3: Migrate Async Commands

**Branch:** `feature/cli-client-consolidation-m3`
**Builds on:** M1
**Goal:** All commands using old `AsyncCLIClient` now use new `AsyncCLIClient`.

## E2E Test Scenario

```bash
# Verify async commands work
ktrdr agent status
ktrdr data show AAPL 1d
```

**Success Criteria:**
- [ ] Commands produce same output as before
- [ ] No imports from old `async_cli_client.py`

---

## Migration Pattern

```python
# Before
from ktrdr.cli.async_cli_client import AsyncCLIClient
async with AsyncCLIClient() as client:
    result = await client._make_request("GET", "/agent/status")

# After
from ktrdr.cli.client import AsyncCLIClient
async with AsyncCLIClient() as client:
    result = await client.get("/agent/status")
```

---

## Task 3.1: Migrate agent_commands.py

**File(s):** `ktrdr/cli/agent_commands.py`
**Type:** CODING
**Estimated time:** 1-2 hours
**Task Categories:** Cross-Component, Background/Async

**Description:**
Replace old `AsyncCLIClient` with new one following migration pattern above.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr agent status
ktrdr agent trigger  # if applicable
```

**Acceptance Criteria:**
- [ ] No imports from `async_cli_client.py`
- [ ] Uses new `AsyncCLIClient`
- [ ] Same output as before

---

## Task 3.2: Migrate async_data_commands.py

**File(s):** `ktrdr/cli/async_data_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component, Background/Async

**Description:**
Replace old `AsyncCLIClient` with new one.

**Acceptance Criteria:**
- [ ] No imports from `async_cli_client.py`
- [ ] Uses new `AsyncCLIClient`

---

## Task 3.3: Migrate data_commands.py (async parts)

**File(s):** `ktrdr/cli/data_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Migrate only async portions using `AsyncCLIClient`.

**Testing Requirements:**

*Smoke Test:*
```bash
ktrdr data show AAPL 1d
```

**Acceptance Criteria:**
- [ ] No imports from `async_cli_client.py`
- [ ] Uses new `AsyncCLIClient`

---

## Task 3.4: Migrate model_commands.py (non-operation parts)

**File(s):** `ktrdr/cli/model_commands.py`
**Type:** CODING
**Estimated time:** 1 hour
**Task Categories:** Cross-Component

**Description:**
Migrate async parts that do NOT use operation execution. Operation execution migrated in M4.

**Acceptance Criteria:**
- [ ] Async (non-operation) parts use new `AsyncCLIClient`
- [ ] Operation execution parts left for M4

---

## Completion Checklist

- [ ] All async commands migrated (except operation execution)
- [ ] No imports from `async_cli_client.py`
- [ ] All existing tests pass
- [ ] `make quality` passes
