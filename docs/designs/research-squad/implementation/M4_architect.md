---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# M4: Architect + Capability Pipeline

## Goal
The Architect identifies capability gaps, produces detailed GitHub issues, and the squad gets notified when new capabilities become available.

## Dependencies
- M2 complete (autonomous loop running)

## Tasks

### Task 4.1: Architect Gap Analysis

**File(s):** `.squad/agents/architect/charter.md` (update), `.squad/roadmap/capability-gaps.md`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Enable the Architect to perform structured gap analysis. After the Engineer produces an experiment spec, the Architect evaluates: can we run this with current capabilities? What's missing? The Architect maintains `capability-gaps.md` with a prioritized list of gaps and which hypotheses they block.

**Implementation Notes:**
- Architect reads: Engineer's spec, components.md, capability-gaps.md, own history
- Architect output: feasibility assessment (can_run: true/false) + gap details if not
- Gap format: what's missing, why it's needed, which hypotheses it blocks, suggested implementation
- When a gap is identified, Architect also proposes a fallback experiment (something the squad CAN run with current capabilities)
- Priority scoring: gaps that block more hypotheses get higher priority
- Architect tracks resolved gaps (when new capabilities are built)

**Testing Requirements:**
- [ ] Architect correctly identifies when an experiment is feasible
- [ ] Architect correctly identifies when a capability is missing
- [ ] Gap entries include blocked hypotheses and priority
- [ ] Fallback experiment is proposed when primary experiment is blocked

**Acceptance Criteria:**
- [ ] capability-gaps.md has structured entries after Architect runs
- [ ] Each gap links to the hypotheses it blocks
- [ ] Architect provides fallback experiment when gaps exist

---

### Task 4.2: GitHub Issue Creation

**File(s):** `.squad/roadmap/build-queue.md`, loop runner (update)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
When the Architect identifies a capability gap, automatically create a GitHub issue with enough detail for implementation. Track issue status in `build-queue.md`.

**Implementation Notes:**
- Use `gh issue create` with structured body (from ARCHITECTURE.md issue format)
- Labels: `squad:architect`, `capability-gap`
- Issue body includes: what's needed, integration points, success criteria, blocked hypotheses
- `build-queue.md` tracks: issue number, gap description, status (open/in-progress/closed), date
- Loop runner checks for newly closed `squad:architect` issues at the start of each cycle
- When an issue is closed, update `capability-gaps.md` (mark resolved) and `components.md` (add new capability)

**Testing Requirements:**
- [ ] GitHub issue is created with correct labels and structured body
- [ ] build-queue.md tracks the issue
- [ ] Closed issue detection works (loop runner finds it)
- [ ] components.md is updated when capability becomes available

**Acceptance Criteria:**
- [ ] Architect's gap analysis triggers GitHub issue creation
- [ ] Issues have enough detail for someone (Karl/Lux) to implement
- [ ] Closed issues flow back into the squad's knowledge (new capability available)

---

### Task 4.3: E2E Validation — Gap → Issue → Capability → Usage

**File(s):** E2E test recipe
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the full capability pipeline: Architect identifies a gap, issue is created, capability is simulated as built, squad uses it.

1. Load the `ke2e` skill
2. Run a squad cycle where the Architect identifies a gap
3. Verify GitHub issue created with correct format
4. Simulate capability being built (manually update components.md)
5. Run another cycle and verify squad proposes an experiment using the new capability

**Acceptance Criteria:**
- [ ] Architect identifies a real gap in a natural squad discussion
- [ ] GitHub issue created with structured body
- [ ] After capability "arrives," squad designs an experiment using it

## Completion Checklist
- [ ] Architect performs structured gap analysis
- [ ] GitHub issues created automatically for capability gaps
- [ ] Closed issues detected and fed back into squad knowledge
- [ ] Full pipeline validated: gap → issue → build → usage
