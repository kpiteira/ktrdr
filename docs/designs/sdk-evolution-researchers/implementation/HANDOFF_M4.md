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

**Next Task Notes (4.4)**: Docker compose service `assessment-agent-1` uses same `ktrdr-agent:dev` image as design agent, port 5020, env `KTRDR_WORKER_TYPE=agent_assessment`. Unit tests already comprehensive from 4.1 + 4.3 (30 tests). Task 4.4 adds compose config + any additional edge case tests.
