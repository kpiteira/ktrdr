# Analyze Context Optimization Data

You are analyzing accumulated context reflection data to identify patterns and make recommendations for improving agent efficiency.

## Instructions

1. **Read the reflections file**: `.claude/context_reflections.md`

2. **Analyze patterns** across all entries:
   - What knowledge gaps appear repeatedly?
   - What patterns keep getting re-discovered?
   - What cross-module dependencies cause confusion?
   - What items were marked "not worth memorizing"?

3. **Generate actionable recommendations**:

   ### High-Value Memories to Create
   Identify knowledge that:
   - Appears in 2+ reflections
   - Would save significant search time
   - Is not easily discoverable from code structure

   For each, provide:
   - Suggested memory name
   - Proposed content (brief)
   - Evidence from reflections

   ### Patterns to Document
   Identify recurring patterns that should be added to CLAUDE.md or architecture docs.

   ### Low-Value Items
   Confirm what's NOT worth memorizing (easily re-discoverable).

   ### Tooling Recommendations
   Based on the types of queries that caused friction:
   - Would semantic search (like Claude Context) help?
   - Are there specific query types Serena doesn't handle well?
   - Should we create custom slash commands for common lookups?

4. **Update experiment status**:
   - How many reflections analyzed?
   - Key findings summary
   - Recommended next actions

5. **Ask Karl** which recommendations to implement.

## Output Format

```markdown
# Context Optimization Analysis

**Reflections Analyzed**: X entries from [date range]

## Key Patterns Identified

### 1. [Pattern Name]
- **Frequency**: X occurrences
- **Impact**: [minimal/moderate/significant]
- **Evidence**: [quotes from reflections]

## Recommendations

### Create These Memories
1. **Memory: `<name>`**
   - Content: <proposed content>
   - Rationale: <why this helps>

### Update These Documents
1. **File**: <path>
   - Add: <what to add>

### Tooling Decisions
- Semantic search needed? [Yes/No] - Rationale: ...
- Custom commands to create? [list]

## Next Steps
- [ ] Recommended action 1
- [ ] Recommended action 2
```
