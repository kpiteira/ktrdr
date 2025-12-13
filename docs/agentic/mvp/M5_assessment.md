# Milestone 5: Assessment Worker

**Branch**: `feature/agent-mvp`
**Builds On**: M4 (Backtest Integration)
**Capability**: Real Claude assessment after backtest, saved to disk

---

## Why This Milestone

Completes the research cycle with Claude's assessment of the results. After backtest passes the gate, Claude evaluates the strategy's performance and records observations for future learning.

---

## E2E Test

```bash
ktrdr agent trigger
# Wait for full cycle completion (~20-30 minutes total)

ktrdr agent status
# Expected: status = idle (cycle completed)

cat strategies/<strategy_name>/assessment.json
# Expected: JSON with verdict, strengths, weaknesses, suggestions

ktrdr operations status <agent_research_op_id>
# Expected: COMPLETED with full result summary
```

---

## Task 5.1: Create Assessment Prompt

**File(s)**: `ktrdr/agents/prompts.py`
**Type**: CODING

**Description**: Add assessment prompt builder that formats training and backtest results for Claude to evaluate.

**Implementation Notes**:
```python
# Add to ktrdr/agents/prompts.py

from dataclasses import dataclass
from typing import Any


@dataclass
class AssessmentContext:
    """Context for building the assessment prompt."""
    operation_id: str
    strategy_name: str
    strategy_path: str
    training_metrics: dict[str, Any]
    backtest_metrics: dict[str, Any]


ASSESSMENT_SYSTEM_PROMPT = """You are an expert trading strategy evaluator. Your role is to:

1. Analyze the training and backtest results objectively
2. Identify strengths and weaknesses of the strategy
3. Provide actionable suggestions for improvement
4. Give an overall verdict on the strategy's potential

Be honest and specific. Reference actual numbers from the results.
Use the save_assessment tool to record your evaluation."""


def get_assessment_prompt(context: AssessmentContext) -> str:
    """Build prompt for Claude to assess strategy results.

    Args:
        context: Assessment context with metrics.

    Returns:
        Formatted prompt string.
    """
    training = context.training_metrics
    backtest = context.backtest_metrics

    return f"""# Strategy Assessment Request

## Strategy Information
- **Name**: {context.strategy_name}
- **Operation ID**: {context.operation_id}
- **Configuration**: {context.strategy_path}

## Training Results
- **Accuracy**: {training.get('accuracy', 0):.1%}
- **Final Loss**: {training.get('final_loss', 0):.4f}
- **Initial Loss**: {training.get('initial_loss', 0):.4f}
- **Loss Improvement**: {_calc_loss_improvement(training):.1%}

## Backtest Results
- **Sharpe Ratio**: {backtest.get('sharpe_ratio', 0):.2f}
- **Win Rate**: {backtest.get('win_rate', 0):.1%}
- **Max Drawdown**: {backtest.get('max_drawdown', 0):.1%}
- **Total Return**: {backtest.get('total_return', 0):.1%}
- **Total Trades**: {backtest.get('total_trades', 0)}

## Your Task

Analyze these results and provide your assessment:

1. **Verdict**: Is this strategy "promising", "mediocre", or "poor"?
2. **Strengths**: What aspects performed well? (list 2-4 points)
3. **Weaknesses**: What aspects need improvement? (list 2-4 points)
4. **Suggestions**: How could the strategy be improved? (list 2-4 points)

Use the `save_assessment` tool to record your evaluation.
"""


def _calc_loss_improvement(metrics: dict[str, Any]) -> float:
    """Calculate loss improvement percentage."""
    initial = metrics.get("initial_loss", 0)
    final = metrics.get("final_loss", 0)
    if initial > 0:
        return (initial - final) / initial
    return 0
```

**Acceptance Criteria**:
- [ ] Prompt includes all relevant training metrics
- [ ] Prompt includes all relevant backtest metrics
- [ ] Clear instructions for Claude
- [ ] Loss improvement calculated correctly

