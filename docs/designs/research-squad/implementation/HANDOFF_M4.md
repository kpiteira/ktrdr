# Handoff — M4: Architect + Capability Pipeline

## Status: COMPLETE — All 3 tasks done, E2E validation passed

## What Changed

### Task 4.1: Architect Gap Analysis

**Architect charter** (`.squad/agents/architect/charter.md`):
- Added structured output format: Feasibility Verdict (GO/MODIFY/BLOCKED) + Gap Analysis (GAP-NNN format)
- Added params:samples ratio check and supported experiment type check (lessons from Architect history — Cycles 7 and 9)
- Added fallback experiment requirement when verdict is BLOCKED/MODIFY
- Added disk persistence instructions: Architect must write to `capability-gaps.md` and `build-queue.md`

**Coordinator skill** (`.claude/skills/squad-coordinator/SKILL.md`):
- Updated Phase 3b Architect template with expanded context (now receives components.md and build-queue.md in addition to capability-gaps.md)
- Added disk-writing instructions matching Scout pattern (M3 — confirmed working)
- Added `Read, Write, Edit` tool requirements for Architect agent
- Architect now reads the charter from repo (`.squad/agents/architect/charter.md`) not shared dir

**capability-gaps.md** (`~/.ktrdr/shared/squad/roadmap/`):
- Structured with GAP-NNN format, seeded 7 OPEN gaps + 1 RESOLVED from components.md's existing gap list
- Each gap has: Blocks, Severity, Effort, Status, What's Missing, Integration Points, Success Criteria, Workaround

**build-queue.md** (`~/.ktrdr/shared/squad/roadmap/`):
- Updated with table format for issue tracking: Gap ID, Description, Status, Filed date, Issue number

### Task 4.2: GitHub Issue Creation

**Architect charter** (`.squad/agents/architect/charter.md`):
- Added `gh issue create` instructions with structured body format matching ARCHITECTURE.md spec
- Labels: `squad:architect`, `capability-gap`
- Issues include: Gap ID, blocked hypotheses, integration points, success criteria

**Coordinator skill** (`.claude/skills/squad-coordinator/SKILL.md`):
- Added `Bash` to Architect's tool requirements (for `gh issue create`)
- Updated "After the Cycle" section to include capability-gaps.md and build-queue.md updates
- Added Architect to Agent Spawning Rules with tool list

**Loop runner** (`.squad/loop_runner.sh`):
- Added `ensure_squad_labels()` — creates `squad:architect` and `capability-gap` labels on GitHub if missing (preflight)
- Added `check_resolved_capabilities()` — queries closed `squad:architect` issues, writes newly resolved to `$SHARED_DIR/loop/newly-resolved-issues.txt`
- Runs `check_resolved_capabilities` at start of each cycle
- Cycle prompt now includes "Newly Resolved Capabilities" section informing the squad
- Evaluate prompt updated: items 7-9 cover capability-gaps.md, build-queue.md, and components.md updates for resolved capabilities

## Key Design Decisions
- Architect writes to disk directly (same pattern as Scout in M3 — Agent tool propagates Write/Edit)
- Gap numbering is sequential (GAP-001, GAP-002...) — Architect checks existing before assigning
- RESOLVED gaps stay in the file (never deleted) for audit trail
- Fallback experiment requirement prevents squad from stalling when BLOCKED
- GitHub label creation is idempotent (`2>/dev/null || true`) — safe to run repeatedly
- Resolved capability detection uses `gh issue list --state closed` (last 50 issues, ~30 days)
- Actual file updates for resolved capabilities happen in the Claude evaluate phase (which has Edit/Write tools), not in bash — keeps shell logic simple
- `newly-resolved-issues.txt` is cleared at the start of each cycle to avoid stale notifications
- E2E validation MUST use `SQUAD_SHARED_DIR` override to avoid colliding with production squad state (lesson learned the hard way)

### Task 4.3: E2E Validation Results

Dry-run squad cycle with Architect enabled. Used isolated `SQUAD_SHARED_DIR` to avoid shared state collision.

| Check | Result | Evidence |
|-------|--------|---------|
| Dry-run cycle completed | **PASS** | Exit 0, "Loop complete. Ran 1 iterations." |
| Feasibility verdict in discussion | **PASS** | GO/BLOCKED references in 14KB discussion log |
| capability-gaps.md updated | **PASS** | 9→13 entries (4 new: GAP-008,009,010,R02) |
| build-queue.md populated | **PASS** | 4 entries with statuses (READY, DEFERRED, RESOLVED) |
| Architect resolved a gap | **PASS** | GAP-R02 marked RESOLVED with code evidence |
| Strategy YAML produced | **PASS** | squad_ei010_gru_mi_validated.yaml |
| experiments.md updated | **PASS** | New entry for Cycle 19 |
| GitHub issue creation | **SKIP** | No HIGH/CRITICAL gaps required external implementation |

E2E test recipe created at `.claude/skills/ke2e/tests/squad/m4-architect-capability-pipeline.md`.

### Task 4.3 (continued): Full JTBD Validation — 2-Cycle Nudge-Driven Test

Used Director nudges to transparently steer the squad toward a frontier that hits a known blocker. Two cycles validated the full pipeline.

**Cycle 1 — Gap identification + issue filing:**

| Check | Result | Evidence |
|-------|--------|---------|
| Director steered toward blocked frontier | **PASS** | Cost-aware loss frontier proposed |
| Engineer produced ideal spec (deliberately blocked) | **PASS** | Twin-head MADL spec + GO fallback |
| Architect gave BLOCKED verdict | **PASS** | "IDEAL BLOCKED (GAP-005 + GAP-008), FALLBACK GO" |
| GitHub issues filed | **PASS** | #376 (cost-aware loss, 3KB body) and #377 (twin-head) |
| build-queue.md populated | **PASS** | Both issues tracked with links |
| Fallback experiment produced | **PASS** | squad_c23_focal_asymmetric_eurusd_1h (GO verdict) |

**Between cycles:** Closed #376 (simulating capability built).

**Cycle 2 — Resolved capability flows back:**

| Check | Result | Evidence |
|-------|--------|---------|
| Loop runner detected closed issue | **PASS** | "Resolved capability: #376" in startup log |
| GAP-005 marked RESOLVED | **PASS** | With practical note about branch availability |
| components.md updated | **PASS** | MADL listed as available capability |
| build-queue.md GAP-005 → RESOLVED | **PASS** | Status changed |
| Squad designed experiment using new capability | **PASS** | c26_madl_momentum_microstructure_5m_eurusd |

**JTBD fully validated:** gap blocks experiment → issue filed → capability built → issue closed → squad detects resolution → squad uses new capability to test previously blocked hypothesis.

Test issues #376 and #377 closed after validation (labeled validation-test).

## Gotchas
- **Shared state collision is real.** Running loop_runner.sh from multiple worktrees writes to the same `~/.ktrdr/shared/squad/` directory. Always use `SQUAD_SHARED_DIR` override for isolated runs. The M3 handoff warned about this; M4 confirmed it by accidentally disturbing production state.
- **GitHub issues not always needed.** Architect correctly triaged LOW severity gaps as setup steps rather than filing issues. The issue creation path works (labels created, `gh issue create` in charter) but the Architect's judgment is to only file when external implementation is needed.
- **Evaluate phase numbering.** After adding capability pipeline items (7-9) to the evaluate prompt, the cadence item became #11. Keep the numbering consistent when adding more items.
- **GRU pipeline confirmed working.** GAP-R02 resolution means the squad can now design GRU experiments with confidence — a real capability unlocked through Architect code review.
