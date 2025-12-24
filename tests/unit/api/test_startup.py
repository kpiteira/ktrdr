"""Unit tests for API startup lifecycle.

Tests the lifespan context manager that manages service lifecycles including:
- Startup reconciliation (M1)
- Orphan detector (M2)
- Worker registry
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLifespanOrphanDetector:
    """Test orphan detector integration in lifespan (Task 2.2)."""

    @pytest.mark.asyncio
    async def test_orphan_detector_started_after_reconciliation(self):
        """Orphan detector should be started after startup reconciliation completes."""
        from ktrdr.api.startup import lifespan

        # Track call order
        call_order = []

        mock_reconciliation = AsyncMock(
            side_effect=lambda: call_order.append("reconciliation")
        )

        mock_orphan_detector_instance = MagicMock()
        mock_orphan_detector_instance.start = AsyncMock(
            side_effect=lambda: call_order.append("orphan_detector_start")
        )
        mock_orphan_detector_instance.stop = AsyncMock()

        mock_orphan_detector_class = MagicMock(
            return_value=mock_orphan_detector_instance
        )

        mock_registry = MagicMock()
        mock_registry.start = AsyncMock()
        mock_registry.stop = AsyncMock()
        mock_registry.set_operations_service = MagicMock()

        mock_app = MagicMock()

        with (
            patch("ktrdr.api.startup._run_startup_reconciliation", mock_reconciliation),
            patch(
                "ktrdr.api.startup.OrphanOperationDetector",
                mock_orphan_detector_class,
            ),
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_registry,
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=MagicMock(),
            ),
            patch(
                "ktrdr.api.endpoints.training.get_training_service",
                new_callable=AsyncMock,
            ),
            patch("ktrdr.api.database.close_database", AsyncMock()),
        ):
            async with lifespan(mock_app):
                # Inside lifespan, verify start was called
                mock_orphan_detector_instance.start.assert_called_once()

        # Verify order: reconciliation before orphan detector
        assert call_order.index("reconciliation") < call_order.index(
            "orphan_detector_start"
        ), "Orphan detector should start after reconciliation"

    @pytest.mark.asyncio
    async def test_orphan_detector_stopped_on_shutdown(self):
        """Orphan detector should be stopped on shutdown."""
        from ktrdr.api.startup import lifespan

        mock_orphan_detector_instance = MagicMock()
        mock_orphan_detector_instance.start = AsyncMock()
        mock_orphan_detector_instance.stop = AsyncMock()

        mock_orphan_detector_class = MagicMock(
            return_value=mock_orphan_detector_instance
        )

        mock_registry = MagicMock()
        mock_registry.start = AsyncMock()
        mock_registry.stop = AsyncMock()
        mock_registry.set_operations_service = MagicMock()

        mock_app = MagicMock()

        with (
            patch("ktrdr.api.startup._run_startup_reconciliation", AsyncMock()),
            patch(
                "ktrdr.api.startup.OrphanOperationDetector",
                mock_orphan_detector_class,
            ),
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_registry,
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=MagicMock(),
            ),
            patch(
                "ktrdr.api.endpoints.training.get_training_service",
                new_callable=AsyncMock,
            ),
            patch("ktrdr.api.database.close_database", AsyncMock()),
        ):
            async with lifespan(mock_app):
                pass  # Enter and exit lifespan

            # After exiting lifespan, stop should have been called
            mock_orphan_detector_instance.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_orphan_detector_receives_correct_dependencies(self):
        """Orphan detector should receive operations service and worker registry."""
        from ktrdr.api.startup import lifespan

        mock_ops_service = MagicMock()
        mock_registry = MagicMock()
        mock_registry.start = AsyncMock()
        mock_registry.stop = AsyncMock()
        mock_registry.set_operations_service = MagicMock()

        mock_orphan_detector_instance = MagicMock()
        mock_orphan_detector_instance.start = AsyncMock()
        mock_orphan_detector_instance.stop = AsyncMock()

        mock_orphan_detector_class = MagicMock(
            return_value=mock_orphan_detector_instance
        )

        mock_app = MagicMock()

        with (
            patch("ktrdr.api.startup._run_startup_reconciliation", AsyncMock()),
            patch(
                "ktrdr.api.startup.OrphanOperationDetector",
                mock_orphan_detector_class,
            ),
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_registry,
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=mock_ops_service,
            ),
            patch(
                "ktrdr.api.endpoints.training.get_training_service",
                new_callable=AsyncMock,
            ),
            patch("ktrdr.api.database.close_database", AsyncMock()),
        ):
            async with lifespan(mock_app):
                pass

        # Verify OrphanOperationDetector was created with correct dependencies
        mock_orphan_detector_class.assert_called_once_with(
            operations_service=mock_ops_service,
            worker_registry=mock_registry,
        )

    @pytest.mark.asyncio
    async def test_orphan_detector_start_logged(self):
        """Orphan detector start should be logged."""
        from ktrdr.api.startup import lifespan

        mock_orphan_detector_instance = MagicMock()
        mock_orphan_detector_instance.start = AsyncMock()
        mock_orphan_detector_instance.stop = AsyncMock()

        mock_orphan_detector_class = MagicMock(
            return_value=mock_orphan_detector_instance
        )

        mock_registry = MagicMock()
        mock_registry.start = AsyncMock()
        mock_registry.stop = AsyncMock()
        mock_registry.set_operations_service = MagicMock()

        mock_app = MagicMock()

        with (
            patch("ktrdr.api.startup._run_startup_reconciliation", AsyncMock()),
            patch(
                "ktrdr.api.startup.OrphanOperationDetector",
                mock_orphan_detector_class,
            ),
            patch(
                "ktrdr.api.endpoints.workers.get_worker_registry",
                return_value=mock_registry,
            ),
            patch(
                "ktrdr.api.services.operations_service.get_operations_service",
                return_value=MagicMock(),
            ),
            patch(
                "ktrdr.api.endpoints.training.get_training_service",
                new_callable=AsyncMock,
            ),
            patch("ktrdr.api.database.close_database", AsyncMock()),
            patch("ktrdr.api.startup.logger") as mock_logger,
        ):
            async with lifespan(mock_app):
                pass

            # Verify "Orphan detector started" was logged
            log_messages = [str(call) for call in mock_logger.info.call_args_list]
            assert any(
                "Orphan detector started" in msg for msg in log_messages
            ), f"Expected 'Orphan detector started' in logs, got: {log_messages}"


class TestGetOrphanDetector:
    """Test get_orphan_detector() function."""

    def test_get_orphan_detector_raises_before_init(self):
        """get_orphan_detector should raise RuntimeError before lifespan starts."""
        import ktrdr.api.startup as startup_module

        # Reset the module-level singleton
        original_value = startup_module._orphan_detector
        startup_module._orphan_detector = None

        try:
            with pytest.raises(RuntimeError) as exc_info:
                startup_module.get_orphan_detector()

            assert "OrphanOperationDetector not initialized" in str(exc_info.value)
        finally:
            # Restore original value
            startup_module._orphan_detector = original_value

    def test_get_orphan_detector_returns_instance_after_init(self):
        """get_orphan_detector should return the detector after lifespan starts."""
        import ktrdr.api.startup as startup_module

        # Set up a mock detector
        mock_detector = MagicMock()
        original_value = startup_module._orphan_detector
        startup_module._orphan_detector = mock_detector

        try:
            result = startup_module.get_orphan_detector()
            assert result is mock_detector
        finally:
            # Restore original value
            startup_module._orphan_detector = original_value