---

## Task 5.2: Create save_assessment Tool

**File(s)**: `ktrdr/agents/tools.py`, `ktrdr/agents/executor.py`
**Type**: CODING

**Description**: Add tool for Claude to save assessment results.

**Implementation Notes**:

In `ktrdr/agents/tools.py`:
```python
SAVE_ASSESSMENT_TOOL = {
    "name": "save_assessment",
    "description": "Save your assessment of the strategy to disk. Call this after analyzing the results.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["promising", "mediocre", "poor"],
                "description": "Overall verdict on the strategy"
            },
            "strengths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of strategy strengths (2-4 items)"
            },
            "weaknesses": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of strategy weaknesses (2-4 items)"
            },
            "suggestions": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of improvement suggestions (2-4 items)"
            },
        },
        "required": ["verdict", "strengths", "weaknesses", "suggestions"]
    }
}

# Add to AGENT_TOOLS list
AGENT_TOOLS = [
    # ... existing tools ...
    SAVE_ASSESSMENT_TOOL,
]
```

In `ktrdr/agents/executor.py`:
```python
import json
import os
from datetime import datetime

class ToolExecutor:
    def __init__(self):
        # ... existing init ...
        self.last_saved_assessment: dict | None = None
        self.last_saved_assessment_path: str | None = None

    async def execute(self, tool_name: str, params: dict) -> dict:
        if tool_name == "save_assessment":
            return await self._execute_save_assessment(params)
        # ... other tools ...

    async def _execute_save_assessment(self, params: dict) -> dict:
        """Save assessment to strategy directory."""
        # Get strategy name from current context
        strategy_name = self._current_strategy_name

        if not strategy_name:
            return {"success": False, "error": "No strategy name set"}

        # Create assessment directory
        assessment_dir = f"strategies/{strategy_name}"
        os.makedirs(assessment_dir, exist_ok=True)

        # Build assessment data
        assessment = {
            "verdict": params["verdict"],
            "strengths": params["strengths"],
            "weaknesses": params["weaknesses"],
            "suggestions": params["suggestions"],
            "assessed_at": datetime.utcnow().isoformat(),
        }

        # Save to file
        assessment_path = f"{assessment_dir}/assessment.json"
        with open(assessment_path, "w") as f:
            json.dump(assessment, f, indent=2)

        # Track for result
        self.last_saved_assessment = assessment
        self.last_saved_assessment_path = assessment_path

        return {
            "success": True,
            "path": assessment_path,
            "message": f"Assessment saved to {assessment_path}"
        }
```

**Unit Tests** (`tests/unit/agent_tests/test_assessment_tool.py`):
- [ ] Test: save_assessment creates JSON file
- [ ] Test: Assessment contains all required fields
- [ ] Test: Assessment directory created if not exists
- [ ] Test: Error returned if no strategy name set
- [ ] Test: Timestamp included in assessment

**Acceptance Criteria**:
- [ ] Tool definition in AGENT_TOOLS
- [ ] Executor saves JSON to `strategies/{name}/assessment.json`
- [ ] Assessment structure validated
- [ ] Tracks last saved assessment for result

---

## Task 5.3: Create AgentAssessmentWorker

**File(s)**: `ktrdr/agents/workers/assessment_worker.py`
**Type**: CODING

**Description**: Create assessment worker that uses Claude to evaluate results.

