# Test: cli/kinfra-spec-workflow

**Purpose:** Validate the kinfra spec command creates properly configured worktrees for feature specifications with correct branch and design folder structure

**Duration:** <30 seconds

**Category:** CLI / Infrastructure

---

## Pre-Flight Checks

**Required modules:**
- None (this test validates CLI and git operations, not running services)

**Test-specific checks:**
- [ ] uv is available in PATH
- [ ] Current directory is KTRDR repository root
- [ ] git is available and repository is valid
- [ ] Parent directory is writable (worktrees created there)
- [ ] No existing worktree with test feature name

---

## Test Data

```yaml
# Unique feature name to avoid conflicts
feature_name: "e2e-test-spec-$(date +%s)"  # timestamp suffix
# Expected paths (relative to repo root)
worktree_path: "../ktrdr-spec-${feature_name}"
branch_name: "spec/${feature_name}"
design_dir: "${worktree_path}/docs/designs/${feature_name}"
```

**Why this data:**
- Timestamp suffix ensures unique feature name per test run
- Avoids conflicts with existing worktrees or branches
- Paths follow documented conventions from ARCHITECTURE.md

---

## Execution Steps

| Step | Action | Expected Result | Evidence to Capture |
|------|--------|-----------------|---------------------|
| 1 | Pre-check: verify no existing test worktree | Clean state | ls exit code |
| 2 | Run `kinfra spec <feature>` | Success message, exit 0 | command output, exit code |
| 3 | Verify worktree directory exists | Directory at `../ktrdr-spec-<feature>/` | ls exit code |
| 4 | Verify design folder exists | Directory at `docs/designs/<feature>/` | ls exit code |
| 5 | Verify branch exists | Branch `spec/<feature>` in git | git branch output |
| 6 | Run `kinfra worktrees` | Table shows new worktree | command output |
| 7 | Test idempotency: run spec again | Error (worktree exists), exit 1 | command output, exit code |
| 8 | Cleanup: remove worktree and branch | Clean removal | exit codes |

---

## Detailed Steps

### Step 1: Pre-Check and Setup

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Generate unique feature name
FEATURE_NAME="e2e-test-spec-$(date +%s)"
WORKTREE_PATH="../ktrdr-spec-${FEATURE_NAME}"

echo "Feature name: $FEATURE_NAME"
echo "Worktree path: $WORKTREE_PATH"

# Verify clean state
if [ -d "$WORKTREE_PATH" ]; then
  echo "FAIL: Worktree already exists at $WORKTREE_PATH"
  exit 1
fi

if git branch --list "spec/${FEATURE_NAME}" | grep -q .; then
  echo "FAIL: Branch spec/${FEATURE_NAME} already exists"
  exit 1
fi

echo "PASS: Clean state verified"
```

**Expected:**
- No existing worktree at target path
- No existing branch with test name
- Exit code 0

**Capture:** Feature name, worktree path, verification output

---

### Step 2: Create Spec Worktree

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Use the same feature name from step 1
# (In practice, tester maintains state across steps)

OUTPUT=$(uv run kinfra spec "$FEATURE_NAME" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: kinfra spec command failed"
  exit 1
fi

# Verify success message format
if echo "$OUTPUT" | grep -q "Created spec worktree"; then
  echo "PASS: Success message present"
else
  echo "FAIL: Expected 'Created spec worktree' in output"
  exit 1
fi

if echo "$OUTPUT" | grep -q "Design folder"; then
  echo "PASS: Design folder message present"
else
  echo "FAIL: Expected 'Design folder' in output"
  exit 1
fi
```

**Expected:**
- Exit code 0
- Output contains "Created spec worktree at ..."
- Output contains "Design folder: ..."

**Capture:** Full command output, exit code

---

### Step 3: Verify Worktree Directory Exists

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-spec-${FEATURE_NAME}"

if [ -d "$WORKTREE_PATH" ]; then
  echo "PASS: Worktree directory exists at $WORKTREE_PATH"
  ls -la "$WORKTREE_PATH" | head -10
