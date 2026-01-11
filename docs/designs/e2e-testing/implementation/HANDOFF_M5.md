# Handoff: Milestone 5 - Designer Agent

## Task 5.1 Complete: e2e-test-designer Agent Definition

**File:** `.claude/agents/e2e-test-designer.md`

### Key Patterns

Agent follows same structure as e2e-tester.md:
- Frontmatter with name, description, tools, model, color
- Role section with DO/DO NOT lists
- Input/Output formats from VALIDATION.md
- Process steps
- Examples

### Input/Output Contracts

Input format (from /kdesign-impl-plan):
```markdown
## E2E Test Design Request
**Milestone:** [name]
**Capability:** [what user can do]
**Validation Requirements:** [numbered list]
**Components Involved:** [list]
**Intent:** [free-form]
**Expectations:** [free-form]
```

Output format:
1. Existing Tests That Apply (table)
2. Additional Validation Needed (gaps, proposed checks)
3. New Test Required (if needed: name, purpose, building blocks, structure)

### Matching Heuristics

Three lookup tables in agent definition:
- By Component (TrainingService -> training/*)
- By Capability ("X works" -> */smoke)
- By Keywords ("training" -> training/*)

### For Task 5.2

Task 5.2 updates SKILL.md to reference the designer agent. Key changes:
- Update agents table to add e2e-test-designer row
- Add "How Tests Are Designed" section explaining the design flow
