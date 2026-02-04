---
name: klandpr
description: Land a PR after milestone completion. Creates PR, requests reviews, addresses feedback, waits for CI, merges, and cleans up the worktree.
user_invocable: true
---

# klandpr - Land PR After Milestone Completion

Automates the full PR landing cycle after a milestone implementation is complete.

---

## Prerequisites

- Milestone implementation is complete (kmilestone has finished)
- You are in an impl worktree (e.g., `ktrdr-impl-genome-M1`)
- All changes are committed
- Local tests pass (`make test-unit && make quality`)

---

## Workflow

### Phase 0: Generate Milestone Report

Before starting the PR cycle, ensure the milestone report is visible. If kmilestone didn't output it (or it was lost to context compaction), generate it now.

**Steps:**

1. **Identify the handoff file:**
   ```bash
   # From current directory name, derive the handoff path
   # e.g., ktrdr-impl-genome-M1 → look for HANDOFF_M1.md
   # e.g., ktrdr-impl-cli-client-M1 → look for HANDOFF_M1.md
   MILESTONE=$(basename "$PWD" | sed 's/.*-//')
   find docs/designs -name "HANDOFF_${MILESTONE}.md" 2>/dev/null
   ```

2. **Read the handoff file** and extract:
   - All "Task X.Y Complete" sections
   - Any challenges/gotchas mentioned
   - E2E test results (look for "PASSED", "FAILED", test names)
   - Any test failures noted

3. **Output the report:**
   ```
   ## Milestone Report: <milestone>

   ### E2E Tests Performed

   | Test | Steps | Result |
   |------|-------|--------|
   | ... | ... | ... |

   ### Challenges & Solutions

   | Task | Challenge | Solution |
   |------|-----------|----------|
   | ... | ... | ... |

   ### Failed Tests (Not Due to This Work)

   | Test | Failure | Status |
   |------|---------|--------|
   | ... | ... | ... |

   (or "None" for each section if empty)
   ```

**Why this matters:** This report is essential for:
- PR description content
- Understanding what was validated
- Documenting learnings for future reference

---

### Phase 1: Create PR and Request Reviews

1. **Verify clean state:**
   ```bash
   git status
   make test-unit
   make quality
   ```
   If issues, fix them before proceeding.

2. **Create the PR:**
   ```bash
   gh pr create --base main --fill
   ```
   Use the milestone summary from kmilestone output for the PR description.

3. **Request Copilot review:**
   ```bash
   REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
   PR_NUMBER=$(gh pr view --json number -q '.number')
   gh api --method POST "repos/$REPO/pulls/$PR_NUMBER/requested_reviewers" \
     -f "reviewers[]=copilot-pull-request-reviewer[bot]"
   ```

4. **Request Claude review:**
   ```bash
   gh pr comment $PR_NUMBER --body "@claude review"
   ```

### Phase 2: Wait for Reviews (max 10 minutes)

Poll every 60 seconds for review comments:

```bash
REPO=$(gh repo view --json nameWithOwner -q '.nameWithOwner')
PR_NUMBER=$(gh pr view --json number -q '.number')

# Check for inline review comments (Copilot posts here)
INLINE_COMMENTS=$(gh api "repos/$REPO/pulls/$PR_NUMBER/comments" --jq 'length')

# Check for issue comments (Claude posts here)
ISSUE_COMMENTS=$(gh api "repos/$REPO/issues/$PR_NUMBER/comments" --jq 'length')
```

**Wait conditions:**
- Check every 60 seconds
- Maximum wait: 10 minutes (10 iterations)
- Consider reviews complete when:
  - Copilot: At least 1 inline comment exists, OR
  - Claude: Issue comment containing "review" from claude bot exists

**While waiting:** Output a countdown: "Waiting for reviews... (X/10)"

**If timeout:** Warn user and ask whether to proceed anyway or abort.

### Phase 3: Address Reviews

Invoke the address-review skill:

```
/address-review
```

This will:
- Fetch all review comments from both APIs
- Assess each critically
- Implement valuable suggestions
- Push back on low-value nitpicks
- Commit and push changes

### Phase 4: Ensure Tests Pass Locally

After addressing reviews:

```bash
make test-unit
make quality
```

**If failures:**
1. Analyze the failures
2. Fix the issues
3. Commit with message: "fix: address test failures after review"
4. Push changes
5. Re-run tests to verify

### Phase 5: Wait for CI

```bash
gh pr checks --watch
```

This blocks until all checks complete.

**If CI fails but local passes:**
1. Fetch the CI logs: `gh pr checks --json name,state,link`
2. Identify the failing check
3. Investigate the difference (environment, dependencies, timing)
4. Fix the issue
5. Push and wait again

