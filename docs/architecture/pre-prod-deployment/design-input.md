# KTRDR Deployment & Secrets Management — Part 1: Foundations (Sections 0–3)

This document contains **Sections 0–3** of the full v4 design. Parts 2 and 3 will cover Sections 4–5 and Sections 6–9 respectively.

---

## 0. Open Questions & Decisions to Confirm

These are the remaining known "to discuss" items. Everything else in this doc reflects **current decisions**.

1. **DNS zone naming**

   - We will use existing BIND, but the exact zone name is still open (e.g. `home.lan`, `internal`, etc.).
   - Doc currently uses `.internal` as a placeholder.

2. **NFS storage backend & snapshot schedule**

   - We assume ZFS/btrfs or similar support for snapshots on Node A, but details (frequency, retention) are not yet defined.

3. **Exact RPO/RTO targets** beyond “\~24h acceptable”

   - As KTRDR matures, we’ll need a more precise target for DB + training artifacts.

4. **CI pipeline implementation details**

   - The design assumes GitHub Actions builds and pushes images to GHCR on merge to `main`, but does not yet prescribe workflow YAMLs.

---

## 1. Document Structure & Mental Model

This doc is organized from **high-level design → concrete flows → implementation notes**, to avoid mixing everything together.

- **Section 2 – High-Level Overview:** environments, topologies, major concepts.
- **Section 3 – Configuration & Secrets (Design):** what the app expects, how secrets flow conceptually.

Other sections are in Parts 2 and 3.

---

## 2. High-Level Overview

### 2.1 Environments

We support three logical environments, with a **single mental model**:

1. **Local Dev (Mac)**

   - Single host.
   - Docker Compose for all services.
   - Uvicorn hot-reload for fast iterations.
   - Secrets via `.env.dev` (manual or 1Password-assisted).

2. **Pre-Prod / Homelab (Proxmox)**

   - 3 Proxmox nodes on a VLAN.
   - LXCs with **static IPs on that VLAN**.
   - Each LXC runs Docker for its stack (core services vs workers).
   - Secrets pulled from 1Password at deploy time.
   - Images pulled from a **private GHCR registry**, built by CI.

3. **Future Production (Azure)**

   - Container-based compute, Key Vault, and Azure Container Registry.
   - Same env-var contract, different underlying mechanisms.

### 2.2 Core Design Principles

1. **Config via env vars only** — The application never hard-codes environment-specific settings.
2. **Secrets never live in git** — No plaintext or encrypted secrets in repos.
3. **Secrets source of truth: 1Password** — via an automation account.
4. **Images are the unit of deployment** — CI builds final images, homelab always pulls from GHCR.
5. **Homelab is the dress rehearsal** — Local → CI → GHCR → Homelab.
6. **Python dependency management via uv** — Locking ensures containers stay in sync with dev.

---

## 3. Configuration & Secrets (Design)

### 3.1 Config Types

1. **Non-sensitive config** (ports, log levels, feature flags).
2. **Sensitive config** (DB creds, API keys, registry creds, JWT secrets).
3. **Topology config** (backend URLs, worker callback URLs, NFS paths).

### 3.2 Application Contract (Env Vars)

Examples:

- **Database:** `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- **Worker → Backend:** `BACKEND_BASE_URL`
  - Dev: `http://backend:8000`
  - Homelab: `http://ktrdr-core.internal:8000`
- **Backend → Worker:** `WORKER_PUBLIC_BASE_URL`
- **Storage:** `SHARED_MOUNT_PATH=/mnt/shared`
- **Secrets:** `JWT_SECRET`, `BROKER_API_KEY`, etc.

Workers and backend **never guess** — all topology is explicit via env.

### 3.3 Secrets Lifecycle (Conceptual)

1. **Creation:** Secrets stored in 1Password infra vaults.
2. **Retrieval:** Deploy CLI calls `op` and loads secrets into memory.
3. **Injection:** Secrets passed to remote LXCs via **inline env vars** over SSH.
4. **At Rest:** No env files; secrets only stored in 1Password + Docker container config.
5. **Rotation:** Update 1Password → deploy again → containers updated.

