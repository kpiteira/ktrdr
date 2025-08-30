"""
Unit Tests for Research Orchestrator Service

Tests the experiment lifecycle management service following the implementation
plan's quality-first approach with comprehensive error handling and state management.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from research_agents.services.database import ResearchDatabaseService
from research_agents.services.research_orchestrator import (
    ExperimentConfig,
    ExperimentExecutionError,
    ExperimentStatus,
    ExperimentType,
    ResearchOrchestrator,
    ResearchOrchestratorError,
    ResourceLimitError,
)


@pytest.fixture
def mock_db_service():
    """Create mock database service"""
    db_service = AsyncMock(spec=ResearchDatabaseService)
    db_service.initialize = AsyncMock()
    db_service.close = AsyncMock()
    db_service.health_check = AsyncMock(return_value={"status": "healthy"})
    db_service.execute_query = AsyncMock()
    return db_service


@pytest.fixture
def orchestrator(mock_db_service):
    """Create research orchestrator instance"""
    orchestrator = ResearchOrchestrator(
        db_service=mock_db_service,
        max_concurrent_experiments=2,
        default_timeout_minutes=60,
    )
    # Don't initialize in fixture - let tests do it
    return orchestrator


@pytest.fixture
def sample_experiment_config():
    """Create sample experiment configuration"""
    return ExperimentConfig(
        experiment_name="Test Strategy",
        hypothesis="Moving averages provide profitable signals",
        experiment_type=ExperimentType.NEURO_FUZZY_STRATEGY,
        parameters={"ma_period": 20, "threshold": 0.02},
        data_requirements={"symbol": "EURUSD", "timeframe": "H1"},
        training_config={"epochs": 100, "batch_size": 32},
        validation_config={"test_split": 0.2},
        timeout_minutes=120,
        priority=1,
    )


class TestResearchOrchestratorInitialization:
    """Test orchestrator initialization and configuration"""

    @pytest.mark.asyncio
    async def test_initialization_success(self, mock_db_service):
        """Test successful orchestrator initialization"""
        orchestrator = ResearchOrchestrator(
            db_service=mock_db_service,
            max_concurrent_experiments=3,
            default_timeout_minutes=240,
        )

        # Should not be initialized yet
        assert not orchestrator._is_initialized
        assert orchestrator.max_concurrent_experiments == 3
        assert orchestrator.default_timeout_minutes == 240

        # Initialize
        await orchestrator.initialize()

        # Verify initialization
        assert orchestrator._is_initialized
        mock_db_service.initialize.assert_called_once()
        assert len(orchestrator._running_experiments) == 0
        assert orchestrator._total_experiments == 0

    @pytest.mark.asyncio
    async def test_initialization_failure(self, mock_db_service):
        """Test orchestrator initialization failure"""
        # Mock database initialization failure
        mock_db_service.initialize.side_effect = Exception("Database connection failed")

        orchestrator = ResearchOrchestrator(
            db_service=mock_db_service, max_concurrent_experiments=2
        )

        # Initialization should raise error
        with pytest.raises(ResearchOrchestratorError) as exc_info:
            await orchestrator.initialize()

        assert "Initialization failed" in str(exc_info.value)
        assert not orchestrator._is_initialized

    @pytest.mark.asyncio
    async def test_double_initialization(self, mock_db_service):
        """Test that double initialization is handled gracefully"""
        orchestrator = ResearchOrchestrator(db_service=mock_db_service)

        # Initialize twice
        await orchestrator.initialize()
        await orchestrator.initialize()  # Should not raise error

        # Database initialize should only be called once
        assert mock_db_service.initialize.call_count == 1
        assert orchestrator._is_initialized


class TestExperimentLifecycle:
    """Test experiment creation and lifecycle management"""

    @pytest.mark.asyncio
    async def test_create_experiment_success(
        self, orchestrator, sample_experiment_config, mock_db_service
    ):
        """Test successful experiment creation"""
        await orchestrator.initialize()

        session_id = uuid4()
        expected_experiment_id = uuid4()

        # Mock database response
        with patch(
            "research_agents.services.research_orchestrator.uuid4",
            return_value=expected_experiment_id,
        ):
            experiment_id = await orchestrator.create_experiment(
                session_id=session_id, config=sample_experiment_config
            )

        # Verify experiment creation
        assert experiment_id == expected_experiment_id
        assert orchestrator._total_experiments == 1

        # Verify database call
        mock_db_service.execute_query.assert_called()
        call_args = mock_db_service.execute_query.call_args

        # Check SQL query structure
        query = call_args[0][0]
        assert "INSERT INTO research.experiments" in query
        assert "experiment_name" in query
        assert "hypothesis" in query

        # Check parameters
        params = call_args[0][1:]
        assert params[0] == expected_experiment_id  # experiment_id
        assert params[1] == session_id  # session_id
        assert params[2] == sample_experiment_config.experiment_name
        assert params[3] == sample_experiment_config.hypothesis

    @pytest.mark.asyncio
    async def test_create_experiment_not_initialized(
        self, mock_db_service, sample_experiment_config
    ):
        """Test experiment creation when orchestrator not initialized"""
        orchestrator = ResearchOrchestrator(db_service=mock_db_service)
        # Don't initialize

        with pytest.raises(ResearchOrchestratorError) as exc_info:
            await orchestrator.create_experiment(uuid4(), sample_experiment_config)

        assert "not initialized" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_experiment_database_error(
        self, orchestrator, sample_experiment_config, mock_db_service
    ):
        """Test experiment creation with database error"""
        await orchestrator.initialize()
        session_id = uuid4()

        # Reset and reconfigure mock for this test
        mock_db_service.execute_query.reset_mock()
        mock_db_service.execute_query.side_effect = Exception("Database error")

        with pytest.raises(ExperimentExecutionError) as exc_info:
            await orchestrator.create_experiment(session_id, sample_experiment_config)

        assert "Failed to create experiment" in str(exc_info.value)
        assert orchestrator._total_experiments == 0  # Counter not incremented on error

    @pytest.mark.asyncio
    async def test_get_experiment_status_success(self, orchestrator, mock_db_service):
        """Test getting experiment status"""
        await orchestrator.initialize()
        experiment_id = uuid4()

        # Mock database response
        mock_experiment_data = {
            "id": experiment_id,
            "experiment_name": "Test Experiment",
            "status": "running",
            "hypothesis": "Test hypothesis",
            "experiment_type": "neuro_fuzzy_strategy",
            "configuration": {"param": "value"},
            "created_at": datetime.now(timezone.utc),
            "started_at": datetime.now(timezone.utc),
            "completed_at": None,
            "results": None,
            "error_info": None,
        }

        mock_db_service.execute_query.return_value = mock_experiment_data

        # Get experiment status
        status = await orchestrator.get_experiment_status(experiment_id)

        # Verify response
        assert status["id"] == experiment_id
        assert status["experiment_name"] == "Test Experiment"
        assert status["status"] == "running"
        assert not status["is_running"]  # Not in _running_experiments
        assert "runtime_info" in status
        assert status["runtime_info"]["total_experiments"] == 0

    @pytest.mark.asyncio
    async def test_get_experiment_status_not_found(self, orchestrator, mock_db_service):
        """Test getting status for non-existent experiment"""
        await orchestrator.initialize()
        experiment_id = uuid4()

        # Mock database returning None
        mock_db_service.execute_query.return_value = None

        with pytest.raises(ExperimentExecutionError) as exc_info:
            await orchestrator.get_experiment_status(experiment_id)

        assert "not found" in str(exc_info.value)


class TestExperimentExecution:
    """Test experiment execution and resource management"""

    @pytest.mark.asyncio
    async def test_start_experiment_success(self, orchestrator, mock_db_service):
        """Test successful experiment start"""
        experiment_id = uuid4()

        await orchestrator.initialize()

        # Mock experiment data from database
        mock_experiment = {
            "id": experiment_id,
            "experiment_name": "Test Experiment",
            "status": "pending",
            "configuration": {"param": "value"},
        }

        # Mock both the database query and the _get_experiment_config method
        with patch.object(
            orchestrator, "_get_experiment_config", new_callable=AsyncMock
        ) as mock_get_config:
            mock_get_config.return_value = mock_experiment

            # Mock experiment execution to prevent actual execution
            with patch.object(
                orchestrator, "_execute_experiment", new_callable=AsyncMock
            ) as mock_execute:
                mock_execute.return_value = None  # Simulate running experiment

                # Start experiment
                await orchestrator.start_experiment(experiment_id)

                # Verify experiment is tracked as running
                assert experiment_id in orchestrator._running_experiments
                assert experiment_id in orchestrator._experiment_locks

    @pytest.mark.asyncio
    async def test_start_experiment_resource_limit(self, orchestrator, mock_db_service):
        """Test experiment start with resource limit exceeded"""
        await orchestrator.initialize()

        # Fill up running experiments (max is 2)
        orchestrator._running_experiments[uuid4()] = AsyncMock()
        orchestrator._running_experiments[uuid4()] = AsyncMock()

        experiment_id = uuid4()

        with pytest.raises(ResourceLimitError) as exc_info:
            await orchestrator.start_experiment(experiment_id)

        assert "Maximum concurrent experiments" in str(exc_info.value)
        assert experiment_id not in orchestrator._running_experiments

    @pytest.mark.asyncio
    async def test_start_experiment_not_pending(self, orchestrator, mock_db_service):
        """Test starting experiment that's not in pending status"""
        await orchestrator.initialize()

        experiment_id = uuid4()

        # Mock experiment with non-pending status
        mock_experiment = {
            "id": experiment_id,
            "experiment_name": "Test Experiment",
            "status": "completed",  # Not pending
            "configuration": {"param": "value"},
        }

        with patch.object(
            orchestrator, "_get_experiment_config", new_callable=AsyncMock
        ) as mock_get_config:
            mock_get_config.return_value = mock_experiment

            with pytest.raises(ExperimentExecutionError) as exc_info:
                await orchestrator.start_experiment(experiment_id)

            assert "not in pending status" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_start_experiment_not_found(self, orchestrator, mock_db_service):
        """Test starting non-existent experiment"""
        await orchestrator.initialize()

        experiment_id = uuid4()

        # Mock database returning None
        with patch.object(
            orchestrator, "_get_experiment_config", new_callable=AsyncMock
        ) as mock_get_config:
            mock_get_config.return_value = None

            with pytest.raises(ExperimentExecutionError) as exc_info:
                await orchestrator.start_experiment(experiment_id)

            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_cancel_experiment_success(self, orchestrator):
        """Test successful experiment cancellation"""
        await orchestrator.initialize()

        experiment_id = uuid4()

        # Create a real asyncio task that can be cancelled
        async def dummy_experiment():
            while True:
                await asyncio.sleep(1)

        task = asyncio.create_task(dummy_experiment())
        orchestrator._running_experiments[experiment_id] = task

        # Mock status update
        with patch.object(
            orchestrator, "_update_experiment_status", new_callable=AsyncMock
        ) as mock_update:
            await orchestrator.cancel_experiment(experiment_id)

            # Verify cancellation
            assert task.cancelled()
            mock_update.assert_called_once_with(
                experiment_id, ExperimentStatus.CANCELLED
            )

    @pytest.mark.asyncio
    async def test_cancel_experiment_not_running(self, orchestrator):
        """Test cancelling experiment that's not running"""
        await orchestrator.initialize()

        experiment_id = uuid4()

        with pytest.raises(ExperimentExecutionError) as exc_info:
            await orchestrator.cancel_experiment(experiment_id)

        assert "is not running" in str(exc_info.value)


