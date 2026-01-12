---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 8: Content Migration

**Goal:** Validate all valuable E2E content, migrate to skill structure, archive sources.

**Branch:** `feature/e2e-framework-m8`

**Builds On:** M7 (Content Harvest) + Decision Point

---

## Approach

Iterative validation-first migration in batches:

```
Phase 1: Process Validation (2-3 tests)
    Prove the migration format works before scaling

Phase 2: Pre-Validated Content
    Training tests (11) → migrate → check → archive
    Data tests (6 non-IB) → migrate → check → archive
    Troubleshooting (6 cures) → migrate → check → archive

Phase 3: Unvalidated Content (by domain)
    Backtest (13) → validate → fix if needed → migrate → check → archive
    Agent (6) → validate → fix if needed → migrate → check → archive
```

### Handling Validation Failures

When a test doesn't pass validation:

| Case | Action |
|------|--------|
| **Test is stale** (endpoint/schema changed) | Fix the test inline, then migrate |
| **Backend bug** | Fix inline if small; discuss if large |
| **Test is obsolete** (feature removed) | Document why, archive without migrating |

---

## Decision Point Output

### Tests to Migrate

**Training (11 tests) - Pre-validated:**

| ID | Test | Destination |
|----|------|-------------|
| 1.1 | Local Training Smoke | tests/training/smoke.md |
| 1.2 | Local Training Progress | tests/training/progress.md |
| 1.3 | Local Training Cancellation | tests/training/cancellation.md |
| 1.4 | Operations List & Filter | tests/training/operations-list.md |
| 2.1 | Training Host Direct Start | tests/training/host-start.md |
| 2.2 | Training Host GPU Allocation | tests/training/host-gpu.md |
| 3.1 | Host Training Integration | tests/training/host-integration.md |
| 3.2 | Host Training Two-Level Cache | tests/training/host-cache.md |
| 3.3 | Host Training Completion | tests/training/host-completion.md |
| 4.1 | Error - Invalid Strategy | tests/training/error-invalid-strategy.md |
| 4.2 | Error - Operation Not Found | tests/training/error-not-found.md |

**Data (6 tests) - Pre-validated (non-IB):**

| ID | Test | Destination |
|----|------|-------------|
| D1.1 | Cache - Get Cached Data | tests/data/cache-get.md |
| D1.2 | Cache - Cache Miss | tests/data/cache-miss.md |
| D1.3 | Cache - Partial Range | tests/data/cache-partial.md |
| D1.4 | Cache - Invalidation | tests/data/cache-invalidate.md |
| D4.1 | Error - Invalid Symbol | tests/data/error-invalid-symbol.md |
| D4.2 | Error - Invalid Timeframe | tests/data/error-invalid-timeframe.md |

**Data (7 tests) - Require IB Gateway (skip or mock):**

| ID | Test | Decision |
|----|------|----------|
| D2.1-D2.3 | IB Host Service | Skip (requires IB Gateway) |
| D3.1-D3.3 | Backend + IB Integration | Skip (requires IB Gateway) |
| D4.3 | Error - IB Connection | Skip (requires IB Gateway) |

**Backtest (13 tests) - Need validation:**

| ID | Test | Destination |
|----|------|-------------|
| B1.1 | Local Backtest Smoke | tests/backtest/smoke.md |
| B1.2 | Local Backtest Results | tests/backtest/results.md |
| B1.3 | Local Backtest Progress | tests/backtest/progress.md |
| B2.1 | API Integration Start | tests/backtest/api-start.md |
| B2.2 | API Integration Results | tests/backtest/api-results.md |
| B2.3 | API Integration List | tests/backtest/api-list.md |
| B3.1-B3.4 | Remote Backtest | tests/backtest/remote-*.md |
| B4.1-B4.3 | Error handling | tests/backtest/error-*.md |

**Agent (6 tests) - Need validation:**

| ID | Test | Destination |
|----|------|-------------|
| A1 | Full Cycle Completion | tests/agent/full-cycle.md |
| A2 | Duplicate Trigger Rejection | tests/agent/duplicate-trigger.md |
| A3 | Cancellation Propagation | tests/agent/cancellation.md |
| A4 | Status API Contract | tests/agent/status-api.md |
| A5 | Metadata Storage | tests/agent/metadata.md |
| A6 | Child Operation IDs | tests/agent/child-ops.md |

### Troubleshooting to Migrate

| Source | Pattern | Destination |
|--------|---------|-------------|
| E2E_CHALLENGES_ANALYSIS.md | 0 trades / 100% accuracy | troubleshooting/training.md |
| E2E_CHALLENGES_ANALYSIS.md | Model collapse | troubleshooting/training.md |
| E2E_CHALLENGES_ANALYSIS.md | Docker daemon issues | troubleshooting/environment.md |
| E2E_CHALLENGES_ANALYSIS.md | Sandbox port confusion | troubleshooting/environment.md |
| E2E_CHALLENGES_ANALYSIS.md | Data location issues | troubleshooting/data.md |
| E2E_CHALLENGES_ANALYSIS.md | API schema differences | troubleshooting/common.md |

