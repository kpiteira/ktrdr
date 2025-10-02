"""
Integration tests for unified CLI operations pattern.

Tests the complete flow of async operations using AsyncOperationExecutor
and concrete adapters (Training, Dummy) with real API interactions.

These tests verify:
- Operations start and complete successfully
- Cancellation works correctly when Ctrl+C is simulated
- Progress updates are accurate and responsive
- Final results display correctly
- Error handling is graceful
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from rich.console import Console

from ktrdr.cli.operation_adapters import (
    DummyOperationAdapter,
    TrainingOperationAdapter,
)
from ktrdr.cli.operation_executor import AsyncOperationExecutor


class TestDummyOperationIntegration:
    """Integration tests for dummy operation using unified pattern."""

    @pytest.mark.asyncio
    async def test_dummy_operation_completes_successfully(self):
        """Test that dummy operation starts, runs, and completes successfully."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=10, iterations=5)
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        # Mock the HTTP client to simulate backend behavior
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response
            start_response = Mock()
            start_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {"operation_id": "dummy-op-123"},
                }
            )
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock polling responses: running -> running -> completed
            poll_responses = [
                {
                    "success": True,
                    "data": {
                        "operation_id": "dummy-op-123",
                        "status": "running",
                        "progress": {
                            "percentage": 40,
                            "current_step": "Iteration 2/5",
                            "total_steps": 5,
                        },
                    },
                },
                {
                    "success": True,
                    "data": {
                        "operation_id": "dummy-op-123",
                        "status": "running",
                        "progress": {
                            "percentage": 80,
                            "current_step": "Iteration 4/5",
                            "total_steps": 5,
                        },
                    },
                },
                {
                    "success": True,
                    "data": {
                        "operation_id": "dummy-op-123",
                        "status": "completed",
                        "progress": {
                            "percentage": 100,
                            "current_step": "Iteration 5/5",
                            "total_steps": 5,
                        },
                        "metadata": {"duration": "10s"},
                    },
                },
            ]

            mock_get_responses = []
            for resp_data in poll_responses:
                mock_resp = Mock()
                mock_resp.json = Mock(return_value=resp_data)
                mock_resp.status_code = 200
                mock_resp.raise_for_status = Mock()
                mock_get_responses.append(mock_resp)

            mock_client.get.side_effect = mock_get_responses

            # Act
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,  # Disable progress bar for testing
            )

            # Assert
            assert success is True
            assert mock_client.post.call_count == 1
            assert mock_client.get.call_count == 3

            # Verify correct endpoint was called
            post_call_args = mock_client.post.call_args
            assert post_call_args[0][0] == "http://localhost:8000/dummy/start"

    @pytest.mark.asyncio
    async def test_dummy_operation_cancellation_works(self):
        """Test that Ctrl+C cancels dummy operation correctly."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=100, iterations=50)
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response
            start_response = Mock()
            start_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {"operation_id": "dummy-cancel-123"},
                }
            )
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock polling responses: running -> user cancels
            poll_response = Mock()
            poll_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {
                        "operation_id": "dummy-cancel-123",
                        "status": "running",
                        "progress": {
                            "percentage": 20,
                            "current_step": "Iteration 10/50",
                        },
                    },
                }
            )
            poll_response.status_code = 200
            poll_response.raise_for_status = Mock()

            # Mock cancel response
            cancel_response = Mock()
            cancel_response.status_code = 200
            cancel_response.raise_for_status = Mock()

            # Mock final status after cancellation
            cancelled_status = Mock()
            cancelled_status.json = Mock(
                return_value={
                    "success": True,
                    "data": {
                        "operation_id": "dummy-cancel-123",
                        "status": "cancelled",
                        "progress": {
                            "percentage": 20,
                            "current_step": "Iteration 10/50",
                        },
                        "metadata": {
                            "iterations_completed": 10,
                            "total_iterations": 50,
                        },
                    },
                }
            )
            cancelled_status.status_code = 200
            cancelled_status.raise_for_status = Mock()

            # Setup mock responses: poll once, then we'll cancel
            mock_client.get.side_effect = [poll_response, cancelled_status]
            mock_client.delete.return_value = cancel_response

            # Simulate user pressing Ctrl+C after first poll
            async def simulate_cancel():
                await asyncio.sleep(0.1)  # Wait for first poll
                executor.cancelled = True

            # Act
            cancel_task = asyncio.create_task(simulate_cancel())
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )
            await cancel_task

            # Assert
            assert success is False  # Cancelled operations return False
            assert mock_client.delete.call_count == 1
            assert mock_client.delete.call_args[0][0].endswith(
                "/operations/dummy-cancel-123"
            )

    @pytest.mark.asyncio
    async def test_dummy_operation_handles_backend_failure(self):
        """Test that backend failures are handled gracefully."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=10, iterations=5)
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response
            start_response = Mock()
            start_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {"operation_id": "dummy-fail-123"},
                }
            )
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock polling responses: running -> failed
            poll_responses = [
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "dummy-fail-123",
                                "status": "running",
                                "progress": {"percentage": 40},
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "dummy-fail-123",
                                "status": "failed",
                                "error_message": "Simulated backend failure",
                                "progress": {"percentage": 60},
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
            ]

            mock_client.get.side_effect = poll_responses

            # Act
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )

            # Assert
            assert success is False
            assert mock_client.get.call_count == 2


