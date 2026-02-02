---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: CI/CD Updates

**Goal:** Update GitHub Actions to build and push all three images to ghcr.io.

**Branch:** `feature/container-optimization`

**Builds on:** M4 (canary validation passed — images work correctly)

---

## E2E Validation

### Success Criteria

After pushing to main:
1. GitHub Actions workflow runs
2. Three images built: backend, worker-cpu, worker-gpu
3. All images pushed to ghcr.io
4. Multi-arch manifests created (amd64 + arm64 for backend/worker-cpu)

### Verification

```bash
# After CI completes, verify images in registry
docker pull ghcr.io/kpiteira/ktrdr-backend:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-cpu:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-gpu:latest

# Check multi-arch
docker manifest inspect ghcr.io/kpiteira/ktrdr-backend:latest
```

---

## Task 5.1: Update build-images.yml for Matrix Build

**File(s):** `.github/workflows/build-images.yml`
**Type:** CODING
**Estimated time:** 45 min

**Task Categories:** Configuration

**Description:**
Update the CI workflow to build three images instead of one.

**Current structure:**
- Single image: `ktrdr-backend`
- Single Dockerfile: `deploy/docker/Dockerfile`

**Target structure:**
- Three images: `ktrdr-backend`, `ktrdr-worker-cpu`, `ktrdr-worker-gpu`
- Three Dockerfiles (from M3)
- Matrix build for efficiency

**Key changes:**

```yaml
name: Build and Push Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_BASE: ${{ github.repository_owner }}/ktrdr

jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        include:
          - image: backend
            dockerfile: deploy/docker/Dockerfile.backend
            platforms: linux/amd64,linux/arm64
          - image: worker-cpu
            dockerfile: deploy/docker/Dockerfile.worker-cpu
            platforms: linux/amd64,linux/arm64
          - image: worker-gpu
            dockerfile: deploy/docker/Dockerfile.worker-gpu
            platforms: linux/amd64  # No ARM GPUs in homelab

    steps:
      - uses: actions/checkout@v4

      - name: Free disk space
        run: |
          sudo rm -rf /usr/share/dotnet
          sudo rm -rf /opt/ghc
          sudo rm -rf /usr/local/share/boost

      - name: Set up QEMU
        uses: docker/setup-qemu-action@v3

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to ghcr.io
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_BASE }}-${{ matrix.image }}
          tags: |
            type=sha,prefix=sha-,format=short
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ${{ matrix.dockerfile }}
          platforms: ${{ matrix.platforms }}
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha,scope=${{ matrix.image }}
          cache-to: type=gha,mode=max,scope=${{ matrix.image }}
```

**Implementation Notes:**
- Keep decision: always build all images (no path filtering)
- Separate cache scope per image type
- worker-gpu is amd64-only (no ARM GPUs)
- Use same tagging strategy: `sha-xxxxx` + `latest`

**Testing Requirements:**

*Smoke Test (local validation):*
```bash
# Validate workflow syntax
cat .github/workflows/build-images.yml | python -c "import sys,yaml; yaml.safe_load(sys.stdin); print('Valid YAML')"

# Check matrix structure
grep -A20 "matrix:" .github/workflows/build-images.yml
```

**Acceptance Criteria:**
- [ ] Workflow file updated
- [ ] Matrix includes all three images
- [ ] Correct Dockerfile paths specified
- [ ] Correct platforms per image
- [ ] Per-image cache scopes configured
- [ ] Valid YAML syntax

---

## Task 5.2: Test Workflow Locally (Optional)

**File(s):** None (testing task)
**Type:** RESEARCH
**Estimated time:** 20 min

**Task Categories:** Configuration

**Description:**
Optionally test the workflow locally using `act` or manual docker builds.

**Manual validation:**
```bash
# Simulate what CI will do for each image
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f deploy/docker/Dockerfile.backend \
  -t test-backend:local \
  --load .

docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -f deploy/docker/Dockerfile.worker-cpu \
  -t test-worker-cpu:local \
  --load .

docker buildx build \
  --platform linux/amd64 \
  -f deploy/docker/Dockerfile.worker-gpu \
  -t test-worker-gpu:local \
  --load .
```

**Implementation Notes:**
- Multi-arch builds require buildx
- `--load` only works for single platform; omit for multi-arch test
- This is optional but recommended before pushing

**Acceptance Criteria:**
- [ ] All three images build with buildx
- [ ] Multi-arch works for backend and worker-cpu
- [ ] Ready to push workflow changes

---

## Task 5.3: Push and Verify CI Build

**File(s):** None (execution task)
**Type:** VALIDATION
**Estimated time:** 30 min (mostly waiting)

**Task Categories:** Cross-Component, External

**Description:**
Push changes to main (or feature branch) and verify CI builds all images.

**Steps:**

1. **Commit workflow changes:**
```bash
git add .github/workflows/build-images.yml
git commit -m "ci: Update build-images.yml for three-image matrix build"
```

2. **Push to trigger CI:**
```bash
git push origin feature/container-optimization
# Or if ready for main:
# git push origin main
```

3. **Monitor CI:**
- Go to GitHub Actions tab
- Watch the "Build and Push Images" workflow
- Verify all three matrix jobs complete

4. **Verify images in registry:**
```bash
# Pull and inspect
docker pull ghcr.io/kpiteira/ktrdr-backend:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-cpu:latest
docker pull ghcr.io/kpiteira/ktrdr-worker-gpu:latest

# Check sizes
docker images | grep ghcr.io/kpiteira/ktrdr

# Verify multi-arch (backend and worker-cpu)
docker manifest inspect ghcr.io/kpiteira/ktrdr-backend:latest | grep architecture
```

**Implementation Notes:**
- CI may take 15-20 minutes for all images
- GPU worker is largest and slowest
- If any job fails, check logs and fix

**Acceptance Criteria:**
- [ ] CI workflow triggered
- [ ] All three matrix jobs pass
- [ ] Images available in ghcr.io
- [ ] Backend and worker-cpu have multi-arch manifests
- [ ] Image tags correct (sha-xxx + latest)

---

## Milestone 5 Completion Checklist

- [ ] Task 5.1: build-images.yml updated
- [ ] Task 5.2: Local buildx test passed (optional)
- [ ] Task 5.3: CI build successful, images in registry
- [ ] All three images available: backend, worker-cpu, worker-gpu
- [ ] Multi-arch manifests for backend and worker-cpu
- [ ] All changes committed
- [ ] M1-M4 functionality verified
- [ ] Ready for environment rollout (M6)

---

## Rollback Plan

If CI build fails:

1. Check workflow logs for specific error
2. Common issues:
   - Dockerfile path typo
   - Missing file in context
   - Cache issues (try clearing cache)
3. Fix and re-push
4. If fundamentally broken, revert to single-image workflow temporarily:
   ```bash
   git revert HEAD  # Revert workflow changes
   git push
   ```