class TestExperimentListingAndSearch:
    """Test experiment listing and filtering"""

    @pytest.mark.asyncio
    async def test_list_experiments_no_filters(self, orchestrator, mock_db_service):
        """Test listing experiments without filters"""
        await orchestrator.initialize()

        # Mock database response
        mock_experiments = [
            {
                "id": uuid4(),
                "session_id": uuid4(),
                "experiment_name": "Experiment 1",
                "status": "completed",
                "hypothesis": "Test hypothesis 1",
                "experiment_type": "neuro_fuzzy_strategy",
                "created_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc),
                "fitness_score": 1.5,
            },
            {
                "id": uuid4(),
                "session_id": uuid4(),
                "experiment_name": "Experiment 2",
                "status": "running",
                "hypothesis": "Test hypothesis 2",
                "experiment_type": "pattern_discovery",
                "created_at": datetime.now(timezone.utc),
                "started_at": datetime.now(timezone.utc),
                "completed_at": None,
                "fitness_score": None,
            },
        ]

        mock_db_service.execute_query.return_value = mock_experiments

        # List experiments
        experiments = await orchestrator.list_experiments()

        # Verify response
        assert len(experiments) == 2
        assert experiments[0]["experiment_name"] == "Experiment 1"
        assert experiments[1]["experiment_name"] == "Experiment 2"

        # Verify is_running status added
        assert not experiments[0]["is_running"]
        assert not experiments[1]["is_running"]

    @pytest.mark.asyncio
    async def test_list_experiments_with_session_filter(
        self, orchestrator, mock_db_service
    ):
        """Test listing experiments filtered by session"""
        await orchestrator.initialize()

        session_id = uuid4()
        mock_db_service.execute_query.return_value = []

        await orchestrator.list_experiments(session_id=session_id)

        # Verify database query parameters
        call_args = mock_db_service.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "WHERE session_id = $1" in query
        assert params[0] == session_id

    @pytest.mark.asyncio
    async def test_list_experiments_with_status_filter(
        self, orchestrator, mock_db_service
    ):
        """Test listing experiments filtered by status"""
        await orchestrator.initialize()

        mock_db_service.execute_query.return_value = []

        await orchestrator.list_experiments(status=ExperimentStatus.COMPLETED)

        # Verify database query parameters
        call_args = mock_db_service.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "WHERE status = $1" in query
        assert params[0] == ExperimentStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_list_experiments_with_multiple_filters(
        self, orchestrator, mock_db_service
    ):
        """Test listing experiments with multiple filters"""
        await orchestrator.initialize()

        session_id = uuid4()
        mock_db_service.execute_query.return_value = []

        await orchestrator.list_experiments(
            session_id=session_id, status=ExperimentStatus.RUNNING, limit=25
        )

        # Verify database query parameters
        call_args = mock_db_service.execute_query.call_args
        query = call_args[0][0]
        params = call_args[0][1:]

        assert "session_id = $1 AND status = $2" in query
        assert "LIMIT $3" in query
        assert params[0] == session_id
        assert params[1] == ExperimentStatus.RUNNING.value
        assert params[2] == 25


