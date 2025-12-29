---
design: ../DESIGN.md
architecture: ../SCENARIOS.md
---

# Milestone 4: Assessment → Memory (Write Path)

**Branch:** `feature/v2-memory-m4`
**Builds on:** Milestone 1, Milestone 2
**Goal:** Assessment creates experiment record in memory

---

## E2E Test Scenario

**Purpose:** Verify assessments are parsed and saved to memory
**Prerequisites:** M1 + M2 complete, memory directory exists

```bash
# 1. Count experiments before
BEFORE=$(ls memory/experiments/ | wc -l)
echo "Experiments before: $BEFORE"

# 2. Run a full research cycle (or simulate assessment)
# Option A: Full cycle via API
curl -X POST http://localhost:8000/api/v1/agent/trigger \
  -H "Content-Type: application/json" \
  -d '{"trigger_reason": "start_new_cycle"}'

# Wait for completion...
# Option B: Unit test that simulates assessment worker

# 3. Count experiments after
AFTER=$(ls memory/experiments/ | wc -l)
echo "Experiments after: $AFTER"

# 4. Verify new experiment file
NEW_EXP=$(ls -t memory/experiments/ | head -1)
echo "New experiment: $NEW_EXP"
cat "memory/experiments/$NEW_EXP"

# Expected: File contains:
# - id: exp_YYYYMMDD_...
# - context: from strategy config
# - results: from training/backtest
# - assessment: parsed verdict, observations, hypotheses

# 5. Verify via Python
uv run python -c "
from ktrdr.agents.memory import load_experiments

exps = load_experiments(n=1)
assert len(exps) == 1
exp = exps[0]

assert 'id' in exp
assert 'context' in exp
assert 'results' in exp
assert 'assessment' in exp
assert exp['assessment'].get('verdict') in ['strong_signal', 'weak_signal', 'no_signal', 'overfit', 'unknown']

print(f'Latest experiment: {exp[\"id\"]}')
print(f'Verdict: {exp[\"assessment\"].get(\"verdict\")}')
print('OK')
"
```

**Success Criteria:**
- [ ] Assessment worker calls HaikuBrain.parse_assessment()
- [ ] Assessment worker calls memory.save_experiment()
- [ ] Experiment record has correct context from strategy config
- [ ] Experiment record has results from training/backtest
- [ ] Experiment record has parsed assessment
- [ ] Malformed assessment still creates record (graceful)

---

## Task 4.1: Add Strategy Config to Assessment Context

