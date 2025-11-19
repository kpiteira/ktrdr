# Pre-Production Deployment Implementation Plan

**Version**: 1.0
**Status**: Ready for Implementation
**Date**: 2025-11-17

---

## Overview

This document breaks down the implementation of the pre-production deployment architecture into phased tasks. The architecture is defined in [ARCHITECTURE.md](ARCHITECTURE.md), with design rationale in [DESIGN.md](DESIGN.md) and operational procedures in [OPERATIONS.md](OPERATIONS.md).

---

## Phase 0: CI/CD Infrastructure (PREREQUISITE)

**Goal**: Enable automated image building and publishing to GHCR

**Critical**: This phase MUST be completed before deployment CLI work. Without CI-built images pushed to GHCR, the deployment commands will fail.

### Task 0.1: Update Backend Dockerfile for uv.lock

**File**: `docker/backend/Dockerfile`

**Current Issue**: Dockerfile uses `requirements.txt` instead of `uv.lock`, causing dev/prod dependency drift

**Implementation**:

1. Replace `requirements.txt` with `uv.lock` and `pyproject.toml`
2. Update pip install command to use `uv sync --frozen --no-dev`
3. Fix Python version paths in COPY statements (currently references 3.11, should be 3.13)
4. Test local build with `docker build -f docker/backend/Dockerfile -t ktrdr-backend:test .`
5. Verify dependencies match uv.lock exactly

**Changes Required**:

```dockerfile
# OLD (lines 28-32):
COPY requirements.txt ./
RUN uv pip install --system --no-cache-dir -r requirements.txt

# NEW:
COPY uv.lock pyproject.toml ./
RUN uv sync --frozen --no-dev --no-cache

# OLD (line 77):
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages

# NEW:
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
```

**Acceptance Criteria**:

- [ ] Dockerfile builds successfully locally
- [ ] Uses uv.lock for exact dependency reproduction
- [ ] Python 3.13 paths correct (no 3.11 references)
- [ ] Built image runs and passes health check
- [ ] Image size reasonable (<500MB runtime stage)

---

### Task 0.2: Create CI Image Build Workflow

**File**: `.github/workflows/build-images.yml`

**Implementation**:

1. Create new GitHub Actions workflow
2. Trigger on push to `main` branch only
3. Set up Docker Buildx for multi-platform support
4. Authenticate to GHCR using `GITHUB_TOKEN`
5. Build backend image with git SHA tag
6. Tag as both `sha-<commit>` and `latest`
7. Push to `ghcr.io/<username>/ktrdr-backend`
8. Add build caching for faster builds

**Workflow Structure**:

```yaml
name: Build and Push Images

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

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
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}/backend
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
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Acceptance Criteria**:

- [ ] Workflow triggers on push to `main`
- [ ] Builds backend image successfully
- [ ] Tags with git SHA (e.g., `sha-abc1234`)
- [ ] Also tags as `latest`
- [ ] Pushes to GHCR successfully
- [ ] Build completes in <5 minutes
- [ ] Uses build cache for faster subsequent builds

---

### Task 0.3: Test Image Pull from GHCR

**Goal**: Verify end-to-end CI → GHCR → Local pull workflow

**Prerequisites**:

- CI workflow merged and run at least once
- GitHub Personal Access Token (PAT) with `read:packages` scope (for local testing)

**Implementation**:

1. Create GitHub PAT for local testing
2. Authenticate Docker to GHCR: `echo $PAT | docker login ghcr.io -u <username> --password-stdin`
3. Pull latest image: `docker pull ghcr.io/<username>/ktrdr-backend:latest`
4. Pull specific SHA: `docker pull ghcr.io/<username>/ktrdr-backend:sha-abc1234`
5. Run image locally to verify it works
6. Test with compose file referencing GHCR image

**Acceptance Criteria**:

- [ ] Can authenticate to GHCR locally
- [ ] Can pull `latest` tag
- [ ] Can pull specific SHA tag
- [ ] Pulled image runs successfully
- [ ] Health check passes
- [ ] Can reference in docker-compose with GHCR URL

**Testing Commands**:

```bash
# Test image pull
docker pull ghcr.io/<username>/ktrdr-backend:latest

