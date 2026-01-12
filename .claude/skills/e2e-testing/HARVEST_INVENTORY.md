# E2E Content Harvest Inventory

**Generated:** 2026-01-11
**Sources Processed:** 10 documents (Batch 1) + sampling of 30 additional
**Status:** COMPLETE (stopped at diminishing returns)

---

## Executive Summary

**Finding:** The docs/testing/ directory contains ~80-90% of actionable E2E content. Remaining 120+ documents contain mostly implementation plans with brief E2E sections that duplicate existing patterns.

**High-Value Sources (migrate these):**
1. SCENARIOS.md - 37 complete test scenarios
2. TESTING_GUIDE.md - All building blocks
3. E2E_CHALLENGES_ANALYSIS.md - 7 troubleshooting patterns

**Decision:** Stopped processing at diminishing returns. Additional documents yield:
- Implementation plans with 3-10 line E2E sections (duplicative)
- Design validation scenarios (already covered by test scripts)
- Handoff documents (some troubleshooting, but patterns already captured)

---

## Summary

| Domain | Content Items | Tests | Troubleshooting | Stale |
|--------|---------------|-------|-----------------|-------|
| Training | 18 | 11 scenarios | 7 issues | Minimal |
| Data | 13 | 13 scenarios | 4 issues | Minimal |
| Backtest | 13 | 13 scenarios (untested) | 0 | Some |
| Agent | 8 | 6 scenarios | 2 issues | Unknown |
| Cross-Cutting | 3 | N/A | 7 challenges | Current |

---

## HIGH VALUE: docs/testing/ (9 files)

### SCENARIOS.md - Test Catalog (CROWN JEWEL)

**Content Type:** Complete Test Catalog with Actual Results
**Lines:** 2316
**Value:** EXTREMELY HIGH - Already formatted as runnable scenarios

**Summary:**
- 37 complete test scenarios with curl commands, expected/actual results
- Training: 11 scenarios (ALL PASSED 2025-10-25)
- Data: 13 scenarios (12 PASSED, 1 documented, 2025-10-28)
- Backtest: 13 scenarios (NOT YET TESTED - Phase 2+)

**Key Content:**

Training Scenarios (11):
- 1.1: Local Training - Smoke Test (~2s)
- 1.2: Local Training - Progress Monitoring (~62s)
- 1.3: Local Training - Cancellation (~30s)
- 1.4: Operations List & Filter (~5s)
- 2.1: Training Host - Direct Start (~3s)
- 2.2: Training Host - GPU Allocation (~1s)
- 3.1: Host Training - Integration (~2s)
- 3.2: Host Training - Two-Level Cache (~5s)
- 3.3: Host Training - Completion (~5s)
- 4.1: Error - Invalid Strategy (~1s)
- 4.2: Error - Operation Not Found (~1s)

Data Scenarios (13):
- D1.1-D1.4: Cache operations (all passed)
- D2.1-D2.3: IB Host Service (all passed, 1 bug fixed)
- D3.1-D3.3: Backend + IB Integration (all passed)
- D4.1-D4.3: Error handling (2 passed, 1 documented)

Backtest Scenarios (13):
- B1.1-B1.3: Local Backtest (not tested)
- B2.1-B2.3: API Integration (B2.1 passed)
- B3.1-B3.4: Remote Backtest (not tested)
- B4.1-B4.3: Error handling (not tested)

**Staleness Assessment:**
- [x] Training scenarios: Still valid (tested 2025-10-25)
- [x] Data scenarios: Still valid (tested 2025-10-28)
- [ ] Backtest scenarios: May need endpoint updates

**Migration Priority:** HIGH - Already in perfect format for e2e-tester

---

### TESTING_GUIDE.md - Building Blocks

**Content Type:** API Reference and Test Patterns
**Lines:** 756
**Value:** HIGH - Essential building blocks for all tests

**Summary:**
Comprehensive reference for creating and executing test scenarios.

**Key Content:**

1. **Service URLs & Ports** (lines 7-12)
   - Backend API: `http://localhost:8000/api/v1`
   - Training Host: `http://localhost:5002`
   - IB Host: `http://localhost:5001`