### 3.4 Encryption at Rest

- Preferred pattern: **no persistent **``** file**.
- Deploy CLI runs commands like:

```bash
docker compose -f docker-compose.core.yml \
  DB_HOST=... DB_PASSWORD=... JWT_SECRET=... \
  up -d backend
```

- Secrets briefly exist in process memory and in Docker’s container config.
- Temporary env files are fallback-only (create → use → delete).

# KTRDR Deployment & Secrets Management — Part 2: Build & Dev (Sections 4–5)

This document contains **Sections 4–5** of the full v4 design. Part 1 covers Sections 0–3 (Foundations), and Part 3 will cover Sections 6–9 (Homelab & Ops).

---

## 4. Images & Versioning (Design)

### 4.1 Image Types

KTRDR uses two categories of container images:

#### **1. Base images (rarely change)**

- Based on a stable OS + Python runtime (currently Python **3.13**, potential upgrade to **3.14** later).
- Include:
  - Core system packages
  - Python interpreter
  - uv
  - Any build tools needed for installing dependencies
- Example tag:
  - `ghcr.io/<org>/ktrdr-base:py3.13-v1`

These images are rebuilt only when the underlying OS/Python/toolchain changes.

#### **2. Service images (backend, worker)**

- Built from the base image using `FROM ktrdr-base:py3.13-v1`.
- Install Python dependencies from a locked file.
- Copy application code.
- Example tags:
  - `ghcr.io/<org>/ktrdr-backend:<tag>`
  - `ghcr.io/<org>/ktrdr-worker:<tag>`

Services are rebuilt *only* when:

- Code changes
- Dependency lockfile changes (via uv)

---

### 4.2 Tagging Strategy

Because semantic versioning has not been strictly maintained historically, and because we rely heavily on CI, we adopt a simple, robust tagging model:

#### **Primary tag: Git SHA**

- Example: `sha-a1b2c3d`
- Advantages:
  - Globally unique
  - Immutable
  - Perfect mapping between deployed image and git commit
  - No risk of accidentally reusing version names

#### **Optional secondary semantic tags (later)**

- When KTRDR has a defined release cadence, tags like `v0.4.0` may be layered on top.
- Not mandatory for homelab or early deployments.

---

### 4.3 Dependency Management with uv

Dependency pain points identified:

- Dev and container deps drift out of sync.
- `requirements.txt` regeneration is manual + error‑prone.
- Uvicorn reloads code, but deps inside containers don't update.

To fix this, we standardize on **uv**.

#### **Guiding Principles**

- `pyproject.toml` is the **only** place where dependencies are declared.
- A lock step generates a deterministic dependency set.
- Containers **never** install deps directly from `pyproject.toml`.

#### **Workflow**

1. Developer edits dependencies via uv commands:

   ```bash
   uv add <package>
   ```

2. Developer runs:

   ```bash
   make deps-lock
   ```

   This will:

   - Call uv to resolve full dependency graph
   - Produce a lock artifact, likely:
     - `requirements.lock.txt` (pip-compatible)

3. Developer commits both:

   - `pyproject.toml`
   - `requirements.lock.txt`

4. Containers install using:

   ```dockerfile
   COPY requirements.lock.txt ./
   RUN pip install -r requirements.lock.txt
   ```

This ensures:

- Perfect reproducibility between dev and prod
- Fewer “works on my machine” issues

---

### 4.4 Where Builds Happen (CI-centric)

CI is the authoritative builder for deployable images.

#### **On merge to **``**:**

1. GitHub Actions checks out code
2. uv is installed
3. Dependencies resolved using lock file
4. Images built:
   - `ktrdr-backend`
   - `ktrdr-worker`
5. Images tagged with current short SHA:
   - `sha-abc1234`
6. Images pushed to **private GHCR**