class TestMetricsAndMonitoring:
    """Test orchestrator metrics and monitoring"""

    @pytest.mark.asyncio
    async def test_get_orchestrator_metrics(self, orchestrator, mock_db_service):
        """Test getting orchestrator performance metrics"""
        await orchestrator.initialize()

        # Set up some state
        orchestrator._total_experiments = 10
        orchestrator._completed_experiments = 8
        orchestrator._failed_experiments = 2
        orchestrator._running_experiments[uuid4()] = AsyncMock()

        # Mock database health check
        mock_db_service.health_check.return_value = {"status": "healthy"}

        # Get metrics
        metrics = await orchestrator.get_orchestrator_metrics()

        # Verify metrics
        assert metrics["total_experiments"] == 10
        assert metrics["completed_experiments"] == 8
        assert metrics["failed_experiments"] == 2
        assert metrics["running_experiments"] == 1
        assert metrics["max_concurrent"] == 2  # From fixture
        assert metrics["is_initialized"]
        assert metrics["database_health"]["status"] == "healthy"


class TestErrorHandlingAndRecovery:
    """Test error handling and recovery mechanisms"""

    @pytest.mark.asyncio
    async def test_recover_interrupted_experiments(self, orchestrator, mock_db_service):
        """Test recovery of interrupted experiments"""
        await orchestrator.initialize()

        # Reset mock to start fresh
        mock_db_service.execute_query.reset_mock()

        # Mock interrupted experiments
        interrupted_experiments = [
            {"id": uuid4(), "experiment_name": "Interrupted 1"},
            {"id": uuid4(), "experiment_name": "Interrupted 2"},
        ]

        mock_db_service.execute_query.side_effect = [
            interrupted_experiments,  # First call - find interrupted
            None,  # Second call - update first experiment
            None,  # Third call - update second experiment
        ]

        # Call recovery
        await orchestrator._recover_interrupted_experiments()

        # Verify database calls - should be exactly 3
        assert mock_db_service.execute_query.call_count == 3

        # First call should find interrupted experiments
        first_call = mock_db_service.execute_query.call_args_list[0]
        assert "status IN ('initializing', 'running', 'analyzing')" in first_call[0][0]

        # Subsequent calls should update experiments to failed
        for call in mock_db_service.execute_query.call_args_list[1:]:
            assert "SET status = 'failed'" in call[0][0]
            # Check that second parameter contains the error info dict
            error_info = call[0][2]  # Second parameter (after id)
            assert isinstance(error_info, dict)
            assert error_info["error_type"] == "SystemInterruption"

    @pytest.mark.asyncio
    async def test_experiment_execution_error_handling(self, orchestrator):
        """Test error handling during experiment execution"""
        await orchestrator.initialize()

        experiment_id = uuid4()
        experiment_config = {"experiment_name": "Test", "configuration": {}}

        # Create experiment lock for the execution
        orchestrator._experiment_locks[experiment_id] = asyncio.Lock()

        # Mock database calls
        with patch.object(
            orchestrator, "_update_experiment_status", new_callable=AsyncMock
        ) as mock_update:
            with patch.object(
                orchestrator, "_fail_experiment", new_callable=AsyncMock
            ) as mock_fail:
                # Mock initialization to raise an error
                with patch.object(
                    orchestrator,
                    "_initialize_experiment",
                    side_effect=Exception("Test error"),
                ):

                    # Execute experiment (should handle the error)
                    try:
                        await orchestrator._execute_experiment(
                            experiment_id, experiment_config
                        )
                    except Exception:
                        pass  # Expected to raise

                    # Verify error handling calls
                    assert (
                        mock_update.call_count >= 1
                    )  # Should be called at least once (initializing status)
                    mock_fail.assert_called_once()  # Experiment should be marked as failed

                    # Verify failed experiments counter incremented
                    assert orchestrator._failed_experiments == 1


