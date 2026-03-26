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
- [ ] Backend API responsive on port 8000

---

## Execution Steps

### Phase 1: Infrastructure Exists

All squad scaffolding files must be present.

#### 1.1 Verify All 8 Agent Charters

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

#### 1.2 Verify Knowledge Base Files

**Command:**
```bash
MISSING=""
for KB_FILE in experiments hypotheses components decisions frontiers synthesis; do
  FILE=".squad/knowledge/${KB_FILE}.md"
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
if grep -q "Pre-Squad: V1.5 Baseline" .squad/knowledge/experiments.md && \
   grep -q "Pre-Squad: Signal Model Evolution" .squad/knowledge/experiments.md; then
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
# Must have confirmed hypotheses (H_003 at minimum) and not be just a template
if grep -q "H_003" .squad/knowledge/hypotheses.md && \
   grep -q "CONFIRMED" .squad/knowledge/hypotheses.md; then
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
# Must have at least D1 through D7 (pre-squad decisions)
COUNT=$(grep -c "^## D[0-9]" .squad/knowledge/decisions.md)
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

### Phase 3: Training Operation Completed

Verify the Cycle 1 training operation completed via API.

#### 3.1 Verify Training Operation

**Command:**
```bash
TRAIN_OP="op_training_20260325_215822_1b2dd75b"
RESPONSE=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$TRAIN_OP")
STATUS=$(echo "$RESPONSE" | jq -r '.data.status')
EPOCHS=$(echo "$RESPONSE" | jq -r '.data.result_summary.training_metrics.total_epochs // .data.result_summary.epochs // empty')
VAL_ACC=$(echo "$RESPONSE" | jq -r '.data.result_summary.training_metrics.best_val_accuracy // .data.result_summary.best_val_accuracy // empty')

echo "Training op: status=$STATUS"

if [ "$STATUS" != "completed" ]; then
  echo "FAIL: Training operation status is '$STATUS', expected 'completed'"
  echo "Full response: $(echo $RESPONSE | jq .)"
  exit 1
fi

echo "OK: Training operation completed (epochs=$EPOCHS, val_accuracy=$VAL_ACC)"
```

**Expected:**
- `status: "completed"`
- epochs around 200
- val_accuracy around 0.601

---

### Phase 4: Backtest Operation Completed With Real Metrics

#### 4.1 Verify Backtest Operation

**Command:**
```bash
BT_OP="op_backtesting_20260326_014519_c77cc523"
RESPONSE=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BT_OP")
STATUS=$(echo "$RESPONSE" | jq -r '.data.status')
TOTAL_RETURN=$(echo "$RESPONSE" | jq -r '.data.result_summary.backtest_result.total_return // .data.result_summary.total_return // empty')
TOTAL_TRADES=$(echo "$RESPONSE" | jq -r '.data.result_summary.backtest_result.total_trades // .data.result_summary.total_trades // empty')

echo "Backtest op: status=$STATUS, return=$TOTAL_RETURN, trades=$TOTAL_TRADES"

if [ "$STATUS" != "completed" ]; then
  echo "FAIL: Backtest operation status is '$STATUS', expected 'completed'"
  echo "Full response: $(echo $RESPONSE | jq .)"
  exit 1
fi

echo "OK: Backtest operation completed (return=$TOTAL_RETURN, trades=$TOTAL_TRADES)"
```

**Expected:**
- `status: "completed"`
- `total_return` is a real number (negative is fine -- the point is it ran)
- `total_trades > 0` (proves real trading occurred)

---

### Phase 5: Knowledge Base Updated After Cycle 1

#### 5.1 Verify Cycle 1 Entry in experiments.md

**Command:**
```bash
if grep -q "Squad Cycle 1" .squad/knowledge/experiments.md; then
  echo "OK: experiments.md has Cycle 1 entry"
else
  echo "FAIL: experiments.md missing Cycle 1 entry"
  exit 1
fi
```

#### 5.2 Verify D8 and D9 in decisions.md

**Command:**
```bash
FAIL=""
grep -q "## D8" .squad/knowledge/decisions.md || FAIL="$FAIL D8"
grep -q "## D9" .squad/knowledge/decisions.md || FAIL="$FAIL D9"

if [ -n "$FAIL" ]; then
  echo "FAIL: decisions.md missing:$FAIL"
  exit 1