Homelab pulls these tags directly during deployment.

#### **Local builds**

Used for experimentation or for local prod‑like testing. Examples:

```bash
make build-backend TAG=local
make build-worker TAG=local
```

Local builds **should not** overwrite CI tags.

---

## 5. Local Development (Mac)

### 5.1 Goals

- Fast feedback
- Minimal ceremony
- Safe secrets handling
- Same env contract as homelab
- Ability to test images locally

---

### 5.2 Compose & Config Layout (Dev)

The repo includes:

- `docker-compose.dev.yml` — references services, ports, volumes
- `env.dev.example` — template listing all required env vars

Git ignores:

- `.env.dev`
- `*.env.local`
- `*.secrets`

This prevents accidental secret commits.

---

### 5.3 Dev Secrets

Two supported modes:

#### **1. Manual **``** (default)**

- Developer copies the template:

  ```bash
  cp env.dev.example .env.dev
  ```

- Fills in:
  - DB creds
  - JWT secret
  - Broker keys
  - Internal URLs (simple for dev)

Compose references it via:

```yaml
env_file: .env.dev
```

#### **2. 1Password-assisted generation (optional, later)**

- Integrated into Python CLI:

  ```bash
  ktrdr deploy dev-local
  ```

- CLI reads from 1Password
- Writes `.env.dev`
- Mirrors homelab deployment logic

---

### 5.4 Hot Reload vs Image Mode

#### **Hot Reload (default dev workflow)**

- Backend runs with bind-mounted code
- Uvicorn uses `--reload`
- Workers can:
  - Run in containers using bind mounts, or
  - Run directly via:

    ```bash
    uv run python -m ktrdr.worker
    ```

This mode is fastest and preferred during active development.

#### **Image Mode (pre‑deployment testing)**

Useful before merging a PR or testing new infra features.

- Developer builds local images:

  ```bash
  make build-backend TAG=local
  make build-worker TAG=local
  ```

- `docker-compose.dev.yml` can be toggled to use:

  ```yaml
  image: ghcr.io/<org>/ktrdr-backend:local
  ```

This ensures local environment behaves similarly to homelab.

# KTRDR Deployment & Secrets Management — Part 3: Homelab & Ops (Sections 6–9)

This document contains **Sections 6–9** of the full v4 design. Part 1 covers Sections 0–3 (Foundations), and Part 2 covers Sections 4–5 (Build & Dev).

---

# 6. Homelab Topology & Networking

## 6.1 Proxmox & VLAN

The homelab consists of **3 Proxmox nodes** connected on a shared VLAN.

### Key Assumptions

- All LXC containers obtain **static IPs** on the homelab VLAN.
- Proxmox manages these static IP assignments.
- Network-level reliability is handled by Proxmox + your existing home network.

### Example IP layout

- `ktrdr-core` → `192.168.50.10`
- `ktrdr-workers-b` → `192.168.50.11`
- `ktrdr-workers-c` → `192.168.50.12`

Each LXC is reachable from the others using DNS names defined in BIND.

---

## 6.2 LXC Layout & Responsibilities

### **Node A (16 GB RAM)**

Runs the **core stack**, including:

- `db` — PostgreSQL + TimescaleDB
- `backend` — orchestrates workers and API traffic
- `prometheus` — metrics
- `grafana` — dashboards
- `jaeger` — traces
- `nfs-server` — shared storage for workers and backend
- *(optional later)* self‑hosted registry for offline mode

### **Node B (16 GB RAM)**

Runs the **worker pool B**:

- LXC `ktrdr-workers-b`
- Docker Compose defines several worker replicas (count tuned to CPU/RAM)

### **Node C (8 GB RAM)**

Runs **worker pool C**:

- LXC `ktrdr-workers-c`
- Fewer replicas than Node B due to lower resources

This split isolates the stateful services (DB, backend, NFS) on a dedicated node, maximizing worker performance on the remaining nodes.

---

## 6.3 DNS & Naming

