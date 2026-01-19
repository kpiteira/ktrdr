# Configuration System: Validation Notes

**Date:** 2025-01-18
**Status:** Paused — blocked on M6/M7 (sandbox merge)
**Branch:** `doc/config-system-design`

---

## Validation Session Summary

Started `/kdesign-validate` on the config system design. Completed scenario enumeration and clarified several important design decisions before discovering a dependency on incomplete sandbox work.

---

## Key Clarifications Made

### 1. Secret Handling for Local Dev

**Original design assumption:** Secrets have no defaults, must be explicitly set.

**Clarified reality:** Local dev needs to "just work" with minimal setup.

**Agreed approach — precedence order (highest to lowest):**
1. **1Password injection** (best — secrets managed properly)
2. **`.env.local` file** (good — explicit local config, gitignored)
3. **Python defaults with BIG WARNINGS** (works but loud)

**Implication:** Decision 3 in DESIGN.md needs revision. Secrets DO have insecure defaults (e.g., `password: str = "localdev"`), but the system emits prominent warnings when those defaults are active.

### 2. Local Dev = Sandbox

**Clarification:** There is no separate "local dev without sandbox" flow. All local development uses the sandbox system.

**Flow:**
1. `ktrdr sandbox up` fetches secrets from 1Password (if authenticated)
2. Passes them to `docker compose` as environment variables
3. Container starts with secrets baked into environment
4. Hot reload restarts Python process (uvicorn `--reload`), NOT the container
5. Container env vars persist across hot reloads — no re-authentication needed

**Why no 1Password re-prompting on hot reload:**
- 1Password CLI caches session in `~/.op/sessions`
- Hot reload doesn't restart the container, just the process inside it
- Secrets only re-fetched on full `docker compose down` + `up` cycle

### 3. How Sandboxes Handle Secrets (Reference)

From `ktrdr/cli/sandbox.py` (lines 551-586):
```python
secrets_env = fetch_sandbox_secrets()  # 1Password fetch
compose_env = os.environ.copy()
compose_env.update(env)           # .env.sandbox (ports, metadata)
compose_env.update(secrets_env)   # 1Password secrets (overrides)
subprocess.run(cmd, check=True, env=compose_env)  # Pass to docker
```

**Key insight:** Secrets are injected at CLI invocation time, not at container runtime. The container inherits environment variables from the docker compose process.

---

## Dependency Identified: M6/M7 Must Complete First

### The Problem

The config system redesign needs to update docker-compose files with new env var names (e.g., `DB_PASSWORD` → `KTRDR_DB_PASSWORD`).

**Current state:**
- `docker-compose.yml` — symlink to `deploy/environments/local/docker-compose.yml`
- `docker-compose.sandbox.yml` — parameterized version for sandboxes

**If we do config redesign now:** Must update TWO compose files, and M6 merge becomes messier.

**If we do M6/M7 first:** One compose file to update, cleaner sequence.

### Recommendation

Complete M6 (Backward-Compatible Merge) and M7 (Documentation & Polish) before proceeding with config system implementation.

**References:**
- `docs/designs/Sandbox/implementation/M6_merge.md`
- `docs/designs/Sandbox/implementation/M7_documentation.md`

**Estimated scope:** M6/M7 is ~1-2 days of work (scripts + polish).

---

## Scenarios Enumerated (For Future Validation)

### Happy Paths
1. **Sandbox startup with 1Password**: `ktrdr sandbox up` fetches secrets, backend starts clean
2. **Sandbox startup without 1Password**: Defaults used, backend starts with BIG WARNINGS
3. **Hot reload**: Code changes, uvicorn restarts, secrets persist, no re-auth

### Error Paths
4. **Missing required setting (no default)**: If a setting has NO default and isn't set, fail fast
5. **Invalid type**: `KTRDR_API_PORT=abc` fails with clear error
6. **Multiple errors**: All validation errors collected and shown together

### Edge Cases
7. **Deprecated env var**: Old `DB_PASSWORD` works with deprecation warning
8. **Both old and new name set**: New name wins, warning emitted

### Integration Boundaries
9. **Worker validates subset**: Worker only validates worker-relevant settings
10. **Test isolation**: Tests override settings, cache cleared between tests

---

## Design Gaps to Address

### GAP-1: Document Secret Population Flow

The design doesn't explicitly document how secrets get from 1Password into the running container. Need to add:

- 1Password → `ktrdr sandbox up` → `compose_env` → container environment
- `.env.local` as optional manual override (gitignored)
- Defaults with warnings as fallback

### GAP-2: Revise Decision 3 (Required Settings)

Current text says secrets have "NO DEFAULT: must be set."

Revised approach:
- Secrets have insecure defaults (e.g., `"localdev"`)
- Validation module detects when defaults are in use
- Emits BIG WARNINGS (not failures) for local dev
- Consider `KTRDR_ENV=production` flag that DOES fail on defaults

### GAP-3: Define "BIG WARNING" Mechanism

Need to specify:
- What the warning looks like (format, visibility)
- When it's emitted (startup? every request?)
- How it's suppressed (production mode? explicit acknowledgment?)

Suggested approach:
```
========================================
WARNING: INSECURE DEFAULT CONFIGURATION
========================================
The following settings are using insecure defaults:
  - KTRDR_DB_PASSWORD: Using default "localdev"
  - KTRDR_AUTH_JWT_SECRET: Using default "local-dev-secret..."

This is fine for local development but MUST NOT be used in production.

To suppress this warning:
  - Set these values via 1Password (recommended)
  - Or create .env.local with secure values
  - Or set KTRDR_ACKNOWLEDGE_INSECURE_DEFAULTS=true
========================================
```

---

## Next Steps (When Resuming)

1. **Complete M6/M7** — Merge sandbox compose, polish edge cases
2. **Update DESIGN.md** — Incorporate clarifications from this session
3. **Resume validation** — Trace scenarios through architecture
4. **Complete gap analysis** — Resolve remaining gaps
5. **Define interface contracts** — Concrete API for settings module
6. **Propose milestones** — Vertical implementation slices

---

## Files in This Design

| File | Purpose |
|------|---------|
| `DESIGN.md` | Problem, goals, decisions, user scenarios |
| `ARCHITECTURE.md` | Components, data flow, migration plan |
| `VALIDATION_NOTES.md` | This file — validation session notes |
