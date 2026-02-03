# Handoff: M3 - Split Dockerfiles

## Task 3.1 Complete: Create Dockerfile.backend (Production)

**What was done:**
- Created `deploy/docker/Dockerfile.backend` with multi-stage build
- No `--extra ml` flag — excludes torch and sklearn
- User created BEFORE `COPY --chown` commands (layer optimization)

**Gotcha: README.md required**
The pyproject.toml references `readme = "README.md"`. Must copy README.md to builder stage or hatchling fails during `uv sync --frozen --no-dev`.

**Image size note:**
Target was ~200-300MB, actual is 534MB. This is WITHOUT torch — the size comes from FastAPI dependency tree (pydantic, SQLAlchemy, alembic, httpx, etc.). The main goal of excluding ML deps (~2.8GB of torch) is achieved.

**Verification:**
```bash
docker build -f deploy/docker/Dockerfile.backend -t ktrdr-backend:prod .
docker images ktrdr-backend:prod --format "{{.Size}}"  # 534MB
docker run --rm ktrdr-backend:prod python -c "import torch"  # Fails with ModuleNotFoundError
```

**Next Task Notes:**
Task 3.2 creates Dockerfile.worker-cpu which DOES need torch but CPU-only version. Key technique: inject CPU PyTorch source before `uv sync`.

## Task 3.2 Complete: Create Dockerfile.worker-cpu

**What was done:**
- Created `deploy/docker/Dockerfile.worker-cpu` with CPU-only torch
- Injects `[tool.uv.sources]` for pytorch-cpu before `uv sync --extra ml`
- Verified torch 2.8.0+cpu is installed

**Image size note:**
Target was ~500MB, actual is 1.35GB. CPU torch itself is ~700-800MB. Still much smaller than CUDA version (~3.3GB).

**Verification:**
```bash
docker build -f deploy/docker/Dockerfile.worker-cpu -t ktrdr-worker-cpu:test .
docker images ktrdr-worker-cpu:test --format "{{.Size}}"  # 1.35GB
docker run --rm ktrdr-worker-cpu:test python -c "import torch; print(f'torch={torch.__version__}, cuda={torch.cuda.is_available()}')"
# Output: torch=2.8.0+cpu, cuda=False
```

**Next Task Notes:**
Task 3.3 renames existing `Dockerfile` to `Dockerfile.worker-gpu` and updates header comments.

## Task 3.3 Complete: Rename/Create Dockerfile.worker-gpu

**What was done:**
- Renamed `Dockerfile` to `Dockerfile.worker-gpu`
- Updated header comments to indicate CUDA 12.6 support
- Added `--extra ml` to uv sync commands
- Changed CMD to training worker (port 5002)
- Added CUDA source injection (cu126)

**Gotcha: Lockfile determines torch variant**
The `--frozen` flag uses the existing lockfile which has CPU torch. To get CUDA torch:
1. Regenerate uv.lock with CUDA source in pyproject.toml, OR
2. Remove --frozen flag (risks version drift)

Current image builds with CPU torch due to lockfile. This is documented in Dockerfile header.

**Next Task Notes:**
Task 3.4 updates Dockerfile.dev to use CPU-only torch (same pattern as worker-cpu).

## Task 3.4 Complete: Update Dockerfile.dev for CPU-Only Torch

**What was done:**
- Added CPU-only PyTorch source injection to Dockerfile.dev
- Updated header comment to note CPU-only torch

**Verification:**
```bash
docker build -f deploy/docker/Dockerfile.dev -t ktrdr-backend:dev .
docker run --rm ktrdr-backend:dev /app/.venv/bin/python -c "import torch; print(torch.__version__)"
# Output: 2.8.0+cpu
```

**Note on image size:**
Dev image is 3.26GB (larger than expected) because:
1. Single-stage build (optimized for quick rebuilds with volume mounts)
2. Layer duplication from chown after uv sync

The key win is torch 2.8.0+cpu is installed instead of CUDA torch.

**Next Task Notes:**
Task 3.5 adds `archive/` to .dockerignore.

## Task 3.5 Complete: Update .dockerignore

**What was done:**
- Verified `archive/` is already in `.dockerignore` (line 44)
- No changes needed

The task was already complete from previous work.

---

## E2E Validation Complete

**Tests executed:**
1. `infra/backend-lazy-imports` - ✅ PASSED (validates code-level lazy imports)
2. `infra/image-torch-availability` - ✅ PASSED (validates image-level torch config)

**Issues found and fixed during E2E:**

1. **Dockerfile.dev PATH issue**
   - Problem: `python` command used system python, not venv
   - Fix: Added `PATH="/app/.venv/bin:$PATH"` to ENV

2. **Dockerfile.worker-gpu CUDA torch overwritten**
   - Problem: Final `uv sync --frozen` re-installed CPU torch after CUDA install
   - Fix: Moved `uv pip install torch --index-url cu126` to AFTER final uv sync

**Final image validation:**

| Image | Size | Torch Version | CUDA |
|-------|------|---------------|------|
| ktrdr-backend:prod | 534MB | None | N/A |
| ktrdr-backend:dev | 3.26GB | 2.8.0+cpu | No |
| ktrdr-worker-cpu:test | 1.35GB | 2.8.0+cpu | No |
| ktrdr-worker-gpu:test | 9.19GB | 2.10.0+cu126 | 12.6 |
