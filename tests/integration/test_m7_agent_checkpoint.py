"""Integration tests for M7: Agent Checkpoint.

This test suite verifies the complete M7 agent checkpoint flow:
1. Start agent session
2. Save checkpoint on failure/cancellation
3. Simulate backend restart (startup reconciliation)
4. Verify operation marked FAILED with checkpoint message
5. Resume session
6. Verify continues from correct phase

Note: Uses mocked services for fast feedback. The key is testing
the same code paths that execute during real backend operations.
"""

from datetime import datetime, timezone

import pytest

from ktrdr.api.models.operations import (
    OperationInfo,
    OperationMetadata,
    OperationStatus,
)
from ktrdr.checkpoint.schemas import AgentCheckpointState
from tests.integration.fixtures.checkpoint_mocks import (
    IntegrationCheckpointService,
    MockOperationsRepository,
)

# ============================================================================
# Test Infrastructure: Agent-specific mock repository
# ============================================================================


class AgentOperationsRepository(MockOperationsRepository):
    """Extended operations repository with agent-specific features.

    Adds support for:
    - is_backend_local flag
    - OperationInfo model compatibility
    """

    async def create(
        self,
        operation_id: str,
        operation_type: str,
        status: str = "pending",
        is_backend_local: bool = False,
        metadata: dict | None = None,
    ) -> dict:
        """Create a new operation with backend-local flag."""
        self.operations[operation_id] = {
            "operation_id": operation_id,
            "operation_type": operation_type,
            "status": status,
            "is_backend_local": is_backend_local,
            "created_at": datetime.now(timezone.utc),
            "started_at": None,
            "completed_at": None,
            "progress_percent": 0,
            "error_message": None,
            "metadata": metadata or {},
        }
        return self.operations[operation_id]

    async def list(self, status: str | None = None) -> list[OperationInfo]:
        """List operations with optional status filter, returning OperationInfo."""
        result = []
        for op_data in self.operations.values():
            # Normalize status for comparison (enum values are lowercase)
            op_status = op_data["status"].lower()
            filter_status = status.lower() if status else None

            if filter_status is None or op_status == filter_status:
                # Convert to OperationInfo for StartupReconciliation compatibility
                result.append(
                    OperationInfo(
                        operation_id=op_data["operation_id"],
                        operation_type=op_data["operation_type"],
                        status=OperationStatus(op_status),
                        created_at=op_data["created_at"],
                        started_at=op_data.get("started_at"),
                        completed_at=op_data.get("completed_at"),
                        is_backend_local=op_data.get("is_backend_local", False),
                        metadata=OperationMetadata(
                            parameters=op_data.get("metadata", {})
                        ),
                        error_message=op_data.get("error_message"),
                    )
                )
        return result

    async def update(
        self,
        operation_id: str,
        status: str | None = None,
        error_message: str | None = None,
        reconciliation_status: str | None = None,
        **kwargs,
    ) -> None:
        """Update operation with reconciliation support."""
        op = self.operations.get(operation_id)
        if op:
            if status is not None:
                op["status"] = status
            if error_message is not None:
                op["error_message"] = error_message
            if reconciliation_status is not None:
                op["reconciliation_status"] = reconciliation_status
            if status and status.upper() in ("COMPLETED", "FAILED", "CANCELLED"):
                op["completed_at"] = datetime.now(timezone.utc)

    async def try_resume(self, operation_id: str) -> bool:
        """Atomically update status to RESUMING if resumable.

        Override parent to handle case-insensitive status comparison.
        """
        op = self.operations.get(operation_id)
        if op and op["status"].lower() in ("cancelled", "failed"):
            op["status"] = "resuming"
            op["started_at"] = datetime.now(timezone.utc)
            op["completed_at"] = None
            op["error_message"] = None
            return True
        return False


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def checkpoint_service():
    """Create IntegrationCheckpointService without artifacts (agent checkpoints are state-only)."""
    return IntegrationCheckpointService(artifacts_dir=None)


