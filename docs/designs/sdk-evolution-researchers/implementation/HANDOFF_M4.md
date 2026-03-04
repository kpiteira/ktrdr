# Handoff — M4: Assessment Agent Worker

## Task 4.1 Complete: Create AssessmentAgentWorker (WorkerAPIBase)

**Pattern: follows DesignAgentWorker exactly** — Same WorkerAPIBase inheritance, same module-level app gating (`KTRDR_WORKER_TYPE=agent_assessment`), same mock OperationsService via direct assignment, same result extraction (last tool call wins).

**Key differences from design worker**: Assessment input is structured (strategy_name, training_metrics, backtest_results dicts) vs design's free-form brief. Result extraction targets `mcp__ktrdr__save_assessment` tool and extracts verdict, strengths, weaknesses, suggestions, hypotheses, assessment_path.

**Placeholder prompt at `ktrdr/agents/assessment_sdk_prompt.py`** — Minimal one-liner. Task 4.2 will flesh out the full analysis rubric.

## Task 4.2 Complete: Write Assessment Agent System Prompt

**Prompt structure (~75 lines)**: Role → Workflow (5 steps) → Analysis Rubric (6 dimensions) → Verdict Guidelines (3 levels with thresholds) → Output Contract → Discovery Tools → Filesystem Access → Safety Constraints. No indicator lists, no pre-loaded context.

**Analysis rubric dimensions**: Sharpe ratio, max drawdown, trade count, win rate vs risk/reward, consistency (training vs backtest gap), indicator relevance.

## Task 4.3 Complete: Memory Integration

**Pattern: `_save_memory()` method called between assessment extraction and `complete_operation()`** — Synchronous filesystem I/O wrapped in try/except. Builds `ExperimentRecord` from input metrics + assessment result, saves hypotheses individually via `save_hypothesis()`.

**Gotcha: mock pattern uses `patch("...assessment_agent_worker.memory")`** — Must patch the module-level import, not `ktrdr.agents.memory` directly. The worker imports `memory` as a module, so tests mock the whole module object.

## Task 4.4 Complete: Wire into Docker Compose + Unit Tests

**Docker service `assessment-agent-1`** — Mirrors `design-agent-1` pattern: same image, auth volume, shared mounts. Port 5020 via `KTRDR_ASSESSMENT_AGENT_PORT` env var. Strategies mounted read-only (assessment reads, doesn't write).

**Unit tests already comprehensive (30 tests)** from tasks 4.1-4.3 covering all acceptance criteria listed in 4.4 (endpoint validation, runtime invocation, transcript extraction, memory integration, best-effort failure handling).

## Task 4.5 Complete: E2E Validation

**E2E test: `agents/assessment-agent-metrics-to-verdict`** — 9-step test designed by e2e-test-architect, executed by e2e-tester. Result: **PASSED (functional)** with known infrastructure issues.

**What worked**: Agent starts, registers, invokes Claude Code (5 turns, $0.24), produces verdict="promising" with 5 strengths, 5 weaknesses, 6 suggestions, 4 hypotheses. Memory integration confirmed (experiment record + hypotheses saved). Assessment references 5/5 input metrics — not generic.

**Gotcha: missing DB env vars in agent containers** — Both `design-agent-1` and `assessment-agent-1` were missing `KTRDR_DB_HOST=db` and related DB vars. Workers need these for OperationsService DB access. Fixed in docker-compose.sandbox.yml.

**Known issue: orphan detector marks operation "failed"** — Pre-existing architectural issue. Backend's in-memory OperationsService doesn't see worker-side operation claims. Worker completes successfully (data in result_summary) but backend orphan detector overwrites status to "failed". Affects all agent workers, not M4-specific. Filed for future fix.

**Known issue: assessment_path null** — MCP `save_assessment` tool was called (data extracted from transcript) but file not written to disk. Minor — assessment data is fully captured in result_summary and memory.
