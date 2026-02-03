---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5b: CI/CD Verification

**Goal:** Verify that the CI/CD changes from M5 work correctly in production.

**Branch:** `main` (run after M5 is merged)

**Builds on:** M5 (workflow updated, PR merged)

**Prerequisites:** M5 must be merged to main and CI workflow must have completed.

---

## Task 5b.1: Verify CI Workflow Execution

**File(s):** None (verification task)
**Type:** VALIDATION
**Estimated time:** 10 min

**Task Categories:** External, Verification

**Description:**
Verify that the GitHub Actions workflow ran successfully after merge.

**Steps:**

1. Go to GitHub Actions tab for the repository
2. Find the "Build and Push Images" workflow run triggered by the M5 merge
3. Verify all three matrix jobs completed successfully:
   - `build (backend)`
   - `build (worker-cpu)`
   - `build (worker-gpu)`
4. Check job logs for any warnings or issues

**Acceptance Criteria:**
- [ ] CI workflow triggered on merge
- [ ] All three matrix jobs passed
- [ ] No errors in job logs
- [ ] Build times reasonable (backend < 10min, workers < 20min)

---

## Task 5b.2: Verify Images in Registry

**File(s):** None (verification task)
**Type:** VALIDATION
**Estimated time:** 15 min

**Task Categories:** External, Verification

**Description:**
Verify that all three images are available in ghcr.io with correct tags and multi-arch support.

**Verification commands:**

```bash
# Pull all three images
docker pull ghcr.io/kpiteira/ktrdr-backend:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-cpu:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-gpu:latest

# Check image sizes (expected: backend ~500MB, workers ~1.3GB+)
docker images | grep ghcr.io/kpiteira/ktrdr

# Verify multi-arch manifests for backend and worker-cpu
docker manifest inspect ghcr.io/kpiteira/ktrdr-backend:latest | jq '.manifests[].platform'
docker manifest inspect ghcr.io/kpiteira/ktrdr-worker-cpu:latest | jq '.manifests[].platform'

# Verify worker-gpu is amd64 only
docker manifest inspect ghcr.io/kpiteira/ktrdr-worker-gpu:latest | jq '.manifests[].platform'

# Verify sha-xxx tags exist (replace with actual SHA from merge commit)
# docker pull ghcr.io/kpiteira/ktrdr-backend:sha-xxxxxxx
```

**Expected results:**

| Image | Multi-arch | Platforms | Approx Size |
|-------|------------|-----------|-------------|
| ktrdr-backend | Yes | linux/amd64, linux/arm64 | ~500MB |
| ktrdr-worker-cpu | Yes | linux/amd64, linux/arm64 | ~1.3GB |
| ktrdr-worker-gpu | No | linux/amd64 | ~2GB+ |

**Acceptance Criteria:**
- [ ] All three images pullable from ghcr.io
- [ ] Backend has amd64 + arm64 manifests
- [ ] Worker-cpu has amd64 + arm64 manifests
- [ ] Worker-gpu has amd64 only (as designed)
- [ ] Both `latest` and `sha-xxx` tags present
- [ ] Image sizes match expectations

---

## Task 5b.3: Smoke Test Images Locally

**File(s):** None (verification task)
**Type:** VALIDATION
**Estimated time:** 10 min

**Task Categories:** Integration, Verification

**Description:**
Quick smoke test to verify the registry images work correctly.

**Verification commands:**

```bash
# Test backend image
docker run --rm ghcr.io/kpiteira/ktrdr-backend:latest python -c "import ktrdr; print(f'ktrdr {ktrdr.__version__}')"

# Verify backend has NO torch
docker run --rm ghcr.io/kpiteira/ktrdr-backend:latest python -c "import torch" 2>&1 | grep -q "ModuleNotFoundError" && echo "✅ Backend correctly has no torch"

# Test worker-cpu image has torch
docker run --rm ghcr.io/kpiteira/ktrdr-worker-cpu:latest python -c "import torch; print(f'torch {torch.__version__}')"

# Test worker-gpu image has torch (if on amd64)
# docker run --rm ghcr.io/kpiteira/ktrdr-worker-gpu:latest python -c "import torch; print(f'torch {torch.__version__}')"
```

**Acceptance Criteria:**
- [ ] Backend image runs and imports ktrdr
- [ ] Backend image does NOT have torch
- [ ] Worker-cpu image has torch installed
- [ ] Images match M4 canary validation behavior

---

## Milestone 5b Completion Checklist

- [ ] Task 5b.1: CI workflow verified
- [ ] Task 5b.2: Registry images verified
- [ ] Task 5b.3: Local smoke test passed
- [ ] Container optimization complete end-to-end
- [ ] Ready for M6 (environment rollout)

---

## Rollback Plan

If verification fails:

1. **CI failed:** Check workflow logs, fix Dockerfile or workflow, push fix to main
2. **Images missing:** Re-run workflow via `workflow_dispatch`
3. **Multi-arch broken:** Check buildx configuration in workflow
4. **Images don't work:** Revert to previous workflow, investigate locally

Previous working workflow is in git history if needed:
```bash
git show HEAD~3:.github/workflows/build-images.yml  # Before M5 changes
```
