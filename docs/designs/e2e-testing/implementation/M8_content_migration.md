---
design: ../DESIGN.md
architecture: ../ARCHITECTURE.md
---

# Milestone 8: Content Migration

**Goal:** Migrate curated content from M7 harvest into the e2e-testing skill structure.

**Branch:** `feature/e2e-framework-m8`

**Builds On:** M7 (Content Harvest) + Decision Point

**PREREQUISITE:** Decision Point review with Karl must be completed before starting this milestone.

---

## E2E Test Scenario

**Purpose:** Verify migrated content is discoverable and usable.

**Duration:** ~5 minutes

**Prerequisites:**
- M7 complete (inventory exists)
- Decision Point completed (curriculum agreed)

**Test Steps:**

```markdown
1. Invoke e2e-test-designer with various validation needs
2. Designer finds appropriate tests from migrated content
3. Invoke e2e-tester on migrated tests
4. Tests execute correctly
5. Old docs archived
```

**Success Criteria:**
- [ ] Designer finds migrated tests
- [ ] Tester executes migrated tests successfully
- [ ] No references to archived docs remain in workflow

---

## Decision Point Output Required

Before starting M8, document the agreed curriculum:

```markdown
## Agreed Curriculum

### Tests to Migrate

| Source | Destination | Priority |
|--------|-------------|----------|
| SCENARIOS.md 1.1 | tests/training/smoke.md | High |
| SCENARIOS.md 1.2 | tests/training/progress.md | High |
| SCENARIOS.md B1.1 | tests/backtest/smoke.md | High |
| ... | ... | ... |

### Troubleshooting to Migrate

| Source | Destination |
|--------|-------------|
| E2E_CHALLENGES_ANALYSIS.md | troubleshooting/training.md |
| ... | ... |

### Content to Archive (Not Migrate)

| Document | Reason |
|----------|--------|
| ... | Outdated / Duplicated / Superseded |

### Additional Tests Needed

| Test | Purpose | Building Blocks |
|------|---------|-----------------|
| ... | ... | ... |
```

---

## Task 8.1: Migrate Test Recipes

**File(s):** `.claude/skills/e2e-testing/tests/{category}/{name}.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Migrate agreed test recipes from SCENARIOS.md into the skill structure.

**Migration Process:**

For each test in the agreed curriculum:

1. **Read source content** from SCENARIOS.md

2. **Transform to new template:**
   - Add standard frontmatter
   - Add pre-flight references
   - Add sanity checks section (critical!)
   - Update commands for sandbox compatibility (${API_PORT})
   - Add troubleshooting section

3. **Write to destination** in tests/{category}/

4. **Update SKILL.md catalog** with new entry

**Example Migration:**

**Source (SCENARIOS.md 1.2):**
```markdown
## 1.2: Local Training - Progress Monitoring

**Category**: Backend Isolated
**Duration**: ~62 seconds

### Test Data
{json}

### Commands
{commands}

### Expected Results
{results}
```

**Destination (tests/training/progress.md):**
```markdown
# Test: training/progress

**Purpose:** Validate progress updates during training
**Duration:** ~60 seconds
**Category:** Training

---

## Pre-Flight Checks

**Required modules:**
- [common](../../preflight/common.md)

**Test-specific checks:**
- [ ] Large dataset available (EURUSD 5m, 2 years)

---

## Test Data

```json
{same as source, but with sandbox-compatible URLs}
```

**Why this data:** Needs enough samples for progress updates (~147K samples, ~60s training)

---

## Execution Steps

{transformed from source}

---

## Success Criteria

{from source, structured as checklist}

---

## Sanity Checks

**CRITICAL:**
- [ ] Accuracy < 99%
- [ ] Progress updates received (at least 3)
- [ ] Loss changes over time

---

## Troubleshooting

{link to troubleshooting/training.md}
```

**Acceptance Criteria:**
- [ ] All agreed tests migrated
- [ ] Template structure followed
- [ ] Sanity checks added
- [ ] Sandbox-compatible (${API_PORT})
- [ ] SKILL.md catalog updated

---

## Task 8.2: Migrate Troubleshooting Content

**File(s):** `.claude/skills/e2e-testing/troubleshooting/{domain}.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Migrate troubleshooting content from E2E_CHALLENGES_ANALYSIS.md and other sources.

**Migration Process:**

1. **Read E2E_CHALLENGES_ANALYSIS.md**
2. **Transform each challenge to symptom→cure format**
3. **Write to appropriate troubleshooting file**

**Domain Files to Create/Update:**

- `troubleshooting/training.md` (already exists from M4, extend)
- `troubleshooting/backtest.md` (new)
- `troubleshooting/data.md` (new)
- `troubleshooting/environment.md` (Docker, sandbox issues)

**Example Migration:**

**Source (E2E_CHALLENGES_ANALYSIS.md Challenge 5):**
```markdown
## Challenge 5: Data Location Issues

### Symptoms
- `LocalDataLoader` returning `None`
- "Data file not found" errors

### Root Cause
Data lives in different locations...

### Resolution
```python
loader = LocalDataLoader(data_dir='/Users/karl/.ktrdr/shared/data')
```
```

**Destination (troubleshooting/data.md):**
```markdown
## Data Not Found

**Symptom:**
- "Data file not found" errors
- LocalDataLoader returns None
- Tests fail with "no data for symbol"

**Cause:** Data path mismatch between environments:
- Local: `./data/`
- Shared: `~/.ktrdr/shared/data/`
- Docker: `/app/data/` (mounted)

**Cure:**
```bash
# Check where data actually is
ls ~/.ktrdr/shared/data/

