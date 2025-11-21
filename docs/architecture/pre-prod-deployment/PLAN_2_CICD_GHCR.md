# Project 2: CI/CD & GHCR

**Status**: Ready for Implementation
**Estimated Effort**: Medium
**Prerequisites**: Project 1a (Dependencies & Dockerfile)

---

## Goal

Automated image building and distribution via GitHub Actions and GitHub Container Registry (GHCR), with every merge to `main` producing a versioned, pullable image.

---

## Context

Per [DESIGN.md](DESIGN.md) Decision 4, CI builds images with git SHA tags for perfect reproducibility. Workers use the same `ktrdr-backend` image with different entry points, simplifying the build process.

---

## Tasks

### Task 2.1: Create GitHub Actions Workflow

**File**: `.github/workflows/build-images.yml`

**Goal**: Automated image building on merge to main

**Actions**:
1. Create new workflow file
2. Trigger on push to `main` and `workflow_dispatch` (manual)
3. Set up Docker Buildx for efficient builds
4. Authenticate to GHCR using `GITHUB_TOKEN`
5. Build backend image
6. Tag with git SHA (`sha-abc1234`) and `latest`
7. Push to `ghcr.io/<username>/ktrdr-backend`
8. Add build caching for faster subsequent builds

**Workflow Content**:
```yaml
name: Build and Push Images

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository_owner }}/ktrdr-backend

jobs:
  build-backend:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            type=sha,prefix=sha-,format=short
            type=raw,value=latest

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/backend/Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Acceptance Criteria**:
- [ ] Workflow file created
- [ ] Triggers on push to main
- [ ] Manual trigger available
- [ ] Uses Docker Buildx
- [ ] Authenticates to GHCR
- [ ] Tags with SHA and latest

---

### Task 2.2: Test CI Workflow

**Goal**: Verify end-to-end CI pipeline

**Actions**:
1. Merge workflow to main (or test on branch first)
2. Verify workflow triggers
3. Check build logs for errors
4. Verify image appears in GHCR
5. Check both tags exist (sha-xxx and latest)
6. Verify build time is reasonable (<5 min)

**Acceptance Criteria**:
- [ ] Workflow runs successfully
- [ ] Image pushed to GHCR
- [ ] SHA tag created (e.g., `sha-a1b2c3d`)
- [ ] `latest` tag created
- [ ] Build completes in <5 minutes
- [ ] Cache is used on subsequent builds

---

### Task 2.3: Create GitHub PAT for Local Testing

**Goal**: Enable local image pulls from private GHCR

**Actions**:
1. Create GitHub Personal Access Token (PAT)
2. Scope: `read:packages` only
3. Store securely (will go to 1Password in Project 4)
4. Test authentication locally
5. Document the process

**Testing**:
```bash
# Authenticate
echo $GITHUB_PAT | docker login ghcr.io -u <username> --password-stdin

# Pull image
docker pull ghcr.io/<username>/ktrdr-backend:latest

# Verify
docker images | grep ktrdr-backend
```

**Acceptance Criteria**:
- [ ] PAT created with read:packages scope
- [ ] Can authenticate Docker to GHCR locally
- [ ] Can pull latest image
- [ ] Can pull specific SHA tag

---

### Task 2.4: Test Pulled Image Locally

**Goal**: Verify CI-built image works correctly

**Actions**:
1. Pull latest image from GHCR
2. Run with required environment variables
3. Verify health check passes
4. Test basic API functionality
5. Compare behavior with locally-built image

**Testing**:
```bash
# Pull and run
docker pull ghcr.io/<username>/ktrdr-backend:latest

docker run --rm -p 8000:8000 \
  -e DB_HOST=host.docker.internal \
  -e DB_PORT=5432 \
  -e DB_NAME=ktrdr \
  -e DB_USER=ktrdr \
  -e DB_PASSWORD=localdev \
  -e JWT_SECRET=testsecret123456789012345678901234 \
  ghcr.io/<username>/ktrdr-backend:latest

# Test
curl http://localhost:8000/api/v1/health
```

**Acceptance Criteria**:
- [ ] Image pulls successfully
- [ ] Container starts without errors
- [ ] Health check passes
- [ ] API responds correctly

---

### Task 2.5: Add Image Mode to docker-compose.dev.yml

**Goal**: Support running with GHCR images instead of local build

**Actions**:
1. Add commented `image:` lines to docker-compose.dev.yml
2. Document how to switch between build mode and image mode
3. Support `IMAGE_TAG` environment variable
4. Test with GHCR images

**Changes to docker-compose.dev.yml**:
```yaml
backend:
  # Build mode (default for development)
  build:
    context: .
    dockerfile: docker/backend/Dockerfile
  # Image mode (uncomment to test with CI-built images)
  # image: ghcr.io/<username>/ktrdr-backend:${IMAGE_TAG:-latest}
