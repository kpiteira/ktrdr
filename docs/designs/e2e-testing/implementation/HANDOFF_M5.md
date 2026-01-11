# Handoff: Milestone 5 - Designer and Architect Agents

## Task 5.1 Complete: Two-Agent Test Design Architecture

**Files:**
- `.claude/agents/e2e-test-designer.md` (haiku - matching)
- `.claude/agents/e2e-test-architect.md` (opus - design)

### Architecture: Split by Cognitive Demand

```
/kdesign-impl-plan
    │
    ▼
e2e-test-designer (haiku) ─── Fast catalog lookup
    │
    ├── Match found → Return recommendation
    │
    └── No match → Structured handoff
                       │
                       ▼
               e2e-test-architect (opus) ─── Deep reasoning
                       │
                       ▼
               Detailed test specification
```

### Model Choice Rationale

| Agent | Model | Cognitive Task | Frequency |
|-------|-------|----------------|-----------|
| e2e-tester | sonnet | Execute & diagnose failures | Per test run |
| e2e-test-designer | haiku | Pattern match against catalog | Per milestone |
| e2e-test-architect | opus | Design new tests from scratch | Rare (catalog grows) |

**Key insight:** Designing new tests requires deep reasoning about:
- What behavior proves the feature works
- What false positives could occur
- What evidence enables debugging
- Edge cases and failure modes

This is genuinely hard - worth opus-level reasoning for quality.

### Gotchas

**Always add `permissionMode: bypassPermissions`** to agent frontmatter. Without this, agents may pause for permission prompts when reading files, breaking autonomous operation.

**Designer hands off, doesn't design.** When no match exists, designer produces a structured handoff for architect. It does NOT attempt to design the test itself.

### Input/Output Contracts

**Designer Input** (from /kdesign-impl-plan):
```markdown
## E2E Test Design Request
**Milestone:** [name]
**Capability:** [what user can do]
**Validation Requirements:** [numbered list]
**Components Involved:** [list]
**Intent:** [free-form]
**Expectations:** [free-form]
```

**Designer Output** (match found):
- Existing Tests That Apply (table)
- Coverage Notes
- Gaps Identified

**Designer Output** (no match - handoff to architect):
```markdown
### Architect Handoff Required

**Invoke e2e-test-architect with the following context:**
[structured handoff with all context]
```

**Architect Output** (new test specification):
- Complete test structure with steps
- Success criteria (specific, measurable)
- Sanity checks (catch false positives)
- Failure categorization guidance

### Matching Heuristics

Three lookup tables in designer agent:
- By Component (TrainingService -> training/*)
- By Capability ("X works" -> */smoke)
- By Keywords ("training" -> training/*)

---

## Task 5.2 Complete: SKILL.md Updated

**File:** `.claude/skills/e2e-testing/SKILL.md`

Updated with:
- Agents table now has all three agents with model column
- "How Tests Are Designed" section with diagram and rationale
- Troubleshooting section links to training.md

---

## Task 5.3 Complete: Verification Passed

All four scenarios verified:

| Scenario | Agent | Result |
|----------|-------|--------|
| Exact match ("training works") | designer | ✅ Found training/smoke, full coverage |
| Partial match ("progress tracking") | designer | ✅ Identified gap, produced handoff |
| No match ("hot-reload") | designer | ✅ No match, produced handoff |
| New test design | architect | ✅ Detailed spec with steps, sanity checks |

**Key observations:**
- Designer (haiku) is fast and produces clean handoffs
- Architect (opus) produces comprehensive specs including:
  - Detailed bash commands
  - Success criteria checklists
  - Sanity checks with thresholds
  - Failure categorization tables
  - Implementation notes

---

## M5 Milestone Complete

All tasks completed:
- [x] Task 5.1: e2e-test-designer agent (haiku)
- [x] Task 5.1: e2e-test-architect agent (opus)
- [x] Task 5.2: SKILL.md updated with both agents
- [x] Task 5.3: Verification passed for all scenarios

### For M6

M6 wires these agents into /kdesign-impl-plan:
1. Invoke designer during Step 4 (task expansion)
2. If designer returns handoff, invoke architect
3. Include test recommendations in milestone output
