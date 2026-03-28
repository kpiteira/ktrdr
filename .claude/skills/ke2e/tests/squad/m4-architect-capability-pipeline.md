# Test: squad/m4-architect-capability-pipeline

**Purpose:** Validate that the Architect agent performs structured gap analysis, writes to capability-gaps.md, creates GitHub issues for HIGH/CRITICAL gaps, and that resolved capabilities flow back into the squad's knowledge.

**Duration:** ~15-25 minutes (one dry-run cycle + issue verification)

**Category:** Squad / M4 Milestone Validation

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] `claude` CLI available on PATH
- [ ] `gh` CLI available and authenticated
- [ ] `.squad/` directory exists at repo root with `loop_runner.sh`
- [ ] `~/.ktrdr/shared/squad/` directory exists (shared outcomes)
- [ ] Knowledge base populated (experiments.md, components.md, frontiers.md have content)
- [ ] `capability-gaps.md` has structured GAP-NNN entries
- [ ] `build-queue.md` exists with table format
- [ ] GitHub labels `squad:architect` and `capability-gap` exist (or loop runner creates them)

**Pre-flight commands:**

```bash
# Verify claude CLI
which claude > /dev/null 2>&1 && echo "OK: claude CLI available" || { echo "FAIL: claude CLI not found"; exit 1; }

# Verify gh CLI
gh auth status > /dev/null 2>&1 && echo "OK: gh CLI authenticated" || { echo "FAIL: gh CLI not authenticated"; exit 1; }

# Verify loop runner
[ -x ".squad/loop_runner.sh" ] && echo "OK: loop_runner.sh exists and is executable" || { echo "FAIL: .squad/loop_runner.sh missing or not executable"; exit 1; }

# Verify shared squad directory
SHARED="$HOME/.ktrdr/shared/squad"
[ -d "$SHARED" ] && echo "OK: shared squad directory exists" || { echo "FAIL: ~/.ktrdr/shared/squad/ missing"; exit 1; }

# Verify knowledge base has content
[ -f "$SHARED/knowledge/components.md" ] && [ "$(wc -l < "$SHARED/knowledge/components.md")" -gt 10 ] && echo "OK: components.md has content" || { echo "FAIL: components.md empty or missing"; exit 1; }

# Verify capability-gaps.md has structured format
[ -f "$SHARED/roadmap/capability-gaps.md" ] && grep -q "GAP-" "$SHARED/roadmap/capability-gaps.md" && echo "OK: capability-gaps.md has GAP entries" || { echo "FAIL: capability-gaps.md missing or no GAP entries"; exit 1; }
```

---

## Execution Steps

### Phase 1: Record Pre-State

#### 1.1 Snapshot capability-gaps.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
GAPS_FILE="$SHARED/roadmap/capability-gaps.md"

PRE_GAP_COUNT=$(grep -c "^### GAP-" "$GAPS_FILE" 2>/dev/null || echo "0")
PRE_GAPS_HASH=$(md5 -q "$GAPS_FILE" 2>/dev/null || md5sum "$GAPS_FILE" | cut -d' ' -f1)

echo "PRE_GAP_COUNT=$PRE_GAP_COUNT"
echo "PRE_GAPS_HASH=$PRE_GAPS_HASH"
```

#### 1.2 Snapshot build-queue.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
BQ_FILE="$SHARED/roadmap/build-queue.md"

PRE_BQ_LINES=$(wc -l < "$BQ_FILE" 2>/dev/null || echo "0")
PRE_BQ_HASH=$(md5 -q "$BQ_FILE" 2>/dev/null || md5sum "$BQ_FILE" | cut -d' ' -f1)

echo "PRE_BQ_LINES=$PRE_BQ_LINES"
echo "PRE_BQ_HASH=$PRE_BQ_HASH"
```

#### 1.3 Count existing squad:architect issues

**Command:**
```bash
PRE_ISSUE_COUNT=$(gh issue list --label "squad:architect" --state all --json number -q 'length' 2>/dev/null || echo "0")
echo "PRE_ISSUE_COUNT=$PRE_ISSUE_COUNT"
```

---

### Phase 2: Run Dry-Run Cycle

Execute one dry-run cycle. The Architect participates during DESIGN phase (Phase 3b in coordinator) and should assess feasibility + write gaps to disk.

#### 2.1 Execute dry-run cycle

