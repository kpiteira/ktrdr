# MCP Development Guidelines

## 🚨 CRITICAL: NEVER TOUCH OTHER CONTAINERS

**WHEN WORKING ON MCP, NEVER REBUILD BACKEND OR WORKERS!**

### ALLOWED Commands

```bash
./mcp/restart_mcp.sh              # Restart all MCP containers
./mcp/restart_mcp.sh local        # Restart only mcp-local
./mcp/restart_mcp.sh preprod      # Restart only mcp-preprod
./mcp/build_mcp.sh                # Build and start MCP containers
./mcp/stop_mcp.sh                 # Stop all MCP containers
docker compose restart mcp-local
docker compose restart mcp-preprod
```

### FORBIDDEN Commands

```bash
docker compose up -d              # NO! Affects all containers
docker compose build              # NO! Rebuilds everything
docker compose restart            # NO! Affects all containers
```

## 🏗️ MCP ARCHITECTURE

MCP (Model Context Protocol) server enables Claude to:

- Access market data (read-only)
- Run strategy research
- Train and test models
- Execute backtests

**Safety First**: No access to live trading or production systems

## 📦 Multi-Instance Setup

| Container | Target Backend | Purpose |
|-----------|----------------|---------|
| `ktrdr-mcp-local` | `http://backend:8000` | Local dev |
| `ktrdr-mcp-preprod` | `http://preprod:8000` | Pre-prod from Mac |
| `ktrdr-mcp` (pre-prod) | `http://backend:8000` | AI automation |

## 📁 MCP STRUCTURE

```text
mcp/
├── src/              # MCP server implementation
│   ├── main.py       # Entry point
│   ├── server.py     # Tool definitions
│   ├── config.py     # Configuration
│   └── clients/      # Backend API clients
├── claude_mcp_config.json         # Mac Claude config template
├── claude_mcp_config.preprod.json # Pre-prod Claude config template
└── scripts           # Build and management scripts
```

## 🔧 DEVELOPMENT WORKFLOW

1. Make changes to MCP code in `mcp/src/`
2. Run `./mcp/restart_mcp.sh local` to restart
3. Test with Claude Desktop/Code
4. Check logs: `docker logs ktrdr-mcp-local`

## 🚫 MCP ANTI-PATTERNS

- Giving access to order execution (research only)
- Modifying production data (read-only access)
- Uncontrolled resource usage (set limits)

## 🧪 TESTING MCP

- Test tools in isolation first
- Verify permissions are restricted
- Check resource consumption
- Monitor for security issues
