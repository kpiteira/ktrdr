---
design: docs/designs/research-squad-v2/DESIGN.md
architecture: docs/designs/research-squad-v2/ARCHITECTURE.md
---

# M5: Lux Integration

**When this works:** Lux runs the squad autonomously — starts cycles, monitors progress, steers via nudges, reflects on findings, stores insights in memory. Karl reviews synthesis.md periodically, not every cycle. The squad becomes one of Lux's capabilities, like code review or design.

**Scenario:** Lux reads its journal: "Last squad run 3 days ago, 5 cycles, found regime-conditional features promising but cost-prohibitive on 5m." Lux writes a nudge: "Explore 1h as a lower-cost alternative to 5m for regime-conditional approach." Starts the squad with max_iterations=5. Monitors progress — sees cycle 3 produced a promising result. After completion, reflects: "The squad confirmed 1h regime-conditional shows signal. Next run should explore GRU vs LSTM for this approach." Stores insight in beliefs.

**Prerequisite:** M4 complete (full loop automation working)

**Scope:** Integration layer between Lux and the squad orchestrator, plus critical squad quality fixes surfaced by M4 validation. Research-first tasks — Lux's capability interface may evolve.

---

## Pre-requisite Fixes (from M4 Validation)

M4 validation (2 real cycles, 2026-04-14) exposed operational issues that must be fixed before Lux can meaningfully steer the squad. These aren't Lux-specific bugs — they affect all squad runs — but they're blocking for autonomous operation.

### Fix A: Nudge Expiry / Arc Scoping
**Problem:** Nudges from prior research arcs carry forward indefinitely. During M4 validation, the Director treated a stale nudge ("Do NOT pause before cycle 5" from a previous arc) as active orders, overriding valid Critic pushback to force-execute a low-value experiment. The entire cycle's strategic direction was shaped by stale context.

**Impact on M5:** If Lux writes nudges to steer the squad, stale nudges from prior Lux-initiated runs will compound. Lux's steering input becomes noise rather than signal.

**Fix:** Either (a) nudges require a `date:` and `arc:` header that the Director checks before treating as active, or (b) the loop clears nudges at the start of a new arc, or (c) the Director prompt instructs it to evaluate nudge freshness against the current research context.

### Fix B: Inventor Consultation Ordering
**Problem:** In full_squad mode, the Director broadcasts to all agents in parallel with the same brief. The Inventor reacts to the Director's pre-chosen direction instead of proposing alternatives. During validation, the Architect independently discovered a zero-code F2 path (CFTC COT data) — exactly the creative contribution the Inventor should have surfaced first.

**Impact on M5:** If Lux expects the squad to explore novel directions, the current pattern means the Inventor is structurally unable to influence strategy selection.

**Fix:** Director charter update — staged consultation for full_squad: Inventor first ("here's the frontier, what should we try?"), then Architect/Scout for feasibility, then Critic to challenge, then Engineer to build.

### Fix C: cycle_complete Semantics
**Problem:** Director called `cycle_complete` twice — once after planning, then continued executing the experiment and called it again with results. The loop used the last call, but the intent is confused.

**Fix:** Director charter clarification — `cycle_complete` is a terminal action. Once called, the Director should not continue spawning agents or executing experiments.

---

## Task 5.1: Squad as Lux Capability

**File(s):** TBD — depends on Lux's capability interface (likely a Claude Code skill or callable module)
**Type:** MIXED (research + coding)
**Estimated time:** 3-4 hours

**Description:**
Make the squad orchestrator invocable as a Lux capability. Lux should be able to start a squad run, check its status, and review results — the same way Karl interacts with the squad, but automated.

**Implementation Notes:**
- **Research first:** how does Lux invoke capabilities today?
  - Check `~/.claude/lux/` for capability patterns
  - Check existing skills in `.claude/skills/` for the integration pattern
  - The squad-coordinator skill (`.claude/skills/squad-coordinator/`) already exists — this may be the integration point
- **Integration surface is narrow:** Lux calls `run_loop()` and reads results
  - Start: `run_loop(max_iterations=N, initial_cadence="full_squad")`
  - Monitor: read `cycle-history.json`, check for stalls
  - Review: read `synthesis.md`, `experiments.md` (recent), `frontiers.md`
  - Steer: write to `loop/nudges.md`
