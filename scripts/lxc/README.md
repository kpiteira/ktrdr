# KTRDR LXC Template Creation

This directory contains scripts for creating and managing Proxmox LXC templates for KTRDR workers.

## Overview

The LXC template system enables **continuous deployment** by separating:
- **Template** (base environment) - Changes rarely
- **Code** (KTRDR application) - Deployed separately, changes frequently

This separation allows deploying code updates to all workers without rebuilding templates.

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

### Creating a Worker from Template

```bash
# Create worker LXC container from template
pct create 201 local:vztmpl/ktrdr-worker-base-v1.tar.zst \
  --hostname ktrdr-backtest-worker-1 \
  --memory 4096 \
  --cores 4 \
  --rootfs local-lvm:16 \
  --net0 name=eth0,bridge=vmbr0,ip=192.168.1.201/24,gw=192.168.1.1

# Start the worker
pct start 201
```

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

## Related Documentation

- **Code Deployment**: `scripts/deploy/README.md` (Task 6.2)
- **Worker Provisioning**: `scripts/lxc/provision-worker.sh` (Task 6.3)
- **Proxmox Deployment Guide**: `docs/user-guides/deployment-proxmox.md` (Task 6.6)
- **Distributed Architecture**: `docs/architecture/distributed/ARCHITECTURE.md`

## References

- [Proxmox LXC Documentation](https://pve.proxmox.com/wiki/Linux_Container)
- [Ubuntu Cloud Images](http://cloud-images.ubuntu.com/)
- [uv Package Manager](https://github.com/astral-sh/uv)
