"""Pytest configuration for MCP unit tests"""

import sys
from pathlib import Path

# Add mcp/src to Python path for test imports
mcp_src_path = Path(__file__).parent.parent.parent.parent / "mcp" / "src"
sys.path.insert(0, str(mcp_src_path))
