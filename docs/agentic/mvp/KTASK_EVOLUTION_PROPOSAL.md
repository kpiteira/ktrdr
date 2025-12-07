# Proposed /ktask Evolution: Handoff Integration

## Core Principle

**Handoff captures implementation learnings that diverge from the plan.**

It is NOT:

- A task tracker (that's the plan)
- Process documentation (that's the command)
- File listings or test counts (observable from code)
- Anything that can be derived from reading the codebase

It IS:

- Gotchas that cost time to discover
- Workarounds that aren't obvious
- Patterns that emerged during implementation
- Decisions made that future implementers need to know

## Token/Context Balance

Before adding anything to handoff, ask: **"Would this save the next implementer significant time?"**

- ✅ "Test directories can't shadow package names" → Saves 30+ min debugging
- ✅ "Use service layer pattern for testability" → Architectural decision not in plan
- ❌ "59 tests passing" → Observable, not actionable
- ❌ "Run `make test-unit`" → Already in process commands
- ❌ "Task 0.3 completed" → Already in plan

## Proposed Changes to /ktask

### 1. Add to Research Phase (Section 3, Step 2)

After "Research Existing Codebase", add:

```markdown
6. **Check for Implementation Handoff**
   - Look for `HANDOFF_*.md` in the same directory as the implementation plan
   - If exists: Read and note critical gotchas and patterns
   - These are implementation learnings from previous tasks - avoid repeating mistakes
```

### 2. Add to Completion (Section 6)

Add before "Provide a brief summary":

```markdown
- **Update or Create Handoff Document**:
  - Location: Same directory as implementation plan, named `HANDOFF_<phase/feature>.md`
  - If doesn't exist: Create it
  - If exists: Add new learnings, remove outdated info

  **CRITICAL - Content Guidelines:**

  INCLUDE (only if saves significant time for next implementer):
  - Gotchas: Problems encountered + symptoms + solutions
  - Workarounds: Non-obvious solutions to technical constraints
  - Emergent patterns: Architectural decisions made during implementation
  - Configuration surprises: Setup that wasn't obvious from docs

  EXCLUDE (wastes tokens, doesn't help implementation):
  - Task completion status (in plan)
  - Process steps (in command)
  - Test counts or coverage numbers
  - File listings (observable from codebase)
  - Anything derivable from reading the code

  **Format:**
  ```markdown
  # [Phase/Feature]: Implementation Learnings

  > Purpose: Learnings that weren't anticipated by the plan.

  ## Critical Gotchas

  ### [Short title]
  **Problem**: What went wrong
  **Symptom**: How it manifested
  **Solution**: How to fix/avoid

  ## Emergent Patterns

  [Only patterns that affect how future tasks should be implemented]
  ```

  **Target size**: Under 100 lines. If longer, you're including too much.
```

## Example: Good vs Bad Content

**Good** (saves time):

```markdown
### Test Directory Shadows Package
**Problem**: `tests/unit/research_agents/` shadows `research_agents/` package
**Symptom**: `import research_agents` resolves to test dir, not package
**Solution**: Name test dir differently: `tests/unit/agent_tests/`
```

**Bad** (wastes tokens):

```markdown
## Completed Tasks
- Task 0.1: Database tables ✅
- Task 0.2: MCP tools ✅

## Test Summary
59 tests passing in 0.5s

## Files Created
- research_agents/services/invoker.py
- tests/unit/agent_tests/test_invoker.py
```

## Implementation

Edit `/Users/karl/.claude/commands/ktask.md`:

1. Section 3, Step 2: Add step 6 for handoff check
2. Section 6: Add handoff update with content guidelines

No new parameters needed - handoff location is derived from plan location.
