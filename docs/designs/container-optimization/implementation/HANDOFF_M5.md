# Handoff: M5 - CI/CD Updates

## Task 5.1 Complete: Update build-images.yml for Matrix Build

**What was done:**
- Updated workflow from single-image platform matrix to multi-image matrix build
- Changed from `IMAGE_NAME` to `IMAGE_BASE` env variable for multi-image naming
- Simplified from digest-based multi-arch (two jobs) to direct multi-platform build
- Added unit tests for workflow validation

**Key changes:**
- Matrix now iterates over images, not platforms
- Each matrix item specifies: image name, dockerfile path, platforms
- worker-gpu is amd64-only (no ARM GPUs in homelab)
- Cache scopes now per-image instead of per-platform

**Gotcha: YAML parses 'on' as boolean True**
When loading workflow YAML in tests, the `on:` key becomes Python `True` not string `"on"`.
Use `True in workflow or "on" in workflow` to check.

**Test file added:** `tests/unit/ci/test_build_images_workflow.py`