2. **API Endpoints** (lines 14-127)
   - Training: POST /trainings/start (note: plural!)
   - Data Cache: GET /data/{symbol}/{timeframe}
   - Data Acquisition: POST /data/acquire/download
   - Backtest: POST /backtests/start
   - Operations: GET/DELETE /operations/{id}

3. **Mode Switching Scripts** (lines 140-152)
   - `./scripts/switch-training-mode.sh local|host`

4. **Log Strings for Verification** (lines 186-242)
   - Local bridge: "Registered local training bridge for operation {id}"
   - Remote proxy: "Registered remote proxy for operation {id} → host {host_id}"
   - NO event loop error: should never see "no running event loop"

5. **Calibrated Test Data** (lines 263-315)
   - Training smoke test: EURUSD 1d 2024, 258 samples, ~2s
   - Training progress: EURUSD 5m 2023-2025, 147K samples, ~62s
   - Data download: EURUSD 1h Dec 2024, ~720 bars, 30-90s

6. **Common Mistakes to Avoid** (lines 444-457)
   - Wrong endpoint: /training/start → /trainings/start
   - Wrong status: "started" → "training_started"
   - Missing mode: must include "mode":"tail" for IB download

7. **Troubleshooting** (lines 592-698)
   - Download uses cache instead of IB
   - 0 trades issue
   - Progress not updating
   - IB service connection issues

**Staleness Assessment:**
- [x] Core content valid
- [x] Endpoints current (Phase 2+ references included)
- [x] Calibrated parameters still good

**Migration Priority:** HIGH - Reference material for all E2E tests

---

### E2E_CHALLENGES_ANALYSIS.md - Troubleshooting Patterns

**Content Type:** Debugging Patterns and Root Cause Analysis
**Lines:** 351
**Value:** HIGH - Real debugging sessions with symptom→cure mappings

**Summary:**
7 challenges encountered during M6 validation with root cause analysis.

**Key Content:**

| Challenge | Symptom | Root Cause | Lesson |
|-----------|---------|------------|--------|
| 0 trades | 100% accuracy, 0 trades | Zigzag threshold too high for forex | Validate label distribution first |
| Docker issues | Daemon errors, port conflicts | Corrupted Docker daemon | Verify Docker health before tests |
| Port confusion | 404s, connection refused | Sandbox uses different ports | Auto-detect environment |
| API schema | Validation errors | symbols[] vs symbol singular | Client library to abstract |
| Data location | "Data not found" | Different paths local vs Docker | Consistent data paths |
| Model collapse | Same prediction for all inputs | Class imbalance | Check prediction diversity |
| Slow feedback | Had to wait for full training | No early validation | Pre-flight checks |

**Proposed Improvements:**
1. Pre-flight checks (label distribution, Docker health)
2. Quick smoke test (2 epochs before full training)
3. Environment abstraction (port detection)
4. Diagnostic output (capture intermediate state)

**Staleness Assessment:**
- [x] All patterns still applicable
- [x] Already incorporated into M3/M4 design

**Migration Priority:** HIGH - Core troubleshooting patterns for cure system

---

### agent-orchestrator-e2e.md - Agent Orchestrator Tests

**Content Type:** E2E Test Scripts
**Lines:** 439
**Value:** MEDIUM-HIGH - Complete bash test scripts for agent orchestrator

**Summary:**
6 test scenarios for agent research orchestrator with bash scripts.

**Key Tests:**
1. Full Cycle Completion (~2 min)
2. Duplicate Trigger Rejection (~5s)
3. Cancellation Propagation (~10s per phase)
4. Status API Contract
5. Metadata Storage
6. Child Operation IDs

**Staleness Assessment:**
- [ ] Unknown - need to verify agent orchestrator is still in use

**Migration Priority:** MEDIUM - Specialized agent testing

---

### e2e-local-training-pull.md - Pull Architecture Validation

**Content Type:** Comprehensive E2E Guide
**Lines:** 1213
**Value:** MEDIUM-HIGH - Detailed validation for M1 pull architecture

**Summary:**
7 scenarios for validating pull-based operations architecture.

