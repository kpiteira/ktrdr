---
name: memory-reflection
description: Use after completing a task, debugging session, or research to capture learnings and context gaps for improving future efficiency. Generates structured reflections appended to .claude/context_reflections.md.
---

# Memory Reflection Skill

## Purpose

Capture learnings from a work session to improve future efficiency. This skill generates structured reflections about context gaps, patterns discovered, and recommendations for memory updates.

**When to use:** After completing a task, debugging session, research, or any substantial work where you encountered friction or rediscovered information.

**Output:** Appends reflection to `.claude/context_reflections.md`

---

## Reflection Process

After completing work, reflect on the session:

### 1. Context Gaps Encountered

What knowledge required multiple searches or re-discovery?

**Architectural Knowledge Gaps:**
- Information about how components interact that wasn't immediately available
- Design decisions that had to be traced through code
- Dependencies that weren't obvious

**Pattern Re-Discovery:**
- Existing patterns in the codebase that had to be found again
- Conventions that weren't documented or remembered

**Cross-Module Dependencies:**
- Connections between modules that weren't apparent
- Side effects or coupling that caused surprises

### 2. Memory Recommendations

Based on gaps encountered:

**Worth Remembering** (would save significant time):
- Architectural knowledge used repeatedly
- Patterns that span multiple files or modules
- Non-obvious dependencies or gotchas

**Not Worth Remembering** (easily re-discoverable):
- Things that can be found with a single grep
- Information that changes frequently
- Implementation details that are obvious from code

### 3. Efficiency Estimate

Rough assessment of impact:
- Searches that could have been avoided: ~N
- Files re-read from previous sessions: [list]
- Patterns re-discovered: N
- Time impact: minimal / moderate / significant

---

## Output Format

Append to `.claude/context_reflections.md` using this format:

```markdown
## Reflection: [Task/Session ID] - [Date YYYY-MM-DD]

### Context Gaps
- [Gap 1]: [What was missing and how it manifested]
- [Gap 2]: ...

### Memory Recommendations

**Create:**
- [Memory name]: [One sentence description]

**Update:**
- [Existing memory]: Add [specific info]

**Skip:**
- [Thing searched]: [Why not worth memorizing]

### Efficiency Estimate
- Avoidable searches: ~N
- Re-read files: [list key files]
- Time impact: [minimal/moderate/significant]

---
```

---

## When to Skip Reflection

Don't generate a reflection if:
- The session was trivial (quick question, small fix)
- No new patterns or gaps were encountered
- The work was entirely within well-understood areas

A reflection should capture *new* learnings, not repeat known information.

---

## Example Reflection

```markdown
## Reflection: Task 2.3 ConfigLoader - 2024-12-13

### Context Gaps
- OperationsService singleton pattern: Had to trace through 3 files to understand 
  how the singleton is initialized and accessed across workers
- WorkerRegistry capability matching: Searched twice to find how GPU vs CPU 
  workers are differentiated

### Memory Recommendations

**Create:**
- "OperationsService singleton": Initialized in api/dependencies.py, accessed via 
  get_operations_service(). Workers have their own instance.

**Update:**
- "Worker architecture": Add that capability matching uses WorkerType enum + 
  optional gpu flag

**Skip:**
- Config file locations: Easy to grep, changes with refactoring

### Efficiency Estimate
- Avoidable searches: ~4
- Re-read files: dependencies.py, worker_registry.py, backtest_worker.py
- Time impact: moderate

---
```

---

## Integration

After generating a reflection, mention:

> "Memory reflection appended to `.claude/context_reflections.md`."

The user can review accumulated reflections with `/analyze-context` to identify patterns worth adding to persistent memory.
