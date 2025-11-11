# KTRDR Deployment Configuration

This directory contains environment-specific configuration for deploying KTRDR workers.

## Configuration Files

```
config/
├── workers.dev.yaml      # Development workers configuration
├── workers.prod.yaml     # Production workers configuration
└── deploy/
    ├── dev.env           # Development environment variables
    ├── prod.env          # Production environment variables
    └── README.md         # This file
```

## Usage

### 1. Source Environment Configuration

Before running deployment or provisioning scripts, source the appropriate environment file:

```bash
# For development
source config/deploy/dev.env

# For production
source config/deploy/prod.env
```

### 2. Verify Configuration

```bash
# Check environment variables are set
echo $KTRDR_BACKEND_API
echo $KTRDR_GATEWAY
echo $KTRDR_GIT_REPO
```

### 3. Use with Deployment Scripts

The environment variables configure deployment and provisioning scripts:

```bash
# Source environment first
source config/deploy/dev.env

# Provision workers (uses environment variables)
./scripts/lxc/provision-worker.sh 211 192.168.1.211 backtesting

# Deploy code (uses GIT_REPO and GIT_REF from environment)
./scripts/deploy/deploy-code.sh "211 212 213" develop
```

## Environment Variables

### `KTRDR_BACKEND_API`
Backend API URL where workers will connect.

- **Dev**: `http://192.168.1.100:8000`
- **Prod**: `http://192.168.1.100:8000`

### `KTRDR_GATEWAY`
Network gateway for worker containers.

- **Default**: `192.168.1.1`

### `KTRDR_NETMASK`
Network mask in CIDR notation.

- **Default**: `24` (255.255.255.0)

### `KTRDR_GIT_REPO`
Git repository URL for code deployment.

- **Default**: `https://github.com/your-org/ktrdr.git`
- **Update** this to your actual repository URL!

### `KTRDR_GIT_REF`
Git branch or tag to deploy.

- **Dev**: `develop`
- **Prod**: `main`

### `KTRDR_WORKER_CONFIG`
Path to worker configuration YAML file.

- **Dev**: `config/workers.dev.yaml`
- **Prod**: `config/workers.prod.yaml`

### `KTRDR_ENV`
Environment name for logging/tracking.

- **Dev**: `development`
- **Prod**: `production`

## Workers Configuration (YAML)

### Structure

```yaml
# Backend API URL
backend_api_url: "http://192.168.1.100:8000"

# Network settings
network:
  gateway: "192.168.1.1"
  netmask: "24"

# Git repository
git_repo: "https://github.com/your-org/ktrdr.git"

# Workers list
workers:
  - id: 201                    # LXC container ID
    ip: "192.168.1.201"        # IP address
    type: "backtesting"        # Worker type (backtesting or training)
    hostname: "ktrdr-backtest-1"  # Container hostname
    cores: 4                   # CPU cores
    memory: 4096               # Memory in MB
```

### Development Workers

Defined in `config/workers.dev.yaml`:
- **IDs**: 211-213
- **IPs**: 192.168.1.211-213
- **Purpose**: Testing, development, experimentation
- **Resources**: Lower (2-4 cores, 2-4GB RAM)

### Production Workers

Defined in `config/workers.prod.yaml`:
- **IDs**: 201-207
- **IPs**: 192.168.1.201-207
- **Purpose**: Production backtesting and training
- **Resources**: Higher (4-8 cores, 4-8GB RAM)

## Provisioning Multiple Workers

### Development Environment

```bash
# Source dev environment
source config/deploy/dev.env

# Provision all dev workers
for worker in $(yq '.workers[] | "\(.id) \(.ip) \(.type)"' config/workers.dev.yaml); do
    id=$(echo $worker | awk '{print $1}')
    ip=$(echo $worker | awk '{print $2}')
    type=$(echo $worker | awk '{print $3}')
    ./scripts/lxc/provision-worker.sh $id $ip $type
done
```

### Production Environment

```bash
# Source prod environment
source config/deploy/prod.env

# Provision all prod workers
for worker in $(yq '.workers[] | "\(.id) \(.ip) \(.type)"' config/workers.prod.yaml); do
    id=$(echo $worker | awk '{print $1}')
    ip=$(echo $worker | awk '{print $2}')
    type=$(echo $worker | awk '{print $3}')
    ./scripts/lxc/provision-worker.sh $id $ip $type
done
```

## Deployment Workflows

### Complete Development Setup

```bash
# 1. Source environment
source config/deploy/dev.env

# 2. Create template (once)
./scripts/lxc/create-template.sh

# 3. Provision workers
./scripts/lxc/provision-worker.sh 211 192.168.1.211 backtesting
./scripts/lxc/provision-worker.sh 212 192.168.1.212 backtesting
./scripts/lxc/provision-worker.sh 213 192.168.1.213 training

# 4. Deploy code
./scripts/deploy/deploy-code.sh "211 212 213" develop

# 5. Install and start services
# (See scripts/deploy/README.md for service installation)
```

### Complete Production Setup

```bash
# 1. Source environment
source config/deploy/prod.env

# 2. Create template (once, if not already done)
./scripts/lxc/create-template.sh

# 3. Provision workers
./scripts/lxc/provision-worker.sh 201 192.168.1.201 backtesting
./scripts/lxc/provision-worker.sh 202 192.168.1.202 backtesting
# ... (continue for all workers)

# 4. Deploy code (production version)
./scripts/deploy/deploy-code.sh "201 202 203 204 205 206 207" main

# 5. Install and start services
# (See scripts/deploy/README.md for service installation)
```

## Customization

### Changing Network Configuration

Edit the environment file and worker configuration:

```bash
# config/deploy/prod.env
export KTRDR_GATEWAY="10.0.0.1"
export KTRDR_NETMASK="24"

# config/workers.prod.yaml
network:
  gateway: "10.0.0.1"
  netmask: "24"

workers:
  - id: 201
    ip: "10.0.0.201"  # Update IP addresses
    # ...
```

### Adding New Workers

Edit the workers YAML file:

```yaml
workers:
  # ... existing workers ...

  # New worker
  - id: 208
    ip: "192.168.1.208"
    type: "backtesting"
    hostname: "ktrdr-backtest-6"
    cores: 4
    memory: 4096
```

Then provision the new worker:

```bash
source config/deploy/prod.env
./scripts/lxc/provision-worker.sh 208 192.168.1.208 backtesting
```

## Best Practices

1. **Always source environment before deployment**
   - Ensures consistent configuration
   - Prevents accidental cross-environment deployment

2. **Keep configurations in version control**
   - Track changes to worker topology
   - Document infrastructure changes

3. **Use separate configurations for dev/prod**
   - Prevents accidental production deployment
   - Allows testing without affecting production

4. **Document custom changes**
   - Add comments to YAML files
   - Update this README for team reference

5. **Test in development first**
   - Always test changes in dev environment
   - Validate before promoting to production

## Related Documentation

- **LXC Templates**: [scripts/lxc/README.md](../../scripts/lxc/README.md) (Task 6.1)
- **Code Deployment**: [scripts/deploy/README.md](../../scripts/deploy/README.md) (Task 6.2)
- **Worker Provisioning**: [scripts/lxc/provision-worker.sh](../../scripts/lxc/provision-worker.sh) (Task 6.3)
- **Distributed Architecture**: [docs/architecture/distributed/ARCHITECTURE.md](../../docs/architecture/distributed/ARCHITECTURE.md)
