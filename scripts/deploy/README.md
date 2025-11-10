# KTRDR Code Deployment

This directory contains scripts and configuration for deploying KTRDR code to worker LXC containers.

## Overview

The deployment system enables **continuous delivery** by separating code deployment from template management:

- **Template** (base environment) - Created once, changes rarely ([Task 6.1](../lxc/README.md))
- **Code** (KTRDR application) - Deployed frequently, updated without template rebuild

This separation allows deploying code updates to all workers in minutes without rebuilding container templates.

## Files

```
scripts/deploy/
├── deploy-code.sh              # Main deployment script
├── systemd/
│   ├── ktrdr-backtest-worker.service   # Systemd service for backtest workers
│   └── ktrdr-training-worker.service   # Systemd service for training workers
└── README.md                   # This file
```

## Quick Start

### 1. Deploy to Single Worker

```bash
# Deploy main branch to worker 201
./deploy-code.sh "201" main
```

### 2. Deploy to Multiple Workers

```bash
# Deploy to workers 201, 202, 203
./deploy-code.sh "201 202 203" main
```

### 3. Deploy Specific Version

```bash
# Deploy tag v1.2.3 to all default workers
./deploy-code.sh "" v1.2.3
```

## Deployment Script

### Usage

```bash
./deploy-code.sh [WORKER_IDS] [GIT_REF]
```

**Parameters:**
- `WORKER_IDS` (optional) - Space-separated list of LXC container IDs
  - Default: `"201 202 203"`
  - Example: `"201 202 203 204 205"`
- `GIT_REF` (optional) - Git branch, tag, or commit SHA to deploy
  - Default: `"main"`
  - Example: `"develop"`, `"v1.2.3"`, `"feature/new-indicator"`

**Environment Variables:**
- `KTRDR_GIT_REPO` - Git repository URL
  - Default: `"https://github.com/your-org/ktrdr.git"`
  - Override: `export KTRDR_GIT_REPO="https://github.com/myorg/ktrdr.git"`

### What the Script Does

The deployment script performs these steps for each worker:

1. **Validates worker** - Checks worker exists and is running
2. **Clones/updates git repository** - Clones repo if first deployment, otherwise updates
3. **Installs dependencies** - Runs `uv sync` to install Python dependencies
4. **Restarts service** - Restarts `ktrdr-worker` systemd service (if exists)
5. **Verifies deployment** - Checks code was deployed successfully

### Examples

#### Deploy to Development Workers

```bash
# Deploy develop branch to test workers
./deploy-code.sh "211 212 213" develop
```

#### Deploy Production Release

```bash
# Deploy release tag to production workers
./deploy-code.sh "201 202 203 204 205" v1.2.3
```

#### Deploy to All Workers

```bash
# If you have many workers, list them all
WORKERS="201 202 203 204 205 206 207 208 209 210"
./deploy-code.sh "$WORKERS" main
```

#### Using Custom Git Repository

```bash
# Deploy from fork
export KTRDR_GIT_REPO="https://github.com/myusername/ktrdr.git"
./deploy-code.sh "201" feature/my-changes
```

## Systemd Service Files

Worker processes run as systemd services for automatic restart and lifecycle management.

### Service Installation

After deploying code, install the systemd service:

```bash
# Enter the worker container
pct enter 201

# Copy service file
cp /opt/ktrdr/scripts/deploy/systemd/ktrdr-backtest-worker.service \
   /etc/systemd/system/

# Reload systemd
systemctl daemon-reload

# Enable service (start on boot)
systemctl enable ktrdr-worker

# Start service
systemctl start ktrdr-worker

# Check status
systemctl status ktrdr-worker
```

### Service Types

#### Backtest Worker Service

**File:** `systemd/ktrdr-backtest-worker.service`

- **Purpose:** Runs backtesting worker for distributed backtesting
- **Port:** 5003
- **User:** ktrdr
- **Auto-restart:** Yes
- **Working Directory:** `/opt/ktrdr`

**Command:**
```bash
uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003
```

#### Training Worker Service

**File:** `systemd/ktrdr-training-worker.service`

- **Purpose:** Runs training worker for distributed model training
- **Port:** 5004
- **User:** ktrdr
- **Auto-restart:** Yes
- **Working Directory:** `/opt/ktrdr`

