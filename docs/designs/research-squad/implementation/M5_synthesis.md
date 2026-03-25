---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# M5: Synthesis + Long-Run Evaluation

## Goal
The Scribe produces macro synthesis from accumulated experiments. Context management handles 50+ experiments without overflow. Evaluate whether the squad mechanism actually compounds knowledge and produces qualitatively better experiments over time.

## Dependencies
- M2 complete (autonomous loop running, at least 10-20 experiments accumulated)

## Tasks

### Task 5.1: Scribe Synthesis Cycle

**File(s):** `.squad/agents/scribe/charter.md` (update), `.squad/knowledge/synthesis.md`, Coordinator logic (synthesis phase)
**Type:** CODING
**Estimated time:** 2-3 hours

**Description:**
Implement the Scribe's synthesis capability. Every N experiments (default 10, configurable), the Scribe reads the full experiment history and produces a fresh `synthesis.md` that distills patterns into:
- **Established facts** (things we know with high confidence, backed by multiple experiments)
- **Active frontiers** (where current exploration is focused)
- **Dead ends** (approaches thoroughly explored and failed, with evidence)
- **Open questions** (things we don't know and should investigate)
- **Best result so far** (the architecture/metrics to beat)

**Implementation Notes:**
- Synthesis is triggered by Director (cadence=synthesis) or automatically every N cycles
- Scribe receives: ALL experiments.md entries + current hypotheses.md + current decisions.md
- This is the highest-context agent call — Scribe needs to see everything to synthesize
- synthesis.md replaces the previous version (not append — it's a fresh distillation)
- After synthesis, other agents read synthesis.md INSTEAD of full experiments.md (context savings)
- Scribe also identifies: repeated experiment patterns, contradictory results, untested high-priority hypotheses

**Testing Requirements:**
- [ ] Synthesis covers all experiments (not just recent)
- [ ] Each section (facts, frontiers, dead ends, questions, best result) is populated
- [ ] Synthesis is concise (< 3 pages even for 50 experiments)
- [ ] After synthesis, agents can be spawned with synthesis.md instead of full experiments.md

**Acceptance Criteria:**
- [ ] Scribe produces meaningful synthesis from 10+ experiments
- [ ] Synthesis identifies patterns that aren't obvious from individual experiments
- [ ] synthesis.md is usable as a context replacement for full history

---

### Task 5.2: Context Management

**File(s):** Coordinator logic (update context assembly), `.squad/agents/*/history.md` (trimming)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Implement context management so the squad scales to 50+ experiments without context overflow. Agents should receive the minimum context they need: synthesis instead of full history, trimmed histories, and only the most relevant knowledge files.

**Implementation Notes:**
- After synthesis exists, replace full experiments.md with synthesis.md + last 5 experiments for most agents
- Scribe still gets full experiments.md during synthesis (it needs everything)
- Agent histories: keep last 20 entries, archive older ones to `{agent}/history_archive.md`
- Track context budget: log approximate token count per agent per cycle
- If any agent exceeds 80% of context window, trigger emergency synthesis
- Components.md and decisions.md are compact and unlikely to overflow — no trimming needed

**Testing Requirements:**
- [ ] Context size is measurably smaller after synthesis (vs full history)
- [ ] Agents still produce quality output with synthesis instead of full history
- [ ] History trimming preserves most recent and most important entries
- [ ] Emergency synthesis triggers when context budget exceeded

**Acceptance Criteria:**
- [ ] Squad operates correctly with 50+ experiments using synthesis-based context
- [ ] No agent exceeds context limits
- [ ] Quality of squad output doesn't degrade with synthesis-based context

---

### Task 5.3: Long-Run Evaluation

**File(s):** `.squad/evaluation/squad_evaluation.md`
**Type:** VALIDATION
**Estimated time:** 3-4 hours (analysis of accumulated results)

**Description:**
After 20-30 experiments, evaluate whether the squad mechanism works. This is the meta-experiment: does collaborative multi-agent reasoning produce better trading architectures than a single agent or random search?

**Evaluation criteria:**
1. **Qualitative progression:** Do later experiments involve fundamentally different architectures than early ones? (Not just parameter tweaks)
2. **Frontier diversity:** Has the squad explored multiple frontiers (cross-asset, attention, exit timing, etc.) or converged on one?
3. **Knowledge compounding:** Does synthesis.md contain insights that wouldn't be obvious from any single experiment?
4. **Best result trajectory:** Is the best Sharpe/win rate improving over time?
5. **Architect utilization:** Has the Architect identified gaps that led to new capabilities that led to better experiments?
6. **Scout influence:** Has the Scout brought external knowledge that changed the research direction?
7. **Decision quality:** Are decisions.md entries well-reasoned and respected by later experiments?

**Document findings in `squad_evaluation.md` with:**
- Experiment progression timeline (what was tried, in what order)
- Best result achieved and the architecture that produced it
- Evidence for/against knowledge compounding
- What worked about the squad model and what didn't
- Recommendations for the next phase (adapt roles, change cadence, add agents, etc.)

**Acceptance Criteria:**
- [ ] Honest evaluation with evidence for each criterion
- [ ] Clear conclusion: does the squad mechanism compound knowledge?
- [ ] Specific recommendations for improvement
- [ ] Comparison to what a single-agent loop would likely have produced

## Completion Checklist
- [ ] Scribe produces meaningful synthesis from 10+ experiments
- [ ] Context management scales to 50+ experiments
- [ ] Long-run evaluation documents whether the squad compounds knowledge
- [ ] Recommendations produced for next phase of development