# Test image run
docker run --rm -p 8000:8000 \
  -e DB_HOST=localhost \
  -e DB_NAME=test \
  -e DB_USER=test \
  -e DB_PASSWORD=test \
  -e JWT_SECRET=test \
  ghcr.io/<username>/ktrdr-backend:latest

# Verify health
curl http://localhost:8000/api/v1/health
```

---

### Task 0.4: Update Docker Compose to Use GHCR Images

**Files**:

- `docs/architecture/pre-prod-deployment/docker-compose.core.yml`
- `docs/architecture/pre-prod-deployment/docker-compose.workers.yml`

**Implementation**:

1. Update image references to use GHCR registry
2. Add `<username>` placeholder for repository owner
3. Document image URL format in ARCHITECTURE.md
4. Test locally with pulled GHCR images

**Changes**:

```yaml
# docker-compose.core.yml
backend:
  image: ghcr.io/<username>/ktrdr-backend:${IMAGE_TAG:-latest}

# docker-compose.workers.yml
backtest-worker:
  image: ghcr.io/<username>/ktrdr-backend:${IMAGE_TAG:-latest}

training-worker:
  image: ghcr.io/<username>/ktrdr-backend:${IMAGE_TAG:-latest}
```

**Acceptance Criteria**:

- [x] Compose files reference GHCR images (COMPLETED)
- [x] Workers use `ktrdr-backend` image, not `ktrdr-worker` (COMPLETED)
- [x] Placeholder standardized to `<github-username>` (COMPLETED)
- [ ] `IMAGE_TAG` environment variable supported
- [ ] Defaults to `latest` if not specified
- [ ] Can override with specific SHA
- [ ] Documented in ARCHITECTURE.md

**Note**: Workers use the SAME `ktrdr-backend` image with different uvicorn entry points.

---

### Task 0.5: Configure Docker Registry Authentication

**Goal**: Enable LXCs to pull private images from GHCR

**Prerequisites**: GitHub Personal Access Token (PAT) with `read:packages` scope

**Implementation**:

1. Create GitHub PAT for GHCR access
2. Store PAT in 1Password vault `KTRDR Homelab Secrets`
3. Add field `ghcr_token` to 1Password item `ktrdr-homelab-core`
4. Update deployment CLI to authenticate Docker to GHCR before pulling images
5. Document manual authentication for testing

**Manual Authentication (for testing)**:

```bash
# On LXC (manual setup)
echo $GHCR_TOKEN | docker login ghcr.io -u <github-username> --password-stdin

# Verify authentication
docker pull ghcr.io/<github-username>/ktrdr-backend:latest
```

**CLI Integration** (to be added in Phase 2, Task 2.4):

```python
# In ktrdr/cli/commands/deploy.py
def docker_login(host: str, username: str, token: str):
    """Authenticate Docker to GHCR on remote host."""
    cmd = f"echo {token} | docker login ghcr.io -u {username} --password-stdin"
    ssh_cmd = ['ssh', host, cmd]
    subprocess.run(ssh_cmd, check=True)

