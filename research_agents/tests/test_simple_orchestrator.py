"""
Simple Tests for Research Orchestrator

Basic tests to verify core functionality works without complex mocking.
"""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from research_agents.services.research_orchestrator import (
    ExperimentConfig,
    ExperimentStatus,
    ExperimentType,
    ResearchOrchestrator,
    ResearchOrchestratorError,
)


class TestBasicOrchestrator:
    """Test basic orchestrator functionality"""

    def test_orchestrator_creation(self):
        """Test creating orchestrator instance"""
        mock_db = AsyncMock()
        orchestrator = ResearchOrchestrator(
            db_service=mock_db,
            max_concurrent_experiments=2,
            default_timeout_minutes=120,
        )

        assert orchestrator.db_service == mock_db
        assert orchestrator.max_concurrent_experiments == 2
        assert orchestrator.default_timeout_minutes == 120
        assert not orchestrator._is_initialized
        assert len(orchestrator._running_experiments) == 0

    def test_experiment_config_creation(self):
        """Test creating experiment configuration"""
        config = ExperimentConfig(
            experiment_name="Test Strategy",
            hypothesis="Test hypothesis",
            experiment_type=ExperimentType.NEURO_FUZZY_STRATEGY,
            parameters={"param1": "value1"},
            data_requirements={"symbol": "EURUSD"},
            training_config={"epochs": 100},
            validation_config={"split": 0.2},
        )

        assert config.experiment_name == "Test Strategy"
        assert config.hypothesis == "Test hypothesis"
        assert config.experiment_type == ExperimentType.NEURO_FUZZY_STRATEGY
        assert config.parameters["param1"] == "value1"
        assert config.timeout_minutes == 240  # Default
        assert config.priority == 1  # Default

    def test_experiment_status_enum(self):
        """Test experiment status enum values"""
        assert ExperimentStatus.PENDING == "pending"
        assert ExperimentStatus.RUNNING == "running"
        assert ExperimentStatus.COMPLETED == "completed"
        assert ExperimentStatus.FAILED == "failed"
        assert ExperimentStatus.CANCELLED == "cancelled"

    def test_experiment_type_enum(self):
        """Test experiment type enum values"""
        assert ExperimentType.NEURO_FUZZY_STRATEGY == "neuro_fuzzy_strategy"
        assert ExperimentType.PATTERN_DISCOVERY == "pattern_discovery"
        assert ExperimentType.INDICATOR_OPTIMIZATION == "indicator_optimization"

    @pytest.mark.asyncio
    async def test_orchestrator_initialization_basic(self):
        """Test basic orchestrator initialization"""
        mock_db = AsyncMock()
        mock_db.initialize = AsyncMock()

        orchestrator = ResearchOrchestrator(db_service=mock_db)

        # Should not be initialized initially
        assert not orchestrator._is_initialized

        # Initialize
        await orchestrator.initialize()

        # Should be initialized now
        assert orchestrator._is_initialized
        mock_db.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_orchestrator_shutdown_basic(self):
        """Test basic orchestrator shutdown"""
        mock_db = AsyncMock()
        mock_db.close = AsyncMock()

        orchestrator = ResearchOrchestrator(db_service=mock_db)
        orchestrator._is_initialized = True

        await orchestrator.shutdown()

        mock_db.close.assert_called_once()
        assert orchestrator._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_create_experiment_not_initialized(self):
        """Test creating experiment when not initialized"""
        mock_db = AsyncMock()
        orchestrator = ResearchOrchestrator(db_service=mock_db)

        config = ExperimentConfig(
            experiment_name="Test",
            hypothesis="Test hypothesis",
            experiment_type=ExperimentType.NEURO_FUZZY_STRATEGY,
            parameters={},
            data_requirements={},
            training_config={},
            validation_config={},
        )

        with pytest.raises(ResearchOrchestratorError, match="not initialized"):
            await orchestrator.create_experiment(uuid4(), config)

    @pytest.mark.asyncio
    async def test_get_orchestrator_metrics_basic(self):
        """Test getting basic orchestrator metrics"""
        mock_db = AsyncMock()
        mock_db.health_check = AsyncMock(return_value={"status": "healthy"})

        orchestrator = ResearchOrchestrator(db_service=mock_db)
        orchestrator._is_initialized = True
        orchestrator._total_experiments = 5
        orchestrator._completed_experiments = 3
        orchestrator._failed_experiments = 1

        metrics = await orchestrator.get_orchestrator_metrics()

        assert metrics["total_experiments"] == 5
        assert metrics["completed_experiments"] == 3
        assert metrics["failed_experiments"] == 1
        assert metrics["running_experiments"] == 0
        assert metrics["is_initialized"]
        assert metrics["database_health"]["status"] == "healthy"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
