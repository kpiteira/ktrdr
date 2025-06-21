# MCP Development Guidelines

## 🚨 CRITICAL: NEVER TOUCH OTHER CONTAINERS

**WHEN WORKING ON MCP, NEVER REBUILD BACKEND OR FRONTEND!**

### ✅ ALLOWED Commands:
```bash
./mcp/restart_mcp.sh              # Restart ONLY MCP
./mcp/build_mcp.sh                 # Build ONLY MCP
./mcp/stop_mcp.sh                  # Stop ONLY MCP
docker-compose -f docker/docker-compose.yml restart --no-deps mcp
```

### ❌ FORBIDDEN Commands:
```bash
docker-compose --profile research up -d    # NO! Rebuilds everything
docker-compose build                       # NO! Rebuilds everything
docker-compose restart                     # NO! Affects all containers
```

## 🏗️ MCP ARCHITECTURE

MCP (Model Context Protocol) server enables Claude to:
- Access market data (read-only)
- Run strategy research
- Train and test models
- Execute backtests

**Safety First**: No access to live trading or production systems

## 📁 MCP STRUCTURE

```
mcp/
├── server/          # MCP server implementation
├── tools/           # Available tools for Claude
├── config/          # MCP configuration
└── scripts/         # Build and deployment scripts
```

## 🔧 DEVELOPMENT WORKFLOW

1. Make changes to MCP code
2. Run `./mcp/build_mcp.sh` (builds ONLY MCP)
3. Test with Claude Desktop
4. Check logs: `docker logs mcp`

## 🚫 MCP ANTI-PATTERNS

❌ Giving access to order execution
✅ Research and analysis only

❌ Modifying production data
✅ Read-only access to market data

❌ Uncontrolled resource usage
✅ Set limits on compute and memory

## 🧪 TESTING MCP

- Test tools in isolation first
- Verify permissions are restricted
- Check resource consumption
- Monitor for security issues