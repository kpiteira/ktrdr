---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 5: Cleanup + Documentation

**Goal:** Old commands removed, all documentation updated, clean errors for old command attempts.

**Branch:** `feature/cli-restructure-m5`

**Builds on:** Milestone 4 (performance optimized)

---

## Task 5.1: Audit CLI References

**File:** N/A (research task)
**Type:** RESEARCH
**Estimated time:** 1.5 hours

**Task Categories:** Configuration

**Description:**
Find all references to old CLI commands in documentation, prompts, slash commands, and code comments. Create a comprehensive list for updating.

**Implementation Notes:**

Search patterns:
```bash
# Find old command patterns
rg "ktrdr models" --type md --type yaml
rg "ktrdr strategies" --type md --type yaml
rg "ktrdr agent" --type md --type yaml
rg "ktrdr operations" --type md --type yaml
rg "ktrdr backtest run" --type md --type yaml

# Check slash commands
rg "ktrdr" .claude/skills/

# Check prompts
rg "ktrdr" docs/prompts/

# Check README
rg "ktrdr" README.md
```

Document findings:

```markdown
## CLI Reference Audit

### Documentation Files
| File | Old Command | New Command |
|------|-------------|-------------|
| README.md:45 | `ktrdr models train` | `ktrdr train` |
| docs/getting-started.md:23 | `ktrdr agent trigger` | `ktrdr research` |
| ... | ... | ... |

### Slash Commands / Skills
| File | Line | Change Needed |
|------|------|---------------|
| .claude/skills/training.md | 12 | Update example |
| ... | ... | ... |

### Code Comments
| File | Line | Change Needed |
|------|------|---------------|
| ktrdr/api/routers/training.py | 45 | Update docstring |
| ... | ... | ... |

### CLAUDE.md
| Section | Change Needed |
|---------|---------------|
| Essential Commands | Update all examples |
| ... | ... |
```

**Testing Requirements:**

*Unit Tests:*
- None (research task)

*Integration Tests:*
- None (research task)

*Smoke Test:*
```bash
# Verify search is comprehensive
rg "ktrdr (models|strategies|agent|operations|backtest run)" --type-add 'docs:*.md' -t docs
```

**Acceptance Criteria:**
- [ ] All old command references identified
- [ ] Categorized by file type (docs, skills, code)
- [ ] Update plan documented
- [ ] No references missed

---

## Task 5.2: Update Documentation

**Files:** Various `.md` files
**Type:** CODING
**Estimated time:** 2 hours

**Task Categories:** Configuration

**Description:**
Update all documentation files identified in Task 5.1 to use new command syntax.

**Implementation Notes:**

Command mapping (from DESIGN.md):

| Old Command | New Command |
|-------------|-------------|
| `ktrdr models train` | `ktrdr train` |
| `ktrdr backtest run` | `ktrdr backtest` |
| `ktrdr strategies backtest` | `ktrdr backtest` |
| `ktrdr strategies validate` | `ktrdr validate` |
| `ktrdr strategies features` | `ktrdr show features` |
| `ktrdr strategies list` | `ktrdr list strategies` |
| `ktrdr strategies migrate` | `ktrdr migrate` |
| `ktrdr operations list` | `ktrdr ops` |
| `ktrdr operations status` | `ktrdr status` |
| `ktrdr operations cancel` | `ktrdr cancel` |
| `ktrdr agent trigger` | `ktrdr research` |
| `ktrdr agent status` | `ktrdr status` |
| `ktrdr agent cancel` | `ktrdr cancel` |

Priority files:
1. `README.md`
2. `CLAUDE.md`
3. `.claude/skills/*.md`
4. `docs/*.md`

**Testing Requirements:**

*Unit Tests:*
- None (documentation)

*Integration Tests:*
- None (documentation)

*Smoke Test:*
```bash
# Verify no old commands remain
rg "ktrdr (models|strategies|agent|operations|backtest run)" --type-add 'docs:*.md' -t docs
# Should return nothing
```

**Acceptance Criteria:**
- [ ] All documentation updated
- [ ] No old command syntax remains
- [ ] Examples are accurate and runnable
- [ ] CLAUDE.md reflects new structure

---

## Task 5.3: Remove Old Command Files

**Files:** Multiple files to delete
**Type:** CODING
**Estimated time:** 1 hour

**Task Categories:** Wiring/DI

**Description:**
Remove old command implementation files and update the CLI entry point to use only the new structure.

**Implementation Notes:**

Files to remove:
```
ktrdr/cli/model_commands.py          # Replaced by commands/train.py
ktrdr/cli/async_model_commands.py    # Replaced by commands/train.py
ktrdr/cli/strategy_commands.py       # Replaced by commands/backtest.py, validate.py, etc.
ktrdr/cli/agent_commands.py          # Replaced by commands/research.py
ktrdr/cli/operations_commands.py     # Replaced by commands/ops.py, status.py, etc.
ktrdr/cli/backtest_commands.py       # Replaced by commands/backtest.py
ktrdr/cli/indicator_commands.py      # Removed (unused per DESIGN.md)
ktrdr/cli/fuzzy_commands.py          # Removed (unused per DESIGN.md)
ktrdr/cli/dummy_commands.py          # Removed (demo only per DESIGN.md)
```

Files to keep (subgroups):
```
ktrdr/cli/sandbox.py                 # Keep - sandbox subgroup
ktrdr/cli/ib_commands.py             # Keep - IB subgroup
ktrdr/cli/deploy_commands.py         # Keep - deploy subgroup
ktrdr/cli/data_commands.py           # Keep - data commands
```