**Command:**
```bash
cd "$(git rev-parse --show-toplevel)"
.squad/loop_runner.sh --dry-run --max-cycles 1 2>&1
```

**Expected:**
- Exit code 0
- Output includes "Loop complete. Ran 1 iterations."
- Discussion log written to `logs/squad/cycle_*_discussion.md`

**Timeout:** 1500 seconds (25 minutes — full squad discussion with web searches)

---

### Phase 3: Post-State Verification

#### 3.1 Verify Architect produced feasibility verdict

**Command:**
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
LOG_DIR="$REPO_ROOT/logs/squad"
DISCUSSION_LOG=$(ls -t "$LOG_DIR"/cycle_*_discussion.md 2>/dev/null | head -1)

if [ -z "$DISCUSSION_LOG" ]; then
  echo "FAIL: No discussion log found"
  exit 1
fi

# Check for Architect's feasibility verdict
HAS_VERDICT=false
grep -Eqi "GO|MODIFY|BLOCKED|feasib|verdict" "$DISCUSSION_LOG" && HAS_VERDICT=true

if [ "$HAS_VERDICT" = true ]; then
  echo "OK: Discussion log contains feasibility verdict"
else
  echo "FAIL: No feasibility verdict found in discussion log"
  exit 1
fi
```

#### 3.2 Verify capability-gaps.md was accessed/updated

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
GAPS_FILE="$SHARED/roadmap/capability-gaps.md"

POST_GAP_COUNT=$(grep -c "^### GAP-" "$GAPS_FILE" 2>/dev/null || echo "0")
POST_GAPS_HASH=$(md5 -q "$GAPS_FILE" 2>/dev/null || md5sum "$GAPS_FILE" | cut -d' ' -f1)

echo "Post-cycle GAP entries: $POST_GAP_COUNT (was: $PRE_GAP_COUNT)"
echo "Gaps file hash: $POST_GAPS_HASH (was: $PRE_GAPS_HASH)"

# Verify the file still has valid structure
if grep -q "## OPEN Gaps" "$GAPS_FILE" && grep -q "GAP-" "$GAPS_FILE"; then
  echo "OK: capability-gaps.md has valid structure with GAP entries"
else
  echo "FAIL: capability-gaps.md lost structure"
  exit 1
fi
```

**Expected:**
- capability-gaps.md retains structure
- Gap count may increase if Architect identified new gaps (or stay same if GO verdict)

#### 3.3 Check for GitHub issue creation (if gaps were identified)

**Command:**
```bash
POST_ISSUE_COUNT=$(gh issue list --label "squad:architect" --state all --json number -q 'length' 2>/dev/null || echo "0")
echo "Post-cycle squad:architect issues: $POST_ISSUE_COUNT (was: $PRE_ISSUE_COUNT)"

if [ "$POST_ISSUE_COUNT" -gt "$PRE_ISSUE_COUNT" ]; then
  NEW_ISSUES=$((POST_ISSUE_COUNT - PRE_ISSUE_COUNT))
  echo "OK: $NEW_ISSUES new GitHub issue(s) created"

  # Show the newest issue
  gh issue list --label "squad:architect" --state open --json number,title --limit 1 -q '.[0] | "#\(.number): \(.title)"'

  # Verify issue has structured body
  NEWEST_NUM=$(gh issue list --label "squad:architect" --state open --json number --limit 1 -q '.[0].number')
  if [ -n "$NEWEST_NUM" ]; then
    BODY=$(gh issue view "$NEWEST_NUM" --json body -q '.body')
    HAS_STRUCTURE=false
    echo "$BODY" | grep -Eqi "integration.*point|success.*criteria|what.*needed|blocked.*hypothes" && HAS_STRUCTURE=true
    if [ "$HAS_STRUCTURE" = true ]; then
      echo "OK: Issue #$NEWEST_NUM has structured body with integration points/success criteria"
    else
      echo "WARN: Issue #$NEWEST_NUM body may not have full structure"
    fi
  fi
else
  echo "INFO: No new GitHub issues created — Architect may have given GO verdict"
  echo "INFO: This is acceptable if the experiment was feasible with current capabilities"
fi
```

**Expected:**
- If Architect's verdict was BLOCKED or MODIFY: at least 1 new issue created with structured body
- If GO: no new issues (which is correct behavior)

