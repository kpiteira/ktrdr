# Pre-Production Deployment Design
## Containerized Homelab with Production Parity

**Version**: 1.0
**Status**: Design Approved
**Date**: 2025-11-16

---

## Executive Summary

This design establishes a **production-grade deployment architecture** for KTRDR across three environments: local development (Mac), pre-production homelab (Proxmox), and future production (Azure). The system uses a **hybrid LXC + Docker architecture** on Proxmox, with secrets managed via 1Password and images built/distributed via CI to GitHub Container Registry.

**Key Principles**: Environment parity via env vars • Secrets never in git • Container-first deployment • Explicit configuration • Homelab as production rehearsal

---

## Design Goals

### Security & Secrets
- No secrets in git (no plaintext, no encrypted blobs)
- No persistent secret files (inline injection at deploy time)
- Single source of truth (1Password automation account)
- Auditable and rotatable (clear rotation process)

### Operational
- Fast local dev (docker compose up, hot reload)
- Low-ceremony deployment (single command per environment)
- Future Azure portability (stable env-var contract)
- Dependency parity (uv lock files ensure dev/prod sync)

---

## Environment Strategy

### 1. Local Dev (Mac)
- **Infrastructure**: Docker Compose on single host
- **Secrets**: `.env.dev` (manual or 1Password-assisted)
- **Purpose**: Rapid iteration, debugging
- **Optimization**: Speed over realism

### 2. Pre-Prod / Homelab (Proxmox)
- **Infrastructure**: 3 Proxmox nodes, LXC containers running Docker
- **Secrets**: 1Password → CLI → inline injection
- **Images**: Private GHCR, CI-built
- **Purpose**: Integration testing, production rehearsal
- **Topology**: Node A (core), Nodes B/C (workers)

### 3. Future Production (Azure)
- **Infrastructure**: Azure Container Apps/AKS
- **Secrets**: Azure Key Vault (replaces 1Password)
- **Images**: GHCR or Azure Container Registry
- **Parity**: Same env-var contract, different mechanisms

---

## Core Design Decisions

### Decision 1: LXC + Docker Hybrid
**Choice**: LXCs as node boundary, Docker inside LXCs

**Rationale**: LXC provides VM-like isolation with container efficiency, Proxmox management (snapshots, backups), and production parity (similar to cloud VMs). Docker enables CI-built images and easy replica scaling.

---

### Decision 2: Consolidated Core Services
**Choice**: All stateful services (DB, backend, observability, NFS) in single LXC

**Rationale**: Limited resources (12 cores total). Consolidation trades isolation for efficiency. Can split later if needed. Pre-prod prioritizes simplicity over HA.

---

### Decision 3: Inline Secrets Injection
**Choice**: No persistent `.env` files, secrets injected inline via SSH

**Flow**: 1Password → CLI memory → SSH + inline env vars → Docker container config

**Rationale**: No secrets on disk = no exposure risk. Production parity (Azure Key Vault pattern). Fast rotation (redeploy = new secrets).

**Trade-off**: More complex deployment, but secrets visible in `docker inspect` requires elevated privileges.

---

### Decision 4: CI-Built Images with SHA Tagging
**Choice**: CI builds images, tags with git SHA, pushes to GHCR

**Image Types**:
- Base: OS + Python 3.13 + uv (rarely changes)
- Service: App code + locked deps (frequent changes)

**Tag Strategy**: Primary = git SHA (unique, immutable), optional semantic versions later

**Worker Image Strategy**: Workers use the **same `ktrdr-backend` image**, not a separate `ktrdr-worker` image. Different entry points (backtest vs training) are specified via uvicorn command arguments. This simplifies CI (single image build), ensures version synchronization, and reflects the reality that workers are part of the backend codebase.

**Registry Authentication**: Private GHCR registry requires authentication. GitHub Personal Access Token (PAT) with `read:packages` scope stored in 1Password, CLI authenticates Docker before pulling images.

**Rationale**: No "works on my machine". Perfect reproducibility. CI as authoritative builder. Single image reduces build complexity and ensures workers/backend always in sync.