# Call before docker compose pull in each deployment command
```

**Acceptance Criteria**:
- [ ] GitHub PAT created with read:packages scope
- [ ] PAT stored in 1Password
- [ ] Manual authentication works on LXC
- [ ] Deployment CLI authenticates before pulling images
- [ ] Documented in OPERATIONS.md
- [ ] Error handling for missing/invalid token

---

## Phase 1: Core Infrastructure

**Goal**: Set up Docker Compose stacks and monitoring configuration files

### Task 1.1: Create Core Stack Docker Compose

**Source**: `docs/architecture/pre-prod-deployment/docker-compose.core.yml` (spec template)

**Target**: `docker-compose.core.yml` (repository root for local testing)

**Implementation**:
1. Copy spec template to repository root for local testing
2. Define all 6 services: db, backend, prometheus, grafana, jaeger, nfs-server
3. Configure networks (`ktrdr-core`)
4. Configure volumes (`postgres_data`, `prometheus_data`, `grafana_data`)
5. Add environment variable placeholders
6. Add health checks for db service
7. Test locally with mock env vars

**Acceptance Criteria**:
- [ ] All services start successfully with `docker compose -f docker-compose.core.yml up`
- [ ] Backend can connect to database
- [ ] Prometheus accessible at `localhost:9090`
- [ ] Grafana accessible at `localhost:3000`
- [ ] Jaeger accessible at `localhost:16686`

**Notes**:
- Use `host.docker.internal` for local NFS testing
- Backend image tag defaults to `latest` for local dev

---

### Task 1.2: Create Worker Stack Docker Compose

**Source**: `docs/architecture/pre-prod-deployment/docker-compose.workers.yml` (spec template)

**Target**: `docker-compose.workers.yml` (repository root for local testing)

**Implementation**:
1. Copy spec template to repository root for local testing
2. Define backtest-worker service with replica configuration
3. Define training-worker service with replica configuration
4. Configure resource limits (CPU, memory)
5. Configure port mappings for replicas
6. Add environment variable placeholders including DB access
7. Test locally with `--scale` flag

**Acceptance Criteria**:
- [ ] Workers start successfully with replica scaling
- [ ] Workers can reach backend at configured URL
- [ ] Workers can access NFS mount
- [ ] Workers can connect to database for checkpointing
- [ ] Port mapping works correctly (replicas on sequential ports)

**Testing**:
```bash
docker compose -f docker-compose.workers.yml up --scale backtest-worker=3 --scale training-worker=2
```

---

### Task 1.3: Create Monitoring Configuration Files

**Source**: `docs/architecture/pre-prod-deployment/monitoring/` (spec templates)

**Target**: `monitoring/` (repository root for local testing)

**Files**:

- `monitoring/prometheus.yml` (homelab production config)
- `monitoring/prometheus-dev.yml` (local development config)
- `monitoring/grafana/datasources.yml`
- `monitoring/grafana/dashboards.yml`

**Implementation**:

1. Copy spec templates to repository root `monitoring/` directory
2. Review Prometheus scrape config for backend and workers
3. Create simplified `prometheus-dev.yml` for local development (uses Docker service names)
4. Review Grafana datasource provisioning (Prometheus + Jaeger)
5. Review Grafana dashboard provisioning config
6. Copy/create Grafana dashboard JSON files if not already present
7. Test with core stack locally

**Acceptance Criteria**:
- [x] `prometheus.yml` created for homelab (COMPLETED)
- [x] `prometheus-dev.yml` created for local dev (COMPLETED)
- [x] Grafana datasources config created (COMPLETED)
- [x] Grafana dashboards config created (COMPLETED)
- [ ] Prometheus scrapes backend metrics successfully
- [ ] Prometheus scrapes worker metrics (with placeholder targets)
- [ ] Grafana auto-provisions Prometheus datasource
- [ ] Grafana auto-provisions Jaeger datasource
- [ ] Dashboard JSON files present in `monitoring/grafana/dashboards/`

---

### Task 1.4: Create Environment Configuration Files

**Files**:
- `.env.core` - Core stack non-secret configuration
- `.env.workers` - Worker stack non-secret configuration (template for all nodes)
- `ENV_VARS.md` - Complete variable reference

**Implementation**:
1. Create `.env.core` with non-secret config (safe to commit)
2. Create `.env.workers` with non-secret config (safe to commit, customize per node)
3. Document hybrid configuration model in ENV_VARS.md
4. Add security notes emphasizing "no secrets at rest"
5. Create validation script to check env var completeness
6. Update `.gitignore` to exclude `.env.dev` only (local development)

**Acceptance Criteria**:
- [x] `.env.core` created with non-secret config (COMPLETED)
- [x] `.env.workers` created with non-secret config (COMPLETED)
- [x] ENV_VARS.md documents hybrid model (COMPLETED)
- [x] Documentation explains which vars are secrets vs config (COMPLETED)
- [x] Hybrid configuration model documented (COMPLETED)
- [ ] `.gitignore` updated to exclude `.env.dev`
- [ ] Validation script created and tested

**ENV_VARS.md Structure**:
- [x] Core stack variables (database, backend, monitoring, registry) (COMPLETED)
- [x] Worker stack variables (API URLs, worker config, DB access, replica scaling) (COMPLETED)
- [x] Security guidelines (COMPLETED)
- [x] Hybrid configuration model (COMPLETED)

**Important**:
- `.env.core` and `.env.workers` contain ONLY non-secret config (URLs, ports, hostnames) - safe to commit
- Secrets (DB_PASSWORD, JWT_SECRET, etc.) are NEVER in .env files
- Secrets injected inline by deployment CLI from 1Password

---

### Task 1.5: Create Local Development Environment

**Goal**: Implement local development workflow per design-input.md Section 5

**Files**:
- `docker-compose.dev.yml`
- `.env.dev.example`
- `monitoring/prometheus-dev.yml`

**Implementation**:

1. Create `docker-compose.dev.yml` for local Mac development
2. Support hot reload mode (bind-mounted code, uvicorn --reload)
3. Support image mode (toggle for pre-deployment testing)
4. Create `.env.dev.example` template
5. Configure simplified networking (single Docker host)
6. Add worker services with `profiles: [workers]` (optional start)
7. Use local directory for shared storage (`./dev-shared`)
8. Document usage examples

**Hot Reload Mode** (default):
- Backend: bind mount `ktrdr/` directory, uvicorn --reload
- Workers: bind mount `ktrdr/` directory, uvicorn --reload
- Fast iteration for development

**Image Mode** (testing):
- Comment out `build:` sections
- Uncomment `image:` lines
- Build images locally: `make build-backend TAG=local`
- Test with CI-like environment

**Acceptance Criteria**:
- [x] `docker-compose.dev.yml` created (COMPLETED)
- [x] `.env.dev.example` created for local development (COMPLETED)
- [x] `monitoring/prometheus-dev.yml` created (COMPLETED)
- [ ] Hot reload mode works (code changes picked up immediately)
- [ ] Image mode works (can test with built images)
- [ ] Workers optional (start with `--profile workers`)
- [ ] All services accessible at localhost
- [ ] Documented in README or dev guide

**Testing**:
```bash
# Start core services only
docker compose -f docker-compose.dev.yml up

