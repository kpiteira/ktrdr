---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M2: E2E Consolidation

Consolidate ktrdr's two overlapping E2E systems (e2e-testing with 71 recipes, ke2e with 12) into the single devops-ai ke2e pattern. Swap agent definitions. This milestone dogfoods kbuild from M1.

## Context

**Current state:**
- `.claude/skills/e2e-testing/` — 71 recipes, 5 preflight modules, 4 troubleshooting guides
- `.claude/skills/ke2e/` — 12 recipes (project-local, shadows global ke2e framework)
- `.claude/agents/` — 3 old agent files (e2e-test-designer, e2e-test-architect, e2e-tester)

**Target state:**
- `.claude/skills/ke2e/` — 83 recipes unified, preflight modules, troubleshooting guides, catalog SKILL.md
- `.claude/agents/` — 3 symlinks to devops-ai agents (ke2e-test-scout, ke2e-test-designer, ke2e-test-runner)
- `.claude/skills/e2e-testing/` — deleted

---

## Task 2.1: Migrate recipes to ke2e catalog

**File(s):** `.claude/skills/ke2e/tests/`, `.claude/skills/e2e-testing/tests/`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Move all 71 test recipes from `e2e-testing/tests/` into `ke2e/tests/`, merging with the existing 12 ke2e recipes. Preserve directory structure (category/name.md). Handle any naming conflicts between the two sets.

**Implementation Notes:**
- The e2e-testing categories are: agent, agents, backtest, backtesting, cli, codebase, data, evolution, fuzzy, indicators, infra, mcp, regression, skills, training, workers
- The ke2e categories are: backtest, cli, training
- Overlapping categories (backtest, cli, training) need file-level conflict checking — compare filenames before moving
- Use `mv` for the move, not copy — we want the old location empty for clean deletion later
- After moving, verify file count: should be 83 total (71 + 12, minus any that were duplicates)

**Testing Requirements:**
- [ ] All 71 recipes from e2e-testing/tests/ are present in ke2e/tests/
- [ ] All 12 existing ke2e recipes are preserved
- [ ] No files lost during move (count before and after)
- [ ] Category directory structure maintained
- [ ] No naming conflicts (if any exist, document resolution in handoff)

**Acceptance Criteria:**
- [ ] `find .claude/skills/ke2e/tests/ -name "*.md" | wc -l` returns 83 (or documented merge count)
- [ ] `e2e-testing/tests/` is empty
- [ ] Every recipe file is readable and has expected structure

---

## Task 2.2: Migrate preflight and troubleshooting modules

**File(s):** `.claude/skills/ke2e/preflight/`, `.claude/skills/ke2e/troubleshooting/`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Move preflight modules (5 files) and troubleshooting guides (4 files) from `e2e-testing/` to `ke2e/`. These are ktrdr-specific modules that complement the global ke2e framework.

**Implementation Notes:**
- Preflight modules: common.md, training.md, backtest.md, data.md, workers.md
- Troubleshooting guides: common.md, data.md, environment.md, training.md
- ke2e currently has no preflight/ or troubleshooting/ directories — create them
- Check if any preflight modules reference `e2e-testing` paths internally and update to `ke2e`
- The global ke2e skill (via symlink) has `preflight/common.md` — our project-local version shadows it

**Testing Requirements:**
- [ ] All 5 preflight modules present in `ke2e/preflight/`
- [ ] All 4 troubleshooting guides present in `ke2e/troubleshooting/`
- [ ] No internal references to old `e2e-testing/` paths
- [ ] Files are readable and structurally intact

**Acceptance Criteria:**
- [ ] `ke2e/preflight/` has 5 module files
- [ ] `ke2e/troubleshooting/` has 4 guide files
- [ ] `e2e-testing/preflight/` and `e2e-testing/troubleshooting/` are empty

---

## Task 2.3: Rewrite ke2e SKILL.md catalog

**File(s):** `.claude/skills/ke2e/SKILL.md`
**Type:** CODING
**Estimated time:** 2 hours

**Description:**
Rewrite the project-local ke2e SKILL.md to serve as the unified catalog for all 83 recipes. This file is what the ke2e-test-scout agent reads to find matching tests. It must list every recipe with category, purpose, duration, and "use when" guidance.

