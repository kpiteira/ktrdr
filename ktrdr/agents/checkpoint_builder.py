"""Agent checkpoint builder functions.

Provides functions to extract checkpoint state from agent operations
for checkpoint/resume functionality.
"""

from typing import Any, Protocol

from ktrdr.checkpoint.schemas import AgentCheckpointState


class OperationLike(Protocol):
    """Protocol for operation-like objects with metadata."""

    operation_id: str
    metadata: Any


class CheckpointServiceLike(Protocol):
    """Protocol for checkpoint service with load_checkpoint method."""

    async def load_checkpoint(
        self, operation_id: str, load_artifacts: bool = False
    ) -> Any: ...


def build_agent_checkpoint_state(operation: OperationLike) -> AgentCheckpointState:
    """Extract checkpoint state from an agent operation.

    Extracts the current phase, strategy info, and child operation IDs
    from the operation's metadata.parameters to build a checkpoint state
    that can be used to resume the agent from this point.

    Args:
        operation: The agent operation (AGENT_RESEARCH) with metadata.

    Returns:
        AgentCheckpointState populated from the operation's metadata.
    """
    params = operation.metadata.parameters

    # Extract current phase
    phase = params.get("phase", "idle")

    # Extract strategy info (populated after design phase)
    strategy_name = params.get("strategy_name")
    strategy_path = params.get("strategy_path")

    # Extract child operation IDs
    training_operation_id = params.get("training_op_id")
    backtest_operation_id = params.get("backtest_op_id")

    # Extract token counts if tracked
    token_counts = params.get("token_counts", {})

    # Build original request from trigger info
    original_request: dict[str, Any] = {}
    if trigger_reason := params.get("trigger_reason"):
        original_request["trigger_reason"] = trigger_reason
    if model := params.get("model"):
        original_request["model"] = model

    return AgentCheckpointState(
        phase=phase,
        strategy_name=strategy_name,
        strategy_path=strategy_path,
        training_operation_id=training_operation_id,
        backtest_operation_id=backtest_operation_id,
        token_counts=token_counts,
        original_request=original_request,
    )


async def build_agent_checkpoint_state_with_training(
    operation: OperationLike,
    checkpoint_service: CheckpointServiceLike,
) -> AgentCheckpointState:
    """Extract checkpoint state including training checkpoint epoch.

    This async version looks up the training operation's checkpoint
    to get the current epoch if the agent is in the training phase.

    Args:
        operation: The agent operation (AGENT_RESEARCH) with metadata.
        checkpoint_service: Service to load training checkpoints.

    Returns:
        AgentCheckpointState with training_checkpoint_epoch if available.
    """
    # Start with basic state
    state = build_agent_checkpoint_state(operation)

    # If in training phase and have a training operation, look up its checkpoint
    if state.phase == "training" and state.training_operation_id:
        checkpoint = await checkpoint_service.load_checkpoint(
            state.training_operation_id, load_artifacts=False
        )
        if checkpoint and hasattr(checkpoint, "state") and checkpoint.state:
            epoch = checkpoint.state.get("epoch")
            # Create new state with the epoch
            return AgentCheckpointState(
                phase=state.phase,
                strategy_name=state.strategy_name,
                strategy_path=state.strategy_path,
                training_operation_id=state.training_operation_id,
                training_checkpoint_epoch=epoch,
                backtest_operation_id=state.backtest_operation_id,
                token_counts=state.token_counts,
                original_request=state.original_request,
            )

    return state
