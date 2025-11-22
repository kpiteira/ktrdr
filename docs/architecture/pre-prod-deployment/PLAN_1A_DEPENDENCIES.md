# Project 1a: Dependency Management & Dockerfile

**Status**: Ready for Implementation
**Estimated Effort**: Small
**Prerequisites**: None

**Branch:** harmonize_dependencies

---

## Goal

Clean, reproducible build system using uv exclusively for all dependency management.

---

## Context

The project currently has both `requirements.txt` and `uv.lock`, creating potential for dependency drift between development and production. The Dockerfile references `requirements.txt` and has outdated Python 3.11 paths that need updating to 3.13.

---

## Tasks

### Task 1.1: Audit Current Dependency Files

**Goal**: Understand current state and identify all files to update

**Actions**:

1. List all dependency-related files (`requirements*.txt`, `pyproject.toml`, `uv.lock`)
2. Check CI workflows for dependency installation commands
3. Check Dockerfile for dependency installation
4. Document any discrepancies between requirements.txt and uv.lock

**Acceptance Criteria**:

- [ ] Complete list of dependency files documented
- [ ] All pip/requirements.txt usages identified
- [ ] Discrepancies (if any) documented

---

### Task 1.2: Remove requirements.txt

**Goal**: Single source of truth for dependencies

**Actions**:

1. Verify `uv.lock` is current: `uv lock --check`
2. If not current, regenerate: `uv lock`
3. Delete `requirements.txt` (and any `requirements-*.txt` variants)
4. Update `.gitignore` if it references requirements files
5. Search codebase for any references to requirements.txt and update

**Acceptance Criteria**:

- [ ] `requirements.txt` deleted
- [ ] `uv.lock` is current and complete
- [ ] No remaining references to requirements.txt in codebase
- [ ] `uv sync` installs all dependencies correctly

---

### Task 1.3: Update Dockerfile for uv.lock

**File**: `docker/backend/Dockerfile`

**Actions**:

1. Replace requirements.txt COPY with uv.lock and pyproject.toml
2. Replace `pip install -r requirements.txt` with `uv sync --frozen --no-dev`
3. Fix Python version paths (3.11 → 3.13) in all COPY statements
4. Ensure uv is installed in builder stage
5. Test build locally

**Changes**:

```dockerfile
# OLD:
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# NEW:
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
```

```dockerfile
# OLD:
COPY --from=builder /usr/local/lib/python3.11/site-packages ...

# NEW:
COPY --from=builder /usr/local/lib/python3.13/site-packages ...
```

**Acceptance Criteria**:

- [ ] Dockerfile uses uv.lock for dependency installation
- [ ] All Python paths reference 3.13
- [ ] `docker build -f docker/backend/Dockerfile -t ktrdr-backend:test .` succeeds
- [ ] Built image runs and passes health check
- [ ] Image size reasonable (<500MB for runtime stage)

---

### Task 1.4: Update CI Workflows

**Goal**: Ensure CI uses uv consistently

**Actions**:

1. Review `.github/workflows/*.yml` for dependency installation
2. Replace any `pip install` with `uv sync` or `uv pip install`
3. Ensure uv is installed in CI environment
4. Test CI workflow runs

**Acceptance Criteria**:

- [ ] All CI workflows use uv for Python dependencies
- [ ] No pip install commands remain (except for uv itself)
- [ ] CI tests pass

---

### Task 1.5: Update Documentation

**Goal**: Reflect uv-only workflow in all docs

**Actions**:

1. Update CLAUDE.md if it references requirements.txt
2. Update any README sections about installation
3. Update contributing guidelines if they exist
4. Search for "requirements.txt" or "pip install" in docs and update

**Acceptance Criteria**:

- [ ] CLAUDE.md reflects uv-only workflow
- [ ] No documentation references requirements.txt for installation
- [ ] Developer setup instructions use uv commands

---

## Validation

**Final Verification**:

```bash
# 1. Verify uv.lock is authoritative
uv lock --check

# 2. Build Docker image
docker build -f docker/backend/Dockerfile -t ktrdr-backend:test .

# 3. Run image and check health
docker run --rm -p 8000:8000 \
  -e DB_HOST=localhost \
  -e DB_NAME=test \
  -e DB_USER=test \
  -e DB_PASSWORD=test \
  -e JWT_SECRET=testsecret123456789012345678901234 \
  ktrdr-backend:test &

sleep 5
curl http://localhost:8000/api/v1/health

# 4. Verify no requirements.txt references
grep -r "requirements.txt" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.md" .
```

---

## Success Criteria

- [ ] `requirements.txt` removed from repository
- [ ] Dockerfile builds successfully with uv.lock
- [ ] All CI workflows use uv
- [ ] Documentation updated
- [ ] No remaining references to requirements.txt

---

## Dependencies

**Depends on**: Nothing
**Blocks**: Project 1b (Local Dev Environment), Project 2 (CI/CD & GHCR)

---

## Notes

- This is foundational work that must complete before other projects
- Keep the change focused - don't refactor Dockerfile beyond dependency changes
- If uv.lock is significantly different from requirements.txt, investigate before deleting

---

**Next Project**: [Project 1b: Local Dev Environment](PLAN_1B_LOCAL_DEV.md)