- **The squad works identically whether invoked by Karl or Lux** — the interface is the same state files
- This may be updating the existing `squad-coordinator` skill to use v2's Python loop instead of v1's shell scripts

**Testing Requirements:**
- [ ] Unit test: squad invocable programmatically with max_iterations and cadence
- [ ] Unit test: status check returns current iteration, cadence, last result
- [ ] Unit test: nudge writing via integration layer works
- [ ] Integration test: Lux invokes squad → squad runs 1 cycle → Lux reads results

**Acceptance Criteria:**
- [ ] Squad orchestrator invocable as a Lux capability
- [ ] Lux can start, monitor, steer (nudge), and review squad runs
- [ ] No changes to orchestrator internals required for integration
- [ ] Existing squad-coordinator skill updated or replaced

---

## Task 5.2: Memory + Reflection Integration

**File(s):** TBD — depends on Lux's memory interface
**Type:** MIXED (research + coding)
**Estimated time:** 2-3 hours

**Description:**
Connect squad results to Lux's memory and reflection systems. After a squad run, Lux reflects on what was learned and stores relevant insights — the research program becomes part of Lux's growing understanding.

**Implementation Notes:**
- **After squad completion, Lux should:**
  - Read synthesis.md for distilled research findings
  - Read cycle-history.json for operational patterns (cost efficiency, agent utilization, stall frequency)
  - Store notable findings in Lux memory (beliefs, observations at `~/.claude/lux/`)
  - Reflect on research trajectory: is the squad evolving or plateauing? Are frontiers being explored or exhausted?
- **Integration with Lux's journal:** squad run summaries in session journals (`~/.claude/lux/journals/`)
- **Integration with Lux's beliefs:** squad discoveries that challenge existing beliefs trigger updates (e.g., "regime-conditional features work" updates a belief about feature selection)
- **Direction:** Lux learns from the squad's experiments. The squad learns from its own history.md files. These are separate learning loops.

**Testing Requirements:**
- [ ] Unit test: squad results parseable by Lux's memory system
- [ ] Unit test: notable findings extractable from synthesis.md
- [ ] Unit test: journal entry produced after squad run completion
- [ ] Integration test: Lux invokes squad → squad runs → Lux reflects → memory updated

**Acceptance Criteria:**
- [ ] Squad results feed into Lux's memory (beliefs and/or observations)
- [ ] Lux reflects on research trajectory after runs
- [ ] Journal entries capture squad run summaries
- [ ] No manual steps between squad completion and Lux reflection

---

## Task 5.3: VALIDATION — Lux Runs the Squad Autonomously

**Type:** VALIDATION
**Estimated time:** 2-3 hours

**Description:**
Lux invokes the squad, monitors a run, steers via nudge, reviews results, and reflects. The full integration loop — proving that the squad is a Lux capability, not just a standalone tool.

**Scenario under test:** Lux starts a 3-cycle squad run. During the run, Lux writes a nudge based on cycle 1 results (steering). After completion, Lux reads synthesis.md, produces a reflection journal entry, and stores an insight in beliefs. Karl's only involvement: reading the journal later.

**Validation Steps:**

1. **Load the `ke2e` skill** before designing any validation
2. **Invoke ke2e-test-scout** with: "Lux integration with squad v2: Lux starts squad run (max_iterations=3), writes a nudge mid-run, reads results after completion, produces reflection journal entry, stores squad-derived insight in memory. Full automation — no human intervention."
3. **Invoke ke2e-test-runner** with the identified test recipe
4. **Tests must exercise real infrastructure** — real Lux session, real squad execution

**Success Criteria:**
- [ ] Lux successfully starts squad orchestrator with parameters
- [ ] Squad runs 3 cycles under Lux's management
- [ ] Lux writes a nudge that the Director reads in a subsequent cycle
- [ ] Lux produces a reflection/journal entry after squad completion
- [ ] Squad-derived insight appears in Lux's memory (beliefs or observations)
- [ ] Entire flow automated — no human intervention required
- [ ] Lux's steering (nudge) visibly influences the Director's next cycle decisions

**Evidence Required:**
- Lux's invocation command/tool call showing squad start
- cycle-history.json showing 3 completed cycles
- nudges.md showing Lux's steering input with timestamp
- Director reasoning in cycle after nudge (showing nudge influence)
- Lux journal entry about the squad run
- Lux memory update with squad-derived insight
