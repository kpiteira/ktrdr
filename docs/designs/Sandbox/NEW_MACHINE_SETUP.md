# Setting Up KTRDR on a New Machine

This guide walks through setting up a complete KTRDR development environment on a new machine.

## Prerequisites

Before starting, ensure you have:

- **Docker Desktop** installed and running
- **Git** configured with SSH key for GitHub access
- **Python 3.11+** with [uv](https://github.com/astral-sh/uv) package manager

## Quick Start

### 1. Clone the Repository

```bash
git clone git@github.com:kpiteira/ktrdr.git
cd ktrdr
```

### 2. Install Dependencies

```bash
uv sync
```

### 3. Initialize Shared Data

The shared data directory (`~/.ktrdr/shared/`) stores symbol data, models, and strategies that are shared across all sandbox instances.

**Option A: Copy from existing environment** (recommended if you have data)

```bash
uv run ktrdr sandbox init-shared --from /path/to/backup
# Or from another KTRDR install:
uv run ktrdr sandbox init-shared --from ~/Documents/dev/ktrdr2
```

**Option B: Start with empty structure** (download data later)

```bash
uv run ktrdr sandbox init-shared --minimal
```

### 4. Create Your First Sandbox

```bash
uv run ktrdr sandbox create dev
cd ../ktrdr--dev
uv run ktrdr sandbox up
```

### 5. Verify Installation

```bash
# Check API health
curl http://localhost:8001/api/v1/health

# Open Grafana dashboard
open http://localhost:3001

# View status
uv run ktrdr sandbox status
```

## Transferring Data Between Machines

### From the Source Machine

Create an archive of your shared data:

```bash
tar -czvf ktrdr-shared-data.tar.gz -C ~ .ktrdr/shared/
```

Transfer the archive to your new machine (USB drive, cloud storage, scp, etc.).

### On the New Machine

Extract the archive:

```bash
# Extract to home directory
tar -xzvf ktrdr-shared-data.tar.gz -C ~

# Verify
ls -la ~/.ktrdr/shared/
```

### Direct Network Transfer

If both machines are on the same network:

```bash
# On new machine, pull from old machine
rsync -avz oldmachine:~/.ktrdr/shared/ ~/.ktrdr/shared/

# Or push from old machine to new
rsync -avz ~/.ktrdr/shared/ newmachine:~/.ktrdr/shared/
```

## Directory Structure

After setup, your directories will look like this:

```
~/
├── Documents/dev/
│   ├── ktrdr/                    # Main repository
│   └── ktrdr--dev/               # Sandbox instance (created by sandbox create)
│
└── .ktrdr/
    ├── sandbox/
    │   └── instances.json        # Registry of sandbox instances
    └── shared/
        ├── data/                 # Symbol data (OHLCV CSVs)
        ├── models/               # Trained ML models
        └── strategies/           # Strategy configurations
```

### What Each Directory Contains

| Directory | Contents | Shared? |
|-----------|----------|---------|
| `~/.ktrdr/shared/data/` | Historical market data (CSV files like `AAPL_1d.csv`) | Yes, across all sandboxes |
| `~/.ktrdr/shared/models/` | Trained machine learning models | Yes, across all sandboxes |
| `~/.ktrdr/shared/strategies/` | Strategy configuration files | Yes, across all sandboxes |
| `~/.ktrdr/sandbox/` | Sandbox instance registry | N/A (metadata only) |

## Common Commands

```bash
# List all sandbox instances
uv run ktrdr sandbox list

# Check status of current sandbox
uv run ktrdr sandbox status

# Stop sandbox (keep data)
uv run ktrdr sandbox down

# Stop and remove all data
uv run ktrdr sandbox down --volumes

# Destroy sandbox completely
uv run ktrdr sandbox destroy
```

## Troubleshooting

### Port Conflicts

If `ktrdr sandbox up` fails with port conflicts:

```bash
# Check what's using the port
lsof -i :8001

# List sandbox instances to see allocated ports
uv run ktrdr sandbox list
```

### Shared Data Not Found

If containers can't access shared data:

```bash
# Verify shared data exists
ls -la ~/.ktrdr/shared/

# Re-initialize if needed
uv run ktrdr sandbox init-shared --minimal
```

### Docker Issues

```bash
# Restart Docker Desktop
# Then restart sandbox
uv run ktrdr sandbox down
uv run ktrdr sandbox up
```

## Next Steps

Once your environment is running:

1. **Run tests**: `make test-unit` (fast), `make test-integration`
2. **Check quality**: `make quality`
3. **View API docs**: http://localhost:8001/api/v1/docs
4. **Monitor with Grafana**: http://localhost:3001
