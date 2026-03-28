# Test: squad/m3-scout-external-research

**Purpose:** Validate that the Scout agent performs real web searches during a squad cycle, writes structured findings to external-insights.md, appends to bibliography.md, and that Scout findings are visible in the squad discussion output.

**Duration:** ~10-20 minutes (one dry-run cycle — discussion phases only, no training/backtest)

**Category:** Squad / M3 Milestone Validation

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] `claude` CLI available on PATH
- [ ] `.squad/` directory exists at repo root with `loop_runner.sh`
- [ ] `~/.ktrdr/shared/squad/` directory exists (shared outcomes)
- [ ] Knowledge base populated (at least `frontiers.md` has content — Scout needs frontiers to research)
- [ ] `.env.sandbox` exists (sandbox slot 1, port 8001)

**Pre-flight commands:**

```bash
# Verify claude CLI
which claude > /dev/null 2>&1 && echo "OK: claude CLI available" || { echo "FAIL: claude CLI not found"; exit 1; }

# Verify loop runner
[ -x ".squad/loop_runner.sh" ] && echo "OK: loop_runner.sh exists and is executable" || { echo "FAIL: .squad/loop_runner.sh missing or not executable"; exit 1; }

# Verify shared squad directory
[ -d "$HOME/.ktrdr/shared/squad" ] && echo "OK: shared squad directory exists" || { echo "FAIL: ~/.ktrdr/shared/squad/ missing"; exit 1; }

# Verify knowledge base has frontiers (Scout needs these to know what to research)
SHARED="$HOME/.ktrdr/shared/squad"
if [ -f "$SHARED/knowledge/frontiers.md" ] && [ "$(wc -l < "$SHARED/knowledge/frontiers.md")" -gt 5 ]; then
  echo "OK: frontiers.md has content for Scout to research"
else
  echo "FAIL: frontiers.md empty or missing — Scout needs frontiers to guide web searches"
  exit 1
fi
```

---

## Execution Steps

### Phase 1: Record Pre-State

Snapshot all Scout-owned files before the cycle runs. This establishes the baseline for measuring what changed.

#### 1.1 Snapshot external-insights.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
INSIGHTS_FILE="$SHARED/roadmap/external-insights.md"

if [ -f "$INSIGHTS_FILE" ]; then
  PRE_INSIGHTS_LINES=$(wc -l < "$INSIGHTS_FILE")
  PRE_INSIGHTS_HASH=$(md5 -q "$INSIGHTS_FILE" 2>/dev/null || md5sum "$INSIGHTS_FILE" | cut -d' ' -f1)
else
  PRE_INSIGHTS_LINES=0
  PRE_INSIGHTS_HASH="missing"
fi

echo "PRE_INSIGHTS_LINES=$PRE_INSIGHTS_LINES"
echo "PRE_INSIGHTS_HASH=$PRE_INSIGHTS_HASH"
```

**Expected:**
- Captures line count and hash. Likely 5 lines (template header only) or more if prior cycles ran.

#### 1.2 Snapshot bibliography.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
BIB_FILE="$SHARED/agents/scout/bibliography.md"

if [ -f "$BIB_FILE" ]; then
  PRE_BIB_LINES=$(wc -l < "$BIB_FILE")
  PRE_BIB_ENTRIES=$(grep -c "^|.*|.*|.*|$" "$BIB_FILE" 2>/dev/null || echo "0")
else
  PRE_BIB_LINES=0
  PRE_BIB_ENTRIES=0
fi

echo "PRE_BIB_LINES=$PRE_BIB_LINES"
echo "PRE_BIB_ENTRIES=$PRE_BIB_ENTRIES"
```

**Expected:**
- Captures line count and entry count. bibliography.md already has entries from Cycles 1 and 6.

#### 1.3 Snapshot reading-queue.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
RQ_FILE="$SHARED/agents/scout/reading-queue.md"

if [ -f "$RQ_FILE" ]; then
  PRE_RQ_HASH=$(md5 -q "$RQ_FILE" 2>/dev/null || md5sum "$RQ_FILE" | cut -d' ' -f1)
  PRE_RQ_LINES=$(wc -l < "$RQ_FILE")
else
  PRE_RQ_HASH="missing"
  PRE_RQ_LINES=0
