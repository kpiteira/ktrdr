# Parallel Coding Workflow: Design

## Problem Statement

As autonomous milestone work scales up (2-5+ concurrent streams), the current setup has friction points:

1. **Terminal visibility:** No easy way to see what each Claude Code session is doing, which needs attention, or which just finished
2. **Sandbox coupling:** Sandboxes are permanently tied to directories, making them expensive to create and inflexible
3. **Resource constraints:** Each sandbox uses ~2.5GB memory, limiting parallel work to 2-3 streams
4. **Worktree friction:** Spec work and implementation work have different needs but share the same heavyweight setup
5. **CLI confusion:** Infrastructure tooling (sandbox, deploy) mixed with product usage (train, backtest) in `ktrdr` CLI

The core problem: **The current setup doesn't scale with the user's ability to run parallel autonomous work.**

---

## Goals

1. **Session visibility:** At a glance, see what each terminal is doing and which needs attention
2. **Sandbox efficiency:** Decouple sandbox infrastructure from code, allowing slots to be shared across worktrees
3. **Resource optimization:** Run 3-5 parallel implementation streams without exhausting memory
4. **Clean worktree workflow:** Simple worktrees for spec work, sandbox-backed worktrees for implementation
5. **CLI separation:** Infrastructure tooling in dedicated `kinfra` CLI, product usage stays in `ktrdr`

---

## Non-Goals (Out of Scope)

