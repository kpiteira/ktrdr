---
name: ke2e
description: Knowledge base for E2E test design and execution against project sandboxes. Used by ke2e-test-scout (catalog lookup), ke2e-test-designer (new test design), and ke2e-test-runner (execution) agents.
metadata:
  version: "1.0.0"
---

# E2E Testing Skill — ktrdr

## Purpose

Project-local E2E test catalog for ktrdr. Framework docs (TEMPLATE.md, FAILURE_CATEGORIES.md) come from the global ke2e skill (devops-ai). This file provides the test catalog, preflight modules, and troubleshooting guides specific to ktrdr.

Used by:
- **ke2e-test-scout** agent — Fast catalog lookup during planning
- **ke2e-test-designer** agent — Design new tests when no match exists
- **ke2e-test-runner** agent — Execute tests and report results

## Test Catalog (83 recipes)

### Training (20 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [training/smoke](tests/training/smoke.md) | Training | <30s | Any training changes |
| [training/progress](tests/training/progress.md) | Training | ~60-90s | Progress tracking, metrics |
| [training/cancellation](tests/training/cancellation.md) | Training | ~30s | Cancellation handling |
| [training/operations-list](tests/training/operations-list.md) | Training | ~5s | Operations API, list/filter |
| [training/host-start](tests/training/host-start.md) | Training (Host) | ~5s | Host service standalone |
| [training/host-gpu](tests/training/host-gpu.md) | Training (Host) | ~3s | GPU allocation |
| [training/host-integration](tests/training/host-integration.md) | Training (Host) | ~5s | Backend → host proxy |
| [training/host-cache](tests/training/host-cache.md) | Training (Host) | ~5s | Operation ID mapping |
| [training/host-completion](tests/training/host-completion.md) | Training (Host) | ~5s | Full cycle through proxy |
| [training/error-invalid-strategy](tests/training/error-invalid-strategy.md) | Training (Error) | ~1s | Error handling |
| [training/error-not-found](tests/training/error-not-found.md) | Training (Error) | ~1s | Error handling |
| [training/context-classifier](tests/training/context-classifier.md) | Training (Feature) | ~60s | Context/regime classifier |
| [training/multi-timeframe-backtest](tests/training/multi-timeframe-backtest.md) | Training (Feature) | ~2min | Multi-TF training |
| [training/focal-loss-classification](tests/training/focal-loss-classification.md) | Training (Feature) | ~2min | Focal loss wiring |
| [training/triple-barrier-labels](tests/training/triple-barrier-labels.md) | Training (Feature) | ~2min | CUSUM filter + uniqueness |
| [training/regime-classifier](tests/training/regime-classifier.md) | Training (Feature) | ~2min | Multi-scale regime |
| [training/fred-context-data](tests/training/fred-context-data.md) | Training (Feature) | ~2min | FRED context data |
| [training/gaussian-hybrid-dead-zone-elimination](tests/training/gaussian-hybrid-dead-zone-elimination.md) | Training (Feature) | ~2min | Gaussian hybrid |
| [training/experiment-1-tb-vs-forward-return](tests/training/experiment-1-tb-vs-forward-return.md) | Training (Experiment) | ~5min | TB vs forward return |
| [training/lstm-temporal-model](tests/training/lstm-temporal-model.md) | Training (Feature) | ~3min | LSTM temporal model |

