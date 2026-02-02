# Handoff: M4 - Impl Workflow

## Task 4.0 Complete: Spike - Docker Override Validation

**Spike Results:** GO ✅

**Research Questions Answered:**
1. Override merging works: `docker compose -f base.yml -f override.yml config` correctly merges volumes
2. Volume mounts overlay base: override volumes are added, not replaced
3. Startup time: ~15s total (db/jaeger health checks account for most of this)
4. Syntax errors give clear messages: "service volume ... is missing a mount target"
5. Health check available immediately: `/api/v1/health` returns 200 once container is ready

**Gotchas:**
- Must pass `--env-file .env.sandbox` explicitly for port substitution to work
- Ports may already be in use by other sandboxes - implementation should check availability
- Template uses `image: ktrdr-backend:dev` - image must already exist (no build)

**Next Task Notes:**
- Task 4.1 creates `kinfra impl` command
- Use `docker compose --env-file .env.sandbox -f ... -f ... up -d` pattern
- Health check endpoint: `/api/v1/health` (not `/health`)
- Consider checking port availability before claiming slot

## Task 4.1 Complete: Create impl command (core)

**Implementation Notes:**
- `impl_app` is a Typer subcommand group registered in main.py
- `_parse_feature_milestone(value)` splits on "/" and returns (feature, milestone) tuple
- `_find_milestone_file(feature, milestone, base_path)` searches docs/designs/<feature>/implementation/ for M<N>_*.md
- Checks slot availability BEFORE creating worktree (GAP-6)
- On Docker failure: releases slot but keeps worktree (GAP-7)

**Import Pattern:**
- `from ktrdr.cli.kinfra.impl import impl_app` - the Typer app
- `from ktrdr.cli.kinfra.override import generate_override` - override generation
- `from ktrdr.cli.kinfra.slots import start_slot_containers` - container start

**Testing Notes:**
- Mock `ktrdr.cli.kinfra.slots.start_slot_containers` not `ktrdr.cli.kinfra.impl.start_slot_containers`
- Same for override module - mock at source not import point

**Next Task Notes:**
- Task 4.2 completes override.py with full template
- Task 4.3 completes slots.py with container management
- Both modules have basic implementations that work
