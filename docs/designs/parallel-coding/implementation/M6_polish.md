---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 6: Polish

**Branch:** `feature/kinfra-polish`
**Builds on:** M5 (full workflow complete)

## Goal

Add finishing touches: command aliases, documentation updates, and a full workflow validation.

---

## Task 6.1: Add command aliases

**File(s):**
- `ktrdr/cli/kinfra/main.py` (modify)
- `ktrdr/cli/kinfra/done.py` (modify)

**Type:** CODING
**Task Categories:** API Endpoint

**Description:**
Add `finish` and `complete` as aliases for the `done` command.

**Implementation Notes:**
```python
# In main.py, register done with aliases
from .done import done as done_command

# Primary command
app.command(name="done")(done_command)

# Aliases (hidden from main help to reduce clutter)
app.command(name="finish", hidden=True)(done_command)
app.command(name="complete", hidden=True)(done_command)
```

**Testing Requirements:**

*Unit Tests:*
- [ ] `test_finish_alias` — `kinfra finish` works
- [ ] `test_complete_alias` — `kinfra complete` works
- [ ] `test_aliases_hidden` — aliases don't show in main help

*Smoke Test:*
```bash
uv run kinfra finish --help
uv run kinfra complete --help
uv run kinfra --help | grep -v finish  # Should not appear
```

**Acceptance Criteria:**
- [ ] `kinfra finish` works as alias for `done`
- [ ] `kinfra complete` works as alias for `done`
- [ ] Aliases hidden from main help (less clutter)

---

## Task 6.2: Update CLAUDE.md

**File(s):**
- `CLAUDE.md` (modify)

**Type:** CODING
**Task Categories:** Configuration

**Description:**
Update CLAUDE.md with new kinfra workflow. Add section on worktree/sandbox commands and update existing sandbox awareness section.

**Implementation Notes:**
Add/update these sections:
1. Add `kinfra` to Essential Commands section
2. Update Sandbox Awareness section to mention kinfra
3. Add warning about raw `docker compose up`
4. Add worktree workflow section

**Changes to make:**

```markdown
## Essential Commands

```bash
# Infrastructure management (kinfra)
kinfra spec <feature>           # Create spec worktree for design
kinfra impl <feature/milestone> # Create impl worktree with sandbox
kinfra done <name>              # Complete worktree, release sandbox
kinfra worktrees                # List active worktrees
kinfra sandbox slots            # List sandbox slots
kinfra sandbox up/down          # Manual sandbox control

# Start development environment
docker compose up               # DON'T use this - see warning below
kinfra sandbox up               # Use this instead
```

## Docker Compose Warning

**NEVER run `docker compose up` without explicit `-f` flag.**

The docker-compose.yml symlink has been removed to prevent port conflicts.
Always use kinfra commands:
- `kinfra sandbox up/down` for sandboxes
- `kinfra local-prod up/down` for local-prod
- `kinfra impl` / `kinfra done` for worktree lifecycle

## Worktree Workflow

For parallel development work:
1. `kinfra spec <feature>` — Create lightweight worktree for design (no Docker)
2. `kinfra impl <feature/milestone>` — Create worktree with sandbox slot
3. Work on implementation with full E2E testing
4. `kinfra done <name>` — Clean up after PR merge
```

**Testing Requirements:**

*Smoke Test:*
```bash
grep "kinfra" CLAUDE.md  # Should find new content
grep "docker compose up" CLAUDE.md  # Should find warning
```

**Acceptance Criteria:**
- [ ] kinfra commands documented
- [ ] Sandbox workflow updated
- [ ] Docker compose warning added
- [ ] Worktree workflow documented

---

## Task 6.3: Update sandbox skill

**File(s):**
- `.claude/skills/sandbox.md` (modify)

**Type:** CODING
**Task Categories:** Configuration

**Description:**
Update sandbox skill with kinfra commands and new workflow.