### Content to Archive

| Document | Reason |
|----------|--------|
| SCENARIOS.md | Content migrated to tests/ |
| TESTING_GUIDE.md | Content migrated to preflight/ and recipes/ |

### Keep in Place

| Document | Reason |
|----------|--------|
| E2E_CHALLENGES_ANALYSIS.md | Historical debugging record |
| agent-orchestrator-e2e.md | Source for agent tests until migrated |

---

## Phase 1: Process Validation

**Goal:** Prove migration format works with 2-3 known-good tests.

### Task 8.1: Pilot Migration (2-3 tests)

**File(s):** `.claude/skills/e2e-testing/tests/training/{smoke,progress,cancellation}.md`

**Type:** CODING

**Description:**
Migrate 3 training tests to validate the migration process before scaling.

**Tests to migrate:**
1. 1.1 Local Training Smoke (simplest)
2. 1.2 Local Training Progress (has more complexity)
3. 1.3 Local Training Cancellation (tests operations)

**Migration Process:**

For each test:

1. **Read source** from SCENARIOS.md
2. **Transform to template:**
   - Add standard frontmatter
   - Add pre-flight references
   - Add sanity checks section
   - Update URLs for sandbox: `${KTRDR_API_PORT:-8000}`
   - Add troubleshooting links
3. **Write to** `tests/training/{name}.md`
4. **Update SKILL.md** catalog

**Check step:**

```bash
# Invoke designer - should find the migrated tests
# Query: "training smoke test"
# Expected: Returns tests/training/smoke.md

# Invoke tester on migrated test
# Expected: Test executes successfully
```

**Archive step:**
- Do NOT archive yet - wait until all tests migrated

**Acceptance Criteria:**
- [ ] 3 tests migrated with correct template
- [ ] Designer finds all 3 tests
- [ ] Tester executes all 3 successfully
- [ ] Sanity checks included
- [ ] Sandbox-compatible URLs

---

## Phase 2: Pre-Validated Content

### Task 8.2: Migrate Remaining Training Tests (8 tests)

**File(s):** `.claude/skills/e2e-testing/tests/training/*.md`

**Type:** CODING

**Description:**
Migrate remaining 8 training tests using validated process from Task 8.1.

**Tests:**
- 1.4, 2.1, 2.2, 3.1, 3.2, 3.3, 4.1, 4.2

**Check step:**
- Designer finds all training tests
- Tester executes a sample (e.g., 4.1 error handling)

**Acceptance Criteria:**
- [ ] All 11 training tests migrated
- [ ] Designer finds all tests
- [ ] Sample tests execute correctly

---

### Task 8.3: Migrate Data Tests (6 tests)

**File(s):** `.claude/skills/e2e-testing/tests/data/*.md`

**Type:** CODING

**Description:**
Migrate 6 non-IB data tests.

**Tests:**
- D1.1-D1.4 (cache operations)
- D4.1-D4.2 (error handling)

**Skip:** D2.x, D3.x, D4.3 (require IB Gateway)

**Check step:**
- Designer finds data tests
- Tester executes cache test

**Acceptance Criteria:**
- [ ] 6 data tests migrated
- [ ] Designer finds all tests
- [ ] Cache test executes correctly

---

### Task 8.4: Migrate Troubleshooting Content

**File(s):** `.claude/skills/e2e-testing/troubleshooting/*.md`

**Type:** CODING

**Description:**
Migrate 6 troubleshooting patterns from E2E_CHALLENGES_ANALYSIS.md.

**Files to create/update:**
- `troubleshooting/training.md` - 0 trades, model collapse
- `troubleshooting/environment.md` - Docker, sandbox ports
- `troubleshooting/data.md` - Data location issues
- `troubleshooting/common.md` - API schema differences

**Transform to symptom→cure format:**

```markdown
## [Problem Name]

**Symptom:**
- Bullet list of observable symptoms

**Cause:** Brief explanation

**Cure:**
```bash
# Commands to fix
```

**Prevention:** How to avoid in future
```

**Check step:**
- Troubleshooting files referenced from test templates
- Cures are actionable

**Acceptance Criteria:**
- [ ] All 6 patterns migrated
- [ ] Symptom→cure format used
- [ ] Prevention tips included

---

### Task 8.5: Create Pre-Flight Modules

**File(s):** `.claude/skills/e2e-testing/preflight/{training,backtest,data}.md`

**Type:** CODING

**Description:**
Create domain-specific pre-flight modules.

**Modules:**
- `preflight/training.md` - Strategy exists, training data available
- `preflight/backtest.md` - Model exists, backtest worker available
- `preflight/data.md` - Data directory accessible

