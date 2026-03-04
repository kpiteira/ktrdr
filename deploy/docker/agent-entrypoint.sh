#!/bin/bash
# Agent container entrypoint
# Ensures .claude.json exists (Claude CLI config file, separate from .claude/ dir)

if [ ! -f "$HOME/.claude.json" ]; then
    # Check for backup in the auth volume
    backup=$(ls -t "$HOME/.claude/backups/.claude.json.backup."* 2>/dev/null | head -1)
    if [ -n "$backup" ]; then
        cp "$backup" "$HOME/.claude.json"
    else
        # Create minimal config — Claude CLI works without it but warns
        echo '{}' > "$HOME/.claude.json"
    fi
fi

exec "$@"
