# E2E Testing Framework: Implementation Plan

## Reference Documents

- **Design:** [../DESIGN.md](../DESIGN.md)
- **Architecture:** [../ARCHITECTURE.md](../ARCHITECTURE.md)
- **Validation:** [../VALIDATION.md](../VALIDATION.md)
- **Challenges Analysis:** [../E2E_CHALLENGES_ANALYSIS.md](../E2E_CHALLENGES_ANALYSIS.md)

---

## Milestone Summary

| # | Name | Tasks | E2E Test | Status |
|---|------|-------|----------|--------|
| M1 | [Skill Foundation](M1_skill_foundation.md) | 5 | Claude navigates skill to find test | ⏳ |
| M2 | [Tester Agent Core](M2_tester_agent_core.md) | 4 | Tester executes training/smoke, returns PASSED | ⏳ |
| M3 | [Pre-Flight Cure System](M3_preflight_cure_system.md) | 3 | Docker stopped → tester applies cure → recovers | ⏳ |
| M4 | [Failure Handling](M4_failure_handling.md) | 4 | Model collapse detected → categorized failure | ⏳ |
| M5 | [Designer Agent](M5_designer_agent.md) | 3 | Designer finds tests for validation needs | ⏳ |
| M6 | [Impl-Plan Integration](M6_impl_plan_integration.md) | 2 | /kdesign-impl-plan invokes designer | ⏳ |
| M7 | [Content Harvest](M7_content_harvest.md) | 2 | Inventory of E2E content from handoffs | ⏳ |
| — | **Decision Point** | — | Curriculum curation with Karl | ⏳ |
| M8 | [Content Migration](M8_content_migration.md) | 4 | Curated tests migrated to catalog | ⏳ |

**Total Tasks:** 27 (excluding decision point)

---

## Dependency Graph

```
M1 (Skill Foundation)
 │
 ▼
M2 (Tester Agent Core)
 │
 ▼
M3 (Pre-Flight Cure System)
 │
 ▼
M4 (Failure Handling & Sanity Checks)
 │
 ▼
M5 (Designer Agent)
 │
 ▼
M6 (Impl-Plan Integration)
 │
 ▼
M7 (Content Harvest)
 │
 ▼
[Decision Point: Curriculum Curation]
 │
 ▼
M8 (Content Migration)
```

All milestones are sequential. Each builds on the previous.

---

## Architecture Patterns Applied

| Pattern | Implemented In | Description |
|---------|----------------|-------------|
| Two-Agent Architecture | M2, M5 | Tester (execution) and Designer (planning) |
| Progressive Disclosure | M1 | SKILL.md < 500 lines, files loaded on-demand |
| Symptom→Cure Mappings | M3 | Pre-flight failures have documented fixes |
| Building Blocks Composition | M1, M8 | Tests composed from preflight/, patterns/ |
| Failure Categorization | M4 | CODE_BUG, ENVIRONMENT, CONFIGURATION, TEST_ISSUE |

---

## Key Decisions (from Validation)

1. **Interface Format:** Hybrid template + free-form for designer I/O
2. **Sanity Checks:** Template-required, recipe-owned
3. **Cure Retry:** Max 2 attempts, 10s wait, then escalate
4. **Failure Categories:** Four types with prescribed actions
5. **Designer Invocation:** Per milestone during impl-plan Step 4
6. **Content Harvesting:** Before migration, with decision point

---

## What Gets Archived (After M8)

- `docs/testing/SCENARIOS.md` → Archive (migrated content)
- `docs/testing/TESTING_GUIDE.md` → Archive (incorporated into skill)
- Individual handoff docs → Keep in place (still useful for context)