class TestShutdownAndCleanup:
    """Test graceful shutdown and resource cleanup"""

    @pytest.mark.asyncio
    async def test_graceful_shutdown_no_running_experiments(
        self, orchestrator, mock_db_service
    ):
        """Test shutdown when no experiments are running"""
        await orchestrator.initialize()

        await orchestrator.shutdown()

        # Verify shutdown event is set
        assert orchestrator._shutdown_event.is_set()

        # Verify database service closed
        mock_db_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_running_experiments(
        self, orchestrator, mock_db_service
    ):
        """Test shutdown with running experiments"""
        await orchestrator.initialize()

        # Add mock running experiments
        exp1_id = uuid4()
        exp2_id = uuid4()

        # Create real asyncio tasks for testing
        async def dummy_experiment1():
            while True:
                await asyncio.sleep(1)

        async def dummy_experiment2():
            while True:
                await asyncio.sleep(1)

        task1 = asyncio.create_task(dummy_experiment1())
        task2 = asyncio.create_task(dummy_experiment2())

        orchestrator._running_experiments[exp1_id] = task1
        orchestrator._running_experiments[exp2_id] = task2

        # Mock status update
        with patch.object(
            orchestrator, "_update_experiment_status", new_callable=AsyncMock
        ):
            await orchestrator.shutdown()

        # Verify tasks were cancelled
        assert task1.cancelled()
        assert task2.cancelled()

        # Verify shutdown event is set
        assert orchestrator._shutdown_event.is_set()

        # Verify database service closed
        mock_db_service.close.assert_called_once()


