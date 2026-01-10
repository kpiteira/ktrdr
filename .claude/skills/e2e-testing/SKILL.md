---
name: e2e-testing
description: Knowledge base for E2E test design and execution. Used by e2e-test-designer (planning) and e2e-tester (execution) agents.
---

# E2E Testing Skill

## Purpose

Knowledge base for E2E test design and execution. Used by:
- **e2e-test-designer** agent — Find/propose tests during planning
- **e2e-tester** agent — Execute tests and report results

## Agents That Use This Skill

| Agent | Purpose | When Invoked |
|-------|---------|--------------|
| [e2e-tester](../../agents/e2e-tester.md) | Execute tests, report results | After milestone implementation |
| e2e-test-designer | Find/propose tests | During /kdesign-impl-plan (M5) |

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

*(To be added in later milestones)*

## Creating New Tests

Use [TEMPLATE.md](TEMPLATE.md) when creating new test recipes.
