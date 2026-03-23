---
design: docs/designs/devops-ai-migration/DESIGN.md
architecture: docs/designs/devops-ai-migration/ARCHITECTURE.md
---

# M1: Skills Migration

Replace ktrdr's remaining old devops skills with devops-ai symlinks, create project config, and install shared rules.

## Context

Global symlinks already exist at `~/.claude/skills/` for: kbuild, kdesign, kplan, kreview, kissue, kworktree, ke2e, kinfra-onboard. Most old skills (ktask, kmilestone, kdesign-*, _execution-core) were previously deleted. Only `address-review` remains.

No `.devops-ai/project.md` or `.claude/rules/` directory exists yet.

---

## Task 1.1: Create project configuration

**File(s):** `.devops-ai/project.md`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Create the `.devops-ai/` directory and `project.md` config file that devops-ai skills read for project context (test commands, paths, infrastructure commands, project-specific patterns).

**Implementation Notes:**
- Follow the format in devops-ai's `templates/project-config.md`
- Infrastructure section references `uv run kinfra` commands (not bare `kinfra` — that changes in M5)
- E2E testing section points to `.claude/skills/ke2e/tests/` (the target location after M2)
- Project-specific patterns section captures ktrdr conventions: `uv run` for Python, strategy file locations, shared data paths, host services

**Testing Requirements:**
- [ ] File parses as valid markdown
- [ ] All sections present (Project, Testing, Paths, Infrastructure, E2E Testing, Project-Specific Patterns)
- [ ] Test commands match actual Makefile targets (`make test-unit`, `make quality`, etc.)

**Acceptance Criteria:**
- [ ] `.devops-ai/project.md` exists with complete ktrdr project config
- [ ] Commands referenced in config actually work when run

---

## Task 1.2: Install shared rules

**File(s):** `.claude/rules/` (new directory with symlinks)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Create `.claude/rules/` directory and symlink devops-ai's shared rules. These rules (~1,490 tokens) are always loaded into Claude's context and encode TDD, handoff, quality gate, E2E testing, vertical slicing, and testing taxonomy principles.

**Implementation Notes:**
- Run devops-ai's `install.sh --rules /Users/karl/Documents/dev/ktrdr-prod` if it supports project-level rule installation
- If not, manually create symlinks: `ln -s /Users/karl/Documents/dev/devops-ai/rules/<name>.md .claude/rules/<name>.md` for each of the 7 rule files
- The `project-config.md` rule references `.devops-ai/project.md` — confirm it finds ktrdr's file
- Add `.claude/rules/` to `.gitignore` if rules are symlinks to external repo (they shouldn't be committed as symlinks)

**Testing Requirements:**
- [ ] All 7 symlinks resolve correctly: `ls -la .claude/rules/`
- [ ] Each symlink target exists and is readable
- [ ] Rules don't conflict with existing ktrdr CLAUDE.md content

**Acceptance Criteria:**
- [ ] `.claude/rules/` contains 7 working symlinks to devops-ai rules
- [ ] Claude session loads rules (visible in context)

---

## Task 1.3: Delete old skills and update permissions

**File(s):** `.claude/skills/address-review/`, `.claude/settings.local.json`
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Delete the last remaining old devops skill (`address-review`, replaced by `kreview` global symlink) and update settings.local.json to include Skill permissions for devops-ai skills.

**Implementation Notes:**
- Delete: `rm -rf .claude/skills/address-review/`
- Read current `.claude/settings.local.json` — it has Bash permissions but no Skill permissions
- Add Skill permissions while preserving existing Bash permissions:
  ```json
  "Skill(kbuild)", "Skill(kdesign)", "Skill(kplan)",
  "Skill(kreview)", "Skill(kissue)", "Skill(kworktree)", "Skill(klandpr)"
  ```
- kworktree stays in permissions (local ktrdr variant still active until M5)
- klandpr stays (ktrdr-specific, not migrating)

**Testing Requirements:**
- [ ] `address-review` directory no longer exists
- [ ] settings.local.json is valid JSON
- [ ] All listed skills are discoverable by Claude (global symlinks + local skills)

**Acceptance Criteria:**
- [ ] No old devops skills remain in `.claude/skills/`
- [ ] settings.local.json has both Bash and Skill permissions
- [ ] `/kreview` is invocable (replaces `/address-review`)

---

## Task 1.4: Validation — dogfood kbuild

**File(s):** (none — validation only)
**Type:** VALIDATION
**Estimated time:** 1 hour

**Description:**
Validate that the migrated skill set works by invoking `/kbuild` on a trivial task. This proves the devops-ai skills load correctly, project config is found, and rules are active.

**Implementation Notes:**
- This is the dogfooding gate: if kbuild doesn't work here, we can't use it for M2
- Test with: `/kbuild impl: docs/designs/devops-ai-migration/implementation/M1_skills-migration.md task: 1.4`
- kbuild should: read this milestone file, find the design/architecture via frontmatter, recognize this as a VALIDATION task
- Verify rules are loaded by checking that TDD and handoff patterns appear in Claude's behavior

**Validation Steps:**
1. Load the `ke2e` skill
2. Invoke ke2e-test-scout — look for any existing test that validates "skill loading" or "CLI command invocation"
3. If no match, manually verify:
   - `/kbuild` responds with skill acknowledgment
   - `/kdesign` responds with skill acknowledgment
   - `/kplan` responds with skill acknowledgment
   - `/kreview` responds with skill acknowledgment
4. Verify `.devops-ai/project.md` is read by kbuild (check if it references correct test commands)

**Acceptance Criteria:**
- [ ] kbuild loads and executes correctly
- [ ] kdesign, kplan, kreview all load from global symlinks
- [ ] Project config is discovered and used
- [ ] Shared rules are active in Claude's context
- [ ] HANDOFF document created/updated