**Command:**
```bash
uvicorn ktrdr.training.training_worker:app --host 0.0.0.0 --port 5004
```

### Service Configuration

Both services include:

- **Automatic Restart:** Service restarts automatically on failure
- **Security Hardening:**
  - Runs as non-root `ktrdr` user
  - Private `/tmp` directory
  - Protected system directories
  - No new privileges allowed
- **Logging:** Logs to systemd journal
- **Resource Limits:** Can be extended with CPU/memory limits
- **Environment:** Reads `.env` file from `/opt/ktrdr/.env`

### Managing Services

```bash
# Start service
systemctl start ktrdr-worker

# Stop service
systemctl stop ktrdr-worker

# Restart service (e.g., after deployment)
systemctl restart ktrdr-worker

# Check status
systemctl status ktrdr-worker

# View logs
journalctl -u ktrdr-worker -f

# View recent logs
journalctl -u ktrdr-worker --since "10 minutes ago"

# Enable (start on boot)
systemctl enable ktrdr-worker

# Disable (don't start on boot)
systemctl disable ktrdr-worker
```

## Deployment Workflow

### Initial Deployment (New Worker)

1. **Create worker from template** (see [Task 6.3](../lxc/provision-worker.sh))
2. **Deploy code:**
   ```bash
   ./deploy-code.sh "201" main
   ```
3. **Install systemd service:**
   ```bash
   pct enter 201
   cp /opt/ktrdr/scripts/deploy/systemd/ktrdr-backtest-worker.service \
      /etc/systemd/system/
   systemctl daemon-reload
   systemctl enable ktrdr-worker
   systemctl start ktrdr-worker
   ```
4. **Verify worker is healthy:**
   ```bash
   curl http://192.168.1.201:5003/health
   ```

### Regular Deployment (Code Updates)

1. **Deploy new code:**
   ```bash
   ./deploy-code.sh "201 202 203" main
   ```
2. **Verify deployment:**
   ```bash
   # Check service restarted
   pct exec 201 -- systemctl status ktrdr-worker

   # Check worker health
   curl http://192.168.1.201:5003/health
   curl http://192.168.1.202:5003/health
   curl http://192.168.1.203:5003/health
   ```

### Rolling Deployment

For zero-downtime deployment to production workers:

```bash
# Deploy to workers one at a time
for worker in 201 202 203 204 205; do
    echo "Deploying to worker $worker..."
    ./deploy-code.sh "$worker" v1.2.3

    # Wait for worker to be healthy
    sleep 5
    curl -f http://192.168.1.${worker}:5003/health || {
        echo "Worker $worker failed health check!"
        exit 1
    }

    echo "Worker $worker deployed successfully"
done
```

### Rollback

If deployment fails, rollback to previous version:

```bash
# Deploy previous working version
./deploy-code.sh "201 202 203" v1.2.2

# Or rollback to main
./deploy-code.sh "201 202 203" main
```

## Environment Configuration

Each worker requires a `.env` file in `/opt/ktrdr/.env`:

```bash
# Backend API URL
KTRDR_API_URL=http://192.168.1.100:8000

# Worker endpoint URL (worker's own URL)
WORKER_ENDPOINT_URL=http://192.168.1.201:5003

# Worker type (backtesting or training)
WORKER_TYPE=backtesting

# Worker ID (unique identifier)
WORKER_ID=backtest-worker-1

# Optional: Capabilities
WORKER_CAPABILITIES=cpu

# Optional: GPU for training workers
# WORKER_CAPABILITIES=gpu
```

**Note:** The `.env` file is NOT included in the template or git repository. It must be created during worker provisioning (Task 6.3) or manually.

## Troubleshooting

### Deployment Fails: "pct command not found"

**Cause:** Script is not running on Proxmox VE

**Solution:** Run the script on your Proxmox server:
```bash
scp scripts/deploy/deploy-code.sh root@proxmox-host:/tmp/
ssh root@proxmox-host "bash /tmp/deploy-code.sh 201 main"
```

### Deployment Fails: "Worker does not exist"

**Cause:** Worker LXC container doesn't exist

**Solution:** Create worker from template first (Task 6.3):
```bash
./scripts/lxc/provision-worker.sh 201 192.168.1.201 backtesting
```

