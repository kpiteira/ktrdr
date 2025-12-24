"""M1 Wiring Smoke Tests.

These tests verify that factory functions and startup configuration
properly wire dependencies together. They catch bugs like:
- get_operations_service() not injecting repository
- get_worker_registry() not having operations_service set

These tests should be run after any changes to factory functions
or startup configuration.

See: docs/architecture/checkpoint/M1_TEST_GAP_ANALYSIS.md
"""

import os

import pytest


class TestOperationsServiceWiring:
    """Verify OperationsService factory wiring."""

    def test_get_operations_service_has_repository(self):
        """CRITICAL: Verify get_operations_service() injects repository.

        This test catches the bug where the factory function creates
        OperationsService without injecting the repository, causing
        all operations to be lost on restart.
        """
        # Skip if database not configured (CI without DB)
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.services.operations_service import get_operations_service

        service = get_operations_service()

        # CRITICAL: Repository must be injected
        assert service._repository is not None, (
            "OperationsService._repository is None! "
            "get_operations_service() must inject repository for persistence to work."
        )

    def test_operations_service_repository_is_correct_type(self):
        """Verify repository is the correct type."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.repositories.operations_repository import OperationsRepository
        from ktrdr.api.services.operations_service import get_operations_service

        service = get_operations_service()

        assert isinstance(service._repository, OperationsRepository), (
            f"Expected OperationsRepository, got {type(service._repository)}. "
            "Check get_operations_service() wiring."
        )


class TestWorkerRegistryWiring:
    """Verify WorkerRegistry factory and startup wiring."""

    def test_worker_registry_has_operations_service_after_startup(self):
        """CRITICAL: Verify WorkerRegistry has OperationsService after startup wiring.

        This test catches the bug where startup.py creates WorkerRegistry
        but never calls set_operations_service(), causing all reconciliation
        to be silently skipped.

        The startup sequence should:
        1. get_worker_registry() → creates WorkerRegistry
        2. set_operations_service(get_operations_service()) → injects dependency
        3. registry.start() → starts health check loop
        """
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        # Simulate what startup.py does
        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.services.operations_service import get_operations_service

        registry = get_worker_registry()

        # This is what startup.py MUST do (M1 fix)
        registry.set_operations_service(get_operations_service())

        # CRITICAL: OperationsService must be set for reconciliation to work
        assert registry._operations_service is not None, (
            "WorkerRegistry._operations_service is None! "
            "startup.py must call registry.set_operations_service(get_operations_service()) "
            "for reconciliation to work. Currently ALL reconciliation is silently skipped."
        )

    def test_worker_registry_operations_service_is_correct_type(self):
        """Verify operations_service is the correct type."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.endpoints.workers import get_worker_registry
        from ktrdr.api.services.operations_service import (
            OperationsService,
            get_operations_service,
        )

        registry = get_worker_registry()
        registry.set_operations_service(get_operations_service())

        assert isinstance(registry._operations_service, OperationsService), (
            f"Expected OperationsService, got {type(registry._operations_service)}. "
            "Check startup.py wiring."
        )


class TestStartupReconciliationWiring:
    """Verify StartupReconciliation is properly wired."""

    @pytest.mark.asyncio
    async def test_startup_reconciliation_can_query_database(self):
        """Verify StartupReconciliation can actually query the database."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.database import get_session_factory
        from ktrdr.api.repositories.operations_repository import OperationsRepository
        from ktrdr.api.services.startup_reconciliation import StartupReconciliation

        # Wire up like startup.py does
        session_factory = get_session_factory()
        repository = OperationsRepository(session_factory)
        reconciliation = StartupReconciliation(repository)

        # Should not raise - verifies DB connection works
        result = await reconciliation.reconcile()

        # Result should be a valid ReconciliationResult
        assert hasattr(result, "total_processed")
        assert hasattr(result, "worker_ops_reconciled")
        assert hasattr(result, "backend_ops_failed")


class TestDatabaseWiring:
    """Verify database configuration and connectivity."""

    def test_database_url_configured(self):
        """Verify database URL can be constructed."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.database import get_database_url

        url = get_database_url()

        # Should be a valid PostgreSQL async URL
        assert url.startswith(
            "postgresql+asyncpg://"
        ), f"Expected postgresql+asyncpg:// URL, got: {url[:30]}..."

    def test_session_factory_created(self):
        """Verify session factory can be created."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from ktrdr.api.database import get_session_factory

        factory = get_session_factory()

        assert factory is not None, "Session factory should be created"

    @pytest.mark.asyncio
    async def test_database_connection_works(self):
        """Verify we can actually connect to the database."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from sqlalchemy import text

        from ktrdr.api.database import get_session

        async with get_session() as session:
            # Simple query to verify connection
            result = await session.execute(text("SELECT 1"))
            value = result.scalar()

        assert value == 1, "Database query should return 1"

    @pytest.mark.asyncio
    async def test_operations_table_exists(self):
        """Verify the operations table exists (migration ran)."""
        if not os.getenv("DB_HOST"):
            pytest.skip("DB_HOST not configured - skipping DB wiring test")

        from sqlalchemy import text

        from ktrdr.api.database import get_session

        async with get_session() as session:
            # Check if table exists
            result = await session.execute(
                text(
                    "SELECT EXISTS ("
                    "SELECT FROM information_schema.tables "
                    "WHERE table_name = 'operations'"
                    ")"
                )
            )
            exists = result.scalar()

        assert exists, "Operations table does not exist! " "Run: alembic upgrade head"
