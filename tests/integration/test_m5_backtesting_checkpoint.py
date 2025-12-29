"""Integration tests for M5: Backtesting Checkpoint + Resume.

This test suite verifies the complete M5 backtesting checkpoint flow:
1. Start backtest, wait for periodic checkpoint
2. Cancel backtest
3. Resume backtest from checkpoint
4. Verify continues from correct bar
5. Verify portfolio state restored
6. Verify final results are valid

Note: Uses mocked DB/checkpoint services for fast feedback.
For real Docker-based tests, see tests/e2e/container/
"""

import pytest

from ktrdr.backtesting.checkpoint_restore import BacktestResumeContext
from ktrdr.checkpoint.checkpoint_policy import CheckpointPolicy
from ktrdr.checkpoint.schemas import BacktestCheckpointState
from tests.integration.fixtures.checkpoint_mocks import (
    IntegrationCheckpointService,
    MockOperationsRepository,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def checkpoint_service():
    """Create IntegrationCheckpointService (no temp directory needed)."""
    return IntegrationCheckpointService()


@pytest.fixture
def operations_repo():
    """Create MockOperationsRepository."""
    return MockOperationsRepository()


@pytest.fixture
def checkpoint_policy():
    """Create CheckpointPolicy with short intervals for testing."""
    return CheckpointPolicy(
        unit_interval=1000,  # Checkpoint every 1000 bars
        time_interval_seconds=3600,  # Disable time-based
    )


def create_portfolio_state(
    bar_index: int,
    starting_cash: float = 10000.0,
    trade_pnl: float = 0.0,
) -> tuple[float, list[dict], list[dict]]:
    """Create portfolio state for a given bar index.

    Returns:
        Tuple of (cash, positions, trades)
    """
    cash = starting_cash + trade_pnl

    # Simulate some open positions
    positions = []
    if bar_index > 500:
        positions.append(
            {
                "symbol": "EURUSD",
                "quantity": 1000,
                "entry_price": 1.0850,
                "entry_date": "2023-06-15T10:30:00",
            }
        )

    # Simulate some completed trades
    trades = []
    for i in range(bar_index // 500):
        trades.append(
            {
                "trade_id": i + 1,
                "symbol": "EURUSD",
                "side": "buy" if i % 2 == 0 else "sell",
                "quantity": 1000,
                "price": 1.0850 + (i * 0.001),
                "date": f"2023-{(i % 12) + 1:02d}-15T10:30:00",
                "pnl": 50.0 * (1 if i % 2 == 1 else -1),
            }
        )

    return cash, positions, trades


def create_equity_samples(
    bar_index: int, starting_equity: float = 10000.0
) -> list[dict]:
    """Create sampled equity curve up to bar_index."""
    samples = []
    # Sample every 100 bars (matching default equity sample interval)
    for i in range(0, bar_index + 1, 100):
        equity = starting_equity + (i * 0.5)  # Simple linear growth
        samples.append(
            {
                "bar_index": i,
                "equity": equity,
            }
        )
    return samples


# ============================================================================
# Test: Full Resume Flow
# ============================================================================


class TestM5FullResumeFlow:
    """Integration tests for the complete backtesting resume flow."""

    @pytest.mark.asyncio
    async def test_full_resume_flow_start_cancel_resume_complete(
        self, checkpoint_service, operations_repo, checkpoint_policy
    ):
        """
        Test the complete M5 backtesting resume flow:
        1. Start backtest, periodic checkpoints are saved
        2. Cancel backtest
        3. Verify checkpoint exists
        4. Resume backtest
        5. Verify backtest continues from correct bar
        6. Complete backtest
        7. Verify checkpoint deleted
        """
        operation_id = "op_backtest_full_resume_flow"

        # Step 1: Create operation
        await operations_repo.create(operation_id, "backtesting", status="running")

        # Step 2: Simulate backtesting with periodic checkpoints
        total_bars = 5000
        cancel_at_bar = 3500

        for bar_index in range(0, cancel_at_bar + 1, 100):  # Step by 100 for efficiency
            # Update progress
            progress = int((bar_index / total_bars) * 100)
            await operations_repo.update_status(
                operation_id, "running", progress_percent=progress
            )

            # Check if we should checkpoint
            if checkpoint_policy.should_checkpoint(bar_index):
                cash, positions, trades = create_portfolio_state(bar_index)
                equity_samples = create_equity_samples(bar_index)

                state = BacktestCheckpointState(
                    bar_index=bar_index,
                    current_date=f"2023-06-15T{(bar_index % 24):02d}:00:00",
                    cash=cash,
                    positions=positions,
                    trades=trades,
                    equity_samples=equity_samples,
                    original_request={
                        "strategy_name": "test_strategy",
                        "symbol": "EURUSD",
                        "timeframe": "1h",
                        "start_date": "2023-01-01",
                        "end_date": "2023-12-31",
                    },
                )

                await checkpoint_service.save_checkpoint(
                    operation_id=operation_id,
                    checkpoint_type="periodic",
                    state=state.to_dict(),
                    artifacts=None,  # No artifacts for backtesting
                )
                checkpoint_policy.record_checkpoint(bar_index)

        # Step 3: Cancel backtest (simulate user cancellation at bar 3500)
        cancel_cash, cancel_positions, cancel_trades = create_portfolio_state(
            cancel_at_bar
        )
        cancel_state = BacktestCheckpointState(
            bar_index=cancel_at_bar,
            current_date="2023-06-15T11:00:00",
            cash=cancel_cash,
            positions=cancel_positions,
            trades=cancel_trades,
            equity_samples=create_equity_samples(cancel_at_bar),
            original_request={
                "strategy_name": "test_strategy",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=cancel_state.to_dict(),
            artifacts=None,
        )
        await operations_repo.update_status(operation_id, "cancelled")

        # Step 4: Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.state["bar_index"] == cancel_at_bar
        assert checkpoint.state["operation_type"] == "backtesting"
        assert checkpoint.checkpoint_type == "cancellation"

        # Step 5: Resume backtest
        resume_success = await operations_repo.try_resume(operation_id)
        assert resume_success is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "resuming"

        # Load checkpoint for resume context
        resume_checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert resume_checkpoint is not None

        # Create resume context (per design D7: start from checkpoint_bar + 1)
        resume_context = BacktestResumeContext(
            start_bar=resume_checkpoint.state["bar_index"] + 1,
            cash=resume_checkpoint.state["cash"],
            original_request=resume_checkpoint.state["original_request"],
            positions=resume_checkpoint.state.get("positions", []),
            trades=resume_checkpoint.state.get("trades", []),
            equity_samples=resume_checkpoint.state.get("equity_samples", []),
        )

        # Verify start bar is correct (checkpoint was at 3500, resume from 3501)
        assert resume_context.start_bar == cancel_at_bar + 1

        # Verify portfolio state is restored
        assert resume_context.cash == cancel_cash
        assert len(resume_context.positions) == len(cancel_positions)
        assert len(resume_context.trades) == len(cancel_trades)

        # Step 6: Simulate resumed backtesting from bar 3501 to 4999
        await operations_repo.update_status(operation_id, "running")
        for bar_index in range(resume_context.start_bar, total_bars, 100):
            progress = int((bar_index / total_bars) * 100)
            await operations_repo.update_status(
                operation_id, "running", progress_percent=progress
            )

        # Step 7: Complete backtest
        await operations_repo.update_status(
            operation_id, "completed", progress_percent=100
        )

        # Step 8: Delete checkpoint after completion
        deleted = await checkpoint_service.delete_checkpoint(operation_id)
        assert deleted is True

        # Verify checkpoint is gone
        assert not checkpoint_service.checkpoint_exists(operation_id)

        # Verify operation is completed
        final_op = operations_repo.get(operation_id)
        assert final_op["status"] == "completed"
        assert final_op["progress_percent"] == 100


# ============================================================================
# Test: Resume From Correct Bar
# ============================================================================


class TestM5ResumeFromCorrectBar:
    """Tests for verifying backtest resumes from the correct bar."""

    @pytest.mark.asyncio
    async def test_resume_starts_from_checkpoint_bar_plus_one(self, checkpoint_service):
        """Per design D7: Resume starts from checkpoint_bar + 1."""
        operation_id = "op_resume_bar_test"

        # Save checkpoint at bar 2500
        checkpoint_bar = 2500
        cash, positions, trades = create_portfolio_state(checkpoint_bar)
        state = BacktestCheckpointState(
            bar_index=checkpoint_bar,
            current_date="2023-06-15T10:00:00",
            cash=cash,
            positions=positions,
            trades=trades,
            original_request={"symbol": "EURUSD", "timeframe": "1h"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        # Load checkpoint and create resume context
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            positions=checkpoint.state.get("positions", []),
            trades=checkpoint.state.get("trades", []),
        )

        # Verify start bar is checkpoint_bar + 1
        assert resume_context.start_bar == checkpoint_bar + 1
        assert resume_context.start_bar == 2501

    @pytest.mark.asyncio
    async def test_resume_from_bar_zero_checkpoint(self, checkpoint_service):
        """Test resume from a checkpoint at bar 0."""
        operation_id = "op_resume_bar_zero"

        state = BacktestCheckpointState(
            bar_index=0,
            current_date="2023-01-01T00:00:00",
            cash=10000.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="failure",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
        )

        # Resume from bar 1
        assert resume_context.start_bar == 1

    @pytest.mark.asyncio
    async def test_equity_samples_preserved_on_resume(self, checkpoint_service):
        """Test that equity samples from prior bars are preserved."""
        operation_id = "op_resume_equity"

        # Checkpoint at bar 2000 with equity samples
        checkpoint_bar = 2000
        equity_samples = create_equity_samples(checkpoint_bar)

        state = BacktestCheckpointState(
            bar_index=checkpoint_bar,
            current_date="2023-06-15T10:00:00",
            cash=10500.0,
            equity_samples=equity_samples,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            equity_samples=checkpoint.state.get("equity_samples", []),
        )

        # Verify equity samples are preserved
        # At bar 2000, with samples every 100 bars, we should have 21 samples (0, 100, 200, ..., 2000)
        expected_samples = (checkpoint_bar // 100) + 1
        assert len(resume_context.equity_samples) == expected_samples


# ============================================================================
# Test: Portfolio Restoration
# ============================================================================


class TestM5PortfolioRestoration:
    """Tests for verifying portfolio state restoration on resume."""

    @pytest.mark.asyncio
    async def test_cash_restored_on_resume(self, checkpoint_service):
        """Test that cash balance is correctly restored."""
        operation_id = "op_cash_restore"

        original_cash = 9875.50
        state = BacktestCheckpointState(
            bar_index=1500,
            current_date="2023-06-15T10:00:00",
            cash=original_cash,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
        )

        assert resume_context.cash == original_cash

    @pytest.mark.asyncio
    async def test_positions_restored_on_resume(self, checkpoint_service):
        """Test that open positions are correctly restored."""
        operation_id = "op_positions_restore"

        positions = [
            {
                "symbol": "EURUSD",
                "quantity": 1000,
                "entry_price": 1.0850,
                "entry_date": "2023-06-15T10:30:00",
            },
            {
                "symbol": "GBPUSD",
                "quantity": -500,
                "entry_price": 1.2450,
                "entry_date": "2023-06-15T11:00:00",
            },
        ]

        state = BacktestCheckpointState(
            bar_index=1500,
            current_date="2023-06-15T12:00:00",
            cash=8500.0,
            positions=positions,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            positions=checkpoint.state.get("positions", []),
        )

        assert len(resume_context.positions) == 2
        assert resume_context.positions[0]["symbol"] == "EURUSD"
        assert resume_context.positions[0]["quantity"] == 1000
        assert resume_context.positions[1]["symbol"] == "GBPUSD"
        assert resume_context.positions[1]["quantity"] == -500

    @pytest.mark.asyncio
    async def test_trades_restored_on_resume(self, checkpoint_service):
        """Test that trade history is correctly restored."""
        operation_id = "op_trades_restore"

        trades = [
            {
                "trade_id": 1,
                "symbol": "EURUSD",
                "side": "buy",
                "quantity": 1000,
                "price": 1.0800,
                "date": "2023-06-10T10:00:00",
                "pnl": 0.0,
            },
            {
                "trade_id": 2,
                "symbol": "EURUSD",
                "side": "sell",
                "quantity": 1000,
                "price": 1.0850,
                "date": "2023-06-12T14:00:00",
                "pnl": 50.0,
            },
        ]

        state = BacktestCheckpointState(
            bar_index=1500,
            current_date="2023-06-15T12:00:00",
            cash=10050.0,  # 10000 + 50 pnl
            trades=trades,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            trades=checkpoint.state.get("trades", []),
        )

        assert len(resume_context.trades) == 2
        assert resume_context.trades[0]["trade_id"] == 1
        assert resume_context.trades[1]["pnl"] == 50.0


# ============================================================================
# Test: Checkpoint Cleanup After Completion
# ============================================================================


class TestM5CheckpointCleanup:
    """Tests for checkpoint deletion after successful completion."""

    @pytest.mark.asyncio
    async def test_checkpoint_deleted_after_successful_completion(
        self, checkpoint_service
    ):
        """Test that checkpoint is deleted after backtest completes successfully."""
        operation_id = "op_cleanup_success"

        # Save a checkpoint
        state = BacktestCheckpointState(
            bar_index=2500,
            current_date="2023-06-15T10:00:00",
            cash=10200.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="periodic",
            state=state.to_dict(),
            artifacts=None,
        )

        # Verify checkpoint exists
        assert checkpoint_service.checkpoint_exists(operation_id)

        # Simulate successful completion - delete checkpoint
        deleted = await checkpoint_service.delete_checkpoint(operation_id)

        # Verify deletion
        assert deleted is True
        assert not checkpoint_service.checkpoint_exists(operation_id)

    @pytest.mark.asyncio
    async def test_checkpoint_preserved_on_resume_failure(self, checkpoint_service):
        """Per design D6: Checkpoint preserved if resume fails."""
        operation_id = "op_resume_failure"

        # Save checkpoint
        state = BacktestCheckpointState(
            bar_index=3000,
            current_date="2023-06-15T12:00:00",
            cash=9800.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        # Simulate resume attempt that fails (don't delete checkpoint)
        # Just verify checkpoint is still there

        assert checkpoint_service.checkpoint_exists(operation_id)

        # Load and verify still valid
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is not None
        assert checkpoint.state["bar_index"] == 3000

    @pytest.mark.asyncio
    async def test_delete_nonexistent_checkpoint_returns_false(
        self, checkpoint_service
    ):
        """Test that deleting a non-existent checkpoint returns False."""
        result = await checkpoint_service.delete_checkpoint("nonexistent_op")
        assert result is False


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestM5EdgeCases:
    """Tests for edge cases in the backtest resume flow."""

    @pytest.mark.asyncio
    async def test_resume_already_running_operation_fails(self, operations_repo):
        """Test that resuming an already running operation fails."""
        operation_id = "op_already_running"

        await operations_repo.create(operation_id, "backtesting", status="running")

        # Try to resume - should fail
        result = await operations_repo.try_resume(operation_id)
        assert result is False

        # Status should still be running
        op = operations_repo.get(operation_id)
        assert op["status"] == "running"

    @pytest.mark.asyncio
    async def test_resume_completed_operation_fails(self, operations_repo):
        """Test that resuming a completed operation fails."""
        operation_id = "op_completed"

        await operations_repo.create(operation_id, "backtesting", status="completed")

        result = await operations_repo.try_resume(operation_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_resume_cancelled_operation_succeeds(self, operations_repo):
        """Test that resuming a cancelled operation succeeds."""
        operation_id = "op_cancelled"

        await operations_repo.create(operation_id, "backtesting", status="cancelled")

        result = await operations_repo.try_resume(operation_id)
        assert result is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "resuming"

    @pytest.mark.asyncio
    async def test_resume_failed_operation_succeeds(self, operations_repo):
        """Test that resuming a failed operation succeeds."""
        operation_id = "op_failed"

        await operations_repo.create(operation_id, "backtesting", status="failed")

        result = await operations_repo.try_resume(operation_id)
        assert result is True

        op = operations_repo.get(operation_id)
        assert op["status"] == "resuming"

    @pytest.mark.asyncio
    async def test_resume_without_checkpoint_is_detectable(
        self, checkpoint_service, operations_repo
    ):
        """Test that attempting to resume without a checkpoint is detectable."""
        operation_id = "op_no_checkpoint"

        await operations_repo.create(operation_id, "backtesting", status="cancelled")

        # Resume succeeds at operation level
        result = await operations_repo.try_resume(operation_id)
        assert result is True

        # But checkpoint doesn't exist
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        assert checkpoint is None

        # Caller should detect this and fail appropriately
        assert not checkpoint_service.checkpoint_exists(operation_id)


# ============================================================================
# Test: BacktestResumeContext Integration
# ============================================================================


class TestM5ResumeContextIntegration:
    """Tests for BacktestResumeContext creation and validation."""

    @pytest.mark.asyncio
    async def test_resume_context_created_from_checkpoint(self, checkpoint_service):
        """Test that BacktestResumeContext is correctly created from checkpoint."""
        operation_id = "op_resume_context"

        # Save checkpoint with all fields
        checkpoint_bar = 2000
        cash, positions, trades = create_portfolio_state(
            checkpoint_bar, trade_pnl=250.0
        )
        equity_samples = create_equity_samples(checkpoint_bar)

        state = BacktestCheckpointState(
            bar_index=checkpoint_bar,
            current_date="2023-06-15T10:00:00",
            cash=cash,
            positions=positions,
            trades=trades,
            equity_samples=equity_samples,
            original_request={
                "strategy_name": "test_strategy",
                "symbol": "EURUSD",
                "timeframe": "1h",
                "start_date": "2023-01-01",
                "end_date": "2023-12-31",
            },
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        # Load and create resume context
        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            positions=checkpoint.state.get("positions", []),
            trades=checkpoint.state.get("trades", []),
            equity_samples=checkpoint.state.get("equity_samples", []),
        )

        # Verify all fields
        assert resume_context.start_bar == checkpoint_bar + 1
        assert resume_context.cash == cash
        assert resume_context.original_request["symbol"] == "EURUSD"
        assert len(resume_context.positions) == len(positions)
        assert len(resume_context.trades) == len(trades)
        assert len(resume_context.equity_samples) == len(equity_samples)

    @pytest.mark.asyncio
    async def test_resume_context_with_empty_optional_fields(self, checkpoint_service):
        """Test resume context when optional fields are empty."""
        operation_id = "op_resume_minimal"

        # Minimal checkpoint with only required fields
        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T10:00:00",
            cash=10000.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        resume_context = BacktestResumeContext(
            start_bar=checkpoint.state["bar_index"] + 1,
            cash=checkpoint.state["cash"],
            original_request=checkpoint.state["original_request"],
            positions=checkpoint.state.get("positions", []),
            trades=checkpoint.state.get("trades", []),
            equity_samples=checkpoint.state.get("equity_samples", []),
        )

        # Verify empty lists for optional fields
        assert resume_context.positions == []
        assert resume_context.trades == []
        assert resume_context.equity_samples == []


# ============================================================================
# Test: Operation Type Verification
# ============================================================================


class TestM5OperationType:
    """Tests for verifying operation_type is correct for worker dispatch."""

    @pytest.mark.asyncio
    async def test_checkpoint_has_correct_operation_type(self, checkpoint_service):
        """Test that checkpoint state includes operation_type='backtesting'."""
        operation_id = "op_type_check"

        state = BacktestCheckpointState(
            bar_index=1000,
            current_date="2023-06-15T10:00:00",
            cash=10000.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)

        # Verify operation_type is present and correct
        assert checkpoint.state["operation_type"] == "backtesting"

    @pytest.mark.asyncio
    async def test_operation_type_used_for_worker_dispatch(self, checkpoint_service):
        """Test that operation_type can be used to dispatch to correct worker."""
        operation_id = "op_dispatch_test"

        state = BacktestCheckpointState(
            bar_index=2000,
            current_date="2023-06-15T12:00:00",
            cash=10100.0,
            original_request={"symbol": "EURUSD"},
        )

        await checkpoint_service.save_checkpoint(
            operation_id=operation_id,
            checkpoint_type="cancellation",
            state=state.to_dict(),
            artifacts=None,
        )

        checkpoint = await checkpoint_service.load_checkpoint(operation_id)
        op_type = checkpoint.state.get("operation_type")

        # Backend resume endpoint would use this to dispatch
        if op_type == "backtesting":
            worker_type = "BACKTESTING"
        elif op_type == "training":
            worker_type = "TRAINING"
        else:
            worker_type = "UNKNOWN"

        assert worker_type == "BACKTESTING"