fi

echo "PRE_RQ_HASH=$PRE_RQ_HASH"
echo "PRE_RQ_LINES=$PRE_RQ_LINES"
```

---

### Phase 2: Run Dry-Run Cycle

Execute one squad cycle with `--dry-run` to run the discussion phase (ORIENT, STRATEGIZE, DESIGN) without the expensive training/backtest step. This is sufficient because Scout participates during STRATEGIZE — the web search and insight writing happen during discussion, not execution.

#### 2.1 Execute dry-run cycle

**Command:**
```bash
cd "$(git rev-parse --show-toplevel)"
.squad/loop_runner.sh --dry-run --max-cycles 1 2>&1
```

**Expected:**
- Exit code 0
- Output includes "DRY RUN -- skipping training and backtest"
- Output includes "Loop complete. Ran 1 iterations."
- A discussion log is written to `logs/squad/cycle_*_discussion.md`

**Timeout:** 1200 seconds (20 minutes — Claude discussion can be lengthy with web searches)

**Notes:**
- The `--dry-run` flag causes the loop runner to skip Phase 2 (training) and Phase 3 (backtest) but still runs the full discussion phase where Scout performs web searches.
- The allowed tools include `WebSearch` and `WebFetch`, which is how Scout accesses external sources.

---

### Phase 3: Post-State Verification

#### 3.1 Verify external-insights.md has structured entries

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
INSIGHTS_FILE="$SHARED/roadmap/external-insights.md"

if [ ! -f "$INSIGHTS_FILE" ]; then
  echo "FAIL: external-insights.md does not exist"
  exit 1
fi

POST_INSIGHTS_LINES=$(wc -l < "$INSIGHTS_FILE")
echo "Post-cycle lines: $POST_INSIGHTS_LINES (was: $PRE_INSIGHTS_LINES)"

# Check for structured insight entries
# Scout charter specifies: source, relevance, key finding, quality rating
HAS_SOURCE=false
HAS_QUALITY=false
HAS_URL=false

grep -qi "source\|reference\|paper\|article" "$INSIGHTS_FILE" && HAS_SOURCE=true
grep -qi "quality\|rating\|HIGH\|MEDIUM\|LOW" "$INSIGHTS_FILE" && HAS_QUALITY=true
grep -qi "http\|https\|arxiv\|doi\|ssrn" "$INSIGHTS_FILE" && HAS_URL=true

echo "Has source references: $HAS_SOURCE"
echo "Has quality ratings: $HAS_QUALITY"
echo "Has URLs: $HAS_URL"

# Must have at least source references and quality ratings (charter requirement)
if [ "$HAS_SOURCE" = true ] && [ "$HAS_QUALITY" = true ]; then
  echo "OK: external-insights.md has structured entries with source and quality"
else
  echo "FAIL: external-insights.md missing structured content (source=$HAS_SOURCE, quality=$HAS_QUALITY)"
  exit 1
fi
```

**Expected:**
- external-insights.md has grown beyond the template header
- Contains source references and quality ratings per Scout charter

#### 3.2 Verify bibliography.md grew

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
BIB_FILE="$SHARED/agents/scout/bibliography.md"

POST_BIB_ENTRIES=$(grep -c "^|.*|.*|.*|$" "$BIB_FILE" 2>/dev/null || echo "0")
echo "Bibliography entries: $POST_BIB_ENTRIES (was: $PRE_BIB_ENTRIES)"

if [ "$POST_BIB_ENTRIES" -gt "$PRE_BIB_ENTRIES" ]; then
  NEW_ENTRIES=$((POST_BIB_ENTRIES - PRE_BIB_ENTRIES))
  echo "OK: bibliography.md grew by $NEW_ENTRIES entries"
else
  echo "FAIL: bibliography.md did not grow (pre=$PRE_BIB_ENTRIES, post=$POST_BIB_ENTRIES)"
  exit 1
