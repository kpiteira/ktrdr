# Milestone 2: Design Worker

**Branch**: `feature/agent-mvp`
**Builds On**: M1 (Orchestrator Shell)
**Capability**: Real Claude call designs a strategy and saves it to disk

---

## Why This Milestone

Replaces the stub design worker with real Claude integration. After this milestone, the agent actually creates novel strategy configurations.

---

## E2E Test

```bash
ktrdr agent trigger
# Wait for design phase to complete (~1-2 minutes)

ktrdr agent status
# Expected: Phase = training, strategy_name populated

# Verify strategy file
ls strategies/
cat strategies/<strategy_name>.yaml
# Expected: Valid strategy configuration with indicators, fuzzy sets, etc.
```

---

## Task 2.1: Create AgentDesignWorker

**File(s)**: `ktrdr/agents/workers/design_worker.py`
**Type**: CODING

**Description**: Create real design worker that uses AnthropicAgentInvoker.

**Implementation Notes**:
```python
# ktrdr/agents/workers/design_worker.py
"""Design worker that uses Claude to create strategies."""

import asyncio
from typing import Any

from ktrdr import get_logger
from ktrdr.api.models.operations import OperationType
from ktrdr.api.services.operations_service import OperationsService
from ktrdr.agents.invoker import AnthropicAgentInvoker
from ktrdr.agents.executor import ToolExecutor
from ktrdr.agents.tools import AGENT_TOOLS
from ktrdr.agents.prompts import get_strategy_designer_prompt, PromptContext
from ktrdr.agents.strategy_utils import get_recent_strategies

logger = get_logger(__name__)


class WorkerError(Exception):
    """Error during worker execution."""
    pass


class AgentDesignWorker:
    """Worker that uses Claude to design trading strategies."""

    # System prompt for strategy designer
    SYSTEM_PROMPT = """You are an expert trading strategy designer. Your goal is to create
novel, well-reasoned trading strategies that can be trained and backtested.

You have access to tools for:
- Viewing available indicators and symbols
- Validating strategy configurations
- Saving strategy configurations to disk

Design strategies that are:
- Novel (different from recent strategies)
- Well-reasoned (clear hypothesis about why it should work)
- Testable (uses available indicators and symbols)
- Realistic (reasonable parameter values)

Always validate your configuration before saving it."""

    def __init__(
        self,
        operations_service: OperationsService,
        invoker: AnthropicAgentInvoker | None = None,
    ):
        self.ops = operations_service
        self.invoker = invoker or AnthropicAgentInvoker()
        self.tool_executor = ToolExecutor()

    async def run(self, parent_operation_id: str) -> dict[str, Any]:
        """Run design phase using Claude.

        Args:
            parent_operation_id: The parent AGENT_RESEARCH operation ID.

        Returns:
            Dict with strategy_name, strategy_path, and token counts.
        """
        logger.info("Starting design phase", parent_operation_id=parent_operation_id)

        # Create child operation for tracking
        op = await self.ops.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata={"parent_operation_id": parent_operation_id},
        )

        try:
            # Build context for prompt
            context = await self._build_prompt_context(op.operation_id)
            prompt = get_strategy_designer_prompt(context)

            # Run Claude
            result = await self.invoker.run(
                prompt=prompt,
                tools=AGENT_TOOLS,
                system_prompt=self.SYSTEM_PROMPT,
                tool_executor=self.tool_executor,
            )

            if not result.success:
                raise WorkerError(f"Claude design failed: {result.error}")

            # Get strategy info from tool executor
            strategy_name = self.tool_executor.last_saved_strategy_name
            strategy_path = self.tool_executor.last_saved_strategy_path

            if not strategy_name:
                raise WorkerError("Claude did not save a strategy configuration")

            # Build result
            design_result = {
                "success": True,
                "strategy_name": strategy_name,
                "strategy_path": strategy_path,
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

            # Complete child operation
            await self.ops.complete_operation(op.operation_id, design_result)

            logger.info(
                "Design phase completed",
                strategy_name=strategy_name,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )

            return design_result

        except asyncio.CancelledError:
            await self.ops.cancel_operation(op.operation_id, "Parent cancelled")
            raise
        except Exception as e:
            await self.ops.fail_operation(op.operation_id, str(e))
            raise WorkerError(f"Design failed: {e}") from e

    async def _build_prompt_context(self, operation_id: str) -> PromptContext:
        """Build context for the strategy designer prompt."""
        # Get available indicators
        available_indicators = self._get_available_indicators()

        # Get available symbols (ones with data)
        available_symbols = await self._get_available_symbols()

        # Get recent strategies to avoid repetition
        recent_strategies = get_recent_strategies(limit=5)

        return PromptContext(
            operation_id=operation_id,
            available_indicators=available_indicators,
            available_symbols=available_symbols,
            recent_strategies=recent_strategies,
        )

    def _get_available_indicators(self) -> list[dict[str, Any]]:
        """Get list of available indicators."""
        # This could be dynamic, but for now use a static list
        return [
            {"name": "RSI", "params": ["period"], "description": "Relative Strength Index"},
            {"name": "MACD", "params": ["fast", "slow", "signal"], "description": "Moving Average Convergence Divergence"},
            {"name": "BB", "params": ["period", "std"], "description": "Bollinger Bands"},
            {"name": "SMA", "params": ["period"], "description": "Simple Moving Average"},
            {"name": "EMA", "params": ["period"], "description": "Exponential Moving Average"},
            {"name": "ATR", "params": ["period"], "description": "Average True Range"},
            {"name": "STOCH", "params": ["k_period", "d_period"], "description": "Stochastic Oscillator"},
        ]

    async def _get_available_symbols(self) -> list[str]:
        """Get list of symbols that have data available."""
        # TODO: Query actual data availability
        return ["EURUSD", "GBPUSD", "USDJPY", "AAPL", "MSFT", "GOOGL"]
```