@pytest.fixture
def operations_repo():
    """Create AgentOperationsRepository."""
    return AgentOperationsRepository()


def create_agent_checkpoint_state(
    phase: str = "training",
    strategy_name: str | None = "test_strategy",
    strategy_path: str | None = "/strategies/test.yaml",
    training_operation_id: str | None = None,
    backtest_operation_id: str | None = None,
) -> dict:
    """Create agent checkpoint state dict."""
    state = AgentCheckpointState(
        phase=phase,
        strategy_name=strategy_name,
        strategy_path=strategy_path,
        training_operation_id=training_operation_id,
        backtest_operation_id=backtest_operation_id,
    )
    return state.to_dict()


# ============================================================================
# Test: Agent Checkpoint Save
# ============================================================================


class TestM7AgentCheckpointSave:
    """Tests for agent checkpoint saving."""

    @pytest.mark.asyncio
    async def test_checkpoint_saved_on_agent_failure(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test that when an agent operation fails:
        - Checkpoint is saved with type="failure"
        - State includes phase information
        """
        operation_id = "op_agent_failure_test"

        # Create a running agent operation
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
            metadata={"phase": "training", "strategy_name": "momentum_v1"},
        )

        # Save checkpoint (simulating what AgentService does on failure)
        state = create_agent_checkpoint_state(
            phase="training",
            strategy_name="momentum_v1",
            training_operation_id="op_training_123",
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
        )

        # Update operation status to failed
        await operations_repo.update_status(
            operation_id, "failed", error_message="Worker failed"
        )

        # Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Verify checkpoint content
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.checkpoint_type == "failure"
        assert checkpoint.state["phase"] == "training"
        assert checkpoint.state["strategy_name"] == "momentum_v1"

    @pytest.mark.asyncio
    async def test_checkpoint_saved_on_agent_cancellation(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """Test checkpoint saved with type='cancellation' on cancel."""
        operation_id = "op_agent_cancel_test"

        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
            metadata={"phase": "designing"},
        )

        # Save cancellation checkpoint
        state = create_agent_checkpoint_state(phase="designing")
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state,
        )

        await operations_repo.update_status(operation_id, "cancelled")

        # Verify
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.checkpoint_type == "cancellation"
        assert checkpoint.state["phase"] == "designing"

    @pytest.mark.asyncio
    async def test_checkpoint_state_deserializable(
        self,
        checkpoint_service: IntegrationCheckpointService,
    ):
        """Test checkpoint state can be deserialized to AgentCheckpointState."""
        operation_id = "op_deserialize_test"

        # Save checkpoint with full state
        state = create_agent_checkpoint_state(
            phase="backtesting",
            strategy_name="trend_follower",
            strategy_path="/strategies/trend.yaml",
            training_operation_id="op_training_456",
            backtest_operation_id="op_backtest_789",
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
        )

        # Load and deserialize
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None

        restored_state = AgentCheckpointState.from_dict(checkpoint.state)
        assert restored_state.phase == "backtesting"
        assert restored_state.strategy_name == "trend_follower"
        assert restored_state.training_operation_id == "op_training_456"
        assert restored_state.backtest_operation_id == "op_backtest_789"


# ============================================================================
# Test: Startup Reconciliation for Agent Operations
# ============================================================================


class TestM7StartupReconciliation:
    """Tests for startup reconciliation of agent operations."""

    @pytest.mark.asyncio
    async def test_backend_local_operation_marked_failed_with_checkpoint_message(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test that on startup reconciliation:
        - Backend-local RUNNING operations are marked FAILED
        - Error message indicates checkpoint availability
        """
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        operation_id = "op_reconcile_with_checkpoint"

        # Create a RUNNING backend-local operation (simulating pre-restart state)
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="RUNNING",
            is_backend_local=True,
            metadata={"phase": "training"},
        )

        # Save a checkpoint for this operation
        state = create_agent_checkpoint_state(phase="training")
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state=state,
        )

        # Run startup reconciliation
        reconciliation = StartupReconciliation(
            repository=operations_repo,
            checkpoint_service=checkpoint_service,
        )
        result = await reconciliation.reconcile()

        # Verify reconciliation counts
        assert result.total_processed == 1
        assert result.backend_ops_failed == 1
        assert result.worker_ops_reconciled == 0

        # Verify operation is now FAILED
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "FAILED"

        # Verify error message indicates checkpoint available
        assert op["error_message"] is not None
        assert "checkpoint available" in op["error_message"].lower()

    @pytest.mark.asyncio
    async def test_backend_local_operation_marked_failed_without_checkpoint(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test that operations without checkpoints get appropriate message.
        """
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        operation_id = "op_reconcile_no_checkpoint"

        # Create a RUNNING backend-local operation (no checkpoint saved)
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="RUNNING",
            is_backend_local=True,
        )

        # Run startup reconciliation (no checkpoint exists)
        reconciliation = StartupReconciliation(
            repository=operations_repo,
            checkpoint_service=checkpoint_service,
        )
        await reconciliation.reconcile()

        # Verify operation is FAILED with appropriate message
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "FAILED"
        assert "no checkpoint available" in op["error_message"].lower()

    @pytest.mark.asyncio
    async def test_worker_based_operation_not_marked_failed(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test that worker-based operations are handled differently.
        """
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        operation_id = "op_worker_based"

        # Create a RUNNING worker-based operation (not backend-local)
        await operations_repo.create(
            operation_id,
            "training",
            status="RUNNING",
            is_backend_local=False,
        )

        # Run startup reconciliation
        reconciliation = StartupReconciliation(
            repository=operations_repo,
            checkpoint_service=checkpoint_service,
        )
        result = await reconciliation.reconcile()

        # Verify it's marked for worker reconciliation, not failed
        assert result.worker_ops_reconciled == 1
        assert result.backend_ops_failed == 0

        op = operations_repo.get(operation_id)
        assert op is not None
        # Status should NOT be FAILED - it should remain RUNNING
        # with reconciliation_status set
        assert op.get("reconciliation_status") == "PENDING_RECONCILIATION"


# ============================================================================
# Test: Agent Resume
# ============================================================================


class TestM7AgentResume:
    """Tests for agent resume from checkpoint."""

    @pytest.mark.asyncio
    async def test_resume_loads_checkpoint_state(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test that resume operation loads checkpoint and can restore state.
        """
        operation_id = "op_agent_resume_test"

        # Create a FAILED operation
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="failed",
            is_backend_local=True,
            metadata={"phase": "training"},
        )

        # Save checkpoint
        state = create_agent_checkpoint_state(
            phase="training",
            strategy_name="rsi_crossover",
            strategy_path="/strategies/rsi.yaml",
            training_operation_id="op_training_child",
        )
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
        )

        # Load checkpoint (simulating AgentService.resume() first step)
        checkpoint = await checkpoint_service.load_checkpoint(
            operation_id, load_artifacts=False
        )

        # Verify checkpoint loaded
        assert checkpoint is not None
        assert checkpoint.state["phase"] == "training"
        assert checkpoint.state["strategy_name"] == "rsi_crossover"

        # Deserialize to AgentCheckpointState
        restored_state = AgentCheckpointState.from_dict(checkpoint.state)
        assert restored_state.training_operation_id == "op_training_child"

    @pytest.mark.asyncio
    async def test_resume_fails_without_checkpoint(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """Test resume handles missing checkpoint gracefully."""
        operation_id = "op_no_checkpoint"

        # Create a FAILED operation without checkpoint
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="failed",
            is_backend_local=True,
        )

        # Try to load checkpoint
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        # Should be None - no checkpoint to resume from
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_resume_operation_status_transition(
        self,
        operations_repo: AgentOperationsRepository,
    ):
        """Test that resume transitions operation from FAILED/CANCELLED to resuming."""
        operation_id = "op_status_transition"

        # Test FAILED → resuming
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="failed",
            is_backend_local=True,
        )

        success = await operations_repo.try_resume(operation_id)
        assert success is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "resuming"

    @pytest.mark.asyncio
    async def test_resume_cancelled_operation(
        self,
        operations_repo: AgentOperationsRepository,
    ):
        """Test that CANCELLED operations can be resumed."""
        operation_id = "op_cancelled_resume"

        await operations_repo.create(
            operation_id,
            "agent_research",
            status="cancelled",
            is_backend_local=True,
        )

        success = await operations_repo.try_resume(operation_id)
        assert success is True

    @pytest.mark.asyncio
    async def test_cannot_resume_running_operation(
        self,
        operations_repo: AgentOperationsRepository,
    ):
        """Test that RUNNING operations cannot be resumed."""
        operation_id = "op_running"

        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
        )

        success = await operations_repo.try_resume(operation_id)
        assert success is False

    @pytest.mark.asyncio
    async def test_cannot_resume_completed_operation(
        self,
        operations_repo: AgentOperationsRepository,
    ):
        """Test that COMPLETED operations cannot be resumed."""
        operation_id = "op_completed"

        await operations_repo.create(
            operation_id,
            "agent_research",
            status="completed",
            is_backend_local=True,
        )

        success = await operations_repo.try_resume(operation_id)
        assert success is False


# ============================================================================
# Test: Full Agent Checkpoint Flow
# ============================================================================


class TestM7FullAgentCheckpointFlow:
    """Integration tests for the complete agent checkpoint flow."""

    @pytest.mark.asyncio
    async def test_full_flow_start_fail_reconcile_resume(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """
        Test the complete M7 agent checkpoint flow:
        1. Start agent session
        2. Progress to training phase
        3. Save checkpoint on failure
        4. Simulate backend restart (reconciliation)
        5. Verify operation marked FAILED with checkpoint message
        6. Resume session
        7. Verify continues from correct phase
        """
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        operation_id = "op_full_agent_flow"

        # Step 1: Start agent session
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
            metadata={
                "phase": "training",
                "strategy_name": "full_flow_strategy",
                "strategy_path": "/strategies/flow.yaml",
            },
        )

        # Step 2: Agent progresses to training phase
        # (Already at training in this test)

        # Step 3: Failure occurs - save checkpoint
        checkpoint_state = create_agent_checkpoint_state(
            phase="training",
            strategy_name="full_flow_strategy",
            strategy_path="/strategies/flow.yaml",
            training_operation_id="op_training_flow_child",
        )
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=checkpoint_state,
        )

        # Operation is still RUNNING (backend crash before status update)
        # This simulates the crash scenario

        # Step 4: Backend restart - run reconciliation
        reconciliation = StartupReconciliation(
            repository=operations_repo,
            checkpoint_service=checkpoint_service,
        )
        result = await reconciliation.reconcile()

        # Verify reconciliation handled the operation
        assert result.backend_ops_failed == 1

        # Step 5: Verify operation marked FAILED with checkpoint message
        op = operations_repo.get(operation_id)
        assert op is not None
        assert op["status"] == "FAILED"
        assert "checkpoint available" in op["error_message"].lower()

        # Step 6: Resume session
        # First, load checkpoint
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None

        # Try to resume
        success = await operations_repo.try_resume(operation_id)
        assert success is True

        # Verify status changed to resuming
        resumed_op = operations_repo.get(operation_id)
        assert resumed_op["status"] == "resuming"

        # Step 7: Verify checkpoint has correct phase to continue from
        restored_state = AgentCheckpointState.from_dict(checkpoint.state)
        assert restored_state.phase == "training"
        assert restored_state.strategy_name == "full_flow_strategy"
        assert restored_state.training_operation_id == "op_training_flow_child"

    @pytest.mark.asyncio
    async def test_full_flow_with_cancellation(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """Test full flow with user cancellation instead of failure."""

        operation_id = "op_cancelled_flow"

        # Start and cancel during designing phase
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
            metadata={"phase": "designing"},
        )

        # Save cancellation checkpoint
        checkpoint_state = create_agent_checkpoint_state(phase="designing")
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=checkpoint_state,
        )

        # Mark as cancelled (user-initiated, not crash)
        await operations_repo.update_status(operation_id, "cancelled")

        # No reconciliation needed for user cancellation
        # Go directly to resume

        # Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Resume
        success = await operations_repo.try_resume(operation_id)
        assert success is True

        # Verify can load checkpoint for resume
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.checkpoint_type == "cancellation"
        assert checkpoint.state["phase"] == "designing"

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_on_successful_completion(
        self,
        checkpoint_service: IntegrationCheckpointService,
        operations_repo: AgentOperationsRepository,
    ):
        """Test that checkpoint is deleted when operation completes successfully."""
        operation_id = "op_success_cleanup"

        # Create operation and checkpoint
        await operations_repo.create(
            operation_id,
            "agent_research",
            status="running",
            is_backend_local=True,
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state=create_agent_checkpoint_state(phase="assessing"),
        )

        # Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Operation completes successfully - delete checkpoint
        deleted = await checkpoint_service.delete_checkpoint(operation_id)
        assert deleted is True

        # Complete the operation
        await operations_repo.update_status(operation_id, "completed")

        # Verify checkpoint is gone
        assert not checkpoint_service.checkpoint_exists(operation_id)

        # Verify operation is completed
        op = operations_repo.get(operation_id)
        assert op["status"] == "completed"


# ============================================================================
# Test: Phase-Specific Resume Scenarios
# ============================================================================


class TestM7PhaseSpecificResume:
    """Tests for resuming from different agent phases."""

    @pytest.mark.asyncio
    async def test_resume_from_designing_phase(
        self,
        checkpoint_service: IntegrationCheckpointService,
    ):
        """Test resume from designing phase."""
        operation_id = "op_resume_designing"

        state = create_agent_checkpoint_state(phase="designing")
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        restored = AgentCheckpointState.from_dict(checkpoint.state)

        assert restored.phase == "designing"
        # No strategy yet in designing phase
        assert restored.training_operation_id is None

    @pytest.mark.asyncio
    async def test_resume_from_training_phase_includes_child_op(
        self,
        checkpoint_service: IntegrationCheckpointService,
    ):
        """Test resume from training phase includes child training operation."""
        operation_id = "op_resume_training"

        state = create_agent_checkpoint_state(
            phase="training",
            strategy_name="test_strategy",
            training_operation_id="op_training_child_123",
        )
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        restored = AgentCheckpointState.from_dict(checkpoint.state)

        assert restored.phase == "training"
        assert restored.training_operation_id == "op_training_child_123"

    @pytest.mark.asyncio
    async def test_resume_from_backtesting_phase_includes_both_child_ops(
        self,
        checkpoint_service: IntegrationCheckpointService,
    ):
        """Test resume from backtesting phase includes training and backtest ops."""
        operation_id = "op_resume_backtesting"

        state = create_agent_checkpoint_state(
            phase="backtesting",
            strategy_name="backtest_strategy",
            training_operation_id="op_training_done",
            backtest_operation_id="op_backtest_current",
        )
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        restored = AgentCheckpointState.from_dict(checkpoint.state)

        assert restored.phase == "backtesting"
        assert restored.training_operation_id == "op_training_done"
        assert restored.backtest_operation_id == "op_backtest_current"

    @pytest.mark.asyncio
    async def test_resume_from_assessing_phase(
        self,
        checkpoint_service: IntegrationCheckpointService,
    ):
        """Test resume from assessing phase."""
        operation_id = "op_resume_assessing"

        state = create_agent_checkpoint_state(
            phase="assessing",
            strategy_name="assessed_strategy",
            training_operation_id="op_training_complete",
            backtest_operation_id="op_backtest_complete",
        )
        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        restored = AgentCheckpointState.from_dict(checkpoint.state)

        assert restored.phase == "assessing"
        # Both child ops should be present
        assert restored.training_operation_id == "op_training_complete"
        assert restored.backtest_operation_id == "op_backtest_complete"