# Start with workers
docker compose -f docker-compose.dev.yml --profile workers up

# Test image mode
make build-backend TAG=local
# Edit docker-compose.dev.yml to use image mode
docker compose -f docker-compose.dev.yml up
```

---

### Task 1.6: Create .gitignore Rules for Secrets

**Goal**: Prevent accidental secret commits (local development only)

**File**: `.gitignore` (repository root)

**Implementation**:

1. Add rules to ignore environment files with secrets
2. Keep .example files tracked in git
3. Ignore any local development artifacts

**Rules to Add**:
```gitignore
# Environment files (contain secrets - LOCAL DEV ONLY)
# Note: Homelab deployment does NOT use .env files (secretless model)
.env.dev
*.env.local
*.secrets

# Local development storage
dev-shared/

# Docker volumes (if mounted locally)
postgres_data_dev/
prometheus_data_dev/
grafana_data_dev/
```

**Acceptance Criteria**:
- [ ] `.gitignore` updated with secret file patterns
- [ ] `.env.dev.example` NOT ignored (should be tracked)
- [ ] Test that `.env.dev` cannot be committed
- [ ] Documented in ENV_VARS.md security section

**Note**: Only `.env.dev` is used (for local development). Homelab uses secretless deployment (1Password → CLI → inline injection).

---

### Task 1.7: Create Environment Validation Script

**Goal**: Validate required environment variables are set

**File**: `scripts/validate-env.sh`

**Implementation**:

1. Create validation script per ENV_VARS.md
2. Check core stack required variables
3. Check worker stack required variables
4. Provide clear error messages for missing variables

**Script** (from ENV_VARS.md):
```bash
#!/bin/bash
# scripts/validate-env.sh

