# E2E Testing Framework: Design Validation

**Date:** 2026-01-10
**Documents Validated:**
- Design: `docs/designs/e2e-testing/DESIGN.md`
- Architecture: `docs/designs/e2e-testing/ARCHITECTURE.md`
- Scope: Full framework (both agents, skill, integration)

---

## Validation Summary

**Scenarios Validated:** 12 scenarios traced
**Critical Gaps Found:** 12 (all resolved)
**Interface Contracts:** Defined for all component boundaries

---

## Key Decisions Made

These decisions came from our conversation and should inform implementation:

### 1. Interface Format: Hybrid Template + Free-Form

**Context:** GAP-1, GAP-2, GAP-19 — Input/output between impl-plan and designer was undefined.

**Decision:** Use hybrid approach — template structure for consistency, free-form fields for intent and expectations. This lets the designer agent understand not just what to find, but why it matters.

**Trade-off accepted:** Designer must handle some ambiguity in free-form fields.

---

### 2. Sanity Checks: Template-Required, Recipe-Owned

**Context:** GAP-10, GAP-11 — Sanity checks (like catching 100% accuracy) weren't systematically defined.

**Decision:** Test template requires a sanity checks section (forces thought at creation time). Each test recipe is self-contained with its specific checks. Common patterns can be referenced but the test owns its validation.

**Trade-off accepted:** Some duplication across tests, but each test is self-contained.

---

### 3. Cure Retry: Max 2 Attempts, 10s Wait

**Context:** GAP-7, GAP-8 — No limits on cure retries, risk of infinite loops.

**Decision:**
- Max 2 cure attempts per pre-flight failure
- 10 second wait after applying cure (services need time to stabilize)
- After 2 attempts, gather diagnostics and escalate to main agent

**Trade-off accepted:** Some recoverable issues might need more attempts, but prevents spinning.

---

### 4. Failure Categories: Four Types with Clear Actions

**Context:** GAP-17, GAP-21, GAP-22 — Main agent didn't know how to act on failures.

**Decision:** Four failure categories with prescribed actions:

| Category | Main Agent Action |
|----------|-------------------|
| ENVIRONMENT | Ask human (can't fix via code) |
| CONFIGURATION | Fix config, re-run test |
| CODE_BUG | Fix code, re-run test |
| TEST_ISSUE | Fix test recipe, re-run test |

**Trade-off accepted:** Some failures might not fit neatly; will add categories as needed.

---

### 5. Designer Invocation: Per Milestone

**Context:** GAP-18 — When should kdesign-impl-plan invoke designer?

**Decision:** Invoke designer once per milestone during Step 4 (task expansion). Each milestone gets focused test recommendations rather than one big batch.

**Trade-off accepted:** Multiple agent invocations, but keeps context focused.

---

### 6. Content Harvesting: Before Migration, With Self-Monitoring

**Context:** Large volume of E2E content scattered across implementation plans and handoff documents.

**Decision:**
- M7 harvests from implementation plans AND handoff documents
- Decision point with Karl before migration to curate what goes into catalog
- Session includes explicit warning about context management with permission to adapt strategy

**Trade-off accepted:** Harvesting is significant work, but captures institutional knowledge.

---

## Scenarios Validated

### Happy Paths
1. **Designer finds existing test** — Impl-plan → designer → catalog match → recommendation
2. **Tester executes and passes** — Pre-flight → execution → validation → PASS report
3. **Designer proposes new test** — No match → proposal with building blocks
4. **Full milestone cycle** — Planning → implementation → tester → all pass

### Error Paths
5. **Pre-flight fails with known cure** — Symptom detected → cure applied → retry → proceed
6. **Pre-flight fails with unknown issue** — No cure → diagnostics → escalate
7. **Test fails after pre-flight (model collapse)** — Sanity check catches → categorized failure

### Edge Cases
8. **Designer finds partial match** — Existing test + additional validation needed
9. **Multiple tests with dependencies** — Ordering handled by test recipe
10. **Cure applied but issue persists** — Max retries → escalate with diagnostics

### Integration Boundaries
11. **kdesign-impl-plan → designer handoff** — Structured input → recommendations
12. **tester → main agent failure handoff** — Categorized report → clear action

---

## Interface Contracts

### kdesign-impl-plan → e2e-test-designer

**Input:**
```markdown
## E2E Test Design Request

**Milestone:** [name/number]
**Capability:** [what user can do when complete]

**Validation Requirements:**
1. [Specific thing that must work]
2. [Another specific thing]

**Components Involved:**
- [Component A]
- [Component B]

**Intent:** [Free-form: what we're really validating and why]
**Expectations:** [What a passing test should demonstrate]
```

**Output:**
```markdown
## E2E Test Recommendations for [Milestone]

### Existing Tests That Apply
| Test | Purpose | Covers Requirement |
|------|---------|-------------------|
| training/smoke | Verify training completes | Requirement 1 |

### Additional Validation Needed
**Gap:** [What's not covered]
**Proposed Check:** [Specific validation]
**Building Blocks:** [preflight/common, patterns/poll-progress]

### New Test Required (if needed)
**Name:** [category/name]
**Purpose:** [One sentence]
**Building Blocks:** [List]
**Proposed Structure:** [Outline]
```

---

### Main Agent → e2e-tester

**Input:**
```markdown
## E2E Test Execution Request

**Tests to Run:**
1. training/smoke
2. training/progress

**Context:** [Optional: why these tests, what was implemented]
```

**Output:**
```markdown
## E2E Test Results

### Summary
| Test | Result | Duration |
|------|--------|----------|
| training/smoke | ✅ PASSED | 8s |

### [test-name]: ✅ PASSED
**Pre-flight:** All checks passed
**Execution:** Completed successfully
**Evidence:** [operation ID, logs, response data]
**Sanity Checks:** All passed

### [test-name]: ❌ FAILED
**Category:** CODE_BUG | ENVIRONMENT | CONFIGURATION | TEST_ISSUE
**Pre-flight:** [status]
**Failure Point:** [which step]
**Expected:** [what should happen]
**Actual:** [what happened]
**Evidence:** [concrete data]
**Diagnosis:** [root cause assessment]
**Suggested Action:** [what to do]
```

---

### Failure Report Format

```markdown
### [test-name]: ❌ FAILED

**Category:** CODE_BUG | ENVIRONMENT | CONFIGURATION | TEST_ISSUE
**Pre-flight:** PASSED | FAILED (with details)
**Failure Point:** [Which step failed]
**Expected:** [What should have happened]
**Actual:** [What actually happened]
**Evidence:** [Operation IDs, log excerpts, response bodies]
**Cures Attempted:** [If pre-flight cures were applied]
**Diagnosis:** [Tester's assessment of root cause]
**Suggested Action:** [Specific actions for main agent]
```

---

## Milestone Structure

### M1: Skill Foundation
**Focus:** Knowledge base structure + one complete test recipe
**What's Built:**
- `e2e-testing/SKILL.md` — catalog, navigation
- `e2e-testing/TEMPLATE.md` — template for new tests
- `e2e-testing/tests/training/smoke.md` — first real test
- `e2e-testing/preflight/common.md` — checks without cures

**E2E Test:** Claude can read SKILL.md and navigate to training/smoke test

---

### M2: Tester Agent Core
**Focus:** Execution loop — run tests, return reports
**What's Built:**
- `e2e-tester.md` agent definition with full execution logic

**E2E Test:** Invoke tester with "Run: training/smoke" → returns ✅ PASSED with evidence

---

### M3: Pre-Flight Cure System
**Focus:** Environment resilience
**What's Built:**
- Symptom→cure mappings in preflight/common.md
- Retry logic (max 2 attempts, 10s wait)
- Diagnostic gathering on escalation

**E2E Test:** Docker stopped → tester applies cure → test recovers

---

### M4: Failure Handling & Sanity Checks
**Focus:** Actionable failure reports
**What's Built:**
- Failure categorization (CODE_BUG, ENVIRONMENT, CONFIGURATION, TEST_ISSUE)
- Sanity checks in test recipes
- Troubleshooting module: troubleshooting/training.md

**E2E Test:** Test with 100% accuracy → returns ❌ FAILED with category=CONFIGURATION

---

### M5: Designer Agent
**Focus:** Test discovery and recommendations
**What's Built:**
- `e2e-test-designer.md` agent definition
- Catalog search and matching logic
- Structured output format

**E2E Test:** Invoke designer with "Validate training progress" → returns training/progress recommendation

---

### M6: kdesign-impl-plan Integration
**Focus:** Trigger mechanism
**What's Built:**
- Update kdesign-impl-plan.md to invoke designer in Step 4
- Parse and incorporate designer output

**E2E Test:** Run /kdesign-impl-plan → milestone E2E section populated by designer

---

### M7: Harvest from Implementation Plans & Handoffs
**Focus:** Discovery and inventory

**Sources:**
- `docs/designs/*/M*_.md` — implementation plans
- `docs/architecture/*/M*_.md` — implementation plans
- `docs/designs/*/implementation/HANDOFF_*.md` — handoff documents
- `docs/architecture/*/HANDOFF_*.md` — handoff documents
- `docs/agentic/*/HANDOFF_*.md` — handoff documents

**What's Built:**
- `HARVEST_INVENTORY.md` — organized inventory of all E2E content
- Categorized by domain (training, backtest, data, etc.)
- Flags E2E tests vs. troubleshooting content
- Notes staleness (API changes since written)

**E2E Test:** Inventory document complete with all sources processed

#### ⚠️ Context Management Warning

This milestone involves reading 40+ handoff documents and numerous implementation
plans. Monitor for signs of context degradation:

**Signs you're randomizing:**
- Repeating observations you already made
- Losing track of which documents you've processed
- Contradicting earlier notes
- Struggling to synthesize patterns across documents

**Adaptation strategies:**
1. **Batch by domain** — Process all training docs, synthesize, then move to backtest
2. **Summarize aggressively** — Write to HARVEST_INVENTORY.md frequently, don't hold in context
3. **Use sub-agent** — Spawn Explore agent for discovery, process results in main session
4. **Pause and checkpoint** — If overwhelmed, save progress and continue in fresh session

**Permission granted:** If you feel the context is degrading, stop, save what you have,
and either change strategy or ask Karl for guidance. Partial progress is better than
corrupted synthesis.

---

### Decision Point: Curriculum Curation (Together)

After M7, review together:
1. **Harvested content** (M7 output) — scattered but battle-tested
2. **Existing SCENARIOS.md** — curated but possibly stale
3. **E2E_CHALLENGES_ANALYSIS.md** — troubleshooting gold

**Questions to answer:**
- Which tests are still valid?
- Which tests cover the same ground?
- What's missing?
- What's the priority order?
- What gets archived vs. migrated?

**Output:** Agreed curriculum — list of tests to migrate, structure decisions.

---

### M8: Content Migration
**Focus:** Execute the decided curriculum
**What's Built:**
- Migrate agreed tests into `tests/{category}/{name}.md`
- Migrate troubleshooting into `troubleshooting/`
- Add domain-specific pre-flight modules
- Update SKILL.md catalog
- Archive old docs/testing/ files

**E2E Test:** Invoke designer with any validation need → finds appropriate test from curated catalog

---

## Dependency Graph

```
M1 → M2 → M3 → M4
                ↓
               M5 → M6 → M7 → [Decision Point] → M8
```

---

## Remaining Open Questions

To be resolved during implementation:

1. **Test recipe granularity** — How detailed should execution steps be? (Exact curl commands vs. pseudocode)
2. **Troubleshooting coverage** — How many gotchas to document before diminishing returns?
3. **Catalog size** — What's the right number of tests? (Comprehensive vs. maintainable)

---

## What Gets Archived

After M8 completion:
- `docs/testing/SCENARIOS.md` → Archive (migrated content)
- `docs/testing/TESTING_GUIDE.md` → Archive (incorporated into skill)
- Individual handoff docs → Keep in place (still useful for implementation context)
