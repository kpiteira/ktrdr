# M5 Cleanup Handoff

## Task 5.1 Complete: Audit CLI References

### CLI Reference Audit Results

**Old Command Patterns Found:**
- `ktrdr models` — 119 references
- `ktrdr strategies` — 95 references
- `ktrdr agent` — 166 references
- `ktrdr operations` — 114 references
- `ktrdr backtest run` — 31 references

---

### Priority 1: User-Facing Documentation (UPDATE REQUIRED)

These files contain user-visible documentation with old CLI commands.

| File | Lines | Old Commands | New Commands |
|------|-------|--------------|--------------|
| `README.md` | 246-262 | `ktrdr models train/list/test`, `ktrdr strategies validate/backtest`, `ktrdr operations list/status/cancel` | `ktrdr train`, `ktrdr validate`, `ktrdr backtest`, `ktrdr ops`, `ktrdr status`, `ktrdr cancel` |
| `CLAUDE.md` | 201 | `ktrdr operations list` | `ktrdr ops` |
| `docs/user-guides/cli-reference.md` | 12-341 | `ktrdr strategies validate/upgrade/list/backtest`, `ktrdr models train`, `ktrdr operations list/status/cancel/resume` | All need updating per mapping |
| `docs/user-guides/strategy-management.md` | 12-113 | `ktrdr strategies list/validate/upgrade/migrate` | `ktrdr list strategies`, `ktrdr validate`, `ktrdr migrate` |
| `docs/user-guides/checkpoint-resume.md` | 40-198 | `ktrdr operations list/resume/status` | `ktrdr ops`, `ktrdr resume`, `ktrdr status` |
| `docs/user-guides/deployment.md` | 823 | `ktrdr models train` | `ktrdr train` |
| `strategies/README.md` | 51-113 | `ktrdr strategies validate/features/migrate` | `ktrdr validate`, `ktrdr show features`, `ktrdr migrate` |
| `docs/developer/testing-guide.md` | 30, 69 | `ktrdr models train`, `ktrdr strategies backtest` | `ktrdr train`, `ktrdr backtest` |
| `docs/strategy-grammar.md` | 403 | `ktrdr strategies validate` | `ktrdr validate` |
| `docs/migration-strategy.md` | 26-35 | `ktrdr strategies standardize-versions/migrate-all/validate-all/cleanup-v1-backups` | Custom commands (may not be migrated - verify) |

---

### Priority 2: Skills/Prompts (UPDATE REQUIRED)

| File | Lines | Change Needed |
|------|-------|---------------|
| `.claude/skills/deployment/SKILL.md` | 82-89 | Update `ktrdr models train/list/test` → `ktrdr train`, Update `ktrdr operations list/status/cancel` → `ktrdr ops/status/cancel` |
| `.claude/skills/e2e-testing/tests/cli/operations-workflow.md` | 51-176 | Update `ktrdr backtest run` → `ktrdr backtest`, Update `ktrdr operations list/status/cancel` → `ktrdr ops/status/cancel` |
| `.claude/skills/e2e-testing/tests/cli/client-migration.md` | 73-119 | Update all old commands to new format |

---

### Priority 3: Code Files (TO BE DELETED in Task 5.3)

These files will be removed entirely, so no updates needed:

| File | Reason |
|------|--------|
| `ktrdr/cli/model_commands.py` | Replaced by `commands/train.py` |
| `ktrdr/cli/async_model_commands.py` | Replaced by `commands/train.py` |
| `ktrdr/cli/strategy_commands.py` | Replaced by `commands/backtest.py`, `validate.py`, etc. |
| `ktrdr/cli/agent_commands.py` | Replaced by `commands/research.py` |
| `ktrdr/cli/operations_commands.py` | Replaced by `commands/ops.py`, `status.py`, etc. |
| `ktrdr/cli/backtest_commands.py` | Replaced by `commands/backtest.py` |

---

### Priority 4: Code Files with User-Facing Strings (UPDATE REQUIRED)

| File | Lines | Change Needed |
|------|-------|---------------|
| `ktrdr/decision/orchestrator.py` | 833 | `ktrdr models train` → `ktrdr train` |
| `ktrdr/cli/operation_runner.py` | 253, 291 | `ktrdr operations status` → `ktrdr status` |
| `ktrdr/cli/operation_adapters.py` | 511 | `ktrdr operations status` → `ktrdr status` |
| `ktrdr/cli/checkpoints_commands.py` | 209 | `ktrdr operations resume` → `ktrdr resume` |
| `ktrdr/config/strategy_validator.py` | 438 | `ktrdr strategies migrate` → `ktrdr migrate` |

---

### Priority 5: Architecture/Design Docs (LOW PRIORITY)