**Unit Tests** (`tests/unit/agent_tests/test_design_worker.py`):
- [ ] Test: Prompt includes operation_id from context
- [ ] Test: Strategy path returned on success
- [ ] Test: WorkerError raised on invoker failure
- [ ] Test: WorkerError raised if no strategy saved
- [ ] Test: Token counts included in result
- [ ] Test: CancelledError propagates correctly
- [ ] Test: Child operation created and completed

**Acceptance Criteria**:
- [ ] Uses existing `AnthropicAgentInvoker`
- [ ] Uses existing prompt builder
- [ ] Saves strategy via `save_strategy_config` tool
- [ ] Returns token counts
- [ ] Creates AGENT_DESIGN child operation

---

## Task 2.2: Wire Design Worker into Orchestrator

**File(s)**:
- `ktrdr/agents/workers/research_worker.py`
- `ktrdr/api/services/agent_service.py`

**Type**: CODING

**Description**: Replace stub design worker with real worker in orchestrator.

**Implementation Notes**:

In `agent_service.py`:
```python
from ktrdr.agents.workers.design_worker import AgentDesignWorker
from ktrdr.agents.workers.stubs import (
    StubTrainingWorker,
    StubBacktestWorker,
    StubAssessmentWorker,
)

class AgentService:
    def _get_worker(self) -> AgentResearchWorker:
        if self._worker is None:
            self._worker = AgentResearchWorker(
                operations_service=self.ops,
                design_worker=AgentDesignWorker(self.ops),  # Real worker
                training_worker=StubTrainingWorker(),       # Still stub
                backtest_worker=StubBacktestWorker(),       # Still stub
                assessment_worker=StubAssessmentWorker(),   # Still stub
            )
        return self._worker
```

**Acceptance Criteria**:
- [ ] Real design worker called when phase enters "designing"
- [ ] Strategy name propagated to parent metadata
- [ ] Stub workers still used for other phases

---

## Task 2.3: Track Strategy in Parent Metadata

**File(s)**: `ktrdr/agents/workers/research_worker.py`
**Type**: CODING

**Description**: Store strategy info in parent operation metadata after design completes.

