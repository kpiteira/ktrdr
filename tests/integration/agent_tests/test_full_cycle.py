"""
Full cycle integration tests for the agent research system (Task 2.9).

These tests validate the complete design → train → backtest → assess loop.

Test scenarios:
1. Happy path: design → train (pass gate) → backtest (pass gate) → assess → success
2. Training gate failure: design → train (fail gate) → end
3. Backtest gate failure: design → train (pass gate) → backtest (fail gate) → end
4. Training error: design → train (error) → end

Requirements:
- PostgreSQL database (set DATABASE_URL environment variable)

Run with:
    DATABASE_URL="postgresql://ktrdr:localdev@localhost:5432/ktrdr" \
    uv run pytest tests/integration/agent_tests/test_full_cycle.py -v
"""

import os
import re
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from research_agents.database.queries import AgentDatabase
from research_agents.database.schema import SessionOutcome, SessionPhase
from research_agents.services.invoker import InvocationResult
from research_agents.services.trigger import TriggerConfig, TriggerService

# Skip all tests in this module if no database URL is set
pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL environment variable not set - skipping E2E tests",
)


class MockContextProvider:
    """Mock context provider for testing."""

    async def get_available_indicators(self) -> list[dict[str, Any]]:
        return [
            {
                "id": "RSIIndicator",
                "name": "RSI",
                "type": "momentum",
                "description": "Relative Strength Index",
                "parameters": [{"name": "period", "type": "int", "default": 14}],
            },
        ]

    async def get_available_symbols(self) -> list[dict[str, Any]]:
        return [
            {
                "symbol": "EURUSD",
                "name": "EUR/USD",
                "type": "forex",
                "available_timeframes": ["1h", "1d"],
            },
        ]


