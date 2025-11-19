# Pre-Production Deployment Architecture
## Technical Specifications

**Version**: 1.0
**Status**: Architecture Draft
**Date**: 2025-11-16

---

## Scope

**This document contains**: Docker Compose files, environment variables, CLI implementation, monitoring configs

**Note**: Configuration files in this directory are **specification templates**. During implementation, they will be copied to the repository root for local testing and to LXCs for deployment.

**See [OPERATIONS.md](OPERATIONS.md) for**: LXC provisioning, network setup, backup procedures, disaster recovery

**Design rationale**: See [DESIGN.md](DESIGN.md)

---

## Docker Compose - Core Stack

**File Location (LXC)**: `/opt/ktrdr-core/docker-compose.core.yml`

**File Location (Spec)**: `docker-compose.core.yml`

**Services**:

- `db` - PostgreSQL + TimescaleDB with health checks
- `backend` - KTRDR backend API, connected to db and shared storage
- `prometheus` - Metrics collection with 90d retention
- `grafana` - Dashboards with auto-provisioned datasources
- `jaeger` - Distributed tracing with OTLP collector
- `nfs-server` - Shared storage exports

**Networks**: `ktrdr-core` (bridge)

**Volumes**: `postgres_data`, `prometheus_data`, `grafana_data`

**Key Configuration**:

- Backend exposed on port 8000
- Grafana exposed on port 3000
- Jaeger UI on 16686, OTLP on 4317
- NFS export at `/srv/ktrdr-shared`
- All services connected to observability stack (OTLP endpoint)

See [`docker-compose.core.yml`](docker-compose.core.yml) for complete configuration.

---

## Docker Compose - Worker Stack

**File Location (LXC)**: `/opt/ktrdr-workers-{b,c}/docker-compose.workers.yml`

**File Location (Spec)**: `docker-compose.workers.yml`

**Services**:

- `backtest-worker` - Backtesting operations (CPU-bound, 1 CPU / 3GB per replica)
- `training-worker` - Training operations (CPU-bound, 2 CPU / 5GB per replica)

**Image Strategy**: Workers use the **same `ktrdr-backend` image** as the backend service, not a separate `ktrdr-worker` image. Different entry points are specified via uvicorn command arguments.

**Networks**: `ktrdr-workers` (bridge)

**Key Configuration**:

- Profile-based scaling with explicit service definitions
- Port allocation (sequential): 5003-5008 (see table below)
- Workers have database access for checkpointing
- Workers connect to backend at `http://backend.ktrdr.home.mynerd.place:8000`
- Workers self-register via `WORKER_PUBLIC_BASE_URL` (e.g., `http://workers-b.ktrdr.home.mynerd.place:5003`)
- **Worker URL Requirement**: Workers MUST read `WORKER_PUBLIC_BASE_URL` from environment (not auto-detect)
- NFS mount at `/mnt/ktrdr-shared` for shared storage
- All workers send traces to Jaeger at core LXC

**Port Allocation Table**:

| Worker | Port | Profile | Always Running? |
|--------|------|---------|-----------------|
| backtest-worker-1 | 5003 | default | Yes |
| backtest-worker-2 | 5004 | scale-2 | No (profile) |
| training-worker-1 | 5005 | default | Yes |
| training-worker-2 | 5006 | scale-2 | No (profile) |
| backtest-worker-3 | 5007 | scale-3 | No (profile) |
| training-worker-3 | 5008 | scale-3 | No (profile) |

**Scaling Examples**:
- Default: `docker compose up -d` → 2 workers (1 backtest, 1 training)
- Scale to 2 each: `docker compose --profile scale-2 up -d` → 4 workers
- Scale to 3 each: `docker compose --profile scale-2 --profile scale-3 up -d` → 6 workers

See [`docker-compose.workers.yml`](docker-compose.workers.yml) for complete configuration.

---

## Environment Variables

**Comprehensive Documentation**: See [ENV_VARS.md](ENV_VARS.md) for complete variable reference, validation rules, and security guidelines.

**Hybrid Configuration Model** (No Secrets At Rest):
- **Homelab**: `.env.core` and `.env.workers` files contain **non-secret config only** (safe to commit)
  - Secrets (DB_PASSWORD, JWT_SECRET, etc.) injected inline by CLI at deploy time
  - [.env.core](.env.core) - Core stack non-secret configuration
  - [.env.workers](.env.workers) - Worker stack non-secret configuration (customize per node)