Update `ktrdr/cli/__init__.py`:
```python
# Remove old imports
# Keep only new app import

from ktrdr.cli.app import app

__all__ = ["app"]
```

Update `pyproject.toml` entry point (if different):
```toml
[project.scripts]
ktrdr = "ktrdr.cli.app:app"
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_old_imports_fail()` — verify old modules not importable

*Integration Tests:*
- [ ] `test_cli_still_works()` — full command suite test
- [ ] `test_subgroups_work()` — sandbox, ib, deploy still work

*Smoke Test:*
```bash
# Verify old modules gone
python -c "from ktrdr.cli.model_commands import *" 2>&1 | grep -q "No module"

# Verify new CLI works
ktrdr --help
ktrdr train --help
ktrdr sandbox status
```

**Acceptance Criteria:**
- [ ] Old command files deleted
- [ ] Entry point updated
- [ ] New CLI works completely
- [ ] Subgroups (sandbox, ib, deploy) still work
- [ ] No import errors

---

## Task 5.4: Verify Clean Error Messages

**File:** `ktrdr/cli/app.py`
**Type:** CODING
**Estimated time:** 30 min

**Task Categories:** Configuration

**Description:**
Verify that attempting old commands produces clean, helpful error messages (not stack traces).

**Implementation Notes:**

Typer naturally handles unknown commands with:
```
Usage: ktrdr [OPTIONS] COMMAND [ARGS]...
Try 'ktrdr --help' for help.

Error: No such command 'models'.
```

This is acceptable. Optionally, add a custom error handler for common old commands:

```python
# Optional: Custom suggestions for old commands
OLD_COMMAND_HINTS = {
    "models": "Did you mean 'ktrdr train'?",
    "strategies": "Try 'ktrdr list strategies', 'ktrdr validate', or 'ktrdr backtest'",
    "agent": "Did you mean 'ktrdr research'?",
    "operations": "Try 'ktrdr ops', 'ktrdr status', or 'ktrdr cancel'",
}

# This would require custom Typer error handling - may not be worth it
# Default Typer errors are clear enough
```

**Decision:** Default Typer error messages are sufficient. No custom handling needed unless users report confusion.

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_unknown_command_error()` — verify clean error, not crash

*Integration Tests:*
- [ ] `test_old_commands_fail_cleanly()` — all old commands produce helpful errors

*Smoke Test:*
```bash
# Should show clean error
ktrdr models train 2>&1 | grep -q "No such command"
ktrdr strategies backtest 2>&1 | grep -q "No such command"
ktrdr agent trigger 2>&1 | grep -q "No such command"
ktrdr operations list 2>&1 | grep -q "No such command"
```

**Acceptance Criteria:**
- [ ] Old commands produce "No such command" error
- [ ] No stack traces for typos
- [ ] Help suggestion shown
- [ ] Exit code is non-zero

---

## Milestone 5 Verification

### E2E Test Scenario

**Purpose:** Prove old commands are gone and new CLI is complete.

**Duration:** ~2 minutes

**Prerequisites:**
- All M1-M4 complete
- Backend running

**Test Steps:**

```bash
# 1. Verify old commands fail cleanly
ktrdr models train 2>&1
# Expected: "No such command 'models'"

ktrdr strategies backtest 2>&1
# Expected: "No such command 'strategies'"

ktrdr agent trigger 2>&1
# Expected: "No such command 'agent'"

ktrdr operations list 2>&1
# Expected: "No such command 'operations'"

# 2. Verify new commands work
ktrdr train --help
ktrdr backtest --help
ktrdr research --help
ktrdr status
ktrdr ops
ktrdr list strategies
ktrdr show AAPL 1h
ktrdr validate momentum

# 3. Verify subgroups still work
ktrdr sandbox status
ktrdr ib status
ktrdr deploy --help

# 4. Verify no old imports
python -c "from ktrdr.cli.model_commands import *" 2>&1
# Expected: ModuleNotFoundError

# 5. Check documentation
grep -r "ktrdr models" docs/ README.md CLAUDE.md
# Expected: No results

# 6. Full workflow test
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
ktrdr ops
ktrdr status $OP_ID
```

**Success Criteria:**
- [ ] All old commands produce clean errors
- [ ] All new commands work
- [ ] Subgroups preserved
- [ ] No old imports possible
- [ ] Documentation clean
- [ ] Full workflow works

### Final Checklist

- [ ] All 4 tasks complete
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes
- [ ] All M1-M4 tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No old CLI references in codebase
- [ ] Documentation audit complete

---

## Post-Milestone Verification

After M5 is complete, run the full verification suite:

```bash
# 1. Performance check
time ktrdr --help
# Must be <100ms

# 2. Full command test
ktrdr train momentum --start 2024-01-01 --end 2024-06-01
ktrdr backtest momentum --start 2024-01-01 --end 2024-06-01
ktrdr research "test"
ktrdr ops --json | jq
ktrdr list strategies
ktrdr show AAPL 1h
ktrdr validate momentum

# 3. JSON output test
ktrdr --json train momentum --start 2024-01-01 --end 2024-06-01
ktrdr --json ops

# 4. Subgroup test
ktrdr sandbox status
ktrdr ib status

# 5. Quality gates
make test-unit
make quality
```

**The CLI restructure is complete when all checks pass.**
