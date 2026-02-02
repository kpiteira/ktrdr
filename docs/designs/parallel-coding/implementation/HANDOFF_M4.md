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

## Task 4.2 Complete: Create override file generator

**Implementation Notes:**
- Implementation was already complete from Task 4.1
- Added 11 unit tests covering all acceptance criteria
- Template uses `${KTRDR_*_DIR}` env vars for shared data directories

**Testing Notes:**
- Use `yaml.safe_load()` to verify valid YAML
- `${VAR}` syntax is valid YAML but won't be substituted during test

**Next Task Notes:**
- Task 4.3 tests slots.py container management
- Similar pattern - implementation exists, add tests

## Task 4.3 Complete: Create slot container management

**Implementation Notes:**
- Implementation was already complete from Task 4.1
- Added 11 unit tests covering all acceptance criteria
- `start_slot_containers()` includes `--env-file .env.sandbox` and both compose files
- `_wait_for_health()` polls `/api/v1/health` with 2s interval

**Testing Notes:**
- Mock `httpx.get` directly (not `ktrdr.cli.kinfra.slots.httpx`) since httpx is imported inside function
- Mock `time.time` for timeout tests - return sequence simulating time progression
- Health check tests verify retry behavior on connection errors and non-200 status

**Next Task Notes:**
- Task 4.4 updates worktrees command to show slot info for impl worktrees
- Need to add `get_slot_for_worktree()` method to registry or query slots by path

## Task 4.4 Complete: Update worktrees command for impl slots

**Implementation Notes:**
- Added `get_slot_for_worktree(worktree_path)` method to Registry class
- Updated worktrees.py to load registry and query slot for each impl worktree
- Display format: `slot N (status, :port)` e.g., `slot 2 (running, :8002)`
- Shows "no slot" for impl worktrees without claimed slot

**Testing Notes:**
- Mock `load_registry` at `ktrdr.cli.kinfra.worktrees.load_registry`
- Mock registry's `get_slot_for_worktree` to return MagicMock with slot attributes
- Tests verify slot number, port, and status all appear in output

**Next Task Notes:**
- Task 4.5 is E2E validation - run full `kinfra impl` workflow
- Need provisioned slots and test milestone file
