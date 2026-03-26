# Test: squad/m1-bootstrap-first-cycle

**Purpose:** Validate the research squad M1 milestone: all infrastructure exists, knowledge base seeded with pre-squad history, first full cycle (ORIENT through LEARN) completed with real training and backtest operations, and knowledge base updated with Cycle 1 findings.

**Duration:** ~60 seconds (file checks + API queries, no operations triggered)

**Category:** Squad / Milestone Validation

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md) -- Docker, sandbox, API health

**Test-specific checks:**
- [ ] `.squad/` directory exists at repo root
- [ ] `~/.ktrdr/shared/squad/` directory exists (shared outcomes)
- [ ] Backend API responsive on port 8000

---

## Execution Steps

### Phase 1: Infrastructure Exists

All squad scaffolding files must be present.

#### 1.1 Verify All 8 Agent Charters (repo)

**Command:**
```bash
MISSING=""
for AGENT in director inventor quant engineer critic architect scout scribe; do
  FILE=".squad/agents/${AGENT}/charter.md"
  if [ ! -f "$FILE" ]; then
    MISSING="$MISSING $AGENT"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing charters:$MISSING"
  exit 1
fi
echo "OK: All 8 agent charters present"
```

**Expected:**
- Output: "OK: All 8 agent charters present"
- Exit code: 0

#### 1.2 Verify Knowledge Base Files (shared space)

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
MISSING=""
for KB_FILE in experiments hypotheses components decisions frontiers synthesis; do
  FILE="$SHARED/knowledge/${KB_FILE}.md"
  if [ ! -f "$FILE" ]; then
    MISSING="$MISSING $KB_FILE"
  fi
done

if [ -n "$MISSING" ]; then
  echo "FAIL: Missing knowledge base files:$MISSING"
  exit 1
fi
echo "OK: All 6 knowledge base files present"
```

**Expected:**
- Output: "OK: All 6 knowledge base files present"
- Exit code: 0

#### 1.3 Verify Coordinator Skill and Executor

**Command:**
```bash
FAIL=""
[ ! -f ".claude/skills/squad-coordinator/SKILL.md" ] && FAIL="$FAIL coordinator-skill"
[ ! -f ".squad/executor.sh" ] && FAIL="$FAIL executor"

if [ -n "$FAIL" ]; then
  echo "FAIL: Missing:$FAIL"
  exit 1
fi
echo "OK: Coordinator skill and executor present"
```

**Expected:**
- Output: "OK: Coordinator skill and executor present"
- Exit code: 0

---

### Phase 2: Knowledge Base Seeded With Pre-Squad History

The knowledge base must contain curated historical entries, not just empty templates.

#### 2.1 Verify experiments.md Has Pre-Squad History

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
if grep -q "Pre-Squad: V1.5 Baseline" "$SHARED/knowledge/experiments.md" && \
   grep -q "Pre-Squad: Signal Model Evolution" "$SHARED/knowledge/experiments.md"; then
  echo "OK: experiments.md has pre-squad history sections"
else
  echo "FAIL: experiments.md missing pre-squad history entries"
  exit 1
fi
```

**Expected:**
- Output: "OK: experiments.md has pre-squad history sections"

#### 2.2 Verify hypotheses.md Has Curated Entries

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
if grep -q "H_003" "$SHARED/knowledge/hypotheses.md" && \
   grep -q "CONFIRMED" "$SHARED/knowledge/hypotheses.md"; then
  echo "OK: hypotheses.md has curated entries with confirmed hypotheses"
else
  echo "FAIL: hypotheses.md missing curated hypothesis entries"
  exit 1
fi
```

**Expected:**
- Output: "OK: hypotheses.md has curated entries with confirmed hypotheses"

#### 2.3 Verify decisions.md Has Architectural Decisions

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
COUNT=$(grep -c "^## D[0-9]" "$SHARED/knowledge/decisions.md")
if [ "$COUNT" -ge 7 ]; then
  echo "OK: decisions.md has $COUNT architectural decisions (>= 7 pre-squad)"
else
  echo "FAIL: decisions.md has only $COUNT decisions (expected >= 7 pre-squad)"
  exit 1
fi
```

**Expected:**
- Output: "OK: decisions.md has N architectural decisions (>= 7 pre-squad)"

---

### Phase 3: Training Operation Completed (non-blocking)

Verify the Cycle 1 training operation if the sandbox database still has it.

