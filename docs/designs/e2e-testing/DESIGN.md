# E2E Testing Framework: Design

## Problem Statement

KTRDR has 2700+ lines of E2E testing documentation (SCENARIOS.md, TESTING_GUIDE.md) that is never used. The coding agent reinvents tests every milestone, wasting context and often creating tests that give false confidence (e.g., 100% training accuracy that's actually model collapse). We need a testing system that Claude will *actually use* - one that integrates into the existing workflow, catches configuration issues early, and provides trustworthy validation.

## Goals

1. **Clear trigger mechanism** - E2E tests are triggered through `/kdesign-impl-plan`, not discovered by accident
2. **Progressive disclosure** - Claude loads only what it needs, not 2000 lines at once
3. **Reusable building blocks** - Core test patterns are composed, not reinvented each milestone
4. **Pre-flight validation** - Configuration issues caught before test execution, with symptom→cure mappings
5. **Leverage existing content** - Migrate useful content from SCENARIOS.md, don't start from scratch

## Non-Goals (Out of Scope)

- Human-friendly CLI commands (nice-to-have, not primary)
- Comprehensive test coverage of every feature (focus on backbone: training, backtesting, data)
- pytest integration (keep tests as executable building blocks Claude can run)
- Frontend/UI testing
- Defining specific test content (that comes after architecture is settled)

## Why the Current System Fails

### 1. No Trigger Mechanism

Nothing in Claude's workflow tells it to use the existing test infrastructure:
- `/kdesign-impl-plan` doesn't reference SCENARIOS.md
- The e2e-testing skill exists but nothing triggers its loading
- The integration-test-specialist agent was used exactly once

**The tests exist, but nothing points Claude to them.**

### 2. No Progressive Disclosure

SCENARIOS.md is 2300+ lines. TESTING_GUIDE.md is 750+ lines. Loading all of this:
- Consumes massive context
- Overwhelms with irrelevant information
- Makes it hard to find what you actually need

**The content is useful but monolithic.**

### 3. No Pre-Flight Validation

The challenges document shows hours wasted debugging "code bugs" that were configuration issues:
- 2.5% zigzag threshold on EURUSD forex (should be 0.5%)
- Docker daemon corrupted
- Wrong port numbers (sandbox vs main)
- Data in wrong directory

**Tests ran but gave misleading results because prerequisites weren't validated.**

### 4. No Symptom→Cure Mappings

When pre-flight or tests fail, Claude spends tokens figuring out solutions to previously-solved problems. We've debugged Docker issues, sandbox port confusion, and data path problems multiple times.

**Known problems need documented solutions.**

## User Experience

### Primary User: Claude (the coding agent)

**Scenario 1: End of Milestone Validation (Existing Tests)**

Claude has completed implementing milestone M7. The milestone plan says:

```
## E2E Validation
- Run: training/smoke (validates training still works)
- Run: backtest/progress (validates the new progress feature)
```

Claude:
1. Loads the e2e-testing skill (or relevant sub-section)
2. Finds the referenced test recipes
3. Runs pre-flight checks → catches any environment issues with known solutions
4. Executes test commands
5. Validates against success criteria
6. Reports PASS/FAIL with evidence

**Scenario 2: New Feature Needs New Test**

Claude is planning milestone M9 which adds a new "strategy hot-reload" feature. During `/kdesign-impl-plan`:

1. Reviews existing test catalog - no test covers hot-reload
2. Plan includes: "Create new E2E test for strategy hot-reload using test template"
3. During implementation, Claude creates new test from building blocks
4. New test is added to catalog for future reuse

**Scenario 3: Pre-Flight Failure with Known Cure**

Claude runs a test, pre-flight fails with "Docker not healthy":

1. Pre-flight module includes symptom→cure mapping
2. Claude sees: "SYMPTOM: Docker not healthy → CURE: Run `docker compose down && docker compose up -d`"
3. Applies cure, re-runs pre-flight
4. Proceeds with test

### Secondary User: Karl (human oversight)

- Reviews milestone plans that include E2E validation references
- Can trust that Claude ran appropriate tests before PR
- Optional: `/e2e smoke` command to run tests manually

## Key Decisions

### Decision 1: Two Sub-Agents for Separation of Concerns

**Choice:** Two specialized sub-agents handle E2E testing:
- **e2e-test-designer**: Researches existing tests, proposes appropriate ones for a given validation need
- **e2e-tester**: Executes tests, reports detailed results, works with main agent on failures

**Alternatives considered:**
- Single skill handles everything - too much responsibility, poor separation
- Main agent does everything - context pollution, reinvents the wheel
- Single agent for both - mixing design-time and execution-time concerns

**Rationale:**
- **e2e-test-designer** is invoked during planning (by /kdesign-impl-plan)
- **e2e-tester** is invoked during execution (at end of milestone)
- Each has focused context and responsibility
- Main agent stays lean, delegates specialized work

### Decision 2: /kdesign-impl-plan Uses e2e-test-designer Sub-Agent

**Choice:** During implementation planning, /kdesign-impl-plan invokes e2e-test-designer to figure out what REAL tests validate the feature

**How it works:**
1. Impl-plan determines what needs to be validated ("training progress tracking works")
2. Invokes e2e-test-designer with clear validation requirements
3. Designer researches existing tests/components via the e2e-testing skill
4. Returns: matching tests OR proposal for new tests
5. Impl-plan incorporates this into the milestone's E2E Validation section

**Alternatives considered:**
- Impl-plan hardcodes test references - doesn't adapt to new features
- Impl-plan guesses at tests - unreliable
- No E2E validation in plans - current broken state

**Rationale:**
- Designer agent has focused context (just E2E testing knowledge)
- Can do deep research without polluting impl-plan's context
- Returns actionable recommendations, not generic instructions

### Decision 3: Skill with Progressive Disclosure (Under 500 Lines)

**Choice:** E2E testing skill follows Claude Code best practices:
- SKILL.md is lean navigation (<500 lines)
- Supporting files loaded on-demand via markdown links
- Scripts for zero-context execution of complex logic

**How progressive disclosure works:**
- SKILL.md contains catalog + instructions
- Links like `[training/smoke.md](tests/training/smoke.md)` signal file exists
- Claude loads supporting files only when task requires them

**Rationale:**
- Aligns with how Claude Code skills are designed to work
- 2000+ lines of test content is fine, just not all loaded at once
- Each test recipe is a separate file, loaded only when needed

### Decision 4: Pre-Flight Checks with Symptom→Cure Mappings

**Choice:** Every test includes pre-flight checks, and each check includes what to do if it fails

**Alternatives considered:**
- Optional pre-flight - defeats the purpose
- Pre-flight without cures - Claude wastes tokens debugging
- Separate troubleshooting docs - won't be found

**Rationale:**
- Most "test failures" in E2E_CHALLENGES_ANALYSIS.md were actually environment issues
- We've solved Docker issues, port confusion, data paths multiple times
- Known problems + known solutions = no wasted tokens
- Format: "SYMPTOM: X → CURE: Y" is clear and actionable

### Decision 5: Building Blocks, Not Monolithic Tests

**Choice:** Tests are composed from reusable building blocks (pre-flight modules, common patterns)

**Alternatives considered:**
- Each test is fully self-contained - massive duplication
- One giant test file - current problem
- Generated tests - too complex

**Rationale:**
- 2000 lines of content is fine, split appropriately
- Pre-flight for Docker is the same across all tests → one module
- "Start operation and poll progress" is a pattern → one module
- New tests compose existing blocks + feature-specific additions

### Decision 6: Migrate, Don't Discard, Existing Content

**Choice:** SCENARIOS.md and TESTING_GUIDE.md content is migrated into the new structure

**Alternatives considered:**
- Start from scratch - wastes valuable tested content
- Keep both systems - confusing, maintenance burden
- Archive without migration - loses institutional knowledge

**Rationale:**
- SCENARIOS.md has 37 tested scenarios with actual results
- TESTING_GUIDE.md has calibrated test parameters, API details
- Problem was structure and discoverability, not content quality
- Migration is a milestone task, not a side effect

## Open Questions

### Q1: e2e-test-designer Agent Scope

The designer agent researches existing tests and proposes appropriate ones. Questions:
- Should it also be able to CREATE new test files, or just propose them?
- How detailed should its proposals be for new tests?
- Should it validate that proposed tests actually exist before returning?

**Current thinking:** Designer proposes, main agent (or human) decides whether to create. Proposals should be detailed enough to implement.

### Q2: e2e-tester Agent Failure Handling

When tests fail, how does e2e-tester work with main agent?
- Returns failure details and lets main agent decide next steps?
- Attempts automated remediation using symptom→cure mappings?
- Escalates to human if cure doesn't work?

**Current thinking:** Tester applies known cures automatically, re-runs. If still failing after cures, returns detailed failure report for main agent to handle.

### Q3: Skill vs Agent Boundary

With two agents (designer, tester), what role does the skill play?
- Skill is the knowledge base that agents use
- Skill could be invoked directly for simple cases
- Agents are for complex scenarios requiring back-and-forth

**Current thinking:** Skill is the knowledge base. Agents use the skill. Main agent could invoke skill directly for very simple tests.

### Q4: What Happens to integration-test-specialist?

Current agent was used once. Options:
- **Merge into e2e-tester** - similar responsibility
- **Keep separate** - integration tests are different from E2E
- **Remove** - e2e-tester covers the use case

**Current thinking:** E2E is the focus. Integration tests are a separate concern for later.

---

## Success Metrics

1. **Designer produces actionable recommendations**: e2e-test-designer returns specific tests or detailed new test proposals
2. **Tester runs reliably**: e2e-tester executes tests, applies cures, reports clearly
3. **Progressive disclosure works**: Claude loads only relevant test sections
4. **Pre-flight catches issues**: Environment problems detected with known cures
5. **Impl-plan integration works**: /kdesign-impl-plan invokes designer and incorporates results
6. **Reuse happens**: Same test recipes used across multiple milestones
