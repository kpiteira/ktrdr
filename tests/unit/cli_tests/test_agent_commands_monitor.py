"""Tests for agent command monitoring with nested child progress."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_progress():
    """Create a mock Rich Progress that's a proper context manager."""
    progress = MagicMock()
    progress.__enter__ = MagicMock(return_value=progress)
    progress.__exit__ = MagicMock(return_value=None)
    progress.add_task = MagicMock(return_value="task_id")
    progress.update = MagicMock()
    progress.remove_task = MagicMock()
    return progress


@pytest.fixture
def mock_console():
    """Create a mock console."""
    return MagicMock()


class TestNestedChildProgress:
    """Tests for nested child progress display in agent monitoring."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock AsyncCLIClient."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    def parent_op_training(self):
        """Parent operation in training phase with training_op_id."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "running",
                "progress": {"percentage": 20.0, "current_step": "Training model..."},
                "metadata": {
                    "parameters": {
                        "phase": "training",
                        "training_op_id": "op_training_456",
                    }
                },
            },
        }

    @pytest.fixture
    def parent_op_backtesting(self):
        """Parent operation in backtesting phase with backtest_op_id."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "running",
                "progress": {"percentage": 65.0, "current_step": "Running backtest..."},
                "metadata": {
                    "parameters": {
                        "phase": "backtesting",
                        "backtest_op_id": "op_backtest_789",
                    }
                },
            },
        }

    @pytest.fixture
    def parent_op_designing(self):
        """Parent operation in designing phase - no child op."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "running",
                "progress": {
                    "percentage": 5.0,
                    "current_step": "Designing strategy...",
                },
                "metadata": {"parameters": {"phase": "designing"}},
            },
        }

    @pytest.fixture
    def child_op_training(self):
        """Child training operation with epoch progress."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_training_456",
                "status": "running",
                "progress": {
                    "percentage": 45.0,
                    "current_step": "Epoch 45/100",
                },
            },
        }

    @pytest.fixture
    def child_op_backtest(self):
        """Child backtest operation with bar progress."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_backtest_789",
                "status": "running",
                "progress": {
                    "percentage": 30.0,
                    "current_step": "Bar 300/1000",
                },
            },
        }

    @pytest.fixture
    def parent_op_completed(self):
        """Parent operation completed."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "completed",
                "progress": {"percentage": 100.0, "current_step": "Complete"},
                "result": {"strategy_name": "test_strategy", "verdict": "promising"},
            },
        }

    @pytest.mark.asyncio
    async def test_child_task_added_for_training_op_id(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_training,
        child_op_training,
        parent_op_completed,
    ):
        """Child task is added when training_op_id is present."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        # Sequence: training phase with child -> completed
        mock_client.get = AsyncMock(
            side_effect=[
                parent_op_training,
                child_op_training,
                parent_op_completed,
            ]
        )

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    await _monitor_agent_cycle("op_parent_123")

        # Should have polled child operation
        calls = mock_client.get.call_args_list
        child_poll_calls = [c for c in calls if "op_training_456" in str(c)]
        assert len(child_poll_calls) >= 1, "Should poll child training operation"

    @pytest.mark.asyncio
    async def test_child_task_added_for_backtest_op_id(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_backtesting,
        child_op_backtest,
        parent_op_completed,
    ):
        """Child task is added when backtest_op_id is present."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        # Sequence: backtesting phase with child -> completed
        mock_client.get = AsyncMock(
            side_effect=[
                parent_op_backtesting,
                child_op_backtest,
                parent_op_completed,
            ]
        )

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    await _monitor_agent_cycle("op_parent_123")

        # Should have polled child operation
        calls = mock_client.get.call_args_list
        child_poll_calls = [c for c in calls if "op_backtest_789" in str(c)]
        assert len(child_poll_calls) >= 1, "Should poll child backtest operation"

    @pytest.mark.asyncio
    async def test_no_child_task_during_design_phase(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_designing,
        parent_op_completed,
    ):
        """No child task during design phase (no child_op_id)."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        # Sequence: designing phase -> completed
        mock_client.get = AsyncMock(
            side_effect=[
                parent_op_designing,
                parent_op_completed,
            ]
        )

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    await _monitor_agent_cycle("op_parent_123")

        # Should only poll parent, not any child
        calls = mock_client.get.call_args_list
        assert all(
            "/operations/op_parent_123" in str(c) for c in calls
        ), "Should only poll parent operation during design phase"

    @pytest.mark.asyncio
    async def test_child_task_removed_when_phase_changes(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_training,
        child_op_training,
        parent_op_completed,
    ):
        """Child task is removed when transitioning to phase without child op."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        # Parent in assessing phase (no child op)
        parent_op_assessing = {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "running",
                "progress": {
                    "percentage": 90.0,
                    "current_step": "Assessing results...",
                },
                "metadata": {"parameters": {"phase": "assessing"}},
            },
        }

        # Sequence: training with child -> assessing (no child) -> completed
        mock_client.get = AsyncMock(
            side_effect=[
                parent_op_training,
                child_op_training,
                parent_op_assessing,
                parent_op_completed,
            ]
        )

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    result = await _monitor_agent_cycle("op_parent_123")

        # Should complete successfully (task removed without error)
        assert result["status"] == "completed"
        # Remove task should have been called when child_op_id cleared
        assert (
            mock_progress.remove_task.called
        ), "Should remove child task when phase changes"

    @pytest.mark.asyncio
    async def test_missing_child_operation_handled_gracefully(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_training,
        parent_op_completed,
    ):
        """Missing child operation doesn't crash the monitor."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        call_count = 0

        async def mock_request(path):
            nonlocal call_count
            call_count += 1
            if "op_training_456" in path:
                # Child not found
                raise Exception("Not found")
            elif call_count == 1:
                return parent_op_training
            else:
                return parent_op_completed

        mock_client.get = AsyncMock(side_effect=mock_request)

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    # Should not raise
                    result = await _monitor_agent_cycle("op_parent_123")

        assert result is not None, "Should complete without crashing"

    @pytest.mark.asyncio
    async def test_child_progress_displayed_correctly(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_training,
        child_op_training,
        parent_op_completed,
    ):
        """Child progress is extracted and displayed via progress.update."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle

        mock_client.get = AsyncMock(
            side_effect=[
                parent_op_training,
                child_op_training,
                parent_op_completed,
            ]
        )

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    await _monitor_agent_cycle("op_parent_123")

        # Verify we polled the child operation at least once
        calls = mock_client.get.call_args_list
        child_calls = [c for c in calls if "op_training_456" in str(c)]
        assert len(child_calls) >= 1

        # Verify progress.update was called with child progress info
        update_calls = mock_progress.update.call_args_list
        # Should have at least one update with child step info
        child_updates = [c for c in update_calls if "Epoch" in str(c) or "└─" in str(c)]
        assert len(child_updates) >= 1, "Should update with child progress info"


class TestErrorHandlingAndPolish:
    """Tests for Task 9.4: Error handling, retry, and cancellation summary polish."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock AsyncCLIClient."""
        client = AsyncMock()
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        return client

    @pytest.fixture
    def parent_op_running(self):
        """Parent operation running."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "running",
                "progress": {"percentage": 20.0, "current_step": "Training model..."},
                "metadata": {"parameters": {"phase": "training"}},
            },
        }

    @pytest.fixture
    def parent_op_completed(self):
        """Parent operation completed."""
        return {
            "success": True,
            "data": {
                "operation_id": "op_parent_123",
                "status": "completed",
                "progress": {"percentage": 100.0, "current_step": "Complete"},
                "result": {"strategy_name": "test_strategy", "verdict": "promising"},
            },
        }

    @pytest.mark.asyncio
    async def test_connection_error_triggers_retry_with_backoff(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_running,
        parent_op_completed,
    ):
        """Connection error triggers retry with exponential backoff."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle
        from ktrdr.cli.client import ConnectionError

        call_count = 0

        async def mock_request(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return parent_op_running
            elif call_count <= 3:
                # Simulate connection error for 2 attempts
                raise ConnectionError(
                    "Could not connect to API at http://localhost:8000",
                )
            else:
                return parent_op_completed

        mock_client.get = AsyncMock(side_effect=mock_request)

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
                        result = await _monitor_agent_cycle("op_parent_123")

        # Should have completed successfully after retries
        assert result["status"] == "completed"
        # Should have slept during retries (exponential backoff)
        # At least 2 retry sleeps + normal poll sleeps
        assert mock_sleep.call_count >= 2

    @pytest.mark.asyncio
    async def test_connection_lost_message_shown_during_retry(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_running,
        parent_op_completed,
    ):
        """'Connection lost, retrying...' message shown in progress bar during retry."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle
        from ktrdr.cli.client import ConnectionError

        call_count = 0

        async def mock_request(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return parent_op_running
            elif call_count == 2:
                raise ConnectionError(
                    "Could not connect to API at http://localhost:8000",
                )
            else:
                return parent_op_completed

        mock_client.get = AsyncMock(side_effect=mock_request)

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        await _monitor_agent_cycle("op_parent_123")

        # Check progress.update was called with "Connection lost" message
        update_calls = mock_progress.update.call_args_list
        connection_lost_updates = [
            c for c in update_calls if "Connection lost" in str(c)
        ]
        assert (
            len(connection_lost_updates) >= 1
        ), "Should show 'Connection lost' in progress"

    @pytest.mark.asyncio
    async def test_404_response_exits_with_operation_lost_message(
        self, mock_client, mock_progress, mock_console, parent_op_running
    ):
        """404 response exits with 'operation not found' message."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle
        from ktrdr.cli.client import APIError

        call_count = 0

        async def mock_request(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return parent_op_running
            else:
                # Operation disappeared (backend restart)
                raise APIError(
                    "Not Found",
                    status_code=404,
                )

        mock_client.get = AsyncMock(side_effect=mock_request)

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    with patch("asyncio.sleep", new_callable=AsyncMock):
                        result = await _monitor_agent_cycle("op_parent_123")

        # Should return with "lost" status
        assert result.get("status") == "lost"
        # Should have printed operation lost message
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        assert any(
            "not found" in str(c).lower() for c in print_calls
        ), "Should print 'operation not found' message"

    @pytest.mark.asyncio
    async def test_retry_delay_resets_after_successful_request(
        self,
        mock_client,
        mock_progress,
        mock_console,
        parent_op_running,
        parent_op_completed,
    ):
        """Retry delay resets to 1s after a successful request."""
        from ktrdr.cli.agent_commands import _monitor_agent_cycle
        from ktrdr.cli.client import ConnectionError

        call_count = 0
        sleep_durations = []

        async def mock_request(path):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return parent_op_running
            elif call_count == 2:
                # First connection error
                raise ConnectionError(
                    "Could not connect to API at http://localhost:8000"
                )
            elif call_count == 3:
                # Second connection error (should use 2s delay)
                raise ConnectionError(
                    "Could not connect to API at http://localhost:8000"
                )
            elif call_count == 4:
                # Success - delay should reset
                return parent_op_running
            elif call_count == 5:
                # Another error - should start from 1s again
                raise ConnectionError(
                    "Could not connect to API at http://localhost:8000"
                )
            else:
                return parent_op_completed

        async def mock_sleep(duration):
            sleep_durations.append(duration)

        mock_client.get = AsyncMock(side_effect=mock_request)

        with patch("ktrdr.cli.agent_commands.AsyncCLIClient", return_value=mock_client):
            with patch("ktrdr.cli.agent_commands.console", mock_console):
                with patch("rich.progress.Progress", return_value=mock_progress):
                    with patch("asyncio.sleep", side_effect=mock_sleep):
                        await _monitor_agent_cycle("op_parent_123")

        # Should have retry delays of ~1s, ~2s, then reset to ~1s
        # Filter out the normal 0.5s poll sleeps
        retry_sleeps = [d for d in sleep_durations if d >= 1.0]
        assert len(retry_sleeps) >= 3
        # First retry should be 1s
        assert retry_sleeps[0] == 1.0
        # Second retry should be 2s (exponential)
        assert retry_sleeps[1] == 2.0
        # After success, third retry should reset to 1s
        assert retry_sleeps[2] == 1.0

    def test_cancellation_summary_includes_child_state(self, mock_console):
        """Cancellation summary includes child operation state when available."""
        from ktrdr.cli.agent_commands import _show_completion_summary

        # Cancelled operation data
        op_data = {
            "status": "cancelled",
            "metadata": {
                "parameters": {
                    "phase": "training",
                    "training_op_id": "op_training_456",
                }
            },
        }

        with patch("ktrdr.cli.agent_commands.console", mock_console):
            _show_completion_summary(op_data, child_state="Epoch 67/100")

        # Should have printed cancellation info with phase and child state
        print_calls = [str(c) for c in mock_console.print.call_args_list]

        # Should show cancelled message
        assert any(
            "cancelled" in str(c).lower() for c in print_calls
        ), "Should print cancelled message"

        # Should show phase
        assert any(
            "training" in str(c).lower() for c in print_calls
        ), "Should print phase"

        # Should show child state (epoch info)
        assert any(
            "epoch" in str(c).lower() or "67" in str(c) for c in print_calls
        ), "Should print child state (epoch info)"

    def test_cancellation_summary_without_child_state(self, mock_console):
        """Cancellation summary works without child state."""
        from ktrdr.cli.agent_commands import _show_completion_summary

        # Cancelled operation data (during design phase - no child)
        op_data = {
            "status": "cancelled",
            "metadata": {
                "parameters": {
                    "phase": "designing",
                }
            },
        }

        with patch("ktrdr.cli.agent_commands.console", mock_console):
            _show_completion_summary(op_data)  # No child_state arg

        # Should have printed cancellation info
        print_calls = [str(c) for c in mock_console.print.call_args_list]

        # Should show cancelled message
        assert any(
            "cancelled" in str(c).lower() for c in print_calls
        ), "Should print cancelled message"

        # Should show phase
        assert any(
            "designing" in str(c).lower() for c in print_calls
        ), "Should print phase"
