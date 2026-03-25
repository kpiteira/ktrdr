---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M5: kinfra CLI Migration

Replace ktrdr's embedded kinfra Python CLI (~800 lines in `ktrdr/cli/kinfra/`) with devops-ai's standalone `kinfra` CLI. Migrate kworktree skill. Extract deploy command.

## Context

**Current state:**
- Embedded kinfra at `ktrdr/cli/kinfra/` with: main.py, spec.py, impl.py, done.py, sandbox.py, slots.py, override.py, local_prod.py, deploy.py, templates/
- kworktree skill calls `uv run kinfra` (embedded)
- Deploy command integrated into kinfra subcommands
- sandbox_detect.py, sandbox_gate.py, sandbox_registry.py as support modules

**Target state:**
- Bare `kinfra` CLI from devops-ai handles: spec, impl, done, worktrees, sandbox start/rebuild/stop, status, observability
- kworktree skill uses devops-ai global version (bare `kinfra`)
- Deploy extracted to `ktrdr/cli/commands/deploy.py` (ktrdr-specific)
- Embedded kinfra deleted

**Blocked on:** devops-ai#17 — health gate cascade (P1) and local-prod pattern (P2) must ship in devops-ai before this milestone starts.

---

## Task 5.1: Verify devops-ai kinfra feature parity

**File(s):** (research — no code changes)
**Type:** RESEARCH
**Estimated time:** 2 hours

**Description:**
Before migrating, verify devops-ai's kinfra CLI has the features ktrdr needs. Check that devops-ai#17 P1 (health cascade) and P2 (local-prod) have been implemented. Document any remaining gaps.

