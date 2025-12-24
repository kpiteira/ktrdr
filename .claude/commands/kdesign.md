# Design Generation Command

Generate design and architecture documents for a new feature or system change through collaborative exploration.

This command embodies our partnership values from CLAUDE.md — craftsmanship over completion, honesty over confidence, decisions made together.

---

## Command Usage

```
/kdesign feature: <description> [context: <relevant-docs>]
```

**Required:**
- `feature:` — What you're building (can be brief, we'll explore together)

**Optional:**
- `context:` — Existing docs, code references, or constraints to consider
- Additional reference materials as needed

---

## What This Produces

Two documents ready for validation:

1. **DESIGN.md** — The what and why
   - Problem statement and goals
   - User-facing behavior
   - Key decisions and trade-offs
   - Out of scope

2. **ARCHITECTURE.md** — The how
   - Component structure
   - Data flow
   - API contracts
   - State management
   - Error handling approach

---

## This is a Conversation, Not a Generator

The command produces drafts. The value comes from refining them together.

Claude will ask questions, propose options, and surface trade-offs. Karl brings domain knowledge, constraints, and preferences. The back-and-forth is how good designs emerge.

---

## Design Process

### Step 1: Understand the Problem

Before proposing solutions, Claude explores the problem space:

**Questions to answer:**
- What problem are we solving?
- Who experiences this problem?
- What does success look like?
- What's the current state?
- What constraints exist?

Claude asks clarifying questions. This isn't a checklist — it's a conversation to build shared understanding.

**Output:** Problem statement (2-3 sentences capturing the core issue)

---

**Pause: Problem Alignment**

Claude shares the problem statement and asks:

> "Here's my understanding of the problem:
> 
> [Problem statement]
> 
> Does this capture it? What am I missing or misunderstanding?"

---

### Step 2: Explore Solution Space

Before committing to a design, explore options:

**For each reasonable approach:**
- How would it work?
- What are the trade-offs?
- What does it make easy? Hard?
- What are the risks?

Claude proposes 2-3 approaches with trade-offs. Not every feature needs multiple options — simple features can have an obvious best approach.

---

**Pause: Approach Selection**

Claude presents options and asks:

> "Here are the approaches I see:
> 
> **Option A: [Name]**
> [Brief description]
> - Good: [benefits]
> - Concern: [drawbacks]
> 
> **Option B: [Name]**
> [Brief description]
> - Good: [benefits]
> - Concern: [drawbacks]
> 
> I'm leaning toward [X] because [reasoning]. What's your take?"

---

### Step 3: Draft Design Document

Based on the selected approach, Claude drafts the design doc:

```markdown
# [Feature Name]: Design

## Problem Statement

[2-3 sentences from Step 1]

## Goals

What we're trying to achieve:
- [Goal 1]
- [Goal 2]
- [Goal 3]

## Non-Goals (Out of Scope)

What we're explicitly not doing:
- [Non-goal 1]
- [Non-goal 2]

## User Experience

How users interact with this feature:

### [Scenario 1]
[Description of user flow]

### [Scenario 2]
[Description of user flow]

## Key Decisions

### [Decision 1]
**Choice:** [What we decided]
**Alternatives considered:** [Other options]
**Rationale:** [Why this choice]

### [Decision 2]
...

## Open Questions

Issues to resolve during validation or implementation:
- [Question 1]
- [Question 2]
```

---

**Pause: Design Review**

Claude shares the draft and asks:

> "Here's the design draft. Before we move to architecture:
> 
> 1. Do the goals capture what matters?
> 2. Are the non-goals right? Anything we should add or remove?
> 3. Do the user scenarios cover the important cases?
> 4. Any decisions you'd make differently?"

---

### Step 4: Draft Architecture Document

With the design settled, Claude drafts the architecture:

```markdown
# [Feature Name]: Architecture

## Overview

[1-2 paragraph summary of the technical approach]

## Components

### [Component 1]
**Responsibility:** [What it does]
**Location:** [File/module path]
**Dependencies:** [What it needs]

### [Component 2]
...

## Data Flow

[Description or diagram of how data moves through the system]

```
[ASCII diagram if helpful]
```

## API Contracts

### [Endpoint/Interface 1]
```
[Method] [Path]
Request: [shape]
Response: [shape]
Errors: [possible errors]
```

### [Endpoint/Interface 2]
...

## State Management

### [State 1]
**Where:** [Storage location]
**Shape:** [Data structure]
**Transitions:** [How it changes]

### [State 2]
...

## Error Handling

### [Error Category 1]
**When:** [Condition]
**Response:** [How system handles it]
**User experience:** [What user sees]

### [Error Category 2]
...

## Integration Points

How this feature connects to existing systems:
- [Integration 1]: [Description]
- [Integration 2]: [Description]

## Migration / Rollout

[If applicable: How we get from current state to new state]

## Verification Strategy

For each component, specify how its correctness will be verified beyond unit tests.
This prevents "components work in isolation but aren't connected" bugs.

### [Component 1]
**Type:** [Persistence | Wiring/DI | State Machine | Background | etc.]
**Unit Test Focus:** [What unit tests verify]
**Integration Test:** [What integration tests verify — wiring, DB persistence, etc.]
**Smoke Test:** [Quick manual verification command]

### [Component 2]
...
```

---

**Pause: Architecture Review**

Claude shares the draft and asks:

> "Here's the architecture draft. Before we finalize:
> 
> 1. Does the component breakdown make sense?
> 2. Any existing patterns I should align with?
> 3. Are there integration points I'm missing?
> 4. Any concerns about this approach?"

---

### Step 5: Finalize Documents

After incorporating feedback, Claude produces final versions of both documents.

**The documents should be:**
- Complete enough to validate (via `/kdesign-validate`)
- Clear about what's decided vs. open
- Honest about trade-offs and risks

---

## Output Files

Save documents to the appropriate location:

```
docs/designs/
  [feature-name]/
    DESIGN.md
    ARCHITECTURE.md
```

Or wherever your project organizes design docs.

---

## Principles

### Right-Sized Design

Not every feature needs extensive documentation:

- **Small change:** Maybe just a design doc, or even inline in the PR
- **Medium feature:** Design + architecture docs
- **Large system:** Extensive docs, possibly split by component

Match the documentation to the complexity.

### Decisions Over Description

Good design docs capture **why**, not just what:

- ❌ "The system uses a queue"
- ✅ "The system uses a queue because operations can take 30+ seconds and we don't want to block the API. We chose Redis over Postgres-based queues because..."

### Acknowledge Uncertainty

It's fine to have open questions. Better to name them than pretend certainty:

- "We'll need to determine the right batch size during implementation"
- "The error handling for [edge case] needs more thought"
- "This assumes [X] is true — need to verify"

### Design for Validation

The output should be ready for `/kdesign-validate`:

- Scenarios should be concrete enough to trace
- Components should be specific enough to identify gaps
- State transitions should be clear enough to verify

---

## When Design Isn't Needed

Skip formal design docs when:

- The change is small and obvious
- You're spiking to learn something
- The implementation will be faster than the design

It's okay to say "let's just build it and see."

---

## Next Steps

After design is complete:

```
/kdesign-validate design: DESIGN.md arch: ARCHITECTURE.md
```

This validates the design through scenario traces before implementation planning.
