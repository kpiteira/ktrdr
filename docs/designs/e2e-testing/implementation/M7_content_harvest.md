---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 7: Content Harvest

**Goal:** Systematically discover and inventory all E2E testing content from implementation plans and handoff documents to prepare for migration.

**Branch:** `feature/e2e-framework-m7`

**Builds On:** M6 (Impl-Plan Integration)

---

## E2E Test Scenario

**Purpose:** Verify inventory captures all E2E content from existing documents.

**Duration:** This is a research milestone, not automated testing

**Test Steps:**

```markdown
1. Scan all implementation plan directories
2. Scan all handoff documents
3. Extract E2E-related content
4. Categorize by domain (training, backtest, data)
5. Note staleness (API changes since written)
6. Produce HARVEST_INVENTORY.md
```

**Success Criteria:**
- [ ] All source directories scanned
- [ ] Content categorized by domain
- [ ] Staleness assessed
- [ ] Inventory is comprehensive

---

## ⚠️ Context Management Warning

This milestone involves reading 40+ documents. From VALIDATION.md:

**Signs you're randomizing:**
- Repeating observations you already made
- Losing track of which documents you've processed
- Contradicting earlier notes
- Struggling to synthesize patterns

**Adaptation strategies:**
1. **Batch by domain** — Process all training docs, synthesize, then move to backtest
2. **Summarize aggressively** — Write to HARVEST_INVENTORY.md frequently
3. **Use sub-agent** — Spawn Explore agent for discovery
4. **Pause and checkpoint** — Save progress if overwhelmed

**Permission granted:** Stop, save, and continue in fresh session if needed.

---

## Task 7.1: Discover Source Documents

**File:** N/A (research task)

**Type:** RESEARCH

**Task Categories:** N/A

**Description:**
Locate all documents that might contain E2E testing content.

**Source Patterns to Search:**

```bash
# Implementation plans
docs/designs/*/M*_.md
docs/architecture/*/M*_.md

# Handoff documents
docs/designs/*/implementation/HANDOFF_*.md
docs/architecture/*/HANDOFF_*.md
docs/agentic/*/HANDOFF_*.md

# Existing test docs
docs/testing/*.md
```

**Search Commands:**

```bash
# Find all implementation plans
find docs -name "M*_*.md" -type f 2>/dev/null

# Find all handoff documents
find docs -name "HANDOFF_*.md" -type f 2>/dev/null

# Count for scope estimation
find docs -name "M*_*.md" -o -name "HANDOFF_*.md" | wc -l
```

**Expected Output:**
List of all documents to process with rough count.

**Acceptance Criteria:**
- [ ] All source patterns searched
- [ ] Document list captured
- [ ] Scope estimated (document count)

---

## Task 7.2: Extract and Inventory E2E Content

**File:** `.claude/skills/e2e-testing/HARVEST_INVENTORY.md`

**Type:** MIXED

**Task Categories:** N/A

**Description:**
Read each source document and extract E2E-related content into a structured inventory.

**Inventory Structure:**

