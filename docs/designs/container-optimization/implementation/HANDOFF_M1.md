# Handoff: M1 - Dead Code & Dependency Cleanup

## Task 1.1 Complete: Archive Frontend

**What was done:**
- Moved `frontend/` → `archive/frontend/` using `git mv` (preserves history)
- Added `archive/` to `.dockerignore`

**Next Task Notes:**
- Task 1.2 deletes dead code including `ktrdr/visualization/`, empty directories, and duplicate Dockerfile
- Verify each target exists before deletion
