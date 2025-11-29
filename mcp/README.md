# KTRDR MCP Server

Model Context Protocol (MCP) server for KTRDR trading strategy research and development. Provides AI agents with structured access to market data, neural network training, and trading strategy operations.

## 📚 Documentation

- **[MCP_TOOLS.md](MCP_TOOLS.md)**: Complete tool reference with comprehensive docstrings, examples, and workflows
- **Architecture**: Pure interface layer delegating to backend API (no local state)
- **Response Pattern**: Hybrid extraction for safety + convenience

## 🏗️ Deployment Architecture

The MCP server runs as a Docker container that makes HTTP calls to the backend API. It uses **stdio transport** (stdin/stdout), meaning Claude launches it as a subprocess.

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ Machine with Claude Code/Desktop                                            │
│                                                                             │
│   Claude ←──stdio──→ MCP Container ──http──→ Backend API                   │
│                      (subprocess)            (local or remote)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Multi-Instance Setup

| Container | Location | Target Backend | Use Case |
|-----------|----------|----------------|----------|
| `ktrdr-mcp-local` | Mac | `localhost:8000` | Local development |
| `ktrdr-mcp-preprod` | Mac | `preprod:8000` | Testing against pre-prod from Mac |
| `ktrdr-mcp` | Pre-prod LXC | `backend:8000` | AI agent automation on pre-prod |

## 🚀 Quick Start

### 1. Start Development Environment

```bash
# Start all services including MCP containers
docker compose -f docker-compose.dev.yml up -d

# Or build/start MCP containers only
./mcp/build_mcp.sh
```

### 2. Configure Claude

Copy the MCP server configuration to your Claude config file:

**Mac location**: `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "ktrdr-local": {
      "command": "docker",
      "args": ["exec", "-i", "ktrdr-mcp-local", "/app/.venv/bin/python", "-m", "src.main"],
      "description": "KTRDR MCP Server - Local Development Backend"
    },
    "ktrdr-preprod": {
      "command": "docker",
      "args": ["exec", "-i", "ktrdr-mcp-preprod", "/app/.venv/bin/python", "-m", "src.main"],
      "description": "KTRDR MCP Server - Pre-production Backend"
    }
  }
}
```

### 3. Restart Claude

Restart Claude Desktop or Claude Code to pick up the new configuration.

## 📦 Container Management

### Scripts

| Script | Purpose |
|--------|---------|
| `./build_mcp.sh` | Build and start MCP containers |
| `./restart_mcp.sh [local\|preprod\|all]` | Restart MCP container(s) |
| `./stop_mcp.sh [local\|preprod\|all]` | Stop MCP container(s) |

### Direct Docker Commands

```bash
# Restart specific MCP container
docker compose -f docker-compose.dev.yml restart mcp-local
docker compose -f docker-compose.dev.yml restart mcp-preprod

# View MCP logs
docker logs ktrdr-mcp-local
docker logs ktrdr-mcp-preprod

# Check MCP container status
docker ps --filter "name=ktrdr-mcp"
```

## 🖥️ Pre-prod Deployment

On the pre-prod LXC (core node), the MCP container is part of `docker-compose.core.yml`:

```yaml
mcp:
  image: ghcr.io/kpiteira/ktrdr-backend:${IMAGE_TAG:-latest}
  container_name: ktrdr-mcp
  environment:
    KTRDR_API_URL: http://backend:8000/api/v1
  # ... see docker-compose.core.yml for full config
```

**Pre-prod Claude config** (`claude_mcp_config.preprod.json`):

```json
{
  "mcpServers": {
    "ktrdr": {
      "command": "docker",
      "args": ["exec", "-i", "ktrdr-mcp", "/app/.venv/bin/python", "-m", "src.main"]
    }
  }
}
```

## 🔧 Configuration

The MCP server is configured via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `KTRDR_API_URL` | Backend API URL | `http://backend:8000/api/v1` |
| `OTLP_ENDPOINT` | OpenTelemetry collector | `http://jaeger:4317` |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

## 🧪 Testing MCP Changes

1. Make changes to `mcp/src/` code
2. Restart the relevant container:

   ```bash
   ./mcp/restart_mcp.sh local
   ```

3. In Claude, test the MCP tools

4. Check logs:

   ```bash
   docker logs ktrdr-mcp-local --tail 50
   ```

## 🔍 Signature Validation

The project includes automated validation to ensure MCP tool signatures match backend API contracts.

### Running Validation

```bash
# Ensure backend is running
docker compose -f docker-compose.dev.yml up -d backend

# Run validation
make validate-mcp

# Or directly
uv run python scripts/validate_mcp_signatures.py
```

### Configuration

Tool-to-endpoint mapping is defined in [`endpoint_mapping.json`](endpoint_mapping.json).

## 📝 MCP Tools Reference

See **[MCP_TOOLS.md](MCP_TOOLS.md)** for complete tool documentation including:

- Parameter descriptions and valid values
- Return structure documentation
- Working code examples
- Related tools for discovery
- Behavioral notes and best practices

### Example Usage

```python
# Start training (returns operation_id)
result = await start_training(
    symbols=["AAPL", "MSFT"],
    timeframes=["1h", "4h"],
    strategy_name="neuro_mean_reversion",
    start_date="2024-01-01",
    end_date="2024-03-01"
)

# Monitor progress
status = await get_operation_status(result["data"]["operation_id"])
print(f"Progress: {status['data']['progress_percentage']}%")
```