```markdown
# E2E Content Harvest Inventory

**Generated:** [date]
**Sources Processed:** [count]

---

## Summary

| Domain | Content Items | Tests | Troubleshooting | Stale |
|--------|---------------|-------|-----------------|-------|
| Training | X | Y | Z | N |
| Backtest | X | Y | Z | N |
| Data | X | Y | Z | N |
| Other | X | Y | Z | N |

---

## Training Domain

### From Implementation Plans

#### docs/designs/training-worker/M3_xxx.md

**Content Type:** E2E Test Steps
**Summary:** Tests for training progress tracking
**Relevant Sections:**
- E2E Validation section (lines X-Y)
- Test commands included

**Staleness Assessment:**
- [ ] API endpoints still valid
- [ ] Commands still work
- [x] Uses old endpoint format (needs update)

**Extract:**
```
[Relevant content copied here]
```

---

### From Handoff Documents

#### docs/designs/training-worker/implementation/HANDOFF_M3.md

**Content Type:** Troubleshooting
**Summary:** Debugging training timeout issues
**Relevant Sections:**
- "Issues Encountered" section

**Staleness Assessment:**
- [x] Still applicable
- [ ] N/A

**Extract:**
```
[Relevant content copied here]
```

---

## Backtest Domain

... similar structure ...

---

## Data Domain

... similar structure ...

---

## Cross-Cutting Content

### From SCENARIOS.md

**Content Type:** Complete Test Catalog
**Summary:** 37 test scenarios with actual results
**Sections:**
- Training: 11 scenarios
- Data: 13 scenarios
- Backtest: 13 scenarios

**Staleness Assessment:**
- [x] Most still valid
- [ ] Some endpoint changes since written
- [ ] Calibrated parameters still good

---

### From TESTING_GUIDE.md

**Content Type:** Building Blocks
**Summary:** API references, commands, patterns
**Sections:**
- Service URLs (still valid)
- API endpoints (mostly valid)
- Mode switching scripts

**Staleness Assessment:**
- [x] Core content valid
- [ ] Some endpoints updated
- [ ] Worker architecture changed (Phase 5.3)

---

### From E2E_CHALLENGES_ANALYSIS.md

**Content Type:** Troubleshooting Gold
**Summary:** Real debugging sessions, symptom→cure mappings
**Sections:**
- Model collapse analysis
- Docker issues
- Sandbox port confusion

**Staleness Assessment:**
- [x] Highly valuable
- [x] Still applicable
- Already incorporated into M3/M4 design

---

## Staleness Summary

| Issue | Documents Affected | Remediation |
|-------|-------------------|-------------|
| Old training endpoint | 3 | Update to /trainings/start |
| Host service config | 5 | Now uses WorkerRegistry |
| Port hardcoding | 4 | Use ${KTRDR_API_PORT:-8000} variable |

---

## Migration Candidates

Based on this harvest, recommended for migration:

### High Priority (Proven Value)
1. SCENARIOS.md training tests → tests/training/
2. SCENARIOS.md backtest tests → tests/backtest/
3. E2E_CHALLENGES_ANALYSIS.md → troubleshooting/

### Medium Priority
4. TESTING_GUIDE.md API reference → update in recipes
5. Implementation plan E2E sections → extract patterns

### Low Priority (May Skip)
6. Outdated handoff content → archive only
7. Duplicate content → consolidate
```

**Process:**

1. **Batch by domain:**
   - Process all training-related docs first
   - Write to inventory before moving to backtest
   - Continue with data, then cross-cutting

2. **For each document:**
   - Scan for E2E keywords: "test", "validate", "verify", "curl", "E2E"
   - Extract relevant sections
   - Assess staleness
   - Write to inventory immediately

3. **Synthesize:**
   - After each domain, summarize patterns
   - Note duplicates
   - Identify gaps

**Acceptance Criteria:**
- [ ] All sources processed
- [ ] Content categorized by domain
- [ ] Staleness assessed for each item
- [ ] Migration candidates identified
- [ ] Inventory is complete and navigable

---

## Milestone 7 Completion Checklist

### All Tasks Complete
- [ ] Task 7.1: Source documents discovered
- [ ] Task 7.2: Content extracted and inventoried

### Deliverable
- [ ] HARVEST_INVENTORY.md exists
- [ ] All domains covered
- [ ] Staleness assessed
- [ ] Migration candidates listed

### Quality Gates
- [ ] Inventory is comprehensive
- [ ] No documents missed
- [ ] Ready for decision point review

---

## Next: Decision Point

After M7, review HARVEST_INVENTORY.md together to answer:

1. Which tests are still valid?
2. Which tests cover the same ground?
3. What's missing?
4. What's the priority order?
5. What gets archived vs. migrated?

This decision point is REQUIRED before proceeding to M8.
