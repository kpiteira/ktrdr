# Project 5: Pre-prod Deployment

**Status**: In Progress
**Estimated Effort**: Large
**Prerequisites**: Project 4 (Secrets & Deployment CLI)

**Branch:** infra/preprod

---

## Goal

Fully operational pre-production environment on Proxmox with monitoring, following all design principles from [DESIGN.md](DESIGN.md).

---

## Repository Structure

**IMPORTANT**: This section defines the canonical structure for all deployment-related files.

### Design Principles

1. **`/deploy/` is the single home** for all deployment artifacts
2. **Environments are explicit** - `local/`, `homelab/`, `canary/`
3. **Shared resources** are in `shared/` - dashboards, datasources
4. **Docs contain documentation only** - examples clearly labeled as such
5. **No root-level compose files** - convenience symlinks only

### Directory Structure

```
/deploy/                              # ALL deployment-related files
├── docker/                           # Dockerfiles
│   ├── Dockerfile                    # Production image
│   └── Dockerfile.dev                # Development image
│
├── environments/                     # Environment-specific configs
│   ├── local/                        # Local development
│   │   ├── docker-compose.yml        # Local dev compose
│   │   └── prometheus.yml            # Local targets (service names)
│   │
│   ├── homelab/                      # Homelab pre-prod
│   │   ├── docker-compose.core.yml   # Core services (backend, db, monitoring)
│   │   ├── docker-compose.workers.yml # CPU workers
│   │   ├── docker-compose.gpu-worker.yml # GPU worker
│   │   ├── .env.example              # Template for secrets
│   │   └── prometheus.yml            # Homelab targets (DNS names)
│   │
│   └── canary/                       # Canary testing
│       └── docker-compose.yml        # Canary compose
│
└── shared/                           # SHARED across all environments
    └── grafana/
        ├── datasources.yml           # Datasource config (same for all)
        ├── dashboards.yml            # Dashboard provisioning
        └── dashboards/               # Dashboard JSONs (SINGLE SOURCE)
            ├── operations.json
            ├── system-overview.json
            └── worker-status.json

# Root-level convenience symlinks (for developer experience)
/docker-compose.yml -> deploy/environments/local/docker-compose.yml

# Documentation (NO config files)
/docs/architecture/pre-prod-deployment/
├── ARCHITECTURE.md
├── DESIGN.md
├── PLAN_5_PREPROD.md                 # This file
├── OPERATIONS.md
└── examples/                         # Clearly labeled examples
    └── README.md                     # "These are EXAMPLES only"
```

### Key Differences from Previous Structure

| Before | After | Rationale |
|--------|-------|-----------|
| `/docker/backend/Dockerfile` | `/deploy/docker/Dockerfile` | All deploy artifacts in one place |
| `/docker-compose.dev.yml` (root) | `/deploy/environments/local/docker-compose.yml` | Explicit environment |
| `/monitoring/` (root) | `/deploy/shared/grafana/` | Shared resources clearly identified |
| `/deploy/homelab/monitoring/` | Uses `../shared/grafana/` | No duplication of dashboards |
| Configs in `/docs/` | Examples only in `/docs/.../examples/` | Docs are documentation |

### Environment-Specific vs Shared

**Shared (in `/deploy/shared/`)**:
- Grafana dashboards (JSON files)
- Grafana datasources.yml (uses docker service names, works everywhere)
- Grafana dashboards.yml (provisioning config)

**Environment-Specific**:
- Prometheus targets (only difference is hostnames)
- Docker Compose files (different service topology)
- Environment files (.env)

### Prometheus Configuration

The only difference between environments is the scrape targets:

**Local** (`/deploy/environments/local/prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'backend'
    metrics_path: '/metrics/'
    static_configs:
      - targets: ['backend:8000']  # Docker service name
```

**Homelab** (`/deploy/environments/homelab/prometheus.yml`):
```yaml
scrape_configs:
  - job_name: 'backend'
    metrics_path: '/metrics/'
    static_configs:
      - targets: ['backend:8000']  # Still docker service name (within compose)

  - job_name: 'workers-b'
    metrics_path: '/metrics/'
    static_configs:
      - targets: ['workers-b.ktrdr.home.mynerd.place:5003', ...]  # External
```

**Note**: The `/metrics/` trailing slash is required because FastAPI's mounted app redirects `/metrics` to `/metrics/`. This is documented behavior, not a workaround.

---

## Context

This project brings together all previous work to deploy KTRDR to the Proxmox homelab. LXC provisioning is manual (per DESIGN.md Decision 9), but deployment is automated via the CLI from Project 4.

---

## Tasks

### Task 5.0: Repository Restructuring

**Goal**: Clean up repository structure to match the design above

**Status**: OBSOLETE - Already completed in previous work

**Actions**:

1. Create new directory structure under `/deploy/`
2. Move Dockerfiles from `/docker/backend/` to `/deploy/docker/`
3. Move `/docker-compose.dev.yml` to `/deploy/environments/local/docker-compose.yml`
4. Move `/docker-compose.canary.yml` to `/deploy/environments/canary/docker-compose.yml`
5. Move `/monitoring/grafana/` to `/deploy/shared/grafana/`
6. Create `/deploy/environments/local/prometheus.yml` from `/monitoring/prometheus.yml`
7. Move `/deploy/homelab/` to `/deploy/environments/homelab/`
8. Update homelab compose files to reference `../../shared/grafana/`
9. Delete duplicate configs from `/docs/architecture/pre-prod-deployment/`
10. Create `/docs/architecture/pre-prod-deployment/examples/` with README
11. Update root symlinks
12. Update CI/CD workflow paths (`.github/workflows/`)
13. Update CLAUDE.md references

**Commands**:

```bash
# Create structure
mkdir -p deploy/docker
mkdir -p deploy/environments/{local,homelab,canary}
mkdir -p deploy/shared/grafana/dashboards

# Move Dockerfiles
mv docker/backend/* deploy/docker/
rmdir docker/backend docker

# Move compose files
mv docker-compose.dev.yml deploy/environments/local/docker-compose.yml
mv docker-compose.canary.yml deploy/environments/canary/docker-compose.yml

# Move shared grafana configs
mv monitoring/grafana/dashboards/* deploy/shared/grafana/dashboards/
mv monitoring/grafana/datasources.yml deploy/shared/grafana/
mv monitoring/grafana/dashboards.yml deploy/shared/grafana/

# Create local prometheus (copy from monitoring/)
cp monitoring/prometheus.yml deploy/environments/local/prometheus.yml

# Move homelab (already exists, just relocate)
mv deploy/homelab/* deploy/environments/homelab/
rmdir deploy/homelab

# Clean up old directories
rm -rf monitoring/grafana
mv monitoring/prometheus.yml deploy/environments/local/prometheus.yml
rm -rf monitoring

# Clean up docs (remove config files, keep docs)
rm -rf docs/architecture/pre-prod-deployment/monitoring
rm -f docs/architecture/pre-prod-deployment/docker-compose*.yml
mkdir -p docs/architecture/pre-prod-deployment/examples

# Create convenience symlink at root
ln -sf deploy/environments/local/docker-compose.yml docker-compose.yml

# Update symlinks (build scripts)
rm build_docker_dev.sh docker_dev.sh
ln -sf deploy/docker/build_docker_dev.sh build_docker_dev.sh 2>/dev/null || true
```

**Update CI/CD** (`.github/workflows/build-images.yml`):
```yaml
# Change:
file: docker/backend/Dockerfile
# To:
file: deploy/docker/Dockerfile
```

**Acceptance Criteria**:

- [ ] All deployment files under `/deploy/`
- [ ] Grafana dashboards in single location (`/deploy/shared/grafana/dashboards/`)
- [ ] No config files in `/docs/` (only examples)
- [ ] CI/CD builds still work
- [ ] Local dev environment still works
- [ ] All symlinks functional

---

### Task 5.1: Verify Proxmox Infrastructure

**Goal**: Ensure LXCs are provisioned and accessible

**Status**: COMPLETED

**Prerequisites** (manual, per OPERATIONS.md):

- Node A LXC: ktrdr-core (16GB RAM)
- Node B LXC: ktrdr-workers-b (16GB RAM)
- Node C LXC: ktrdr-workers-c (8GB RAM)
- Static IPs assigned
- SSH keys configured
- Docker installed on each LXC
- **LXC nesting enabled** (`pct set <CTID> --features nesting=1,keyctl=1`)

**Verification Steps**:

1. SSH to each LXC
2. Verify Docker is installed and running
3. Verify disk space available
4. Verify network connectivity between LXCs
5. Document IPs and hostnames

**Commands**:

```bash
# Test SSH access
ssh backend.ktrdr.home.mynerd.place 'echo ok'
ssh workers-b.ktrdr.home.mynerd.place 'echo ok'
ssh workers-c.ktrdr.home.mynerd.place 'echo ok'

# Check Docker
ssh backend.ktrdr.home.mynerd.place 'docker --version && docker ps'

# Check disk space
ssh backend.ktrdr.home.mynerd.place 'df -h'

# Test inter-LXC connectivity
ssh workers-b.ktrdr.home.mynerd.place 'ping -c 3 backend.ktrdr.home.mynerd.place'
```

**Acceptance Criteria**:

- [x] All 3 LXCs accessible via SSH
- [x] Docker installed and running on each
- [x] Sufficient disk space (>20GB free on core)
- [x] Network connectivity between LXCs verified
- [x] LXC nesting enabled for Docker-in-LXC

---

### Task 5.2: Configure DNS

**Goal**: DNS entries resolve correctly

**Status**: COMPLETED

**Required DNS Entries** (in local DNS server):

```text
; Core services (Node A)
backend.ktrdr.home.mynerd.place         -> Node A IP
postgres.ktrdr.home.mynerd.place        -> Node A IP
grafana.ktrdr.home.mynerd.place         -> Node A IP
prometheus.ktrdr.home.mynerd.place      -> Node A IP

; CPU Workers (Nodes B & C)
workers-b.ktrdr.home.mynerd.place       -> Node B IP
workers-c.ktrdr.home.mynerd.place       -> Node C IP

; GPU Worker (VM with GPU passthrough)
ktrdr-gpuworker.ktrdr.home.mynerd.place -> GPU Host IP
```

**Acceptance Criteria**:

- [x] All DNS entries configured (including GPU worker)
- [x] Resolution works from deployment machine
- [x] Resolution works between LXCs and GPU VM

---

### Task 5.3: Set Up NFS Shared Storage

**Goal**: NFS share accessible from all LXCs and GPU VM via `/mnt/ktrdr_data`

**Status**: COMPLETED (2025-12-06)

**Implementation Details**:

1. **NFS Server** (proxmox4 host):
   - Export: `/mnt/ktrdr_data 10.42.0.0/22(rw,sync,no_subtree_check,no_root_squash)`
   - User: `ktrdr` (UID 999, GID 1500) created for Docker container compatibility

2. **Permissions Configuration**:
   - Directories: `2775` (drwxrwsr-x) - setgid ensures new files inherit ktrdr group
   - Files: `664` (rw-rw-r--) - group write enabled
   - All files owned by `ktrdr:ktrdr` (999:1500)

3. **Client Configuration**:
   - LXCs use NFSv3: `10.42.0.11:/mnt/ktrdr_data /mnt/ktrdr_data nfs rw,relatime,vers=3,hard,proto=tcp 0 0`
   - GPU VM uses NFSv4: `10.42.0.11:/mnt/ktrdr_data /mnt/ktrdr_data nfs4 rw,relatime,vers=4.2,hard,proto=tcp 0 0`

4. **Docker Access**:
   - Containers use `group_add: ["1500"]` in docker-compose
   - Container user: `uid=999(ktrdr) gid=999(ktrdr) groups=999(ktrdr),1500`

5. **Group Configuration** (all nodes):
   - `ktrdr` group (GID 1500) created on all LXCs and GPU VM for consistent naming
   - SSH users added to ktrdr group where needed (e.g., `karl` on GPU VM)

**Acceptance Criteria**:

- [x] NFS server running on Proxmox Node A (bare metal)
- [x] NFS mounted on Proxmox Nodes B & C (bare metal)
- [x] Bind mounts configured for all 3 LXCs
- [x] NFS mounted directly on GPU Worker VM
- [x] Can read/write from all LXCs and GPU VM
- [x] Persists across reboots
- [x] Proper permissions (2775/664) with setgid bit
- [x] Docker containers can write via group membership (GID 1500)

---

### Task 5.4: Create Deployment Directories

**Goal**: Prepare directories for compose files on LXCs

**Status**: COMPLETED

**On Core LXC**:

```bash
mkdir -p /opt/ktrdr-core/monitoring/grafana/dashboards
```

**On Worker LXCs**:

```bash
mkdir -p /opt/ktrdr-workers-{b,c}
```

**Deployment Script** (copies files from repo to LXCs):

```bash
# Core deployment
scp deploy/environments/homelab/docker-compose.core.yml \
    backend.ktrdr.home.mynerd.place:/opt/ktrdr-core/

scp deploy/environments/homelab/prometheus.yml \
    backend.ktrdr.home.mynerd.place:/opt/ktrdr-core/monitoring/

scp -r deploy/shared/grafana/* \
    backend.ktrdr.home.mynerd.place:/opt/ktrdr-core/monitoring/grafana/

# Worker deployment (Node B)
scp deploy/environments/homelab/docker-compose.workers.yml \
    workers-b.ktrdr.home.mynerd.place:/opt/ktrdr-workers-b/

# Worker deployment (Node C)
scp deploy/environments/homelab/docker-compose.workers.yml \
    workers-c.ktrdr.home.mynerd.place:/opt/ktrdr-workers-c/
```

**Acceptance Criteria**:

- [ ] Directories created on all LXCs
- [ ] Compose files in place
- [ ] Monitoring configs (from shared) in place on core
- [ ] Environment files customized per node

---

### Task 5.5: Update Compose Files for Pre-prod

**Goal**: Ensure compose files reference correct paths

**docker-compose.core.yml Grafana volumes**:

```yaml
grafana:
  volumes:
    - ./monitoring/grafana/datasources.yml:/etc/grafana/provisioning/datasources/datasources.yml:ro
    - ./monitoring/grafana/dashboards.yml:/etc/grafana/provisioning/dashboards/dashboards.yml:ro
    - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards:ro
    - grafana_data:/var/lib/grafana
```

**docker-compose.workers.yml command** (fixed):

```yaml
command: ["python", "-m", "uvicorn", "ktrdr.backtesting.backtest_worker:app", ...]
```

**Note**: Workers use `python -m uvicorn` because `uvicorn` is not in PATH in the production image.

**Acceptance Criteria**:

- [x] Core compose file references monitoring paths correctly
- [x] Worker compose files use `python -m uvicorn`
- [x] All URLs point to correct hostnames
- [x] Image references use GHCR

---

### Task 5.6: Create Pre-prod Prometheus Config

**File**: `/opt/ktrdr-core/monitoring/prometheus.yml` (deployed from `/deploy/environments/homelab/prometheus.yml`)

**Status**: COMPLETED

**Configuration**:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'ktrdr-backend'
    metrics_path: '/metrics/'  # Trailing slash required (FastAPI redirect)
    static_configs:
      - targets: ['backend:8000']

  - job_name: 'ktrdr-workers-b'
    metrics_path: '/metrics/'
    static_configs:
      - targets:
        - 'workers-b.ktrdr.home.mynerd.place:5003'
        - 'workers-b.ktrdr.home.mynerd.place:5004'
        - 'workers-b.ktrdr.home.mynerd.place:5005'
        - 'workers-b.ktrdr.home.mynerd.place:5006'
        - 'workers-b.ktrdr.home.mynerd.place:5007'
        - 'workers-b.ktrdr.home.mynerd.place:5008'

  - job_name: 'ktrdr-workers-c'
    metrics_path: '/metrics/'
    static_configs:
      - targets:
        - 'workers-c.ktrdr.home.mynerd.place:5003'
        - 'workers-c.ktrdr.home.mynerd.place:5004'
        - 'workers-c.ktrdr.home.mynerd.place:5005'
        - 'workers-c.ktrdr.home.mynerd.place:5006'
        - 'workers-c.ktrdr.home.mynerd.place:5007'
        - 'workers-c.ktrdr.home.mynerd.place:5008'

  - job_name: 'ktrdr-gpu-worker'
    metrics_path: '/metrics/'
    static_configs:
      - targets:
        - 'ktrdr-gpuworker.ktrdr.home.mynerd.place:5005'
```

**Acceptance Criteria**:

- [x] Config includes backend with `/metrics/` path
- [x] Config includes all CPU workers on Nodes B & C
- [x] Config includes GPU worker
- [x] Targets use correct hostnames/ports

---

### Task 5.7: Deploy Core Stack

**Goal**: Core services running on Node A

**Status**: COMPLETED (with issues fixed)

**Issues Fixed During Deployment**:

1. **Dockerfile path issue**: Production Dockerfile used `/home/ktrdr/app` instead of `/app`. Fixed by refactoring to use `/app` (industry standard).

2. **Logging directory**: Container expected `/app/logs` but it didn't exist. Fixed in Dockerfile.

**Commands**:

```bash
# Deploy core services
ssh backend.ktrdr.home.mynerd.place 'cd /opt/ktrdr-core && docker compose -f docker-compose.core.yml up -d'

# Verify
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health
```

**Acceptance Criteria**:

- [x] All core services running
- [x] Backend API accessible
- [x] Grafana accessible
- [x] Jaeger accessible
- [x] Prometheus accessible
- [x] Database healthy

---

### Task 5.8: Deploy Worker Stacks

**Goal**: Workers running on Nodes B and C

**Status**: COMPLETED

**Issues Fixed During Deployment**:

1. **LXC nesting**: Docker-in-LXC requires nesting enabled. Fixed with `pct set <CTID> --features nesting=1,keyctl=1`.

2. **uvicorn path**: Direct `uvicorn` not in PATH. Fixed by using `python -m uvicorn`.

**Commands**:

```bash
# Deploy to Node B
ssh workers-b.ktrdr.home.mynerd.place 'cd /opt/ktrdr-workers-b && docker compose -f docker-compose.workers.yml up -d'

# Deploy to Node C
ssh workers-c.ktrdr.home.mynerd.place 'cd /opt/ktrdr-workers-c && docker compose -f docker-compose.workers.yml up -d'

# Verify registration
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq
```

**Acceptance Criteria**:

- [x] CPU workers running on Node B
- [x] CPU workers running on Node C
- [x] GPU training worker running on GPU VM
- [x] All workers registered with backend (5 workers: 2 backtest, 3 training)
- [x] Workers show as AVAILABLE

**Verified Workers (2025-12-06)**:

| Worker ID | Type | Endpoint | Status |
|-----------|------|----------|--------|
| training-worker-22c2939c | training | 10.42.1.13:5002 (GPU VM) | available |
| backtesting-worker-df53cf77 | backtesting | workers-b:5003 | available |
| training-worker-d4f2a0da | training | workers-b:5005 | available |
| backtesting-worker-b1944d7e | backtesting | workers-c:5003 | available |
| training-worker-95355759 | training | workers-c:5005 | available |

**Note**: GPU worker currently registers with `gpu: false`. Fix planned for next release to enable GPU-priority routing.

---

### Task 5.9: Deploy GPU Worker

**Goal**: GPU worker running on GPU VM

**Status**: PENDING

**Commands**:

```bash
# Deploy GPU worker
ssh ktrdr-gpuworker.ktrdr.home.mynerd.place 'cd /opt/ktrdr-gpu && docker compose -f docker-compose.gpu-worker.yml up -d'

# Verify registration (should show gpu: true)
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq '.[] | select(.capabilities.gpu == true)'
```

**Acceptance Criteria**:

- [ ] GPU worker running
- [ ] Registered with `gpu: true` capability
- [ ] Training operations route to GPU worker preferentially

---

### Task 5.10: Verify Grafana Dashboards

**Goal**: Dashboards display data correctly

**Status**: COMPLETED (2025-12-06)

**Issues Fixed**:

1. **Missing dashboards**: Dashboard JSON files weren't deployed. Fixed by copying from `/deploy/shared/grafana/dashboards/`.

2. **Datasource UID mismatch**: Dashboards expect `uid: prometheus` but Grafana auto-generated different UID. Fixed by adding explicit `uid: prometheus` in datasources.yml.

3. **Prometheus metrics path**: `/metrics` returns 307 redirect. Fixed by using `/metrics/` in prometheus.yml.

**Verification Results (2025-12-06)**:

Prometheus Targets:

| Job | Instance | Health |
|-----|----------|--------|
| ktrdr-backend | backend:8000 | UP |
| ktrdr-workers-b | workers-b:5003 | UP |
| ktrdr-workers-b | workers-b:5005 | UP |
| ktrdr-workers-c | workers-c:5003 | UP |
| ktrdr-workers-c | workers-c:5005 | UP |
| ktrdr-gpu-worker | ktrdr-gpuworker:5005 | DOWN (wrong port, actual is 5002) |

Grafana Datasources:

- `prometheus` (Prometheus) ✅
- `jaeger` (Jaeger) ✅

Grafana Dashboards:

- KTRDR System Overview ✅
- KTRDR Worker Status ✅
- KTRDR Operations Dashboard ✅

**Known Issue**: Prometheus config has GPU worker on port 5005, but actual port is 5002. Fix in next release.

**Acceptance Criteria**:

- [x] Prometheus targets show UP (active workers)
- [x] Grafana datasources have correct UIDs
- [x] System Overview dashboard shows data
- [x] Worker Status dashboard shows data
- [x] Operations dashboard shows data

---

### Task 5.11: Verify Full System

**Goal**: End-to-end system verification

**Status**: COMPLETED (2025-12-06)

**Commands**:

```bash
# 1. Check registered workers
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq

# 2. Check Prometheus targets
curl http://backend.ktrdr.home.mynerd.place:9090/api/v1/targets | jq '.data.activeTargets[] | {job: .labels.job, health: .health}'

# 3. Run test operation
# (via CLI or API)

# 4. Check Jaeger for traces
curl http://backend.ktrdr.home.mynerd.place:16686/api/services | jq

# 5. Verify Grafana dashboards show data
# Open http://grafana.ktrdr.home.mynerd.place:3000
```

**Verification Results (2025-12-06)**:

- Backend health: OK (v1.0.7.2)
- Workers registered: 5 (all AVAILABLE)
- Prometheus targets: 5 UP (active workers)
- Jaeger services: `ktrdr-api` receiving traces
- Grafana: All 3 dashboards operational

**Acceptance Criteria**:

- [x] All workers registered
- [x] Prometheus shows active targets UP
- [x] Sample operation completes successfully (training + backtesting tested)
- [x] Traces visible in Jaeger
- [x] Grafana dashboards show real data

---

### Task 5.12: Document Operational Procedures

**File**: Update `docs/architecture/pre-prod-deployment/OPERATIONS.md`

**Goal**: Complete operational documentation

**Acceptance Criteria**:

- [ ] All operational procedures documented
- [ ] Clear step-by-step instructions
- [ ] Troubleshooting guide complete

---

## Validation

**Final System Verification**:

```bash
# 1. All services healthy
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/health

# 2. Workers registered (expected: 4+ workers)
curl http://backend.ktrdr.home.mynerd.place:8000/api/v1/workers | jq 'length'

# 3. Prometheus targets UP
curl -s http://backend.ktrdr.home.mynerd.place:9090/api/v1/targets | \
  jq '[.data.activeTargets[] | select(.health=="up")] | length'

# 4. Grafana dashboards
# Open http://grafana.ktrdr.home.mynerd.place:3000
# Verify all 3 dashboards show data
```

---

## Success Criteria

- [x] Repository restructured per design (Task 5.0 - already done)
- [x] All LXCs operational (Core, Workers-B, Workers-C)
- [x] GPU Worker VM operational
- [x] DNS resolving correctly
- [x] NFS shared storage working (with proper permissions)
- [x] Core stack deployed and healthy
- [x] CPU workers deployed on Nodes B & C
- [x] GPU training worker deployed
- [x] All workers registered with backend (5 workers)
- [x] Prometheus scraping all targets (active workers)
- [x] **Grafana dashboards showing data**
- [x] Jaeger receiving traces
- [ ] Documentation complete (Task 5.12 in progress)

**Known Issues for Future Releases**:

1. GPU worker registers with `gpu: false` (should be `gpu: true` for priority routing)
2. Prometheus GPU worker target on wrong port (5005 vs actual 5002)

---

## Dependencies

**Depends on**:

- Project 2 (CI/CD & GHCR) - need images to pull
- Project 3 (Observability Dashboards) - dashboards to deploy
- Project 4 (Secrets & Deployment CLI) - deployment commands

**Blocks**: Nothing (final project)

---

## Notes

- LXC provisioning is manual (per DESIGN.md)
- LXC nesting must be enabled for Docker-in-LXC
- Workers use `python -m uvicorn` (not direct `uvicorn`)
- Prometheus requires `/metrics/` (trailing slash) due to FastAPI redirect
- Grafana datasources must have explicit UIDs matching dashboard expectations

---

**Previous Project**: [Project 4: Secrets & Deployment CLI](PLAN_4_SECRETS_CLI.md)
