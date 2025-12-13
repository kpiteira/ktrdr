# Phase 1: Foundation (Design-Only Cycle)

**Goal**: `ktrdr agent trigger` → Claude designs strategy → saves to disk → operation completes

**Prerequisite**: Start from clean `main` branch

---

## Task 1.1: Add AGENT_RESEARCH operation type

**File**: `ktrdr/api/models/operations.py`

**Change**: Add new enum value (line ~33):

```python
class OperationType(str, Enum):
    """Type of operation."""

    DATA_LOAD = "data_load"
    TRAINING = "training"
    BACKTESTING = "backtesting"
    INDICATOR_COMPUTE = "indicator_compute"
    FUZZY_ANALYSIS = "fuzzy_analysis"
    AGENT_RESEARCH = "agent_research"  # NEW: Full research cycle
    DUMMY = "dummy"
```

**Note**: Remove `AGENT_DESIGN` and `AGENT_SESSION` if present (those were from the old approach).

**Test**:
```python
# tests/unit/api/test_operations_models.py
def test_agent_research_operation_type():
    assert OperationType.AGENT_RESEARCH.value == "agent_research"
```

---

## Task 1.2: Create AgentService (minimal)

**File**: `ktrdr/api/services/agent_service.py` (new file)

```python
"""
Agent research service - orchestrates research cycles.

Uses OperationsService as the single source of truth for state.
No separate session database.
"""

import asyncio
from typing import Any, Optional

from ktrdr import get_logger
from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationType,
    OperationStatus,
)
from ktrdr.api.services.operations_service import (
    OperationsService,
    get_operations_service,
)

logger = get_logger(__name__)


class AgentService:
    """Orchestrates agent research cycles using OperationsService."""

    def __init__(
        self,
        operations_service: Optional[OperationsService] = None,
    ):
        """Initialize the agent service.

        Args:
            operations_service: OperationsService instance (uses singleton if None)
        """
        self._ops = operations_service or get_operations_service()

    async def trigger(self) -> dict[str, Any]:
        """Start a new research cycle.

        Returns:
            Dict with:
            - triggered: bool - whether cycle was started
            - operation_id: str - if started
            - reason: str - if not started
        """
        # Check for existing active cycle
        active = await self._get_active_research_operation()
        if active:
            return {
                "triggered": False,
                "reason": "active_operation_exists",
                "operation_id": active.operation_id,
                "phase": active.metadata.parameters.get("phase", "unknown"),
            }

        # Create operation for the cycle
        operation = await self._ops.create_operation(
            operation_type=OperationType.AGENT_RESEARCH,
            metadata=OperationMetadata(
                parameters={
                    "phase": "designing",
                }
            ),
        )

        # Start the cycle task
        task = asyncio.create_task(
            self._run_research_cycle(operation.operation_id),
            name=f"agent_research_{operation.operation_id}",
        )
        await self._ops.start_operation(operation.operation_id, task)

        logger.info(f"Started research cycle: {operation.operation_id}")

        return {
            "triggered": True,
            "operation_id": operation.operation_id,
        }

    async def get_status(self) -> dict[str, Any]:
        """Get current research cycle status.

        Returns:
            Dict with status info or idle indicator
        """
        active = await self._get_active_research_operation()
        if not active:
            return {"status": "idle", "operation": None}

        return {
            "status": "active",
            "operation": {
                "id": active.operation_id,
                "phase": active.metadata.parameters.get("phase", "unknown"),
                "progress": {
                    "percentage": active.progress.percentage if active.progress else 0,
                    "current_step": active.progress.current_step if active.progress else None,
                },
                "strategy_name": active.metadata.parameters.get("strategy_name"),
                "created_at": active.created_at.isoformat() if active.created_at else None,
            },
        }

    async def _get_active_research_operation(self):
        """Find any active AGENT_RESEARCH operation."""
        operations = await self._ops.list_operations(
            operation_type=OperationType.AGENT_RESEARCH,
            status=OperationStatus.RUNNING,
        )
        return operations[0] if operations else None

    async def _run_research_cycle(self, operation_id: str) -> None:
        """Execute a research cycle (Phase 1: design only)."""
        try:
            # Phase 1: Design
            await self._update_phase(operation_id, "designing")
            design_result = await self._run_design_phase(operation_id)

            if not design_result.get("success"):
                await self._ops.fail_operation(
                    operation_id,
                    error_message=design_result.get("error", "Design failed"),
                )
                return

            # Update with strategy info
            await self._update_metadata(operation_id, {
                "strategy_name": design_result.get("strategy_name"),
                "strategy_path": design_result.get("strategy_path"),
            })

            # Phase 1 complete - mark done
            # (Phases 2-4 will add training, backtest, assessment here)
            await self._ops.complete_operation(
                operation_id,
                result_summary={
                    "phase": "designed",
                    "strategy_name": design_result.get("strategy_name"),
                },
            )

            logger.info(f"Research cycle {operation_id} completed (design only)")

        except asyncio.CancelledError:
            logger.info(f"Research cycle {operation_id} cancelled")
            raise
        except Exception as e:
            logger.error(f"Research cycle {operation_id} failed: {e}")
            await self._ops.fail_operation(operation_id, error_message=str(e))

    async def _run_design_phase(self, operation_id: str) -> dict[str, Any]:
        """Run Claude to design a strategy.

        Returns:
            Dict with success, strategy_name, strategy_path, or error
        """
        from ktrdr.agents.executor import ToolExecutor, create_tool_executor
        from ktrdr.agents.invoker import AnthropicAgentInvoker
        from ktrdr.agents.tools import AGENT_TOOLS

        # Update progress
        await self._ops.update_progress(
            operation_id,
            percentage=10,
            current_step="Invoking Claude to design strategy",
        )

        # Create invoker and executor
        invoker = AnthropicAgentInvoker()
        executor = create_tool_executor()

        # Build prompt
        prompt = self._build_design_prompt()

        # System prompt for the agent
        system_prompt = self._get_system_prompt()

        # Run the agent
        result = await invoker.run(
            prompt=prompt,
            tools=AGENT_TOOLS,
            system_prompt=system_prompt,
            tool_executor=executor,
        )

        if not result.success:
            return {"success": False, "error": result.error}

        # Extract strategy info from tool_outputs
        # tool_outputs is populated by save_strategy_config tool
        if result.tool_outputs:
            return {
                "success": True,
                "strategy_name": result.tool_outputs.get("strategy_name"),
                "strategy_path": result.tool_outputs.get("strategy_path"),
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
            }

        # No strategy was saved - this is a failure
        return {
            "success": False,
            "error": "Agent completed but did not save a strategy",
        }

    def _build_design_prompt(self) -> str:
        """Build the prompt for strategy design."""
        return """Design a new trading strategy.

Your task:
1. Use get_recent_strategies() to see what's been tried before (avoid repetition)
2. Use get_available_indicators() to see what indicators are available
3. Use get_available_symbols() to see what data is available
4. Design a novel strategy approach
5. Use validate_strategy_config() to check your config
6. Use save_strategy_config() to save it

Be creative but practical. Focus on a single clear hypothesis.
"""

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the agent."""
        return """You are a trading strategy designer for the KTRDR neuro-fuzzy system.

You design strategies that use:
- Technical indicators (RSI, MACD, Bollinger Bands, etc.)
- Fuzzy logic membership functions
- Neural networks for decision making

Your goal is to create novel, testable strategies. Each strategy should:
- Have a clear hypothesis about market behavior
- Use 2-4 complementary indicators (avoid redundant indicators)
- Define appropriate fuzzy sets for each indicator
- Configure a reasonable neural network architecture

Always validate your strategy config before saving it.
Always save your strategy when done designing.
"""

    async def _update_phase(self, operation_id: str, phase: str) -> None:
        """Update the phase in operation metadata."""
        op = await self._ops.get_operation(operation_id)
        if op:
            params = dict(op.metadata.parameters)
            params["phase"] = phase
            op.metadata.parameters = params

    async def _update_metadata(self, operation_id: str, updates: dict) -> None:
        """Update operation metadata with new values."""
        op = await self._ops.get_operation(operation_id)
        if op:
            params = dict(op.metadata.parameters)
            params.update(updates)
            op.metadata.parameters = params
```

