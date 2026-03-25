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

## M2: E2E Consolidation

### Task 2.1 — recipe migration
- 71 recipes moved from e2e-testing/tests/ to ke2e/tests/ with zero naming conflicts
- 12 existing ke2e recipes preserved = 83 total

### Task 2.2 — preflight + troubleshooting
- 5 preflight modules + 4 troubleshooting guides moved to ke2e/
- No internal references to old `e2e-testing` paths found
- Copied helper script (run-test.sh) as well

### Task 2.3 — SKILL.md catalog
- Created unified catalog with all 83 recipes organized by category
- References global ke2e for TEMPLATE.md and FAILURE_CATEGORIES.md

### Task 2.4 — agent swap
- Deleted 3 old agents (e2e-test-designer, e2e-test-architect, e2e-tester)
- Created 3 symlinks to devops-ai agents (ke2e-test-scout, ke2e-test-designer, ke2e-test-runner)
- Deleted entire e2e-testing/ skill directory

### Gotchas
- `backtesting/` and `backtest/` are separate categories (2 integration tests vs 16 core tests). Not merged — they serve different purposes.

## M3: Shared Observability

### Compose changes
- Removed jaeger, prometheus, grafana services (~72 lines) + their named volumes
- Removed backend's depends_on jaeger
- Added `devops-ai-observability` external network to 7 services (backend + 4 workers + 2 agents)
- Updated all 10 OTEL endpoints to `http://devops-ai-jaeger:4317`

### sandbox_ports.py
- Removed 5 fields: grafana, jaeger_ui, jaeger_otlp_grpc, jaeger_otlp_http, prometheus
- 6 ports per slot (down from 11)

### Port reference cleanup
- Fixed ~20 display strings to show shared ports (43000, 46686, 49090) with "(shared)"
- CLI telemetry endpoint updated to shared OTLP port 44317

### Gotchas
- mypy has 59 pre-existing errors (same on main)
- GF_ADMIN_PASSWORD secret no longer needed (grafana is shared)