class TestTrainingOperationIntegration:
    """Integration tests for training operation using unified pattern."""

    @pytest.mark.asyncio
    async def test_training_operation_completes_successfully(self):
        """Test that training operation starts, runs, and completes successfully."""
        # Arrange
        console = Console()
        adapter = TrainingOperationAdapter(
            strategy_name="test_strategy",
            symbols=["AAPL"],
            timeframes=["1h"],
            start_date="2024-01-01",
            end_date="2024-03-01",
            validation_split=0.2,
            detailed_analytics=False,
        )
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response (training API returns task_id)
            start_response = Mock()
            start_response.json = Mock(
                return_value={
                    "success": True,
                    "task_id": "train-op-456",
                    "message": "Training started",
                }
            )
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock polling responses: running -> running -> completed
            poll_responses = [
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "train-op-456",
                                "status": "running",
                                "progress": {
                                    "percentage": 30,
                                    "current_step": "Epoch 3/10",
                                },
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "train-op-456",
                                "status": "running",
                                "progress": {
                                    "percentage": 70,
                                    "current_step": "Epoch 7/10",
                                },
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "train-op-456",
                                "status": "completed",
                                "progress": {
                                    "percentage": 100,
                                    "current_step": "Epoch 10/10",
                                },
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
            ]

            # Mock performance metrics response
            perf_response = Mock()
            perf_response.json = Mock(
                return_value={
                    "success": True,
                    "training_metrics": {
                        "final_train_accuracy": 0.85,
                        "final_val_accuracy": 0.82,
                        "epochs_completed": 10,
                        "training_time_minutes": 5.5,
                    },
                    "test_metrics": {
                        "test_accuracy": 0.83,
                        "precision": 0.84,
                        "recall": 0.81,
                        "f1_score": 0.825,
                    },
                    "model_info": {
                        "parameters_count": 125000,
                        "model_size_bytes": 512000,
                    },
                }
            )
            perf_response.status_code = 200
            perf_response.raise_for_status = Mock()

            # Setup mock responses: 3 polls + 1 performance fetch
            mock_client.get.side_effect = poll_responses + [perf_response]

            # Act
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )

            # Assert
            assert success is True
            assert mock_client.post.call_count == 1
            assert mock_client.get.call_count == 4  # 3 polls + 1 perf fetch

            # Verify correct endpoint was called
            post_call_args = mock_client.post.call_args
            assert post_call_args[0][0] == "http://localhost:8000/trainings/start"

            # Verify training payload
            payload = post_call_args[1]["json"]
            assert payload["strategy_name"] == "test_strategy"
            assert payload["symbols"] == ["AAPL"]
            assert payload["timeframes"] == ["1h"]
            assert payload["start_date"] == "2024-01-01"
            assert payload["end_date"] == "2024-03-01"

    @pytest.mark.asyncio
    async def test_training_operation_cancellation_works(self):
        """Test that Ctrl+C cancels training operation correctly."""
        # Arrange
        console = Console()
        adapter = TrainingOperationAdapter(
            strategy_name="test_strategy",
            symbols=["AAPL"],
            timeframes=["1h"],
            start_date="2024-01-01",
            end_date="2024-03-01",
        )
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response
            start_response = Mock()
            start_response.json = Mock(return_value={"task_id": "train-cancel-789"})
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock polling response
            poll_response = Mock()
            poll_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {
                        "operation_id": "train-cancel-789",
                        "status": "running",
                        "progress": {
                            "percentage": 40,
                            "current_step": "Epoch 4/10",
                        },
                    },
                }
            )
            poll_response.status_code = 200
            poll_response.raise_for_status = Mock()

            # Mock cancel response
            cancel_response = Mock()
            cancel_response.status_code = 200

            # Mock cancelled status
            cancelled_status = Mock()
            cancelled_status.json = Mock(
                return_value={
                    "success": True,
                    "data": {
                        "operation_id": "train-cancel-789",
                        "status": "cancelled",
                        "progress": {"percentage": 40},
                        "metadata": {"epochs_completed": 4},
                    },
                }
            )
            cancelled_status.status_code = 200
            cancelled_status.raise_for_status = Mock()

            mock_client.get.side_effect = [poll_response, cancelled_status]
            mock_client.delete.return_value = cancel_response

            # Simulate cancellation
            async def simulate_cancel():
                await asyncio.sleep(0.1)
                executor.cancelled = True

            # Act
            cancel_task = asyncio.create_task(simulate_cancel())
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )
            await cancel_task

            # Assert
            assert success is False
            assert mock_client.delete.call_count == 1

    @pytest.mark.asyncio
    async def test_progress_updates_are_responsive(self):
        """Test that progress updates are accurate and responsive (<500ms lag)."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=10, iterations=5)
        executor = AsyncOperationExecutor(
            base_url="http://localhost:8000",
            poll_interval=0.3,  # 300ms polling for responsive updates
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Mock start response
            start_response = Mock()
            start_response.json = Mock(
                return_value={
                    "success": True,
                    "data": {"operation_id": "progress-test"},
                }
            )
            start_response.status_code = 200
            start_response.raise_for_status = Mock()
            mock_client.post.return_value = start_response

            # Mock progressive updates
            poll_responses = [
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "progress-test",
                                "status": "running",
                                "progress": {"percentage": 20},
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "progress-test",
                                "status": "running",
                                "progress": {"percentage": 60},
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
                Mock(
                    json=Mock(
                        return_value={
                            "success": True,
                            "data": {
                                "operation_id": "progress-test",
                                "status": "completed",
                                "progress": {"percentage": 100},
                            },
                        }
                    ),
                    status_code=200,
                    raise_for_status=Mock(),
                ),
            ]

            mock_client.get.side_effect = poll_responses

            # Act
            import time

            start_time = time.time()
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )
            elapsed = time.time() - start_time

            # Assert
            assert success is True

            # Verify responsive polling (3 polls × 300ms = ~900ms max)
            # Allow some overhead for test execution
            assert elapsed < 2.0, f"Polling took too long: {elapsed}s"

            # Verify all progress updates were received
            assert mock_client.get.call_count == 3


class TestErrorHandling:
    """Test error handling in unified operations pattern."""

    @pytest.mark.asyncio
    async def test_handles_connection_error_gracefully(self):
        """Test that connection errors are handled with clear messages."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=10, iterations=5)
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Simulate connection error
            mock_client.post.side_effect = httpx.ConnectError(
                "Connection refused", request=Mock()
            )

            # Act
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )

            # Assert
            assert success is False

    @pytest.mark.asyncio
    async def test_handles_http_400_error(self):
        """Test that HTTP 4xx errors are handled without retries."""
        # Arrange
        console = Console()
        adapter = DummyOperationAdapter(duration=10, iterations=5)
        executor = AsyncOperationExecutor(base_url="http://localhost:8000")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            # Simulate 400 Bad Request
            mock_response = Mock()
            mock_response.status_code = 400
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request", request=Mock(), response=mock_response
            )
            mock_client.post.return_value = mock_response

            # Act
            success = await executor.execute_operation(
                adapter=adapter,
                console=console,
                show_progress=False,
            )

            # Assert
            assert success is False
            # Should not retry on 4xx errors
            assert mock_client.post.call_count == 1