fi
```

**Expected:**
- At least 1 new entry added to bibliography.md

#### 3.3 Verify reading-queue.md was updated

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
RQ_FILE="$SHARED/agents/scout/reading-queue.md"

if [ ! -f "$RQ_FILE" ]; then
  echo "WARN: reading-queue.md does not exist — Scout may not have found next topics"
  # Not a hard failure: reading queue is aspirational, not guaranteed
else
  POST_RQ_HASH=$(md5 -q "$RQ_FILE" 2>/dev/null || md5sum "$RQ_FILE" | cut -d' ' -f1)
  POST_RQ_LINES=$(wc -l < "$RQ_FILE")
  echo "Reading queue: $POST_RQ_LINES lines (was: $PRE_RQ_LINES)"

  if [ "$POST_RQ_HASH" != "$PRE_RQ_HASH" ]; then
    echo "OK: reading-queue.md was modified"
  else
    echo "WARN: reading-queue.md unchanged — Scout may not have queued next topics"
    # Soft warning, not hard failure
  fi
fi
```

**Expected:**
- reading-queue.md modified (WARN if unchanged — not a hard failure since reading queue is secondary)

#### 3.4 Verify discussion log contains web search evidence

**Command:**
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
LOG_DIR="$REPO_ROOT/logs/squad"

# Find the most recent discussion log
DISCUSSION_LOG=$(ls -t "$LOG_DIR"/cycle_*_discussion.md 2>/dev/null | head -1)

if [ -z "$DISCUSSION_LOG" ]; then
  echo "FAIL: No discussion log found in $LOG_DIR"
  exit 1
fi

echo "Discussion log: $DISCUSSION_LOG"
LOG_SIZE=$(wc -c < "$DISCUSSION_LOG")
echo "Log size: $LOG_SIZE bytes"

# Check for evidence of web search activity
# Claude's WebSearch/WebFetch tools leave traces in the output
HAS_SEARCH=false
HAS_URL=false
HAS_SCOUT=false

grep -qi "search\|searched\|web.*search\|WebSearch\|query" "$DISCUSSION_LOG" && HAS_SEARCH=true
grep -qi "http\|https\|arxiv\|doi\|ssrn\|scholar" "$DISCUSSION_LOG" && HAS_URL=true
grep -qi "scout\|Scout\|external.*research\|external.*insight\|bibliography" "$DISCUSSION_LOG" && HAS_SCOUT=true

echo "Has search evidence: $HAS_SEARCH"
echo "Has URLs: $HAS_URL"
echo "Has Scout references: $HAS_SCOUT"

if [ "$HAS_SEARCH" = true ] && [ "$HAS_URL" = true ] && [ "$HAS_SCOUT" = true ]; then
  echo "OK: Discussion log shows Scout performed web searches with URLs"
else
  echo "FAIL: Discussion log missing web search evidence (search=$HAS_SEARCH, urls=$HAS_URL, scout=$HAS_SCOUT)"
  exit 1
fi
```

**Expected:**
- Discussion log exists and contains search queries, URLs, and Scout references

#### 3.5 Verify Director/Inventor referenced Scout findings

**Command:**
```bash
REPO_ROOT="$(git rev-parse --show-toplevel)"
LOG_DIR="$REPO_ROOT/logs/squad"
DISCUSSION_LOG=$(ls -t "$LOG_DIR"/cycle_*_discussion.md 2>/dev/null | head -1)

if [ -z "$DISCUSSION_LOG" ]; then
  echo "FAIL: No discussion log found"
  exit 1
fi

# Look for evidence that other agents engaged with Scout's findings
# Director and Inventor speak after Scout in STRATEGIZE phase
CROSS_REF=false

# Check for phrases indicating other agents used Scout's input
grep -qi "scout.*found\|scout.*identified\|scout.*report\|scout.*research\|based on.*scout\|scout.*suggest\|external.*research.*suggest\|literature.*suggest\|paper.*suggest" "$DISCUSSION_LOG" && CROSS_REF=true

if [ "$CROSS_REF" = true ]; then
  echo "OK: Discussion log shows other agents referenced Scout findings"
else
  echo "WARN: Could not confirm other agents explicitly referenced Scout findings"
  echo "INFO: This is a soft check — the discussion may reference findings without naming 'Scout'"
  # Soft warning: cross-referencing is valuable but hard to assert deterministically
