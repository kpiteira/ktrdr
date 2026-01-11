# Handoff: Milestone 5 - Designer Agent

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

### For Task 5.2

Task 5.2 updates SKILL.md to reference both agents:
- Update agents table to add e2e-test-designer and e2e-test-architect rows
- Add "How Tests Are Designed" section explaining the two-agent flow
