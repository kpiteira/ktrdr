---
name: mcp-server
description: Use when working on the MCP server, MCP tools, MCP client integrations, or adding new MCP tools for Claude Desktop.
---

# MCP Server

**When this skill is loaded, announce it to the user by outputting:**
`🛠️✅ SKILL mcp-server loaded!`

Load this skill when working on:

- MCP server setup and configuration
- MCP tool registration and implementation
- API client integrations for MCP tools
- Adding new MCP tools

---

## Key Files

| File | Purpose |
|------|---------|
| `mcp/src/server.py` | FastMCP server instance + tool registration |
| `mcp/src/main.py` | Entry point |
| `mcp/src/api_client.py` | Backend API connection pool (httpx async) |
| `mcp/src/tools/strategy_tools.py` | Strategy validation tools |

### Client Layer

| File | Purpose |
|------|---------|
| `mcp/src/clients/base.py` | BaseAPIClient (shared async HTTP) |
| `mcp/src/clients/data_client.py` | Market data queries |
| `mcp/src/clients/backtesting_client.py` | Backtest execution |
| `mcp/src/clients/training_client.py` | Model training operations |
| `mcp/src/clients/strategies_client.py` | Strategy management |
| `mcp/src/clients/operations_client.py` | Operation tracking |
| `mcp/src/clients/indicators_client.py` | Technical indicator queries |
| `mcp/src/clients/system_client.py` | System health/metadata |

---

## Architecture

```
Claude Desktop / MCP Client
    │
    ▼ MCP Protocol (stdio)
FastMCP Server (mcp/src/server.py)
    │
    ├── @mcp.tool() decorated functions
    │
    ▼ Domain-specific async clients
Backend API (http://localhost:8000)
```

**Framework:** FastMCP (Python MCP SDK)

**Safety:** Research-only tools. No live trading or order execution.

---

## Available Tools

```python
@mcp.tool()
async def hello_ktrdr() -> str:
    """Health check / connectivity test."""

@mcp.tool()
async def check_backend_health() -> dict:
    """Backend connectivity + service status."""

@mcp.tool()
async def get_available_symbols() -> list[str]:
    """List configured trading symbols."""

@mcp.tool()
async def validate_strategy(path: str) -> dict:
    """Validate strategy YAML (v2/v3 format)."""
```

---

## Adding a New Tool

1. Create or find the appropriate client in `mcp/src/clients/`
2. Add tool function in `mcp/src/server.py` or a tools file:
   ```python
   @mcp.tool()
   @trace_mcp_tool()
   async def my_tool(param: str) -> dict:
       """Tool description shown to Claude."""
       client = get_api_client()
       return await client.my_endpoint(param)
   ```
3. The tool auto-registers via the `@mcp.tool()` decorator

---

## Configuration

Supports multiple backend targets via environment:
- **Local dev:** `http://localhost:8000`
- **Preprod:** Configurable via environment

Client pooling managed by `get_api_client()` factory using httpx async sessions.