#### 3.1 Verify Training Operation

**Command:**
```bash
TRAIN_OP="op_training_20260325_215822_1b2dd75b"
RESPONSE=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TRAIN_OP")
SUCCESS=$(echo "$RESPONSE" | jq -r '.success // false')

if [ "$SUCCESS" != "true" ]; then
  echo "SKIP: Training operation $TRAIN_OP not found (sandbox may have been rebuilt)"
  echo "INFO: Verify via knowledge base instead — experiments.md should have Cycle 1 results"
else
  STATUS=$(echo "$RESPONSE" | jq -r '.data.status')
  VAL_ACC=$(echo "$RESPONSE" | jq -r '.data.result_summary.training_metrics.best_val_accuracy // .data.result_summary.metrics.best_val_accuracy // "unknown"')
  echo "Training op: status=$STATUS, val_accuracy=$VAL_ACC"

  if [ "$STATUS" != "completed" ]; then
    echo "FAIL: Training operation status is '$STATUS', expected 'completed'"
    exit 1
  fi
  echo "OK: Training operation completed (val_accuracy=$VAL_ACC)"
fi
```

**Expected:**
- `status: "completed"` with val_accuracy ~0.601, OR "SKIP" if sandbox rebuilt

---

### Phase 4: Backtest Operation Completed (non-blocking)

#### 4.1 Verify Backtest Operation

**Command:**
```bash
BT_OP="op_backtesting_20260326_014519_c77cc523"
RESPONSE=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BT_OP")
SUCCESS=$(echo "$RESPONSE" | jq -r '.success // false')

if [ "$SUCCESS" != "true" ]; then
  echo "SKIP: Backtest operation $BT_OP not found (sandbox may have been rebuilt)"
  echo "INFO: Verify via knowledge base instead — experiments.md should have Cycle 1 metrics"
else
  STATUS=$(echo "$RESPONSE" | jq -r '.data.status')
  TRADES=$(echo "$RESPONSE" | jq -r '.data.result_summary.metrics.total_trades // .data.result_summary.total_trades // 0')
  echo "Backtest op: status=$STATUS, trades=$TRADES"

  if [ "$STATUS" != "completed" ]; then
    echo "FAIL: Backtest operation status is '$STATUS', expected 'completed'"
    exit 1
  fi
  if [ "$TRADES" -eq 0 ] 2>/dev/null; then
    echo "FAIL: Backtest completed but produced 0 trades (degenerate model)"
    exit 1
  fi
  echo "OK: Backtest operation completed (trades=$TRADES)"
fi
```

**Expected:**
- `status: "completed"` with trades > 0, OR "SKIP" if sandbox rebuilt

---

### Phase 5: Knowledge Base Updated After Cycle 1

#### 5.1 Verify Cycle 1 Entry in experiments.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
if grep -q "Squad Cycle 1" "$SHARED/knowledge/experiments.md"; then
  echo "OK: experiments.md has Cycle 1 entry"
else
  echo "FAIL: experiments.md missing Cycle 1 entry"
  exit 1
fi
```

#### 5.2 Verify D8 and D9 in decisions.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
FAIL=""
grep -q "## D8" "$SHARED/knowledge/decisions.md" || FAIL="$FAIL D8"
grep -q "## D9" "$SHARED/knowledge/decisions.md" || FAIL="$FAIL D9"

if [ -n "$FAIL" ]; then
  echo "FAIL: decisions.md missing:$FAIL"
  exit 1
fi
echo "OK: decisions.md has D8 and D9 from Cycle 1"
```

#### 5.3 Verify Frontiers F1/F2/F3 in frontiers.md

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
FAIL=""
grep -q "### F1" "$SHARED/knowledge/frontiers.md" || FAIL="$FAIL F1"
grep -q "### F2" "$SHARED/knowledge/frontiers.md" || FAIL="$FAIL F2"
grep -q "### F3" "$SHARED/knowledge/frontiers.md" || FAIL="$FAIL F3"

if [ -n "$FAIL" ]; then
  echo "FAIL: frontiers.md missing:$FAIL"
  exit 1
fi
echo "OK: frontiers.md has F1, F2, F3 from Cycle 1"
```

#### 5.4 Verify Agent Histories Updated

**Command:**
```bash
SHARED="$HOME/.ktrdr/shared/squad"
UPDATED=0
for AGENT in director inventor quant engineer critic architect scout scribe; do
  HIST="$SHARED/agents/${AGENT}/history.md"
  if [ -f "$HIST" ] && grep -q "Cycle 1" "$HIST"; then
    UPDATED=$((UPDATED + 1))
  fi
