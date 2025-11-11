# KTRDR Proxmox LXC Deployment Guide

**Version**: 1.0
**Date**: 2025-11-10
**Audience**: DevOps, System Administrators, Production Operators
**Deployment Target**: Proxmox VE with LXC Containers (Production)

---

## Table of Contents

1. [Overview](#overview)
2. [Why Proxmox LXC?](#why-proxmox-lxc)
3. [Architecture](#architecture)
4. [Prerequisites](#prerequisites)
5. [Initial Setup](#initial-setup)
6. [LXC Template Creation](#lxc-template-creation)
7. [Backend Deployment](#backend-deployment)
8. [Worker Deployment](#worker-deployment)
9. [GPU Training Host Setup](#gpu-training-host-setup)
10. [Network Configuration](#network-configuration)
11. [Verification & Testing](#verification--testing)
12. [Monitoring & Maintenance](#monitoring--maintenance)
13. [Scaling Operations](#scaling-operations)
14. [Troubleshooting](#troubleshooting)
15. [Performance Tuning](#performance-tuning)

---

## Overview

This guide covers deploying KTRDR on Proxmox VE using LXC containers for production environments. Proxmox provides a robust, scalable infrastructure with lower overhead than Docker, making it ideal for CPU-intensive training and backtesting workloads.

**Deployment Model**:
- **Backend LXC**: Central orchestrator (1 container)
- **Worker LXCs**: Cloned from template for parallel execution (N containers)
- **GPU Host Service**: Native process for GPU training (optional)
- **IB Host Service**: Native process for IB Gateway integration (optional)

**Key Benefits**:
- Lower overhead than Docker (5-15% performance improvement)
- Full OS environment (easier debugging)
- Proxmox management tools (backups, snapshots, monitoring)
- Multi-host distribution across Proxmox cluster
- Production-grade reliability

---

## Why Proxmox LXC?

### Proxmox Advantages

**Performance**:
- LXC containers have ~2-5% overhead vs bare metal (Docker: ~10-20%)
- Shared kernel provides near-native performance
- Lower memory footprint per container
- Faster startup times (1-3 seconds vs 5-10 seconds for Docker)

**Management**:
- Web UI for container management
- Built-in backup and restore
- Snapshot capabilities
- Live migration between hosts
- Resource monitoring and limits

**Infrastructure**:
- Multi-host clustering
- Shared storage (NFS, Ceph, ZFS)
- HA capabilities (automatic failover)
- Network management (bridges, VLANs)

**Operations**:
- Full OS environment (systemd, package manager)
- SSH access to each container
- Standard Linux tooling
- Easier debugging than Docker

### When to Use Proxmox

**Ideal For**:
- Production deployments
- Large-scale operations (> 20 workers)
- Multi-host distributed deployments
- Long-running workloads
- Performance-critical applications
- Teams with existing Proxmox infrastructure

**Not Ideal For**:
- Local development (use Docker Compose)
- Quick prototyping (use Docker Compose)
- Single-machine testing (use Docker Compose)
- Cloud deployments (use Kubernetes)

---

## Architecture

### System Topology

```
┌─────────────────────────────────────────────────────────────┐
│ Proxmox Cluster                                             │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │ Proxmox Host A (192.168.1.10)                │          │
│  │                                               │          │
│  │  ┌─────────────┐        ┌────────────┐       │          │
│  │  │ Backend LXC │        │Worker LXC 1│       │          │
│  │  │192.168.1.100│        │192.168.1.201       │          │
│  │  │  Port 8000  │        │  Port 5003 │       │          │
│  │  └─────────────┘        └────────────┘       │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │ Proxmox Host B (192.168.1.11)                │          │
│  │                                               │          │
│  │  ┌────────────┐  ┌────────────┐              │          │
│  │  │Worker LXC 2│  │Worker LXC 3│              │          │
│  │  │192.168.1.202  │192.168.1.203              │          │
│  │  │  Port 5003 │  │  Port 5003 │              │          │
│  │  └────────────┘  └────────────┘              │          │
│  └──────────────────────────────────────────────┘          │
│                                                             │
│  ┌──────────────────────────────────────────────┐          │
│  │ GPU Host (192.168.1.20) - Bare Metal         │          │
│  │                                               │          │
│  │  ┌──────────────────┐                        │          │
│  │  │Training Host Svc │                        │          │
│  │  │   Port 5002      │  CUDA/GPU Access       │          │
│  │  └──────────────────┘                        │          │
│  └──────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### Network Layout

| Component | IP Address | Port | Purpose |
|-----------|------------|------|---------|
| Backend LXC | 192.168.1.100 | 8000 | API & Orchestration |
| Worker LXC 1-N | 192.168.1.201-250 | 5003/5004 | Backtesting/Training |
| GPU Host Service | 192.168.1.20 | 5002 | GPU Training |
| IB Host Service | 192.168.1.21 | 5001 | IB Gateway |

**Note**: IP addresses are examples. Use your network's addressing scheme.

### Data Flow

```
Client → Backend LXC (192.168.1.100:8000)
            ↓
        WorkerRegistry (selects worker)
            ↓
        Worker LXC (192.168.1.201:5003)
            ↓
        Execute Operation
            ↓
        Report Progress (via operations endpoints)
            ↓
        Backend ← Worker (operation complete)
            ↓
        Client (result)
```

---

## Prerequisites

### Proxmox Environment

**Required**:
- **Proxmox VE**: 8.0 or later
- **Storage**: 100GB+ available for LXC containers and templates
- **Network**: Configured bridge (vmbr0 or custom)
- **Privileges**: Root access to Proxmox hosts

**Verify Proxmox Version**:
```bash
pveversion
# Expected: pve-manager/8.0.x or later
```

### LXC Container Requirements

**Per Container**:
- **Backend LXC**: 4 cores, 8GB RAM, 20GB disk
- **Worker LXC**: 2-4 cores, 4-8GB RAM, 15GB disk
- **Template LXC**: 2 cores, 2GB RAM, 10GB disk (base template)

**Total Minimum** (functional system):
- 1 Backend + 5 Workers = 18 cores, 32GB RAM, 95GB disk

### Network Requirements

**Static IP Addresses**:
- Backend: 1 static IP (e.g., 192.168.1.100)
- Workers: N static IPs (e.g., 192.168.1.201-250)
- GPU Host: 1 static IP (e.g., 192.168.1.20)
- IB Host: 1 static IP (e.g., 192.168.1.21)

**Firewall Rules** (all hosts):
```bash
# Backend: Allow API access
Port 8000/tcp (from workers and clients)

# Workers: Allow operations and health checks
Ports 5003-5004/tcp (from backend)

# GPU Host: Allow training operations
Port 5002/tcp (from backend)

# IB Host: Allow data operations
Port 5001/tcp (from backend)
```

**DNS/Hostname Resolution** (optional but recommended):
- Configure DNS entries for backend and hosts
- Or use `/etc/hosts` on each LXC

### Shared Storage (Recommended)

**Purpose**: Share code, models, and data across LXCs

**Options**:
1. **NFS**: Network File System (most common)
2. **Ceph**: Distributed storage (if using Ceph cluster)
3. **ZFS**: Local ZFS pool (single host)

**Mounts** (example):
```bash
# On each LXC:
/opt/ktrdr        # Application code (read-only)
/data/ktrdr       # Market data (read-only)
/models/ktrdr     # Trained models (read-write)
```

### GPU Host Requirements (Optional)

**For GPU Training**:
- **Hardware**: NVIDIA GPU with CUDA support
- **OS**: Ubuntu 22.04 or later (bare metal or privileged LXC)
- **CUDA**: CUDA Toolkit 12.x or later
- **Python**: Python 3.11+ with PyTorch GPU support

---

## Initial Setup

### Step 1: Prepare Proxmox Environment

**Create Backup Storage** (if not exists):
```bash
# On Proxmox host
pvesm add dir backups --path /mnt/backups --content backup

# Verify
pvesm status
```

**Create Shared Storage** (NFS example):
```bash
# On NFS server
sudo mkdir -p /exports/ktrdr/{code,data,models}
sudo chown -R 1000:1000 /exports/ktrdr
echo "/exports/ktrdr 192.168.1.0/24(rw,sync,no_subtree_check)" | \
  sudo tee -a /etc/exports
sudo exportfs -ra

# On Proxmox host
pvesm add nfs ktrdr-storage \
  --server 192.168.1.50 \
  --export /exports/ktrdr \
  --content rootdir,images
```

**Configure Network Bridge** (if custom network):
```bash
# Edit /etc/network/interfaces on Proxmox host
auto vmbr1
iface vmbr1 inet static
    address 192.168.1.10/24
    bridge-ports none
    bridge-stp off
    bridge-fd 0

# Apply changes
ifreload -a
```

### Step 2: Download Base LXC Template

**Debian 12 Template** (recommended):
```bash
# On Proxmox host
pveam update
pveam download local debian-12-standard_12.2-1_amd64.tar.zst

# Verify
pveam list local
```

**Ubuntu 22.04 Template** (alternative):
```bash
pveam download local ubuntu-22.04-standard_22.04-1_amd64.tar.zst
```

---

## LXC Template Creation

The LXC template is the base image for all worker LXCs. Create it once, clone many times.

### Step 1: Create Base LXC Container

**Using Proxmox Web UI**:
1. Navigate to: Datacenter → Node → Create CT
2. **General**:
   - CT ID: 900 (example, use any available)
   - Hostname: ktrdr-template
   - Password: (set root password)
3. **Template**: debian-12-standard
4. **Root Disk**: 10GB
5. **CPU**: 2 cores
6. **Memory**: 2048 MB
7. **Network**:
   - Bridge: vmbr0 (or your bridge)
   - IPv4: DHCP (for initial setup)
8. **DNS**: Use host settings
9. Create

**Using CLI**:
```bash
# On Proxmox host
pct create 900 local:vztmpl/debian-12-standard_12.2-1_amd64.tar.zst \
  --hostname ktrdr-template \
  --cores 2 \
  --memory 2048 \
  --rootfs local-lvm:10 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --password

# Start container
pct start 900
```

### Step 2: Configure Base Template

**Enter container**:
```bash
# On Proxmox host
pct enter 900
```

**Inside Container**, run the template setup script:

```bash
# Update system
apt-get update && apt-get upgrade -y

# Install required packages
apt-get install -y \
    curl \
    git \
    python3.11 \
    python3.11-venv \
    python3-pip \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    ca-certificates

# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.cargo/bin:$PATH"

# Verify installations
python3.11 --version
uv --version

# Create ktrdr user
useradd -m -s /bin/bash ktrdr
mkdir -p /opt/ktrdr
chown ktrdr:ktrdr /opt/ktrdr

# Clean up
apt-get clean
rm -rf /var/lib/apt/lists/*

# Exit container
exit
```

**Reference Script**: For automated setup, see [`scripts/lxc/create-template.sh`](../../scripts/lxc/create-template.sh)

### Step 3: Convert to Template

**Stop and convert**:
```bash
# On Proxmox host
pct stop 900

# Convert to template (Proxmox 8.x)
# This makes the container read-only and optimized for cloning
# Note: In Proxmox, LXC containers don't have a "template" flag like VMs
# Instead, we'll use this container as a source for cloning
```

**Create Template Snapshot** (for easy cloning):
```bash
# Take snapshot
pct snapshot 900 template-base --description "Base KTRDR template with Python 3.11 and uv"

# List snapshots
pct listsnapshot 900
```

**Note**: LXC containers in Proxmox don't have a formal "template" designation like VMs. We use CT 900 as a read-only source and clone from it.

---

## Backend Deployment

### Step 1: Clone Backend LXC from Template

**Using Web UI**:
1. Right-click Container 900 → Clone
2. **Mode**: Full Clone
3. **Target**: Same node or different
4. **VM ID**: 100 (example)
5. **Hostname**: ktrdr-backend
6. **Resource Pool**: (optional)
7. Clone

**Using CLI**:
```bash
# On Proxmox host
pct clone 900 100 \
  --hostname ktrdr-backend \
  --full \
  --description "KTRDR Backend (Orchestrator)"

# Configure resources
pct set 100 \
  --cores 4 \
  --memory 8192

# Configure network with static IP
pct set 100 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.100/24,gw=192.168.1.1

# Start container
pct start 100
```

### Step 2: Deploy Backend Code

**Enter backend container**:
```bash
pct enter 100
```

**Deploy code** (manual method):
```bash
# As root in container
cd /opt/ktrdr

# Clone repository
git clone https://github.com/your-org/ktrdr.git .

# Or rsync from deployment machine
# rsync -avz /local/path/ktrdr/ root@192.168.1.100:/opt/ktrdr/

# Install dependencies
export PATH="/root/.cargo/bin:$PATH"
uv sync

# Verify installation
uv run python -c "import ktrdr; print('✅ KTRDR installed')"
```

**Reference Script**: For automated deployment, see [`scripts/deploy/deploy-code.sh`](../../scripts/deploy/deploy-code.sh)

### Step 3: Configure Backend Environment

**Create environment file**:
```bash
# /opt/ktrdr/.env
cat > /opt/ktrdr/.env << 'EOF'
# Backend Configuration
KTRDR_API_URL=http://192.168.1.100:8000
LOG_LEVEL=INFO

# Host Services
USE_IB_HOST_SERVICE=true
IB_HOST_SERVICE_URL=http://192.168.1.21:5001

# Data paths
DATA_DIR=/data/ktrdr
MODELS_DIR=/models/ktrdr
EOF

chmod 600 /opt/ktrdr/.env
chown ktrdr:ktrdr /opt/ktrdr/.env
```

### Step 4: Create Systemd Service

**Create service file**:
```bash
cat > /etc/systemd/system/ktrdr-backend.service << 'EOF'
[Unit]
Description=KTRDR Backend API Server
After=network.target

[Service]
Type=simple
User=ktrdr
Group=ktrdr
WorkingDirectory=/opt/ktrdr
EnvironmentFile=/opt/ktrdr/.env
ExecStart=/root/.cargo/bin/uv run python scripts/run_api_server.py
Restart=always
RestartSec=10s

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ktrdr-backend

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Enable and start
systemctl enable ktrdr-backend
systemctl start ktrdr-backend

# Check status
systemctl status ktrdr-backend
```

### Step 5: Verify Backend

**Check service status**:
```bash
# Inside backend container
systemctl status ktrdr-backend

# Expected: active (running)
```

**Test API**:
```bash
# From any machine
curl http://192.168.1.100:8000/api/v1/health | jq

# Expected:
# {
#   "healthy": true,
#   "timestamp": "2025-11-10T10:30:00Z"
# }
```

---

## Worker Deployment

### Step 1: Clone Worker LXC from Template

**Clone multiple workers** (example: 5 backtest workers):

```bash
# On Proxmox host

# Worker 1
pct clone 900 201 --hostname ktrdr-worker-bt-1 --full
pct set 201 --cores 4 --memory 8192
pct set 201 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1
pct start 201

# Worker 2
pct clone 900 202 --hostname ktrdr-worker-bt-2 --full
pct set 202 --cores 4 --memory 8192
pct set 202 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.202/24,gw=192.168.1.1
pct start 202

# Workers 3-5 (similar)
# ...

# Or use loop
for i in {1..5}; do
  CTID=$((200 + i))
  IP=$((200 + i))
  pct clone 900 $CTID --hostname ktrdr-worker-bt-$i --full
  pct set $CTID --cores 4 --memory 8192
  pct set $CTID --net0 name=eth0,bridge=vmbr0,ip=192.168.1.$IP/24,gw=192.168.1.1
  pct start $CTID
done
```

**Reference Script**: For automated provisioning, see [`scripts/lxc/provision-worker.sh`](../../scripts/lxc/provision-worker.sh)

### Step 2: Deploy Worker Code

**Deploy to all workers** (from deployment machine):

```bash
# Using rsync
for i in {201..205}; do
  echo "Deploying to 192.168.1.$i..."
  rsync -avz \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    /local/path/ktrdr/ root@192.168.1.$i:/opt/ktrdr/
done

# Or use deployment script
./scripts/deploy/deploy-code.sh --targets "192.168.1.201-205"
```

### Step 3: Configure Worker Environment

**For each worker** (example: backtest worker 1):

```bash
# Enter worker container
pct enter 201

# Create environment file
cat > /opt/ktrdr/.env << 'EOF'
# Worker Configuration
KTRDR_API_URL=http://192.168.1.100:8000
WORKER_ID=ktrdr-worker-bt-1
WORKER_TYPE=backtesting
WORKER_PORT=5003
WORKER_ENDPOINT_URL=http://192.168.1.201:5003

# Capabilities
WORKER_CORES=4
WORKER_MEMORY_GB=8

# Logging
LOG_LEVEL=INFO

# Data paths (read-only mounts)
DATA_DIR=/data/ktrdr
MODELS_DIR=/models/ktrdr
EOF

chmod 600 /opt/ktrdr/.env
chown ktrdr:ktrdr /opt/ktrdr/.env
```

**For training workers** (use port 5004, type=training):
```bash
# Adjust for training workers
WORKER_TYPE=training
WORKER_PORT=5004
WORKER_ENDPOINT_URL=http://192.168.1.XXX:5004
```

### Step 4: Create Worker Systemd Service

**Backtest worker service**:
```bash
# Inside worker container
cat > /etc/systemd/system/ktrdr-worker.service << 'EOF'
[Unit]
Description=KTRDR Backtest Worker
After=network.target

[Service]
Type=simple
User=ktrdr
Group=ktrdr
WorkingDirectory=/opt/ktrdr
EnvironmentFile=/opt/ktrdr/.env
ExecStart=/root/.cargo/bin/uv run python -m ktrdr.backtesting.backtest_worker
Restart=always
RestartSec=10s

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ktrdr-worker

# Security
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

# For training workers, change ExecStart to:
# ExecStart=/root/.cargo/bin/uv run python -m ktrdr.training.training_worker

systemctl daemon-reload
systemctl enable ktrdr-worker
systemctl start ktrdr-worker
systemctl status ktrdr-worker
```

### Step 5: Verify Worker Registration

**Check worker logs**:
```bash
# Inside worker container
journalctl -u ktrdr-worker -f

# Look for:
# "✅ Worker registered successfully with backend"
# "Worker ID: ktrdr-worker-bt-1"
# "Worker endpoint: http://192.168.1.201:5003"
```

**Verify from backend**:
```bash
# From any machine
curl http://192.168.1.100:8000/api/v1/workers | jq

# Should show all registered workers:
# [
#   {
#     "worker_id": "ktrdr-worker-bt-1",
#     "worker_type": "backtesting",
#     "endpoint_url": "http://192.168.1.201:5003",
#     "status": "AVAILABLE",
#     ...
#   },
#   ...
# ]
```

---

## GPU Training Host Setup

GPU training requires direct hardware access, so it runs as a native service (not in LXC).

### Step 1: Prepare GPU Host Machine

**Verify GPU**:
```bash
# On GPU host
nvidia-smi

# Expected: GPU information displayed
```

**Install CUDA** (if not installed):
```bash
# Ubuntu 22.04
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get install -y cuda-toolkit-12-3

# Verify
nvcc --version
```

### Step 2: Deploy Training Host Service

**Clone repository**:
```bash
# On GPU host
cd /opt
sudo git clone https://github.com/your-org/ktrdr.git
cd ktrdr/training-host-service

# Install dependencies
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="/root/.local/bin:$PATH"
uv sync

# Verify GPU support
uv run python -c "import torch; print(torch.cuda.is_available())"
# Expected: True
```

**Configure environment**:
```bash
# /opt/ktrdr/training-host-service/.env
cat > .env << 'EOF'
KTRDR_API_URL=http://192.168.1.100:8000
WORKER_ENDPOINT_URL=http://192.168.1.20:5002
WORKER_PORT=5002
LOG_LEVEL=INFO
EOF
```

**Start service**:
```bash
# Use provided script
./start.sh

# Or create systemd service (recommended for production)
sudo cat > /etc/systemd/system/ktrdr-training-host.service << 'EOF'
[Unit]
Description=KTRDR Training Host Service (GPU)
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/opt/ktrdr/training-host-service
EnvironmentFile=/opt/ktrdr/training-host-service/.env
ExecStart=/root/.local/bin/uv run python -m uvicorn main:app --host 0.0.0.0 --port 5002
Restart=always
RestartSec=10s

StandardOutput=journal
StandardError=journal
SyslogIdentifier=ktrdr-training-host

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable ktrdr-training-host
sudo systemctl start ktrdr-training-host
```

### Step 3: Verify GPU Host Registration

```bash
# Check registration
curl http://192.168.1.100:8000/api/v1/workers | \
  jq '.[] | select(.capabilities.gpu==true)'

# Expected:
# {
#   "worker_id": "training-host-1",
#   "worker_type": "training",
#   "endpoint_url": "http://192.168.1.20:5002",
#   "capabilities": {
#     "gpu": true,
#     "gpu_type": "CUDA",
#     "gpu_count": 2,
#     "gpu_memory_gb": 24
#   },
#   "status": "AVAILABLE"
# }
```

---

## Network Configuration

### IP Address Planning

**Fixed IP Assignments** (example):

| Range | Purpose | Example |
|-------|---------|---------|
| 192.168.1.100-109 | Backend & Services | Backend: 192.168.1.100 |
| 192.168.1.201-250 | Worker LXCs | Workers: 192.168.1.201-205 |
| 192.168.1.20-29 | GPU Hosts | GPU Host: 192.168.1.20 |
| 192.168.1.21 | IB Host | IB Host: 192.168.1.21 |

**Important**: Workers must use their actual routable IPs (not Docker DNS names) so the backend can reach them for health checks.

### Firewall Configuration

**Backend LXC (192.168.1.100)**:
```bash
# Inside backend container
# Allow API access from workers and clients
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT

# Save rules (Debian/Ubuntu)
apt-get install -y iptables-persistent
netfilter-persistent save
```

**Worker LXCs** (each worker):
```bash
# Inside worker container
# Allow operations and health checks from backend
iptables -A INPUT -p tcp --dport 5003 -s 192.168.1.100 -j ACCEPT  # Backtest
iptables -A INPUT -p tcp --dport 5004 -s 192.168.1.100 -j ACCEPT  # Training

netfilter-persistent save
```

**Proxmox Host Firewall** (optional, via Web UI):
1. Navigate to: Datacenter → Firewall
2. Create rule:
   - Direction: IN
   - Action: ACCEPT
   - Protocol: tcp
   - Dest port: 8000 (backend)
   - Comment: KTRDR Backend API
3. Apply

### DNS Configuration (Optional)

**Update /etc/hosts** on each LXC:
```bash
# On backend and all workers
cat >> /etc/hosts << 'EOF'
192.168.1.100   ktrdr-backend
192.168.1.201   ktrdr-worker-bt-1
192.168.1.202   ktrdr-worker-bt-2
192.168.1.203   ktrdr-worker-bt-3
192.168.1.20    ktrdr-gpu-host
192.168.1.21    ktrdr-ib-host
EOF
```

---

## Verification & Testing

### 1. Check LXC Status

**On Proxmox host**:
```bash
# List all KTRDR containers
pct list | grep ktrdr

# Expected:
# 100  running  ktrdr-backend
# 201  running  ktrdr-worker-bt-1
# 202  running  ktrdr-worker-bt-2
# ...
```

### 2. Verify Worker Registration

**Check registry**:
```bash
curl http://192.168.1.100:8000/api/v1/workers | jq -r '.[] | "\(.worker_id): \(.status)"'

# Expected:
# ktrdr-worker-bt-1: AVAILABLE
# ktrdr-worker-bt-2: AVAILABLE
# ktrdr-worker-bt-3: AVAILABLE
# training-host-1: AVAILABLE
```

**Count by type**:
```bash
curl http://192.168.1.100:8000/api/v1/workers | \
  jq 'group_by(.worker_type) | map({type: .[0].worker_type, count: length})'

# Expected:
# [
#   {"type": "backtesting", "count": 5},
#   {"type": "training", "count": 3}
# ]
```

### 3. Test Backtest Execution

**Start backtest**:
```bash
curl -X POST http://192.168.1.100:8000/api/v1/backtests/start \
  -H "Content-Type: application/json" \
  -d '{
    "model_path": "/models/ktrdr/neuro_mean_reversion/1d_v21",
    "strategy_name": "neuro_mean_reversion",
    "symbol": "EURUSD",
    "timeframe": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }' | jq

# Save operation ID
OPERATION_ID=$(curl -s ... | jq -r '.operation_id')
```

**Monitor progress**:
```bash
watch -n 2 "curl -s http://192.168.1.100:8000/api/v1/operations/$OPERATION_ID | jq '.progress'"
```

**Verify completion**:
```bash
curl http://192.168.1.100:8000/api/v1/operations/$OPERATION_ID | jq

# Check status: "completed"
# Check result: {...}
```

### 4. Test GPU Training

**Start training**:
```bash
curl -X POST http://192.168.1.100:8000/api/v1/trainings/start \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_yaml": "...",
    "symbols": ["EURUSD"],
    "timeframe": "1d",
    "prefer_gpu": true
  }' | jq

# Check worker_id in response - should be GPU host
```

### 5. End-to-End System Test

**Run comprehensive test**:
```bash
# Start multiple operations concurrently
for i in {1..10}; do
  curl -X POST http://192.168.1.100:8000/api/v1/backtests/start \
    -H "Content-Type: application/json" \
    -d "{...}" &
done

# Monitor worker status
watch -n 5 'curl -s http://192.168.1.100:8000/api/v1/workers | \
  jq ".[] | {worker_id, status, current_op: .metadata.current_operation}"'

# Expected:
# - Operations distributed across workers
# - All workers show BUSY during execution
# - Workers return to AVAILABLE after completion
# - All operations complete successfully
```

---

## Monitoring & Maintenance

### Worker Health Monitoring

**Automated health checks** (backend does this automatically):
- Polls each worker every 10 seconds
- 3 consecutive failures → TEMPORARILY_UNAVAILABLE
- 5 minutes unavailable → REMOVED from registry

**Manual health check**:
```bash
# Check all workers
curl http://192.168.1.100:8000/api/v1/workers/health | jq

# Expected:
# {
#   "total_workers": 8,
#   "available": 8,
#   "busy": 0,
#   "temporarily_unavailable": 0
# }
```

### Log Management

**Backend logs**:
```bash
# Inside backend LXC
journalctl -u ktrdr-backend -f

# Or on Proxmox host
pct exec 100 -- journalctl -u ktrdr-backend -f
```

**Worker logs**:
```bash
# Inside worker LXC
journalctl -u ktrdr-worker -f

# On Proxmox host
pct exec 201 -- journalctl -u ktrdr-worker -f
```

**Aggregate logs** (all workers):
```bash
# On Proxmox host
for i in {201..205}; do
  echo "=== Worker $i ===="
  pct exec $i -- journalctl -u ktrdr-worker --since "10 minutes ago" -n 20
done
```

### Disk Space Management

**Check disk usage**:
```bash
# On Proxmox host
for i in 100 {201..205}; do
  echo "=== CT $i ==="
  pct exec $i -- df -h /
done

# Expected: < 80% usage
```

**Clean up logs** (inside container):
```bash
# Rotate logs
journalctl --vacuum-time=7d
journalctl --vacuum-size=500M
```

### Template Updates

**When to update template**:
- Security updates (monthly)
- Python/dependency upgrades (quarterly)
- Configuration changes affecting all workers

**Update process**:
1. Start template container: `pct start 900`
2. Update packages: `pct exec 900 -- apt-get update && apt-get upgrade -y`
3. Update ktrdr code: `pct exec 900 -- cd /opt/ktrdr && git pull`
4. Stop template: `pct stop 900`
5. Create new snapshot: `pct snapshot 900 template-v1.1 --description "Updated 2025-11-10"`
6. Deploy updates to workers (see Worker Refresh below)

### Worker Refresh

**Rolling update** (no downtime):
```bash
# Update workers one at a time
for i in {201..205}; do
  echo "Updating worker $i..."

  # Stop worker
  pct exec $i -- systemctl stop ktrdr-worker

  # Update code
  rsync -avz /opt/ktrdr/ root@192.168.1.$i:/opt/ktrdr/

  # Restart worker
  pct exec $i -- systemctl start ktrdr-worker

  # Wait for registration
  sleep 10

  # Verify
  curl -s http://192.168.1.100:8000/api/v1/workers | \
    jq ".[] | select(.worker_id==\"ktrdr-worker-bt-$(($i-200))\") | .status"
done
```

### Backup and Restore

**Backup LXCs**:
```bash
# Backup backend
vzdump 100 --storage backups --compress zstd --mode stop

# Backup all workers
vzdump 201-205 --storage backups --compress zstd --mode snapshot

# List backups
pvesm list backups
```

**Restore from backup**:
```bash
# Restore backend to new CT ID
pct restore 110 /mnt/backups/vzdump-lxc-100-*.tar.zst \
  --storage local-lvm

# Update network config for new IP if needed
pct set 110 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.110/24
pct start 110
```

---

## Scaling Operations

### Adding Workers

**Scale up** (add 5 more backtest workers):
```bash
# On Proxmox host
for i in {6..10}; do
  CTID=$((200 + i))
  IP=$((200 + i))

  echo "Creating worker $i (CT $CTID)..."

  # Clone from template
  pct clone 900 $CTID --hostname ktrdr-worker-bt-$i --full

  # Configure resources
  pct set $CTID --cores 4 --memory 8192

  # Configure network
  pct set $CTID --net0 name=eth0,bridge=vmbr0,ip=192.168.1.$IP/24,gw=192.168.1.1

  # Start
  pct start $CTID

  # Deploy code (wait for container to be ready)
  sleep 10
  rsync -avz /opt/ktrdr/ root@192.168.1.$IP:/opt/ktrdr/

  # Configure and start service
  pct exec $CTID -- bash -c "cd /opt/ktrdr && ./setup-worker.sh backtest 192.168.1.$IP"

  echo "Worker $i ready!"
done

# Verify
curl http://192.168.1.100:8000/api/v1/workers | \
  jq '[.[] | select(.worker_type=="backtesting")] | length'
# Expected: 10
```

### Removing Workers

**Graceful removal**:
```bash
# Check if worker is idle
WORKER_ID="ktrdr-worker-bt-5"
curl http://192.168.1.100:8000/api/v1/workers | \
  jq ".[] | select(.worker_id==\"$WORKER_ID\") | .metadata.current_operation"

# If null (idle), safe to remove
CTID=205

# Stop worker service
pct exec $CTID -- systemctl stop ktrdr-worker

# Stop container
pct stop $CTID

# Optional: Destroy container (after backend removes from registry)
# Wait 5+ minutes for backend cleanup
# pct destroy $CTID
```

### Multi-Host Distribution

**Deploy workers across Proxmox hosts**:

**Host A** (Proxmox host 192.168.1.10):
```bash
# 3 workers on Host A
for i in {1..3}; do
  CTID=$((200 + i))
  # Clone, configure, start (same as above)
done
```

**Host B** (Proxmox host 192.168.1.11):
```bash
# 2 workers on Host B
for i in {4..5}; do
  CTID=$((200 + i))
  # Clone, configure, start (same as above)
done
```

All workers register with backend at 192.168.1.100 automatically!

---

## Troubleshooting

### Issue 1: Worker Not Registering

**Symptoms**:
- Worker service running
- Worker not appearing in backend registry

**Diagnosis**:
```bash
# Check worker logs
pct exec 201 -- journalctl -u ktrdr-worker -n 50

# Look for:
# "Failed to register with backend..."
# "Connection refused..."
```

**Solutions**:

**Cause 1: Wrong backend URL**
```bash
# Check environment
pct exec 201 -- cat /opt/ktrdr/.env | grep KTRDR_API_URL

# Should be: KTRDR_API_URL=http://192.168.1.100:8000

# Fix if wrong
pct exec 201 -- bash -c 'echo "KTRDR_API_URL=http://192.168.1.100:8000" >> /opt/ktrdr/.env'
pct exec 201 -- systemctl restart ktrdr-worker
```

**Cause 2: Network connectivity**
```bash
# Test from worker to backend
pct exec 201 -- curl -I http://192.168.1.100:8000/health

# If fails, check firewall and routing
pct exec 201 -- ping -c 3 192.168.1.100
```

**Cause 3: Backend not ready**
```bash
# Check backend status
pct exec 100 -- systemctl status ktrdr-backend

# Restart if needed
pct exec 100 -- systemctl restart ktrdr-backend
```

### Issue 2: Worker Marked as Dead

**Symptoms**:
- Worker status: TEMPORARILY_UNAVAILABLE
- Worker service running

**Diagnosis**:
```bash
# Check worker health endpoint
curl http://192.168.1.201:5003/health | jq

# Should return: {"healthy": true}

# If fails, check worker process
pct exec 201 -- ps aux | grep python
```

**Solutions**:

**Cause 1: Worker overloaded**
```bash
# Check resource usage on Proxmox host
pct status 201

# Check inside container
pct exec 201 -- top -b -n 1 | head -20

# If CPU/memory maxed: increase resources
pct set 201 --cores 8 --memory 16384
pct reboot 201
```

**Cause 2: Worker crashed**
```bash
# Check for errors
pct exec 201 -- journalctl -u ktrdr-worker --since "10 minutes ago" | grep -i error

# Restart worker
pct exec 201 -- systemctl restart ktrdr-worker
```

### Issue 3: LXC Networking Issues

**Symptoms**:
- Cannot reach worker from backend
- Worker cannot reach backend

**Diagnosis**:
```bash
# Check container network config
pct config 201 | grep net0

# Check IP inside container
pct exec 201 -- ip addr show eth0

# Test connectivity
pct exec 201 -- ping -c 3 192.168.1.100  # To backend
pct exec 100 -- ping -c 3 192.168.1.201  # To worker
```

**Solutions**:

**Cause 1: Wrong IP configuration**
```bash
# Reconfigure network
pct set 201 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1

# Restart container
pct reboot 201
```

**Cause 2: Firewall blocking**
```bash
# Check Proxmox firewall (Web UI: Container → Firewall)
# Or disable temporarily for testing:
pct set 201 --firewall 0

# Check container firewall
pct exec 201 -- iptables -L -n
```

### Issue 4: GPU Host Not Registering

**Symptoms**:
- GPU host service running
- No GPU workers in registry

**Diagnosis**:
```bash
# On GPU host
systemctl status ktrdr-training-host

# Check logs
journalctl -u ktrdr-training-host -n 50

# Test registration endpoint
curl http://192.168.1.100:8000/api/v1/workers/register -X POST \
  -H "Content-Type: application/json" \
  -d '{"worker_id": "test", "worker_type": "training", "endpoint_url": "http://192.168.1.20:5002", "capabilities": {"gpu": true}}'
```

**Solutions**:

**Cause 1: Wrong backend URL**
```bash
# Check configuration
cat /opt/ktrdr/training-host-service/.env

# Fix if needed
echo "KTRDR_API_URL=http://192.168.1.100:8000" >> .env
systemctl restart ktrdr-training-host
```

**Cause 2: GPU not detected**
```bash
# Verify GPU
nvidia-smi

# Verify PyTorch can see GPU
cd /opt/ktrdr/training-host-service
uv run python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"

# Expected: CUDA available: True
```

### Issue 5: Storage Mount Issues

**Symptoms**:
- Workers cannot access shared data
- Models not found

**Diagnosis**:
```bash
# Check mounts
pct exec 201 -- mount | grep ktrdr

# Check NFS mount
pct exec 201 -- df -h | grep nfs

# Test access
pct exec 201 -- ls -la /data/ktrdr
```

**Solutions**:

**Cause 1: NFS not mounted**
```bash
# Mount NFS manually
pct exec 201 -- mount -t nfs 192.168.1.50:/exports/ktrdr/data /data/ktrdr

# Make permanent in /etc/fstab
pct exec 201 -- bash -c 'echo "192.168.1.50:/exports/ktrdr/data /data/ktrdr nfs defaults 0 0" >> /etc/fstab'
```

**Cause 2: Permissions**
```bash
# Check ownership
pct exec 201 -- ls -la /data/ktrdr

# Fix if needed (on NFS server)
sudo chown -R 1000:1000 /exports/ktrdr
```

---

## Performance Tuning

### CPU Allocation

**Balanced allocation** (recommended):
- Backend: 4 cores (orchestration overhead minimal)
- Workers: 4 cores each (balance between parallelism and single-op performance)

**High-throughput allocation**:
- Backend: 4 cores
- Workers: 2 cores each (more workers, more parallel ops)

**Example**: 32-core host
```bash
# 1 backend (4 cores) + 7 workers (4 cores each) = 32 cores
pct set 100 --cores 4
for i in {201..207}; do pct set $i --cores 4; done
```

### Memory Allocation

**Minimum**:
- Backend: 8GB
- Workers: 4GB each

**Recommended**:
- Backend: 8GB
- Backtest workers: 8GB each (larger backtests need more memory)
- Training workers: 12-16GB each (model training is memory-intensive)

**Check actual usage**:
```bash
# On Proxmox host
for i in 100 {201..205}; do
  echo "=== CT $i ==="
  pct exec $i -- free -h
done
```

### Storage Performance

**Backend storage**:
- SSD recommended (logs, operation metadata)
- 20GB minimum, 50GB recommended

**Worker storage**:
- SSD recommended (temporary computation data)
- 15GB minimum per worker

**Shared storage** (NFS):
- 10GbE network recommended for large datasets
- SSD-backed NFS server for models

**ZFS tuning** (if using ZFS):
```bash
# On Proxmox host
# Increase ARC size for better caching
echo "options zfs zfs_arc_max=$((16*1024*1024*1024))" > /etc/modprobe.d/zfs.conf
update-initramfs -u
```

### Network Performance

**Bonding** (aggregate multiple NICs):
```bash
# On Proxmox host - /etc/network/interfaces
auto bond0
iface bond0 inet manual
    bond-slaves eno1 eno2
    bond-miimon 100
    bond-mode 802.3ad
    bond-xmit-hash-policy layer2+3

auto vmbr0
iface vmbr0 inet static
    address 192.168.1.10/24
    bridge-ports bond0
    bridge-stp off
    bridge-fd 0
```

**10GbE recommended** for:
- Shared NFS storage
- Multi-host worker communication
- Large data transfers

---

## Summary

This Proxmox deployment guide covered:

1. **Why Proxmox**: Performance benefits, management tools, production readiness
2. **Architecture**: Backend + Worker LXCs + GPU/IB host services
3. **Prerequisites**: Proxmox VE, network, shared storage requirements
4. **LXC Template**: Creating base template for worker cloning
5. **Backend Deployment**: Backend LXC setup, code deployment, systemd service
6. **Worker Deployment**: Worker LXC cloning, configuration, registration
7. **GPU Host Setup**: Native GPU training service for CUDA access
8. **Network Configuration**: IP planning, firewall rules, DNS
9. **Verification**: Worker registration, backtest/training tests
10. **Monitoring**: Health checks, logs, disk space, backups
11. **Scaling**: Adding/removing workers, multi-host distribution
12. **Troubleshooting**: Common issues and solutions
13. **Performance Tuning**: CPU, memory, storage, network optimization

**Key Takeaways**:

- Proxmox LXC provides production-grade distributed execution with lower overhead than Docker
- Template-based cloning enables rapid worker scaling
- Workers self-register automatically (no manual configuration)
- Multi-host distribution leverages Proxmox clustering
- Comprehensive monitoring and maintenance procedures for 24/7 operation

**Next Steps**:

- **For CI/CD**: See [CI/CD Operations Runbook](../developer/cicd-operations-runbook.md)
- **For Development**: See [Docker Compose Deployment Guide](deployment.md)
- **For Architecture**: See [Distributed Workers Architecture](../architecture-overviews/distributed-workers.md)

---

**Document Version**: 1.0
**Last Updated**: 2025-11-10
