# Design: Migrate ktrdr DevOps Tooling to DevOps AI

## Problem Statement

ktrdr's devops tooling evolved organically over months and now diverges from the generalized, leaner patterns in DevOps AI. This creates maintenance burden (two sets of skills to keep in sync), inconsistency (different command names and workflows between projects), and missed improvements (ktrdr doesn't benefit from devops-ai's shared observability, simplified port allocation, or consolidated skills).

## Goals

- ktrdr uses devops-ai skills via symlinks (single source of truth, no drift)
- One E2E test system (ke2e), not two overlapping ones
- Shared observability stack (fewer containers, no per-slot telemetry ports)
- Port allocation from config (infra.toml), not hardcoded Python
- Zero regression in ktrdr's development workflow
- Upstream improvements to devops-ai where ktrdr has stronger patterns
- Each phase dogfoods the previous phase's tooling

## Non-Goals

- Rewriting ktrdr's 27 domain skills (they're project-specific, they stay)
- Migrating ktrdr's deploy commands (homelab, canary, coding-agent) — these are ktrdr-only
- Changing how ktrdr's application code works — this is purely devops tooling
- Adopting Superpowers wholesale — cherry-pick patterns only (see devops-ai#17)

## Phases

### Phase 1: Skills Migration

Replace ktrdr's diverged skill copies with devops-ai symlinks.

| Delete from ktrdr | Replaced by (devops-ai symlink) |
|---|---|
| `.claude/skills/ktask/` | `kbuild` (task mode) |
| `.claude/skills/kmilestone/` | `kbuild` (milestone mode) |
| `.claude/skills/kdesign/` | `kdesign` (unified) |
| `.claude/skills/kdesign-validate/` | `kdesign` (merged in) |
| `.claude/skills/kdesign-impl-plan/` | `kplan` |
| `.claude/skills/address-review/` | `kreview` |
| `.claude/skills/_execution-core/` | Absorbed into `kbuild` |

**Stays in ktrdr:**
- `/kworktree` — deferred to Phase 3c (calls `uv run kinfra`, not bare `kinfra`)
- `/klandpr` — ktrdr-specific, no devops-ai equivalent
- 27 domain skills (training-pipeline, backtesting-engine, etc.)

**New files:**
- `.devops-ai/project.md` — ktrdr project config for devops-ai skills
- `.claude/rules/` — symlinks to devops-ai shared rules

**Decision: No deactivation period.** Delete old skills when replacing. Git history is the rollback path.

### Phase 2: E2E System Migration

Consolidate two overlapping E2E systems into one. Dogfoods Phase 1 (use kbuild for implementation).

**Agent swap:**

| Delete from ktrdr | Replaced by (devops-ai symlink) |
|---|---|
| `.claude/agents/e2e-test-designer.md` | `ke2e-test-scout.md` |
| `.claude/agents/e2e-test-architect.md` | `ke2e-test-designer.md` |
| `.claude/agents/e2e-tester.md` | `ke2e-test-runner.md` |

**Skill consolidation:**
- Delete `.claude/skills/e2e-testing/` (old system with 71 recipes)
- Project-local `.claude/skills/ke2e/` contains ktrdr's test catalog
- Global `~/.claude/skills/ke2e/` provides framework (from devops-ai symlink)
- Move 71 + 10 recipes into unified `ke2e/tests/` catalog
- Migrate preflight modules and troubleshooting guides

**Decision: Project-local ke2e shadows global.** The ke2e framework (SKILL.md template, FAILURE_CATEGORIES.md) comes from devops-ai. The test catalog, preflight modules, and troubleshooting guides are ktrdr-specific and live in the project's `.claude/skills/ke2e/`.

### Phase 3a: Shared Observability

Remove per-slot Jaeger/Grafana/Prometheus. Use devops-ai's shared stack. Dogfoods Phase 1+2.

- Remove `jaeger`, `grafana`, `prometheus` services from `docker-compose.sandbox.yml`
- Remove `depends_on` references to those services
- Add `devops-ai-observability` external Docker network
- Set OTEL endpoint to `http://devops-ai-jaeger:4317`
- Remove observability port allocations from `sandbox_ports.py`

**Ports freed per slot:** 5 (Jaeger UI, OTLP gRPC, OTLP HTTP, Prometheus, Grafana)

**Acceptable degradation:** If shared stack is down, traces silently lost. Same behavior as if per-slot Jaeger crashed.

### Phase 3b: Port Allocation + infra.toml

Replace hardcoded Python port allocation with declarative config. Dogfoods Phase 1+2+3a.

Create `.devops-ai/infra.toml` with uniform `base + slot_id` formula:
- `KTRDR_API_PORT = 8000`
- `KTRDR_DB_PORT = 5432`
- 6 worker ports (1 design, 2 backtest, 2 training, 1 assessment)

**Decision: Drop worker profiles.** No more light/standard/heavy slots. Every slot gets the same services — compose file is the source of truth. With shared observability removing 3 containers per slot and typically 2-3 concurrent sandboxes, resource concerns are minimal.

**Decision: 6 workers per slot.**
- 1 design worker (new — currently missing from infra)
- 2 backtest workers
- 2 training workers
- 1 assessment worker (new — currently missing from infra)

Replace ktrdr's per-project registry (`~/.ktrdr/sandbox/instances.json`) with devops-ai's global registry (`~/.devops-ai/registry.json`).

### Phase 3c: Full kinfra Migration

Replace embedded `ktrdr/cli/kinfra/` (~800 lines) with devops-ai's standalone `kinfra` CLI. Dogfoods all previous phases.

**Direct replacements:**
- `uv run kinfra spec` → `kinfra spec`
- `uv run kinfra impl` → `kinfra impl`
- `uv run kinfra done` → `kinfra done`
- `uv run kinfra worktrees` → `kinfra worktrees`
- `uv run kinfra sandbox up/down` → `kinfra sandbox start/rebuild`

**Requires upstream devops-ai work (tracked in devops-ai#17):**
- Health gate cascade (DB → backend → workers) — P1
- Local-prod pattern (optional project setting) — P2

**Stays as ktrdr-only CLI commands:**
- `ktrdr deploy` (homelab, canary, coding-agent)

**kworktree migrates here** — once kinfra itself is the devops-ai CLI, kworktree can use bare `kinfra` instead of `uv run kinfra`.

### Phase 4: Cleanup

After all phases validated through dogfooding:
- Delete `ktrdr/cli/sandbox_ports.py`
- Delete `ktrdr/cli/sandbox_registry.py`
- Delete `ktrdr/cli/sandbox_detect.py`
- Delete `ktrdr/cli/sandbox_gate.py`
- Delete `ktrdr/cli/kinfra/` (entire embedded kinfra)
- Delete old override templates
- Remove observability services from compose files
- Update CLAUDE.md to reflect new commands
- Update memory files referencing old skill names

## Key Decisions

### D1: Delete-not-deactivate
Old skills are deleted when replaced, not kept in deactivated state. Git history provides rollback. Simpler, no confusion about which skill is active.

### D2: Dogfooding as validation gate
Each phase uses previous phase's tooling. Phase 2 uses kbuild (from Phase 1). Phase 3 uses ke2e (from Phase 2). This forces each phase to prove itself before we build on it.

### D3: Drop worker profiles
Profiles (light/standard/heavy) were a port management trick. With shared observability reducing containers and <=3 concurrent sandboxes being the norm, uniform slot configuration is simpler and sufficient.

### D4: 6 workers (1D+2B+2T+1A)
Design and assessment workers exist in code but were never added to infrastructure. This migration fixes that gap. Worker composition: 1 design, 2 backtest, 2 training, 1 assessment.

### D5: kworktree deferred to Phase 3c
kworktree calls `uv run kinfra` (embedded). Can only switch to bare `kinfra` after the CLI itself is migrated. No interim shim.

### D6: klandpr stays in ktrdr
Mature, project-specific PR lifecycle tool. No devops-ai equivalent needed. May be contributed upstream later if demand exists.

### D7: Cherry-pick from Superpowers, don't adopt
Sub-agent review loops and health gate cascade are the highest-value patterns. Tracked in devops-ai#17 for upstream implementation. Sequential Thinking MCP documented as optional companion.

## Risks

### R1: kinfra feature parity (Phase 3c)
devops-ai's kinfra doesn't have local-prod or cascading health gates yet. Phase 3c is blocked until devops-ai#17 P1 items ship.

**Mitigation:** Phase 3a and 3b can proceed independently. 3c waits for upstream.

### R2: Recipe migration breaks E2E (Phase 2)
Moving 81 recipes between directory structures could introduce path/reference issues.

**Mitigation:** Validate with ke2e-test-runner against a running sandbox after migration. The recipes themselves don't change — only their location.

### R3: Shared observability dependency (Phase 3a)
All sandboxes depend on `kinfra observability up`. If forgotten, no traces.

**Mitigation:** kinfra sandbox start could check/warn if observability stack is down. Silent trace loss is acceptable for dev (same as Jaeger crashing today).

### R4: Port allocation formula change (Phase 3b)
Existing sandboxes use ktrdr's mixed-offset formulas. New formula (uniform base+slot) produces different ports for some services.

**Mitigation:** All existing sandboxes must be torn down before migration. This is a "rebuild all" transition, not a rolling update.

## Upstream Improvements to DevOps AI

Tracked in devops-ai#17:
1. **Health gate cascade** — P1, blocking Phase 3c
2. **Sub-agent review loops** — P1, enhances kbuild
3. **Preflight cure loops** — P2, enhances ke2e
4. **Local-prod pattern** — P2, blocking Phase 3c
5. **Sequential Thinking docs** — P3
6. **Parallel agent dispatch** — P3, blocked on Agent Teams
7. **Deploy command** — Backlog

## Milestone Structure

| Milestone | Phase | Depends On | Dogfoods |
|---|---|---|---|
| M1: Skills migration | Phase 1 | — | — |
| M2: E2E consolidation | Phase 2 | M1 | kbuild |
| M3: Shared observability | Phase 3a | M1 | kbuild, ke2e |
| M4: Port allocation + infra.toml | Phase 3b | M3 | kbuild, ke2e |
| M5: kinfra CLI migration | Phase 3c | M4 + devops-ai#17 | kbuild, ke2e |
| M6: Cleanup | Phase 4 | M5 | All |
