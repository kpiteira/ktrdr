# KTRDR Scripts

Utility scripts for the KTRDR trading system.

## MCP Signature Validation

Automatically validates MCP tool signatures against backend API contracts.

### Usage

**Local validation**:
```bash
# Start backend
./start_ktrdr.sh

# Run validation (via Makefile - recommended)
make validate-mcp

# Or run script directly
uv run python scripts/validate_mcp_signatures.py

# Strict mode (warnings as errors)
uv run python scripts/validate_mcp_signatures.py --strict
```

**Pre-commit hook** (automatic):
- Runs when `mcp/src/server.py` modified
- Requires backend running
- Blocks commit if validation fails

**CI validation** (automatic):
- Runs on PRs affecting MCP or backend
- Blocks merge if validation fails

### Troubleshooting

**"Backend not reachable"**:
- Ensure backend running: `./start_ktrdr.sh`
- Check port 8000: `lsof -i:8000`

**Validation failures**:
- Read error report carefully
- Check parameter names and types
- Consult `mcp/endpoint_mapping.json`
