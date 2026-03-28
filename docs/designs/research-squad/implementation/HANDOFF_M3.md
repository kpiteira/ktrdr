# Handoff — M3: Scout + External Research

## Status: COMPLETE — All 3 tasks done, E2E validation passed (4/5 hard checks, 1 soft fail)

## What Changed

### Task 3.1: Scout Agent with Web Search
- **Scout charter** (`.squad/agents/scout/charter.md`): Added ownership of `external-insights.md` and explicit disk persistence responsibility
- **Coordinator skill** (`.claude/skills/squad-coordinator/SKILL.md`): Updated Scout template (Phase 2a) to include persistence instructions — Scout now writes structured findings to `external-insights.md`, appends to `bibliography.md`, and maintains `reading-queue.md`
- **Coordinator skill**: Updated Scout tool requirements to include `Read, Write, Edit` alongside `WebSearch, WebFetch`
- **Loop runner** (`.squad/loop_runner.sh`): Added Scout file paths to the key paths listed in the cycle prompt

### Task 3.2: External Insights Integration
- **Director template**: Now receives `external-insights.md` (accumulated) in addition to `scout_findings` (this cycle)
- **Inventor template**: Now receives `external-insights.md` and explicit instruction to incorporate Scout insights
- **Architect template**: Now receives `external-insights.md` for capability-relevant insights
- **LEARN phase (Scribe)**: Added "External Insight Influence" section — Scribe records which Scout findings influenced experiment design
- **Evaluate prompt** (loop_runner.sh): Added step 6 to update `external-insights.md` statuses (NEW → CITED/TESTED)
- **After the Cycle** section: Updated numbered list to include external-insights.md status updates

## Key Design Decisions
- Scout **overwrites** `external-insights.md` each cycle (curated, actionable view) but **appends** to `bibliography.md` (historical record)
- `reading-queue.md` is overwritten each cycle (it's a forward-looking queue, not history)
- External insights use Status tracking: NEW → CITED → TESTED → SUPERSEDED
- Both ephemeral `scout_findings` (text from agent) AND persistent `external-insights.md` (file on disk) are routed to Director/Inventor — ephemeral for this-cycle freshness, persistent for cross-cycle accumulation

## What Already Worked (no changes needed)
- Loop runner already allowed `WebSearch WebFetch` in `--allowedTools`
- Scout charter already had quality filters and structured output format
- Bibliography already had entries from earlier cycles
- Coordinator skill already had Scout template in Phase 2a with proper context routing

## Task 3.3: E2E Validation Results

Dry-run squad cycle with Scout enabled. Results:

| Check | Result | Evidence |
|-------|--------|---------|
| external-insights.md populated | **PASS** | 5→108 lines, 7 structured insights |
| Real URLs present | **PASS** | PMC12329085, arXiv 2506.06840, ScienceDirect 2025 |
| Quality ratings | **PASS** | HIGH/MEDIUM-HIGH/MEDIUM/LOW on all 7 entries |
| bibliography.md grew | **PASS** | 29→44 lines, 10 new sources |
| reading-queue.md updated | **SOFT FAIL** | Unchanged — Scout prioritized other files |
| Cross-agent referencing | **PASS** | Director used EI-001/EI-002; Inventor built on GRU finding; 2 new frontiers from Scout |
| Evaluate tracks influence | **PASS** | EI-001, EI-002 marked CITED in external-insights.md |

E2E test recipe created at `.claude/skills/ke2e/tests/squad/m3-scout-external-research.md`.

## Gotchas
- Scout's disk writes depend on the Agent tool passing Write/Edit access through to sub-agents. The parent session has these tools in `--allowedTools`, so they should propagate. **Confirmed working** in E2E test.
- The `external-insights.md` file lives at `~/.ktrdr/shared/squad/roadmap/external-insights.md` (not in agents/scout/), because it's a squad-level output consumed by multiple agents.
- reading-queue.md was not updated by Scout during the E2E test — may need stronger prompting or to move this to a less-critical status.
- Full squad discussion cycle takes 20+ minutes (8 agents + web searches). Budget accordingly for validation runs.
- **Shared state collision:** loop_runner.sh has no locking — two concurrent runs (e.g. M2 long validation + M3 dry-run) walk on each other's iteration counter, cadence, and current-experiment. The shared dir (`~/.ktrdr/shared/squad/`) assumes single-instance operation. A lockfile or per-run SHARED_DIR override would fix this.
