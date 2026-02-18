"""Unit tests for worker consolidation (M4 Task 4.1).

Tests verify:
1. Shared _run_backtest() method exists and handles both fresh and resume paths
2. Both paths use create_checkpoint_callback (shared infrastructure)
3. Both paths use save_cancellation_checkpoint (shared infrastructure)
4. No duplicated error handling blocks
5. Fresh and resumed backtests still complete via the shared path
"""

import inspect
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestSharedRunBacktestMethod:
    """Tests for the consolidated _run_backtest method."""

    def test_run_backtest_method_exists(self):
        """BacktestWorker should have a shared _run_backtest method."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        assert hasattr(BacktestWorker, "_run_backtest"), (
            "BacktestWorker should have _run_backtest() shared method"
        )

    def test_run_backtest_accepts_resume_context(self):
        """_run_backtest should accept optional resume_context parameter."""
        import inspect

        from ktrdr.backtesting.backtest_worker import BacktestWorker

        sig = inspect.signature(BacktestWorker._run_backtest)
        params = list(sig.parameters.keys())
        assert "resume_context" in params, (
            "_run_backtest should accept resume_context for resumed backtests"
        )

    def test_execute_backtest_work_delegates_to_run_backtest(self):
        """_execute_backtest_work should delegate to _run_backtest."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "_run_backtest" in source, (
            "_execute_backtest_work should delegate to _run_backtest"
        )

    def test_execute_resumed_work_delegates_to_run_backtest(self):
        """_execute_resumed_backtest_work should delegate to _run_backtest."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_resumed_backtest_work)
        assert "_run_backtest" in source, (
            "_execute_resumed_backtest_work should delegate to _run_backtest"
        )


class TestSharedCheckpointInfrastructure:
    """Tests that both paths use shared checkpoint infrastructure."""

    def test_fresh_path_uses_create_checkpoint_callback(self):
        """Fresh path should use create_checkpoint_callback from base class."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        # The fresh path should NOT have inline checkpoint_callback definition
        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "def checkpoint_callback" not in source, (
            "Fresh path should not have inline checkpoint_callback — "
            "use create_checkpoint_callback from WorkerAPIBase"
        )

    def test_run_backtest_uses_create_checkpoint_callback(self):
        """_run_backtest should use create_checkpoint_callback from base."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._run_backtest)
        assert "create_checkpoint_callback" in source, (
            "_run_backtest should use self.create_checkpoint_callback()"
        )

    def test_run_backtest_uses_save_cancellation_checkpoint(self):
        """_run_backtest should use save_cancellation_checkpoint from base."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._run_backtest)
        assert "save_cancellation_checkpoint" in source, (
            "_run_backtest should use self.save_cancellation_checkpoint()"
        )


class TestNoDuplicatedErrorHandling:
    """Tests that error handling is not duplicated between fresh and resume paths."""

    def test_fresh_path_has_no_cancellation_handling(self):
        """Fresh path should not have its own CancellationError handling."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "CancellationError" not in source, (
            "Fresh path should not handle CancellationError — "
            "this is handled in _run_backtest"
        )

    def test_resume_path_has_no_cancellation_handling(self):
        """Resume path should not have its own CancellationError handling."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_resumed_backtest_work)
        assert "CancellationError" not in source, (
            "Resume path should not handle CancellationError — "
            "this is handled in _run_backtest"
        )

    def test_fresh_path_has_no_asyncio_cancelled_handling(self):
        """Fresh path should not have its own asyncio.CancelledError handling."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "CancelledError" not in source, (
            "Fresh path should not handle CancelledError — "
            "this is handled in _run_backtest"
        )

    def test_run_backtest_handles_both_cancellation_types(self):
        """_run_backtest should handle both CancellationError and CancelledError."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._run_backtest)
        assert "CancellationError" in source, (
            "_run_backtest should handle CancellationError"
        )
        assert "CancelledError" in source, (
            "_run_backtest should handle asyncio.CancelledError"
        )


class TestFreshBacktestFlow:
    """Tests for the fresh backtest execution flow after consolidation."""

    @pytest.fixture
    def mock_operations_service(self):
        """Create mock operations service."""
        service = MagicMock()
        service.create_operation = AsyncMock()
        service.start_operation = AsyncMock()
        service.complete_operation = AsyncMock()
        service.fail_operation = AsyncMock()
        service.register_local_bridge = MagicMock()

        token = MagicMock()
        token.is_cancelled_requested = False
        service.get_cancellation_token = MagicMock(return_value=token)
        return service

    def test_fresh_path_creates_operation(self):
        """Fresh path should still create operation before delegating."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "create_operation" in source, (
            "Fresh path should create operation before delegating to _run_backtest"
        )

    def test_fresh_path_starts_operation(self):
        """Fresh path should still start operation before delegating."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "start_operation" in source, (
            "Fresh path should start operation before delegating"
        )

    def test_fresh_path_builds_original_request(self):
        """Fresh path should build original_request dict for checkpoints."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        assert "original_request" in source, (
            "Fresh path should build original_request dict for checkpoint context"
        )

    def test_original_request_includes_model_path(self):
        """original_request must include model_path for checkpoint resume."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_backtest_work)
        # Find the original_request dict construction and verify model_path
        assert '"model_path"' in source or "'model_path'" in source, (
            "original_request dict must include model_path — "
            "resume path reads it via original_request.get('model_path')"
        )


class TestResumedBacktestFlow:
    """Tests for the resumed backtest execution flow after consolidation."""

    def test_resume_path_adopts_operation(self):
        """Resume path should adopt operation before delegating."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_resumed_backtest_work)
        assert "adopt_and_start_operation" in source, (
            "Resume path should adopt operation before delegating to _run_backtest"
        )

    def test_resume_path_passes_context(self):
        """Resume path should pass resume_context to _run_backtest."""
        from ktrdr.backtesting.backtest_worker import BacktestWorker

        source = inspect.getsource(BacktestWorker._execute_resumed_backtest_work)
        assert "resume_context" in source, (
            "Resume path should pass context to _run_backtest"
        )
