---
name: e2e-testing
description: Knowledge base for E2E test design and execution. Used by e2e-test-designer (planning) and e2e-tester (execution) agents.
---

# E2E Testing Skill

## Purpose

Knowledge base for E2E test design and execution. Used by:
- **e2e-test-designer** agent — Find/propose tests during planning
- **e2e-tester** agent — Execute tests and report results

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