REQUIRED_CORE=(DB_NAME DB_USER DB_PASSWORD JWT_SECRET GF_ADMIN_PASSWORD)
REQUIRED_WORKERS=(KTRDR_API_URL WORKER_TYPE WORKER_PORT WORKER_PUBLIC_BASE_URL DB_USER DB_PASSWORD)

check_vars() {
  local -n vars=$1
  local missing=()

  for var in "${vars[@]}"; do
    if [[ -z "${!var}" ]]; then
      missing+=("$var")
    fi
  done

  if [[ ${#missing[@]} -gt 0 ]]; then
    echo "❌ Missing required variables: ${missing[*]}"
    return 1
  fi

  echo "✅ All required variables set"
  return 0
}

# Usage:
# source .env.core && ./scripts/validate-env.sh core
# source .env.workers && ./scripts/validate-env.sh workers

if [[ "$1" == "core" ]]; then
  check_vars REQUIRED_CORE
elif [[ "$1" == "workers" ]]; then
  check_vars REQUIRED_WORKERS
else
  echo "Usage: $0 {core|workers}"
  exit 1
fi
```

**Acceptance Criteria**:
- [ ] Script created and executable
- [ ] Validates core stack variables
- [ ] Validates worker stack variables
- [ ] Clear error messages for missing variables
- [ ] Returns proper exit codes (0 success, 1 failure)
- [ ] Documented in ENV_VARS.md

---

## Phase 2: Deployment CLI

**Goal**: Implement Python CLI deployment commands with 1Password integration

### Task 2.1: Implement 1Password Integration

**File**: `ktrdr/cli/helpers/secrets.py`

**Implementation**:
1. Create secrets helper module
2. Implement `fetch_secrets_from_1password(item_name: str) -> Dict[str, str]`
3. Add error handling for missing `op` CLI
4. Add error handling for missing 1Password items
5. Add caching to avoid repeated `op` calls in same session
6. Write unit tests with mocked `subprocess` calls

**Acceptance Criteria**:
- [ ] Can fetch secrets from 1Password CLI
- [ ] Returns dict with field labels as keys
- [ ] Graceful error if `op` not installed
- [ ] Graceful error if item not found
- [ ] Unit tests pass

**Dependencies**: Requires `op` CLI installed locally for testing

---

### Task 2.2: Implement Git SHA Helper

**File**: `ktrdr/cli/helpers/git_utils.py`

**Implementation**:
1. Create git utilities module
2. Implement `get_latest_sha_tag() -> str`
3. Add error handling for non-git directories
4. Format as `sha-{short_sha}`
5. Write unit tests

**Acceptance Criteria**:
- [ ] Returns current git SHA in `sha-abc1234` format
- [ ] Graceful error if not in git repo
- [ ] Unit tests pass

---

### Task 2.3: Implement SSH Execution Helper

**File**: `ktrdr/cli/helpers/ssh_utils.py`

**Implementation**:
1. Create SSH utilities module
2. Implement `ssh_exec_with_env(host, workdir, env_vars, command)`
3. Build inline env var string with proper quoting
4. Build full SSH command
5. Add error handling for SSH failures
6. Add option for dry-run (print command without executing)
7. Write unit tests with mocked SSH

**Acceptance Criteria**:
- [ ] Correctly quotes env var values (handles spaces, special chars)
- [ ] Executes SSH command with inline env vars
- [ ] Returns stdout/stderr
- [ ] Dry-run mode prints command without executing
- [ ] Unit tests pass

**Security Note**: Secrets briefly visible in process args, but acceptable per DESIGN.md

---

### Task 2.4: Implement Pre-Deployment Validation

**File**: `ktrdr/cli/helpers/validation.py`

**Goal**: Validate prerequisites before attempting deployment

**Implementation**:

1. Create validation helper module
2. Implement `validate_deployment_prerequisites(host: str, checks: List[str]) -> bool`
3. Check DNS resolution (`ping -c 1 {host}`)
4. Check SSH connectivity (`ssh {host} 'echo ok'`)
5. Check Docker installed on target (`ssh {host} 'docker --version'`)
6. Check op CLI installed locally (`op --version`)
7. Check op authenticated (`op account list`)
8. Return detailed error messages for failures

**Validation Checks**:

```python
def validate_deployment_prerequisites(host: str) -> Tuple[bool, List[str]]:
    """
    Validate deployment prerequisites.

    Returns:
        (success: bool, errors: List[str])
    """
    errors = []

    # Check DNS resolution
    try:
        socket.gethostbyname(host)
    except socket.gaierror:
        errors.append(f"DNS resolution failed for {host}")

    # Check SSH connectivity
    result = subprocess.run(['ssh', host, 'echo', 'ok'],
                          capture_output=True, timeout=5)
    if result.returncode != 0:
        errors.append(f"SSH connection failed to {host}")

    # Check Docker on remote
    result = subprocess.run(['ssh', host, 'docker', '--version'],
                          capture_output=True, timeout=5)
    if result.returncode != 0:
        errors.append(f"Docker not installed on {host}")

    # Check op CLI locally
    result = subprocess.run(['op', '--version'],
                          capture_output=True)
    if result.returncode != 0:
        errors.append("1Password CLI (op) not installed locally")

    # Check op authenticated
    result = subprocess.run(['op', 'account', 'list'],
                          capture_output=True)
    if result.returncode != 0:
        errors.append("1Password CLI not authenticated (run: op signin)")

    return (len(errors) == 0, errors)
```

**Acceptance Criteria**:
- [ ] DNS resolution check implemented
- [ ] SSH connectivity check implemented
- [ ] Remote Docker check implemented
- [ ] Local op CLI check implemented
- [ ] op authentication check implemented
- [ ] Clear error messages for each failure
- [ ] Returns success/failure with detailed errors
- [ ] Unit tests with mocked subprocess calls

---

### Task 2.5: Implement Core Deployment Command

**File**: `ktrdr/cli/commands/deploy.py`

**Implementation**:
1. Create deployment command module
2. Implement `deploy` command group
3. Implement `deploy core <service>` subcommand
4. **NEW**: Run pre-deployment validation (Task 2.4)
5. **NEW**: Authenticate Docker to GHCR (Task 0.5)
6. Fetch secrets from 1Password
7. Build env vars dict
8. Call SSH helper to execute Docker Compose
9. Add `--dry-run` flag
10. Add `--tag` flag to override IMAGE_TAG
11. Add `--skip-validation` flag (for testing)
12. Write integration tests (mocked SSH and 1Password)

**Acceptance Criteria**:
- [ ] Pre-deployment validation runs before deployment
- [ ] Docker authenticates to GHCR before pull
- [ ] `ktrdr deploy core backend` works
- [ ] `ktrdr deploy core all` deploys all core services
- [ ] Secrets fetched from 1Password
- [ ] SSH command executed with inline env vars
- [ ] Dry-run shows command without executing
- [ ] Custom tag override works
- [ ] Validation can be skipped with `--skip-validation`

**Command Flow**:
```python
ktrdr deploy core backend
  ├─> validate_deployment_prerequisites('ktrdr-core.internal')  # NEW
  ├─> fetch_secrets_from_1password('ktrdr-homelab-core')
  ├─> docker_login('ktrdr-core.internal', username, ghcr_token)  # NEW
  ├─> get_latest_sha_tag()
  ├─> ssh_exec_with_env('ktrdr-core.internal', '/opt/ktrdr-core', env_vars, 'docker compose pull backend && docker compose up -d backend')
  └─> print success message
```

---

### Task 2.6: Implement Worker Deployment Command

**File**: `ktrdr/cli/commands/deploy.py` (extend)

**Implementation**:
1. Implement `deploy workers <node>` subcommand
2. Support node choices: B, C (dynamic from config later)
3. Fetch DB secrets from 1Password (workers need DB access)
4. Build env vars dict including replica counts
5. Call SSH helper to execute Docker Compose
6. Add `--replicas-backtest` and `--replicas-training` flags
7. Write integration tests

**Acceptance Criteria**:
- [ ] `ktrdr deploy workers B` works
- [ ] `ktrdr deploy workers C` works
- [ ] Replica counts can be overridden via flags
- [ ] Workers get DB credentials for checkpointing
- [ ] Integration tests pass

**Command Flow**:
```python
ktrdr deploy workers B
  ├─> fetch_secrets_from_1password('ktrdr-homelab-core')  # For DB access
  ├─> get_latest_sha_tag()
  ├─> ssh_exec_with_env('ktrdr-workers-b.internal', '/opt/ktrdr-workers-b', env_vars, 'docker compose pull && docker compose up -d')
  └─> print success message
```

---

## Phase 3: Integration & Testing

**Goal**: End-to-end testing, documentation, and CI integration

### Task 3.1: Register CLI Commands

**File**: `ktrdr/cli/cli.py`

**Implementation**:
1. Import `deploy` command group
2. Register with main CLI via `cli.add_command(deploy)`
3. Test command discovery (`ktrdr deploy --help`)
4. Update CLI documentation

**Acceptance Criteria**:
- [ ] `ktrdr --help` shows `deploy` command
- [ ] `ktrdr deploy --help` shows subcommands (`core`, `workers`)
- [ ] Commands accessible via installed CLI

---

### Task 3.2: Create Deployment Documentation

**File**: `docs/user-guides/deployment-homelab.md`

**Implementation**:
1. Create user guide for homelab deployment
2. Document prerequisites (LXC setup per OPERATIONS.md)
3. Document 1Password setup (vault structure, field naming)
4. Document first-time deployment workflow
5. Document update deployment workflow
6. Document rollback procedure
7. Document troubleshooting steps
8. Add screenshots/examples

**Sections**:
- Prerequisites
- 1Password Configuration
- First-Time Deployment
- Updating Deployments
- Scaling Workers
- Rollback Procedure
- Troubleshooting

---

### Task 3.3: Integration Testing

**Test Suite**: `tests/integration/test_deployment.py`

**Implementation**:
1. Create integration test for full deployment flow (mocked)
2. Test secret fetching (mocked 1Password)
3. Test SSH command building
4. Test env var injection
5. Test error scenarios (missing secrets, SSH failure, etc.)
6. Add CI job to run deployment tests

**Test Scenarios**:
- Deploy core services with valid secrets
- Deploy workers with valid secrets
- Handle missing 1Password item
- Handle SSH connection failure
- Handle invalid service name
- Dry-run mode produces correct output

**Acceptance Criteria**:
- [ ] All integration tests pass
- [ ] Tests cover happy path and error cases
- [ ] Tests run in CI
- [ ] No actual SSH connections or 1Password calls in tests

---

### Task 3.4: End-to-End Deployment Verification

**Goal**: Manual verification on actual homelab infrastructure

**Prerequisites**:
- LXCs provisioned per OPERATIONS.md
- 1Password configured with `ktrdr-homelab-core` item
- DNS configured (`ktrdr-core.internal`, `ktrdr-workers-b.internal`, etc.)

**Verification Steps**:
1. Deploy core stack: `ktrdr deploy core all`
2. Verify all core services running
3. Deploy worker stack B: `ktrdr deploy workers B`
4. Deploy worker stack C: `ktrdr deploy workers C`
5. Verify workers register with backend
6. Verify observability stack accessible (Grafana, Jaeger, Prometheus)
7. Run sample backtest operation
8. Verify metrics in Prometheus
9. Verify traces in Jaeger
10. Test rollback with `--tag` flag

**Acceptance Criteria**:
- [ ] Core stack deploys successfully
- [ ] Worker stacks deploy successfully
- [ ] Workers self-register with backend
- [ ] Backend API accessible at port 8000
- [ ] Grafana accessible at port 3000
- [ ] Jaeger accessible at port 16686
- [ ] Sample backtest completes successfully
- [ ] Metrics visible in Prometheus
- [ ] Traces visible in Jaeger
- [ ] Rollback to previous image tag works

---

## Dependencies & Prerequisites

### External Dependencies
- **1Password CLI** (`op`): Required for secrets management
- **SSH**: Required for remote deployment
- **Docker**: Required for local testing
- **Git**: Required for SHA tagging

### Infrastructure Dependencies (from OPERATIONS.md)
- LXC containers provisioned on Proxmox
- Static IPs assigned via Proxmox
- DNS entries configured in BIND
- NFS share created on core LXC (`/srv/ktrdr-shared`)
- NFS mounted on worker LXCs (`/mnt/ktrdr-shared`)

### Code Dependencies
- Backend image built and pushed to GHCR (completed in Phase 0)
- Worker image uses same backend image (shared image approach)

---

## Testing Strategy

### Unit Tests
- Mock all external dependencies (subprocess, SSH, 1Password)
- Test helper functions in isolation
- Coverage target: >90%

### Integration Tests
- Mock external services but test full CLI flow
- Test error handling and edge cases
- Run in CI on every commit

### End-to-End Tests
- Manual verification on actual infrastructure
- Run before declaring implementation complete
- Document results in deployment guide

---

## Success Criteria

### Functional Requirements
- ✅ Core stack deploys via CLI command
- ✅ Worker stacks deploy via CLI command
- ✅ Secrets fetched from 1Password (no secrets in git)
- ✅ Images pulled from GHCR with git SHA tags
- ✅ Monitoring stack (Prometheus, Grafana, Jaeger) configured
- ✅ Workers can access database for checkpointing
- ✅ NFS shared storage accessible to all services

### Non-Functional Requirements
- ✅ Deployment takes <5 minutes per stack
- ✅ Secrets never persisted to disk (inline injection only)
- ✅ Rollback possible via `--tag` flag
- ✅ Documentation comprehensive and accurate
- ✅ Tests provide >90% coverage

### Operational Requirements
- ✅ Clear error messages on failure
- ✅ Dry-run mode for safety
- ✅ Idempotent deployments (can run multiple times safely)
- ✅ Graceful handling of missing prerequisites

---

## Risk Mitigation

### Risk: Secrets exposure in process args
- **Mitigation**: Acceptable per DESIGN.md trade-off analysis
- **Note**: Requires elevated privileges to view via `ps` or `docker inspect`

### Risk: SSH key management
- **Mitigation**: Document SSH key setup in deployment guide
- **Assumption**: SSH key-based auth configured for LXC hosts

### Risk: 1Password CLI authentication
- **Mitigation**: Document `op signin` workflow
- **Assumption**: User has 1Password account with automation capabilities

### Risk: Docker Compose version compatibility
- **Mitigation**: Document minimum Docker Compose version (v2.x)
- **Testing**: Test on Docker Compose v2.20+

### Risk: Network connectivity to LXCs
- **Mitigation**: Pre-deployment connectivity check in CLI
- **Testing**: Verify DNS resolution and SSH access before deployment

---

## Future Enhancements (Out of Scope)

- Auto-scaling workers based on queue depth
- Automated LXC provisioning (currently manual per OPERATIONS.md)
- Secret rotation automation
- Blue-green deployments
- Health check monitoring and auto-restart
- Deployment notifications (Slack, email, etc.)
- Multi-environment support (staging, production)

---

## Related Documents

- [DESIGN.md](DESIGN.md) - Design decisions and rationale
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical specifications
- [OPERATIONS.md](OPERATIONS.md) - Manual operational procedures
- [design-input.md](design-input.md) - Original design requirements (9 sections)

---

**Document End**