---

### Decision 5: Dependency Management via uv
**Choice**: `pyproject.toml` as source, `uv` locks, containers install from lock

**Workflow**: `uv add <pkg>` → `make deps-lock` → commit `pyproject.toml` + `requirements.lock.txt` → CI installs from lock

**Rationale**: Perfect dev/prod parity. No drift. Fewer surprises.

---

### Decision 6: Explicit Network Configuration
**Choice**: All topology in environment variables, no auto-discovery

**Contract**:
- Workers → Backend: `KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000`
- Workers self-registration: `WORKER_PUBLIC_BASE_URL=http://workers-b.ktrdr.home.mynerd.place:5003`
- Backend → DB: `DB_HOST=db` (Docker internal)
- Storage: `SHARED_MOUNT_PATH=/mnt/shared`

**DNS Naming**: Uses `ktrdr.home.mynerd.place` pattern per [ktrdr-dns-naming.md](ktrdr-dns-naming.md)

**Worker URL Requirement**: Workers MUST read `WORKER_PUBLIC_BASE_URL` from environment variable (not auto-detect). Auto-detection fails in distributed LXC topology.

**Rationale**: No guessing. Works whether services co-located (dev) or distributed (homelab). Explicit failures. `WORKER_PUBLIC_BASE_URL` enables backend to call back to workers for progress/status, critical for distributed worker architecture (per CLAUDE.md WorkerAPIBase pattern).

---

### Decision 7: NFS Shared Storage
**Choice**: NFS server in core LXC, workers mount via LXC-level NFS

**Flow**: Core exports `/srv/ktrdr-shared` → Workers mount to `/mnt/ktrdr-shared` → Containers bind-mount to `/mnt/shared`

**Use Cases**: Training artifacts, market data CSVs, DB backups

**Rationale**: Data locality (workers access results), backup simplicity (NFS snapshots), storage efficiency (single copy).

---

### Decision 8: Python CLI Deployment
**Choice**: Extend existing `ktrdr` CLI with deployment commands

**Commands**: `ktrdr deploy core <service>`, `ktrdr deploy workers <node>`

**Rationale**: Unified tooling. Secure secrets (in-memory only). Configuration-driven scaling.

---

### Decision 9: Manual LXC Provisioning
**Choice**: LXC creation, Docker install, network config are manual (out of scope)

**Rationale**: Infrequent (once per node). Deployment is frequent (daily). Automate frequent task, not infrequent. Can add IaC later.

---

### Decision 10: Pre-Deployment Validation
**Choice**: CLI validates all prerequisites before attempting deployment

**Checks**: DNS resolution, SSH connectivity, Docker installed, op CLI authenticated

**Rationale**: Fail fast with clear errors rather than mysterious deployment failures mid-way through process.

---

### Decision 11: Worker Scaling Strategy
**Choice**: Profile-based scaling with explicit service definitions (up to 3 workers per type)

**Port Allocation (Sequential)**:
- backtest-worker-1: `5003` (default, always running)
- backtest-worker-2: `5004` (scale-2 profile)
- backtest-worker-3: `5007` (scale-3 profile)
- training-worker-1: `5005` (default, always running)
- training-worker-2: `5006` (scale-2 profile)
- training-worker-3: `5008` (scale-3 profile)

**Scaling Commands**:
- 1 of each (default): `docker compose up -d`
- 2 of each: `docker compose --profile scale-2 up -d`
- 3 of each: `docker compose --profile scale-2 --profile scale-3 up -d`

**Rationale**: Explicit service definitions avoid docker-compose `--scale` port conflicts. Profile-based approach enables gradual capacity increase based on observed load. Each worker has unique port and self-registers independently with backend.

**Future Work**: Beyond 3 workers per type requires separate scaling specification or orchestration tooling (Swarm/K8s).

---

## Key Trade-Offs

### Consolidated Core vs Separate Services
**Decision**: Single core LXC for DB + backend + observability

**Cost**: Resource contention, shared failure domain
**Benefit**: Simpler management, lower overhead, network locality