- Building a custom session manager (we'll source Agent Deck)
- Cross-session memory/context (captured in MEMORY_WISHLIST.md for future work)
- Status line customization (Agent Deck solves the visibility problem)
- Sandbox performance optimization beyond worker count reduction

---

## User Experience

### Scenario 1: Starting Spec Work

```bash
# Create a spec worktree
kinfra spec genome-system

# Creates: docs/designs/genome-system/ (if not exists)
# Creates: ../ktrdr-spec-genome-system (git worktree)
# No sandbox, no docker, just code
```

User works on design docs, YAML files, etc. No E2E testing needed.

### Scenario 2: Starting Implementation Work

```bash
# Create an implementation worktree with sandbox (milestone-based)
kinfra impl genome/M1

# Auto-detects: docs/designs/genome/implementation/M1_*.md
# Checks slot availability FIRST (fails fast if none available)
# Claims an available sandbox slot
# Creates: ../ktrdr-impl-genome-M1 (git worktree)
# Starts sandbox infrastructure (~1 min, prompts for secrets)

# Request specific profile if needed:
kinfra impl genome/M1 --profile standard
```

User has full E2E testing capability with hot reload.

### Scenario 3: Running kmilestone

```bash
# In an implementation worktree
/kmilestone @docs/designs/genome-system/implementation/M1_foundation.md

# Milestone execution proceeds normally
# E2E tests run against the claimed sandbox
# After PR merge, run `kinfra done` to clean up
```

### Scenario 4: Checking Session Status

Agent Deck's tmux status bar shows:

```
⚡ [1] genome-M1 (waiting) [2] config-M3 (running) [3] spec-work (idle)
```

User presses `Ctrl+b 1` to jump to the waiting session.

### Scenario 5: Completing a Milestone

```bash
# After PR merge (via hook or manual)
kinfra done genome-M1
# Aliases: kinfra finish genome-M1, kinfra complete genome-M1

# Checks for uncommitted/unpushed changes (aborts if dirty)
# Stops sandbox containers
# Releases sandbox slot
# Removes worktree

# Force cleanup even with uncommitted changes:
kinfra done genome-M1 --force
```

### Scenario 6: Managing Infrastructure

```bash
# List what's active
kinfra worktrees

# Manual sandbox control
kinfra sandbox slots          # List all slots with status
kinfra sandbox up             # Start sandbox in current worktree
kinfra sandbox down           # Stop sandbox

# Local-prod (singleton, for real IB/GPU testing)
kinfra local-prod up
kinfra local-prod down

# Deployments
kinfra deploy homelab
kinfra deploy canary
```

---

## Key Decisions

### Decision 1: Source Agent Deck for Session Management

**Choice:** Use Agent Deck rather than building custom tooling

**Alternatives considered:**
- Claude Squad (more popular, but less state detection)
- Custom Zellij integration (requires building what exists)
- Warp terminal (replaces entire terminal)

**Rationale:** Agent Deck has the exact features needed:
- 4-state detection (running/waiting/idle/error)
- tmux status bar notifications
- Session jumping with `Ctrl+b 1-6`
- Claude Code integration (status, fork, resume)

### Decision 2: Decouple Sandbox Slots from Code Directories

**Choice:** Sandbox slots are infrastructure-only; worktrees claim slots temporarily

**Alternatives considered:**
- Keep current model (sandbox = clone with infrastructure)
- Lighter sandboxes (fewer services)

**Rationale:**
- Allows many worktrees with few sandbox slots
- Infrastructure is expensive to create; code is cheap
- Matches actual usage: spec work doesn't need sandboxes

### Decision 3: Variable Worker Profiles

**Choice:** Different slots have different worker counts based on typical usage

| Profile | Workers | Memory | Use Case |
|---------|---------|--------|----------|
| light | 1 backtest, 1 training | ~1.5GB | Normal milestone work |
| standard | 2 backtest, 2 training | ~2.5GB | Parallel operation testing |
| heavy | 4 backtest, 4 training | ~4GB | Stress testing (rare) |

**Slot allocation:**
- Slots 1-4: light profile (most common use)
- Slot 5: standard profile (parallel operation testing)
- Slot 6: heavy profile (stress testing, rare)

**Alternatives considered:**
- All slots identical (wastes resources or limits flexibility)
- On-demand worker scaling (complex)

**Rationale:**
- Most milestone work needs only 1 worker per type
- Parallel worker testing is occasional, not constant
- Heavy profile available when explicitly needed

### Decision 4: Pre-Create Sandbox Slots (Down When Unclaimed)

**Choice:** Pre-create 3-4 sandbox slots; keep them stopped when unclaimed

**Alternatives considered:**
- Keep slots running always (wastes memory)
- On-demand creation (slow when you need it)
- Single shared sandbox (conflicts between streams)

**Rationale:**
- Pre-created slots have config ready, DB volumes persist
- Stopped slots consume no memory
- ~1 min startup is acceptable (requires secrets intervention)
- Only claimed slots run, so 3-4 slots don't mean 3-4x memory

### Decision 5: New `kinfra` CLI for Infrastructure Tooling

**Choice:** Create separate `kinfra` CLI for infrastructure/development tooling

**What moves to kinfra:**
- `ktrdr sandbox *` → `kinfra sandbox *`
- `ktrdr local-prod *` → `kinfra local-prod *`
- `ktrdr deploy *` → `kinfra deploy *`
- New: `kinfra spec`, `kinfra impl`, `kinfra done`, `kinfra worktrees`

**What stays in ktrdr:**
- Product usage: `train`, `backtest`, `research`, `status`, `ops`, etc.
- Data management: `data`, `checkpoints`
- Strategy tools: `validate`, `migrate`

**Alternatives considered:**
- Keep everything in `ktrdr` (pollutes product CLI with dev tooling)
- Full abstraction with config layer (over-engineering for now)

**Rationale:**
- Clear separation: `ktrdr` for using the product, `kinfra` for building it
- Lift-and-shift existing code (minimal refactoring)
- Stays ktrdr-specific for now (no config layer)
- Can extract to separate repo later if useful for other projects

---

### Decision 6: Remove docker-compose.yml Symlink

**Choice:** Delete the `docker-compose.yml` symlink and require explicit compose file specification

**Problem:** The repo has a symlink `docker-compose.yml -> deploy/environments/local/docker-compose.yml` which uses port 8000. Running `docker compose up` without `-f` uses this symlink even in sandbox folders, causing E2E tests to hit the wrong backend.

**Alternatives considered:**
- Make symlink point to sandbox compose (breaks local-prod assumptions)
- Environment-detecting compose file (complex, fragile)

**Rationale:**
- Explicit is better than implicit
- `kinfra sandbox up` and `kinfra local-prod up` are the correct commands
- Worktrees in new architecture have no compose files anyway

---

### Decision 7: Explicit Release After PR Merge

**Choice:** User runs `kinfra done` after PR merge to release sandbox and clean up worktree

**Why not auto-release:**
- Git worktrees don't auto-delete when branch merges
- Detecting PR merge requires webhook infrastructure (complexity)
- Explicit cleanup is simple and reliable

**Workflow:**
1. PR merged via `gh pr merge --squash --delete-branch`
2. User (or Claude) runs `kinfra done <name>`
3. Sandbox stops, slot releases, worktree removed

**Future option:** Could add post-merge hook that triggers `kinfra done` automatically, but explicit is fine for now.

---

## Open Questions

1. **Agent Deck stability:** Is v0.9.2 stable enough for daily use? (Will validate during trial)
2. **Hook mechanism:** Git post-merge hook vs. GitHub webhook for auto-release? (Prefer local hook for simplicity)

---

## Success Criteria

1. Can run 3+ parallel implementation streams without manual juggling
2. Can see at a glance which sessions need attention (Agent Deck)
3. Can create spec worktrees in seconds (`kinfra spec`, no docker)
4. Can create impl worktrees with sandbox in ~1 min (`kinfra impl`)
5. Easy cleanup after PR merge (`kinfra done`)
6. Unclaimed slots consume zero memory (containers stopped)
7. Light profile slots use ~1.5GB (down from ~2.5GB)
8. Clear CLI separation: `ktrdr` for product, `kinfra` for infra

---

## Migration Plan (Prioritized)

### Phase 1: Quick Wins (Immediate Value)

| Step | What | Why |
|------|------|-----|
| 1.1 | Remove docker-compose.yml symlink | Fixes current E2E test bugs |
| 1.2 | Add `docker-compose.yml` to .gitignore | Prevents recreation |
| 1.3 | Install Agent Deck | Immediate visibility into sessions |
| 1.4 | Configure Agent Deck | tmux status bar, notifications |

### Phase 2: CLI Separation (Clean Foundation)

| Step | What | Why |
|------|------|-----|
| 2.1 | Create `kinfra` CLI package | New entry point |
| 2.2 | Move sandbox commands to kinfra | Clean separation |
| 2.3 | Move local-prod commands to kinfra | Clean separation |
| 2.4 | Move deploy commands to kinfra | Clean separation |
| 2.5 | Add deprecation warnings in ktrdr | Guide users to kinfra |
| 2.6 | Update CLAUDE.md and skills | Use kinfra, not raw docker compose |

### Phase 3: Spec Workflow (Quick Win)

| Step | What | Why |
|------|------|-----|
| 3.1 | Implement `kinfra spec` | Create spec worktrees easily |
| 3.2 | Implement `kinfra worktrees` | List active worktrees |

### Phase 4: Impl Workflow (Full Value)

| Step | What | Why |
|------|------|-----|
| 4.1 | Create sandbox slot pool infrastructure | `~/.ktrdr/sandboxes/slot-N/` |
| 4.2 | Implement slot registry v2 | Track claims, profiles |
| 4.3 | Create compose files per profile | light, standard, heavy |
| 4.4 | Implement `kinfra impl` | Create worktree + claim slot |
| 4.5 | Implement `kinfra done` | Release slot + cleanup |
| 4.6 | Provision 6 slots | 4 light, 1 standard, 1 heavy |
| 4.7 | Migrate existing sandboxes | Move to claiming model |

### Phase 5: Polish

| Step | What | Why |
|------|------|-----|
| 5.1 | Document new workflow | User guide |
| 5.2 | Add `finish`/`complete` aliases | User preference |
| 5.3 | Consider post-merge hook | Auto-cleanup (optional) |

### Phase 6: Cleanup (Future)

| Step | What | Why |
|------|------|-----|
| 6.1 | Remove `instances` from Registry | Dual tracking (instances + slots) is transitional debt |
| 6.2 | Deprecate `sandbox create/init` | Replace with `kinfra impl` workflow |
| 6.3 | Simplify `sandbox list` | Only show slot-based worktrees |

**Note:** Phase 6 should be executed after Phase 4 is complete and the slot-claiming workflow is proven stable. The `instances` dict exists for backward compatibility during the transition.