**Scenarios:**
1. Start Training and Verify Operation Created
2. Progress Updates via Pull
3. Metrics Collection
4. Training Completion
5. Bridge Registration Verification
6. Metrics Cursor Behavior
7. Error-Free Execution

**Key Patterns:**
- Bridge registration logging
- Cache hit/miss behavior
- Cursor-based metrics retrieval
- Expected log sequences

**Staleness Assessment:**
- [x] Still applicable (pull architecture is current)
- [x] Logging patterns still valid

**Migration Priority:** MEDIUM - Training-specific validation

---

### AGENT_E2E_TESTING.md - Anthropic API Testing

**Content Type:** Testing Guide
**Lines:** 254
**Value:** MEDIUM - Agent-specific E2E testing

**Summary:**
Guidance for testing with real Anthropic API vs mock invokers.

**Key Content:**
- Mock vs Real test distinction
- Environment setup (DATABASE_URL, ANTHROPIC_API_KEY)
- Cost considerations ($0.05-0.30 per test)
- CI/CD integration patterns

**Staleness Assessment:**
- [ ] Model names may have changed (claude-sonnet-4)
- [x] Overall patterns still valid

**Migration Priority:** LOW - Specialized agent testing

---

### phase-6-manual-validation-checklist.md - Feature ID Validation

**Content Type:** Manual Validation Checklist
**Lines:** 557
**Value:** MEDIUM - Systematic validation procedure

**Summary:**
Checklist for feature_id system validation (Phase 6 of indicator standardization).

**Sections:**
1. Strategy Configuration Validation (4 tests)
2. Training Pipeline Validation (4 tests)
3. Error Handling Validation (2 tests)
4. Integration Testing (2 tests)
5. Documentation Validation (2 tests)
6. Performance Validation (2 tests)

**Staleness Assessment:**
- [x] Still applicable for v3 strategies
- [ ] May be superseded by newer validation

**Migration Priority:** LOW - Feature-specific validation

---

### V2 Cleanup Documents (3 files)

**Content Type:** Validation Evidence
**Value:** LOW - Historical validation, not active tests

**Summary:**
Documentation proving v2 code was removed and v3 is functional.

**Migration Priority:** ARCHIVE - Historical reference only

---

## Batches Sampled (Diminishing Returns)

### Batch 2: docs/agentic/mvp/ (21 files) - SAMPLED
**Finding:** Contains design validation scenarios (5 in scenarios.md) but these duplicate agent-orchestrator-e2e.md. Implementation plans have brief E2E sections (3-10 lines) already covered by TESTING_GUIDE.md patterns.

### Batch 3: docs/architecture/checkpoint/ (9 files) - SAMPLED
**Finding:** Contains MILESTONE_TEST_REQUIREMENTS.md (test design framework) - useful reference but not test scenarios. Other files are implementation plans with standard E2E sections.

### Remaining 100+ documents - NOT PROCESSED
**Reason:** Diminishing returns. Patterns already captured from high-value sources.

---

## Staleness Summary

| Issue | Documents Affected | Remediation |
|-------|-------------------|-------------|
| Backtest scenarios not tested | SCENARIOS.md | Run Phase 2+ tests |
| Agent orchestrator status unknown | agent-orchestrator-e2e.md | Verify still active |
| Model names may have changed | AGENT_E2E_TESTING.md | Update to claude-opus-4.5 |

---

## Migration Candidates

### High Priority (Proven Value)
1. **SCENARIOS.md** → tests/ directory structure
   - training/smoke.md, training/progress.md, etc.
   - data/cache.md, data/ib-download.md, etc.
   - backtest/ (after Phase 2+ testing)

2. **E2E_CHALLENGES_ANALYSIS.md** → troubleshooting/
   - Pre-flight check patterns
   - Symptom→cure mappings for cure system

3. **TESTING_GUIDE.md** → recipes/building-blocks.md
   - API reference
   - Log verification patterns
   - Calibrated test data

### Medium Priority
4. agent-orchestrator-e2e.md → tests/agent/
5. e2e-local-training-pull.md → tests/training/ (architecture validation)

### Low Priority (May Skip)
6. AGENT_E2E_TESTING.md → specialized, may archive
7. phase-6-manual-validation-checklist.md → feature-specific
8. V2 cleanup docs → archive only
