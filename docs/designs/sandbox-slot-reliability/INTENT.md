# Sandbox Slot Reliability: Fix the Foundation

## What We Want to Fix

The sandbox slot system — the infrastructure that gives each worktree its own isolated Docker environment — has four failure modes that compound into a broken developer experience. Every time we spin up parallel worktrees, we hit at least one of these. The fixes are straightforward and well-understood.

---

## Why Now

We just merged Wave 1 of predictive features (4 parallel worktrees, all successful). Cleaning up those worktrees and creating Wave 2 hit every single failure mode:

1. Stale slot claims from Wave 1 — had to manually edit `instances.json`
2. Backend auth failures on slot reuse — PostgreSQL volumes retained old credentials
3. Missing `.env.sandbox` in new worktrees — Claude in M1 couldn't find its sandbox
4. Orphaned containers after failed starts — slot released but Docker state left behind

This blocks the 3 remaining waves of predictive features work. We can't keep manually patching infrastructure between every wave.

---

## The Four Failure Modes

### 1. Stale Slot Claims (No Orphan Detection)

**What happens:** A worktree is removed (via `kinfra done`, manual deletion, or failed cleanup), but the slot remains `claimed_by` a path that no longer exists. No command exists to release an individual slot.

**Root cause:** `sandbox_registry.py` stores `claimed_by` as a filesystem path but never validates the path still exists. The `slots` command displays claims without checking.

**Fix:** Add `kinfra sandbox release <slot>` command. Add automatic orphan detection in `sandbox slots` — if `claimed_by` path doesn't exist, mark it and offer to release.

### 2. DB Auth Failures on Slot Reuse

**What happens:** A slot is released and re-claimed by a new worktree. The backend container fails to start with `asyncpg.exceptions.InvalidPasswordError`. PostgreSQL's named volume (`postgres_data`) persists the old database with old credentials.

**Root cause:** `stop_slot_containers()` runs `docker compose down` (without `-v`), preserving volumes. When the slot is re-claimed, the new `.env.sandbox` may have different credentials. PostgreSQL only applies `POSTGRES_PASSWORD` on first init — if the volume already has data, it's ignored.

**Fix:** When a slot is claimed, run `docker compose down -v` first to ensure a clean volume state. This is safe because slots are meant to be ephemeral per-worktree environments, not persistent databases.

### 3. Missing .env.sandbox in Worktrees

**What happens:** `kinfra impl` creates the worktree and claims a slot, but the worktree directory doesn't have `.env.sandbox`. Commands in the worktree fail with "Not in a sandbox directory."

**Root cause:** `impl.py` doesn't generate `.env.sandbox` in the worktree. It relies on the slot infrastructure directory (`~/.ktrdr/sandboxes/slot-N/`) having one, but doesn't copy or symlink it to the worktree. The `sandbox up` command (which does generate env files) is a separate code path.

**Fix:** Generate `.env.sandbox` in the worktree directory during `kinfra impl`, using the same `generate_env_file()` function that `sandbox create` and `sandbox init` use.

### 4. Orphaned State After Failed Start

**What happens:** `kinfra impl` claims a slot, starts containers, but the backend health check fails. The slot is released, but containers and volumes are left running/dangling. The next `kinfra impl` that claims the same slot inherits the broken state.

**Root cause:** The exception handler in `impl.py` calls `registry.release_slot()` but doesn't stop containers or remove volumes. There's no cleanup-on-failure path.

**Fix:** In the exception handler, run `docker compose down -v` before releasing the slot. Also add cleanup to `start_slot_containers()` failure path.

---

## Additional Issue: Secret Injection Gap

**What happens:** `start_slot_containers()` in `slots.py` runs `docker compose up` without passing 1Password secrets to the environment. The `sandbox up` command in `sandbox.py` does inject secrets (via `fetch_sandbox_secrets()`), but `slots.py` doesn't.

**Root cause:** Two independent code paths start containers — `sandbox up` (full secret injection) and `start_slot_containers()` (no secret injection). The slot system was built later and didn't replicate the secret flow.

**Fix:** `start_slot_containers()` should use the same secret injection as `sandbox up`.

---

## Files to Change

| File | Change |
|------|--------|
| `ktrdr/cli/kinfra/sandbox.py` | Add `release` subcommand, add orphan detection to `slots` |
| `ktrdr/cli/kinfra/slots.py` | Add secret injection, add volume cleanup on claim, add cleanup on failure |
| `ktrdr/cli/kinfra/impl.py` | Generate `.env.sandbox` in worktree, clean up on failure |
| `ktrdr/cli/kinfra/done.py` | Ensure `down -v` on cleanup (not just `down`) |
| `ktrdr/cli/sandbox_registry.py` | Add `release_slot` CLI-accessible path, orphan detection helper |

---

## What This Is Not

This is not a redesign of the sandbox system. The architecture is sound — slot pools, per-worktree isolation, Docker Compose overrides. These are wiring bugs and missing error handling in the lifecycle management. Five focused fixes, each with a clear root cause and solution.