- **Local Dev**: `.env.dev` contains both config and secrets (in .gitignore)
  - [.env.dev.example](.env.dev.example) - Template for local development

### Core Stack (Summary)

**Database**:

- `DB_HOST=db`
- `DB_PORT=5432`
- `DB_NAME=ktrdr`
- `DB_USER=<secret>`
- `DB_PASSWORD=<secret>`

**Backend**:

- `JWT_SECRET=<secret>` (min 32 chars)
- `OTLP_ENDPOINT=http://jaeger:4317`
- `SHARED_MOUNT_PATH=/mnt/shared`

**Monitoring**:

- `GF_ADMIN_PASSWORD=<secret>`

**Registry**:

- `IMAGE_TAG=sha-<7-char-sha>` (from CI, e.g., `sha-a1b2c3d`)

### Worker Stack (Summary)

**Workers**:

- `KTRDR_API_URL=http://backend.ktrdr.home.mynerd.place:8000`
- `WORKER_TYPE=backtesting` (or `training`)
- `WORKER_PORT=5003` (or `5004`)
- **`WORKER_PUBLIC_BASE_URL=http://workers-b.ktrdr.home.mynerd.place:5003`** (for self-registration)
- `WORKER_HOSTNAME=workers-b.ktrdr.home.mynerd.place` (node-specific)
- `SHARED_MOUNT_PATH=/mnt/shared`
- `OTLP_ENDPOINT=http://backend.ktrdr.home.mynerd.place:4317`
- `DB_HOST=backend.ktrdr.home.mynerd.place` (for checkpointing)
- `DB_PORT=5432`
- `DB_NAME=ktrdr`
- `DB_USER=<secret>`
- `DB_PASSWORD=<secret>`

**Note**: `WORKER_PUBLIC_BASE_URL` is critical for worker self-registration with the backend. It must be externally accessible from the core LXC.

---

## Deployment CLI

### Implementation

**Location**: `ktrdr/cli/commands/deploy.py` (new file)

```python
import click
import subprocess
import json
from typing import Dict

@click.group()
def deploy():
    """Deploy KTRDR to homelab infrastructure."""
    pass

@deploy.command()
@click.argument('service', type=click.Choice(['backend', 'db', 'all']))
def core(service):
    """Deploy core services to ktrdr-core LXC."""
    # 1. Fetch secrets from 1Password
    secrets = fetch_secrets_from_1password('ktrdr-homelab-core')

    # 2. Build env var dict
    env_vars = {
        'DB_NAME': 'ktrdr',
        'DB_USER': secrets['db_username'],
        'DB_PASSWORD': secrets['db_password'],
        'JWT_SECRET': secrets['jwt_secret'],
        'GF_ADMIN_PASSWORD': secrets['grafana_password'],
        'IMAGE_TAG': get_latest_sha_tag(),
    }

    # 3. SSH to core LXC and execute
    host = 'backend.ktrdr.home.mynerd.place'
    workdir = '/opt/ktrdr-core'
    command = f'docker compose pull {service} && docker compose up -d {service}'

    ssh_exec_with_env(host, workdir, env_vars, command)
    click.echo(f"✓ Deployed {service} to core LXC")

@deploy.command()
@click.argument('node', type=click.Choice(['B', 'C']))
def workers(node):
    """Deploy workers to ktrdr-workers-{node} LXC."""
    # Fetch DB secrets for workers (needed for checkpointing)
    secrets = fetch_secrets_from_1password('ktrdr-homelab-core')

    host = f'workers-{node.lower()}.ktrdr.home.mynerd.place'
    workdir = f'/opt/ktrdr-workers-{node.lower()}'

    env_vars = {
        'IMAGE_TAG': get_latest_sha_tag(),
        'BACKTEST_WORKER_REPLICAS': '1',
        'TRAINING_WORKER_REPLICAS': '1',
        'DB_USER': secrets['db_username'],
        'DB_PASSWORD': secrets['db_password'],
    }

    command = 'docker compose pull && docker compose up -d'
    ssh_exec_with_env(host, workdir, env_vars, command)
    click.echo(f"✓ Deployed workers to node {node}")

# Helper functions

def fetch_secrets_from_1password(item_name: str) -> Dict[str, str]:
    """Fetch secrets from 1Password using op CLI."""
    cmd = ['op', 'item', 'get', item_name, '--format', 'json']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    item = json.loads(result.stdout)

    secrets = {}
    for field in item['fields']:
        if field['type'] == 'CONCEALED':
            secrets[field['label']] = field['value']
    return secrets

def get_latest_sha_tag() -> str:
    """Get latest git SHA tag from local repo."""
    cmd = ['git', 'rev-parse', '--short', 'HEAD']
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    sha = result.stdout.strip()
    return f'sha-{sha}'

def ssh_exec_with_env(host: str, workdir: str, env_vars: Dict[str, str], command: str):
    """SSH to host, execute command with inline env vars."""
    # Build env string (quotes for safety)
    env_string = ' '.join([f"{k}='{v}'" for k, v in env_vars.items()])

    # Build full SSH command
    full_cmd = f'cd {workdir} && {env_string} {command}'
    ssh_cmd = ['ssh', host, full_cmd]

    # Execute
    subprocess.run(ssh_cmd, check=True)
```

