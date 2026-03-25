---
design: docs/designs/research-squad/DESIGN.md
architecture: docs/designs/research-squad/ARCHITECTURE.md
---

# M3: Scout + External Research

## Goal
The squad discovers an external technique, data source, or approach it wouldn't have found from its own experiments, and incorporates it into an experiment design. The Scout brings the outside world into the research loop — preventing closed-world thinking where the squad only knows what it has tried.

## Dependencies
- M2 complete (autonomous loop running)

## Tasks

### Task 3.1: Scout Agent with Web Search

**File(s):** `.squad/agents/scout/charter.md` (update), Coordinator logic (update Scout spawning)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Enable the Scout agent with WebSearch and WebFetch tools. The Scout reads `frontiers.md` to understand what the squad is exploring, searches for relevant papers and techniques, and produces structured findings.

**Implementation Notes:**
- Scout is spawned with `WebSearch` and `WebFetch` tools enabled
- Scout reads: own charter, own history, frontiers.md, bibliography.md
- Scout searches based on current frontiers (e.g., "LSTM forex cross-asset features", "temporal fusion transformer FX prediction")
- Output format: structured insights with source, relevance, key finding, actionable recommendation
- Scout's charter includes quality filters:
  - Prefer peer-reviewed or well-cited papers
  - Skeptical of results without transaction costs
  - Skeptical of in-sample-only results
  - Note dataset size and whether FX-specific or general
- Scout runs during STRATEGIZE phase, before Director proposes frontier

**Testing Requirements:**
- [ ] Scout successfully performs web searches
- [ ] Scout produces structured insights (not raw search results)
- [ ] Insights reference specific papers/sources with URLs
- [ ] Quality filters are applied (Scout notes limitations of sources)

**Acceptance Criteria:**
- [ ] Scout finds at least one relevant external source per cycle
- [ ] Findings are in structured format parseable by the Scribe
- [ ] Bibliography.md grows with new references

---

### Task 3.2: External Insights Integration

**File(s):** `.squad/roadmap/external-insights.md`, `.squad/agents/scout/bibliography.md`, Coordinator logic (update context routing)
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Integrate Scout's findings into the squad's knowledge base and decision flow. Director and Inventor receive Scout findings as input during STRATEGIZE.

**Implementation Notes:**
- Scout writes findings to `external-insights.md` (curated, actionable)
- Scout appends references to `bibliography.md` (all sources found, with relevance notes)
- Scout maintains `reading-queue.md` (topics to investigate next, driven by frontiers)
- Director receives external-insights.md content when spawned
- Inventor receives external-insights.md content (may inspire novel approaches)
- Architect receives insights that reference new capabilities ("this technique requires attention mechanisms")
- Scribe records which insights influenced experiment design

**Testing Requirements:**
- [ ] external-insights.md contains structured entries after Scout runs
- [ ] bibliography.md grows over cycles
- [ ] Director references Scout findings in frontier proposals
- [ ] Insights that reference capability gaps are visible to Architect

**Acceptance Criteria:**
- [ ] Scout findings flow into Director and Inventor context
- [ ] At least one experiment design is influenced by a Scout finding
- [ ] Bibliography persists across cycles

---

### Task 3.3: E2E Validation — Scout Influences Experiment

**File(s):** E2E test recipe
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate that the Scout brings external knowledge that demonstrably influences experiment design.

1. Load the `ke2e` skill
2. Run 2-3 squad cycles with Scout enabled
3. Verify:
   - Scout performed web searches
   - At least one finding was cited by Director or Inventor
   - The experiment design references or incorporates the external insight
   - bibliography.md has new entries

**Acceptance Criteria:**
- [ ] Scout finds external research relevant to current frontiers
- [ ] At least one experiment design is demonstrably influenced by Scout findings
- [ ] Knowledge base updated with external references

## Completion Checklist
- [ ] Scout performs real web searches based on current frontiers
- [ ] Findings are structured, quality-filtered, and actionable
- [ ] External insights flow into squad decision-making
- [ ] Bibliography grows as a persistent knowledge resource