You already run a **BIND DNS service** in the homelab.

We define stable DNS entries such as:

- `ktrdr-core.internal` → `192.168.50.10`
- `ktrdr-workers-b.internal` → `192.168.50.11`
- `ktrdr-workers-c.internal` → `192.168.50.12`

(`.internal` is a placeholder; the final zone name remains an open question.)

### Internal vs External Access

- Internal stack communication uses BIND DNS.
- External access (e.g. exposing Grafana) can be routed through Traefik.

---

## 6.4 Backend/Worker Network Contract

**All addressing is explicit and delivered via env vars.** Workers and backend never attempt to infer whether they are on the same Docker network or in separate LXCs.

### Inside `ktrdr-core` (Core LXC)

- Backend → DB: `db:5432` (Docker internal service name)

### Workers → Backend

Workers use:

```
BACKEND_BASE_URL=http://ktrdr-core.internal:8000
```

This allows all workers, regardless of node, to reach the backend consistently.

### Backend → Worker (callbacks)

Each worker instance exposes an endpoint on a known port (e.g. `9000`). Workers are configured with:

```
WORKER_PUBLIC_BASE_URL=http://ktrdr-workers-b.internal:9000
```

They send this value during registration. Backend stores this and uses it for:

- polling
- status queries
- long‑running job progress retrieval

This contract avoids any “guessing” and ensures the topology is explicitly encoded.

---

## 6.5 Shared Storage (NFS)

### Location

- NFS server runs \*\*inside \*\*\`\`.
- Exports: `/srv/ktrdr-shared`

### Clients

Each worker LXC mounts:

- `/srv/ktrdr-shared` → `/mnt/ktrdr-shared`

### Inside Containers

Docker services bind‑mount the host path:

- `/mnt/ktrdr-shared` → `/mnt/shared`

### Usage Examples

- Workers write results under: `/mnt/shared/results/<job_id>/...`
- Backend reads the same results
- DB snapshots stored under: `/mnt/shared/db-backups/`

Storage integrity is crucial because training results are expensive to recompute.

---

# 7. Homelab Deployment & Continuous Deployment

## 7.1 Stack Structure & Compose Files

Each LXC hosts its own stack with its own **docker‑compose** file.

### Core node (`ktrdr-core`)

`/opt/ktrdr-core/docker-compose.core.yml` defines:

- db
- backend
- prometheus
- grafana
- jaeger
- nfs-server

### Worker nodes (`ktrdr-workers-b`, `ktrdr-workers-c`)

`/opt/ktrdr-workers-*/docker-compose.workers.yml` defines:

- worker service
- number of replicas

Each stack is deployed independently.

---

## 7.2 `ktrdr` Python CLI Deployment Commands

Deployment is integrated directly into the existing **Python CLI**.

### Commands

- `ktrdr deploy core backend`
- `ktrdr deploy core all`
- `ktrdr deploy workers B`
- `ktrdr deploy workers C`

### What the CLI does

1. Reads secrets via `op` (1Password CLI)
2. Reads stack layout from a config file, e.g. `infra/homelab/stack-config.yml`
3. SSHes into the target LXC
4. Injects secrets and config via **inline env vars**
5. Runs:

   ```bash
   docker compose pull <service>
   docker compose up -d <service>
   ```

No `.env` file is stored on the LXC.

---

## 7.3 Env Injection Without Persistent Files

Preferred approach:

- All secrets supplied inline over SSH:

  ```bash
  DB_USER=... DB_PASSWORD=... JWT_SECRET=... \
  docker compose -f docker-compose.core.yml up -d backend
  ```

- No persistent `.env` file is created.
- Secrets exist only in:
  - The 1Password vault
  - The in‑memory environment of the deploy process
  - Docker’s container config

Fallback: temporary `.env` files created → used → deleted within the same SSH session.

---

## 7.4 Scaling Workers & Adding New Hosts

Worker capacity is controlled by a simple YAML config: `infra/homelab/worker-nodes.yml`

Example:

```yaml
worker_nodes:
  - name: B
    host: ktrdr-workers-b
    compose_path: /opt/ktrdr-workers-b/docker-compose.workers.yml
  - name: C
    host: ktrdr-workers-c
    compose_path: /opt/ktrdr-workers-c/docker-compose.workers.yml