else
  echo "FAIL: Worktree directory not found at $WORKTREE_PATH"
  exit 1
fi

# Verify it's a valid git worktree
if [ -f "$WORKTREE_PATH/.git" ]; then
  echo "PASS: .git file exists (worktree marker)"
  cat "$WORKTREE_PATH/.git"
else
  echo "FAIL: No .git file - not a valid worktree"
  exit 1
fi
```

**Expected:**
- Directory exists at `../ktrdr-spec-<feature>/`
- Directory contains `.git` file (worktree marker, not directory)
- Directory contains expected KTRDR files

**Capture:** Directory listing, .git file content

---

### Step 4: Verify Design Folder Exists

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

DESIGN_DIR="../ktrdr-spec-${FEATURE_NAME}/docs/designs/${FEATURE_NAME}"

if [ -d "$DESIGN_DIR" ]; then
  echo "PASS: Design folder exists at $DESIGN_DIR"
  ls -la "$DESIGN_DIR"
else
  echo "FAIL: Design folder not found at $DESIGN_DIR"
  echo "Checking parent directories..."
  ls -la "../ktrdr-spec-${FEATURE_NAME}/docs/" 2>/dev/null || echo "No docs folder"
  ls -la "../ktrdr-spec-${FEATURE_NAME}/docs/designs/" 2>/dev/null || echo "No designs folder"
  exit 1
fi
```

**Expected:**
- Directory exists at `docs/designs/<feature>/` within worktree
- Directory is empty (ready for design documents)

**Capture:** Directory listing

---

### Step 5: Verify Branch Exists

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

BRANCH_NAME="spec/${FEATURE_NAME}"

# Check branch exists
BRANCH_OUTPUT=$(git branch --list "$BRANCH_NAME")
if [ -n "$BRANCH_OUTPUT" ]; then
  echo "PASS: Branch $BRANCH_NAME exists"
  echo "Branch output: $BRANCH_OUTPUT"
else
  echo "FAIL: Branch $BRANCH_NAME not found"
  echo "Listing all spec branches:"
  git branch --list "spec/*"
  exit 1
fi

# Verify worktree is on correct branch
WORKTREE_PATH="../ktrdr-spec-${FEATURE_NAME}"
CURRENT_BRANCH=$(git -C "$WORKTREE_PATH" branch --show-current)
if [ "$CURRENT_BRANCH" = "$BRANCH_NAME" ]; then
  echo "PASS: Worktree is on correct branch: $CURRENT_BRANCH"
else
  echo "FAIL: Worktree on wrong branch. Expected: $BRANCH_NAME, Got: $CURRENT_BRANCH"
  exit 1
fi
```

**Expected:**
- Branch `spec/<feature>` exists in repository
- Worktree is checked out to that branch

**Capture:** Branch listing, current branch in worktree

---

### Step 6: Verify kinfra worktrees Shows New Worktree

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

OUTPUT=$(uv run kinfra worktrees 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -ne 0 ]; then
  echo "FAIL: kinfra worktrees command failed"
  exit 1
fi

# Verify worktree appears in output
if echo "$OUTPUT" | grep -q "ktrdr-spec-${FEATURE_NAME}"; then
  echo "PASS: Worktree appears in list"
else
  echo "FAIL: Worktree not found in kinfra worktrees output"
  exit 1
fi

# Verify type is "spec"
if echo "$OUTPUT" | grep "ktrdr-spec-${FEATURE_NAME}" | grep -q "spec"; then
  echo "PASS: Worktree type is 'spec'"
else
  echo "WARNING: Could not verify worktree type"
fi

# Verify branch is shown
if echo "$OUTPUT" | grep -q "spec/${FEATURE_NAME}"; then
  echo "PASS: Branch name appears in list"
else
  echo "WARNING: Branch name not visible in output"
fi
```

**Expected:**
- Exit code 0
- Output contains worktree name `ktrdr-spec-<feature>`
- Output shows type as "spec"
- Output shows branch as `spec/<feature>`

**Capture:** Full worktrees output