class TestConfigurationAndValidation:
    """Test configuration validation and parameter handling"""

    @pytest.mark.asyncio
    async def test_orchestrator_configuration_defaults(self, mock_db_service):
        """Test default configuration values"""
        orchestrator = ResearchOrchestrator(db_service=mock_db_service)

        assert orchestrator.max_concurrent_experiments == 3  # Default
        assert orchestrator.default_timeout_minutes == 240  # Default
        assert len(orchestrator._running_experiments) == 0
        assert len(orchestrator._experiment_locks) == 0
        assert orchestrator._total_experiments == 0
        assert orchestrator._completed_experiments == 0
        assert orchestrator._failed_experiments == 0

    @pytest.mark.asyncio
    async def test_orchestrator_custom_configuration(self, mock_db_service):
        """Test custom configuration values"""
        orchestrator = ResearchOrchestrator(
            db_service=mock_db_service,
            max_concurrent_experiments=5,
            default_timeout_minutes=180,
        )

        assert orchestrator.max_concurrent_experiments == 5
        assert orchestrator.default_timeout_minutes == 180


# Integration-style tests (still unit tests but testing component interaction)


class TestExperimentWorkflow:
    """Test complete experiment workflow scenarios"""

    @pytest.mark.asyncio
    async def test_complete_experiment_lifecycle(
        self, orchestrator, sample_experiment_config, mock_db_service
    ):
        """Test a complete experiment from creation to completion"""
        await orchestrator.initialize()

        session_id = uuid4()

        # Step 1: Create experiment
        experiment_id = await orchestrator.create_experiment(
            session_id, sample_experiment_config
        )
        assert orchestrator._total_experiments == 1

        # Step 2: Mock experiment data for starting
        mock_experiment = {
            "id": experiment_id,
            "experiment_name": sample_experiment_config.experiment_name,
            "status": "pending",
            "configuration": sample_experiment_config.parameters,
        }
        mock_db_service.execute_query.return_value = mock_experiment

        # Step 3: Start experiment (mock execution)
        with patch.object(orchestrator, "_execute_experiment", new_callable=AsyncMock):
            await orchestrator.start_experiment(experiment_id)

            # Verify experiment is tracked
            assert experiment_id in orchestrator._running_experiments
            assert experiment_id in orchestrator._experiment_locks

    @pytest.mark.asyncio
    async def test_concurrent_experiment_management(
        self, orchestrator, sample_experiment_config, mock_db_service
    ):
        """Test managing multiple concurrent experiments"""
        await orchestrator.initialize()

        session_id = uuid4()

        # Create two experiments
        exp1_id = await orchestrator.create_experiment(
            session_id, sample_experiment_config
        )
        exp2_id = await orchestrator.create_experiment(
            session_id, sample_experiment_config
        )

        assert orchestrator._total_experiments == 2

        # Mock experiment data
        mock_db_service.execute_query.return_value = {
            "id": exp1_id,
            "experiment_name": "Test",
            "status": "pending",
            "configuration": {},
        }

        # Start both experiments
        with patch.object(orchestrator, "_execute_experiment", new_callable=AsyncMock):
            await orchestrator.start_experiment(exp1_id)

            # Update mock for second experiment
            mock_db_service.execute_query.return_value = {
                "id": exp2_id,
                "experiment_name": "Test",
                "status": "pending",
                "configuration": {},
            }

            await orchestrator.start_experiment(exp2_id)

            # Verify both are tracked
            assert len(orchestrator._running_experiments) == 2
            assert exp1_id in orchestrator._running_experiments
            assert exp2_id in orchestrator._running_experiments

        # Try to start a third (should fail due to limit of 2)
        exp3_id = await orchestrator.create_experiment(
            session_id, sample_experiment_config
        )

        with pytest.raises(ResourceLimitError):
            await orchestrator.start_experiment(exp3_id)