**Check step:**
- Pre-flight modules load correctly
- Checks are executable

**Acceptance Criteria:**
- [ ] 3 pre-flight modules created
- [ ] Each has executable checks
- [ ] Cures included for failures

---

## Phase 3: Unvalidated Content

### Task 8.6: Validate and Migrate Backtest Tests

**File(s):** `.claude/skills/e2e-testing/tests/backtest/*.md`

**Type:** MIXED (validation + coding)

**Description:**
Validate 13 backtest scenarios, fix issues, then migrate passing tests.

**Process:**

1. **Validate each scenario:**
   - Run the test commands from SCENARIOS.md
   - Record: PASS, FAIL (stale), FAIL (backend bug), OBSOLETE

2. **For failures:**
   - Stale test: Fix inline (update endpoint, schema)
   - Backend bug: Fix if small, discuss if large
   - Obsolete: Document reason, skip migration

3. **Migrate passing tests:**
   - Same process as training tests
   - Update SKILL.md catalog

4. **Check:**
   - Designer finds backtest tests
   - Tester executes sample

**Batch if needed:** If >5 tests need fixes, split into sub-batches.

**Acceptance Criteria:**
- [ ] All 13 scenarios validated
- [ ] Passing tests migrated
- [ ] Failures documented (reason + fix or skip)
- [ ] Designer finds backtest tests

---

### Task 8.7: Validate and Migrate Agent Tests

**File(s):** `.claude/skills/e2e-testing/tests/agent/*.md`

**Type:** MIXED (validation + coding)

**Description:**
Verify agent orchestrator is active, validate 6 scenarios, migrate if applicable.

**Process:**

1. **Check orchestrator status:**
   ```bash
   # Is agent orchestrator still in use?
   grep -r "agent_research" ktrdr/
   curl http://localhost:8000/api/v1/agent/status
   ```

2. **If active:** Validate and migrate tests
3. **If deprecated:** Document, archive source without migrating

**Acceptance Criteria:**
- [ ] Orchestrator status confirmed
- [ ] If active: tests migrated
- [ ] If deprecated: documented

---

## Phase 4: Archive

### Task 8.8: Archive Source Documents

**File(s):** `docs/testing/archive/`

**Type:** CODING

**Description:**
Archive source documents now that migration is complete.

**Process:**

1. **Create archive:**
   ```bash
   mkdir -p docs/testing/archive
   ```

2. **Move superseded files:**
   ```bash
   mv docs/testing/SCENARIOS.md docs/testing/archive/
   mv docs/testing/TESTING_GUIDE.md docs/testing/archive/
   ```

3. **Add README:**
   ```markdown
   # Archived Testing Documents

   Superseded by `.claude/skills/e2e-testing/`

   **Do Not Update** - These files are frozen.
   ```

**Acceptance Criteria:**
- [ ] Archive directory created
- [ ] SCENARIOS.md archived
- [ ] TESTING_GUIDE.md archived
- [ ] README explains why

---

## E2E Test Scenario

**Purpose:** Verify complete migration is discoverable and usable.

**Duration:** ~10 minutes

**Test Steps:**

```markdown
1. Query designer for "training smoke test" → finds tests/training/smoke.md
2. Query designer for "backtest error handling" → finds tests/backtest/error-*.md
3. Query designer for "data cache" → finds tests/data/cache-*.md
4. Execute tester on training/smoke.md → PASS
5. Execute tester on backtest/smoke.md → PASS
6. Verify archived docs not referenced in workflow
```

**Success Criteria:**
- [ ] Designer finds tests across all domains
- [ ] Tester executes tests successfully
- [ ] Pre-flight checks work
- [ ] Troubleshooting content accessible
- [ ] No references to archived docs

---

## Milestone 8 Completion Checklist

### All Tasks Complete
- [ ] Task 8.1: Pilot migration (3 tests)
- [ ] Task 8.2: Remaining training tests (8 tests)
- [ ] Task 8.3: Data tests (6 tests)
- [ ] Task 8.4: Troubleshooting content (6 patterns)
- [ ] Task 8.5: Pre-flight modules (3 modules)
- [ ] Task 8.6: Backtest tests (up to 13 tests)
- [ ] Task 8.7: Agent tests (up to 6 tests)
- [ ] Task 8.8: Archive source documents

### Totals

| Category | Migrated | Skipped | Fixed |
|----------|----------|---------|-------|
| Training | 11 | 0 | - |
| Data | 6 | 7 (IB) | - |
| Backtest | TBD | TBD | TBD |
| Agent | TBD | TBD | TBD |
| Troubleshooting | 6 | 0 | - |
| Pre-flight | 3 | 0 | - |

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed
- [ ] SKILL.md catalog complete
- [ ] Designer finds all migrated tests
- [ ] Tester executes samples successfully

---

## Framework Complete

After M8, the E2E testing framework is fully operational with validated, migrated content.