---

### Step 7: Test Idempotency (Duplicate Creation Fails)

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

# Attempt to create same worktree again
OUTPUT=$(uv run kinfra spec "$FEATURE_NAME" 2>&1)
EXIT_CODE=$?

echo "$OUTPUT"
echo ""
echo "Exit code: $EXIT_CODE"

# Should fail with exit 1
if [ $EXIT_CODE -eq 1 ]; then
  echo "PASS: Duplicate creation correctly rejected (exit 1)"
else
  echo "FAIL: Expected exit code 1, got $EXIT_CODE"
  exit 1
fi

# Should have error message about existing worktree
if echo "$OUTPUT" | grep -qi "already exists"; then
  echo "PASS: Error message mentions existing worktree"
else
  echo "FAIL: Expected error message about existing worktree"
  exit 1
fi
```

**Expected:**
- Exit code 1 (failure)
- Error message indicates worktree already exists
- Original worktree unchanged

**Capture:** Error output, exit code

---

### Step 8: Cleanup

**Command:**
```bash
cd /Users/karl/Documents/dev/ktrdr--stream-b

WORKTREE_PATH="../ktrdr-spec-${FEATURE_NAME}"
BRANCH_NAME="spec/${FEATURE_NAME}"

# Remove worktree
echo "Removing worktree at $WORKTREE_PATH..."
git worktree remove "$WORKTREE_PATH" --force
WORKTREE_EXIT=$?

if [ $WORKTREE_EXIT -eq 0 ]; then
  echo "PASS: Worktree removed"
else
  echo "FAIL: Failed to remove worktree (exit $WORKTREE_EXIT)"
  # Try manual removal as fallback
  rm -rf "$WORKTREE_PATH"
  git worktree prune
fi

# Remove branch
echo "Removing branch $BRANCH_NAME..."
git branch -D "$BRANCH_NAME"
BRANCH_EXIT=$?

if [ $BRANCH_EXIT -eq 0 ]; then
  echo "PASS: Branch removed"
else
  echo "WARNING: Failed to remove branch (exit $BRANCH_EXIT)"
  # Branch might not exist if worktree removal cleaned it
fi

# Verify cleanup
if [ -d "$WORKTREE_PATH" ]; then
  echo "FAIL: Worktree directory still exists"
  exit 1
fi

if git branch --list "$BRANCH_NAME" | grep -q .; then
  echo "WARNING: Branch still exists (may need manual cleanup)"
fi

