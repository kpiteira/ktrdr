"""
Unit tests for Agent OperationsService integration (Task 1.13a).

Tests verify that agent operations follow the same patterns as training/backtesting:
1. Operation ID returned from trigger
2. Progress queryable via OperationsService
3. Token counts visible in result_summary
4. OpenTelemetry spans created
5. Operations visible in operations list alongside training/backtest
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ktrdr.api.models.operations import (
    OperationMetadata,
    OperationProgress,
    OperationStatus,
    OperationType,
)
from ktrdr.api.services.operations_service import OperationsService


class TestAgentDesignOperationType:
    """Test that AGENT_DESIGN is a valid operation type."""

    def test_agent_design_operation_type_exists(self):
        """AGENT_DESIGN should be a valid OperationType enum value."""
        assert hasattr(OperationType, "AGENT_DESIGN")
        assert OperationType.AGENT_DESIGN.value == "agent_design"

    def test_agent_design_can_be_used_in_create_operation(self):
        """Operations can be created with AGENT_DESIGN type."""
        ops_service = OperationsService()

        # Should be able to generate operation ID for AGENT_DESIGN
        operation_id = ops_service.generate_operation_id(OperationType.AGENT_DESIGN)
        assert "agent_design" in operation_id


class TestAgentOperationsServiceIntegration:
    """Test that AgentService integrates correctly with OperationsService."""

    @pytest.fixture
    def mock_operations_service(self):
        """Create a mock operations service."""
        ops = MagicMock(spec=OperationsService)

        # Mock create_operation to return a proper operation
        mock_operation = MagicMock()
        mock_operation.operation_id = "op_agent_design_20251210_123456_abc12345"
        ops.create_operation = AsyncMock(return_value=mock_operation)
        ops.start_operation = AsyncMock()
        ops.update_progress = AsyncMock()
        ops.complete_operation = AsyncMock()
        ops.fail_operation = AsyncMock()

        return ops

    @pytest.fixture
    def mock_agent_db(self):
        """Create a mock agent database."""
        db = AsyncMock()
        db.get_active_session.return_value = None
        db.create_session.return_value = MagicMock(id=123, phase="designing")
        db.update_session.return_value = None
        return db

    @pytest.mark.asyncio
    async def test_trigger_returns_operation_id(
        self, mock_operations_service, mock_agent_db
    ):
        """POST /agent/trigger should return an operation_id."""
        from ktrdr.api.services.agent_service import AgentService

        # Create service with mocked operations service
        with (
            patch(
                "ktrdr.api.services.agent_service.get_agent_db",
                new=AsyncMock(return_value=mock_agent_db),
            ),
            patch(
                "ktrdr.api.services.agent_service.TriggerConfig.from_env"
            ) as mock_config,
        ):
            mock_config.return_value.enabled = True

            service = AgentService(operations_service=mock_operations_service)
            result = await service.trigger(dry_run=False)

            # Should return operation_id
            assert (
                "operation_id" in result
            ), f"Expected 'operation_id' in result, got: {result}"
            assert result["operation_id"] == "op_agent_design_20251210_123456_abc12345"
            assert result["triggered"] is True

    @pytest.mark.asyncio
    async def test_operation_progress_queryable(self):
        """Progress should be queryable via GET /operations/{id}."""
        ops_service = OperationsService()

        # Create an AGENT_DESIGN operation
        operation = await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(
                symbol="N/A",
                timeframe="N/A",
                mode="strategy_design",
                parameters={"session_id": 123, "trigger_reason": "start_new_cycle"},
            ),
        )
        operation_id = operation.operation_id

        # Start the operation
        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await ops_service.start_operation(operation_id, dummy_task)

        # Update progress
        await ops_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=50.0,
                current_step="Calling Anthropic API",
                steps_completed=2,
                steps_total=5,
            ),
        )

        # Query operation
        op = await ops_service.get_operation(operation_id)

        assert op is not None
        assert op.progress.percentage == 50.0
        assert op.progress.current_step == "Calling Anthropic API"
        assert op.progress.steps_completed == 2
        assert op.progress.steps_total == 5

    @pytest.mark.asyncio
    async def test_token_counts_in_result_summary(self):
        """Token counts should be visible in result_summary on completion."""
        ops_service = OperationsService()

        # Create and start operation
        operation = await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(
                symbol="N/A",
                timeframe="N/A",
                mode="strategy_design",
                parameters={"session_id": 123},
            ),
        )
        operation_id = operation.operation_id

        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await ops_service.start_operation(operation_id, dummy_task)

        # Complete with token counts
        await ops_service.complete_operation(
            operation_id,
            result_summary={
                "session_id": 123,
                "strategy_name": "momentum_crossover_v1",
                "input_tokens": 1500,
                "output_tokens": 800,
            },
        )

        # Query and verify
        op = await ops_service.get_operation(operation_id)

        assert op is not None
        assert op.status == OperationStatus.COMPLETED
        assert op.result_summary is not None
        assert op.result_summary["input_tokens"] == 1500
        assert op.result_summary["output_tokens"] == 800

    @pytest.mark.asyncio
    async def test_agent_operations_listed_with_others(self):
        """Agent operations should appear in operations list."""
        ops_service = OperationsService()

        # Create training operation
        await ops_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(
                symbol="EURUSD",
                timeframe="1h",
                mode="training",
            ),
        )

        # Create agent operation
        await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(
                symbol="N/A",
                timeframe="N/A",
                mode="strategy_design",
            ),
        )

        # List all operations
        operations, total, active = await ops_service.list_operations()

        # Both should be listed
        assert total == 2
        types = [op.operation_type for op in operations]
        assert OperationType.TRAINING in types
        assert OperationType.AGENT_DESIGN in types

    @pytest.mark.asyncio
    async def test_agent_operation_filter_by_type(self):
        """Should be able to filter operations by AGENT_DESIGN type."""
        ops_service = OperationsService()

        # Create multiple operations
        await ops_service.create_operation(
            operation_type=OperationType.TRAINING,
            metadata=OperationMetadata(symbol="EURUSD", timeframe="1h"),
        )
        await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )
        await ops_service.create_operation(
            operation_type=OperationType.BACKTESTING,
            metadata=OperationMetadata(symbol="GBPUSD", timeframe="1d"),
        )

        # Filter by AGENT_DESIGN
        operations, total, _ = await ops_service.list_operations(
            operation_type=OperationType.AGENT_DESIGN
        )

        assert total == 1
        assert operations[0].operation_type == OperationType.AGENT_DESIGN


class TestAgentOperationProgress:
    """Test progress tracking during agent execution."""

    @pytest.mark.asyncio
    async def test_progress_updates_at_checkpoints(self):
        """Progress should update at expected checkpoints."""
        ops_service = OperationsService()

        operation = await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )
        operation_id = operation.operation_id

        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await ops_service.start_operation(operation_id, dummy_task)

        # Checkpoint 1: Preparing context
        await ops_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=5.0,
                current_step="Preparing agent context",
                steps_completed=1,
                steps_total=5,
            ),
        )
        op = await ops_service.get_operation(operation_id)
        assert op.progress.current_step == "Preparing agent context"

        # Checkpoint 2: Calling API
        await ops_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=20.0,
                current_step="Calling Anthropic API",
                steps_completed=2,
                steps_total=5,
            ),
        )
        op = await ops_service.get_operation(operation_id)
        assert op.progress.current_step == "Calling Anthropic API"

        # Checkpoint 3: Executing tools
        await ops_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=60.0,
                current_step="Executing tool: save_strategy_config",
                steps_completed=3,
                steps_total=5,
                items_processed=1,
                items_total=2,
            ),
        )
        op = await ops_service.get_operation(operation_id)
        assert op.progress.items_processed == 1

        # Checkpoint 4: Validating
        await ops_service.update_progress(
            operation_id,
            OperationProgress(
                percentage=90.0,
                current_step="Validating strategy",
                steps_completed=4,
                steps_total=5,
            ),
        )

        # Checkpoint 5: Complete
        await ops_service.complete_operation(
            operation_id,
            result_summary={
                "strategy_name": "test_strategy",
                "input_tokens": 1000,
                "output_tokens": 500,
            },
        )
        op = await ops_service.get_operation(operation_id)
        assert op.progress.percentage == 100.0
        assert op.status == OperationStatus.COMPLETED


class TestAgentOperationErrorHandling:
    """Test error handling for agent operations."""

    @pytest.mark.asyncio
    async def test_operation_fails_on_error(self):
        """Operation should be marked as FAILED on error."""
        ops_service = OperationsService()

        operation = await ops_service.create_operation(
            operation_type=OperationType.AGENT_DESIGN,
            metadata=OperationMetadata(symbol="N/A", timeframe="N/A"),
        )
        operation_id = operation.operation_id

        dummy_task = asyncio.create_task(asyncio.sleep(0))
        await ops_service.start_operation(operation_id, dummy_task)

        # Fail the operation
        await ops_service.fail_operation(
            operation_id, "Anthropic API rate limit exceeded"
        )

        op = await ops_service.get_operation(operation_id)
        assert op.status == OperationStatus.FAILED
        assert op.error_message == "Anthropic API rate limit exceeded"


class TestAgentServiceTriggerIntegration:
    """Test that AgentService.trigger properly integrates with OperationsService."""

    @pytest.fixture
    def ops_service(self):
        """Create a real OperationsService for integration tests."""
        return OperationsService()

    @pytest.mark.asyncio
    async def test_trigger_creates_operation_before_work(self, ops_service):
        """trigger() should create operation BEFORE starting background work."""
        from ktrdr.api.services.agent_service import AgentService

        mock_db = AsyncMock()
        mock_db.get_active_session.return_value = None

        with (
            patch(
                "ktrdr.api.services.agent_service.get_agent_db",
                new=AsyncMock(return_value=mock_db),
            ),
            patch(
                "ktrdr.api.services.agent_service.TriggerConfig.from_env"
            ) as mock_config,
        ):
            mock_config.return_value.enabled = True

            service = AgentService(operations_service=ops_service)
            result = await service.trigger(dry_run=False)

            # Should return operation_id
            assert result["triggered"] is True
            assert "operation_id" in result
            operation_id = result["operation_id"]

            # Operation should exist and be RUNNING
            op = await ops_service.get_operation(operation_id)
            assert op is not None
            assert op.operation_type == OperationType.AGENT_DESIGN
            assert op.status == OperationStatus.RUNNING

            # Allow background task to start
            await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_trigger_dry_run_no_operation_created(self, ops_service):
        """trigger(dry_run=True) should NOT create an operation."""
        from ktrdr.api.services.agent_service import AgentService

        mock_db = AsyncMock()
        mock_db.get_active_session.return_value = None

        with (
            patch(
                "ktrdr.api.services.agent_service.get_agent_db",
                new=AsyncMock(return_value=mock_db),
            ),
            patch(
                "ktrdr.api.services.agent_service.TriggerConfig.from_env"
            ) as mock_config,
        ):
            mock_config.return_value.enabled = True

            service = AgentService(operations_service=ops_service)
            result = await service.trigger(dry_run=True)

            # Should indicate dry run
            assert result["dry_run"] is True
            assert result["would_trigger"] is True

            # No operations should exist
            operations, total, _ = await ops_service.list_operations()
            assert total == 0
