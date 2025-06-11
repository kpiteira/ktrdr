# MCP Container Management

This directory contains scripts for safely managing the MCP container without affecting the backend or frontend.

## 🚨 CRITICAL RULE 🚨

**NEVER touch the backend or frontend containers when working on MCP features!**

## Safe MCP Scripts

Use these scripts to manage ONLY the MCP container:

### `./restart_mcp.sh`
Restarts only the MCP container. Use this when you've made configuration changes.

### `./build_mcp.sh`  
Rebuilds and starts only the MCP container. Use this when you've made code changes.

### `./stop_mcp.sh`
Stops only the MCP container. Use this for maintenance or debugging.

## Direct Docker Commands

If you prefer direct docker-compose commands, use these SAFE patterns:

```bash
# ✅ SAFE - Only affects MCP
docker-compose -f docker/docker-compose.yml restart mcp
docker-compose -f docker/docker-compose.yml build mcp
docker-compose -f docker/docker-compose.yml up -d mcp
docker-compose -f docker/docker-compose.yml stop mcp

# ❌ DANGEROUS - Affects ALL containers  
docker-compose --profile research up -d
docker-compose build
docker-compose restart
```

## Why This Matters

The backend and frontend containers are:
- Complex to rebuild
- Sensitive to environment changes  
- Not related to MCP development
- Working correctly and should not be disturbed

The MCP container is:
- Independent and isolated
- Safe to rebuild frequently
- What you're actually working on

## Testing MCP Changes

After making changes:
1. Run `./build_mcp.sh` to rebuild only MCP
2. Restart Claude Desktop to reconnect
3. Test your MCP tools

Never restart other containers - they don't need it for MCP changes!