class MockFullCycleInvoker:
    """Mock invoker that simulates the full design → assess cycle.

    This invoker handles both design and assessment phases:
    - Design phase: Creates valid strategy, updates session to DESIGNED
    - Assessment phase: Records assessment, completes session
    """

    def __init__(
        self,
        db: AgentDatabase,
        strategies_dir: str = "strategies",
        should_fail_design: bool = False,
        should_fail_assessment: bool = False,
    ):
        self.db = db
        self.strategies_dir = strategies_dir
        self.should_fail_design = should_fail_design
        self.should_fail_assessment = should_fail_assessment
        self.invoke_count = 0
        self.design_invoke_count = 0
        self.assessment_invoke_count = 0
        self.designed_strategy_name: str | None = None

    def _has_run_method(self) -> bool:
        """Check if this is a modern invoker with run() method."""
        return hasattr(self, "run") and callable(self.run)

    async def invoke(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> InvocationResult:
        """Legacy invoke method - delegates to appropriate handler."""
        self.invoke_count += 1

        # Detect phase from prompt content
        if "ASSESSING" in prompt.upper() or "assessment" in prompt.lower():
            return await self._handle_assessment(prompt, system_prompt)
        else:
            return await self._handle_design(prompt, system_prompt)

    async def run(
        self,
        prompt: str,
        tools: list[dict[str, Any]],
        system_prompt: str,
        tool_executor: Any | None = None,
    ) -> Any:
        """Modern run method with tool support."""
        from dataclasses import dataclass

        @dataclass
        class AgentResult:
            success: bool
            output: str
            input_tokens: int
            output_tokens: int
            error: str | None

        self.invoke_count += 1

        # Detect phase from prompt content
        if "ASSESSING" in prompt.upper() or "backtest" in prompt.lower():
            result = await self._handle_assessment(prompt, system_prompt)
        else:
            result = await self._handle_design(prompt, system_prompt)

        return AgentResult(
            success=result.success,
            output=result.raw_output or "",
            input_tokens=100,
            output_tokens=50,
            error=result.error,
        )

    async def _handle_design(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> InvocationResult:
        """Handle design phase invocation."""
        from research_agents.services.strategy_service import save_strategy_config

        self.design_invoke_count += 1

        if self.should_fail_design:
            return InvocationResult(
                success=False,
                exit_code=1,
                output=None,
                raw_output="Design failed",
                error="Mock design failure",
            )

        try:
            # Extract session_id from prompt
            match = re.search(r"Session ID:\s*(\d+)", prompt)
            if not match:
                raise ValueError("Could not find session_id in prompt")
            session_id = int(match.group(1))

            # Create valid strategy config
            timestamp = int(time.time())
            strategy_name = f"full_cycle_test_{timestamp}"
            strategy_config = {
                "name": strategy_name,
                "description": "Full cycle test strategy",
                "version": "1.0",
                "hypothesis": "Test hypothesis",
                "scope": "universal",
                "training_data": {
                    "symbols": {"mode": "single", "list": ["EURUSD"]},
                    "timeframes": {
                        "mode": "single",
                        "list": ["1h"],
                        "base_timeframe": "1h",
                    },
                    "history_required": 200,
                },
                "deployment": {
                    "target_symbols": {"mode": "training_only"},
                    "target_timeframes": {"mode": "single", "supported": ["1h"]},
                },
                "indicators": [
                    {
                        "name": "rsi",
                        "feature_id": "rsi_14",
                        "period": 14,
                        "source": "close",
                    }
                ],
                "fuzzy_sets": {
                    "rsi_14": {
                        "oversold": {"type": "triangular", "parameters": [0, 20, 35]},
                        "neutral": {"type": "triangular", "parameters": [30, 50, 70]},
                        "overbought": {
                            "type": "triangular",
                            "parameters": [65, 80, 100],
                        },
                    }
                },
                "model": {
                    "type": "mlp",
                    "architecture": {
                        "hidden_layers": [32, 16],
                        "activation": "relu",
                        "output_activation": "softmax",
                        "dropout": 0.2,
                    },
                    "features": {
                        "include_price_context": False,
                        "lookback_periods": 2,
                        "scale_features": True,
                    },
                    "training": {
                        "learning_rate": 0.001,
                        "batch_size": 32,
                        "epochs": 50,
                        "optimizer": "adam",
                        "early_stopping": {
                            "enabled": True,
                            "patience": 10,
                            "min_delta": 0.001,
                        },
                    },
                },
                "decisions": {
                    "output_format": "classification",
                    "confidence_threshold": 0.6,
                    "position_awareness": True,
                },
                "training": {
                    "method": "supervised",
                    "labels": {
                        "source": "zigzag",
                        "zigzag_threshold": 0.03,
                        "label_lookahead": 20,
                    },
                    "data_split": {"train": 0.7, "validation": 0.15, "test": 0.15},
                },
            }

            # Save strategy
            save_result = await save_strategy_config(
                name=strategy_name,
                config=strategy_config,
                description="Full cycle test strategy",
                strategies_dir=self.strategies_dir,
            )

            if not save_result["success"]:
                raise ValueError(
                    f"Failed to save strategy: {save_result.get('errors')}"
                )

            self.designed_strategy_name = strategy_name

            # Update session to DESIGNED
            await self.db.update_session(
                session_id=session_id,
                phase=SessionPhase.DESIGNED,
                strategy_name=strategy_name,
            )

            return InvocationResult(
                success=True,
                exit_code=0,
                output={"session_id": session_id, "strategy_name": strategy_name},
                raw_output=f"Strategy {strategy_name} designed successfully",
                error=None,
            )

        except Exception as e:
            return InvocationResult(
                success=False,
                exit_code=1,
                output=None,
                raw_output="",
                error=str(e),
            )

    async def _handle_assessment(
        self,
        prompt: str,
        system_prompt: str | None,
    ) -> InvocationResult:
        """Handle assessment phase invocation."""
        self.assessment_invoke_count += 1

        if self.should_fail_assessment:
            return InvocationResult(
                success=False,
                exit_code=1,
                output=None,
                raw_output="Assessment failed",
                error="Mock assessment failure",
            )

        try:
            # Extract session_id from prompt
            match = re.search(r"Session ID:\s*(\d+)", prompt)
            if not match:
                # Session may already be in ASSESSING phase, get it from DB
                pass

            return InvocationResult(
                success=True,
                exit_code=0,
                output={"status": "assessed"},
                raw_output="Assessment completed successfully",
                error=None,
            )

        except Exception as e:
            return InvocationResult(
                success=False,
                exit_code=1,
                output=None,
                raw_output="",
                error=str(e),
            )


def create_mock_operation(
    operation_id: str,
    status: str,
    result_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
):
    """Create a mock operation object."""
    mock_op = MagicMock()
    mock_op.operation_id = operation_id
    mock_op.status = status
    mock_op.result_summary = result_summary
    mock_op.error_message = error_message
    return mock_op


@pytest_asyncio.fixture
async def agent_db():
    """Create and connect to the agent database."""
    db = AgentDatabase()
    try:
        await db.connect(os.getenv("DATABASE_URL"))
    except Exception as e:
        pytest.skip(f"Could not connect to database: {e}")
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def clean_db(agent_db: AgentDatabase):
    """Ensure database is clean before each test."""
    async with agent_db.pool.acquire() as conn:
        await conn.execute("DELETE FROM agent_actions")
        await conn.execute("DELETE FROM agent_sessions")
    return agent_db


@pytest_asyncio.fixture
async def test_strategies_dir(tmp_path):
    """Create a temporary directory for test strategies."""
    strategies_dir = tmp_path / "test_strategies"
    strategies_dir.mkdir()
    return str(strategies_dir)


class TestFullCycleHappyPath:
    """Test the complete happy path: design → train → backtest → assess."""

    @pytest.mark.asyncio
    async def test_full_cycle_success(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test complete cycle: design → train (pass) → backtest (pass) → assess.

        This test simulates:
        1. Agent designs a strategy (DESIGNING → DESIGNED)
        2. Training starts and completes successfully (DESIGNED → TRAINING)
        3. Training gate passes
        4. Backtest starts and completes successfully (TRAINING → BACKTESTING)
        5. Backtest gate passes
        6. Agent assesses results (BACKTESTING → ASSESSING → COMPLETE)
        """
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        # Mock training API to return success
        mock_training_result = {
            "success": True,
            "operation_id": "op_training_test_001",
        }

        # Mock backtest API to return success
        mock_backtest_result = {
            "success": True,
            "operation_id": "op_backtest_test_001",
        }

        # Mock operations service
        mock_ops_service = MagicMock()

        # Training operation: completed with passing metrics
        training_op = create_mock_operation(
            operation_id="op_training_test_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.65,  # Above 0.45 threshold
                "final_loss": 0.3,  # Below 0.8 threshold
                "initial_loss": 1.0,  # Loss reduction > 20%
                "model_path": "/app/models/test_model.pt",
            },
        )

        # Backtest operation: completed with passing metrics
        backtest_op = create_mock_operation(
            operation_id="op_backtest_test_001",
            status="COMPLETED",
            result_summary={
                "win_rate": 0.55,  # Above 0.45 threshold
                "max_drawdown": 0.15,  # Below 0.4 threshold
                "sharpe_ratio": 0.8,  # Above -0.5 threshold
            },
        )

        async def mock_get_operation(op_id: str):
            if "training" in op_id:
                return training_op
            elif "backtest" in op_id:
                return backtest_op
            return None

        mock_ops_service.get_operation = AsyncMock(side_effect=mock_get_operation)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act - Phase 1: Design
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new=AsyncMock(return_value=mock_backtest_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            # Trigger 1: Design phase
            result1 = await service.check_and_trigger()
            assert result1["triggered"] is True
            session_id = result1["session_id"]

            # Verify session is in DESIGNED state
            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.DESIGNED

            # Trigger 2: Should start training
            result2 = await service.check_and_trigger()
            assert result2["reason"] == "handled_designed_session"

            # Verify session is now in TRAINING state
            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.TRAINING

            # Trigger 3: Training complete, gate passes, start backtest
            result3 = await service.check_and_trigger()
            assert result3["reason"] == "training_gate_passed_backtest_started"

            # Verify session is now in BACKTESTING state
            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.BACKTESTING

            # Trigger 4: Backtest complete, gate passes, invoke assessment
            result4 = await service.check_and_trigger()
            assert result4["reason"] == "assessment_completed"
            assert result4["outcome"] == "success"

            # Verify session is COMPLETE with SUCCESS outcome
            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.COMPLETE
            assert session.outcome == SessionOutcome.SUCCESS

        # Assert invoker was called for design and assessment
        assert mock_invoker.design_invoke_count == 1
        assert mock_invoker.assessment_invoke_count == 1


class TestTrainingGateFailure:
    """Test training gate failure scenarios."""

    @pytest.mark.asyncio
    async def test_training_gate_fails_low_accuracy(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when training accuracy is below threshold.

        Expected flow:
        1. Design completes successfully
        2. Training completes but accuracy < 0.45
        3. Training gate fails
        4. Session marked as FAILED_TRAINING_GATE
        """
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {
            "success": True,
            "operation_id": "op_training_fail_001",
        }

        # Training operation with low accuracy (below 0.45 threshold)
        training_op = create_mock_operation(
            operation_id="op_training_fail_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.30,  # Below 0.45 threshold - SHOULD FAIL
                "final_loss": 0.3,
                "initial_loss": 1.0,
            },
        )

        mock_ops_service = MagicMock()
        mock_ops_service.get_operation = AsyncMock(return_value=training_op)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            # Trigger 1: Design phase
            result1 = await service.check_and_trigger()
            session_id = result1["session_id"]

            # Trigger 2: Start training
            await service.check_and_trigger()

            # Trigger 3: Training complete, gate should fail
            result3 = await service.check_and_trigger()
            assert result3["reason"] == "training_gate_failed"
            assert "accuracy" in result3["gate_reason"].lower()

            # Verify session outcome
            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.COMPLETE
            assert session.outcome == SessionOutcome.FAILED_TRAINING_GATE

    @pytest.mark.asyncio
    async def test_training_gate_fails_high_loss(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when training loss is above threshold."""
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {
            "success": True,
            "operation_id": "op_training_loss_001",
        }

        # Training operation with high final loss (above 0.8 threshold)
        training_op = create_mock_operation(
            operation_id="op_training_loss_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.55,
                "final_loss": 0.95,  # Above 0.8 threshold - SHOULD FAIL
                "initial_loss": 1.0,
            },
        )

        mock_ops_service = MagicMock()
        mock_ops_service.get_operation = AsyncMock(return_value=training_op)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()
            session_id = result1["session_id"]
            await service.check_and_trigger()  # Start training
            result3 = await service.check_and_trigger()  # Check training

            assert result3["reason"] == "training_gate_failed"
            assert "loss" in result3["gate_reason"].lower()

            session = await clean_db.get_session(session_id)
            assert session.outcome == SessionOutcome.FAILED_TRAINING_GATE


class TestBacktestGateFailure:
    """Test backtest gate failure scenarios."""

    @pytest.mark.asyncio
    async def test_backtest_gate_fails_low_win_rate(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when backtest win rate is below threshold.

        Expected flow:
        1. Design completes successfully
        2. Training completes and passes gate
        3. Backtest completes but win_rate < 0.45
        4. Backtest gate fails
        5. Session marked as FAILED_BACKTEST_GATE
        """
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {"success": True, "operation_id": "op_train_pass_001"}
        mock_backtest_result = {"success": True, "operation_id": "op_bt_fail_001"}

        # Training passes
        training_op = create_mock_operation(
            operation_id="op_train_pass_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.3,
                "initial_loss": 1.0,
                "model_path": "/app/models/test.pt",
            },
        )

        # Backtest fails gate - low win rate
        backtest_op = create_mock_operation(
            operation_id="op_bt_fail_001",
            status="COMPLETED",
            result_summary={
                "win_rate": 0.30,  # Below 0.45 threshold - SHOULD FAIL
                "max_drawdown": 0.15,
                "sharpe_ratio": 0.5,
            },
        )

        mock_ops_service = MagicMock()

        async def mock_get_operation(op_id: str):
            if "train" in op_id:
                return training_op
            elif "bt" in op_id:
                return backtest_op
            return None

        mock_ops_service.get_operation = AsyncMock(side_effect=mock_get_operation)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new=AsyncMock(return_value=mock_backtest_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()  # Design
            session_id = result1["session_id"]
            await service.check_and_trigger()  # Start training
            await service.check_and_trigger()  # Training done, start backtest
            result4 = await service.check_and_trigger()  # Check backtest

            assert result4["reason"] == "backtest_gate_failed"
            assert "win" in result4["gate_reason"].lower()

            session = await clean_db.get_session(session_id)
            assert session.outcome == SessionOutcome.FAILED_BACKTEST_GATE

    @pytest.mark.asyncio
    async def test_backtest_gate_fails_high_drawdown(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when backtest drawdown is above threshold."""
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {"success": True, "operation_id": "op_train_dd_001"}
        mock_backtest_result = {"success": True, "operation_id": "op_bt_dd_001"}

        training_op = create_mock_operation(
            operation_id="op_train_dd_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.3,
                "initial_loss": 1.0,
                "model_path": "/app/models/test.pt",
            },
        )

        # High drawdown (above 0.4 threshold)
        backtest_op = create_mock_operation(
            operation_id="op_bt_dd_001",
            status="COMPLETED",
            result_summary={
                "win_rate": 0.55,
                "max_drawdown": 0.55,  # Above 0.4 threshold - SHOULD FAIL
                "sharpe_ratio": 0.5,
            },
        )

        mock_ops_service = MagicMock()

        async def mock_get_operation(op_id: str):
            if "train" in op_id:
                return training_op
            elif "bt" in op_id:
                return backtest_op
            return None

        mock_ops_service.get_operation = AsyncMock(side_effect=mock_get_operation)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new=AsyncMock(return_value=mock_backtest_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()
            session_id = result1["session_id"]
            await service.check_and_trigger()
            await service.check_and_trigger()
            result4 = await service.check_and_trigger()

            assert result4["reason"] == "backtest_gate_failed"
            assert "drawdown" in result4["gate_reason"].lower()

            session = await clean_db.get_session(session_id)
            assert session.outcome == SessionOutcome.FAILED_BACKTEST_GATE


class TestTrainingError:
    """Test training operation error scenarios."""

    @pytest.mark.asyncio
    async def test_training_operation_fails(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when training operation fails.

        Expected flow:
        1. Design completes successfully
        2. Training operation starts
        3. Training operation fails (FAILED status)
        4. Session marked as FAILED_TRAINING
        """
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {
            "success": True,
            "operation_id": "op_training_error_001",
        }

        # Training operation with FAILED status
        training_op = create_mock_operation(
            operation_id="op_training_error_001",
            status="FAILED",
            error_message="Training failed: Out of memory",
        )

        mock_ops_service = MagicMock()
        mock_ops_service.get_operation = AsyncMock(return_value=training_op)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()  # Design
            session_id = result1["session_id"]
            await service.check_and_trigger()  # Start training
            result3 = await service.check_and_trigger()  # Check training

            assert result3["reason"] == "training_operation_failed"

            session = await clean_db.get_session(session_id)
            assert session.phase == SessionPhase.COMPLETE
            assert session.outcome == SessionOutcome.FAILED_TRAINING

    @pytest.mark.asyncio
    async def test_training_start_fails(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Test that session fails when training fails to start."""
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        # Training API returns failure
        mock_training_result = {
            "success": False,
            "error": "No workers available",
        }

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with patch(
            "ktrdr.agents.executor.start_training_via_api",
            new=AsyncMock(return_value=mock_training_result),
        ):
            result1 = await service.check_and_trigger()  # Design
            session_id = result1["session_id"]
            result2 = await service.check_and_trigger()  # Try to start training

            assert result2["reason"] == "training_start_failed"

            session = await clean_db.get_session(session_id)
            assert session.outcome == SessionOutcome.FAILED_TRAINING


class TestStateTransitions:
    """Test correct state transitions throughout the cycle."""

    @pytest.mark.asyncio
    async def test_state_transitions_logged_correctly(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Verify all state transitions are recorded correctly in database."""
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {"success": True, "operation_id": "op_train_st_001"}
        mock_backtest_result = {"success": True, "operation_id": "op_bt_st_001"}

        training_op = create_mock_operation(
            operation_id="op_train_st_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.3,
                "initial_loss": 1.0,
                "model_path": "/app/models/test.pt",
            },
        )

        backtest_op = create_mock_operation(
            operation_id="op_bt_st_001",
            status="COMPLETED",
            result_summary={
                "win_rate": 0.55,
                "max_drawdown": 0.15,
                "sharpe_ratio": 0.8,
            },
        )

        mock_ops_service = MagicMock()

        async def mock_get_operation(op_id: str):
            if "train" in op_id:
                return training_op
            elif "bt" in op_id:
                return backtest_op
            return None

        mock_ops_service.get_operation = AsyncMock(side_effect=mock_get_operation)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Track state transitions
        states_observed = []

        async def record_state(session_id: int):
            session = await clean_db.get_session(session_id)
            states_observed.append(session.phase)

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new=AsyncMock(return_value=mock_backtest_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()
            session_id = result1["session_id"]
            await record_state(session_id)  # After design

            await service.check_and_trigger()
            await record_state(session_id)  # After training started

            await service.check_and_trigger()
            await record_state(session_id)  # After backtest started

            await service.check_and_trigger()
            await record_state(session_id)  # After assessment

        # Assert state transitions
        assert states_observed == [
            SessionPhase.DESIGNED,
            SessionPhase.TRAINING,
            SessionPhase.BACKTESTING,
            SessionPhase.COMPLETE,
        ]

    @pytest.mark.asyncio
    async def test_operation_ids_tracked_in_session(
        self,
        clean_db: AgentDatabase,
        test_strategies_dir: str,
    ):
        """Verify operation IDs are properly tracked in session."""
        # Arrange
        context_provider = MockContextProvider()
        mock_invoker = MockFullCycleInvoker(
            db=clean_db,
            strategies_dir=test_strategies_dir,
        )
        config = TriggerConfig(interval_seconds=0.1, enabled=True)

        mock_training_result = {"success": True, "operation_id": "op_train_track_001"}
        mock_backtest_result = {"success": True, "operation_id": "op_bt_track_001"}

        training_op = create_mock_operation(
            operation_id="op_train_track_001",
            status="COMPLETED",
            result_summary={
                "accuracy": 0.65,
                "final_loss": 0.3,
                "initial_loss": 1.0,
                "model_path": "/app/models/test.pt",
            },
        )

        backtest_op = create_mock_operation(
            operation_id="op_bt_track_001",
            status="COMPLETED",
            result_summary={
                "win_rate": 0.55,
                "max_drawdown": 0.15,
                "sharpe_ratio": 0.8,
            },
        )

        mock_ops_service = MagicMock()

        async def mock_get_operation(op_id: str):
            if "train" in op_id:
                return training_op
            elif "bt" in op_id:
                return backtest_op
            return None

        mock_ops_service.get_operation = AsyncMock(side_effect=mock_get_operation)

        service = TriggerService(
            config=config,
            db=clean_db,
            invoker=mock_invoker,
            context_provider=context_provider,
        )

        # Act
        with (
            patch(
                "ktrdr.agents.executor.start_training_via_api",
                new=AsyncMock(return_value=mock_training_result),
            ),
            patch(
                "ktrdr.agents.executor.start_backtest_via_api",
                new=AsyncMock(return_value=mock_backtest_result),
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
        ):
            result1 = await service.check_and_trigger()
            session_id = result1["session_id"]

            await service.check_and_trigger()  # Start training

            # Check training operation ID is tracked
            session = await clean_db.get_session(session_id)
            assert session.operation_id == "op_train_track_001"

            await service.check_and_trigger()  # Complete training, start backtest

            # Check backtest operation ID is tracked
            session = await clean_db.get_session(session_id)
            assert session.operation_id == "op_bt_track_001"