### Registration with Main CLI

**File**: `ktrdr/cli/cli.py`

```python
from ktrdr.cli.commands.deploy import deploy

# Add to main CLI group
cli.add_command(deploy)
```

---

## Monitoring Configuration

### Prometheus

**File Location**: `monitoring/prometheus.yml`

**Scrape Targets**:

- `ktrdr-backend` - Backend API at `backend:8000`
- `ktrdr-workers-b` - Worker node B at `ktrdr-workers-b.internal:5003`, `:5004`, etc.
- `ktrdr-workers-c` - Worker node C at `ktrdr-workers-c.internal:5003`, `:5004`, etc.

**Configuration**:

- Scrape interval: 15s
- Retention: 90d (configured in compose file)

**Note**: Add/remove worker targets as replicas scale. Update `prometheus.yml` and redeploy: `ktrdr deploy core prometheus`.

See [`monitoring/prometheus.yml`](monitoring/prometheus.yml) for complete configuration.

---

### Grafana Datasources

**File Location**: `monitoring/grafana/datasources.yml`

**Datasources**:

- Prometheus (default) - `http://prometheus:9090`
- Jaeger - `http://jaeger:16686`

See [`monitoring/grafana/datasources.yml`](monitoring/grafana/datasources.yml) for complete configuration.

---

### Grafana Dashboards

**File Location**: `monitoring/grafana/dashboards.yml`

**Configuration**: Auto-provisioning from `/var/lib/grafana/dashboards`

**v1 Approach**: Manual dashboard creation as needed via Grafana UI

**Future Enhancement**: Pre-built dashboard JSON files for system overview, worker metrics, and database performance. See DESIGN.md "Future Enhancements".

See [`monitoring/grafana/dashboards.yml`](monitoring/grafana/dashboards.yml) for complete configuration.

---

## Storage Layout

### NFS Share Structure

**Path on core LXC**: `/srv/ktrdr-shared`

```
/srv/ktrdr-shared/
├── data/                    # Market data CSVs
│   ├── AAPL/
│   ├── EURUSD/
│   └── ...
├── results/                 # Training/backtest results
│   ├── backtest_<id>/
│   └── training_<id>/
├── models/                  # Trained models
│   └── <model_name>_<version>/
└── db-backups/              # PostgreSQL dumps
    └── ktrdr_YYYYMMDD.sql.gz
```

### Docker Volumes

**Core LXC**:

- `postgres_data` - PostgreSQL data
- `prometheus_data` - Prometheus TSDB
- `grafana_data` - Grafana dashboards

**Worker LXCs**: None (stateless)

---

## Network Configuration

### DNS Entries

**DNS configuration** per [ktrdr-dns-naming.md](ktrdr-dns-naming.md) using `ktrdr.home.mynerd.place` zone:

```
; Core services
backend.ktrdr.home.mynerd.place.     IN A    <Node A IP>
postgres.ktrdr.home.mynerd.place.    IN A    <Node A IP>
grafana.ktrdr.home.mynerd.place.     IN A    <Node A IP>
prometheus.ktrdr.home.mynerd.place.  IN A    <Node A IP>

; Worker nodes
workers-b.ktrdr.home.mynerd.place.   IN A    <Node B IP>
workers-c.ktrdr.home.mynerd.place.   IN A    <Node C IP>
```

