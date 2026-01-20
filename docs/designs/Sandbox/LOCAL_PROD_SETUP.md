# Local-Prod Setup Guide

Local-prod is your primary KTRDR execution environment for real work - connecting to IB Gateway, running GPU training, and using the MCP server with Claude. It's not for testing (that's what sandboxes are for).

## Prerequisites

Before starting, ensure you have:

- **macOS** with Docker Desktop installed and running
- **Git** configured with access to the KTRDR repository
- **uv** package manager ([installation](https://github.com/astral-sh/uv))
- **1Password CLI** (`op`) for secrets management ([installation](https://developer.1password.com/docs/cli/get-started/))

### Quick Prerequisite Check

Run the bootstrap script to verify all prerequisites:

```bash
curl -fsSL https://raw.githubusercontent.com/kpiteira/ktrdr/main/scripts/setup-local-prod.sh | bash -s -- --check-only
```

Or if you already have a clone:

```bash
./scripts/setup-local-prod.sh --check-only
```

---

## 1Password Setup

Local-prod uses 1Password to manage secrets securely. Create a 1Password item with the following configuration:

### Item Configuration

| Field | Value |
|-------|-------|
| **Item Name** | `ktrdr-local-prod` |
| **Item Type** | Login or Secure Note |

### Required Fields

Add these fields to the item:

| Field Name | Description | Example |
|------------|-------------|---------|
| `db_password` | PostgreSQL database password | `your-secure-db-password` |
| `jwt_secret` | JWT signing secret (min 32 chars) | `your-jwt-secret-minimum-32-characters` |
| `anthropic_api_key` | Anthropic API key for agents | `sk-ant-...` |
| `grafana_password` | Grafana admin password | `your-grafana-password` |

### Creating the Item

**Option A: 1Password Desktop App**

1. Open 1Password
2. Click "+" to create new item
3. Choose "Login" or "Secure Note"
4. Set title to `ktrdr-local-prod`
5. Add each field as a custom field

**Option B: 1Password CLI**

```bash
op item create \
  --category login \
  --title "ktrdr-local-prod" \
  --vault "Private" \
  'db_password[password]=YOUR_DB_PASSWORD' \
  'jwt_secret[password]=YOUR_JWT_SECRET_MIN_32_CHARS' \
  'anthropic_api_key[password]=sk-ant-YOUR_KEY' \
  'grafana_password[password]=YOUR_GRAFANA_PASSWORD'
```

### Without 1Password

If you don't want to use 1Password, you can start local-prod with insecure defaults:

```bash
ktrdr local-prod up --no-secrets
```

**Warning**: This uses hardcoded insecure defaults. Only use for testing, never for real work.

---

## Clone and Initialize

### Automated Setup (Recommended)

Use the bootstrap script for a guided setup:

```bash
curl -fsSL https://raw.githubusercontent.com/kpiteira/ktrdr/main/scripts/setup-local-prod.sh | bash
```

The script will:
1. Check prerequisites
2. Clone the repository
3. Install dependencies
4. Initialize local-prod
5. Offer to set up shared data

### Manual Setup

```bash
# 1. Clone the repository
git clone https://github.com/kpiteira/ktrdr.git ~/Documents/dev/ktrdr-prod
cd ~/Documents/dev/ktrdr-prod

# 2. Install dependencies
uv sync

# 3. Initialize as local-prod
uv run ktrdr local-prod init

# 4. Initialize shared data
# Option A: Copy from existing environment
uv run ktrdr sandbox init-shared --from ~/Documents/dev/ktrdr2

# Option B: Start with minimal structure
uv run ktrdr sandbox init-shared --minimal

# 5. Start local-prod
uv run ktrdr local-prod up
```

### Expected Output

After `local-prod init`:

```
Initialized local-prod at /Users/you/Documents/dev/ktrdr-prod
  Slot: 0 (standard ports)
  API: http://localhost:8000
  Grafana: http://localhost:3000
  Jaeger: http://localhost:16686
```

After `local-prod up`:

```
Starting local-prod...
  Fetching secrets from 1Password (ktrdr-local-prod)...
  Starting Docker Compose...
  Waiting for services...

  ✓ Database ready
  ✓ Backend healthy
  ✓ Workers registered (4)
  ✓ Observability stack ready
  ✓ MCP server ready

Local-prod is running!
  API: http://localhost:8000
  Grafana: http://localhost:3000
  Jaeger: http://localhost:16686
```

---

## Daily Usage

### Starting and Stopping

```bash
cd ~/Documents/dev/ktrdr-prod

# Start local-prod
ktrdr local-prod up

# Check status
ktrdr local-prod status

# View logs
ktrdr local-prod logs
ktrdr local-prod logs backend      # Specific service
ktrdr local-prod logs -f           # Follow logs

# Stop local-prod (keeps data)
ktrdr local-prod down

# Stop and remove all data
ktrdr local-prod down --volumes
```

### Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Backend API | http://localhost:8000 | Main API endpoint |
| Swagger UI | http://localhost:8000/api/v1/docs | API documentation |
| Grafana | http://localhost:3000 | Dashboards and metrics |
| Jaeger | http://localhost:16686 | Distributed tracing |
| Prometheus | http://localhost:9090 | Metrics collection |

### Health Checks

```bash
# API health
curl http://localhost:8000/api/v1/health

# Workers registered
curl http://localhost:8000/api/v1/workers | jq

# All services status
ktrdr local-prod status
```

---

## Host Services

Local-prod runs on slot 0 (standard ports) to enable connection to host services running natively on your Mac.

### IB Gateway Connection

The IB Host Service provides access to Interactive Brokers Gateway/TWS.

**Setup:**

1. Install and configure IB Gateway or TWS
2. Start the IB Host Service:

```bash
cd ~/Documents/dev/ktrdr-prod
./ib-host-service/start.sh
```

3. The service runs at `http://127.0.0.1:5001`
4. Docker containers connect via `host.docker.internal:5001`

**Verification:**

```bash
# Check IB host service health
curl http://localhost:5001/health

# From backend container
docker exec ktrdr-prod-backend-1 curl http://host.docker.internal:5001/health
```

### GPU Training Host Service

The Training Host Service provides GPU-accelerated training, bypassing Docker GPU limitations.

**Setup:**

1. Ensure PyTorch with CUDA/MPS support is installed on host
2. Start the training host service:

```bash
cd ~/Documents/dev/ktrdr-prod
./training-host-service/start.sh
```

3. The service runs at `http://127.0.0.1:5002`
4. Docker containers connect via `host.docker.internal:5002`

**Verification:**

```bash
# Check training host service health
curl http://localhost:5002/health

# Detailed GPU status
curl http://localhost:5002/health/detailed
```

### Host Service Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Your Mac                                                         │
│                                                                  │
│   ┌─────────────────┐     ┌─────────────────┐                   │
│   │ IB Host Service │     │ Training Host   │                   │
│   │ (port 5001)     │     │ Service (5002)  │                   │
│   └────────┬────────┘     └────────┬────────┘                   │
│            │                       │                             │
│            │   host.docker.internal                              │
│            │                       │                             │
│   ┌────────┴───────────────────────┴────────┐                   │
│   │              Docker Desktop              │                   │
│   │  ┌──────────┐  ┌──────────┐  ┌───────┐ │                   │
│   │  │ Backend  │  │ Workers  │  │  MCP  │ │                   │
│   │  │ (8000)   │  │ (5003-6) │  │       │ │                   │
│   │  └──────────┘  └──────────┘  └───────┘ │                   │
│   └─────────────────────────────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## MCP Server Usage

Local-prod includes an MCP (Model Context Protocol) server that enables Claude to interact with KTRDR.

### Claude Desktop Configuration

Add this to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "ktrdr-local": {
      "command": "docker",
      "args": ["exec", "-i", "ktrdr-prod-mcp-local-1", "/app/.venv/bin/python", "-m", "src.main"],
      "description": "KTRDR MCP Server - Local Development"
    }
  }
}
```

### Claude Code Configuration

For Claude Code, add to your MCP configuration:

```json
{
  "mcpServers": {
    "ktrdr-local": {
      "command": "docker",
      "args": ["exec", "-i", "ktrdr-prod-mcp-local-1", "/app/.venv/bin/python", "-m", "src.main"]
    }
  }
}
```

### Verifying MCP Connection

1. Ensure local-prod is running: `ktrdr local-prod status`
2. Check MCP container is healthy: `docker ps | grep mcp-local`
3. Restart Claude Desktop/Code
4. Test by asking Claude to use a KTRDR tool

### MCP Tools Available

The MCP server provides tools for:

- **Data Access**: Load OHLCV data, check available symbols
- **Training**: Start training jobs, monitor progress
- **Backtesting**: Run backtests, analyze results
- **Operations**: Track long-running operations

See [mcp/MCP_TOOLS.md](../../../mcp/MCP_TOOLS.md) for complete tool documentation.

---

## Troubleshooting

### Local-Prod Won't Start

**Symptom**: `ktrdr local-prod up` fails

**Solutions**:

1. Check Docker is running:
   ```bash
   docker info
   ```

2. Check for port conflicts:
   ```bash
   lsof -i :8000  # Backend
   lsof -i :5432  # Database
   lsof -i :3000  # Grafana
   ```

3. Remove stale containers:
   ```bash
   docker compose -f docker-compose.sandbox.yml down
   ktrdr local-prod up
   ```

### 1Password Secrets Not Found

**Symptom**: "Item not found: ktrdr-local-prod"

**Solutions**:

1. Verify 1Password CLI is authenticated:
   ```bash
   op account get
   ```

2. If not authenticated:
   ```bash
   op signin
   ```

3. Verify item exists:
   ```bash
   op item get ktrdr-local-prod --fields label=db_password
   ```

4. Use `--no-secrets` as fallback:
   ```bash
   ktrdr local-prod up --no-secrets
   ```

### Workers Not Registering

**Symptom**: `curl localhost:8000/api/v1/workers` shows 0 workers

**Solutions**:

1. Check worker container logs:
   ```bash
   docker logs ktrdr-prod-backtest-worker-1-1
   docker logs ktrdr-prod-training-worker-1-1
   ```

2. Ensure backend is healthy first:
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

3. Restart workers:
   ```bash
   docker compose -f docker-compose.sandbox.yml restart backtest-worker-1
   ```

### Host Services Can't Connect

**Symptom**: Backend can't reach IB or Training host services

**Solutions**:

1. Verify host services are running:
   ```bash
   curl http://localhost:5001/health  # IB
   curl http://localhost:5002/health  # Training
   ```

2. Test from inside container:
   ```bash
   docker exec ktrdr-prod-backend-1 curl http://host.docker.internal:5001/health
   ```

3. Check Docker Desktop settings allow `host.docker.internal`

### MCP Not Working with Claude

**Symptom**: Claude doesn't see KTRDR tools

**Solutions**:

1. Verify MCP container is running:
   ```bash
   docker ps | grep mcp-local
   ```

2. Check container name matches config:
   ```bash
   docker ps --format "{{.Names}}" | grep mcp
   ```

3. Test MCP manually:
   ```bash
   docker exec -i ktrdr-prod-mcp-local-1 /app/.venv/bin/python -m src.main
   ```
   (Should show "MCP server started" then wait for input)

4. Restart Claude Desktop/Code after config changes

### Database Connection Issues

**Symptom**: "Connection refused" to database

**Solutions**:

1. Check database container:
   ```bash
   docker logs ktrdr-prod-db-1
   ```

2. Wait for database to be ready:
   ```bash
   docker exec ktrdr-prod-db-1 pg_isready
   ```

3. Check database port:
   ```bash
   lsof -i :5432
   ```

---

## Destroying Local-Prod

To completely remove local-prod:

```bash
# From any directory (uses registry lookup)
ktrdr local-prod destroy --force
```

This will:
- Stop all containers
- Remove Docker volumes
- Unregister from the sandbox registry

**Note**: This keeps the clone directory intact. Delete it manually if desired.

---

## Comparison: Local-Prod vs Sandbox

| Aspect | Local-Prod | Sandbox |
|--------|------------|---------|
| Purpose | Real execution | E2E testing |
| Git setup | Clone | Worktree |
| Slot | 0 (standard ports) | 1-10 (offset ports) |
| Count | Singleton | Up to 10 |
| Host services | Yes (IB, GPU) | No |
| MCP server | Yes | No |
| Creation | `init` (manual clone first) | `create` (automated) |
| 1Password item | `ktrdr-local-prod` | `ktrdr-sandbox-dev` |
