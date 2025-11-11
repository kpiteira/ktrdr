# KTRDR CI/CD & Operations Runbook

**Version**: 1.0
**Date**: 2025-11-10
**Audience**: DevOps, SRE, Production Support, Senior Developers
**Purpose**: Production deployment automation and operational procedures

---

## Table of Contents

1. [Overview](#overview)
2. [Deployment Pipeline](#deployment-pipeline)
3. [Deployment Automation](#deployment-automation)
4. [Environment Management](#environment-management)
5. [Operations Procedures](#operations-procedures)
6. [Monitoring & Alerting](#monitoring--alerting)
7. [Incident Response](#incident-response)
8. [Rollback Procedures](#rollback-procedures)
9. [Common Operational Tasks](#common-operational-tasks)
10. [Security & Secrets Management](#security--secrets-management)
11. [Maintenance Windows](#maintenance-windows)

---

## Overview

This runbook defines the continuous deployment pipeline and operational procedures for KTRDR in production environments. It covers automated deployments, monitoring, incident response, and common operational tasks.

**Deployment Environments**:
- **Development**: Docker Compose on developer machines (local)
- **Staging**: Proxmox LXC cluster (test.ktrdr.internal)
- **Production**: Proxmox LXC cluster (prod.ktrdr.internal)

**Key Principles**:
- **Automation First**: All deployments automated via scripts
- **Zero Downtime**: Rolling updates for worker deployments
- **Fast Rollback**: Restore previous version within 5 minutes
- **Observable**: Comprehensive monitoring and alerting
- **Repeatable**: Idempotent deployment scripts

---

## Deployment Pipeline

### CI/CD Workflow

```
Developer → Git Push → GitHub Actions → Build & Test → Deploy
                          ↓               ↓             ↓
                       Lint/Test      Unit Tests    Staging
                       Type Check     Integration   Production
                       Build Docker   E2E Tests
```

### Deployment Stages

#### Stage 1: Continuous Integration (GitHub Actions)

**Trigger**: Push to any branch

**Actions**:
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Install dependencies
        run: uv sync
      - name: Run tests
        run: make ci
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

**Quality Gates**:
- ✅ All unit tests pass
- ✅ Code coverage > 80%
- ✅ Linting passes (Ruff)
- ✅ Type checking passes (MyPy)
- ✅ No security vulnerabilities (Bandit, Safety)

#### Stage 2: Build & Package

**Trigger**: Push to `main` or `release/*` branch

**Actions**:
- Build Docker images
- Tag with commit SHA and version
- Push to container registry (GitHub Container Registry)
- Create deployment artifacts

**Example**:
```bash
# Build backend image
docker build -t ghcr.io/your-org/ktrdr-backend:${COMMIT_SHA} \
             -t ghcr.io/your-org/ktrdr-backend:latest \
             -f docker/Dockerfile .

# Build worker image
docker build -t ghcr.io/your-org/ktrdr-worker:${COMMIT_SHA} \
             -t ghcr.io/your-org/ktrdr-worker:latest \
             -f docker/Dockerfile.worker .

# Push to registry
docker push ghcr.io/your-org/ktrdr-backend:${COMMIT_SHA}
docker push ghcr.io/your-org/ktrdr-worker:${COMMIT_SHA}
```

#### Stage 3: Deploy to Staging

**Trigger**: Successful build on `main` branch

**Actions**:
1. Deploy to staging Proxmox cluster
2. Run smoke tests
3. Run integration tests
4. Verify worker registration
5. Run sample backtest/training operations

**Approval**: Automatic (if all tests pass)

#### Stage 4: Deploy to Production

**Trigger**: Manual approval after staging validation

**Actions**:
1. Create deployment plan
2. Notify team (Slack, PagerDuty)
3. Deploy to production using rolling update
4. Monitor for errors (5-minute observation period)
5. Mark deployment complete

**Approval**: Manual (DevOps or SRE approval required)

---

## Deployment Automation

### One-Command Deployment Script

**Script**: `scripts/deploy/deploy-to-proxmox.sh`

**Usage**:
```bash
# Deploy to staging
./scripts/deploy/deploy-to-proxmox.sh --env staging --version v1.5.2

# Deploy to production
./scripts/deploy/deploy-to-proxmox.sh --env production --version v1.5.2 --confirm

# Dry run (show what would be deployed)
./scripts/deploy/deploy-to-proxmox.sh --env production --version v1.5.2 --dry-run
```

**Script Features**:
- Pre-deployment validation (version exists, environment accessible)
- Rolling update (workers updated one at a time)
- Health checks after each worker update
- Automatic rollback on failure
- Deployment summary and logs

### Deployment Script Structure

```bash
#!/bin/bash
# scripts/deploy/deploy-to-proxmox.sh

set -euo pipefail

# Configuration
ENVIRONMENT=${1:?Environment required (staging|production)}
VERSION=${2:?Version required (e.g., v1.5.2)}
CONFIRM=${3:-false}

# Environment-specific configuration
if [ "$ENVIRONMENT" = "staging" ]; then
    PROXMOX_HOST="proxmox-staging.internal"
    BACKEND_CTID=100
    WORKER_CTIDS=(201 202 203 204 205)
elif [ "$ENVIRONMENT" = "production" ]; then
    PROXMOX_HOST="proxmox-prod.internal"
    BACKEND_CTID=100
    WORKER_CTIDS=(201 202 203 204 205 206 207 208 209 210)
else
    echo "Invalid environment: $ENVIRONMENT"
    exit 1
fi

# Pre-deployment validation
validate_deployment() {
    echo "=== Pre-Deployment Validation ==="

    # Check version exists
    if ! git rev-parse "$VERSION" >/dev/null 2>&1; then
        echo "ERROR: Version $VERSION does not exist"
        exit 1
    fi

    # Check Proxmox connectivity
    if ! ssh "root@$PROXMOX_HOST" "pct list" >/dev/null 2>&1; then
        echo "ERROR: Cannot connect to Proxmox host $PROXMOX_HOST"
        exit 1
    fi

    # Check backend is running
    if ! ssh "root@$PROXMOX_HOST" "pct status $BACKEND_CTID" | grep -q "running"; then
        echo "ERROR: Backend container $BACKEND_CTID is not running"
        exit 1
    fi

    echo "✅ Pre-deployment validation passed"
}

# Deploy backend
deploy_backend() {
    echo "=== Deploying Backend (CT $BACKEND_CTID) ==="

    # Deploy code
    ssh "root@$PROXMOX_HOST" "pct exec $BACKEND_CTID -- bash" <<EOF
        cd /opt/ktrdr
        git fetch
        git checkout $VERSION
        uv sync
        systemctl restart ktrdr-backend
EOF

    # Wait for backend to be healthy
    sleep 10
    BACKEND_IP=$(ssh "root@$PROXMOX_HOST" "pct exec $BACKEND_CTID -- hostname -I" | awk '{print $1}')

    if curl -sf "http://$BACKEND_IP:8000/api/v1/health" >/dev/null; then
        echo "✅ Backend deployed successfully"
    else
        echo "ERROR: Backend health check failed"
        exit 1
    fi
}

# Deploy workers (rolling update)
deploy_workers() {
    echo "=== Deploying Workers (Rolling Update) ==="

    for CTID in "${WORKER_CTIDS[@]}"; do
        echo "Deploying worker CT $CTID..."

        # Check if worker is idle
        WORKER_IP=$(ssh "root@$PROXMOX_HOST" "pct exec $CTID -- hostname -I" | awk '{print $1}')
        WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status // "unknown"')

        if [ "$WORKER_STATUS" = "busy" ]; then
            echo "⚠️  Worker $CTID is busy, waiting..."
            # Wait up to 5 minutes for worker to become idle
            for i in {1..60}; do
                sleep 5
                WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status // "unknown"')
                if [ "$WORKER_STATUS" != "busy" ]; then
                    break
                fi
            done

            if [ "$WORKER_STATUS" = "busy" ]; then
                echo "ERROR: Worker $CTID still busy after 5 minutes"
                exit 1
            fi
        fi

        # Deploy code
        ssh "root@$PROXMOX_HOST" "pct exec $CTID -- bash" <<EOF
            cd /opt/ktrdr
            systemctl stop ktrdr-worker
            git fetch
            git checkout $VERSION
            uv sync
            systemctl start ktrdr-worker
EOF

        # Wait for worker to register
        sleep 10

        # Verify registration
        if curl -s "http://$BACKEND_IP:8000/api/v1/workers" | \
           jq -e ".[] | select(.endpoint_url==\"http://$WORKER_IP:5003\")" >/dev/null; then
            echo "✅ Worker $CTID deployed and registered"
        else
            echo "ERROR: Worker $CTID failed to register"
            exit 1
        fi
    done

    echo "✅ All workers deployed successfully"
}

# Main deployment flow
main() {
    echo "=== KTRDR Deployment ==="
    echo "Environment: $ENVIRONMENT"
    echo "Version: $VERSION"
    echo "Backend: CT $BACKEND_CTID"
    echo "Workers: ${WORKER_CTIDS[*]}"
    echo ""

    if [ "$CONFIRM" != "true" ] && [ "$ENVIRONMENT" = "production" ]; then
        read -p "Deploy to PRODUCTION? (yes/no): " CONFIRM_INPUT
        if [ "$CONFIRM_INPUT" != "yes" ]; then
            echo "Deployment cancelled"
            exit 0
        fi
    fi

    validate_deployment
    deploy_backend
    deploy_workers

    echo ""
    echo "=== Deployment Complete ==="
    echo "Environment: $ENVIRONMENT"
    echo "Version: $VERSION"
    echo "Time: $(date)"
}

main
```

### Worker Update Without Downtime

**Strategy**: Rolling update with health checks

```bash
# scripts/deploy/rolling-update-workers.sh

for WORKER_IP in 192.168.1.{201..210}; do
    echo "Updating worker $WORKER_IP..."

    # 1. Check if idle
    if curl -s "http://$WORKER_IP:5003/health" | jq -e '.worker_status == "idle"' >/dev/null; then
        # 2. Stop worker service
        ssh "root@$WORKER_IP" "systemctl stop ktrdr-worker"

        # 3. Update code
        rsync -avz --delete /opt/ktrdr/ "root@$WORKER_IP:/opt/ktrdr/"

        # 4. Restart worker
        ssh "root@$WORKER_IP" "systemctl start ktrdr-worker"

        # 5. Wait for registration
        sleep 10

        # 6. Verify
        if curl -s "http://192.168.1.100:8000/api/v1/workers" | \
           jq -e ".[] | select(.endpoint_url==\"http://$WORKER_IP:5003\") | .status == \"AVAILABLE\"" >/dev/null; then
            echo "✅ Worker $WORKER_IP updated"
        else
            echo "ERROR: Worker $WORKER_IP failed health check"
            exit 1
        fi
    else
        echo "⚠️  Worker $WORKER_IP is busy, skipping (will retry later)"
    fi
done
```

---

## Environment Management

### Environment Configuration

**Staging**:
```bash
# /opt/ktrdr/.env.staging
ENVIRONMENT=staging
KTRDR_API_URL=http://192.168.2.100:8000
LOG_LEVEL=DEBUG

# Host services
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://192.168.2.21:5001

# Data paths
DATA_DIR=/data/ktrdr/staging
MODELS_DIR=/models/ktrdr/staging
```

**Production**:
```bash
# /opt/ktrdr/.env.production
ENVIRONMENT=production
KTRDR_API_URL=http://192.168.1.100:8000
LOG_LEVEL=INFO

# Host services
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://192.168.1.21:5001

# Data paths
DATA_DIR=/data/ktrdr/production
MODELS_DIR=/models/ktrdr/production
```

### Environment Validation Script

```bash
# scripts/validate-environment.sh

#!/bin/bash
set -euo pipefail

ENVIRONMENT=${1:?Environment required}
ENV_FILE="/opt/ktrdr/.env.$ENVIRONMENT"

echo "=== Validating $ENVIRONMENT environment ==="

# Check environment file exists
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file $ENV_FILE not found"
    exit 1
fi

# Source environment
set -a
source "$ENV_FILE"
set +a

# Validate required variables
REQUIRED_VARS=(
    "KTRDR_API_URL"
    "DATA_DIR"
    "MODELS_DIR"
)

for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR:-}" ]; then
        echo "ERROR: Required variable $VAR not set"
        exit 1
    fi
done

# Validate paths exist
for PATH_VAR in DATA_DIR MODELS_DIR; do
    if [ ! -d "${!PATH_VAR}" ]; then
        echo "ERROR: Directory ${!PATH_VAR} does not exist"
        exit 1
    fi
done

# Validate backend connectivity
if ! curl -sf "$KTRDR_API_URL/api/v1/health" >/dev/null; then
    echo "ERROR: Cannot reach backend at $KTRDR_API_URL"
    exit 1
fi

echo "✅ Environment validation passed"
```

---

## Operations Procedures

### Starting the System

**Complete System Startup**:
```bash
# 1. Start backend
ssh root@proxmox-prod "pct start 100"
sleep 10

# 2. Verify backend is healthy
curl http://192.168.1.100:8000/api/v1/health

# 3. Start all workers
ssh root@proxmox-prod "for i in {201..210}; do pct start \$i; done"
sleep 30

# 4. Verify worker registration
curl http://192.168.1.100:8000/api/v1/workers | jq -r '.[] | "\(.worker_id): \(.status)"'

# 5. Start GPU training host (if applicable)
ssh root@gpu-host "systemctl start ktrdr-training-host"

# 6. Start IB host service (if applicable)
ssh root@ib-host "systemctl start ktrdr-ib-host"

# 7. Verify complete system
curl http://192.168.1.100:8000/api/v1/workers/health | jq
```

### Stopping the System

**Graceful Shutdown**:
```bash
# 1. Stop accepting new operations (optional - implement drain endpoint)
# curl -X POST http://192.168.1.100:8000/api/v1/admin/drain

# 2. Wait for active operations to complete
echo "Waiting for operations to complete..."
while true; do
    ACTIVE=$(curl -s "http://192.168.1.100:8000/api/v1/operations?status=running" | jq '.operations | length')
    if [ "$ACTIVE" -eq 0 ]; then
        break
    fi
    echo "  $ACTIVE operations still running..."
    sleep 10
done

# 3. Stop workers
ssh root@proxmox-prod "for i in {201..210}; do pct stop \$i; done"

# 4. Stop backend
ssh root@proxmox-prod "pct stop 100"

# 5. Stop host services
ssh root@gpu-host "systemctl stop ktrdr-training-host"
ssh root@ib-host "systemctl stop ktrdr-ib-host"

echo "✅ System stopped gracefully"
```

### Adding Workers During High Load

**Dynamic Scaling**:
```bash
# 1. Identify available capacity
CURRENT_WORKERS=$(curl -s http://192.168.1.100:8000/api/v1/workers | jq -r '.[] | select(.worker_type=="backtesting") | .worker_id' | wc -l)
echo "Current backtest workers: $CURRENT_WORKERS"

# 2. Clone new workers from template
for i in {11..15}; do
    CTID=$((200 + i))
    IP=$((200 + i))

    echo "Creating worker $i (CT $CTID)..."

    # Clone
    ssh root@proxmox-prod "pct clone 900 $CTID --hostname ktrdr-worker-bt-$i --full"

    # Configure
    ssh root@proxmox-prod "pct set $CTID --cores 4 --memory 8192 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.$IP/24,gw=192.168.1.1"

    # Start
    ssh root@proxmox-prod "pct start $CTID"
    sleep 10

    # Deploy code
    rsync -avz /opt/ktrdr/ root@192.168.1.$IP:/opt/ktrdr/

    # Configure worker
    ssh root@192.168.1.$IP "cat > /opt/ktrdr/.env << EOF
KTRDR_API_URL=http://192.168.1.100:8000
WORKER_ID=ktrdr-worker-bt-$i
WORKER_TYPE=backtesting
WORKER_PORT=5003
WORKER_ENDPOINT_URL=http://192.168.1.$IP:5003
WORKER_CORES=4
WORKER_MEMORY_GB=8
LOG_LEVEL=INFO
DATA_DIR=/data/ktrdr
MODELS_DIR=/models/ktrdr
EOF"

    # Start worker service
    ssh root@192.168.1.$IP "systemctl enable ktrdr-worker && systemctl start ktrdr-worker"

    # Verify
    sleep 10
    if curl -s http://192.168.1.100:8000/api/v1/workers | jq -e ".[] | select(.endpoint_url==\"http://192.168.1.$IP:5003\")" >/dev/null; then
        echo "✅ Worker $i deployed"
    else
        echo "ERROR: Worker $i registration failed"
    fi
done

# 3. Verify new capacity
NEW_WORKERS=$(curl -s http://192.168.1.100:8000/api/v1/workers | jq -r '.[] | select(.worker_type=="backtesting") | .worker_id' | wc -l)
echo "New backtest worker count: $NEW_WORKERS"
```

### Removing Workers for Maintenance

**Drain and Remove**:
```bash
# 1. Select worker to remove
WORKER_IP=192.168.1.210
CTID=210

# 2. Check if idle
WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status')

if [ "$WORKER_STATUS" = "busy" ]; then
    echo "Worker is busy. Waiting for operation to complete..."

    # Wait up to 30 minutes
    for i in {1..360}; do
        sleep 5
        WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status')
        if [ "$WORKER_STATUS" != "busy" ]; then
            break
        fi
    done
fi

# 3. Stop worker
ssh root@proxmox-prod "pct stop $CTID"

# 4. Wait for backend to remove from registry (5 minutes)
echo "Waiting for backend to remove worker from registry..."
sleep 300

# 5. Verify removed
if ! curl -s http://192.168.1.100:8000/api/v1/workers | jq -e ".[] | select(.endpoint_url==\"http://$WORKER_IP:5003\")" >/dev/null; then
    echo "✅ Worker removed from registry"
else
    echo "⚠️  Worker still in registry (may need manual removal)"
fi

# 6. Optional: Destroy container (after verification)
# ssh root@proxmox-prod "pct destroy $CTID"
```

### Upgrading Python Dependencies

**Procedure**:
```bash
# 1. Update pyproject.toml with new versions
# 2. Test locally
cd /local/ktrdr
uv sync
make test-unit
make quality

# 3. Commit and push
git add pyproject.toml uv.lock
git commit -m "chore(deps): upgrade dependencies"
git push

# 4. Deploy to staging
./scripts/deploy/deploy-to-proxmox.sh --env staging --version main

# 5. Run staging validation tests
./scripts/test/run-staging-tests.sh

# 6. Deploy to production (after validation)
./scripts/deploy/deploy-to-proxmox.sh --env production --version main --confirm
```

### Template Rebuild and Propagation

**When to Rebuild Template**:
- Security updates (monthly)
- Python version upgrades (quarterly)
- System package upgrades (as needed)

**Procedure**:
```bash
# 1. Start template container
ssh root@proxmox-prod "pct start 900"

# 2. Apply updates
ssh root@proxmox-prod "pct exec 900 -- bash" <<'EOF'
    apt-get update
    apt-get upgrade -y
    apt-get clean
    rm -rf /var/lib/apt/lists/*
EOF

# 3. Update uv
ssh root@proxmox-prod "pct exec 900 -- bash" <<'EOF'
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="/root/.cargo/bin:$PATH"
    uv --version
EOF

# 4. Stop template
ssh root@proxmox-prod "pct stop 900"

# 5. Create new snapshot
ssh root@proxmox-prod "pct snapshot 900 template-$(date +%Y%m%d) --description 'Updated $(date +%Y-%m-%d)'"

# 6. Deploy to workers (rolling update - see "Adding Workers" section)
# Clone new workers from updated template, drain and remove old workers
```

### Model Deployment

**Deploy Trained Models to Workers**:
```bash
# 1. Train model (on GPU host or training worker)
# Model saved to: /models/ktrdr/neuro_mean_reversion/1d_v22/

# 2. Verify model files
ls -lh /models/ktrdr/neuro_mean_reversion/1d_v22/
# Expected: model.pt, metadata.json, config.yaml

# 3. Deploy to shared storage (if using NFS)
# Models automatically available to all workers via shared mount

# 4. Verify model accessible from workers
ssh root@proxmox-prod "pct exec 201 -- ls -lh /models/ktrdr/neuro_mean_reversion/1d_v22/"

# 5. Test model loading on worker
curl -X POST http://192.168.1.100:8000/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/models/ktrdr/neuro_mean_reversion/1d_v22",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  }'

# 6. Monitor test backtest
# Verify successful completion
```

---

## Monitoring & Alerting

### Worker Health Monitoring

**Automated Checks** (backend does this):
- Poll every 10 seconds
- 3 failures → TEMPORARILY_UNAVAILABLE
- 5 minutes unavailable → REMOVED

**Manual Monitoring**:
```bash
# Real-time worker status
watch -n 5 'curl -s http://192.168.1.100:8000/api/v1/workers/health | jq'

# Check for unhealthy workers
curl -s http://192.168.1.100:8000/api/v1/workers | \
  jq '.[] | select(.status!="AVAILABLE") | {worker_id, status, failures: .health_check_failures}'
```

### Dead Worker Alerts

**Setup Alert Script**:
```bash
# scripts/monitoring/check-dead-workers.sh

#!/bin/bash
DEAD_WORKERS=$(curl -s http://192.168.1.100:8000/api/v1/workers | \
  jq -r '.[] | select(.status=="TEMPORARILY_UNAVAILABLE") | .worker_id')

if [ -n "$DEAD_WORKERS" ]; then
    echo "ALERT: Dead workers detected:"
    echo "$DEAD_WORKERS"

    # Send alert (Slack, email, PagerDuty)
    curl -X POST https://hooks.slack.com/services/YOUR/WEBHOOK/URL \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"⚠️ Dead KTRDR workers: $DEAD_WORKERS\"}"
fi
```

**Cron Job**:
```bash
# On monitoring server or backend
*/5 * * * * /opt/ktrdr/scripts/monitoring/check-dead-workers.sh
```

### Operation Failure Rates

**Calculate failure rate**:
```bash
# Get operations from last hour
OPERATIONS=$(curl -s "http://192.168.1.100:8000/api/v1/operations?since=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)")

TOTAL=$(echo "$OPERATIONS" | jq '.operations | length')
FAILED=$(echo "$OPERATIONS" | jq '[.operations[] | select(.status=="failed")] | length')

if [ "$TOTAL" -gt 0 ]; then
    FAILURE_RATE=$(echo "scale=2; ($FAILED / $TOTAL) * 100" | bc)
    echo "Failure rate (last hour): $FAILURE_RATE%"

    # Alert if > 10%
    if (( $(echo "$FAILURE_RATE > 10" | bc -l) )); then
        echo "ALERT: High failure rate!"
        # Send alert
    fi
fi
```

### System Resource Monitoring

**Check resource usage across all LXCs**:
```bash
# scripts/monitoring/check-resources.sh

#!/bin/bash

echo "=== Resource Usage Report ==="
echo "$(date)"
echo ""

# Backend
echo "Backend (CT 100):"
ssh root@proxmox-prod "pct exec 100 -- bash -c '
    echo \"  CPU: \$(top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\\([0-9.]*\\)%* id.*/\\1/\" | awk \"{print 100 - \\$1}\")%\"
    echo \"  Memory: \$(free -h | awk \"/^Mem:/{print \\$3 \"/\" \\$2}\")\"
    echo \"  Disk: \$(df -h / | awk \"NR==2{print \\$3 \"/\" \\$2 \" (\" \\$5 \")\"}\")'
"

# Workers
for i in {201..210}; do
    echo "Worker CT $i:"
    ssh root@proxmox-prod "pct exec $i -- bash -c '
        echo \"  CPU: \$(top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\\([0-9.]*\\)%* id.*/\\1/\" | awk \"{print 100 - \\$1}\")%\"
        echo \"  Memory: \$(free -h | awk \"/^Mem:/{print \\$3 \"/\" \\$2}\")\"
        echo \"  Disk: \$(df -h / | awk \"NR==2{print \\$3 \"/\" \\$2 \" (\" \\$5 \")\"}\")'
    " || echo "  (Offline)"
done
```

### Performance Metrics

**Collect performance metrics**:
```bash
# Average operation duration by type
curl -s "http://192.168.1.100:8000/api/v1/operations?limit=1000" | \
  jq -r '.operations[] | select(.status=="completed") | [.operation_type, .duration] | @tsv' | \
  awk '{sum[$1]+=$2; count[$1]++} END {for (type in sum) print type, sum[type]/count[type]}'

# Operations per hour
curl -s "http://192.168.1.100:8000/api/v1/operations?since=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" | \
  jq '.operations | length'
```

---

## Incident Response

### Worker Down

**Symptoms**: Worker marked TEMPORARILY_UNAVAILABLE or removed from registry

**Response**:
```bash
# 1. Identify affected worker
WORKER_ID="ktrdr-worker-bt-5"
WORKER_IP=$(echo "$WORKER_ID" | sed 's/.*-bt-/192.168.1.20/')  # Adjust based on naming

# 2. Check worker status on Proxmox
ssh root@proxmox-prod "pct status 205"

# 3a. If stopped, restart
ssh root@proxmox-prod "pct start 205"

# 3b. If running but unresponsive, restart service
ssh root@proxmox-prod "pct exec 205 -- systemctl restart ktrdr-worker"

# 4. Monitor logs
ssh root@proxmox-prod "pct exec 205 -- journalctl -u ktrdr-worker -f"

# 5. Verify registration
sleep 15
curl -s http://192.168.1.100:8000/api/v1/workers | jq ".[] | select(.worker_id==\"$WORKER_ID\")"

# 6. If still failing, check for errors
ssh root@proxmox-prod "pct exec 205 -- journalctl -u ktrdr-worker --since '10 minutes ago' | grep -i error"
```

**Escalation**:
- If worker repeatedly fails: Remove from cluster, investigate offline
- If multiple workers failing: Check network, shared storage, backend issues

### Backend Down

**Symptoms**: API unreachable, all operations failing

**Response**:
```bash
# 1. Check backend status
ssh root@proxmox-prod "pct status 100"

# 2a. If stopped, start
ssh root@proxmox-prod "pct start 100"

# 2b. If running, check service
ssh root@proxmox-prod "pct exec 100 -- systemctl status ktrdr-backend"

# 3. Check logs for errors
ssh root@proxmox-prod "pct exec 100 -- journalctl -u ktrdr-backend --since '10 minutes ago' | tail -100"

# 4. If service crashed, restart
ssh root@proxmox-prod "pct exec 100 -- systemctl restart ktrdr-backend"

# 5. Verify health
sleep 10
curl http://192.168.1.100:8000/api/v1/health

# 6. Verify workers can reach backend
ssh root@proxmox-prod "pct exec 201 -- curl -I http://192.168.1.100:8000/health"

# 7. Check worker re-registration
curl http://192.168.1.100:8000/api/v1/workers | jq '. | length'
```

**Failover** (if high availability configured):
```bash
# Promote secondary backend to primary
# Update DNS or load balancer to point to secondary
# Workers will automatically re-register with new backend
```

### GPU Host Down

**Symptoms**: No GPU workers in registry, GPU training operations failing

**Response**:
```bash
# 1. Check GPU host status
ssh root@gpu-host "systemctl status ktrdr-training-host"

# 2. Check GPU availability
ssh root@gpu-host "nvidia-smi"

# 3. Check service logs
ssh root@gpu-host "journalctl -u ktrdr-training-host -n 100"

# 4. Restart service if needed
ssh root@gpu-host "systemctl restart ktrdr-training-host"

# 5. Verify registration
sleep 10
curl http://192.168.1.100:8000/api/v1/workers | \
  jq '.[] | select(.capabilities.gpu==true)'

# 6. Verify CPU fallback working
# Training operations should automatically use CPU workers
curl http://192.168.1.100:8000/api/v1/workers | \
  jq '.[] | select(.worker_type=="training" and .capabilities.gpu==false)'
```

### Network Partition

**Symptoms**: Workers can't reach backend, health checks failing, operations timing out

**Response**:
```bash
# 1. Test connectivity from workers to backend
for i in {201..210}; do
    echo "Worker $i:"
    ssh root@proxmox-prod "pct exec $i -- ping -c 3 192.168.1.100" || echo "  FAILED"
done

# 2. Check Proxmox network
ssh root@proxmox-prod "ip addr show vmbr0"
ssh root@proxmox-prod "brctl show vmbr0"

# 3. Check firewall rules
ssh root@proxmox-prod "iptables -L -n | grep 8000"

# 4. Check routes
ssh root@proxmox-prod "pct exec 201 -- ip route"

# 5. If network issue on Proxmox, restart networking
# (CAUTION: May cause brief outage)
ssh root@proxmox-prod "systemctl restart networking"

# 6. Verify workers can reach backend
for i in {201..210}; do
    ssh root@proxmox-prod "pct exec $i -- curl -I http://192.168.1.100:8000/health"
done
```

### Disk Full

**Symptoms**: Operations failing with "No space left on device", logs not writing

**Response**:
```bash
# 1. Identify which container is full
ssh root@proxmox-prod "for i in 100 {201..210}; do echo \"CT \$i:\"; pct exec \$i -- df -h /; done"

# 2. Check what's using space
CTID=201  # Adjust based on findings
ssh root@proxmox-prod "pct exec $CTID -- du -sh /* | sort -hr | head -10"

# 3. Common cleanup actions
ssh root@proxmox-prod "pct exec $CTID -- bash" <<'EOF'
    # Clean apt cache
    apt-get clean

    # Clean journalctl logs (keep last 7 days)
    journalctl --vacuum-time=7d

    # Clean temporary files
    rm -rf /tmp/*
    rm -rf /var/tmp/*

    # Check for large log files
    find /var/log -type f -size +100M
EOF

# 4. If insufficient, expand disk
ssh root@proxmox-prod "pct resize $CTID rootfs +10G"
ssh root@proxmox-prod "pct exec $CTID -- resize2fs /dev/mapper/pve-vm--$CTID--disk--0"

# 5. Verify space available
ssh root@proxmox-prod "pct exec $CTID -- df -h /"
```

---

## Rollback Procedures

### Code Rollback

**Scenario**: New deployment causing issues, need to revert

**Procedure**:
```bash
# 1. Identify previous working version
git log --oneline -10
# Example: v1.5.1 (previous) → v1.5.2 (current, broken)

PREVIOUS_VERSION="v1.5.1"

# 2. Test rollback in staging first (if possible)
./scripts/deploy/deploy-to-proxmox.sh --env staging --version $PREVIOUS_VERSION

# 3. Rollback production
./scripts/deploy/deploy-to-proxmox.sh --env production --version $PREVIOUS_VERSION --confirm

# 4. Verify system health
curl http://192.168.1.100:8000/api/v1/health
curl http://192.168.1.100:8000/api/v1/workers/health

# 5. Test operations
./scripts/test/smoke-test.sh

# 6. Document rollback
echo "Rollback performed: v1.5.2 → v1.5.1 at $(date)" >> /var/log/ktrdr-deployments.log
```

**Rollback Time**: < 5 minutes (backend + rolling worker update)

### Configuration Rollback

**Scenario**: Configuration change causing issues

**Procedure**:
```bash
# 1. Restore previous configuration from backup
BACKUP_DATE="2025-11-09"

# Backend
ssh root@proxmox-prod "pct exec 100 -- cp /opt/ktrdr/.env.backup.$BACKUP_DATE /opt/ktrdr/.env"
ssh root@proxmox-prod "pct exec 100 -- systemctl restart ktrdr-backend"

# Workers
for i in {201..210}; do
    ssh root@proxmox-prod "pct exec $i -- cp /opt/ktrdr/.env.backup.$BACKUP_DATE /opt/ktrdr/.env"
    ssh root@proxmox-prod "pct exec $i -- systemctl restart ktrdr-worker"
done

# 2. Verify services restarted
sleep 15
curl http://192.168.1.100:8000/api/v1/health
curl http://192.168.1.100:8000/api/v1/workers | jq '. | length'
```

### Template Rollback (Restore LXC Snapshot)

**Scenario**: Template update caused issues, need to restore

**Procedure**:
```bash
# 1. List available snapshots
ssh root@proxmox-prod "pct listsnapshot 900"

# 2. Rollback template to previous snapshot
SNAPSHOT_NAME="template-20251109"
ssh root@proxmox-prod "pct rollback 900 $SNAPSHOT_NAME"

# 3. For workers already deployed from bad template:
# - Clone new workers from restored template
# - Drain and remove workers created from bad template
# (See "Adding Workers" and "Removing Workers" sections)
```

---

## Common Operational Tasks

### Viewing Logs Across All LXCs

**Aggregate logs**:
```bash
# scripts/ops/view-logs.sh

#!/bin/bash
COMPONENT=${1:-all}  # backend, workers, all
SINCE=${2:-"10 minutes ago"}

if [ "$COMPONENT" = "backend" ] || [ "$COMPONENT" = "all" ]; then
    echo "=== Backend Logs ==="
    ssh root@proxmox-prod "pct exec 100 -- journalctl -u ktrdr-backend --since '$SINCE' -n 50"
fi

if [ "$COMPONENT" = "workers" ] || [ "$COMPONENT" = "all" ]; then
    for i in {201..210}; do
        echo "=== Worker CT $i ==="
        ssh root@proxmox-prod "pct exec $i -- journalctl -u ktrdr-worker --since '$SINCE' -n 20" || echo "(Offline)"
    done
fi
```

**Usage**:
```bash
# View backend logs
./scripts/ops/view-logs.sh backend "1 hour ago"

# View all worker logs
./scripts/ops/view-logs.sh workers "30 minutes ago"

# View everything
./scripts/ops/view-logs.sh all "2 hours ago"
```

### Checking System Status

**Complete status check**:
```bash
# scripts/ops/system-status.sh

#!/bin/bash

echo "=== KTRDR System Status ==="
echo "$(date)"
echo ""

# Backend
echo "Backend:"
curl -s http://192.168.1.100:8000/api/v1/health | jq -r '"  Health: \(.healthy)"'

# Workers
echo ""
echo "Workers:"
WORKER_STATS=$(curl -s http://192.168.1.100:8000/api/v1/workers/health)
echo "$WORKER_STATS" | jq -r '"  Total: \(.total_workers)"'
echo "$WORKER_STATS" | jq -r '"  Available: \(.available)"'
echo "$WORKER_STATS" | jq -r '"  Busy: \(.busy)"'
echo "$WORKER_STATS" | jq -r '"  Unavailable: \(.temporarily_unavailable)"'

# Operations
echo ""
echo "Operations (last hour):"
OPS=$(curl -s "http://192.168.1.100:8000/api/v1/operations?since=$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)")
TOTAL=$(echo "$OPS" | jq '.operations | length')
RUNNING=$(echo "$OPS" | jq '[.operations[] | select(.status=="running")] | length')
COMPLETED=$(echo "$OPS" | jq '[.operations[] | select(.status=="completed")] | length')
FAILED=$(echo "$OPS" | jq '[.operations[] | select(.status=="failed")] | length')

echo "  Total: $TOTAL"
echo "  Running: $RUNNING"
echo "  Completed: $COMPLETED"
echo "  Failed: $FAILED"

# Resource usage
echo ""
echo "Resource Usage:"
ssh root@proxmox-prod "pct exec 100 -- bash -c '
    echo \"  Backend CPU: \$(top -bn1 | grep \"Cpu(s)\" | sed \"s/.*, *\\([0-9.]*\\)%* id.*/\\1/\" | awk \"{print 100 - \\$1}\")%\"
    echo \"  Backend Memory: \$(free -h | awk \"/^Mem:/{print \\$3 \"/\" \\$2}\")\"
'"
```

### Draining a Worker (Graceful Shutdown)

**Wait for operations to complete before stopping**:
```bash
# scripts/ops/drain-worker.sh

#!/bin/bash
WORKER_IP=${1:?Worker IP required}
CTID=${2:?Container ID required}

echo "Draining worker $WORKER_IP (CT $CTID)..."

# 1. Check current status
WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status')
echo "Current status: $WORKER_STATUS"

# 2. If busy, wait for operation to complete
if [ "$WORKER_STATUS" = "busy" ]; then
    CURRENT_OP=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.current_operation')
    echo "Worker is busy with operation: $CURRENT_OP"
    echo "Waiting for completion (checking every 30 seconds)..."

    # Wait up to 2 hours (typical training operation duration)
    for i in {1..240}; do
        sleep 30
        WORKER_STATUS=$(curl -s "http://$WORKER_IP:5003/health" | jq -r '.worker_status')
        if [ "$WORKER_STATUS" != "busy" ]; then
            echo "Operation completed!"
            break
        fi
        echo "  Still busy... ($i * 30 seconds elapsed)"
    done

    if [ "$WORKER_STATUS" = "busy" ]; then
        echo "WARNING: Worker still busy after 2 hours. Consider manual intervention."
        exit 1
    fi
fi

# 3. Stop worker service
echo "Stopping worker service..."
ssh root@proxmox-prod "pct exec $CTID -- systemctl stop ktrdr-worker"

# 4. Wait for backend to detect and remove (5 minutes)
echo "Waiting for backend to remove worker from registry..."
sleep 300

# 5. Verify removed
if ! curl -s http://192.168.1.100:8000/api/v1/workers | jq -e ".[] | select(.endpoint_url==\"http://$WORKER_IP:5003\")" >/dev/null; then
    echo "✅ Worker drained and removed from registry"
else
    echo "⚠️  Worker still in registry"
fi

# 6. Stop container (optional)
# ssh root@proxmox-prod "pct stop $CTID"
```

### Emergency Stop Procedures

**Force stop all operations** (last resort):
```bash
# WARNING: This will kill running operations!

# 1. Stop all workers immediately
ssh root@proxmox-prod "for i in {201..210}; do pct stop \$i --timeout 0; done"

# 2. Stop backend
ssh root@proxmox-prod "pct stop 100 --timeout 0"

# 3. Stop host services
ssh root@gpu-host "systemctl stop ktrdr-training-host"
ssh root@ib-host "systemctl stop ktrdr-ib-host"

echo "⚠️  EMERGENCY STOP COMPLETE"
echo "All operations were forcefully terminated."
echo "Review logs before restarting system."
```

---

## Security & Secrets Management

### Secrets Storage

**DO NOT**:
- Store secrets in Git
- Store secrets in plain text on disk
- Share secrets in Slack/email

**DO**:
- Use environment variables
- Use Proxmox's built-in secrets management
- Use external secrets management (HashiCorp Vault, AWS Secrets Manager)
- Encrypt secrets at rest

**Example** (using environment variables):
```bash
# /opt/ktrdr/.env
IB_USERNAME=your-username
IB_PASSWORD=your-password  # Read from secrets manager in production
API_KEY=your-api-key
```

**Vault Integration** (example):
```bash
# Fetch secrets from Vault
export VAULT_ADDR="https://vault.internal:8200"
export VAULT_TOKEN="s.xxxxx"

# Retrieve secrets
IB_PASSWORD=$(vault kv get -field=password secret/ktrdr/ib)
API_KEY=$(vault kv get -field=api_key secret/ktrdr/api)

# Inject into environment
cat > /opt/ktrdr/.env << EOF
IB_USERNAME=your-username
IB_PASSWORD=$IB_PASSWORD
API_KEY=$API_KEY
EOF

chmod 600 /opt/ktrdr/.env
```

### Access Control

**Proxmox Access**:
- Limit root access to specific IPs
- Use SSH keys (disable password authentication)
- Enable 2FA for Proxmox Web UI

**Backend API**:
- Enable authentication for sensitive endpoints
- Use API keys for programmatic access
- Rate limiting to prevent abuse

**Network Segmentation**:
- Workers only accessible from backend
- Backend accessible from specific IPs (VPN, office)
- GPU/IB hosts on separate network segment

---

## Maintenance Windows

### Scheduled Maintenance

**Standard Maintenance Window**: Sunday 02:00-06:00 UTC

**Pre-Maintenance Checklist**:
- [ ] Announce maintenance window (48 hours advance notice)
- [ ] Backup all LXC containers
- [ ] Take snapshots of template
- [ ] Verify rollback procedures tested
- [ ] Prepare communication channels (status page, Slack)

**During Maintenance**:
- [ ] Stop accepting new operations
- [ ] Wait for active operations to complete
- [ ] Perform updates/changes
- [ ] Test system functionality
- [ ] Restore services
- [ ] Verify worker registration
- [ ] Run smoke tests

**Post-Maintenance**:
- [ ] Monitor system for 1 hour
- [ ] Check logs for errors
- [ ] Verify all workers healthy
- [ ] Update status page
- [ ] Send completion notification

**Emergency Maintenance**:
- Announce as soon as possible
- Follow same checklist
- Document reason for emergency maintenance

---

## Summary

This CI/CD and operations runbook covered:

1. **Deployment Pipeline**: CI/CD stages, quality gates, automated deployments
2. **Deployment Automation**: One-command deployments, rolling updates, configuration management
3. **Environment Management**: Staging vs production configuration, validation
4. **Operations Procedures**: Starting/stopping, scaling, upgrades, template management
5. **Monitoring & Alerting**: Worker health, operation failures, resource usage, performance metrics
6. **Incident Response**: Worker/backend/GPU/network failures, disk full
7. **Rollback Procedures**: Code, configuration, template rollbacks
8. **Common Tasks**: Log viewing, status checks, worker draining, emergency stops
9. **Security**: Secrets management, access control, network segmentation
10. **Maintenance Windows**: Scheduled maintenance, checklists, emergency procedures

**Key Principles**:
- **Automation First**: All deployments scripted and repeatable
- **Zero Downtime**: Rolling updates minimize disruption
- **Fast Rollback**: Restore within 5 minutes
- **Observable**: Comprehensive monitoring and alerting
- **Documented**: Clear procedures for all scenarios

**Related Documents**:
- **For Deployment**: See [Proxmox Deployment Guide](../user-guides/deployment-proxmox.md)
- **For Development**: See [Distributed Workers Developer Guide](distributed-workers-guide.md)
- **For Architecture**: See [Distributed Workers Architecture](../architecture-overviews/distributed-workers.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-10