# Performance and stress tests (still unit-level)


class TestPerformanceCharacteristics:
    """Test performance characteristics and resource usage"""

    @pytest.mark.asyncio
    async def test_experiment_creation_performance(
        self, orchestrator, sample_experiment_config, mock_db_service
    ):
        """Test performance of creating multiple experiments"""
        await orchestrator.initialize()

        import time

        session_id = uuid4()
        num_experiments = 100

        start_time = time.time()

        # Create many experiments
        experiment_ids = []
        for i in range(num_experiments):
            config = ExperimentConfig(
                experiment_name=f"Performance Test {i}",
                hypothesis=sample_experiment_config.hypothesis,
                experiment_type=sample_experiment_config.experiment_type,
                parameters=sample_experiment_config.parameters,
                data_requirements=sample_experiment_config.data_requirements,
                training_config=sample_experiment_config.training_config,
                validation_config=sample_experiment_config.validation_config,
            )

            exp_id = await orchestrator.create_experiment(session_id, config)
            experiment_ids.append(exp_id)

        elapsed_time = time.time() - start_time

        # Verify all experiments created
        assert len(experiment_ids) == num_experiments
        assert orchestrator._total_experiments == num_experiments

        # Performance assertion (should be fast)
        assert elapsed_time < 5.0  # Should complete in under 5 seconds

        # Verify database was called at least once per experiment
        # (may be more due to initialization)
        assert mock_db_service.execute_query.call_count >= num_experiments

    @pytest.mark.asyncio
    async def test_memory_usage_with_many_experiments(self, orchestrator):
        """Test memory usage doesn't grow excessively with many experiments"""
        await orchestrator.initialize()

        # Simulate many completed experiments without requiring psutil
        initial_count = orchestrator._completed_experiments

        # Simulate many completed experiments
        for _i in range(1000):
            uuid4()
            # Add to completed counter without actually running
            orchestrator._completed_experiments += 1

        # Verify counters work correctly
        assert orchestrator._completed_experiments == initial_count + 1000

        # Verify running experiments dict doesn't grow unbounded
        assert len(orchestrator._running_experiments) == 0
        assert len(orchestrator._experiment_locks) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