```

**Documentation**:
```markdown
## Testing with CI-Built Images

To test with images from GHCR instead of building locally:

1. Authenticate to GHCR: `echo $PAT | docker login ghcr.io -u <username> --password-stdin`
2. Edit docker-compose.dev.yml: comment `build:` sections, uncomment `image:` lines
3. Run: `docker compose -f docker-compose.dev.yml up`

To use a specific version:
```bash
IMAGE_TAG=sha-a1b2c3d docker compose -f docker-compose.dev.yml up
```
```

**Acceptance Criteria**:
- [ ] Image mode documented in compose file
- [ ] Can switch to image mode easily
- [ ] IMAGE_TAG override works
- [ ] Stack runs with GHCR images

---

### Task 2.6: Update Pre-prod Compose Files for GHCR

**Files**:
- `docs/architecture/pre-prod-deployment/docker-compose.core.yml`
- `docs/architecture/pre-prod-deployment/docker-compose.workers.yml`

**Goal**: Pre-prod compose files reference GHCR images

**Actions**:
1. Update image references to use GHCR
2. Use placeholder for repository owner
3. Support IMAGE_TAG environment variable
4. Default to `latest` if not specified

**Changes**:
```yaml
# docker-compose.core.yml
backend:
  image: ghcr.io/<github-username>/ktrdr-backend:${IMAGE_TAG:-latest}

# docker-compose.workers.yml
backtest-worker-1:
  image: ghcr.io/<github-username>/ktrdr-backend:${IMAGE_TAG:-latest}

training-worker-1:
  image: ghcr.io/<github-username>/ktrdr-backend:${IMAGE_TAG:-latest}
```

**Acceptance Criteria**:
- [ ] Core compose uses GHCR images
- [ ] Worker compose uses GHCR images
- [ ] IMAGE_TAG variable supported
- [ ] Placeholder documented for customization

---

### Task 2.7: Document GHCR Workflow

**Goal**: Clear documentation for image distribution

**Actions**:
1. Document CI workflow in ARCHITECTURE.md
2. Document image tagging strategy
3. Document how to find available tags
4. Document authentication requirements
5. Add troubleshooting section

**Documentation Content**:
- How CI builds images
- Tag format (sha-xxx, latest)
- How to list available tags
- How to authenticate
- How to pull specific versions
- Troubleshooting common issues

**Acceptance Criteria**:
- [ ] ARCHITECTURE.md updated with CI workflow
- [ ] Tagging strategy documented
- [ ] Authentication documented
- [ ] Clear instructions for pulling images

---

## Validation

**Final Verification**:
```bash
# 1. Verify CI workflow exists and runs
# Check GitHub Actions tab for successful run

# 2. List available tags
# Visit: https://github.com/<username>/ktrdr2/pkgs/container/ktrdr-backend

# 3. Authenticate locally
echo $GITHUB_PAT | docker login ghcr.io -u <username> --password-stdin

# 4. Pull latest
docker pull ghcr.io/<username>/ktrdr-backend:latest

# 5. Pull specific SHA (from recent CI run)
docker pull ghcr.io/<username>/ktrdr-backend:sha-abc1234

# 6. Run with GHCR image
docker run --rm ghcr.io/<username>/ktrdr-backend:latest --version

# 7. Test image mode in compose
# Edit docker-compose.dev.yml for image mode
IMAGE_TAG=latest docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml ps
curl http://localhost:8000/api/v1/health
```

---

## Success Criteria

- [ ] GitHub Actions workflow builds on every merge to main
- [ ] Images pushed to GHCR with SHA tags
- [ ] `latest` tag always points to most recent build
- [ ] Can pull images locally with authentication
- [ ] docker-compose.dev.yml supports image mode
- [ ] Pre-prod compose files reference GHCR
- [ ] Documentation complete

---

## Dependencies

**Depends on**: Project 1a (Dependencies & Dockerfile)
**Blocks**: Project 4 (Secrets & Deployment CLI), Project 5 (Pre-prod Deployment)

---

## Notes

- Single image (`ktrdr-backend`) used for both backend and workers
- Workers differentiate via entry point command, not different images
- Build caching significantly speeds up subsequent builds
- PAT with `read:packages` scope is sufficient for pulling

---

**Previous Project**: [Project 1b: Local Dev Environment](PLAN_1B_LOCAL_DEV.md)
**Next Project**: [Project 3: Observability Dashboards](PLAN_3_OBSERVABILITY.md)
