# KTRDR LXC Templates and Worker Provisioning

This directory contains scripts for creating Proxmox LXC templates and provisioning workers from those templates.

## Overview

The LXC template system enables **continuous deployment** by separating:
- **Template** (base environment) - Changes rarely (Task 6.1)
- **Worker Provisioning** (create workers from template) - Fast, automated (Task 6.3)
- **Code** (KTRDR application) - Deployed separately, changes frequently (Task 6.2)

This separation allows:
1. **One-time template creation** - Build base environment once
2. **Fast worker provisioning** - Clone workers in seconds
3. **Rapid code deployment** - Update all workers in minutes

## Template Contents

### What's INCLUDED in the template:

- **Operating System**: Ubuntu 22.04 LTS
- **Python**: Python 3.13 with development headers
- **Package Manager**: `uv` (Astral's fast Python package manager)
- **System Dependencies**:
  - curl, git, wget
  - build-essential (gcc, make, etc.)
  - ca-certificates
- **Directory Structure**:
  - `/opt/ktrdr` - Application root
  - `/opt/ktrdr/logs` - Log files
  - `/opt/ktrdr/data` - Data files
  - `/opt/ktrdr/models` - Model files
- **System User**: `ktrdr` user for running services

### What's NOT INCLUDED in the template:

- ❌ KTRDR code (deployed separately via git/scripts)
- ❌ Configuration files (.env, config/)
- ❌ Environment variables
- ❌ Trained models or data files
- ❌ Virtual environment (.venv)

## Prerequisites

Before running the template creation script:

- **Proxmox VE 8.x** installed and configured
- **Root access** (or sudo privileges)
- **Network connectivity** for downloading packages
- **Storage space**: At least 10GB available in `/var/lib/vz/template/cache/`
- **Ubuntu 22.04 template** available in Proxmox:
  - Download from: http://download.proxmox.com/images/system/
  - Place in: `/var/lib/vz/template/cache/`
  - Expected name: `ubuntu-22.04-standard_22.04-1_amd64.tar.zst`

## Creating the Template

### Step 1: Prepare Proxmox Environment

Ensure you have the Ubuntu base template:

```bash
# Check if Ubuntu template exists
ls -lh /var/lib/vz/template/cache/ubuntu-22.04*.tar.zst

# If not, download it:
cd /var/lib/vz/template/cache/
wget http://download.proxmox.com/images/system/ubuntu-22.04-standard_22.04-1_amd64.tar.zst
```

### Step 2: Run Template Creation Script

```bash
# Clone KTRDR repository (if not already done)
cd /opt
git clone https://github.com/your-org/ktrdr.git
cd ktrdr

# Run template creation script
cd scripts/lxc
./create-template.sh
```

The script will:
1. Create LXC container (ID 999)
2. Start container and wait for network
3. Install Python 3.13 and system dependencies
4. Install uv package manager
5. Create base directory structure
6. Clean up temporary files
7. Stop container
8. Convert to template using `vzdump`
9. Save as `/var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst`
10. Destroy source container

### Step 3: Verify Template

```bash
# Check template was created
ls -lh /var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst

# Should show ~300-500MB template file
```

## Using the Template

### Creating a Worker from Template (Manual Method)

**Note:** Use `provision-worker.sh` (Task 6.3) for automated provisioning instead!

```bash
# Manual method (if you need fine-grained control)
pct clone 999 201 --hostname ktrdr-backtest-worker-1
pct set 201 --net0 name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1
pct start 201
```

### Creating a Worker from Template (Automated Method - Recommended)

**Use the automated provisioning script:**

```bash
# Provision backtesting worker
./provision-worker.sh 201 192.168.1.201 backtesting

# Provision training worker
./provision-worker.sh 202 192.168.1.202 training

# Default is backtesting if type not specified
./provision-worker.sh 203 192.168.1.203
```

See **Worker Provisioning** section below for details.

### Verifying Base Environment

```bash
# Start the container
pct start 201

# Verify Python 3.13 is installed
pct exec 201 -- python3.13 --version
# Expected: Python 3.13.x

# Verify uv is installed
pct exec 201 -- su - ktrdr -c "uv --version"
# Expected: uv x.x.x

# Verify directory structure
pct exec 201 -- ls -la /opt/ktrdr
# Expected: logs/, data/, models/ directories exist
```

## Deploying Code to Workers

Once the worker is created from the template, deploy KTRDR code:

```bash
# Enter the container
pct enter 201

# Switch to ktrdr user
su - ktrdr

# Clone KTRDR repository
cd /opt/ktrdr
git clone https://github.com/your-org/ktrdr.git .

# Checkout desired branch
git checkout main  # or specific version tag

# Install Python dependencies with uv
uv sync

# Create .env file with environment-specific configuration
cat > .env << EOF
KTRDR_API_URL=http://192.168.1.100:8000
WORKER_ENDPOINT_URL=http://192.168.1.201:5003
WORKER_TYPE=backtesting
WORKER_ID=backtest-worker-1
EOF

# Exit container
exit
exit
```

## Configuration

### Template Configuration Variables

Edit `create-template.sh` to customize template settings:

```bash
# Container ID for template creation (will be destroyed after)
TEMPLATE_ID=999

# Template output name
TEMPLATE_NAME="ktrdr-worker-base-v1"

# Ubuntu base template name
UBUNTU_TEMPLATE="ubuntu-22.04-standard_22.04-1_amd64.tar.zst"

# Resource allocation during template creation
MEMORY_MB=2048  # RAM for template build
CORES=2         # CPU cores for template build
DISK_GB=8       # Disk size for template build
```

## Troubleshooting

### Issue: "pct command not found"

**Cause**: Script is not running on Proxmox VE

**Solution**: This script must run on a Proxmox VE host. Copy it to your Proxmox server:

```bash
scp scripts/lxc/create-template.sh root@proxmox-host:/tmp/
ssh root@proxmox-host "bash /tmp/create-template.sh"
```

### Issue: "Container 999 already exists"

**Cause**: Previous template creation was interrupted

**Solution**: The script automatically handles this. If manual cleanup is needed:

```bash
pct stop 999
pct destroy 999
```

### Issue: "Network timeout" during package installation

**Cause**: Container cannot reach internet

**Solution**:
1. Check Proxmox network configuration
2. Verify DHCP is available on vmbr0
3. Or use static IP: Edit `create-template.sh` and change:
   ```bash
   --net0 name=eth0,bridge=vmbr0,ip=192.168.1.99/24,gw=192.168.1.1
   ```

### Issue: "Python 3.13 not available"

**Cause**: Ubuntu repositories don't have Python 3.13 yet

**Solution**: Script will need to be updated to install from deadsnakes PPA:

```bash
pct exec "$TEMPLATE_ID" -- bash -c "
    add-apt-repository ppa:deadsnakes/ppa -y
    apt-get update
    apt-get install -y python3.13 python3.13-venv python3.13-dev
"
```

## Template Versioning

Template naming convention: `ktrdr-worker-base-vX`

- **v1**: Initial template (Ubuntu 22.04, Python 3.13, uv)
- **v2**: Future versions with updated dependencies

When creating new template versions:

1. Update `TEMPLATE_NAME` in script
2. Run `create-template.sh` to create new template
3. Test new template thoroughly before production use
4. Keep old template for rollback capability

## Maintenance

### Updating the Template

When system dependencies need updates:

1. Modify `create-template.sh` to add new packages
2. Increment template version (v1 → v2)
3. Create new template
4. Test with one worker
5. Roll out to all workers

### Template Storage

Templates are stored in: `/var/lib/vz/template/cache/`

```bash
# List all templates
ls -lh /var/lib/vz/template/cache/

# Remove old template versions (careful!)
rm /var/lib/vz/template/cache/ktrdr-worker-base-v0.tar.zst
```

### Backup Template

```bash
# Copy template to backup location
cp /var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst \
   /backup/lxc-templates/

# Or to another Proxmox host
scp /var/lib/vz/template/cache/ktrdr-worker-base-v1.tar.zst \
    root@proxmox-host2:/var/lib/vz/template/cache/
```

## Worker Provisioning (Task 6.3)

After creating the base template, use `provision-worker.sh` to quickly create new workers.

### Quick Start

```bash
# Provision a backtesting worker
./provision-worker.sh 201 192.168.1.201 backtesting

# Provision a training worker
./provision-worker.sh 202 192.168.1.202 training
```

### What the Provisioning Script Does

1. **Clones worker from template** (ID 999)
2. **Configures network** settings (IP, gateway)
3. **Starts the container**
4. **Creates .env file** with worker configuration:
   - `KTRDR_API_URL` - Backend API endpoint
   - `WORKER_ENDPOINT_URL` - Worker's own URL
   - `WORKER_TYPE` - backtesting or training
   - `WORKER_ID` - Unique identifier

### Usage

```bash
./provision-worker.sh WORKER_ID WORKER_IP [WORKER_TYPE]
```

**Parameters:**
- `WORKER_ID` (required) - Unique LXC container ID (e.g., 201, 202, 203)
- `WORKER_IP` (required) - IP address for the worker (e.g., 192.168.1.201)
- `WORKER_TYPE` (optional) - "backtesting" or "training" (default: "backtesting")

### Examples

```bash
# Backtesting workers
./provision-worker.sh 201 192.168.1.201 backtesting
./provision-worker.sh 202 192.168.1.202 backtesting
./provision-worker.sh 203 192.168.1.203  # Defaults to backtesting

# Training workers
./provision-worker.sh 204 192.168.1.204 training
./provision-worker.sh 205 192.168.1.205 training
```

### Provisioning Multiple Workers

```bash
# Provision 5 backtesting workers
for i in {201..205}; do
    ./provision-worker.sh $i 192.168.1.$i backtesting
done

# Provision 3 training workers
for i in {211..213}; do
    ./provision-worker.sh $i 192.168.1.$i training
done
```

### After Provisioning

Once a worker is provisioned, you need to:

1. **Deploy code** (see Task 6.2):
   ```bash
   ./scripts/deploy/deploy-code.sh "201" main
   ```

2. **Install systemd service**:
   ```bash
   pct enter 201
   cp /opt/ktrdr/scripts/deploy/systemd/ktrdr-backtest-worker.service \
      /etc/systemd/system/ktrdr-worker.service
   systemctl daemon-reload
   systemctl enable ktrdr-worker
   systemctl start ktrdr-worker
   ```

3. **Verify worker is healthy**:
   ```bash
   curl http://192.168.1.201:5003/health
   ```

### Environment Variables

The provisioning script supports customization via environment variables:

- `KTRDR_BACKEND_API` - Backend API URL (default: http://192.168.1.100:8000)
- `KTRDR_GATEWAY` - Network gateway (default: 192.168.1.1)
- `KTRDR_NETMASK` - Network mask (default: 24)

Example:
```bash
export KTRDR_BACKEND_API="http://10.0.0.100:8000"
export KTRDR_GATEWAY="10.0.0.1"
./provision-worker.sh 201 10.0.0.201 backtesting
```

### Troubleshooting Provisioning

#### Issue: "Template 999 does not exist"

**Solution:** Create the base template first:
```bash
./create-template.sh
```

#### Issue: "Worker ID already exists"

**Solution:** Choose a different ID or destroy existing worker:
```bash
pct stop 201
pct destroy 201
```

#### Issue: "Worker failed to become ready"

**Cause:** Network configuration issue

**Solution:**
```bash
# Check if worker started
pct status 201

# Check network inside container
pct enter 201
ping 192.168.1.1  # Test gateway
ping 8.8.8.8      # Test internet
```

## Related Documentation

- **Code Deployment**: [scripts/deploy/README.md](../deploy/README.md) (Task 6.2)
- **Worker Provisioning**: `scripts/lxc/provision-worker.sh` (Task 6.3 - this file)
- **Proxmox Deployment Guide**: `docs/user-guides/deployment-proxmox.md` (Task 6.6)
- **Distributed Architecture**: [docs/architecture/distributed/ARCHITECTURE.md](../../docs/architecture/distributed/ARCHITECTURE.md)

## References

- [Proxmox LXC Documentation](https://pve.proxmox.com/wiki/Linux_Container)
- [Ubuntu Cloud Images](http://cloud-images.ubuntu.com/)
- [uv Package Manager](https://github.com/astral-sh/uv)