**Test file**: `tests/unit/api/services/test_agent_service.py`

```python
"""Tests for AgentService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ktrdr.api.models.operations import OperationType, OperationStatus
from ktrdr.api.services.agent_service import AgentService


class TestAgentServiceTrigger:
    """Tests for AgentService.trigger()"""

    @pytest.fixture
    def mock_ops_service(self):
        """Create mock OperationsService."""
        ops = MagicMock()
        ops.list_operations = AsyncMock(return_value=[])
        ops.create_operation = AsyncMock()
        ops.start_operation = AsyncMock()
        return ops

    @pytest.mark.asyncio
    async def test_trigger_creates_operation(self, mock_ops_service):
        """Trigger should create AGENT_RESEARCH operation."""
        mock_op = MagicMock()
        mock_op.operation_id = "op_agent_research_123"
        mock_ops_service.create_operation.return_value = mock_op

        service = AgentService(operations_service=mock_ops_service)

        with patch.object(service, '_run_research_cycle', new_callable=AsyncMock):
            result = await service.trigger()

        assert result["triggered"] is True
        assert result["operation_id"] == "op_agent_research_123"

        # Verify operation was created with correct type
        mock_ops_service.create_operation.assert_called_once()
        call_kwargs = mock_ops_service.create_operation.call_args[1]
        assert call_kwargs["operation_type"] == OperationType.AGENT_RESEARCH

    @pytest.mark.asyncio
    async def test_trigger_rejects_when_active(self, mock_ops_service):
        """Trigger should reject when cycle already running."""
        existing_op = MagicMock()
        existing_op.operation_id = "op_agent_research_existing"
        existing_op.metadata.parameters = {"phase": "designing"}
        mock_ops_service.list_operations.return_value = [existing_op]

        service = AgentService(operations_service=mock_ops_service)
        result = await service.trigger()

        assert result["triggered"] is False
        assert result["reason"] == "active_operation_exists"
        assert result["operation_id"] == "op_agent_research_existing"


class TestAgentServiceStatus:
    """Tests for AgentService.get_status()"""

    @pytest.mark.asyncio
    async def test_status_idle_when_no_active(self):
        """Status should return idle when no active cycle."""
        ops = MagicMock()
        ops.list_operations = AsyncMock(return_value=[])

        service = AgentService(operations_service=ops)
        result = await service.get_status()

        assert result["status"] == "idle"
        assert result["operation"] is None

    @pytest.mark.asyncio
    async def test_status_active_with_details(self):
        """Status should return details when cycle active."""
        from datetime import datetime, timezone

        active_op = MagicMock()
        active_op.operation_id = "op_agent_research_123"
        active_op.metadata.parameters = {
            "phase": "designing",
            "strategy_name": "test_strategy",
        }
        active_op.progress = MagicMock(percentage=50, current_step="Designing...")
        active_op.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        ops = MagicMock()
        ops.list_operations = AsyncMock(return_value=[active_op])

        service = AgentService(operations_service=ops)
        result = await service.get_status()

        assert result["status"] == "active"
        assert result["operation"]["id"] == "op_agent_research_123"
        assert result["operation"]["phase"] == "designing"
        assert result["operation"]["progress"]["percentage"] == 50
```