**Reason**: 12 cores total across 3 nodes. Every core matters. Pre-prod optimizes for efficiency over HA.

---

### Inline Secrets vs .env Files
**Decision**: Inline injection, no persistent files

**Cost**: Complex deployment, secrets in `docker inspect`
**Benefit**: No disk exposure, audit trail, fast rotation

**Reason**: Security benefit outweighs complexity. Matches cloud-native patterns (Key Vault).

---

### Git SHA vs Semantic Versioning
**Decision**: Primary tag = git SHA

**Cost**: Less human-readable, no breaking change indicator
**Benefit**: Unique, immutable, perfect mapping, CI-friendly

**Reason**: SemVer requires discipline not historically maintained. SHA is foolproof.

---

### Manual Provisioning vs IaC
**Decision**: Manual LXC creation

**Cost**: Manual steps, not reproducible
**Benefit**: Simpler, flexible, one-time cost

**Reason**: LXCs created ~5 times total, deployments daily. Optimize frequent task.

---

## System Topology

**Node A** (16GB RAM): Core LXC → DB, Backend, Prometheus, Grafana, Jaeger, NFS
**Node B** (16GB RAM): Worker LXC → Backtest/Training replicas
**Node C** (8GB RAM): Worker LXC → Additional capacity

**Communication**:
- LXC-to-LXC: DNS (`backend.ktrdr.home.mynerd.place`, `workers-b.ktrdr.home.mynerd.place`)
- Docker-to-Docker: Service names (`db`, `prometheus`)
- External: Proxmox port forwards (Grafana, API)

---

## Success Criteria

### Functional
✅ Multi-environment deployment (local, homelab, Azure)
✅ Secure secrets (no git, auditable, rotatable)
✅ Container-based (CI builds, homelab pulls)
✅ Distributed architecture (core + workers across LXCs)
✅ Shared storage (NFS for artifacts)

### Non-Functional
✅ Fast local dev (sub-minute feedback)
✅ Low-ceremony deployment (single command)
✅ Dependency parity (identical locked deps)
✅ Production readiness (maps to Azure)
✅ Operational simplicity (config-driven scaling)

---

## Future Enhancements (v2 Roadmap)

### Backup Automation
- Automated daily pg_dump with retention management
- NFS snapshot automation (ZFS/btrfs)
- Off-site backup synchronization
- Documented DR testing procedures

**v1 Approach**: Manual backup procedures documented in OPERATIONS.md

### Deployment Rollback
- Automated rollback to previous image tag
- Health check verification post-deployment
- Automatic rollback on failed health checks

**v1 Approach**: Manual rollback via `IMAGE_TAG` override

### Worker Scaling & Performance (Beyond 3 Workers)
- Scaling beyond 3 workers per type per node
- Automatic load balancing across workers
- Resource optimization based on observed load
- Auto-scaling based on queue depth
- Orchestration tooling (Docker Swarm, Kubernetes)

**v1 Approach**: Profile-based scaling up to 3 workers per type (supports 1-3 of each via profiles)

### Monitoring & Alerting
- Grafana dashboard creation
- Alert rules for critical metrics
- Centralized log aggregation
- Anomaly detection

**v1 Approach**: Basic metrics collection, manual dashboard creation as needed

---

## Next Steps

1. **Implement** per [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) (phased tasks)
2. **Configure** per [ENV_VARS.md](ENV_VARS.md) (environment variables)
3. **Deploy** per [OPERATIONS.md](OPERATIONS.md) (operational procedures)

---

**Related Documents**:
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical specifications
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Phased implementation tasks
- [OPERATIONS.md](OPERATIONS.md) - Operational procedures
- [ENV_VARS.md](ENV_VARS.md) - Environment variable reference
- [ktrdr-dns-naming.md](ktrdr-dns-naming.md) - DNS naming strategy
- [.env.core](.env.core) - Core stack non-secret configuration
- [.env.workers](.env.workers) - Worker stack non-secret configuration
- [.env.dev.example](.env.dev.example) - Local development environment template
- [docker-compose.dev.yml](docker-compose.dev.yml) - Local development compose file

---

**Document End**