fi
echo "OK: decisions.md has D8 and D9 from Cycle 1"
```

#### 5.3 Verify Frontiers F1/F2/F3 in frontiers.md

**Command:**
```bash
FAIL=""
grep -q "### F1" .squad/knowledge/frontiers.md || FAIL="$FAIL F1"
grep -q "### F2" .squad/knowledge/frontiers.md || FAIL="$FAIL F2"
grep -q "### F3" .squad/knowledge/frontiers.md || FAIL="$FAIL F3"

if [ -n "$FAIL" ]; then
  echo "FAIL: frontiers.md missing:$FAIL"
  exit 1
fi
echo "OK: frontiers.md has F1, F2, F3 from Cycle 1"
```

#### 5.4 Verify Agent Histories Updated

**Command:**
```bash
UPDATED=0
for AGENT in director inventor quant engineer critic architect scout scribe; do
  HIST=".squad/agents/${AGENT}/history.md"
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

- [ ] All 8 agent charters exist
- [ ] All 6 knowledge base files exist
- [ ] Coordinator skill and executor script exist
- [ ] experiments.md has pre-squad history (V1.5 baseline + Signal Model Evolution)
- [ ] hypotheses.md has curated entries with confirmed hypotheses
- [ ] decisions.md has >= 7 pre-squad architectural decisions
- [ ] Training operation `op_training_20260325_215822_1b2dd75b` status = "completed"
- [ ] Backtest operation `op_backtesting_20260326_014519_c77cc523` status = "completed" with trades > 0
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
| Backtest total_trades > 0 | Backtest that ran but never traded (degenerate model) |
| Training val_accuracy < 0.99 | If 99%+ accuracy, likely data leakage or test bug |
| D8/D9 are new (not just D1-D7 renumbered) | Knowledge base not actually updated by Scribe |
| >= 3 agent histories updated | Cycle ran but Scribe skipped agent history updates |
| Confirmed hypotheses in hypotheses.md | Template with headers only, no curated content |

**Sanity check command:**
```bash
# Verify backtest had real trades (not zero)
BT_OP="op_backtesting_20260326_014519_c77cc523"
TRADES=$(curl -s "http://localhost:${KTRDR_API_PORT:-8000}/api/v1/operations/$BT_OP" | \
  jq -r '.data.result_summary.backtest_result.total_trades // .data.result_summary.total_trades // 0')
if [ "$TRADES" -eq 0 ] 2>/dev/null; then
  echo "SANITY FAIL: Backtest completed but produced 0 trades"
  exit 1
fi
echo "SANITY OK: Backtest produced $TRADES trades"
```

---

## Failure Categorization

| Failure | Category | Action |
|---------|----------|--------|
| Missing charter files | INCOMPLETE_SETUP | Run squad bootstrap again |
| Missing knowledge base files | INCOMPLETE_SETUP | Run squad bootstrap again |
| Empty knowledge base (no pre-squad history) | INCOMPLETE_SEED | Re-run knowledge base seeding step |
| Training op not found (404) | STALE_DATA | Operations may have been purged; re-run cycle |
| Training op failed | EXECUTION_FAILURE | Check training logs for root cause |
| Backtest op 0 trades | MODEL_QUALITY | Training produced degenerate model; check strategy |
| No Cycle 1 in experiments.md | SCRIBE_FAILURE | Scribe did not update knowledge base |
| Missing D8/D9 | SCRIBE_FAILURE | Scribe did not record new decisions |
| < 3 agent histories updated | SCRIBE_FAILURE | Scribe skipped agent history updates |

---

## Troubleshooting

**If training operation returns 404:**
- Operations are stored in the database; if sandbox was rebuilt, operations are lost
- Re-run the full squad cycle to regenerate

**If backtest shows 0 trades:**
- Check the strategy's confidence threshold -- too high means no signals pass
- Check the trained model's predictions -- may be predicting single class

**If knowledge base files exist but are empty/template-only:**
- The seeding step may have been skipped
- Verify pre-squad history was curated from prior experiment records
- Re-run the ORIENT phase which reads and seeds knowledge

**If agent histories are missing Cycle 1:**
- The LEARN phase (Scribe) may not have completed
- Check `.squad/loop/last-result.md` for cycle completion evidence

---

## Evidence to Capture

- Charter file count (8/8)
- Knowledge base file count (6/6)
- Training operation status + metrics (epochs, val_accuracy)
- Backtest operation status + metrics (total_return, total_trades)
- Cycle 1 presence in experiments.md (grep output)
- D8/D9 presence in decisions.md (grep output)
- F1/F2/F3 presence in frontiers.md (grep output)
- Agent history update count (N/8 with Cycle 1 content)
