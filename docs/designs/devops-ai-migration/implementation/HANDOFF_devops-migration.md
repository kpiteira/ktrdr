# Handoff: DevOps AI Migration

## M1: Skills Migration

### Task 1.1 — project.md
- Created `.devops-ai/project.md` following devops-ai template format
- Infrastructure section still references `uv run kinfra` (changes to bare `kinfra` in M5)

### Task 1.2 — shared rules
- 7 rules symlinked to `.claude/rules/` from devops-ai
- Added `.claude/rules/` to `.gitignore` (symlinks to external repo, don't commit)

### Task 1.3 — old skills + permissions
- Only `address-review` needed deletion (other old skills were previously removed)
- settings.local.json had NO Skill permissions before — added fresh list
- Old skills still appear in skill list (ktask, kmilestone, kdesign-impl-plan, etc.) — these are from global `~/.claude/skills/` but NOT from devops-ai. They may be stale local installations. Investigate if they persist after validation.

### Gotchas
- The skill list in system reminders still shows old names (ktask, kmilestone, etc.). These appear to come from somewhere outside `.claude/skills/`. Possibly cached or from another source. Monitor in validation.
