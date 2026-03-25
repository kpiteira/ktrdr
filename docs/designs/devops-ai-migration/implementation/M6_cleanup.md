---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M6: Cleanup

Final cleanup after all phases validated through dogfooding. Remove stale references, update memory, verify full development cycle.

## Context

After M1-M5, the migration is functionally complete. This milestone removes dead references, updates persistent documentation, and performs a full end-to-end development cycle using only devops-ai tools.

---

## Task 6.1: Clean stale references

**File(s):** Multiple (search-driven)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Search the entire codebase for references to deleted modules, old skill names, old port variables, and old kinfra commands. Fix or remove all stale references.

**Implementation Notes:**
- Search patterns:
  - `ktask` — old skill name (should be kbuild)
  - `kmilestone` — old skill name (should be kbuild)
  - `kdesign-validate` — old skill name (merged into kdesign)
  - `kdesign-impl-plan` — old skill name (should be kplan)
  - `address-review` — old skill name (should be kreview)
  - `e2e-testing` — old skill name (should be ke2e)
  - `e2e-test-designer` — old agent name (should be ke2e-test-scout)
  - `e2e-test-architect` — old agent name (should be ke2e-test-designer)
  - `e2e-tester` — old agent name (should be ke2e-test-runner)
  - `KTRDR_WORKER_PORT_1` through `KTRDR_WORKER_PORT_4` — old port variable names
  - `KTRDR_JAEGER_UI_PORT`, `KTRDR_GRAFANA_PORT`, `KTRDR_PROMETHEUS_PORT` — removed ports
  - `uv run kinfra` — should be bare `kinfra`
  - `sandbox_ports`, `sandbox_registry`, `sandbox_detect`, `sandbox_gate` — deleted modules
  - `ktrdr.cli.kinfra` — deleted module
- Check: CLAUDE.md, memory files, skill files, CI workflows, Makefile, scripts/
- Update or remove each reference

**Testing Requirements:**
- [ ] Zero matches for any search pattern listed above
- [ ] `make quality` passes
- [ ] `make test-unit` passes

**Acceptance Criteria:**
- [ ] No stale references to old skills, agents, ports, or modules
- [ ] All documentation internally consistent

---

## Task 6.2: Update memory files

**File(s):** `.claude/projects/-Users-karl-Documents-dev-ktrdr-prod/memory/MEMORY.md` and referenced memory files
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Update auto-memory entries that reference old commands, skills, or infrastructure patterns. These memories persist across sessions and would cause confusion if stale.

**Implementation Notes:**
- Read MEMORY.md and scan for references to:
  - `/ktask`, `/kmilestone` → update to `/kbuild`
  - `/kdesign-impl-plan` → update to `/kplan`
  - `/address-review` → update to `/kreview`
  - `e2e-test-designer`, `e2e-test-architect`, `e2e-tester` → update to ke2e agent names
  - Old port numbers (5003-5006 for workers) → update to new ranges (6100-6600)
  - Per-slot Jaeger/Grafana ports → shared ports (46686, 43000)
  - `uv run kinfra` → bare `kinfra`
  - `sandbox_ports.py`, `sandbox_registry.py` → deleted
- Update or remove each stale memory entry
- Add new memory entry documenting the migration completion

**Testing Requirements:**
- [ ] No stale references in MEMORY.md or referenced files
- [ ] New memory entry captures migration state

**Acceptance Criteria:**
- [ ] Memory files reflect current devops-ai tooling
- [ ] Future sessions won't see stale command references

---

## Task 6.3: Remove old registry

**File(s):** `~/.ktrdr/sandbox/` (external directory)
**Type:** CODING
**Estimated time:** 30 minutes

**Description:**
Remove ktrdr's old per-project sandbox registry now that the global devops-ai registry is in use.

**Implementation Notes:**
- Verify no active instances in `~/.ktrdr/sandbox/instances.json`
- Back up the file before deleting: `cp ~/.ktrdr/sandbox/instances.json ~/.ktrdr/sandbox/instances.json.bak`
- Remove: `rm -rf ~/.ktrdr/sandbox/`
- If `~/.ktrdr/` has other contents (shared/ for data/models/strategies), keep the parent directory
- Only delete the `sandbox/` subdirectory

**Testing Requirements:**
- [ ] No active sandbox instances before deletion
- [ ] `~/.ktrdr/shared/` preserved (if exists)
- [ ] kinfra uses global registry successfully

**Acceptance Criteria:**
- [ ] Old registry directory removed
- [ ] Global registry is sole source of truth
- [ ] Shared data directories unaffected

---

## Task 6.4: Validation — full development cycle

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Execute a complete development cycle using only devops-ai tools: design → plan → implement → test → PR. This is the final proof that the migration is complete and the workflow works end-to-end.

**Implementation Notes:**
- This should be a REAL development task, not a synthetic test
- Pick any small pending ktrdr issue or improvement
- Use exclusively devops-ai tools throughout

**Validation Steps:**
1. Load the `ke2e` skill
2. Execute the full workflow:
   - `/kdesign` — design a small feature or fix
   - `/kplan` — create implementation plan
   - `/kworktree impl <feature>/M1` — create worktree using bare `kinfra`
   - `/kbuild impl: M1_<name>.md` — implement with TDD
   - ke2e validation runs against sandbox
   - Commit and push
   - (Optional) Create PR
   - `/kworktree done <name>` — clean up
3. Throughout, verify:
   - kbuild reads `.devops-ai/project.md` for test commands
   - ke2e-test-scout finds recipes in `ke2e/tests/`
   - ke2e-test-runner executes against sandbox
   - Traces visible in shared Jaeger
   - 6 workers available in sandbox
   - All commands use bare `kinfra`
   - Handoff documents created

**Acceptance Criteria:**
- [ ] Complete design → plan → implement → test cycle with only devops-ai tools
- [ ] No fallback to old commands needed
- [ ] Shared observability works throughout
- [ ] 6 workers in sandbox
- [ ] ke2e validation passes
- [ ] Migration complete — ready for normal development