# Verify Docker mount
docker compose exec backend ls /app/data/

# If missing, copy to shared
cp -r ./data/* ~/.ktrdr/shared/data/
```

**Prevention:**
- Always use shared data directory
- Verify data exists before running tests
```

**Acceptance Criteria:**
- [ ] All relevant troubleshooting content migrated
- [ ] Symptom→cure format used
- [ ] Prevention tips included
- [ ] Domain files organized logically

---

## Task 8.3: Create Additional Pre-Flight Modules

**File(s):** `.claude/skills/e2e-testing/preflight/{domain}.md`

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Create domain-specific pre-flight modules based on harvested content.

**Modules to Create:**

### preflight/training.md

```markdown
# Pre-Flight: Training

**Used by:** Training E2E tests
**Purpose:** Training-specific checks beyond common

---

## Checks

### 1. Strategy File Exists

**Command:**
```bash
ls ~/.ktrdr/shared/strategies/${STRATEGY_NAME}.yaml
```

**Pass if:** File exists
**Fail message:** "Strategy file not found"

**Cure:**
- Copy strategy to shared directory
- Check strategy name spelling

---

### 2. Training Data Available

**Command:**
```bash
curl -s "http://localhost:${API_PORT}/api/v1/data/${SYMBOL}/${TIMEFRAME}" | jq '.data.dates | length'
```

**Pass if:** Returns count > 0
**Fail message:** "No data for {symbol}/{timeframe}"

**Cure:**
- Load data: POST /api/v1/data/acquire/download
- Check data directory
```

### preflight/backtest.md

```markdown
# Pre-Flight: Backtest

**Used by:** Backtest E2E tests

---

## Checks

### 1. Model File Exists

**Command:**
```bash
ls ~/.ktrdr/shared/models/${MODEL_PATH}
```

### 2. Backtest Worker Available

**Command:**
```bash
curl -s "http://localhost:${API_PORT}/api/v1/workers" | jq '.workers[] | select(.type=="backtest")'
```
```

**Acceptance Criteria:**
- [ ] Training pre-flight module created
- [ ] Backtest pre-flight module created
- [ ] Cures included for each check
- [ ] Modules referenced in test recipes

---

## Task 8.4: Archive Old Documents

**File(s):** docs/testing/*.md

**Type:** CODING

**Task Categories:** Configuration

**Description:**
Archive old testing documents that have been superseded by the new skill structure.

**Archive Process:**

1. **Create archive directory:**
   ```bash
   mkdir -p docs/testing/archive
   ```

2. **Move superseded files:**
   ```bash
   mv docs/testing/SCENARIOS.md docs/testing/archive/
   mv docs/testing/TESTING_GUIDE.md docs/testing/archive/
   ```

3. **Add archive README:**
   ```markdown
   # Archived Testing Documents

   These documents have been superseded by the e2e-testing skill.

   **New Location:** `.claude/skills/e2e-testing/`

   **Why Archived:**
   - Content migrated to skill structure
   - Progressive disclosure now works
   - Agents use skill, not these docs

   **For Reference Only:**
   - SCENARIOS.md - Original 37 test scenarios
   - TESTING_GUIDE.md - Original building blocks

   **Do Not Update:** These files are frozen. Update the skill instead.
   ```

4. **Keep in place (not archive):**
   - E2E_CHALLENGES_ANALYSIS.md (historical record)
   - Handoff documents (still useful for context)

**Acceptance Criteria:**
- [ ] Archive directory created
- [ ] SCENARIOS.md archived
- [ ] TESTING_GUIDE.md archived
- [ ] Archive README explains why
- [ ] Skill is now the source of truth

---

## Milestone 8 Completion Checklist

### All Tasks Complete
- [ ] Task 8.1: Test recipes migrated
- [ ] Task 8.2: Troubleshooting content migrated
- [ ] Task 8.3: Pre-flight modules created
- [ ] Task 8.4: Old documents archived

### E2E Verification
- [ ] Designer finds migrated tests for various needs
- [ ] Tester executes migrated tests successfully
- [ ] Pre-flight modules work correctly
- [ ] No workflow references archived docs

### Quality Gates
- [ ] `make quality` passes
- [ ] All files committed to feature branch
- [ ] SKILL.md catalog is complete
- [ ] Progressive disclosure works (files loaded on-demand)

---

## Framework Complete

After M8, the E2E testing framework is fully operational:

```
┌─────────────────────────────────────────────────────────────┐
│                    PLANNING PHASE                            │
│                                                              │
│  /kdesign-impl-plan                                          │
│       ↓                                                      │
│  e2e-test-designer                                           │
│       ↓                                                      │
│  Milestone E2E Validation section                            │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│                    EXECUTION PHASE                           │
│                                                              │
│  Claude implements milestone                                 │
│       ↓                                                      │
│  e2e-tester (with tests from plan)                          │
│       ↓                                                      │
│  Pre-flight → Execution → Sanity Checks → Report            │
└─────────────────────────────────────────────────────────────┘

Key Achievements:
✅ Tests are discovered, not reinvented
✅ Pre-flight catches environment issues
✅ Sanity checks catch false positives
✅ Failures are categorized and actionable
✅ Institutional knowledge preserved
```