#### 3.4 Verify build-queue.md consistency

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
BQ_FILE="$SHARED/roadmap/build-queue.md"

POST_BQ_HASH=$(md5 -q "$BQ_FILE" 2>/dev/null || md5sum "$BQ_FILE" | cut -d' ' -f1)

if [ "$POST_BQ_HASH" != "$PRE_BQ_HASH" ]; then
  echo "OK: build-queue.md was updated"
else
  echo "INFO: build-queue.md unchanged (expected if GO verdict)"
fi

# Verify table structure is intact
if grep -q "Gap ID" "$BQ_FILE"; then
  echo "OK: build-queue.md retains table structure"
else
  echo "WARN: build-queue.md may have lost table structure"
fi
```

#### 3.5 Verify Architect's fallback experiment (if BLOCKED/MODIFY)

**Command:**
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
LOG_DIR="$REPO_ROOT/logs/squad"
DISCUSSION_LOG=$(ls -t "$LOG_DIR"/cycle_*_discussion.md 2>/dev/null | head -1)

# Check if Architect was BLOCKED or MODIFY
IS_BLOCKED=false
grep -Eqi "BLOCKED|MODIFY" "$DISCUSSION_LOG" && IS_BLOCKED=true

if [ "$IS_BLOCKED" = true ]; then
  # When BLOCKED/MODIFY, Architect should propose fallback
  HAS_FALLBACK=false
  grep -Eqi "fallback|alternative|workaround|approximat|instead.*use|can.*run.*with" "$DISCUSSION_LOG" && HAS_FALLBACK=true

  if [ "$HAS_FALLBACK" = true ]; then
    echo "OK: Architect proposed fallback when BLOCKED/MODIFY"
  else
    echo "WARN: Architect gave BLOCKED/MODIFY but no clear fallback found in log"
  fi
else
  echo "INFO: Architect gave GO verdict — no fallback needed"
fi
```

---

## Success Criteria

All must pass:

- [ ] Dry-run cycle completed (exit code 0, "Loop complete" in output)
- [ ] Discussion log contains feasibility verdict (GO/MODIFY/BLOCKED)
- [ ] capability-gaps.md retains valid structure with GAP entries after cycle
- [ ] build-queue.md retains table structure

Conditional (when BLOCKED/MODIFY):
- [ ] At least 1 new GitHub issue created with `squad:architect` label
- [ ] Issue has structured body (integration points, success criteria)
- [ ] Fallback experiment proposed

Soft checks (WARN, not FAIL):
- [ ] build-queue.md updated to reflect new gaps
- [ ] Architect history updated with cycle learnings

---

## Sanity Checks

| Check | What It Catches |
|-------|----------------|
| Feasibility verdict in discussion log | Architect was not invoked during DESIGN phase |
| capability-gaps.md structure preserved | Architect clobbered the file instead of updating |
| GitHub issue has structured body | Issue was created but without useful content |
| Build queue consistency | Gaps tracked but not in queue (or vice versa) |
| Fallback when BLOCKED | Architect blocks without alternatives, stalling the squad |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| loop_runner.sh fails to start | INFRASTRUCTURE | Check claude CLI, .squad/ directory, permissions |
| No feasibility verdict | ARCHITECT_NOT_INVOKED | Check coordinator skill Phase 3b template |
| capability-gaps.md clobbered | WRITE_ERROR | Architect used Write instead of Edit, overwriting existing content |
| No GitHub issue when BLOCKED | ISSUE_CREATION_FAILED | Check gh CLI auth, Bash tool availability for Architect |
| Issue missing structure | TEMPLATE_ISSUE | Architect charter issue template not followed |
| Labels don't exist | LABEL_SETUP_FAILED | ensure_squad_labels() failed in loop runner preflight |

---

## Simulated Capability Resolution (Phase 4 — Optional)

To test the full pipeline (gap → issue → capability → usage), after the dry-run cycle:

1. Close one of the newly created issues: `gh issue close <number>`
2. Run another dry-run cycle: `.squad/loop_runner.sh --dry-run --max-cycles 1`
3. Verify the cycle prompt mentions "Newly Resolved Capabilities"
4. Verify capability-gaps.md marks the gap as RESOLVED
5. Verify components.md is updated with the new capability

This is optional because it requires two consecutive cycles, but validates the full feedback loop.