**See**: [OPERATIONS.md](OPERATIONS.md) for DNS server setup

### Port Allocation

**Core LXC** (`ktrdr-core`):

- `8000` - Backend API (externally accessible)
- `3000` - Grafana UI (externally accessible)
- `16686` - Jaeger UI (externally accessible)
- `9090` - Prometheus (internal only)
- `5432` - PostgreSQL (internal only)
- `4317` - Jaeger OTLP (internal only)
- `2049` - NFS (accessible to workers)

**Worker LXCs**:

- `5003+` - Backtest workers (sequential per replica)
- `5004+` - Training workers (sequential per replica)

---

## Deployment Workflows

### Code Deployment

**Trigger**: Merge to `main`

```bash
# 1. CI builds and pushes images to GHCR (automatic)

# 2. Deploy core
ktrdr deploy core all

# 3. Deploy workers
ktrdr deploy workers B
ktrdr deploy workers C
```

### Secret Rotation

**Trigger**: Secret changed in 1Password

```bash
# Redeploy affected services (containers restart with new secrets)
ktrdr deploy core backend
ktrdr deploy workers B
ktrdr deploy workers C
```

### Scaling Workers (v2 - Future)

**v1 Approach**: Single worker per type per node. Additional capacity via additional nodes.

**Future Enhancement**: Multi-replica scaling, load balancing, auto-scaling based on queue depth. See DESIGN.md "Future Enhancements".

---

## Local Development Environment

**File**: `docker-compose.dev.yml`

**Purpose**: Fast local development on Mac with hot reload

**Key Features**:
- Hot reload mode (default): bind-mounted code, uvicorn --reload
- Image mode (testing): toggle to test with CI-built images
- Simplified networking: single Docker host, localhost access
- Optional workers: start with `--profile workers`

**Services**:
- `db` - PostgreSQL + TimescaleDB
- `backend` - Backend API with hot reload
- `prometheus` - Metrics (7d retention for dev)
- `grafana` - Dashboards
- `jaeger` - Tracing
- `backtest-worker` - Optional backtest worker (profile: workers)
- `training-worker` - Optional training worker (profile: workers)

**Usage**:

```bash
# Start core services only (default)
docker compose -f docker-compose.dev.yml up

# Start with workers for distributed testing
docker compose -f docker-compose.dev.yml --profile workers up

# Test with built images (image mode)
# 1. Build images: make build-backend TAG=local
# 2. Edit docker-compose.dev.yml: comment 'build:', uncomment 'image:' lines
# 3. docker compose -f docker-compose.dev.yml up
```

**Access**:
- Backend API: http://localhost:8000
- Grafana: http://localhost:3000
- Jaeger UI: http://localhost:16686
- Prometheus: http://localhost:9090

**Environment**: Copy [.env.dev.example](.env.dev.example) to `.env.dev` and customize for local development

See [`docker-compose.dev.yml`](docker-compose.dev.yml) for complete configuration.

---

## Container Registry Authentication

**GHCR Access**: Private repository requires authentication

**Prerequisites**:
1. GitHub Personal Access Token (PAT) with `read:packages` scope
2. Token stored in 1Password: vault `KTRDR Homelab Secrets`, item `ktrdr-homelab-core`, field `ghcr_token`

**Manual Authentication** (for testing):

```bash
# On LXC or local machine
echo $GHCR_TOKEN | docker login ghcr.io -u <github-username> --password-stdin

# Verify
docker pull ghcr.io/<github-username>/ktrdr-backend:latest
```

**Automated** (via deployment CLI):
- `ktrdr deploy` commands automatically authenticate before pulling images
- Uses token from 1Password
- See IMPLEMENTATION_PLAN.md Task 0.5 for details

---

## Related Documents

- [DESIGN.md](DESIGN.md) - Design decisions and rationale
- [OPERATIONS.md](OPERATIONS.md) - LXC provisioning, network setup, backups, DR
- [ENV_VARS.md](ENV_VARS.md) - Comprehensive environment variable reference
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) - Phased implementation tasks
- [.env.core](.env.core) - Core stack non-secret configuration (safe to commit)
- [.env.workers](.env.workers) - Worker stack non-secret configuration (safe to commit)
- [.env.dev.example](.env.dev.example) - Local development environment template
- [docker-compose.dev.yml](docker-compose.dev.yml) - Local development compose file

---

**Document End**
