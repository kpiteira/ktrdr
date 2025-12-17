#!/bin/bash
# KTRDR Sandbox Entrypoint
# Validates environment and keeps container running for exec commands

set -e

echo "=== KTRDR Sandbox Starting ==="
echo ""

# Check for ANTHROPIC_API_KEY
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "WARNING: ANTHROPIC_API_KEY is not set. Claude Code will not work without it."
    echo "         Set it via: docker run -e ANTHROPIC_API_KEY=your-key ..."
    echo ""
fi

# Check if workspace has a git repository
if [ ! -d "/workspace/.git" ]; then
    echo "WARNING: /workspace is empty or has no git repository."
    echo "         Run sandbox-init.sh to clone the repository."
    echo ""
fi

# Report status
echo "Environment:"
echo "  - Python: $(python3 --version 2>&1)"
echo "  - Node: $(node --version 2>&1)"
echo "  - uv: $(uv --version 2>&1)"
echo "  - Claude: $(which claude 2>/dev/null || echo 'not found')"
echo "  - Docker CLI: $(docker --version 2>&1 | head -1)"
echo ""

if [ -d "/workspace/.git" ]; then
    echo "Workspace: /workspace (git repo present)"
    cd /workspace
    echo "  - Branch: $(git branch --show-current 2>/dev/null || echo 'unknown')"
    echo "  - Status: $(git status --porcelain 2>/dev/null | wc -l | xargs) uncommitted changes"
else
    echo "Workspace: /workspace (empty)"
fi

echo ""
echo "=== Sandbox Ready ==="
echo ""

# If arguments were passed, run them instead of sleeping
# This allows: docker run sandbox python3 --version
if [ $# -gt 0 ]; then
    exec "$@"
fi

# Default: keep container running for exec commands
exec sleep infinity