**Implementation Notes**:
```python
# ktrdr/agents/workers/assessment_worker.py
"""Assessment worker that uses Claude to evaluate strategy results."""

import asyncio
from typing import Any

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.agents.invoker import AnthropicAgentInvoker
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.agents.prompts import (
    get_assessment_prompt,
    AssessmentContext,
    ASSESSMENT_SYSTEM_PROMPT,
)

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""
    pass


class AgentAssessmentWorker:
    """Worker that uses Claude to assess strategy results."""

    def __init__(
        self,
        operations_service: OperationsService,
        invoker: AnthropicAgentInvoker | None = None,
    ):
        self.ops = operations_service
        self.invoker = invoker or AnthropicAgentInvoker()
        self.tool_executor = ToolExecutor()

    async def run(
        self,
        parent_operation_id: str,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        """Run assessment phase using Claude.

        Args:
            parent_operation_id: Parent AGENT_RESEARCH operation ID.
            results: Dict with 'training' and 'backtest' result dicts.

        Returns:
            Dict with verdict, assessment_path, and token counts.
        """
        logger.info("Starting assessment phase", parent_operation_id=parent_operation_id)

        # Get parent operation for strategy info
        parent_op = await self.ops.get_operation(parent_operation_id)
        strategy_name = parent_op.metadata.get("strategy_name")
        strategy_path = parent_op.metadata.get("strategy_path")

        # Set strategy name in executor for save_assessment tool
        self.tool_executor._current_strategy_name = strategy_name

        # Create child operation
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_ASSESSMENT,
            metadata={"parent_operation_id": parent_operation_id},
        )

        try:
            # Build context for prompt
            context = AssessmentContext(
                operation_id=op.operation_id,
                strategy_name=strategy_name,
                strategy_path=strategy_path,
                training_metrics=results["training"],
                backtest_metrics=results["backtest"],
            )
            prompt = get_assessment_prompt(context)

            # Run Claude
            result = await self.invoker.run(
                prompt=prompt,
                tools=AGENT_TOOLS,
                system_prompt=ASSESSMENT_SYSTEM_PROMPT,
                tool_executor=self.tool_executor,
            )

            if not result.success:
                raise WorkerError(f"Claude assessment failed: {result.error}")

            # Get assessment from tool executor
            assessment = self.tool_executor.last_saved_assessment
            assessment_path = self.tool_executor.last_saved_assessment_path

            if not assessment:
                raise WorkerError("Claude did not save an assessment")

            # Build result
            assessment_result = {
                "success": True,
                "verdict": assessment["verdict"],
                "strengths": assessment["strengths"],
                "weaknesses": assessment["weaknesses"],
                "suggestions": assessment["suggestions"],
                "assessment_path": assessment_path,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            # Complete child operation
            await self.ops.complete_operation(op.operation_id, assessment_result)

            logger.info(
                "Assessment phase completed",
                verdict=assessment["verdict"],
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )

            return assessment_result

        except asyncio.CancelledError:
            await self.ops.cancel_operation(op.operation_id, "Parent cancelled")
            raise
        except Exception as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise WorkerError(f"Assessment failed: {e}") from e
```

**Unit Tests** (`tests/unit/agent_tests/test_assessment_worker.py`):
- [ ] Test: Creates AGENT_ASSESSMENT operation
- [ ] Test: Passes training and backtest metrics to prompt
- [ ] Test: Returns verdict from save_assessment tool
- [ ] Test: Returns token counts
- [ ] Test: Raises WorkerError if assessment not saved
- [ ] Test: CancelledError propagates correctly

**Acceptance Criteria**:
- [ ] Creates AGENT_ASSESSMENT child operation
- [ ] Uses assessment prompt with results
- [ ] Saves assessment via tool
- [ ] Returns token counts and verdict

---

## Task 5.4: Wire Assessment into Orchestrator

**File(s)**: `ktrdr/api/services/agent_service.py`
**Type**: CODING

**Description**: Replace stub assessment worker with real worker.

**Implementation Notes**:
```python
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.training_adapter import TrainingWorkerAdapter
from ktrdr.agents.workers.backtest_adapter import BacktestWorkerAdapter
from ktrdr.agents.workers.assessment_worker import AgentAssessmentWorker

class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),
                training_worker=TrainingWorkerAdapter(self.ops),
                backtest_worker=BacktestWorkerAdapter(self.ops),
                assessment_worker=AgentAssessmentWorker(self.ops),  # Real assessment
            )
        return self._worker
```

