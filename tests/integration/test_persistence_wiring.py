"""Integration tests for dependency wiring in persistence layer.

These tests verify that factory functions properly inject dependencies.
This catches "component works but isn't connected" bugs.
"""

import pytest

from ktrdr.api.repositories.operations_repository import OperationsRepository
from ktrdr.api.services.operations_service import (
    get_operations_service,
)


class TestOperationsServiceWiring:
    """Tests that verify OperationsService is properly wired with its dependencies."""

    def test_get_operations_service_returns_singleton(self):
        """get_operations_service should return the same instance."""
        service1 = get_operations_service()
        service2 = get_operations_service()
        assert service1 is service2

    def test_operations_service_has_repository(self):
        """OperationsService must have a repository injected for DB persistence.

        This is the test that would have caught the M1 wiring bug.
        """
        service = get_operations_service()

        # CRITICAL: This assertion catches the wiring bug
        assert service._repository is not None, (
            "OperationsService._repository is None! "
            "Operations will not persist to database. "
            "get_operations_service() must inject a repository."
        )

    def test_operations_service_repository_is_correct_type(self):
        """Repository should be an OperationsRepository instance."""
        service = get_operations_service()
        assert isinstance(
            service._repository, OperationsRepository
        ), f"Expected OperationsRepository, got {type(service._repository)}"

    def test_operations_service_repository_has_session_factory(self):
        """Repository must have a session factory for DB access."""
        service = get_operations_service()
        repo = service._repository

        assert repo is not None
        assert (
            repo._session_factory is not None
        ), "Repository has no session factory - cannot access database"


class TestStartupReconciliationWiring:
    """Tests that verify startup reconciliation uses real DB."""

    @pytest.mark.asyncio
    async def test_startup_reconciliation_queries_real_db(self):
        """Startup reconciliation must query real database, not just cache.

        This test imports and runs reconciliation to verify it can access DB.
        """
        import os

        # Skip if no DB configured (CI without DB)
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured")

        from ktrdr.api.database import get_session_factory
        from ktrdr.api.repositories.operations_repository import OperationsRepository
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        session_factory = get_session_factory()
        repository = OperationsRepository(session_factory)
        reconciliation = StartupReconciliation(repository)

        # Should not raise - verifies DB connectivity
        result = await reconciliation.reconcile()

        # Result should be a valid reconciliation result
        assert hasattr(result, "total_processed")