```

### Adding a new worker node (e.g. `D`)

1. Create LXC `ktrdr-workers-d` on any Proxmox node.
2. Assign static IP + create DNS entry (e.g. `ktrdr-workers-d.internal`).
3. Create `/opt/ktrdr-workers-d/docker-compose.workers.yml` with appropriate worker replica count.
4. Add an entry to `worker-nodes.yml`:

   ```yaml
   - name: D
     host: ktrdr-workers-d
     compose_path: /opt/ktrdr-workers-d/docker-compose.workers.yml
   ```

5. Run:

   ```bash
   ktrdr deploy workers D
   ```

This approach avoids any code changes when adding capacity; all scaling is configuration‑driven.

---

# 8. Backups & Disaster Recovery

## 8.1 Priorities

1. **Database (critical)** — up to \~24h data loss acceptable today.
2. **Training/backtest artifacts (important)** — expensive to recompute.
3. **Configuration** — largely stored in git and Proxmox.

---

## 8.2 Database Backups

Database backups happen **inside**``.

### Daily logical backup

Use `pg_dump`:

```bash
pg_dump ktrdr | gzip > /mnt/shared/db-backups/ktrdr-$(date +%Y%m%d).sql.gz
```

- Stored on NFS so workers and core can access.
- Retention strategy configurable (e.g., keep 30 days).

### Optional: Proxmox LXC volume snapshots

- Faster full‑system recovery
- Can be scheduled via Proxmox UI

---

## 8.3 NFS Backups & Snapshots

Because training results are valuable:

- Use **ZFS/btrfs snapshots** on Node A for `/srv/ktrdr-shared` if possible.
- Optionally sync snapshots to:
  - External USB disk
  - NAS
  - Cloud storage (manual or scripted)

Snapshot strategy (example):

- Hourly snapshots (retain 24)
- Daily snapshots (retain 30)
- Weekly snapshots (retain 8)

---

## 8.4 Recovery Scenarios

### Scenario A: Worker node loss

1. Recreate LXC from template
2. Mount NFS share
3. Deploy workers using:

   ```bash
   ktrdr deploy workers <NodeName>
   ```

### Scenario B: `ktrdr-core` loss

1. Restore from Proxmox backup *or* recreate LXC
2. Restore DB from most recent `pg_dump` if needed
3. Mount NFS
4. Run:

   ```bash
   ktrdr deploy core all
   ```

### Scenario C: Logical DB corruption

- Restore from last known good `pg_dump`
- Accept RPO constraint (\~24h for now)

---

# 9. Future Azure Mapping (High-Level)

The homelab architecture maps cleanly to Azure services.

## 9.1 Compute Mapping

- **Backend + Workers** → Azure Container Apps or AKS
- **Observability** → Azure Monitor, Application Insights (or self‑hosted Grafana)

## 9.2 Secrets Mapping

- 1Password replaced by **Azure Key Vault**
- Deploy scripts replaced by Key Vault references + managed identities

## 9.3 Registry Mapping

- GHCR replaced or complemented by **Azure Container Registry (ACR)**
- CI can push to both GHCR + ACR if desired

## 9.4 Network & Topology Mapping

- Internal communication → Azure VNets + Private DNS Zones
- `*.internal` hostnames → Azure Private DNS

## 9.5 Infra as Code

- Use **Bicep** or **Terraform** to define:
  - Container Apps environments
  - Key Vault
  - VNet
  - ACR

The core principle remains the same: **code → CI builds image → registry → env vars inject config → containers run → secrets via a dedicated secrets manager.**

---

*End of Part 3 — Homelab & Ops*