Also update research_worker.py to store assessment result:
```python
# Phase 4: Assessment
await self._update_phase(operation_id, "assessing")
assessment_result = await self._run_child(
    operation_id, "assessment", self.assessment_worker.run,
    operation_id, {
        "training": training_result,
        "backtest": backtest_result,
    }
)

# Store assessment result
await self.ops.update_operation_metadata(operation_id, {
    "assessment_verdict": assessment_result["verdict"],
    "assessment_path": assessment_result["assessment_path"],
})

# Return final result
return {
    "success": True,
    "strategy_name": design_result["strategy_name"],
    "verdict": assessment_result["verdict"],
    "total_tokens": (
        design_result.get("input_tokens", 0) +
        design_result.get("output_tokens", 0) +
        assessment_result.get("input_tokens", 0) +
        assessment_result.get("output_tokens", 0)
    ),
}
```

**Acceptance Criteria**:
- [ ] Real assessment runs after backtest gate passes
- [ ] Assessment completion → cycle completes
- [ ] Assessment verdict in parent metadata
- [ ] Total token usage tracked

---

## Task 5.5: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_full_cycle.py`
**Type**: CODING

**Description**: Test complete cycle from design through assessment.

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_full_cycle.py
"""Integration test for full research cycle."""

import os
import json
import pytest
import asyncio

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.api.models.operations import OperationStatus


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_full_cycle_completes():
    """Full cycle from design to assessment completes."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    assert result["triggered"] is True
    op_id = result["operation_id"]

    # Wait for completion (up to 30 minutes)
    for _ in range(900):
        status = await service.get_status()
        if status.get("status") == "idle":
            break
        await asyncio.sleep(2)

    # Verify completion
    op = await ops.get_operation(op_id)
    assert op.status == OperationStatus.COMPLETED
    assert op.result_summary.get("success") is True
    assert "strategy_name" in op.result_summary
    assert "verdict" in op.result_summary


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_full_cycle_creates_files():
    """Full cycle creates strategy and assessment files."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for completion
    for _ in range(900):
        status = await service.get_status()
        if status.get("status") == "idle":
            break
        await asyncio.sleep(2)

    # Get strategy name
    op = await ops.get_operation(op_id)
    if op.status != OperationStatus.COMPLETED:
        pytest.skip("Cycle did not complete (gate may have failed)")

    strategy_name = op.result_summary.get("strategy_name")
    assert strategy_name is not None

    # Check strategy file
    strategy_path = f"strategies/{strategy_name}.yaml"
    assert os.path.exists(strategy_path), f"Strategy file not found: {strategy_path}"

    # Check assessment file
    assessment_path = f"strategies/{strategy_name}/assessment.json"
    assert os.path.exists(assessment_path), f"Assessment file not found: {assessment_path}"

    # Verify assessment content
    with open(assessment_path) as f:
        assessment = json.load(f)

    assert "verdict" in assessment
    assert assessment["verdict"] in ["promising", "mediocre", "poor"]
    assert "strengths" in assessment
    assert "weaknesses" in assessment
    assert "suggestions" in assessment