---

## Task 1.3: Capture strategy_name from tool results

**Problem**: The `AnthropicAgentInvoker` doesn't capture tool outputs. When `save_strategy_config` is called, we need to capture the strategy_name and path.

**File**: `ktrdr/agents/invoker.py`

**Change**: Modify `_execute_tools` to capture important results:

```python
async def _execute_tools(
    self,
    tool_calls: list[Any],
    tool_executor: ToolExecutor | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Execute tool calls and return results.

    Returns:
        Tuple of (tool_result_blocks, captured_outputs)
    """
    results = []
    captured_outputs = {}  # NEW: Capture important outputs

    for tool_call in tool_calls:
        tool_name = tool_call.name
        tool_input = tool_call.input
        tool_use_id = tool_call.id

        # ... existing execution code ...

        result_content = await tool_executor(tool_name, tool_input)

        # NEW: Capture strategy info from save_strategy_config
        if tool_name == "save_strategy_config" and isinstance(result_content, dict):
            if result_content.get("success"):
                captured_outputs["strategy_name"] = result_content.get("name")
                captured_outputs["strategy_path"] = result_content.get("path")

        results.append({
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": str(result_content),
        })

    return results, captured_outputs
```

**Also update** `run()` method to collect and return captured outputs:

```python
async def run(self, ...) -> AgentResult:
    # ... existing code ...
    all_captured_outputs = {}  # Collect across all iterations

    while True:
        # ... API call ...

        if not tool_calls:
            # Return with captured outputs
            return AgentResult(
                success=True,
                output=output_text,
                input_tokens=total_input_tokens,
                output_tokens=total_output_tokens,
                error=None,
                tool_outputs=all_captured_outputs if all_captured_outputs else None,
            )

        # Execute tools and capture outputs
        tool_results, captured = await self._execute_tools(tool_calls, tool_executor)
        all_captured_outputs.update(captured)

        # ... continue loop ...
```