**File:** `ktrdr/agents/workers/assessment_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Ensure the assessment worker has access to the full strategy configuration, not just the path. This is needed to populate the experiment record's context field.

**Implementation Notes:**
- Strategy config may already be loaded somewhere in the flow
- If not, load it from the strategy_path
- Pass to parse_assessment as context

**Code sketch:**
```python
async def run(self, parent_operation_id: str, results: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    # ... existing code ...

    # Get strategy info from parent operation
    parent_op = await self.ops.get_operation(parent_operation_id)
    strategy_name = parent_op.metadata.parameters.get("strategy_name")
    strategy_path = parent_op.metadata.parameters.get("strategy_path")

    # NEW: Load strategy config for context
    strategy_config = self._load_strategy_config(strategy_path)

    # ... rest of assessment flow ...


def _load_strategy_config(self, strategy_path: str | None) -> dict:
    """Load strategy configuration from YAML file."""
    if not strategy_path:
        return {}
    try:
        from pathlib import Path
        import yaml
        path = Path(strategy_path)
        if path.exists():
            return yaml.safe_load(path.read_text())
    except Exception as e:
        logger.warning(f"Failed to load strategy config: {e}")
    return {}
```

**Tests:** `tests/unit/agents/test_assessment_worker.py`
- [ ] `test_load_strategy_config_success` — loads valid YAML
- [ ] `test_load_strategy_config_missing` — returns {} for missing file
- [ ] `test_load_strategy_config_invalid` — returns {} for invalid YAML

**Acceptance Criteria:**
- [ ] Strategy config loaded from file
- [ ] Graceful handling of missing/invalid files
- [ ] Config available for context extraction

---

## Task 4.2: Build ExperimentRecord from Assessment

**File:** `ktrdr/agents/workers/assessment_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1.5 hours

**Description:**
After getting the parsed assessment, build an ExperimentRecord with full context and save to memory.

**Implementation Notes:**
- Context extracted from strategy_config (indicators, timeframe, etc.)
- Results from training_metrics and backtest_metrics
- Assessment from ParsedAssessment
- Generate ID using memory.generate_experiment_id()

**Code sketch:**
```python
from ktrdr.agents.memory import (
    ExperimentRecord,
    save_experiment,
    generate_experiment_id,
)
from ktrdr.llm.haiku_brain import HaikuBrain


async def run(self, parent_operation_id: str, results: dict[str, Any], model: str | None = None) -> dict[str, Any]:
    # ... existing assessment code ...

    # After getting assessment dict from tool or text parsing:
    assessment = ...  # existing code

    # NEW: Parse assessment with HaikuBrain for structured observations
    brain = HaikuBrain()
    parsed = brain.parse_assessment(
        output=result.output if hasattr(result, 'output') else str(assessment),
        context={
            "strategy_config": strategy_config,
            "training_results": results.get("training", {}),
            "backtest_results": results.get("backtest", {}),
        },
    )

    # NEW: Save to memory
    await self._save_to_memory(
        strategy_name=strategy_name,
        strategy_config=strategy_config,
        training_metrics=results.get("training", {}),
        backtest_metrics=results.get("backtest", {}),
        parsed_assessment=parsed,
    )

    # ... existing completion code ...


async def _save_to_memory(
    self,
    strategy_name: str,
    strategy_config: dict,
    training_metrics: dict,
    backtest_metrics: dict,
    parsed_assessment,
) -> None:
    """Save experiment record to memory."""
    try:
        context = self._extract_context(strategy_config)
        results = self._extract_results(training_metrics, backtest_metrics)

        record = ExperimentRecord(
            id=generate_experiment_id(),
            timestamp=datetime.now().isoformat(),
            strategy_name=strategy_name,
            context=context,
            results=results,
            assessment={
                "verdict": parsed_assessment.verdict,
                "observations": parsed_assessment.observations,
                "hypotheses": parsed_assessment.hypotheses,
                "limitations": parsed_assessment.limitations,
            },
            source="agent",
        )

        path = save_experiment(record)
        logger.info(f"Saved experiment to memory: {path}")

    except Exception as e:
        # Memory save failure should not fail the assessment
        logger.error(f"Failed to save experiment to memory: {e}")


def _extract_context(self, strategy_config: dict) -> dict:
    """Extract context fields from strategy config."""
    indicators = [ind.get("name") for ind in strategy_config.get("indicators", [])]
    training_data = strategy_config.get("training_data", {})
    training = strategy_config.get("training", {})

    return {
        "indicators": indicators,
        "composition": "solo" if len(indicators) == 1 else "pair" if len(indicators) == 2 else "ensemble",
        "timeframe": training_data.get("timeframes", {}).get("list", ["1h"])[0],
        "symbol": training_data.get("symbols", {}).get("list", ["EURUSD"])[0],
        "zigzag_threshold": training.get("labels", {}).get("zigzag_threshold", 0.02),
        "nn_architecture": strategy_config.get("model", {}).get("architecture", {}).get("hidden_layers", []),
    }


def _extract_results(self, training_metrics: dict, backtest_metrics: dict) -> dict:
    """Extract results fields from metrics."""
    return {
        "test_accuracy": training_metrics.get("accuracy", 0),
        "val_accuracy": training_metrics.get("val_accuracy", 0),
        "val_test_gap": abs(
            training_metrics.get("val_accuracy", 0) - training_metrics.get("accuracy", 0)
        ),
        "sharpe_ratio": backtest_metrics.get("sharpe_ratio"),
        "total_trades": backtest_metrics.get("total_trades"),
        "win_rate": backtest_metrics.get("win_rate"),
    }
```

**Tests:** `tests/unit/agents/test_assessment_worker.py`
- [ ] `test_save_to_memory_creates_file` — file exists after save
- [ ] `test_save_to_memory_correct_content` — all fields populated
- [ ] `test_save_to_memory_failure_continues` — assessment still succeeds
- [ ] `test_extract_context_from_config` — correct fields extracted
- [ ] `test_extract_results_from_metrics` — correct fields extracted

**Acceptance Criteria:**
- [ ] ExperimentRecord built with all fields
- [ ] Context extracted from strategy config
- [ ] Results extracted from metrics
- [ ] Record saved to memory/experiments/
- [ ] Memory failure doesn't fail assessment

---

## Task 4.3: Handle Malformed Assessment Gracefully

**File:** `ktrdr/agents/workers/assessment_worker.py` (MODIFY)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Ensure that even when the agent produces malformed output, we still create an experiment record with what we can extract.

**Implementation Notes:**
- HaikuBrain.parse_assessment() already returns ParsedAssessment.empty() on failure
- We should still save the record with verdict="unknown"
- Raw assessment text preserved in the record
- Log warning but don't fail

**Code sketch:**
```python
async def _save_to_memory(self, ...):
    try:
        # ... existing code ...

        # Even if parsed_assessment.verdict is "unknown", still save
        record = ExperimentRecord(
            id=generate_experiment_id(),
            timestamp=datetime.now().isoformat(),
            strategy_name=strategy_name,
            context=context,
            results=results,
            assessment={
                "verdict": parsed_assessment.verdict,
                "observations": parsed_assessment.observations or ["Assessment could not be parsed"],
                "hypotheses": parsed_assessment.hypotheses,
                "limitations": parsed_assessment.limitations,
                "raw_text": parsed_assessment.raw_text[:1000],  # Preserve for debugging
            },
            source="agent",
        )

        path = save_experiment(record)

        if parsed_assessment.verdict == "unknown":
            logger.warning(f"Saved experiment with unknown verdict: {path}")
        else:
            logger.info(f"Saved experiment to memory: {path}")

    except Exception as e:
        logger.error(f"Failed to save experiment to memory: {e}")
```

**Tests:** `tests/unit/agents/test_assessment_worker.py`
- [ ] `test_malformed_assessment_still_saves` — record created with unknown verdict
- [ ] `test_malformed_assessment_has_raw_text` — raw text preserved
- [ ] `test_malformed_assessment_logs_warning` — warning logged

**Acceptance Criteria:**
- [ ] Malformed assessment still creates experiment record
- [ ] Verdict set to "unknown" when parsing fails
- [ ] Raw text preserved for debugging
- [ ] Warning logged for visibility

---

## Task 4.4: Add Integration Test

**File:** `tests/integration/agents/test_assessment_memory.py` (NEW)
**Type:** CODING
**Estimated time:** 1 hour

**Description:**
Create an integration test that verifies the full flow: assessment worker → HaikuBrain → memory.

**Implementation Notes:**
- Mock the Anthropic API (don't call real Claude)
- Mock HaikuBrain to return predictable ParsedAssessment
- Verify file is created with correct content

**Code sketch:**
```python
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock

from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker
from ktrdr.agents.memory import EXPERIMENTS_DIR, load_experiments


@pytest.fixture
def mock_ops_service():
    """Mock operations service."""
    ops = AsyncMock()
    ops.get_operation.return_value = Mock(
        metadata=Mock(parameters={
            "strategy_name": "test_strategy",
            "strategy_path": None,
        })
    )
    ops.create_operation.return_value = Mock(operation_id="test_op")
    return ops


@pytest.fixture
def mock_invoker():
    """Mock Anthropic invoker."""
    invoker = AsyncMock()
    invoker.run.return_value = Mock(
        success=True,
        output="## Assessment\n### Verdict\nstrong_signal",
        input_tokens=100,
        output_tokens=50,
    )
    return invoker


@pytest.mark.asyncio
async def test_assessment_saves_to_memory(mock_ops_service, mock_invoker, tmp_path):
    """Assessment worker saves experiment record to memory."""
    # Patch memory directory
    with patch("ktrdr.agents.memory.MEMORY_DIR", tmp_path):
        with patch("ktrdr.agents.memory.EXPERIMENTS_DIR", tmp_path / "experiments"):
            worker = AgentAssessmentWorker(mock_ops_service, invoker=mock_invoker)

            # Mock HaikuBrain
            with patch("ktrdr.agents.workers.assessment_worker.HaikuBrain") as MockBrain:
                mock_brain = MockBrain.return_value
                mock_brain.parse_assessment.return_value = Mock(
                    verdict="strong_signal",
                    observations=["Test observation"],
                    hypotheses=[],
                    limitations=[],
                    raw_text="test",
                )

                # Set up tool executor to return assessment
                worker.tool_executor.last_saved_assessment = {
                    "verdict": "promising",
                    "strengths": ["Good"],
                    "weaknesses": ["None"],
                    "suggestions": ["Continue"],
                }
                worker.tool_executor.last_saved_assessment_path = "/test/path"

                result = await worker.run(
                    parent_operation_id="parent_op",
                    results={
                        "training": {"accuracy": 0.65},
                        "backtest": {"sharpe_ratio": 0.5},
                    },
                )

            # Verify experiment saved
            exp_dir = tmp_path / "experiments"
            assert exp_dir.exists()
            files = list(exp_dir.glob("*.yaml"))
            assert len(files) == 1
```

**Acceptance Criteria:**
- [ ] Integration test passes
- [ ] Test verifies file creation
- [ ] Test verifies file content
- [ ] Test uses mocks (no real API calls)

---

## Completion Checklist

- [ ] All tasks complete and committed
- [ ] Unit tests pass: `uv run pytest tests/unit/agents/test_assessment_worker.py -v`
- [ ] Integration tests pass: `uv run pytest tests/integration/agents/test_assessment_memory.py -v`
- [ ] E2E test passes (assessment creates experiment file)
- [ ] Quality gates pass: `make quality`
- [ ] No regressions in assessment flow
- [ ] Experiment records created with correct schema
- [ ] Malformed assessments still create records
