# Presentation: Trusting AI-Generated Code

**Duration:** ~45 minutes
**Audience:** PMs (primary), developers welcome
**Format:** Live demo with real work happening in parallel

## Core Thesis

Trust in AI-generated code isn't binary - it's built through layers of verification, clear collaboration contracts, and systematic quality gates. This presentation demonstrates those layers by actually building features during the talk.

---

## 1. Quick Context (2 min)

**Goal:** Set the stage - this is a complex project, not a toy.

- Brief intro: solo developer working on a distributed trading system
- Show the architecture diagram (see architecture.md)
- Frame the core question: *"How do you trust code you didn't write line-by-line?"*

**Key point:** The complexity justifies the process. This isn't over-engineering for a TODO app.

---

## 2. Let's Get to Work (3 min)

**Goal:** Kick off real work immediately - demonstrate trust through action.

### The Two Features

1. **CLI Restructure** (stream-a)
   - Real feature work
   - Restructuring the command architecture for better maintainability
   - Multiple milestones, substantial changes

2. **Sandbox Shell** (stream-b)
   - Infrastructure work
   - Adding a `ktrdr sandbox shell` command
   - Smaller scope, good for showing the full cycle

### Actions
- Explain each feature briefly (what and why)
- Run `ktask` on both streams
- Set expectation: "These will work while we talk. Let's see where they get."

**Key point:** I trust the system enough to let it work unsupervised during a live presentation.

---

## 3. Foundations: How We Work Together (5 min)

**Goal:** Show that CLAUDE.md is a collaboration contract, not just instructions.

### What to Show
- Open CLAUDE.md in VS Code
- Walk through key sections:
  - **Working Agreement**: uncertainty, trade-offs, disagreement, mistakes
  - **Anti-patterns**: the "quick fix" trap, recognizing "bad loops"
  - **Shared Values**: craftsmanship over completion, honesty over confidence

### Key Points
- Most people think about instructing AI on *what to build*
- Fewer think about *how to collaborate*
- The working agreement shapes behavior across all interactions

**File to show:** `CLAUDE.md` (sections: "How We Work Together", "Anti-Patterns to Avoid")

---

## 4. Specification: Clarity Before Code (8 min)

**Goal:** Show how structured specs prevent hallucination and scope creep.

### The Workflow
```
Feature Design → Architecture → Milestones → Tasks → Implementation
     ↓              ↓             ↓           ↓          ↓
  DESIGN.md    ARCHITECTURE.md  OVERVIEW.md  M*.md    ktask
```

### What to Show
- The spec work pane (right side of Zellij)
- Walk through an existing design: `docs/designs/cli-restructure/`
  - DESIGN.md - the what and why
  - ARCHITECTURE.md - technical decisions
  - implementation/OVERVIEW.md - milestone breakdown
  - implementation/M*.md - task details

### Key Points
- Specs are context for the AI, not just documentation for humans
- Structured format prevents drift and hallucination
- Tasks are atomic and independently executable

**Check-in:** Glance at how the two tasks are progressing.

---

## 5. Execution: Parallel Streams (8 min)

**Goal:** Show how multiple AI agents work simultaneously without conflict.

### The Zellij Setup
- Tab: "Coding" - two interactive coding sessions
- Tab: "Autonomous Agent" - fire-and-forget execution
- Tab: "Spec Work" - design and planning
- Each stream has its own sandbox/branch/context

### What to Show
- Switch between Zellij panes
- Show what each Claude has been doing while we talked
- Demonstrate how streams stay independent (different branches, different sandboxes)

### Key Points
- Parallel doesn't mean chaotic - clear boundaries keep things clean
- Interactive vs autonomous modes serve different purposes
- Context isolation prevents cross-contamination

---

## 6. Verification: Trust But Verify (10 min)

**Goal:** Show the quality gates that catch problems before they ship.

### Layers of Verification

1. **Sandbox Environments**
   - Isolated Docker environments with their own ports
   - AI can run E2E tests without affecting main environment
   - Show: `ktrdr sandbox status`, the sandbox architecture

2. **Automatic Quality Gates**
   - `make quality` - lint, format, typecheck
   - `make test-unit` - fast feedback loop
   - Pre-commit hooks catch issues before they're committed

3. **Skills/Prompts That Shape Output**
   - `/kdesign` - structured design generation
   - `/ktask` - TDD-focused implementation
   - `/kdesign-validate` - verify design before implementation
   - Custom agents for specific tasks (e2e-tester, bundler-specialist, etc.)

### What to Show
- Run quality checks on current work
- Show a skill/prompt file (e.g., `.claude/commands/ktask.md`)
- Show the E2E test infrastructure

**Key point:** Each layer catches different types of problems. Defense in depth.

---

## 7. Continuity: Handoffs & Learning (5 min)

**Goal:** Show how context transfers between sessions.

### Handoff Documents
- Created at end of milestones
- Capture: what was done, decisions made, issues encountered, what's next
- Example: `docs/designs/cli-restructure/implementation/HANDOFF_M1.md`

### The Caught Failure
- Walk through a specific example where the system caught something
- What would have shipped without these layers
- The compound effect: each layer adds confidence

### What to Show
- A real handoff doc
- Git history showing iterative fixes caught by tests

---

## 8. Wrap-up (4 min)

**Goal:** Land the message and show the payoff.

### Final Check-in
- How far did the two tasks get during the presentation?
- Review what was accomplished (commits, tests passing, etc.)

### Recap: The Layers of Trust
1. **Collaboration contract** (CLAUDE.md) - shapes how we work
2. **Structured specs** - clarity prevents hallucination
3. **Parallel isolation** - independence prevents chaos
4. **Quality gates** - automatic verification
5. **Handoffs** - learning compounds over time

### The Meta-Point
This presentation itself was a trust exercise. Real work happened while I talked. That's only possible because of these layers.

### Q&A

---

## Files to Have Open / Ready

- `CLAUDE.md`
- `docs/designs/cli-restructure/DESIGN.md`
- `docs/designs/cli-restructure/implementation/OVERVIEW.md`
- `docs/designs/sandbox-shell/` (the smaller feature)
- `.claude/commands/ktask.md`
- A handoff doc example
- Zellij with all panes ready

## Backup Plans

- If a task fails during the presentation: "This is actually perfect - let's see how the system handles failure"
- If tasks complete too fast: Focus on the output, review the commits
- If tasks are slow: More time to explain, check in periodically

---

## Notes

- Draw parallels to GitHub Copilot where relevant (for audience familiarity)
- Keep energy up during "showing" sections - narrate what's happening
- The live element is the hook - embrace the uncertainty