### Deployment Fails: "git clone failed"

**Causes:**
1. Worker has no internet access
2. Git repository URL is wrong
3. Private repository without authentication

**Solutions:**
```bash
# Check worker network
pct exec 201 -- ping -c 3 github.com

# Verify git repo URL
export KTRDR_GIT_REPO="https://github.com/correct-org/ktrdr.git"
./deploy-code.sh "201" main

# For private repos, set up SSH keys or git credentials
pct exec 201 -- bash
su - ktrdr
git config --global credential.helper store
```

### Deployment Succeeds but Service Won't Start

**Cause:** Dependencies not installed or environment misconfigured

**Solutions:**
```bash
# Check service logs
pct exec 201 -- journalctl -u ktrdr-worker --since "5 minutes ago"

# Manually test worker startup
pct exec 201 -- bash
su - ktrdr
cd /opt/ktrdr
uv sync
source .venv/bin/activate
uvicorn ktrdr.backtesting.backtest_worker:app --host 0.0.0.0 --port 5003
```

### Dependencies Installation Fails

**Cause:** `uv` not installed or network issues

**Solutions:**
```bash
# Check uv is installed
pct exec 201 -- su - ktrdr -c "uv --version"

# If not installed, recreate worker from template (Task 6.1)

# Check network for pip packages
pct exec 201 -- ping -c 3 pypi.org
```

### Service Restarts but Worker Not Registering

**Cause:** Worker can't reach backend API

**Solutions:**
```bash
# Check .env file
pct exec 201 -- cat /opt/ktrdr/.env

# Test backend connectivity
pct exec 201 -- curl http://192.168.1.100:8000/health

# Check worker logs
pct exec 201 -- journalctl -u ktrdr-worker -n 50
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Deploy to Production
on:
  push:
    tags:
      - 'v*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to Proxmox Workers
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.PROXMOX_HOST }}
          username: root
          key: ${{ secrets.PROXMOX_SSH_KEY }}
          script: |
            cd /opt/ktrdr
            ./scripts/deploy/deploy-code.sh "201 202 203 204 205" ${{ github.ref_name }}
```

### GitLab CI Example

```yaml
deploy_production:
  stage: deploy
  only:
    - tags
  script:
    - ssh root@proxmox "cd /opt/ktrdr && ./scripts/deploy/deploy-code.sh '201 202 203' $CI_COMMIT_TAG"
```

## Related Documentation

- **Template Creation:** [scripts/lxc/README.md](../lxc/README.md) (Task 6.1)
- **Worker Provisioning:** `scripts/lxc/provision-worker.sh` (Task 6.3)
- **Configuration Management:** Task 6.4 (coming soon)
- **Proxmox Deployment Guide:** Task 6.6 (coming soon)
- **Distributed Architecture:** [docs/architecture/distributed/ARCHITECTURE.md](../../docs/architecture/distributed/ARCHITECTURE.md)

## Best Practices

1. **Always test deployments in development first**
   - Deploy to test workers (211-213) before production (201-210)

2. **Use version tags for production**
   - Don't deploy branches to production
   - Use semantic versioning (v1.2.3)

3. **Deploy during low-traffic periods**
   - Schedule deployments when few operations are running

4. **Monitor workers after deployment**
   - Check health endpoints
   - Review systemd logs
   - Verify worker registration with backend

5. **Keep deployment history**
   - Tag deployments in git
   - Document what was deployed when

6. **Have rollback plan**
   - Know the last working version
   - Test rollback procedure

7. **Automate deployments**
   - Use CI/CD pipelines
   - Automate testing before deployment

## Security Considerations

- **Git Repository Access:** Use HTTPS or SSH keys for authentication
- **Service User:** Workers run as `ktrdr` user (not root)
- **Network Security:** Workers should only access backend API and git repository
- **Secrets Management:** Never commit `.env` files with secrets
- **Updates:** Keep Python dependencies updated via `uv sync`

## Performance

- **Deployment Time:** ~2-3 minutes per worker
- **Parallel Deployments:** Script can be run on multiple workers simultaneously
- **Downtime:** ~10-30 seconds per worker (service restart)
- **Bandwidth:** ~50-100MB download per worker (code + dependencies)

## Version History

- **v1** (Task 6.2) - Initial deployment script with systemd services
