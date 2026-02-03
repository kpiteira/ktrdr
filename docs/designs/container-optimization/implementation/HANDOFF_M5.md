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

## Task 5.2 Complete: Test Workflow Locally (Optional)

**What was done:**
- Verified buildx available (v0.30.1)
- Confirmed all three Dockerfiles exist and pass syntax validation
- Skipped full multi-arch build (M4 already validated images work)

**Rationale for skipping full build:**
- M4 validated images build and run correctly
- Task 5.1 unit tests verified workflow structure
- Full multi-arch build takes 15-30+ minutes
- This task is explicitly marked "optional"

## Task 5.3: Push and Verify CI Build (External Validation)

**What was done:**
- Confirmed all changes committed (2 commits ahead of main)
- Documented verification steps for post-push validation

**This is an external system validation** that requires:
1. Pushing to GitHub (or merging PR)
2. Observing GitHub Actions workflow
3. Verifying ghcr.io images

**Post-Push Verification Steps:**

1. **Monitor CI:**
   - Go to GitHub Actions tab
   - Watch "Build and Push Images" workflow
   - Verify all three matrix jobs complete (backend, worker-cpu, worker-gpu)

2. **Verify images in registry:**
   ```bash
   # Pull and inspect
   docker pull ghcr.io/kpiteira/ktrdr-backend:latest
   docker pull ghcr.io/kpiteira/ktrdr-worker-cpu:latest
   docker pull ghcr.io/kpiteira/ktrdr-worker-gpu:latest

   # Check sizes
   docker images | grep ghcr.io/kpiteira/ktrdr

   # Verify multi-arch (backend and worker-cpu)
   docker manifest inspect ghcr.io/kpiteira/ktrdr-backend:latest | grep architecture
   docker manifest inspect ghcr.io/kpiteira/ktrdr-worker-cpu:latest | grep architecture
   ```

**Acceptance Criteria (to be validated after CI):**
- [ ] CI workflow triggered
- [ ] All three matrix jobs pass
- [ ] Images available in ghcr.io
- [ ] Backend and worker-cpu have multi-arch manifests (amd64 + arm64)
- [ ] Image tags correct (sha-xxx + latest)