**Test**:
```python
@pytest.mark.asyncio
async def test_invoker_captures_strategy_from_save_tool():
    """Invoker should capture strategy_name when save_strategy_config succeeds."""
    # Setup mock that returns save result
    mock_executor = AsyncMock(return_value={
        "success": True,
        "name": "test_strategy_v1",
        "path": "/app/strategies/test_strategy_v1.yaml",
    })

    # ... run invoker with mock ...

    assert result.tool_outputs is not None
    assert result.tool_outputs["strategy_name"] == "test_strategy_v1"
```

---

## Task 1.4: Wire up API endpoints

**File**: `ktrdr/api/endpoints/agent.py`

Replace existing content with simplified version:

```python
"""
Agent research API endpoints.

Provides endpoints for triggering and monitoring research cycles.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Any, Optional

from ktrdr import get_logger
from ktrdr.api.services.agent_service import AgentService
from ktrdr.api.services.operations_service import get_operations_service

logger = get_logger(__name__)
router = APIRouter(prefix="/agent", tags=["agent"])

# Singleton service instance
_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get agent service instance."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService(
            operations_service=get_operations_service()
        )
    return _agent_service


# --- Response Models ---

class TriggerResponse(BaseModel):
    """Response for POST /agent/trigger."""
    triggered: bool
    operation_id: Optional[str] = None
    reason: Optional[str] = None
    phase: Optional[str] = None


class StatusResponse(BaseModel):
    """Response for GET /agent/status."""
    status: str  # "idle" or "active"
    operation: Optional[dict[str, Any]] = None


# --- Endpoints ---

@router.post("/trigger", response_model=TriggerResponse)
async def trigger_agent(
    service: AgentService = Depends(get_agent_service),
) -> TriggerResponse:
    """
    Start a new research cycle.

    Creates an AGENT_RESEARCH operation and starts the design phase.
    Returns immediately - use GET /agent/status or
    GET /operations/{id} to track progress.
    """
    result = await service.trigger()
    return TriggerResponse(**result)


@router.get("/status", response_model=StatusResponse)
async def get_status(
    service: AgentService = Depends(get_agent_service),
) -> StatusResponse:
    """
    Get current research cycle status.

    Returns "idle" if no cycle is running, or details of the active cycle.
    """
    result = await service.get_status()
    return StatusResponse(**result)
```

**Move models to**: `ktrdr/api/models/agent.py` (simplified)

```python
"""Agent API response models."""

from typing import Any, Optional
from pydantic import BaseModel


class TriggerResponse(BaseModel):
    """Response for POST /agent/trigger."""
    triggered: bool
    operation_id: Optional[str] = None
    reason: Optional[str] = None
    phase: Optional[str] = None


class StatusResponse(BaseModel):
    """Response for GET /agent/status."""
    status: str  # "idle" or "active"
    operation: Optional[dict[str, Any]] = None
```

---

## Task 1.5: Wire up CLI commands

**File**: `ktrdr/cli/agent_commands.py`

