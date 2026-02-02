---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 1: Dead Code & Dependency Cleanup

**Goal:** Remove all dead code and unused dependencies, establishing a clean baseline.

**Branch:** `feature/container-optimization`

**Builds on:** Nothing (first milestone)

---

## E2E Validation

### Success Criteria

```bash
# All tests pass after cleanup
make test-unit && make quality

# Lock file regenerated successfully
uv lock --check
```

### Verification

- [ ] No import errors in test suite
- [ ] No missing module errors at runtime
- [ ] Lock file is valid and committed

---

## Task 1.1: Archive Frontend

**File(s):** `frontend/` → `archive/frontend/`
**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Configuration

**Description:**
Move the inactive frontend directory to archive for reference. This preserves the code while clearly marking it as inactive.

**Implementation Notes:**
- Use `git mv` to preserve history
- Update `.dockerignore` to exclude `archive/`

**Commands:**
```bash
mkdir -p archive
git mv frontend archive/frontend
```

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify move succeeded
ls archive/frontend/package.json && echo "SUCCESS"
ls frontend 2>/dev/null && echo "FAIL: frontend still exists" || echo "SUCCESS: frontend removed"
```

**Acceptance Criteria:**
- [ ] `frontend/` no longer exists in repo root
- [ ] `archive/frontend/` contains all frontend files
- [ ] Git history preserved for archived files

---

## Task 1.2: Delete Dead Code

**File(s):**
- Delete: `ktrdr/visualization/` (entire directory)
- Delete: `docker/backend/Dockerfile.dev` (duplicate)
- Delete: `research_agents/` (empty)
- Delete: `models/` (empty)
- Delete: `output/` (empty)

**Type:** CODING
**Estimated time:** 15 min

**Task Categories:** Configuration

**Description:**
Remove code and directories confirmed to have zero usage.

**Implementation Notes:**
- Visualization module: 0 imports found, only smoke test exists
- Dockerfile.dev duplicate: `deploy/docker/Dockerfile.dev` is the canonical version
- Empty directories serve no purpose

**Commands:**
```bash
rm -rf ktrdr/visualization
rm -rf docker/backend/Dockerfile.dev
rm -rf research_agents models output
```

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify deletions
ls ktrdr/visualization 2>/dev/null && echo "FAIL" || echo "SUCCESS: visualization deleted"
ls docker/backend/Dockerfile.dev 2>/dev/null && echo "FAIL" || echo "SUCCESS: duplicate dockerfile deleted"
```

**Acceptance Criteria:**
- [ ] `ktrdr/visualization/` does not exist
- [ ] `docker/backend/Dockerfile.dev` does not exist
- [ ] Empty directories removed
- [ ] No import errors when running tests

---

## Task 1.3: Remove Unused Dependencies

**File(s):** `pyproject.toml`
**Type:** CODING
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Remove dependencies confirmed to have zero imports in the codebase.

**Dependencies to remove:**
- `streamlit>=1.22.0` — 0 imports
- `plotly>=5.13.0` — 0 imports
- `redis>=6.2.0` — 0 imports
- `openai>=1.93.0` — 0 imports
- `aiohttp>=3.12.14` — redundant (httpx is standard)
- `requests>=2.32.4` — redundant (httpx is standard)

**Implementation Notes:**
- Remove from `[project.dependencies]` section
- Do NOT remove `httpx` — it's the standard HTTP client
- Do NOT touch `[dependency-groups]` section

**Testing Requirements:**

*Unit Tests:*
- Existing tests must pass after removal

*Smoke Test:*
```bash
# Verify dependencies removed from pyproject.toml
grep -E "streamlit|plotly|redis|openai|aiohttp|requests" pyproject.toml && echo "FAIL: deps still present" || echo "SUCCESS"
```

**Acceptance Criteria:**
- [ ] Six dependencies removed from pyproject.toml
- [ ] No grep matches for removed deps in pyproject.toml
- [ ] `uv lock` succeeds (Task 1.4)

---

## Task 1.4: Restructure Dependencies for ML Optional Group

**File(s):** `pyproject.toml`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Move ML dependencies to optional group, move ib_async to separate optional group.

**Changes:**
1. Move `torch>=2.7.1` from `[project.dependencies]` to `[project.optional-dependencies] ml`
2. Move `scikit-learn>=1.6.1` from `[project.dependencies]` to `[project.optional-dependencies] ml`
3. Move `ib_async>=2.1.0` from `[project.dependencies]` to `[project.optional-dependencies] ib`

**Target structure:**
```toml
[project.optional-dependencies]
ml = [
    "torch>=2.7.1",
    "scikit-learn>=1.6.1",
]
ib = [
    "ib_async>=2.1.0",
]
dev = [
    # existing dev deps
]
```

**Implementation Notes:**
- Keep existing `dev` optional group as-is
- The `ml` group will be used with `--extra ml` in worker Dockerfiles
- The `ib` group is only needed by ib-host-service (runs natively, not in containers)

**Testing Requirements:**

*Smoke Test:*
```bash
# Verify structure
grep -A3 '^\[project.optional-dependencies\]' pyproject.toml
grep 'torch' pyproject.toml | head -5
```

**Acceptance Criteria:**
- [ ] `torch` and `scikit-learn` in `[project.optional-dependencies] ml`
- [ ] `ib_async` in `[project.optional-dependencies] ib`
- [ ] Neither in main `[project.dependencies]`

---

## Task 1.5: Regenerate Lock File and Verify

**File(s):** `uv.lock`
**Type:** CODING
**Estimated time:** 10 min

**Task Categories:** Configuration

**Description:**
Regenerate the UV lock file after dependency changes and verify everything still works.

**Commands:**
```bash
uv lock
uv sync --extra ml  # Full install to verify
```

**Testing Requirements:**

*Unit Tests:*
```bash
make test-unit
make quality
```

*Smoke Test:*
```bash
# Verify lock file updated
uv lock --check && echo "SUCCESS: lock file valid"

# Verify ML deps installable
uv sync --extra ml
python -c "import torch; print('torch OK')"
python -c "import sklearn; print('sklearn OK')"
```

**Acceptance Criteria:**
- [ ] `uv lock` succeeds without errors
- [ ] `uv sync --extra ml` installs all dependencies
- [ ] `make test-unit` passes
- [ ] `make quality` passes
- [ ] All changes committed

---

## Milestone 1 Completion Checklist

- [ ] Task 1.1: Frontend archived
- [ ] Task 1.2: Dead code deleted
- [ ] Task 1.3: Unused dependencies removed
- [ ] Task 1.4: ML deps in optional group
- [ ] Task 1.5: Lock file regenerated and verified
- [ ] All unit tests pass: `make test-unit`
- [ ] Quality gates pass: `make quality`
- [ ] All changes committed with clear messages
- [ ] No regressions introduced