echo "PASS: Cleanup complete"
```

**Expected:**
- Worktree removed successfully
- Branch deleted successfully
- No residual files or branches

**Capture:** Cleanup exit codes

---

## Success Criteria

All must pass for test to pass:

- [ ] `uv run kinfra spec <feature>` exits 0 with success message
- [ ] Worktree directory created at `../ktrdr-spec-<feature>/`
- [ ] Worktree is valid git worktree (has .git file, not directory)
- [ ] Design folder created at `docs/designs/<feature>/` within worktree
- [ ] Branch `spec/<feature>` exists in repository
- [ ] Worktree is checked out to correct branch
- [ ] `uv run kinfra worktrees` shows new worktree with type "spec"
- [ ] Duplicate creation attempt fails with exit 1 and clear error
- [ ] Cleanup removes worktree and branch

---

## Sanity Checks

Catch false positives:

| Check | Threshold | Failure Indicates |
|-------|-----------|-------------------|
| Worktree has .git file (not dir) | Missing or wrong type | Not a real worktree, maybe copy |
| Branch refs/heads/spec/* | Not under spec/ | Wrong branch naming |
| Design dir inside worktree | Wrong parent path | Created in main repo instead |
| kinfra worktrees has columns | No table output | Rich formatting broken |
| Second spec call fails | Exit 0 on duplicate | Idempotency check missing |

---

## Failure Categorization

| Failure Type | Category | Suggested Action |
|--------------|----------|------------------|
| "command not found: kinfra" | CONFIGURATION | Run `uv sync` to install entry points |
| "No module named 'ktrdr.cli.kinfra'" | CODE_BUG | Check kinfra module structure |
| Worktree not created | CODE_BUG | Check subprocess git worktree call |
| Design folder not created | CODE_BUG | Check mkdir call in spec.py |
| Branch not found | CODE_BUG | Check git branch creation logic |
| Wrong branch name format | CODE_BUG | Check branch_name variable in spec.py |
| Worktree not in list | CODE_BUG | Check worktrees.py name pattern matching |
| Duplicate creation succeeds | CODE_BUG | Check exists check in spec.py |
| Permission denied on parent | ENVIRONMENT | Check filesystem permissions |
| Git error on worktree create | ENVIRONMENT | Check git version, repo state |

---

## Troubleshooting

**If "command not found: kinfra":**
- **Cause:** Entry point not installed after adding to pyproject.toml
- **Cure:** Run `uv sync` to reinstall package with new entry points

**If "fatal: not a git repository":**
- **Cause:** Running from wrong directory or .git corrupted
- **Cure:** Ensure running from KTRDR repo root with valid .git

**If "Permission denied" on worktree creation:**
- **Cause:** Parent directory not writable
- **Cure:** Check permissions on parent of repo root

**If worktree created but design folder missing:**
- **Cause:** mkdir call in spec.py failed silently
- **Cure:** Check spec.py design_dir.mkdir() call, check worktree permissions

**If branch exists but worktree creation fails:**
- **Cause:** Branch checked out elsewhere, or stale worktree reference
- **Cure:** Run `git worktree prune` then retry

**If kinfra worktrees doesn't show the worktree:**
- **Cause:** Name pattern not matching "ktrdr-spec-" prefix
- **Cure:** Check worktrees.py name detection logic, verify actual directory name

**If duplicate creation succeeds (should fail):**
- **Cause:** Exists check not working
- **Cure:** Check worktree_path.exists() logic in spec.py

---

## Cleanup

Cleanup is **critical** for this test. Always execute cleanup even if test fails.

**Automatic cleanup in Step 8:**
```bash
# Remove worktree
git worktree remove "../ktrdr-spec-${FEATURE_NAME}" --force

# Remove branch
git branch -D "spec/${FEATURE_NAME}"
```

**Manual cleanup if automatic fails:**
```bash
# Find and list all test worktrees
git worktree list | grep "ktrdr-spec-e2e-test"

# Remove specific worktree
rm -rf ../ktrdr-spec-e2e-test-*
git worktree prune

# Remove orphaned branches
git branch | grep "spec/e2e-test" | xargs -r git branch -D
```

---

## Evidence to Capture

- Feature name used (with timestamp)
- Full output of `kinfra spec` command
- Directory listing of created worktree
- Contents of .git file in worktree
- Directory listing of design folder
- Git branch listing showing spec/* branch
- Current branch in worktree
- Full output of `kinfra worktrees`
- Error output from duplicate creation attempt
- Cleanup command outputs
- All exit codes

---

## Notes for Implementation

**Key Files:**
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/spec.py` - spec command implementation
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/worktrees.py` - worktrees listing
- `/Users/karl/Documents/dev/ktrdr--stream-b/ktrdr/cli/kinfra/main.py` - CLI registration

**State Persistence:**
The tester must maintain the `$FEATURE_NAME` variable across all steps. This is typically done by:
1. Setting it in Step 1
2. Referencing it in all subsequent steps
3. Using it in cleanup

**Worktree Mechanics:**
- Git worktrees are lightweight checkouts in separate directories
- The `.git` file (not directory) points back to main repo's `.git/worktrees/<name>`
- Worktrees share the object database with the main repo
- Branches checked out in worktrees cannot be checked out elsewhere

**Branch Reuse:**
The spec command supports reusing existing branches. A follow-up test could verify:
1. Create spec worktree
2. Cleanup worktree but keep branch
3. Create spec worktree again - should reuse branch

**Parallel Execution:**
Using timestamp suffix ensures this test can run in parallel without conflicts. Each run gets a unique feature name.
