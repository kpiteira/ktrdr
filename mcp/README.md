# KTRDR MCP Server

Model Context Protocol (MCP) server for KTRDR trading strategy research and development. Provides AI agents with structured access to market data, neural network training, and trading strategy operations.

## 📚 Documentation

- **[MCP_TOOLS.md](MCP_TOOLS.md)**: Complete tool reference with comprehensive docstrings, examples, and workflows
- **Architecture**: Pure interface layer delegating to backend API (no local state)
- **Response Pattern**: Hybrid extraction for safety + convenience

## 🚀 Quick Start

All MCP tools have comprehensive docstrings with:
- Clear parameter descriptions and valid values
- Complete return structure documentation
- Working code examples
- Related tools for discovery ("See Also")
- Behavioral notes and best practices

Example - Starting a training operation:
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

## 🏗️ Architecture

### Response Handling Pattern

The MCP clients use a **hybrid response extraction pattern**:

1. **Critical operations** → `_extract_or_raise()`: Validates responses for operations that must succeed
2. **Discovery operations** → `_extract_list/dict()`: Graceful defaults for browsing/listing
3. **Status operations** → Full response: Maximum information for monitoring

See [MCP_TOOLS.md](MCP_TOOLS.md#response-handling-architecture) for details.

## 📦 Container Management

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