**Common remote-only issues:**
- Missing environment variables in CI
- Timing/race conditions that don't reproduce locally
- Docker image differences
- Dependency version mismatches

### Phase 6: Merge

```bash
gh pr merge --squash --delete-branch
```

**Important:** This merges the PR on GitHub (not a local merge). The `--delete-branch` removes the remote branch after merge.

### Phase 7: Cleanup

Determine the worktree name from current directory and run cleanup:

```bash
# Extract worktree name from current path
# e.g., /path/to/ktrdr-impl-genome-M1 → genome-M1
WORKTREE_NAME=$(basename "$PWD" | sed 's/ktrdr-impl-//')

# Get session title (feature/milestone format)
# e.g., genome-M1 → genome/M1
# e.g., cli-client-M1 → cli-client/M1
SESSION_TITLE=$(echo "$WORKTREE_NAME" | sed 's/-\([^-]*\)$/\/\1/')

# Remove agent-deck session
agent-deck remove "$SESSION_TITLE"

# Clean up worktree and sandbox
# Note: We're IN the worktree, so cd out first
cd ..
uv run kinfra done "$WORKTREE_NAME" --force
```

**Note:** After cleanup, the terminal will be in the parent directory and the worktree will be deleted.

---

## Error Handling

| Situation | Action |
|-----------|--------|
| PR creation fails | Check for uncommitted changes, verify branch is pushed |
| Review request fails | Proceed anyway, reviews are nice-to-have |
| Review timeout | Ask user: proceed or abort? |
| address-review finds nothing | Continue to CI check |
| Local tests fail | Fix before proceeding |
| CI fails | Investigate and fix, loop until green |
| Merge conflict | Alert user, manual intervention needed |
| Worktree cleanup fails | Alert user, manual cleanup with `kinfra done --force` |

---

## Full Example

```
User: /klandpr

Claude: Starting PR landing cycle...

## Phase 0: Milestone Report

Reading handoff file: docs/designs/genome/implementation/HANDOFF_M1.md

### E2E Tests Performed

| Test | Steps | Result |
|------|-------|--------|
| training/full-training-cycle | 12 | PASSED |
| backtest/model-integration | 8 | PASSED |

### Challenges & Solutions

| Task | Challenge | Solution |
|------|-----------|----------|
| 1.2 | GPU memory exhaustion on large batches | Reduced batch size, added gradient checkpointing |
| 1.4 | Flaky test due to floating point precision | Used approx comparison with tolerance |

### Failed Tests (Not Due to This Work)

| Test | Failure | Status |
|------|---------|--------|
| test_data_loader::test_timeout | Intermittent timeout | Pre-existing flaky test |

---

## Phase 1: Verify and Create PR

Running pre-flight checks...
✓ git status: clean
✓ make test-unit: passed
✓ make quality: passed

Creating PR...
✓ PR #318 created: https://github.com/kpiteira/ktrdr2/pull/318

Requesting reviews...
✓ Copilot review requested
✓ Claude review requested (@claude review comment posted)

## Phase 2: Waiting for Reviews

Waiting for reviews... (1/10)
Waiting for reviews... (2/10)
Waiting for reviews... (3/10)
✓ Copilot review received (4 comments)
✓ Claude review received

## Phase 3: Addressing Reviews

[Invoking /address-review...]

## Review Assessment Summary

**PR**: #318
**Total comments**: 6

| # | Comment | Assessment | Action |
|---|---------|------------|--------|
| 1 | Add error handling for edge case | High value | IMPLEMENT |
| 2 | Rename variable | Nitpick | PUSH BACK |
| 3 | Add docstring | Self-documenting code | PUSH BACK |
| 4 | Fix potential race condition | High value | IMPLEMENT |
...

Implementing 2 changes...
✓ Changes committed and pushed

## Phase 4: Local Test Verification

Running make test-unit...
✓ All tests passed

Running make quality...
✓ Quality checks passed

## Phase 5: Waiting for CI

Watching PR checks...
✓ All checks passed

## Phase 6: Merging

Merging PR #318 with squash...
✓ PR merged successfully
✓ Remote branch deleted

## Phase 7: Cleanup

Removing agent-deck session "genome/M1"...
✓ Session removed

Running kinfra done genome-M1...
✓ Sandbox released
✓ Worktree removed

---

🎉 Milestone genome/M1 landed successfully!

PR: https://github.com/kpiteira/ktrdr2/pull/318
Merged to: main
```

---

## Notes

- This command assumes you're running from within the impl worktree
- The cleanup phase will terminate your current shell's working directory
- After completion, you'll be in the parent directory of the (now deleted) worktree
- If anything fails mid-process, you can re-run `/klandpr` to continue from where it left off (idempotent operations)