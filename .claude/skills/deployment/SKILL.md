---
name: deployment
description: Use when starting or scaling the development environment, deploying to production Proxmox LXC, using patch deployments for preprod fixes, managing Docker Compose services, or running CLI commands.
---

# Deployment & Operations

Load this skill when:
- Starting or scaling the development environment
- Deploying to production (Proxmox)
- Using patch deployments for fast preprod fixes
- Managing workers or services

---

## Development Environment (Docker Compose)

### Starting the System

```bash
# Start complete local dev environment
docker compose up

# Start in background
docker compose up -d

# View logs
docker compose logs -f

# Stop all services
docker compose down

# Rebuild after Dockerfile changes
docker compose build

# Restart specific service
docker compose restart backend
```

### Scaling Workers

```bash
# Scale workers horizontally
docker-compose up -d --scale backtest-worker=5 --scale training-worker=3
```

### Host Services (for IB Gateway / GPU)

```bash
# IB Host Service (required for IB Gateway access)
cd ib-host-service && ./start.sh

# Training Host Service (GPU training)
cd training-host-service && ./start.sh
```

### Service URLs

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/api/v1/docs |
| ReDoc | http://localhost:8000/api/v1/redoc |
| Grafana | http://localhost:3000 |
| Jaeger UI | http://localhost:16686 |
| Prometheus | http://localhost:9090 |

---

## CLI Commands Reference

```bash
# Main entry point
ktrdr --help

# Data operations
ktrdr data show AAPL 1d --start-date 2024-01-01
ktrdr data load EURUSD 1h --start-date 2024-01-01 --end-date 2024-12-31
ktrdr data get-range AAPL 1d

# Training operations
ktrdr train config/strategies/example.yaml --start-date 2024-01-01 --end-date 2024-06-01

# Operations management
ktrdr ops
ktrdr status <operation-id>
ktrdr cancel <operation-id>

# IB Gateway integration
ktrdr ib test-connection
ktrdr ib check-status
```

---

## Patch Deployment (Fast Preprod Hotfixes)

For rapid iteration during preprod debugging instead of waiting for CI/CD (~30+ min):

```bash
# Step 1: Build CPU-only image locally (~6 min, ~500MB vs 3.3GB)
make docker-build-patch

# Step 2: Deploy to preprod
make deploy-patch

# With options:
uv run ktrdr deploy patch --dry-run     # Preview
uv run ktrdr deploy patch --verbose     # Detailed output
```

### How it works
- Builds CPU-only image using PyTorch's CPU index (excludes ~2.7GB CUDA)
- Transfers compressed tarball (~150MB) to each host via SCP
- Loads image and restarts services with `IMAGE_TAG=patch`
- GPU worker excluded (requires CUDA)

### When to use
- Debugging preprod issues requiring code changes
- Testing fixes before merging to main
- Any situation where CI/CD is too slow

### When NOT to use
- Production deployments (always use CI/CD)
- GPU worker patches (needs CUDA)

---

## Production Deployment (Proxmox LXC)

KTRDR uses Proxmox LXC containers for production — better performance and lower overhead than Docker.

### Why Proxmox LXC?

- **5-15% better performance** vs Docker
- **Lower memory footprint** per worker
- **Template-based cloning** for rapid scaling
- **Full OS environment** with systemd
- **Proxmox management tools** (backups, snapshots, monitoring)

### Quick Start

```bash
# 1. Create LXC template (one-time)
# See: docs/user-guides/deployment-proxmox.md

# 2. Clone and deploy backend
ssh root@proxmox "pct clone 900 100 --hostname ktrdr-backend"
ssh root@proxmox "pct set 100 --cores 4 --memory 8192 --net0 ip=192.168.1.100/24"
ssh root@proxmox "pct start 100"

# 3. Deploy code
./scripts/deploy/deploy-code.sh --target 192.168.1.100

# 4. Clone workers (5 example)
for i in {1..5}; do
  CTID=$((200 + i))
  IP=$((200 + i))
  ssh root@proxmox "pct clone 900 $CTID --hostname ktrdr-worker-$i"
  ssh root@proxmox "pct set $CTID --cores 4 --memory 8192 --net0 ip=192.168.1.$IP/24"
  ssh root@proxmox "pct start $CTID"
  ./scripts/deploy/deploy-code.sh --target 192.168.1.$IP
done

# 5. Verify
curl http://192.168.1.100:8000/api/v1/workers | jq
```

### Operations & Maintenance

```bash
# Deploy new version (rolling update, zero downtime)
./scripts/deploy/deploy-to-proxmox.sh --env production --version v1.5.2

# Add workers during high load
./scripts/lxc/provision-worker.sh --count 10 --start-id 211

# Health check all workers
./scripts/ops/system-status.sh

# View logs across all LXCs
./scripts/ops/view-logs.sh all "1 hour ago"

# Check resource usage
./scripts/ops/check-resources.sh
```

### When to Use Proxmox vs Docker

| Use Case | Recommended | Why |
|----------|-------------|-----|
| Local development | Docker Compose | Quick setup, easy iteration |
| Testing/staging | Docker Compose | Matches dev environment |
| Production | **Proxmox LXC** | Better performance |
| > 20 workers | **Proxmox LXC** | Lower overhead scales better |

---

## Verification Commands

```bash
# Check registered workers
curl http://localhost:8000/api/v1/workers | jq

# Check if host services are running
lsof -i :5001  # IB Host Service
lsof -i :5002  # Training Host Service

# Test connectivity from Docker
docker exec ktrdr-backend curl http://host.docker.internal:5001/health
docker exec ktrdr-backend curl http://host.docker.internal:5002/health

# Check environment in container
docker exec ktrdr-backend env | grep -E "(IB|TRAINING)"
```

---

## Documentation

- **Docker Development**: [docs/user-guides/deployment.md](docs/user-guides/deployment.md)
- **Proxmox Production**: [docs/user-guides/deployment-proxmox.md](docs/user-guides/deployment-proxmox.md)
- **CI/CD & Operations**: [docs/developer/cicd-operations-runbook.md](docs/developer/cicd-operations-runbook.md)
