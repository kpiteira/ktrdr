"""Tests for AgentService wiring of container dispatch.

Task 5.2: AgentService creates AgentDispatchService and passes it to
the research worker when not using stub workers.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from ktrdr.api.models.workers import WorkerType


class TestAgentServiceDispatchWiring:
    """Tests for AgentService._get_worker() dispatch wiring."""

    def test_get_worker_creates_dispatch_when_not_stub(self):
        """_get_worker creates AgentDispatchService for non-stub mode."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(
            operations_service=mock_ops, checkpoint_service=MagicMock()
        )

        with (
            patch(
                "ktrdr.api.services.agent_service._use_stub_workers", return_value=False
            ),
            patch("ktrdr.api.endpoints.workers.get_worker_registry") as mock_get_reg,
        ):
            mock_registry = MagicMock()
            mock_get_reg.return_value = mock_registry

            worker = service._get_worker()

            # AgentDispatchService should be created with the registry
            assert worker._agent_dispatch is not None

    def test_get_worker_no_dispatch_when_stub(self):
        """_get_worker does NOT create AgentDispatchService for stub mode."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(
            operations_service=mock_ops, checkpoint_service=MagicMock()
        )

        with patch(
            "ktrdr.api.services.agent_service._use_stub_workers", return_value=True
        ):
            worker = service._get_worker()

            # No dispatch in stub mode — uses asyncio tasks
            assert worker._agent_dispatch is None

    def test_dispatch_uses_worker_registry(self):
        """AgentDispatchService receives the actual worker registry."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(
            operations_service=mock_ops, checkpoint_service=MagicMock()
        )

        with (
            patch(
                "ktrdr.api.services.agent_service._use_stub_workers", return_value=False
            ),
            patch("ktrdr.api.endpoints.workers.get_worker_registry") as mock_get_reg,
        ):
            mock_registry = MagicMock()
            mock_get_reg.return_value = mock_registry

            worker = service._get_worker()

            # The dispatch service should use the worker registry
            assert worker._agent_dispatch._registry is mock_registry


class TestWorkerStatusIncludesAgentTypes:
    """Tests that worker status includes agent worker types."""

    def test_worker_status_includes_agent_design(self):
        """_get_worker_status includes AGENT_DESIGN workers."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(
            operations_service=mock_ops, checkpoint_service=MagicMock()
        )

        with patch("ktrdr.api.endpoints.workers.get_worker_registry") as mock_get_reg:
            mock_registry = MagicMock()
            mock_registry.list_workers.return_value = []
            mock_get_reg.return_value = mock_registry

            service._get_worker_status()

            # Should query for agent types
            worker_types_queried = [
                call.kwargs.get("worker_type") or call.args[0]
                for call in mock_registry.list_workers.call_args_list
                if call.kwargs.get("worker_type") or (call.args and call.args[0])
            ]
            assert WorkerType.AGENT_DESIGN in worker_types_queried
            assert WorkerType.AGENT_ASSESSMENT in worker_types_queried

    def test_worker_status_shows_agent_counts(self):
        """_get_worker_status reports busy/total for agent types."""
        from ktrdr.api.services.agent_service import AgentService

        mock_ops = AsyncMock()
        service = AgentService(
            operations_service=mock_ops, checkpoint_service=MagicMock()
        )

        with patch("ktrdr.api.endpoints.workers.get_worker_registry") as mock_get_reg:
            mock_registry = MagicMock()

            def list_workers_impl(worker_type=None):
                if worker_type == WorkerType.AGENT_DESIGN:
                    worker = MagicMock()
                    worker.status = MagicMock()
                    worker.status.value = "available"
                    # Not busy
                    from ktrdr.api.models.workers import WorkerStatus

                    worker.status = WorkerStatus.AVAILABLE
                    return [worker]
                return []

            mock_registry.list_workers.side_effect = list_workers_impl
            mock_get_reg.return_value = mock_registry

            status = service._get_worker_status()

            assert "agent_design" in status
            assert status["agent_design"]["total"] == 1
            assert status["agent_design"]["busy"] == 0