fi
```

**Expected:**
- Evidence that Director or Inventor referenced Scout's research (WARN if not found, since phrasing varies)

#### 3.6 Verify external-insights.md has at least one URL

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
INSIGHTS_FILE="$SHARED/roadmap/external-insights.md"

URL_COUNT=$(grep -cE "https?://" "$INSIGHTS_FILE" 2>/dev/null || echo "0")
echo "URLs in external-insights.md: $URL_COUNT"

if [ "$URL_COUNT" -ge 1 ]; then
  echo "OK: external-insights.md has $URL_COUNT source URL(s)"
  # Show first URL as evidence
  grep -m1 -oE "https?://[^ )\"']+" "$INSIGHTS_FILE" | head -1
else
  echo "FAIL: external-insights.md has no URLs — Scout may not have performed real web searches"
  exit 1
fi
```

**Expected:**
- At least 1 URL present in external-insights.md, proving real web search occurred

---

## Success Criteria

All must pass:

- [ ] Dry-run cycle completed (exit code 0, "Loop complete" in output)
- [ ] external-insights.md has structured entries with source references and quality ratings
- [ ] external-insights.md contains at least 1 source URL
- [ ] bibliography.md grew by at least 1 entry compared to pre-state
- [ ] Discussion log exists and shows web search evidence (search terms, URLs, Scout references)

Soft checks (WARN, not FAIL):

- [ ] reading-queue.md was modified
- [ ] Director/Inventor explicitly referenced Scout findings in discussion

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| URL present in external-insights.md | Scout wrote insights from memory/hallucination instead of actual web search |
| bibliography.md grew (not just unchanged) | Scout skipped bibliography updates despite charter requirement |
| Discussion log has search + URL + scout evidence | Cycle ran but Scout was not invoked during STRATEGIZE |
| external-insights.md has quality ratings | Scout dumped raw text instead of structured findings per charter format |
| Pre-state vs post-state comparison | Files already had content and Scout added nothing new |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| loop_runner.sh fails to start | INFRASTRUCTURE | Check claude CLI availability, .squad/ directory, permissions |
| Claude session fails during discussion | CLAUDE_FAILURE | Check `logs/squad/cycle_*` stderr log for error details |
| external-insights.md empty after cycle | SCOUT_NOT_INVOKED | Scout was skipped during STRATEGIZE — check coordinator skill |
| No URLs in external-insights.md | NO_WEB_SEARCH | WebSearch/WebFetch tools may not be available or Scout used cached knowledge |
| bibliography.md unchanged | SCOUT_WRITE_FAILURE | Scout ran but did not persist findings — check charter vs behavior |
| No discussion log found | LOG_FAILURE | loop_runner.sh may have failed before writing discussion output |
| Discussion log has no Scout references | SCOUT_ABSENT | Coordinator did not invoke Scout role — check squad-coordinator skill |

---

## Troubleshooting

**If Claude session fails:**
- Check `logs/squad/cycle_*` for stderr output
- Verify `claude` CLI is authenticated and has model access
- Verify allowed tools list includes `WebSearch` and `WebFetch`

**If external-insights.md is empty after cycle:**
- Check the discussion log (`logs/squad/cycle_*_discussion.md`) for Scout's contributions
- Scout may have contributed verbally but not written to disk — this is a charter violation
- Verify the coordinator prompt includes Scout file paths

**If bibliography.md did not grow:**
- Scout may have found no new sources (unlikely but possible)
- Check if Scout's output in the discussion log mentions sources that weren't persisted
- Compare discussion log content against bibliography.md

**If no URLs found:**
- Scout may have used general knowledge instead of performing web searches
- Check if `WebSearch` and `WebFetch` appear in the allowed tools for the Claude invocation
- The loop_runner.sh `--allowedTools` line should include both

**If dry-run takes more than 20 minutes:**
- Claude discussion with web searches can be lengthy
- Check `logs/squad/` for partial output
- The squad has 8 agents speaking during STRATEGIZE — each contributes

---

## Evidence to Capture

- Pre-state: external-insights.md line count + hash, bibliography.md entry count, reading-queue.md hash
- Post-state: same metrics after cycle
- Delta: number of new bibliography entries, new insight entries
- Discussion log path and size
- First URL found in external-insights.md (proof of real web search)
- Search terms found in discussion log (proof of active research)
- Cross-reference evidence (other agents using Scout findings)
