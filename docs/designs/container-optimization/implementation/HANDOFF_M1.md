# Handoff: M1 - Dead Code & Dependency Cleanup

## Task 1.1 Complete: Archive Frontend

**What was done:**
- Moved `frontend/` → `archive/frontend/` using `git mv` (preserves history)
- Added `archive/` to `.dockerignore`

## Task 1.2 Complete: Delete Dead Code

**What was done:**
- Deleted `ktrdr/visualization/` module and all its tests (0 external imports)
- Deleted `docker/backend/Dockerfile.dev` (duplicate of `deploy/docker/Dockerfile.dev`)
- Deleted empty directories: `research_agents/`, `models/`, `output/`

**Gotcha:**
- Visualization had test files in multiple locations: `tests/unit/visualization/`, `tests/visualization/`, and `tests/integration/workflows/test_visualization_integration.py` — all needed removal

## Task 1.3 Complete: Remove Unused Dependencies

**What was done:**
- Removed 4 unused dependencies: streamlit, plotly, redis, openai

**Deviation from plan:**
- aiohttp and requests were NOT removed — they have actual imports
  - aiohttp: `ktrdr/data/components/data_fetcher.py` (async HTTP sessions)
  - requests: `ktrdr/training/production_error_handler.py` (webhook alerts)
- Migration to httpx deferred to future task

## Task 1.4 Complete: Restructure Dependencies for ML Optional Group

**What was done:**
- Created `[project.optional-dependencies] ml` with torch, scikit-learn
- Created `[project.optional-dependencies] ib` with ib_async
- Removed these from main `[project.dependencies]`

**Usage:**
- Full install: `uv sync --extra ml --extra ib`
- Backend only: `uv sync` (no extras)
- Workers: `uv sync --extra ml`

## Task 1.5 Complete: Regenerate Lock File and Verify

**What was done:**
- Regenerated `uv.lock` (removed 17 packages no longer needed as direct deps)
- Verified `uv sync --extra ml` succeeds
- Verified all 5128 unit tests pass
- Verified all quality checks pass

**Note:**
- Some removed packages (streamlit, plotly, etc.) still appear during sync as transitive dependencies of other packages — this is expected behavior

---

## Milestone 1 Complete

All 5 tasks completed. Ready for PR creation.

**Summary of changes:**
- Archived frontend to `archive/frontend/`
- Deleted visualization module and tests
- Removed 4 unused dependencies
- Restructured ML/IB deps to optional groups
- Lock file regenerated and verified