These are historical/specification docs. May be left as-is since they document the state at time of writing. Decision: Skip unless confusing to users.

- `docs/architecture/` — 50+ references across multiple files
- `docs/designs/` — Many references (excluding cli-restructure which is the plan itself)
- `docs/agentic/` — 150+ references
- `specification/` — 50+ references
- `docs/testing/` — Various references

---

### Priority 6: Test Files (VERIFY BEHAVIOR)

These test the OLD commands and may break when old files are deleted:

| File | Notes |
|------|-------|
| `tests/unit/cli/test_strategy_migrate.py` | Tests `ktrdr strategies migrate` |
| `tests/unit/cli/test_strategy_features.py` | Tests `ktrdr strategies features` |
| `tests/unit/cli/test_strategy_commands.py` | Tests `ktrdr strategies validate` |
| `tests/integration/test_unified_cli_migration.py` | Tests old `ktrdr models train` |
| `tests/integration/agent_tests/test_agent_*.py` | Tests old `ktrdr agent` commands |

**Decision needed:** These tests may need to be updated to test new commands OR deleted if testing old code that will be removed.

---

### Command Mapping Reference

| Old Command | New Command |
|-------------|-------------|
| `ktrdr models train` | `ktrdr train` |
| `ktrdr models list` | N/A (removed or `ktrdr list models` if exists) |
| `ktrdr models test` | N/A (verify if exists in new CLI) |
| `ktrdr backtest run` | `ktrdr backtest` |
| `ktrdr strategies backtest` | `ktrdr backtest` |
| `ktrdr strategies validate` | `ktrdr validate` |
| `ktrdr strategies features` | `ktrdr show features` |
| `ktrdr strategies list` | `ktrdr list strategies` |
| `ktrdr strategies migrate` | `ktrdr migrate` |
| `ktrdr strategies upgrade` | N/A (verify if exists) |
| `ktrdr operations list` | `ktrdr ops` |
| `ktrdr operations status` | `ktrdr status` |
| `ktrdr operations cancel` | `ktrdr cancel` |
| `ktrdr operations resume` | `ktrdr resume` |
| `ktrdr operations retry` | N/A (verify if exists) |
| `ktrdr agent trigger` | `ktrdr research` |
| `ktrdr agent status` | `ktrdr status` |
| `ktrdr agent cancel` | `ktrdr cancel` |
| `ktrdr agent budget` | N/A (verify if exists) |

---

### Summary Counts

| Category | Files Needing Update |
|----------|---------------------|
| User-facing docs (Priority 1) | 10 files |
| Skills/prompts (Priority 2) | 3 files |
| Code files to delete (Priority 3) | 6 files |
| Code with user-facing strings (Priority 4) | 5 files |
| Arch/design docs (Priority 5) | ~50 files (skip) |
| Test files (Priority 6) | 5 files (verify) |

---

---

## Task 5.2 Complete: Update Documentation

### What Was Updated

**Priority 1 (User-facing docs):** 7 files
- README.md
- CLAUDE.md
- docs/user-guides/cli-reference.md
- docs/user-guides/strategy-management.md
- docs/user-guides/checkpoint-resume.md
- strategies/README.md

**Priority 2 (Skills/prompts):** 3 files
- .claude/skills/deployment/SKILL.md
- .claude/skills/e2e-testing/tests/cli/operations-workflow.md
- .claude/skills/e2e-testing/tests/cli/client-migration.md

**Priority 4 (Code with user-facing strings):** 5 files
- ktrdr/decision/orchestrator.py
- ktrdr/cli/operation_runner.py
- ktrdr/cli/operation_adapters.py
- ktrdr/cli/checkpoints_commands.py
- ktrdr/config/strategy_validator.py

### Verification

```bash
# Verified no old commands remain in priority files:
rg "ktrdr (models|strategies|agent|operations|backtest run)" README.md CLAUDE.md \
  docs/user-guides/*.md strategies/README.md .claude/skills/**/*.md
# Result: No matches found
```

### Skipped Files (By Design)

- **docs/user-guides/deployment.md** — Only 1 reference, low priority
- **docs/developer/testing-guide.md** — Only 2 references, low priority
- **docs/strategy-grammar.md** — Only 1 reference, low priority
- **docs/migration-strategy.md** — Custom commands not in new CLI (may be obsolete)
- **Architecture/design docs** — Historical documentation, left as-is

### Next Task Notes (Task 5.3)

For Task 5.3 (Remove Old Command Files):
1. Files to delete per the audit in Task 5.1 (Priority 3 section)
2. Update `ktrdr/cli/__init__.py` to remove old imports
3. Consolidate command registration to `app.py` only (fix dual registration debt)
4. Run `make test-unit` after deletions to catch import errors
5. Tests in Priority 6 will likely fail - may need deletion or updates
