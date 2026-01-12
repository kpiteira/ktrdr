# Sandbox Usage Guide

This guide covers common sandbox workflows and explains when to use each approach.

## Understanding Git Worktrees

When you run `ktrdr sandbox create`, it uses **git worktrees** under the hood.

### What is a Worktree?

A worktree is a linked copy of your repository that shares the same `.git` history but has its own working directory. Think of it as a lightweight clone.

```
~/Documents/dev/
├── ktrdr/                    # Main repo (has .git directory)
├── ktrdr--indicator-std/     # Worktree (linked to ktrdr's .git)
└── ktrdr--training-refactor/ # Another worktree (same .git)
```

### Why Worktrees?

| Feature | Clone | Worktree |
| ------- | ----- | -------- |
| Disk space | Full copy (~2GB+) | Just working files (~200MB) |
| Git history | Separate | Shared |
| Branch switching | Independent | Linked (can't checkout same branch twice) |
| Setup time | Slow (full clone) | Fast (just checkout) |

### Worktree Gotcha

You **cannot have the same branch checked out in two worktrees**. If `main` is checked out in `ktrdr/`, you can't also check it out in `ktrdr--indicator-std/`.

Solution: Each worktree works on a different branch. This is actually the intended workflow.

---

## Use Case 1: Single Feature with Multiple Milestones

**Scenario:** You're implementing indicator standardization across M1, M2, M3, etc. Each milestone has its own branch, but it's all one logical feature.

**Approach:** One sandbox, switch branches as you progress.

```bash
# Create sandbox once (starts on main or a feature branch)
uv run ktrdr sandbox create indicator-std
cd ../ktrdr--indicator-std
uv run ktrdr sandbox up

# Work on M1
git checkout -b feature/indicator-std-m1
# ... implement, commit, PR, merge to main ...

# Move to M2
git fetch origin
git checkout -b feature/indicator-std-m2 origin/main
# ... implement, commit, PR, merge to main ...

# Move to M3, etc.
```

**Key points:**
- Sandbox persists across branch switches
- No need to restart Docker unless compose file changes
- Design docs on `main` are available after each merge

---

## Use Case 2: Multiple Parallel Features

**Scenario:** You're working on indicator standardization AND a training refactor simultaneously. They're independent streams.

**Approach:** Multiple sandboxes, one per feature.

```bash
# From main repo
uv run ktrdr sandbox create indicator-std
uv run ktrdr sandbox create training-refactor

# Now you have:
# ~/Documents/dev/ktrdr--indicator-std/     (slot 1, port 8001)
# ~/Documents/dev/ktrdr--training-refactor/ (slot 2, port 8002)

# Start both
cd ../ktrdr--indicator-std && uv run ktrdr sandbox up
cd ../ktrdr--training-refactor && uv run ktrdr sandbox up

# List all running sandboxes
uv run ktrdr sandbox list
```

**Key points:**
- Each sandbox has isolated Docker containers on different ports
- Both can run simultaneously without conflicts
- Switch between them by changing directories

---

## Use Case 3: Using an Existing Clone

**Scenario:** You already have a clone (not created by `sandbox create`) and want to run it as a sandbox.

**Approach:** Use `ktrdr sandbox init` instead of `create`.

```bash
# You already have a clone somewhere
cd ~/my-projects/ktrdr-clone

# Initialize it as a sandbox
uv run ktrdr sandbox init

# Now it has .env.sandbox and allocated ports
uv run ktrdr sandbox up
```

**Key points:**
- Works with any KTRDR clone
- Validates it's a KTRDR repo (checks git remote)
- Allocates a port slot and creates `.env.sandbox`

---

## Use Case 4: Agent-Driven Development

**Scenario:** You want a Claude Code agent to work on a feature autonomously while you continue other work.

**Approach:** Create a dedicated sandbox for the agent.

```bash
# Create sandbox for agent work
uv run ktrdr sandbox create agent-feature-x --branch feature/agent-work

# Open that directory in a separate VS Code window
# Start a Claude Code session there
# The agent works in isolation with its own Docker stack
```

**Key points:**
- Agent has full access to a running KTRDR environment
- Your main environment is unaffected
- Agent can run tests, check APIs, etc. on its own ports

---

## Quick Reference: Which Approach?

| Situation | Command |
| --------- | ------- |
| New feature, will have milestones | `sandbox create <name>` → switch branches |
| Two features in parallel | `sandbox create <name1>` + `sandbox create <name2>` |
| Already have a clone | `sandbox init` in that directory |
| Need fresh start | `sandbox destroy` + `sandbox create` |

---

## Common Operations

### Check What's Running

```bash
# See all sandboxes and their status
uv run ktrdr sandbox list

# Detailed status of current sandbox
uv run ktrdr sandbox status
```

### Stop and Clean Up

```bash
# Stop containers (keep data)
uv run ktrdr sandbox down

# Stop and remove volumes (fresh DB next time)
uv run ktrdr sandbox down --volumes

# Completely remove sandbox (containers, volumes, worktree)
uv run ktrdr sandbox destroy
```

### Restart After Code Changes

Most code changes are picked up via hot reload. But if you change:
- `docker-compose.sandbox.yml`
- Dockerfile
- Dependencies (pyproject.toml)

Then restart:

```bash
uv run ktrdr sandbox down
uv run ktrdr sandbox up --build  # --build forces image rebuild
```

---

## Port Allocation

Each sandbox gets a "slot" (1-10) with dedicated ports:

| Slot | API | DB | Grafana | Jaeger | Workers |
| ---- | --- | --- | ------- | ------ | ------- |
| 0 (main) | 8000 | 5432 | 3000 | 16686 | 5003-5006 |
| 1 | 8001 | 5433 | 3001 | 16687 | 5010-5013 |
| 2 | 8002 | 5434 | 3002 | 16688 | 5020-5023 |
| 3 | 8003 | 5435 | 3003 | 16689 | 5030-5033 |

The CLI auto-detects which sandbox you're in and uses the correct ports.

---

## Secrets Management

Sandbox secrets are managed via 1Password for security and easy rotation.

### 1Password Setup (One-Time)

1. Install the 1Password CLI:
   ```bash
   brew install 1password-cli
   ```

2. Sign in:
   ```bash
   op signin
   ```

3. Create a 1Password item named `ktrdr-sandbox-dev` with these fields:

   | Field | Type | Description |
   |-------|------|-------------|
   | `db_password` | password | PostgreSQL password |
   | `jwt_secret` | password | JWT signing secret (min 32 chars) |
   | `anthropic_api_key` | password | Anthropic API key for agents |
   | `grafana_password` | password | Grafana admin password |

   All fields should be type "password" (CONCEALED in 1Password).

### How It Works

When you run `ktrdr sandbox up`:

1. Checks if 1Password CLI is authenticated
2. Fetches secrets from `ktrdr-sandbox-dev` item
3. Injects them as environment variables into Docker

```bash
# Normal usage - secrets from 1Password
uv run ktrdr sandbox up

# Output shows loaded secrets:
# Fetching secrets from 1Password...
#   ✓ Loaded: ANTHROPIC_API_KEY, DB_PASSWORD, GF_ADMIN_PASSWORD, JWT_SECRET
```

### Skipping Secrets (CI/Testing)

For CI environments or quick testing without 1Password:

```bash
uv run ktrdr sandbox up --no-secrets
```

This uses insecure defaults (acceptable for isolated testing only).

### Rotating Secrets

1. Update the values in 1Password
2. Restart the sandbox:
   ```bash
   uv run ktrdr sandbox down
   uv run ktrdr sandbox up
   ```

Note: Changing `db_password` requires resetting the database volume since PostgreSQL stores the password at initialization:

```bash
uv run ktrdr sandbox down --volumes
uv run ktrdr sandbox up
```