**Implementation Notes**:
```python
async def run(self, operation_id: str) -> dict[str, Any]:
    # Phase 1: Design
    await self._update_phase(operation_id, "designing")
    design_result = await self._run_child(...)

    # Store strategy info in parent metadata
    await self.ops.update_operation_metadata(operation_id, {
        "strategy_name": design_result["strategy_name"],
        "strategy_path": design_result["strategy_path"],
    })

    # Continue to training...
```

**Acceptance Criteria**:
- [ ] Parent metadata has `strategy_name` after design
- [ ] Parent metadata has `strategy_path` after design
- [ ] Status endpoint shows strategy_name

---

## Task 2.4: Add Indicator/Symbol Discovery Tools

**File(s)**: `ktrdr/agents/executor.py`
**Type**: CODING

**Description**: Implement `get_available_indicators` and `get_available_symbols` tool handlers.

**Implementation Notes**:
```python
# In ToolExecutor

async def _execute_get_available_indicators(self, params: dict) -> dict:
    """Return list of available indicators."""
    return {
        "indicators": [
            {"name": "RSI", "params": ["period"], "description": "Relative Strength Index"},
            {"name": "MACD", "params": ["fast", "slow", "signal"], "description": "MACD"},
            {"name": "BB", "params": ["period", "std"], "description": "Bollinger Bands"},
            {"name": "SMA", "params": ["period"], "description": "Simple Moving Average"},
            {"name": "EMA", "params": ["period"], "description": "Exponential Moving Average"},
            {"name": "ATR", "params": ["period"], "description": "Average True Range"},
            {"name": "STOCH", "params": ["k_period", "d_period"], "description": "Stochastic"},
        ]
    }

async def _execute_get_available_symbols(self, params: dict) -> dict:
    """Return list of symbols with data available."""
    # TODO: Query actual data service for symbols with data
    return {
        "symbols": ["EURUSD", "GBPUSD", "USDJPY", "AAPL", "MSFT", "GOOGL"]
    }
```

**Acceptance Criteria**:
- [ ] `get_available_indicators` returns indicator list
- [ ] `get_available_symbols` returns symbol list
- [ ] Agent can use these tools during design

---

## Task 2.5: Integration Test

**File(s)**: `tests/integration/agent_tests/test_agent_design_real.py`
**Type**: CODING

**Description**: Test real design worker (requires ANTHROPIC_API_KEY).

**Implementation Notes**:
```python
# tests/integration/agent_tests/test_agent_design_real.py
"""Integration test for real Claude design."""

import os
import pytest
import asyncio
import yaml

from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import OperationsService


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_real_design_creates_strategy():
    """Real Claude design creates valid strategy file."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    # Trigger
    result = await service.trigger()
    assert result["triggered"] is True
    op_id = result["operation_id"]

    # Wait for design to complete (training phase means design done)
    for _ in range(120):  # Up to 2 minutes
        status = await service.get_status()
        phase = status.get("phase", "")
        if phase in ["training", "backtesting", "assessing"]:
            break
        if status.get("status") == "idle":
            break
        await asyncio.sleep(1)

    # Get strategy name from status
    status = await service.get_status()
    strategy_name = status.get("strategy_name")
    assert strategy_name is not None, "No strategy name in status"

    # Verify file exists
    strategy_path = f"strategies/{strategy_name}.yaml"
    assert os.path.exists(strategy_path), f"Strategy file not found: {strategy_path}"

    # Verify valid YAML
    with open(strategy_path) as f:
        config = yaml.safe_load(f)

    assert "name" in config
    assert "indicators" in config or "fuzzy_sets" in config


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set"
)
async def test_design_worker_tracks_tokens():
    """Design worker records token usage."""
    ops = OperationsService()
    service = AgentService(operations_service=ops)

    result = await service.trigger()
    op_id = result["operation_id"]

    # Wait for design to complete
    for _ in range(120):
        op = await ops.get_operation(op_id)
        if op.metadata.get("phase") != "designing":
            break
        await asyncio.sleep(1)

    # Check design operation has tokens
    design_op_id = op.metadata.get("design_op_id")
    assert design_op_id is not None

    design_op = await ops.get_operation(design_op_id)
    assert design_op.result_summary.get("input_tokens", 0) > 0
    assert design_op.result_summary.get("output_tokens", 0) > 0
```

