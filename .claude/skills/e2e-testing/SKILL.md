---
name: e2e-testing
description: Knowledge base for E2E test design and execution. Used by e2e-test-designer (catalog lookup), e2e-test-architect (new test design), and e2e-tester (execution) agents.
---

# E2E Testing Skill

## Purpose

Knowledge base for E2E test design and execution. Used by:
- **e2e-test-designer** agent — Fast catalog lookup during planning
- **e2e-test-architect** agent — Design new tests when no match exists
- **e2e-tester** agent — Execute tests and report results

## Agents That Use This Skill

| Agent | Model | Purpose | When Invoked |
|-------|-------|---------|--------------|
| [e2e-tester](../../agents/e2e-tester.md) | sonnet | Execute tests, report results | After milestone implementation |
| [e2e-test-designer](../../agents/e2e-test-designer.md) | haiku | Find existing tests, identify gaps | During /kdesign-impl-plan |
| [e2e-test-architect](../../agents/e2e-test-architect.md) | opus | Design new tests from scratch | When designer finds no match |

## How Tests Are Designed

Test design uses two agents with different cognitive demands:

```
/kdesign-impl-plan
    │
    ▼
e2e-test-designer (haiku) ─── catalog lookup
    │
    ├── match found ──→ return recommendation
    │
    └── no match ──→ e2e-test-architect (opus)
                          │
                          ▼
                    detailed test specification
```

### e2e-test-designer (haiku) - Catalog Lookup

1. Receives validation requirements from /kdesign-impl-plan
2. Loads this skill's catalog
3. Searches for matching tests using heuristics
4. Returns recommendations OR hands off to architect

### e2e-test-architect (opus) - New Test Design

1. Receives handoff from designer when no match exists
2. Analyzes requirements deeply
3. Designs comprehensive test specification
4. Returns detailed test with success criteria and sanity checks

**Why two agents?** Catalog lookup is mechanical (haiku is fast/cheap). Designing new tests requires reasoning about validation, false positives, and edge cases (opus provides quality).

See [e2e-test-designer](../../agents/e2e-test-designer.md) and [e2e-test-architect](../../agents/e2e-test-architect.md) for full details.

## How Tests Are Executed

The e2e-tester agent:
1. Loads this skill (SKILL.md)
2. Finds requested tests in the catalog
3. Loads test recipe files
4. Runs pre-flight checks
5. Executes test steps
6. Reports PASS/FAIL with evidence

See [e2e-tester agent](../../agents/e2e-tester.md) for full details.

## Test Catalog

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [training/smoke](tests/training/smoke.md) | Training | <30s | Any training changes |

## Pre-Flight Modules

| Module | Checks | Used By |
|--------|--------|---------|
| [common](preflight/common.md) | Docker, sandbox, API health | All tests |

## Reusable Patterns

*(To be added in later milestones)*

## Troubleshooting

| Domain | Module | Common Issues |
|--------|--------|---------------|
| [Training](troubleshooting/training.md) | training.md | Model collapse, 0 trades, NaN metrics, timeouts |

## Creating New Tests

Use [TEMPLATE.md](TEMPLATE.md) when creating new test recipes.