```python
"""
Agent CLI commands.

Provides CLI interface for triggering and monitoring research cycles.
"""

import asyncio
import sys

import typer
from rich.console import Console
from rich.table import Table

from ktrdr.cli.async_cli_client import AsyncCLIClient, AsyncCLIClientError
from ktrdr.logging import get_logger

logger = get_logger(__name__)
console = Console()
error_console = Console(stderr=True)

agent_app = typer.Typer(
    name="agent",
    help="Research agent commands",
    no_args_is_help=True,
)


@agent_app.command("trigger")
def trigger_agent(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start a new research cycle."""
    try:
        asyncio.run(_trigger_async(verbose))
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _trigger_async(verbose: bool):
    """Async trigger implementation."""
    async with AsyncCLIClient() as client:
        result = await client._make_request("POST", "/agent/trigger")

    if result.get("triggered"):
        console.print(f"[green]Research cycle started![/green]")
        console.print(f"  Operation ID: {result['operation_id']}")
        console.print()
        console.print("Track progress with: [cyan]ktrdr agent status[/cyan]")
    else:
        reason = result.get("reason", "unknown")
        if reason == "active_operation_exists":
            console.print(f"[yellow]Cycle already running[/yellow]")
            console.print(f"  Operation ID: {result.get('operation_id')}")
            console.print(f"  Phase: {result.get('phase')}")
        else:
            console.print(f"[yellow]Not triggered:[/yellow] {reason}")


@agent_app.command("status")
def show_status(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Show current research cycle status."""
    try:
        asyncio.run(_status_async(verbose))
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _status_async(verbose: bool):
    """Async status implementation."""
    async with AsyncCLIClient() as client:
        result = await client._make_request("GET", "/agent/status")

    if result.get("status") == "idle":
        console.print("[dim]No active research cycle[/dim]")
        console.print()
        console.print("Start one with: [cyan]ktrdr agent trigger[/cyan]")
        return

    op = result.get("operation", {})

    console.print("[green]Research cycle active[/green]")
    console.print()

    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Operation ID", op.get("id", "unknown"))
    table.add_row("Phase", op.get("phase", "unknown").upper())

    progress = op.get("progress", {})
    if progress.get("percentage"):
        table.add_row("Progress", f"{progress['percentage']:.0f}%")
    if progress.get("current_step"):
        table.add_row("Current Step", progress["current_step"])
    if op.get("strategy_name"):
        table.add_row("Strategy", op["strategy_name"])

    console.print(table)


@agent_app.command("cancel")
def cancel_cycle(
    operation_id: str = typer.Argument(help="Operation ID to cancel"),
):
    """Cancel a research cycle."""
    try:
        asyncio.run(_cancel_async(operation_id))
    except Exception as e:
        error_console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


async def _cancel_async(operation_id: str):
    """Async cancel implementation."""
    async with AsyncCLIClient() as client:
        result = await client._make_request(
            "DELETE",
            f"/operations/{operation_id}/cancel",
        )

    if result.get("success"):
        console.print(f"[green]Cancelled:[/green] {operation_id}")
    else:
        console.print(f"[red]Failed:[/red] {result.get('error', 'Unknown error')}")
```

---

## Phase 1 Verification

### Manual Test Sequence

```bash
# 1. Start the system
docker compose up -d

# 2. Trigger a research cycle
ktrdr agent trigger
# Expected: "Research cycle started!" with operation ID

# 3. Check status
ktrdr agent status
# Expected: Shows phase "DESIGNING" with progress

# 4. Wait for completion or check operations
ktrdr operations list --type agent_research
# Expected: Shows operation with status

# 5. Check strategy was saved
ls strategies/
# Expected: New strategy YAML file

# 6. Test cancellation (start new cycle first)
ktrdr agent trigger
ktrdr agent status  # Get operation ID
ktrdr agent cancel <operation_id>
# Expected: "Cancelled" message
```

### Acceptance Criteria

- [ ] `ktrdr agent trigger` creates AGENT_RESEARCH operation
- [ ] Claude is invoked and designs a strategy
- [ ] Strategy is saved to `strategies/` folder
- [ ] `ktrdr agent status` shows progress correctly
- [ ] `ktrdr agent cancel` works
- [ ] Operation appears in `ktrdr operations list`
- [ ] No session database code (all state in OperationsService)

---

## Files Created/Modified Summary

| File | Action |
|------|--------|
| `ktrdr/api/models/operations.py` | Modify - add AGENT_RESEARCH |
| `ktrdr/api/services/agent_service.py` | Create new |
| `ktrdr/agents/invoker.py` | Modify - capture tool outputs |
| `ktrdr/api/endpoints/agent.py` | Rewrite simplified |
| `ktrdr/api/models/agent.py` | Rewrite simplified |
| `ktrdr/cli/agent_commands.py` | Rewrite simplified |
| `tests/unit/api/services/test_agent_service.py` | Create new |