**Acceptance Criteria**:
- [ ] Strategy file created with valid YAML
- [ ] Strategy has required fields (name, indicators or fuzzy_sets)
- [ ] Token usage recorded in operation
- [ ] Test skipped if no API key

---

## Milestone 2 Verification Script

```bash
#!/bin/bash
set -e

echo "=== M2: Design Worker Verification ==="

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "ERROR: ANTHROPIC_API_KEY not set"
    echo "Export your API key and try again"
    exit 1
fi

# Trigger cycle
echo "1. Triggering cycle..."
RESULT=$(curl -s -X POST http://localhost:8000/api/v1/agent/trigger)
OP_ID=$(echo $RESULT | jq -r '.operation_id')
echo "   Operation: $OP_ID"

# Wait for design to complete (poll for training phase)
echo ""
echo "2. Waiting for design phase to complete..."
for i in {1..120}; do
    STATUS=$(curl -s http://localhost:8000/api/v1/agent/status)
    PHASE=$(echo $STATUS | jq -r '.phase')

    if [ "$PHASE" == "training" ] || [ "$PHASE" == "backtesting" ] || [ "$PHASE" == "assessing" ]; then
        echo "   Design complete! Now in phase: $PHASE"
        STRATEGY=$(echo $STATUS | jq -r '.strategy_name')
        break
    fi

    if [ "$PHASE" == "idle" ]; then
        echo "   Cycle completed (or failed)"
        break
    fi

    echo "   [$i] Phase: $PHASE"
    sleep 2
done

# Check strategy name
echo ""
echo "3. Checking strategy..."
if [ "$STRATEGY" == "null" ] || [ -z "$STRATEGY" ]; then
    echo "   FAIL: No strategy name in status"
    exit 1
fi
echo "   Strategy name: $STRATEGY"

# Check strategy file
echo ""
echo "4. Checking strategy file..."
STRATEGY_FILE="strategies/$STRATEGY.yaml"
if [ ! -f "$STRATEGY_FILE" ]; then
    echo "   FAIL: Strategy file not found: $STRATEGY_FILE"
    exit 1
fi
echo "   PASS: Strategy file exists"

# Show strategy content
echo ""
echo "5. Strategy content:"
echo "   ---"
cat "$STRATEGY_FILE" | sed 's/^/   /'
echo "   ---"

# Check token usage
echo ""
echo "6. Checking token usage..."
DESIGN_OP_ID=$(curl -s http://localhost:8000/api/v1/operations/$OP_ID | jq -r '.data.metadata.design_op_id')
DESIGN_OP=$(curl -s http://localhost:8000/api/v1/operations/$DESIGN_OP_ID)
INPUT_TOKENS=$(echo $DESIGN_OP | jq -r '.data.result_summary.input_tokens')
OUTPUT_TOKENS=$(echo $DESIGN_OP | jq -r '.data.result_summary.output_tokens')
echo "   Input tokens: $INPUT_TOKENS"
echo "   Output tokens: $OUTPUT_TOKENS"

if [ "$INPUT_TOKENS" == "null" ] || [ "$INPUT_TOKENS" == "0" ]; then
    echo "   WARNING: No input tokens recorded"
fi

echo ""
echo "=== M2 Complete ==="
```

---

## Files Created/Modified in M2

**New files**:
```
ktrdr/agents/workers/design_worker.py
tests/unit/agent_tests/test_design_worker.py
tests/integration/agent_tests/test_agent_design_real.py
```

**Modified files**:
```
ktrdr/agents/workers/research_worker.py  # Store strategy in metadata
ktrdr/api/services/agent_service.py      # Use real design worker
ktrdr/agents/executor.py                 # Add indicator/symbol tools
```

---

*Estimated effort: ~3-4 hours*