### Backtest (16 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [backtest/smoke](tests/backtest/smoke.md) | Backtest | <10s | Any backtest changes |
| [backtest/progress](tests/backtest/progress.md) | Backtest | ~20s | Progress tracking |
| [backtest/cancellation](tests/backtest/cancellation.md) | Backtest | ~15s | Cancellation handling |
| [backtest/api-start](tests/backtest/api-start.md) | Backtest (API) | ~10s | API workflow |
| [backtest/api-results](tests/backtest/api-results.md) | Backtest (API) | ~15s | Progress via API |
| [backtest/api-list](tests/backtest/api-list.md) | Backtest (API) | ~10s | API cancellation |
| [backtest/remote-start](tests/backtest/remote-start.md) | Backtest (Remote) | ~10s | Remote service |
| [backtest/remote-proxy](tests/backtest/remote-proxy.md) | Backtest (Remote) | ~10s | Backend → remote proxy |
| [backtest/remote-progress](tests/backtest/remote-progress.md) | Backtest (Remote) | ~25s | Two-level progress |
| [backtest/remote-cancel](tests/backtest/remote-cancel.md) | Backtest (Remote) | ~15s | Remote cancellation |
| [backtest/error-invalid-strategy](tests/backtest/error-invalid-strategy.md) | Backtest (Error) | ~2s | Error handling |
| [backtest/error-missing-data](tests/backtest/error-missing-data.md) | Backtest (Error) | ~2s | Error handling |
| [backtest/error-model-not-found](tests/backtest/error-model-not-found.md) | Backtest (Error) | ~2s | Error handling |
| [backtest/context-data-multi-provider](tests/backtest/context-data-multi-provider.md) | Backtest (Feature) | ~2min | Multi-provider context |
| [backtest/ensemble-regime-routed](tests/backtest/ensemble-regime-routed.md) | Backtest (Feature) | ~3min | Regime-routed ensemble |
| [backtest/execution-realism](tests/backtest/execution-realism.md) | Backtest (Feature) | ~2min | Execution realism |
| [backtest/lstm-temporal-backtest](tests/backtest/lstm-temporal-backtest.md) | Backtest (Feature) | ~3min | LSTM temporal backtest |

### Backtesting Integration (2 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [backtesting/context-gated-ensemble](tests/backtesting/context-gated-ensemble.md) | Integration | ~5min | Context gate + ensemble |
| [backtesting/regression-context-gated-ensemble](tests/backtesting/regression-context-gated-ensemble.md) | Integration | ~5min | Regression + context gate |

### CLI (16 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [cli/train-command](tests/cli/train-command.md) | CLI | ~60s | Train command |
| [cli/operations-workflow](tests/cli/operations-workflow.md) | CLI | ~90s | Operation commands |
| [cli/information-commands](tests/cli/information-commands.md) | CLI | ~30s | List/show/validate |
| [cli/performance](tests/cli/performance.md) | CLI | ~10s | Startup performance |
| [cli/client-migration](tests/cli/client-migration.md) | CLI (Migration) | ~2min | Client consolidation |
| [cli/research-strategy-cycle](tests/cli/research-strategy-cycle.md) | CLI (Research) | ~2min | Research full cycle |
| [cli/research-strategy-validation](tests/cli/research-strategy-validation.md) | CLI (Research) | ~30s | Strategy validation |
| [cli/url-resolution](tests/cli/url-resolution.md) | CLI (Utility) | ~5s | URL resolution |
| [cli/regime-analyze](tests/cli/regime-analyze.md) | CLI | ~30s | Regime analysis |
| [cli/workers-command](tests/cli/workers-command.md) | CLI | ~5s | Workers command |
| [cli/context-analyze](tests/cli/context-analyze.md) | CLI (Feature) | ~30s | Context gate analysis |
| [cli/kinfra-foundation](tests/cli/kinfra-foundation.md) | CLI (kinfra) | ~30s | kinfra foundation |
| [cli/kinfra-spec-workflow](tests/cli/kinfra-spec-workflow.md) | CLI (kinfra) | ~60s | kinfra spec |
| [cli/kinfra-impl-workflow](tests/cli/kinfra-impl-workflow.md) | CLI (kinfra) | ~2min | kinfra impl |
| [cli/kinfra-done-workflow](tests/cli/kinfra-done-workflow.md) | CLI (kinfra) | ~60s | kinfra done |
| [cli/kinfra-slot-provisioning](tests/cli/kinfra-slot-provisioning.md) | CLI (kinfra) | ~2min | Slot provisioning |

### Agent (6 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [agent/full-cycle](tests/agent/full-cycle.md) | Agent | ~2min | Full orchestrator cycle |
| [agent/duplicate-trigger](tests/agent/duplicate-trigger.md) | Agent | ~10s | Concurrency handling |
| [agent/cancellation](tests/agent/cancellation.md) | Agent | ~15s | Cancellation propagation |
| [agent/status-api](tests/agent/status-api.md) | Agent | ~10s | Status API contract |
| [agent/metadata](tests/agent/metadata.md) | Agent | ~2min | Metadata storage |
| [agent/child-ops](tests/agent/child-ops.md) | Agent | ~2min | Child operation tracking |