**Implementation Notes:**
- Run `kinfra --help` and compare commands against ktrdr's embedded kinfra
- Verify `kinfra init` works with ktrdr's infra.toml (from M4)
- Verify `kinfra sandbox start` performs health checks
- Verify health cascade is implemented (if devops-ai#17 P1 shipped)
- Verify local-prod support exists (if devops-ai#17 P2 shipped)
- Check 1Password integration: does `kinfra sandbox start` resolve `op://` secrets?
- Document any gaps that would block migration

**Testing Requirements:**
- [ ] `kinfra` CLI is installed and accessible
- [ ] `kinfra init` parses ktrdr's infra.toml
- [ ] `kinfra sandbox start` can start containers
- [ ] Health checks work against ktrdr's backend
- [ ] 1Password secrets are resolved

**Acceptance Criteria:**
- [ ] Gap analysis document: list of features that work, features missing, workarounds
- [ ] Clear go/no-go decision for proceeding with migration
- [ ] If blocked, document what's needed from devops-ai

---

## Task 5.2: Extract deploy command

**File(s):** `ktrdr/cli/kinfra/deploy.py` → `ktrdr/cli/commands/deploy.py`, `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Extract the deploy command from embedded kinfra into ktrdr's standard CLI command structure. This keeps deploy as a ktrdr-specific command that doesn't depend on embedded kinfra.

**Implementation Notes:**
- Read `ktrdr/cli/kinfra/deploy.py` to understand deploy targets (homelab, canary, coding-agent)
- Create `ktrdr/cli/commands/deploy.py` with the same functionality
- Register as `ktrdr deploy <target>` on the CLI app
- Import any helpers from kinfra that deploy needs — if they're kinfra-specific, inline them
- Avoid importing from `ktrdr.cli.kinfra` — the whole module will be deleted
- The deploy command should work independently of kinfra

**Testing Requirements:**
- [ ] `uv run ktrdr deploy --help` shows deploy targets
- [ ] Deploy logic preserved (same behavior as embedded version)
- [ ] No imports from `ktrdr.cli.kinfra`
- [ ] `make quality` passes
- [ ] `make test-unit` passes

**Acceptance Criteria:**
- [ ] Deploy command works as `ktrdr deploy <target>`
- [ ] Zero dependency on embedded kinfra module
- [ ] Existing deploy workflows unaffected

---

## Task 5.3: Switch kinfra invocations to standalone CLI

**File(s):** `.claude/skills/kworktree/SKILL.md`, `.devops-ai/project.md`, `CLAUDE.md`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Replace all references to `uv run kinfra` with bare `kinfra` throughout the project. Delete ktrdr's local kworktree skill so the global devops-ai version takes over.

**Implementation Notes:**
- Delete `.claude/skills/kworktree/SKILL.md` (local ktrdr variant)
- Global `~/.claude/skills/kworktree/` (devops-ai symlink) automatically takes over
- Update `.devops-ai/project.md` Infrastructure section: `uv run kinfra` → `kinfra`
- Update `CLAUDE.md`:
  - Essential Commands section
  - Sandbox Awareness section
  - Docker Compose Warning section
  - Worktree Workflow section
  - All references to `uv run kinfra`
- Search codebase for `uv run kinfra` references and update
- Note: `ktrdr deploy` stays as `uv run ktrdr deploy` (it's a ktrdr CLI command, not kinfra)

**Testing Requirements:**
- [ ] No references to `uv run kinfra` in CLAUDE.md or project.md
- [ ] Local kworktree skill deleted
- [ ] `kinfra status` works from project root
- [ ] `kinfra worktrees` works
- [ ] `kinfra sandbox start` works against running sandbox

**Acceptance Criteria:**
- [ ] All kinfra invocations use bare `kinfra`
- [ ] kworktree uses devops-ai global version
- [ ] Documentation consistent

---

## Task 5.4: Delete embedded kinfra

**File(s):** `ktrdr/cli/kinfra/`, `ktrdr/cli/sandbox_ports.py`, `ktrdr/cli/sandbox_registry.py`, `ktrdr/cli/sandbox_detect.py`, `ktrdr/cli/sandbox_gate.py`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Delete the embedded kinfra module and all supporting sandbox Python modules. Update any remaining imports.

**Implementation Notes:**
- Delete entire directory: `ktrdr/cli/kinfra/` (main.py, spec.py, impl.py, done.py, sandbox.py, slots.py, override.py, local_prod.py, deploy.py, templates/)
- Delete support modules:
  - `ktrdr/cli/sandbox_ports.py` (replaced by infra.toml + devops-ai compute_ports)
  - `ktrdr/cli/sandbox_registry.py` (replaced by global registry)
  - `ktrdr/cli/sandbox_detect.py` (replaced by devops-ai's sandbox detection)
  - `ktrdr/cli/sandbox_gate.py` (upstreamed as health cascade)
- Search for imports of these modules across codebase:
  - `from ktrdr.cli.kinfra import ...`
  - `from ktrdr.cli.sandbox_ports import ...`
  - `from ktrdr.cli.sandbox_registry import ...`
  - `from ktrdr.cli.sandbox_detect import ...`
  - `from ktrdr.cli.sandbox_gate import ...`
- Update or remove any `kinfra` registration on ktrdr's CLI app (if it was a subcommand group)
- Check `ktrdr/cli/__init__.py` or `ktrdr/cli/app.py` for kinfra imports

**Testing Requirements:**
- [ ] No Python files remain in `ktrdr/cli/kinfra/`
- [ ] No `sandbox_*.py` files remain in `ktrdr/cli/`
- [ ] No dangling imports anywhere in codebase
- [ ] `make quality` passes (no import errors)
- [ ] `make test-unit` passes
- [ ] ktrdr CLI still works for non-kinfra commands (train, backtest, etc.)

**Acceptance Criteria:**
- [ ] ~800 lines of embedded kinfra code deleted
- [ ] ~400+ lines of sandbox support code deleted
- [ ] Zero import errors
- [ ] ktrdr CLI functional for all non-kinfra commands

---

## Task 5.5: Validation — full worktree lifecycle

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the complete worktree lifecycle using bare kinfra and devops-ai kworktree skill. This proves the full migration works end-to-end.

**Implementation Notes:**
- This is the most important validation in the entire migration
- Tests the complete chain: kinfra CLI → infra.toml → sandbox → health check → worktree

**Validation Steps:**
1. Load the `ke2e` skill
2. Invoke ke2e-test-scout with requirement: "Validate full worktree lifecycle — create impl worktree, sandbox starts with health checks, work in worktree, tear down cleanly"
3. Execute lifecycle:
   - `kinfra impl test-migration/M1` → creates worktree + claims slot + starts sandbox
   - Verify sandbox healthy: `curl http://localhost:${API_PORT}/api/v1/health`
   - Verify workers registered: `curl http://localhost:${API_PORT}/api/v1/workers` shows 6 workers
   - Verify traces in shared Jaeger
   - `kinfra done test-migration-M1` → stops containers + releases slot + removes worktree
   - Verify slot released: `kinfra status` shows slot available
   - Verify no orphan containers: `docker ps` shows no test-migration containers
4. Test kworktree skill:
   - `/kworktree impl test-migration2/M1` should use bare `kinfra`
   - Verify agent-deck session created
   - `/kworktree done test-migration2-M1`
5. Test deploy command (separate from kinfra):
   - `uv run ktrdr deploy --help` shows targets

**Acceptance Criteria:**
- [ ] Full lifecycle works: create → use → destroy
- [ ] 6 workers register in sandbox
- [ ] Traces visible in shared Jaeger
- [ ] Slot properly released after done
- [ ] kworktree skill uses bare kinfra
- [ ] Deploy command independent and functional
- [ ] HANDOFF document updated
