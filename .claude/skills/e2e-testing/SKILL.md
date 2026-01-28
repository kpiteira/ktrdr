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

### Training Tests

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [training/smoke](tests/training/smoke.md) | Training | <30s | Any training changes |
| [training/progress](tests/training/progress.md) | Training | ~60-90s | Progress tracking, metrics collection |
| [training/cancellation](tests/training/cancellation.md) | Training | ~30s | Cancellation handling, cleanup |
| [training/operations-list](tests/training/operations-list.md) | Training | ~5s | Operations API, list/filter |
| [training/host-start](tests/training/host-start.md) | Training (Host) | ~5s | Host service standalone |
| [training/host-gpu](tests/training/host-gpu.md) | Training (Host) | ~3s | GPU allocation |
| [training/host-integration](tests/training/host-integration.md) | Training (Integration) | ~5s | Backend → host proxy |
| [training/host-cache](tests/training/host-cache.md) | Training (Integration) | ~5s | Two-level operation ID mapping |
| [training/host-completion](tests/training/host-completion.md) | Training (Integration) | ~5s | Full cycle through proxy |
| [training/error-invalid-strategy](tests/training/error-invalid-strategy.md) | Training (Error) | ~1s | Error handling |
| [training/error-not-found](tests/training/error-not-found.md) | Training (Error) | ~1s | Error handling |

### Data Tests

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [data/cache-get](tests/data/cache-get.md) | Data | <3s | Cache loading, data retrieval |
| [data/cache-range](tests/data/cache-range.md) | Data | <100ms | Metadata queries |
| [data/cache-validate](tests/data/cache-validate.md) | Data | <1s | Data validation |
| [data/cache-info](tests/data/cache-info.md) | Data | <500ms | Data inventory API |
| [data/error-invalid-symbol](tests/data/error-invalid-symbol.md) | Data (Error) | <1s | Error handling |
| [data/error-invalid-timeframe](tests/data/error-invalid-timeframe.md) | Data (Error) | <1s | Error handling |

### Backtest Tests

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [backtest/smoke](tests/backtest/smoke.md) | Backtest | <10s | Any backtest changes |
| [backtest/progress](tests/backtest/progress.md) | Backtest | ~20s | Progress tracking |
| [backtest/cancellation](tests/backtest/cancellation.md) | Backtest | ~15s | Cancellation handling |
| [backtest/api-start](tests/backtest/api-start.md) | Backtest (Integration) | ~10s | API workflow |
| [backtest/api-results](tests/backtest/api-results.md) | Backtest (Integration) | ~15s | Progress via API |
| [backtest/api-list](tests/backtest/api-list.md) | Backtest (Integration) | ~10s | API cancellation |
| [backtest/remote-start](tests/backtest/remote-start.md) | Backtest (Remote) | ~10s | Remote service |
| [backtest/remote-proxy](tests/backtest/remote-proxy.md) | Backtest (Remote) | ~10s | Backend → remote proxy |
| [backtest/remote-progress](tests/backtest/remote-progress.md) | Backtest (Remote) | ~25s | Two-level progress |
| [backtest/remote-cancel](tests/backtest/remote-cancel.md) | Backtest (Remote) | ~15s | Remote cancellation |
| [backtest/error-invalid-strategy](tests/backtest/error-invalid-strategy.md) | Backtest (Error) | ~2s | Error handling |
| [backtest/error-missing-data](tests/backtest/error-missing-data.md) | Backtest (Error) | ~2s | Error handling |
| [backtest/error-model-not-found](tests/backtest/error-model-not-found.md) | Backtest (Error) | ~2s | Error handling |

### Agent Tests

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [agent/full-cycle](tests/agent/full-cycle.md) | Agent | ~2min | Full orchestrator cycle |
| [agent/duplicate-trigger](tests/agent/duplicate-trigger.md) | Agent | ~10s | Concurrency handling |
| [agent/cancellation](tests/agent/cancellation.md) | Agent | ~15s | Cancellation propagation |
| [agent/status-api](tests/agent/status-api.md) | Agent | ~10s | Status API contract |
| [agent/metadata](tests/agent/metadata.md) | Agent | ~2min | Metadata storage |
| [agent/child-ops](tests/agent/child-ops.md) | Agent | ~2min | Child operation tracking |

### CLI Tests

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [cli/client-migration](tests/cli/client-migration.md) | CLI (Migration) | ~2min | Client consolidation M5 cleanup |
| [cli/train-command](tests/cli/train-command.md) | CLI (Restructure) | ~60s | CLI restructure M1 - train command |
| [cli/operations-workflow](tests/cli/operations-workflow.md) | CLI (Restructure) | ~90s | CLI restructure M2 - operation commands |
| [cli/information-commands](tests/cli/information-commands.md) | CLI (Restructure) | ~30s | CLI restructure M3 - list/show/validate |
| [cli/performance](tests/cli/performance.md) | CLI (Restructure) | ~10s | CLI restructure M4 - startup performance |
| [cli/research-strategy-cycle](tests/cli/research-strategy-cycle.md) | CLI (Research) | ~2min | Research agent full cycle |
| [cli/research-strategy-validation](tests/cli/research-strategy-validation.md) | CLI (Research) | ~30s | Strategy validation after research |
| [cli/url-resolution](tests/cli/url-resolution.md) | CLI (Utility) | ~5s | URL resolution for CLI commands |

## Pre-Flight Modules

| Module | Checks | Used By |
|--------|--------|---------|
| [common](preflight/common.md) | Docker, sandbox, API health | All tests |
| [training](preflight/training.md) | Strategy, data, workers | Training tests |
| [backtest](preflight/backtest.md) | Model, strategy, data, workers | Backtest tests |
| [data](preflight/data.md) | Directory access, mounts | Data tests |

## Reusable Patterns

*(To be added in later milestones)*

## Troubleshooting

| Domain | Module | Common Issues |
|--------|--------|---------------|
| [Training](troubleshooting/training.md) | Training | Model collapse, 0 trades, NaN metrics, timeouts |
| [Data](troubleshooting/data.md) | Data | Location issues, missing symbols, timeframe mismatch |
| [Environment](troubleshooting/environment.md) | Environment | Docker daemon, sandbox ports, resource exhaustion |
| [Common](troubleshooting/common.md) | General | API schema, timeouts, permissions |

## Creating New Tests

Use [TEMPLATE.md](TEMPLATE.md) when creating new test recipes.