**Implementation Notes:**
- Replace `ktrdr sandbox` references with `kinfra sandbox`
- Add slot pool documentation
- Add worktree workflow section
- Update any code examples

**Acceptance Criteria:**
- [ ] Skill references kinfra commands
- [ ] Slot pool documented
- [ ] Worktree workflow documented
- [ ] Examples updated

---

## Task 6.4: Execute E2E Test - Full Workflow

**Type:** VALIDATION
**Estimated time:** 20 min

**Description:**
Validate the complete workflow works end-to-end.

**E2E Test: Full Parallel Workflow**

This test validates the complete user journey:
1. Create spec worktree for design
2. Create impl worktree with sandbox
3. Verify containers running
4. Complete worktree
5. Verify cleanup

**Execution Steps:**

| Step | Action | Expected Result | Evidence |
|------|--------|-----------------|----------|
| **Spec Workflow** ||||
| 1 | `uv run kinfra spec polish-test` | Worktree created | Exit code 0 |
| 2 | `ls ../ktrdr-spec-polish-test/docs/designs/polish-test/` | Design folder exists | Exit code 0 |
| 3 | `uv run kinfra worktrees` | Shows spec worktree | Table shows "polish-test" |
| 4 | `git worktree remove ../ktrdr-spec-polish-test && git branch -d spec/polish-test` | Cleanup | Exit code 0 |
| **Impl Workflow** ||||
| 5 | Create milestone: `mkdir -p docs/designs/polish-e2e/implementation && echo "# M1" > docs/designs/polish-e2e/implementation/M1_test.md` | File created | Exit code 0 |
| 6 | `uv run kinfra impl polish-e2e/M1` | Worktree + sandbox created | Exit code 0, output shows slot |
| 7 | `uv run kinfra sandbox slots` | Slot claimed | Shows "polish-e2e-M1" |
| 8 | `curl http://localhost:800X/health` (use correct port) | Backend healthy | 200 response |
| 9 | `uv run kinfra worktrees` | Shows impl with slot info | Table shows slot number |
| **Done Workflow** ||||
| 10 | `uv run kinfra done polish-e2e-M1 --force` | Cleanup complete | Exit code 0 |
| 11 | `uv run kinfra sandbox slots` | Slot available | No "polish-e2e" claim |
| 12 | `ls ../ktrdr-impl-polish-e2e-M1` | Worktree gone | Exit code != 0 |
| **Aliases** ||||
| 13 | `uv run kinfra finish --help` | Shows done help | Exit code 0 |
| 14 | `uv run kinfra complete --help` | Shows done help | Exit code 0 |
| **Documentation** ||||
| 15 | `grep "kinfra" CLAUDE.md` | Found | Exit code 0 |

**Cleanup:**
```bash
rm -rf docs/designs/polish-e2e/
```

**Success Criteria:**
- [ ] Spec workflow works
- [ ] Impl workflow works (worktree + sandbox)
- [ ] Done workflow works (cleanup)
- [ ] Aliases work
- [ ] Documentation updated

**Acceptance Criteria:**
- [ ] All E2E test steps pass
- [ ] Full workflow is smooth
- [ ] `make quality` passes
- [ ] All previous milestone E2E tests still pass

---

## Milestone 6 Verification

### Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `make test-unit`
- [ ] E2E test passes (above)
- [ ] All previous milestone E2E tests still pass
- [ ] Quality gates pass: `make quality`
- [ ] No regressions introduced
- [ ] Documentation complete and accurate

---

## Feature Complete

After M6, the parallel coding workflow is complete:

- **Agent Deck** (M0): External session management researched
- **kinfra CLI** (M1): New infrastructure CLI established
- **Spec Workflow** (M2): Quick worktrees for design work
- **Slot Pool** (M3): Pre-provisioned sandbox infrastructure
- **Impl Workflow** (M4): Worktrees with claimed sandboxes
- **Done Workflow** (M5): Clean resource release
- **Polish** (M6): Aliases and documentation

Users can now run 3-5 parallel implementation streams with minimal overhead.
