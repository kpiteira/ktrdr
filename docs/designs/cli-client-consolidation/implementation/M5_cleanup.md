---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Cleanup

**Branch:** `feature/cli-client-consolidation-m5`
**Builds on:** M2, M3, M4
**Goal:** Old client code deleted. Single source of truth.

## E2E Test Scenario

```bash
# Verify no references to old clients
grep -r "from ktrdr.cli.async_cli_client" ktrdr/
grep -r "from ktrdr.cli.api_client" ktrdr/
grep -r "from ktrdr.cli.operation_executor" ktrdr/

# Should return nothing

# Verify all tests pass
make test-unit
make quality
```

**Success Criteria:**
- [ ] Old files deleted
- [ ] No references remain
- [ ] All tests pass

---

## Task 5.1: Delete async_cli_client.py

**File(s):** `ktrdr/cli/async_cli_client.py`
**Type:** CODING
**Estimated time:** 30 minutes
**Task Categories:** -

**Description:**
Delete the old async CLI client file.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.async_cli_client" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] No imports remain

---

## Task 5.2: Delete api_client.py

**File(s):** `ktrdr/cli/api_client.py`
**Type:** CODING
**Estimated time:** 30 minutes
**Task Categories:** -

**Description:**
Delete the old sync API client file. Also remove `get_api_client()` helper if it exists elsewhere.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.api_client" ktrdr/
grep -r "get_api_client" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] `get_api_client()` removed if exists
- [ ] No imports remain

---

## Task 5.3: Delete operation_executor.py

**File(s):** `ktrdr/cli/operation_executor.py`
**Type:** CODING
**Estimated time:** 30 minutes
**Task Categories:** -

**Description:**
Delete the old operation executor file.

**Pre-check:**
```bash
grep -r "from ktrdr.cli.operation_executor" ktrdr/
# Should return nothing
```

**Acceptance Criteria:**
- [ ] File deleted
- [ ] No imports remain

---

## Completion Checklist

- [ ] All old client files deleted
- [ ] `make test-unit` passes
- [ ] `make quality` passes
- [ ] Grep finds no references to deleted files
- [ ] All CLI commands still work

---

## Success Criteria (Overall Project)

1. ✅ Single `ktrdr/cli/client/` module handles all CLI HTTP needs
2. ✅ All existing CLI tests pass
3. ✅ No user-facing behavior changes
4. ✅ ~500-700 lines of code removed
5. ✅ URL handling in exactly one place