### Agent SDK (3 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [agents/design-agent-brief-to-strategy](tests/agents/design-agent-brief-to-strategy.md) | Agent SDK | ~2min | Design agent |
| [agents/assessment-agent-metrics-to-verdict](tests/agents/assessment-agent-metrics-to-verdict.md) | Agent SDK | ~2min | Assessment agent |
| [agents/sdk-invocation-in-container](tests/agents/sdk-invocation-in-container.md) | Agent SDK | ~30s | SDK in container |

### Data (6 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [data/cache-get](tests/data/cache-get.md) | Data | <3s | Cache loading |
| [data/cache-range](tests/data/cache-range.md) | Data | <100ms | Metadata queries |
| [data/cache-validate](tests/data/cache-validate.md) | Data | <1s | Data validation |
| [data/cache-info](tests/data/cache-info.md) | Data | <500ms | Data inventory |
| [data/error-invalid-symbol](tests/data/error-invalid-symbol.md) | Data (Error) | <1s | Error handling |
| [data/error-invalid-timeframe](tests/data/error-invalid-timeframe.md) | Data (Error) | <1s | Error handling |

### Workers (4 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [workers/config-validation](tests/workers/config-validation.md) | Workers | ~10s | Worker config |
| [workers/deprecated-names](tests/workers/deprecated-names.md) | Workers | ~5s | Deprecated names |
| [workers/port-defaults](tests/workers/port-defaults.md) | Workers | ~5s | Port defaults |
| [workers/startup-registration](tests/workers/startup-registration.md) | Workers | ~15s | Worker registration |

### Infrastructure (2 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [infra/backend-lazy-imports](tests/infra/backend-lazy-imports.md) | Infrastructure | ~30s | Import performance |
| [infra/image-torch-availability](tests/infra/image-torch-availability.md) | Infrastructure | ~10s | Torch in container |

### Regression (1 test)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [regression/full-cycle](tests/regression/full-cycle.md) | Regression | ~5min | Full train + backtest |

### Migration Validation (4 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [indicators/registry-migration-complete](tests/indicators/registry-migration-complete.md) | Migration | ~30s | Indicator registry |
| [fuzzy/migration-complete](tests/fuzzy/migration-complete.md) | Migration | ~30s | Fuzzy registry |
| [codebase/m4-cleanup-complete](tests/codebase/m4-cleanup-complete.md) | Migration | ~30s | Cleanup validation |
| [skills/m5-documentation-complete](tests/skills/m5-documentation-complete.md) | Migration | ~10s | Documentation |

### Other (3 tests)

| Test | Category | Duration | Use When |
|------|----------|----------|----------|
| [evolution/single-generation](tests/evolution/single-generation.md) | Evolution | ~3min | Evolution cycle |
| [mcp/strategy-save-roundtrip](tests/mcp/strategy-save-roundtrip.md) | MCP | ~30s | MCP strategy save |

## Pre-Flight Modules

| Module | Checks | Used By |
|--------|--------|---------|
| [common](preflight/common.md) | Docker, sandbox, API health | All tests |
| [training](preflight/training.md) | Strategy, data, workers | Training tests |
| [backtest](preflight/backtest.md) | Model, strategy, data, workers | Backtest tests |
| [data](preflight/data.md) | Directory access, mounts | Data tests |
| [workers](preflight/workers.md) | Worker endpoints, registration | Worker tests |

## Troubleshooting

| Domain | Module | Common Issues |
|--------|--------|---------------|
| [Training](troubleshooting/training.md) | Training | Model collapse, 0 trades, NaN metrics, timeouts |
| [Data](troubleshooting/data.md) | Data | Location issues, missing symbols, timeframe mismatch |
| [Environment](troubleshooting/environment.md) | Environment | Docker daemon, sandbox ports, resource exhaustion |
| [Common](troubleshooting/common.md) | General | API schema, timeouts, permissions |

## Creating New Tests

Use the global ke2e TEMPLATE.md when creating new test recipes. See global ke2e FAILURE_CATEGORIES.md for categorizing failures.

## What "Real E2E" Means

E2E tests make real calls against a running sandbox container. Not mocked.

- Real API calls to container endpoints (curl, httpx)
- Real processing inside the container
- Real state changes observed via docker exec or API response
- Observable outcomes asserted on real data

Integration tests with mocked externals are NOT E2E.