done

echo "Agent histories with Cycle 1 content: $UPDATED/8"

if [ "$UPDATED" -lt 3 ]; then
  echo "FAIL: Only $UPDATED agents have Cycle 1 history (expected >= 3)"
  exit 1
fi
echo "OK: $UPDATED agent histories updated with Cycle 1 content"
```

**Expected:**
- At least 3 agents (director, inventor, critic at minimum) have Cycle 1 entries

---

## Success Criteria

All must pass:

- [ ] All 8 agent charters exist (repo: `.squad/agents/*/charter.md`)
- [ ] All 6 knowledge base files exist (shared: `~/.ktrdr/shared/squad/knowledge/`)
- [ ] Coordinator skill and executor script exist
- [ ] experiments.md has pre-squad history (V1.5 baseline + Signal Model Evolution)
- [ ] hypotheses.md has curated entries with confirmed hypotheses
- [ ] decisions.md has >= 7 pre-squad architectural decisions
- [ ] Training operation completed OR skipped (sandbox rebuilt)
- [ ] Backtest operation completed with trades > 0 OR skipped (sandbox rebuilt)
- [ ] experiments.md has "Squad Cycle 1" entry
- [ ] decisions.md has D8 and D9
- [ ] frontiers.md has F1, F2, F3
- [ ] At least 3 agent histories contain Cycle 1 content

---

## Sanity Checks

**CRITICAL:** These catch false positives

| Check | What It Catches |
|-------|----------------|
| Pre-squad history exists in experiments.md | Empty template file passed off as "seeded" |
| Backtest total_trades > 0 (when available) | Backtest that ran but never traded (degenerate model) |
| Training val_accuracy < 0.99 (when available) | If 99%+ accuracy, likely data leakage or test bug |
| D8/D9 are new (not just D1-D7 renumbered) | Knowledge base not actually updated by Scribe |
| >= 3 agent histories updated | Cycle ran but Scribe skipped agent history updates |
| Confirmed hypotheses in hypotheses.md | Template with headers only, no curated content |

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| Missing charter files | INCOMPLETE_SETUP | Run squad bootstrap again |
| Missing knowledge base files | INCOMPLETE_SETUP | Check `~/.ktrdr/shared/squad/` was populated |
| Empty knowledge base (no pre-squad history) | INCOMPLETE_SEED | Re-run knowledge base seeding step |
| Training op not found (404) | STALE_DATA | Non-blocking; verify via knowledge base instead |
| Training op failed | EXECUTION_FAILURE | Check training logs for root cause |
| Backtest op 0 trades | MODEL_QUALITY | Training produced degenerate model; check strategy |
| No Cycle 1 in experiments.md | SCRIBE_FAILURE | Scribe did not update knowledge base |
| Missing D8/D9 | SCRIBE_FAILURE | Scribe did not record new decisions |
| < 3 agent histories updated | SCRIBE_FAILURE | Scribe skipped agent history updates |

---

## Troubleshooting

**If training/backtest operations return 404:**
- Operations are stored in the database; if sandbox was rebuilt, operations are lost
- This is non-blocking — verify results via knowledge base files instead
- Re-run the full squad cycle to regenerate if needed

**If knowledge base files not found in shared space:**
- Check `~/.ktrdr/shared/squad/` exists
- Files may still be in repo `.squad/knowledge/` if migration wasn't run
- Move files: `mv .squad/knowledge/* ~/.ktrdr/shared/squad/knowledge/`

**If agent histories are missing Cycle 1:**
- The LEARN phase (Scribe) may not have completed
- Check `~/.ktrdr/shared/squad/loop/last-result.md` for cycle completion evidence

---

## Evidence to Capture

- Charter file count (8/8)
- Knowledge base file count (6/6)
- Training operation status + metrics (epochs, val_accuracy) — or SKIP reason
- Backtest operation status + metrics (total_return, total_trades) — or SKIP reason
- Cycle 1 presence in experiments.md (grep output)
- D8/D9 presence in decisions.md (grep output)
- F1/F2/F3 presence in frontiers.md (grep output)
- Agent history update count (N/8 with Cycle 1 content)