@pytest.mark.integration
async def test_all_child_operations_created():
    """Full cycle creates all child operations."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for completion (with stubs if no API key)
    for _ in range(60):
        status = await service.get_status()
        if status.get("status") == "idle":
            break
        await asyncio.sleep(1)

    # Check parent metadata has all child IDs
    op = await ops.get_operation(op_id)

    # At minimum, design should have run
    assert op.metadata.get("design_op_id") is not None

    # If completed, all should be present
    if op.status == OperationStatus.COMPLETED:
        assert op.metadata.get("training_op_id") is not None
        assert op.metadata.get("backtest_op_id") is not None
        assert op.metadata.get("assessment_op_id") is not None
```

**Acceptance Criteria**:
- [ ] Full cycle completes (design → train → backtest → assess)
- [ ] Strategy YAML file created
- [ ] Assessment JSON file created
- [ ] All child operations in parent metadata
- [ ] Final result has strategy_name and verdict

---

## Milestone 5 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M5: Full Cycle Verification ==="

# Check API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    exit 1
fi

# Trigger cycle
echo "1. Triggering full cycle..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   Operation: $OP_ID"

# Wait for completion
echo ""
echo "2. Waiting for full cycle (this may take 20-30 minutes)..."
START_TIME=$(date +%s)

for i in {1..900}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase // .status')

    if [ "$PHASE" == "idle" ]; then
        END_TIME=$(date +%s)
        DURATION=$((END_TIME - START_TIME))
        echo "   Cycle completed in ${DURATION}s"
        break
    fi

    # Show progress every 30 seconds
    if [ $((i % 15)) -eq 0 ]; then
        echo "   [$i] Phase: $PHASE"
    fi

    sleep 2
done

# Check final status
echo ""
echo "3. Checking final status..."
OP_DATA=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID)
OP_STATUS=$(echo $OP_DATA | jq -r '.data.status')
echo "   Status: $OP_STATUS"

if [ "$OP_STATUS" == "failed" ]; then
    ERROR=$(echo $OP_DATA | jq -r '.data.error_message')
    echo "   Error: $ERROR"
    echo ""
    echo "   Note: Gate failures are expected if strategy performs poorly"
    exit 0
fi

if [ "$OP_STATUS" != "completed" ]; then
    echo "   FAIL: Unexpected status"
    exit 1
fi

# Get strategy info
STRATEGY=$(echo $OP_DATA | jq -r '.data.result_summary.strategy_name')
VERDICT=$(echo $OP_DATA | jq -r '.data.result_summary.verdict')
echo "   Strategy: $STRATEGY"
echo "   Verdict: $VERDICT"

# Check files
echo ""
echo "4. Checking output files..."

STRATEGY_FILE="strategies/$STRATEGY.yaml"
if [ -f "$STRATEGY_FILE" ]; then
    echo "   PASS: Strategy file exists: $STRATEGY_FILE"
else
    echo "   FAIL: Strategy file not found"
    exit 1
fi

ASSESSMENT_FILE="strategies/$STRATEGY/assessment.json"
if [ -f "$ASSESSMENT_FILE" ]; then
    echo "   PASS: Assessment file exists: $ASSESSMENT_FILE"
else
    echo "   FAIL: Assessment file not found"
    exit 1
fi

# Show assessment
echo ""
echo "5. Assessment content:"
cat "$ASSESSMENT_FILE" | jq

# Show all child operations
echo ""
echo "6. Child operations:"
echo "   Design: $(echo $OP_DATA | jq -r '.data.metadata.design_op_id')"
echo "   Training: $(echo $OP_DATA | jq -r '.data.metadata.training_op_id')"
echo "   Backtest: $(echo $OP_DATA | jq -r '.data.metadata.backtest_op_id')"
echo "   Assessment: $(echo $OP_DATA | jq -r '.data.metadata.assessment_op_id')"

# Token usage
echo ""
echo "7. Token usage:"
TOTAL_TOKENS=$(echo $OP_DATA | jq -r '.data.result_summary.total_tokens')
echo "   Total tokens: $TOTAL_TOKENS"

echo ""
echo "=== M5 Complete - Full cycle works! ==="
```

---

## Files Created/Modified in M5

**New files**:
```
ktrdr/agents/workers/assessment_worker.py
tests/unit/agent_tests/test_assessment_tool.py
tests/unit/agent_tests/test_assessment_worker.py
tests/integration/agent_tests/test_agent_full_cycle.py
```

**Modified files**:
```
ktrdr/agents/prompts.py                  # Add AssessmentContext and prompt
ktrdr/agents/tools.py                    # Add SAVE_ASSESSMENT_TOOL
ktrdr/agents/executor.py                 # Add save_assessment handler
ktrdr/agents/workers/research_worker.py  # Store assessment result
ktrdr/api/services/agent_service.py      # Use real assessment worker
```

---

*Estimated effort: ~4 hours*