**Implementation Notes:**
- Read the current `e2e-testing/SKILL.md` for its catalog table format — this is the format the scout expects
- Read each recipe's purpose/duration to populate the catalog table
- Organize by category with clear headings
- Include preflight module table and troubleshooting reference table
- Reference global ke2e for framework docs: "See global ke2e for TEMPLATE.md and FAILURE_CATEGORIES.md"
- Keep the same frontmatter format as devops-ai ke2e but with ktrdr-specific content

**Testing Requirements:**
- [ ] SKILL.md has valid frontmatter (name, description, metadata)
- [ ] Catalog table lists all 83 recipes
- [ ] Each entry has: Test path, Category, Duration, Use When
- [ ] Preflight module table is accurate
- [ ] Troubleshooting table is accurate

**Acceptance Criteria:**
- [ ] ke2e-test-scout can load SKILL.md and find recipes by category search
- [ ] Every recipe in `tests/` has a corresponding catalog entry
- [ ] No references to old `e2e-testing` skill

---

## Task 2.4: Swap agent definitions and delete old skill

**File(s):** `.claude/agents/`, `.claude/skills/e2e-testing/`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Replace the 3 old agent files with symlinks to devops-ai's ke2e agents. Delete the now-empty `e2e-testing/` skill directory.

**Implementation Notes:**
- Delete old agents:
  - `.claude/agents/e2e-test-designer.md`
  - `.claude/agents/e2e-test-architect.md`
  - `.claude/agents/e2e-tester.md`
- Create symlinks to devops-ai agents:
  - `ln -s /Users/karl/Documents/dev/devops-ai/agents/ke2e-test-scout.md .claude/agents/ke2e-test-scout.md`
  - `ln -s /Users/karl/Documents/dev/devops-ai/agents/ke2e-test-designer.md .claude/agents/ke2e-test-designer.md`
  - `ln -s /Users/karl/Documents/dev/devops-ai/agents/ke2e-test-runner.md .claude/agents/ke2e-test-runner.md`
- Keep `integration-test-specialist.md` and `unit-test-quality-checker.md` (not part of this migration)
- Delete `e2e-testing/` directory entirely (all content moved to ke2e in tasks 2.1-2.2)
- Verify e2e-testing SKILL.md, TEMPLATE.md, FAILURE_CATEGORIES.md, HARVEST_INVENTORY.md are no longer needed (ke2e global has equivalent framework docs)

**Testing Requirements:**
- [ ] Old agent files deleted (3 files)
- [ ] New agent symlinks resolve correctly (3 symlinks)
- [ ] `e2e-testing/` directory completely removed
- [ ] Remaining agents (`integration-test-specialist`, `unit-test-quality-checker`) unaffected

**Acceptance Criteria:**
- [ ] `ls -la .claude/agents/` shows 3 symlinks + 2 local files
- [ ] `.claude/skills/e2e-testing/` does not exist
- [ ] No dangling references to old agent names in project files

---

## Task 2.5: Validation — run ke2e against sandbox

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 2 hours

**Description:**
Validate the consolidated E2E system by running the ke2e-test-scout to find a test, then ke2e-test-runner to execute it against a running sandbox. This is the dogfooding gate: if ke2e doesn't work here, we can't use it for M3.

**Implementation Notes:**
- Requires a running sandbox: `uv run kinfra sandbox up` (or use existing local-prod)
- This validation uses the NEW agent chain (scout → runner), not the old agents

**Validation Steps:**
1. Load the `ke2e` skill
2. Invoke ke2e-test-scout with requirement: "Validate training pipeline works end-to-end — training starts, progresses, and completes with a valid model"
3. Scout should find `training/smoke` in the catalog
4. Invoke ke2e-test-runner with `training/smoke`
5. Runner should:
   - Run preflight checks (Docker, backend health, training prerequisites)
   - Execute training smoke test steps
   - Report PASS/FAIL with evidence
6. If sandbox is not available, validate scout-only flow:
   - Scout finds recipes correctly
   - Scout produces valid handoff format when no match exists
   - Manually verify 3 recipes from different categories load and parse correctly

**Acceptance Criteria:**
- [ ] ke2e-test-scout finds recipes in new `.claude/skills/ke2e/tests/` location
- [ ] ke2e-test-runner executes at least one test (or scout-only if no sandbox)
- [ ] Failure categorization works (ENVIRONMENT/CONFIGURATION/CODE_BUG/TEST_ISSUE)
- [ ] No references to old `e2e-testing` skill in agent behavior
- [ ] HANDOFF document updated with any gotchas from migration
