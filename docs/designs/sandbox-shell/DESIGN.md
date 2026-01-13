# Sandbox Shell Command: Design

## Problem Statement

When working in a sandbox, developers need to quickly access a shell inside running containers for debugging, running ad-hoc commands, or inspecting state. Currently, this requires manually typing `docker compose -f docker-compose.sandbox.yml exec backend bash` with the correct environment variables set.

## Goals

1. **One command to shell** — `ktrdr sandbox shell` opens an interactive shell instantly
2. **Service selection** — Optionally specify which service to shell into
3. **Consistent with existing patterns** — Uses same sandbox detection as other commands

## Non-Goals (Out of Scope)

- Running non-interactive commands (use `docker compose exec` directly)
- Multiple simultaneous shells
- Shell customization or environment injection

## User Experience

### Default Usage (Backend)

```bash
cd ~/dev/ktrdr--my-feature
ktrdr sandbox shell

# Output:
# Connecting to backend...
# root@abc123:/app#
```

### Specific Service

```bash
ktrdr sandbox shell db

# Output:
# Connecting to db...
# root@def456:/#
```

### Available Services

Common services: `backend`, `db`, `grafana`, `jaeger`, `worker-backtest-1`, `worker-training-1`

### Error Cases

```bash
# Not in a sandbox directory
ktrdr sandbox shell
# Error: Not in a sandbox directory (.env.sandbox not found)

# Service not running
ktrdr sandbox shell backend
# Error: Service 'backend' is not running
# Run 'ktrdr sandbox up' to start the stack
```

## Key Decisions

### Decision 1: Default to Backend

**Choice:** When no service is specified, shell into `backend`.

**Rationale:** Backend is the most common debugging target — checking logs, running Python commands, inspecting the application state.

### Decision 2: Use Bash with Fallback

**Choice:** Try `bash` first, fall back to `sh` if unavailable.

**Rationale:** Bash provides a better experience (history, tab completion), but some minimal containers only have `sh`.

### Decision 3: Always Interactive

**Choice:** Always run with `-it` flags (interactive + TTY).

**Rationale:** A shell command without interactivity is pointless. For non-interactive commands, users can use `docker compose exec` directly.

## Open Questions

None — this is a straightforward feature.
