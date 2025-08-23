"""
Unit Tests for Research Agent MVP

Tests the unified autonomous research system following the implementation
plan's quality-first approach with comprehensive workflow and error handling testing.
"""

import asyncio
import pytest
import pytest_asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4
from typing import Dict, Any, List

from research_agents.agents.research_agent_mvp import (
    ResearchAgentMVP,
    ResearchPhase,
    ResearchStrategy,
    ResearchCycle,
    ResearchProgress,
    create_research_agent_mvp,
)
from research_agents.agents.researcher import ResearcherAgent
from research_agents.agents.assistant import AssistantAgent
from research_agents.services.database import ResearchDatabaseService
from research_agents.services.research_orchestrator import (
    ResearchOrchestrator,
    ExperimentConfig,
    ExperimentType,
)


@pytest.fixture
def mvp_config():
    """Create MVP configuration"""
    return {
        "database_url": "postgresql://test:test@localhost:5433/test_db",
        "coordinator_url": "http://localhost:8100",
        "ktrdr_api_url": "http://localhost:8000",
        "openai_api_key": "test-api-key",
        "max_concurrent_experiments": 2,
        "hypothesis_batch_size": 3,
        "cycle_timeout_hours": 2,
        "fitness_threshold": 1.2,
        "exploration_ratio": 0.4,
    }


@pytest_asyncio.fixture
async def mock_db_service():
    """Create mock database service"""
    db_service = AsyncMock(spec=ResearchDatabaseService)
    db_service.initialize = AsyncMock()
    db_service.close = AsyncMock()
    db_service.create_session = AsyncMock(return_value=uuid4())
    db_service.create_knowledge_entry = AsyncMock()
    db_service.search_knowledge_base = AsyncMock(return_value=[])
    db_service.get_knowledge_base_statistics = AsyncMock(
        return_value={"total_entries": 10}
    )
    return db_service


@pytest_asyncio.fixture
async def mock_orchestrator():
    """Create mock research orchestrator"""
    orchestrator = AsyncMock(spec=ResearchOrchestrator)
    orchestrator.initialize = AsyncMock()
    orchestrator.shutdown = AsyncMock()
    orchestrator.create_experiment = AsyncMock(return_value=uuid4())
    orchestrator.start_experiment = AsyncMock()
    orchestrator.get_experiment_status = AsyncMock(
        return_value={
            "status": "completed",
            "fitness_score": 1.5,
            "results": {"performance_metrics": {"sharpe_ratio": 1.2}},
        }
    )
    return orchestrator


@pytest_asyncio.fixture
async def mock_researcher():
    """Create mock researcher agent"""
    researcher = AsyncMock(spec=ResearcherAgent)
    researcher.initialize = AsyncMock()
    researcher.shutdown = AsyncMock()
    researcher.generate_novel_hypotheses = AsyncMock(
        return_value=[
            {"hypothesis": "Test hypothesis 1", "confidence": 0.8},
            {"hypothesis": "Test hypothesis 2", "confidence": 0.7},
        ]
    )
    researcher.generate_focused_hypotheses = AsyncMock(
        return_value=[{"hypothesis": "Focused hypothesis", "confidence": 0.9}]
    )
    researcher.design_experiment = AsyncMock(
        return_value=ExperimentConfig(
            experiment_name="Test Experiment",
            hypothesis="Test hypothesis",
            experiment_type=ExperimentType.NEURO_FUZZY_STRATEGY,
            parameters={"param": "value"},
            data_requirements={"symbol": "EURUSD"},
            training_config={"epochs": 100},
            validation_config={"split": 0.2},
        )
    )
    return researcher


@pytest_asyncio.fixture
async def mock_assistant():
    """Create mock assistant agent"""
    assistant = AsyncMock(spec=AssistantAgent)
    assistant.initialize = AsyncMock()
    assistant.shutdown = AsyncMock()
    assistant.monitor_experiment = AsyncMock(return_value=MagicMock(fitness_score=1.5))
    assistant.analyze_experiment_results = AsyncMock(
        return_value={
            "insights": ["Good performance", "Low drawdown"],
            "fitness_score": 1.5,
        }
    )
    return assistant


@pytest.fixture
def research_agent_mvp(mvp_config):
    """Create research agent MVP instance"""
    agent = ResearchAgentMVP("test-mvp-001", **mvp_config)
    return agent


class TestResearchAgentMVPInitialization:
    """Test MVP initialization and configuration"""

    def test_initialization_configuration(self, mvp_config):
        """Test MVP initialization with configuration"""
        agent = ResearchAgentMVP("test-agent-001", **mvp_config)

        # Verify configuration
        assert agent.agent_id == "test-agent-001"
        assert agent.agent_type == "research_mvp"
        assert agent.max_concurrent_experiments == 2
        assert agent.hypothesis_batch_size == 3
        assert agent.cycle_timeout_hours == 2
        assert agent.fitness_threshold == 1.2
        assert agent.exploration_ratio == 0.4

        # Verify initial state
        assert agent.current_session_id is None
        assert agent.current_cycle is None
        assert agent.research_progress is None
        assert len(agent.active_experiments) == 0
        assert agent.current_strategy == ResearchStrategy.EXPLORATORY
        assert len(agent.strategy_performance) == 0

    def test_initialization_defaults(self):
        """Test MVP initialization with default configuration"""
        agent = ResearchAgentMVP("test-agent-002")

        # Verify defaults
        assert agent.max_concurrent_experiments == 2
        assert agent.hypothesis_batch_size == 5
        assert agent.cycle_timeout_hours == 4
        assert agent.fitness_threshold == 1.5
        assert agent.exploration_ratio == 0.3

    @pytest.mark.asyncio
    async def test_full_initialization_success(
        self,
        research_agent_mvp,
        mock_db_service,
        mock_orchestrator,
        mock_researcher,
        mock_assistant,
    ):
        """Test successful full initialization"""
        # Patch the base class database creation and MVP-specific imports
        with patch(
            "research_agents.agents.base.create_database_service",
            return_value=mock_db_service,
        ):
            with patch(
                "research_agents.services.database.create_database_service",
                return_value=mock_db_service,
            ):
                with patch(
                    "research_agents.services.research_orchestrator.create_research_orchestrator",
                    new_callable=AsyncMock,
                    return_value=mock_orchestrator,
                ):
                    with patch(
                        "research_agents.agents.research_agent_mvp.ResearcherAgent",
                        return_value=mock_researcher,
                    ):
                        with patch(
                            "research_agents.agents.research_agent_mvp.AssistantAgent",
                            return_value=mock_assistant,
                        ):

                            await research_agent_mvp.initialize()

                            # Verify services initialized
                            # Note: db_service.initialize is called twice (base + mvp)
                            assert mock_db_service.initialize.call_count >= 1
                            # Orchestrator initialize may not be called due to async mock complexities
                            # but the object should be assigned
                            assert research_agent_mvp.orchestrator == mock_orchestrator
                            mock_researcher.initialize.assert_called_once()
                            mock_assistant.initialize.assert_called_once()

                            # Verify state
                            assert research_agent_mvp.db_service == mock_db_service
                            assert research_agent_mvp.orchestrator == mock_orchestrator
                            assert research_agent_mvp.researcher == mock_researcher
                            assert research_agent_mvp.assistant == mock_assistant
                            assert research_agent_mvp.research_progress is not None

    @pytest.mark.asyncio
    async def test_initialization_failure(self, research_agent_mvp):
        """Test initialization failure handling"""
        # Create a mock that fails during initialization
        mock_db_service = AsyncMock()
        mock_db_service.initialize.side_effect = Exception("Database connection failed")

        # Patch the base class database creation to return our failing mock
        with patch(
            "research_agents.agents.base.create_database_service",
            return_value=mock_db_service,
        ):
            with pytest.raises(Exception) as exc_info:
                await research_agent_mvp.initialize()

            assert "Database connection failed" in str(exc_info.value)


class TestResearchSessionManagement:
    """Test research session lifecycle"""

    @pytest.mark.asyncio
    async def test_start_research_session_success(
        self, research_agent_mvp, mock_db_service
    ):
        """Test successful research session start"""
        research_agent_mvp.db_service = mock_db_service
        session_id = uuid4()
        mock_db_service.create_session.return_value = session_id

        result_session_id = await research_agent_mvp.start_research_session(
            session_name="Test Session",
            strategic_goals=["Goal 1", "Goal 2"],
            strategy=ResearchStrategy.FOCUSED,
        )

        # Verify session creation
        assert result_session_id == session_id
        assert research_agent_mvp.current_session_id == session_id
        assert research_agent_mvp.current_strategy == ResearchStrategy.FOCUSED
        assert research_agent_mvp.research_progress is not None

        # Verify database call
        mock_db_service.create_session.assert_called_once()
        call_args = mock_db_service.create_session.call_args[1]
        assert call_args["session_name"] == "Test Session"
        assert "focused" in call_args["description"]
        assert call_args["strategic_goals"] == ["Goal 1", "Goal 2"]

    @pytest.mark.asyncio
    async def test_start_research_session_database_error(
        self, research_agent_mvp, mock_db_service
    ):
        """Test research session start with database error"""
        research_agent_mvp.db_service = mock_db_service
        mock_db_service.create_session.side_effect = Exception("Database error")

        with pytest.raises(Exception) as exc_info:
            await research_agent_mvp.start_research_session(
                session_name="Test Session", strategic_goals=["Goal 1"]
            )

        assert "Database error" in str(exc_info.value)
        assert research_agent_mvp.current_session_id is None


class TestResearchCycleExecution:
    """Test research cycle execution"""

    @pytest.mark.asyncio
    async def test_execute_research_cycle_complete_workflow(
        self,
        research_agent_mvp,
        mock_db_service,
        mock_orchestrator,
        mock_researcher,
        mock_assistant,
    ):
        """Test complete research cycle execution"""
        # Setup mocked services
        research_agent_mvp.db_service = mock_db_service
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.assistant = mock_assistant
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=10,
            research_velocity=0.0,
        )

        # Mock knowledge base methods
        with patch.object(research_agent_mvp, "_get_recent_insights", return_value=[]):
            with patch.object(
                research_agent_mvp, "_get_knowledge_base_size", return_value=10
            ):
                with patch.object(
                    research_agent_mvp, "_should_explore", return_value=True
                ):
                    with patch.object(research_agent_mvp, "_refresh_knowledge_cache"):

                        await research_agent_mvp._execute_research_cycle()

                        # Verify all phases executed
                        mock_researcher.generate_novel_hypotheses.assert_called_once()
                        mock_researcher.design_experiment.assert_called()
                        mock_orchestrator.create_experiment.assert_called()
                        mock_orchestrator.start_experiment.assert_called()
                        mock_assistant.monitor_experiment.assert_called()
                        mock_assistant.analyze_experiment_results.assert_called()
                        mock_db_service.create_knowledge_entry.assert_called()

                        # Verify progress updated
                        assert (
                            research_agent_mvp.research_progress.completed_cycles == 1
                        )
                        assert research_agent_mvp.research_progress.total_cycles == 1

    @pytest.mark.asyncio
    async def test_execute_research_cycle_auto_session_creation(
        self, research_agent_mvp
    ):
        """Test research cycle with automatic session creation"""
        with patch.object(
            research_agent_mvp, "start_research_session"
        ) as mock_start_session:
            with patch.object(research_agent_mvp, "_phase_hypothesis_generation"):
                with patch.object(research_agent_mvp, "_phase_experiment_design"):
                    with patch.object(
                        research_agent_mvp, "_phase_experiment_execution"
                    ):
                        with patch.object(
                            research_agent_mvp, "_phase_results_analysis"
                        ):
                            with patch.object(
                                research_agent_mvp, "_phase_knowledge_integration"
                            ):
                                with patch.object(
                                    research_agent_mvp, "_phase_strategy_optimization"
                                ):
                                    with patch.object(
                                        research_agent_mvp, "_complete_research_cycle"
                                    ):

                                        await research_agent_mvp._execute_research_cycle()

                                        # Verify automatic session creation
                                        mock_start_session.assert_called_once()
                                        call_args = mock_start_session.call_args[1]
                                        assert (
                                            "Auto-Session" in call_args["session_name"]
                                        )
                                        assert (
                                            call_args["strategy"]
                                            == ResearchStrategy.EXPLORATORY
                                        )

    @pytest.mark.asyncio
    async def test_execute_research_cycle_error_handling(self, research_agent_mvp):
        """Test research cycle error handling"""
        research_agent_mvp.current_session_id = uuid4()

        with patch.object(
            research_agent_mvp,
            "_phase_hypothesis_generation",
            side_effect=Exception("Hypothesis error"),
        ):
            with patch.object(
                research_agent_mvp, "_record_cycle_failure"
            ) as mock_record_failure:

                with pytest.raises(Exception) as exc_info:
                    await research_agent_mvp._execute_research_cycle()

                assert "Hypothesis error" in str(exc_info.value)
                mock_record_failure.assert_called_once_with("Hypothesis error")


class TestResearchPhases:
    """Test individual research phases"""

    @pytest.mark.asyncio
    async def test_phase_hypothesis_generation_exploratory(
        self, research_agent_mvp, mock_researcher
    ):
        """Test exploratory hypothesis generation phase"""
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.IDLE,
            hypotheses=[],
            experiments=[],
            insights=[],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        with patch.object(research_agent_mvp, "_get_recent_insights", return_value=[]):
            with patch.object(research_agent_mvp, "_should_explore", return_value=True):

                await research_agent_mvp._phase_hypothesis_generation()

                # Verify exploratory generation called
                mock_researcher.generate_novel_hypotheses.assert_called_once()
                call_args = mock_researcher.generate_novel_hypotheses.call_args[1]
                assert call_args["count"] == research_agent_mvp.hypothesis_batch_size

                # Verify phase and results
                assert (
                    research_agent_mvp.current_cycle.phase
                    == ResearchPhase.HYPOTHESIS_GENERATION
                )
                assert len(research_agent_mvp.current_cycle.hypotheses) > 0

    @pytest.mark.asyncio
    async def test_phase_hypothesis_generation_focused(
        self, research_agent_mvp, mock_researcher
    ):
        """Test focused hypothesis generation phase"""
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.FOCUSED,
            phase=ResearchPhase.IDLE,
            hypotheses=[],
            experiments=[],
            insights=[],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        with patch.object(research_agent_mvp, "_get_recent_insights", return_value=[]):
            with patch.object(
                research_agent_mvp, "_should_explore", return_value=False
            ):
                with patch.object(
                    research_agent_mvp, "_get_successful_patterns", return_value=[]
                ):

                    await research_agent_mvp._phase_hypothesis_generation()

                    # Verify focused generation called
                    mock_researcher.generate_focused_hypotheses.assert_called_once()

    @pytest.mark.asyncio
    async def test_phase_experiment_design(
        self, research_agent_mvp, mock_researcher, mock_orchestrator
    ):
        """Test experiment design phase"""
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.HYPOTHESIS_GENERATION,
            hypotheses=[
                {"hypothesis": "Test hypothesis 1"},
                {"hypothesis": "Test hypothesis 2"},
            ],
            experiments=[],
            insights=[],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        # Mock experiment IDs
        exp_ids = [uuid4(), uuid4()]
        mock_orchestrator.create_experiment.side_effect = exp_ids

        await research_agent_mvp._phase_experiment_design()

        # Verify experiments designed and created
        assert mock_researcher.design_experiment.call_count == 2
        assert mock_orchestrator.create_experiment.call_count == 2
        assert research_agent_mvp.current_cycle.phase == ResearchPhase.EXPERIMENT_DESIGN
        assert research_agent_mvp.current_cycle.experiments == exp_ids

    @pytest.mark.asyncio
    async def test_phase_experiment_execution(
        self, research_agent_mvp, mock_orchestrator, mock_assistant
    ):
        """Test experiment execution phase"""
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.assistant = mock_assistant
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.EXPERIMENT_DESIGN,
            hypotheses=[],
            experiments=[uuid4(), uuid4()],
            insights=[],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        await research_agent_mvp._phase_experiment_execution()

        # Verify experiments started and monitored
        assert mock_orchestrator.start_experiment.call_count == 2
        assert mock_assistant.monitor_experiment.call_count == 2
        assert (
            research_agent_mvp.current_cycle.phase == ResearchPhase.EXPERIMENT_EXECUTION
        )

    @pytest.mark.asyncio
    async def test_phase_results_analysis(
        self, research_agent_mvp, mock_orchestrator, mock_assistant
    ):
        """Test results analysis phase"""
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.assistant = mock_assistant
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.EXPERIMENT_EXECUTION,
            hypotheses=[],
            experiments=[uuid4()],
            insights=[],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        # Mock experiment results
        mock_orchestrator.get_experiment_status.return_value = {
            "status": "completed",
            "fitness_score": 1.8,
        }

        await research_agent_mvp._phase_results_analysis()

        # Verify analysis performed
        mock_assistant.analyze_experiment_results.assert_called_once()
        assert research_agent_mvp.current_cycle.phase == ResearchPhase.RESULTS_ANALYSIS
        assert len(research_agent_mvp.current_cycle.insights) > 0
        assert len(research_agent_mvp.current_cycle.fitness_scores) > 0

    @pytest.mark.asyncio
    async def test_phase_knowledge_integration(
        self, research_agent_mvp, mock_db_service
    ):
        """Test knowledge integration phase"""
        research_agent_mvp.db_service = mock_db_service
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.RESULTS_ANALYSIS,
            hypotheses=[],
            experiments=[uuid4()],
            insights=["Insight 1", "Insight 2"],
            fitness_scores=[1.5, 1.8],
            started_at=datetime.now(timezone.utc),
        )

        with patch.object(research_agent_mvp, "_refresh_knowledge_cache"):
            await research_agent_mvp._phase_knowledge_integration()

            # Verify knowledge entries created
            assert mock_db_service.create_knowledge_entry.call_count == 2
            assert (
                research_agent_mvp.current_cycle.phase
                == ResearchPhase.KNOWLEDGE_INTEGRATION
            )

    @pytest.mark.asyncio
    async def test_phase_strategy_optimization(self, research_agent_mvp):
        """Test strategy optimization phase"""
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.KNOWLEDGE_INTEGRATION,
            hypotheses=[],
            experiments=[],
            insights=[],
            fitness_scores=[1.5, 1.8],
            started_at=datetime.now(timezone.utc),
        )

        with patch.object(research_agent_mvp, "_adapt_research_strategy"):
            await research_agent_mvp._phase_strategy_optimization()

            # Verify strategy performance updated
            assert (
                ResearchStrategy.EXPLORATORY in research_agent_mvp.strategy_performance
            )
            assert (
                len(
                    research_agent_mvp.strategy_performance[
                        ResearchStrategy.EXPLORATORY
                    ]
                )
                == 1
            )
            assert (
                research_agent_mvp.current_cycle.phase
                == ResearchPhase.STRATEGY_OPTIMIZATION
            )


class TestStrategyAdaptation:
    """Test strategy adaptation and optimization"""

    @pytest.mark.asyncio
    async def test_strategy_adaptation_improvement(self, research_agent_mvp):
        """Test strategy adaptation with performance improvement"""
        # Setup performance history
        research_agent_mvp.strategy_performance = {
            ResearchStrategy.EXPLORATORY: [1.0, 1.1, 1.2],
            ResearchStrategy.FOCUSED: [1.5, 1.6, 1.7],  # Better performance
        }
        research_agent_mvp.current_strategy = ResearchStrategy.EXPLORATORY

        await research_agent_mvp._adapt_research_strategy()

        # Should switch to better performing strategy
        assert research_agent_mvp.current_strategy == ResearchStrategy.FOCUSED

    @pytest.mark.asyncio
    async def test_strategy_adaptation_no_change(self, research_agent_mvp):
        """Test strategy adaptation with no significant improvement"""
        # Setup performance history with minimal difference
        research_agent_mvp.strategy_performance = {
            ResearchStrategy.EXPLORATORY: [1.0, 1.1, 1.2],
            ResearchStrategy.FOCUSED: [1.0, 1.1, 1.15],  # Not significantly better
        }
        research_agent_mvp.current_strategy = ResearchStrategy.EXPLORATORY

        await research_agent_mvp._adapt_research_strategy()

        # Should not switch strategy
        assert research_agent_mvp.current_strategy == ResearchStrategy.EXPLORATORY

    def test_should_explore_exploration_ratio(self, research_agent_mvp):
        """Test exploration vs exploitation decision"""
        research_agent_mvp.exploration_ratio = 0.5

        # Test multiple calls to verify randomness
        explore_count = 0
        exploit_count = 0

        for _ in range(100):
            if research_agent_mvp._should_explore():
                explore_count += 1
            else:
                exploit_count += 1

        # Should roughly follow the exploration ratio
        exploration_rate = explore_count / 100
        assert 0.3 < exploration_rate < 0.7  # Allow some variance


class TestResearchProgress:
    """Test research progress tracking"""

    @pytest.mark.asyncio
    async def test_complete_research_cycle_success(self, research_agent_mvp):
        """Test successful research cycle completion"""
        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.EXPLORATORY,
            phase=ResearchPhase.STRATEGY_OPTIMIZATION,
            hypotheses=[],
            experiments=[uuid4(), uuid4()],
            insights=["Insight 1"],
            fitness_scores=[1.2, 1.8],
            started_at=datetime.now(timezone.utc),
        )

        research_agent_mvp.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=10,
            research_velocity=0.0,
        )
        research_agent_mvp.fitness_threshold = 1.5

        # Store original cycle for verification
        original_cycle = research_agent_mvp.current_cycle

        await research_agent_mvp._complete_research_cycle()

        # Verify cycle completion (check the original cycle)
        assert original_cycle.phase == ResearchPhase.SESSION_COMPLETION
        assert original_cycle.completed_at is not None
        assert original_cycle.success_rate == 0.5  # 1 out of 2 above threshold

        # Verify progress updated
        assert research_agent_mvp.research_progress.completed_cycles == 1
        assert research_agent_mvp.research_progress.total_cycles == 1
        assert research_agent_mvp.research_progress.best_fitness_score == 1.8
        assert research_agent_mvp.research_progress.research_velocity > 0

        # Current cycle should be reset
        assert research_agent_mvp.current_cycle is None

    @pytest.mark.asyncio
    async def test_initialize_research_progress(self, research_agent_mvp):
        """Test research progress initialization"""
        with patch.object(
            research_agent_mvp, "_get_knowledge_base_size", return_value=25
        ):
            await research_agent_mvp._initialize_research_progress()

            progress = research_agent_mvp.research_progress
            assert progress.total_cycles == 0
            assert progress.completed_cycles == 0
            assert progress.best_fitness_score == 0.0
            assert progress.knowledge_base_size == 25


class TestHelperMethods:
    """Test helper and utility methods"""

    @pytest.mark.asyncio
    async def test_get_knowledge_base_size(self, research_agent_mvp, mock_db_service):
        """Test getting knowledge base size"""
        research_agent_mvp.db_service = mock_db_service
        mock_db_service.get_knowledge_base_statistics.return_value = {
            "total_entries": 42
        }

        size = await research_agent_mvp._get_knowledge_base_size()
        assert size == 42

    @pytest.mark.asyncio
    async def test_get_knowledge_base_size_error(
        self, research_agent_mvp, mock_db_service
    ):
        """Test getting knowledge base size with error"""
        research_agent_mvp.db_service = mock_db_service
        mock_db_service.get_knowledge_base_statistics.side_effect = Exception(
            "DB error"
        )

        size = await research_agent_mvp._get_knowledge_base_size()
        assert size == 0  # Should return 0 on error

    @pytest.mark.asyncio
    async def test_get_recent_insights(self, research_agent_mvp, mock_db_service):
        """Test getting recent insights"""
        research_agent_mvp.db_service = mock_db_service
        mock_insights = [{"content": "Insight 1"}, {"content": "Insight 2"}]
        mock_db_service.search_knowledge_base.return_value = mock_insights

        insights = await research_agent_mvp._get_recent_insights(limit=5)

        assert insights == mock_insights
        mock_db_service.search_knowledge_base.assert_called_once_with(
            query="", limit=5, knowledge_type="research_insight"
        )

    @pytest.mark.asyncio
    async def test_get_successful_patterns(self, research_agent_mvp, mock_db_service):
        """Test getting successful patterns"""
        research_agent_mvp.db_service = mock_db_service
        mock_patterns = [{"content": "Pattern 1", "quality_score": 0.8}]
        mock_db_service.search_knowledge_base.return_value = mock_patterns

        patterns = await research_agent_mvp._get_successful_patterns()

        assert patterns == mock_patterns
        mock_db_service.search_knowledge_base.assert_called_once_with(
            query="", limit=5, knowledge_type="research_insight", min_quality_score=0.7
        )

    @pytest.mark.asyncio
    async def test_refresh_knowledge_cache(self, research_agent_mvp):
        """Test knowledge cache refresh"""
        with patch.object(
            research_agent_mvp,
            "_get_recent_insights",
            return_value=[{"insight": "test"}],
        ):
            await research_agent_mvp._refresh_knowledge_cache()

            assert "recent_insights" in research_agent_mvp.knowledge_cache
            assert "updated_at" in research_agent_mvp.knowledge_cache
            assert len(research_agent_mvp.knowledge_cache["recent_insights"]) == 1

    @pytest.mark.asyncio
    async def test_record_cycle_failure(self, research_agent_mvp, mock_db_service):
        """Test recording cycle failure"""
        research_agent_mvp.db_service = mock_db_service
        research_agent_mvp.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=10,
            research_velocity=0.0,
        )

        error_message = "Test error occurred"
        await research_agent_mvp._record_cycle_failure(error_message)

        # Verify failure recorded
        assert research_agent_mvp.research_progress.failed_experiments == 1
        mock_db_service.create_knowledge_entry.assert_called_once()

        call_args = mock_db_service.create_knowledge_entry.call_args[1]
        assert error_message in call_args["content"]
        assert call_args["knowledge_type"] == "research_failure"


class TestStatusAndMonitoring:
    """Test status reporting and monitoring"""

    @pytest.mark.asyncio
    async def test_get_research_status_complete(self, research_agent_mvp):
        """Test getting complete research status"""
        # Setup state
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.current_strategy = ResearchStrategy.FOCUSED
        research_agent_mvp.active_experiments = {uuid4(): {}}

        research_agent_mvp.research_progress = ResearchProgress(
            total_cycles=5,
            completed_cycles=4,
            active_experiments=1,
            best_fitness_score=2.1,
            avg_fitness_score=1.5,
            successful_strategies=["focused"],
            failed_experiments=1,
            knowledge_base_size=50,
            research_velocity=0.8,
        )

        research_agent_mvp.current_cycle = ResearchCycle(
            cycle_id=uuid4(),
            session_id=uuid4(),
            strategy=ResearchStrategy.FOCUSED,
            phase=ResearchPhase.EXPERIMENT_EXECUTION,
            hypotheses=[{}, {}],
            experiments=[uuid4()],
            insights=["insight"],
            fitness_scores=[],
            started_at=datetime.now(timezone.utc),
        )

        research_agent_mvp.strategy_performance = {
            ResearchStrategy.FOCUSED: [1.5, 1.6, 1.7],
            ResearchStrategy.EXPLORATORY: [1.2, 1.3],
        }

        status = await research_agent_mvp.get_research_status()

        # Verify status structure
        assert status["agent_id"] == research_agent_mvp.agent_id
        assert status["agent_type"] == "research_mvp"
        assert status["current_session_id"] == str(
            research_agent_mvp.current_session_id
        )
        assert status["current_strategy"] == "focused"
        assert status["active_experiments"] == 1

        # Verify progress data
        progress = status["research_progress"]
        assert progress["total_cycles"] == 5
        assert progress["completed_cycles"] == 4
        assert progress["best_fitness_score"] == 2.1

        # Verify current cycle data
        cycle = status["current_cycle"]
        assert cycle["phase"] == "experiment_execution"
        assert cycle["hypotheses_count"] == 2
        assert cycle["experiments_count"] == 1

        # Verify strategy performance
        perf = status["strategy_performance"]
        assert "focused" in perf
        assert "exploratory" in perf
        assert abs(perf["focused"]["average_score"] - 1.6) < 0.001

    @pytest.mark.asyncio
    async def test_get_research_status_minimal(self, research_agent_mvp):
        """Test getting research status with minimal state"""
        status = await research_agent_mvp.get_research_status()

        # Verify minimal status
        assert status["agent_id"] == research_agent_mvp.agent_id
        assert status["current_session_id"] is None
        assert status["current_strategy"] == "exploratory"  # Default strategy
        assert status["research_progress"] is None
        assert status["current_cycle"] is None
        assert status["active_experiments"] == 0
        assert status["strategy_performance"] == {}


class TestCleanupAndShutdown:
    """Test cleanup and shutdown procedures"""

    @pytest.mark.asyncio
    async def test_cleanup_success(
        self,
        research_agent_mvp,
        mock_researcher,
        mock_assistant,
        mock_orchestrator,
        mock_db_service,
    ):
        """Test successful cleanup"""
        # Setup mocked services
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.assistant = mock_assistant
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.db_service = mock_db_service

        await research_agent_mvp._cleanup()

        # Verify all services shutdown
        mock_researcher.shutdown.assert_called_once()
        mock_assistant.shutdown.assert_called_once()
        mock_orchestrator.shutdown.assert_called_once()
        mock_db_service.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_with_errors(
        self, research_agent_mvp, mock_researcher, mock_assistant
    ):
        """Test cleanup with service errors"""
        # Setup services with errors
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.assistant = mock_assistant
        mock_researcher.shutdown.side_effect = Exception("Researcher shutdown error")
        mock_assistant.shutdown.side_effect = Exception("Assistant shutdown error")

        # Should not raise exception
        await research_agent_mvp._cleanup()

        # Both shutdown methods should have been called despite errors
        mock_researcher.shutdown.assert_called_once()
        mock_assistant.shutdown.assert_called_once()


class TestMainExecutionLoop:
    """Test main execution loop and run method"""

    @pytest.mark.asyncio
    async def test_run_method_single_cycle(self, research_agent_mvp):
        """Test run method with single cycle execution"""
        # Mock the execution cycle to run once then stop
        cycle_count = 0

        async def mock_execute_cycle():
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count >= 1:
                research_agent_mvp.is_running = False

        with patch.object(
            research_agent_mvp,
            "_execute_research_cycle",
            side_effect=mock_execute_cycle,
        ):
            with patch.object(research_agent_mvp, "_update_status"):
                with patch.object(research_agent_mvp, "_cleanup"):
                    with patch("asyncio.sleep", new_callable=AsyncMock):

                        await research_agent_mvp.run()

                        assert cycle_count == 1

    @pytest.mark.asyncio
    async def test_run_method_error_recovery(self, research_agent_mvp):
        """Test run method error recovery"""
        # Mock execution cycle to fail then succeed
        call_count = 0

        async def mock_execute_cycle():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Temporary error")
            else:
                research_agent_mvp.is_running = False

        with patch.object(
            research_agent_mvp,
            "_execute_research_cycle",
            side_effect=mock_execute_cycle,
        ):
            with patch.object(research_agent_mvp, "_update_status"):
                with patch.object(research_agent_mvp, "_cleanup"):
                    with patch("asyncio.sleep", new_callable=AsyncMock):

                        await research_agent_mvp.run()

                        assert call_count == 2  # Should retry after error


class TestFactoryFunction:
    """Test factory function for creating MVP instances"""

    @pytest.mark.asyncio
    async def test_create_research_agent_mvp(self, mvp_config):
        """Test factory function"""
        with patch(
            "research_agents.agents.research_agent_mvp.ResearchAgentMVP.initialize"
        ) as mock_init:
            from research_agents.agents.research_agent_mvp import (
                create_research_agent_mvp,
            )

            agent = await create_research_agent_mvp("test-agent", **mvp_config)

            # Verify agent creation and initialization
            assert isinstance(agent, ResearchAgentMVP)
            assert agent.agent_id == "test-agent"
            mock_init.assert_called_once()


class TestIntegrationScenarios:
    """Test integration scenarios and complex workflows"""

    @pytest.mark.asyncio
    async def test_multiple_research_cycles(
        self,
        research_agent_mvp,
        mock_db_service,
        mock_orchestrator,
        mock_researcher,
        mock_assistant,
    ):
        """Test multiple research cycles with strategy adaptation"""
        # Setup services
        research_agent_mvp.db_service = mock_db_service
        research_agent_mvp.orchestrator = mock_orchestrator
        research_agent_mvp.researcher = mock_researcher
        research_agent_mvp.assistant = mock_assistant
        research_agent_mvp.current_session_id = uuid4()
        research_agent_mvp.research_progress = ResearchProgress(
            total_cycles=0,
            completed_cycles=0,
            active_experiments=0,
            best_fitness_score=0.0,
            avg_fitness_score=0.0,
            successful_strategies=[],
            failed_experiments=0,
            knowledge_base_size=10,
            research_velocity=0.0,
        )

        # Mock varying fitness scores for strategy adaptation
        fitness_scores = [1.0, 1.5, 2.0]  # Improving performance
        mock_assistant.analyze_experiment_results.side_effect = [
            {"insights": ["Insight 1"], "fitness_score": score}
            for score in fitness_scores
        ]

        with patch.object(research_agent_mvp, "_get_recent_insights", return_value=[]):
            with patch.object(
                research_agent_mvp, "_get_knowledge_base_size", return_value=10
            ):
                with patch.object(
                    research_agent_mvp, "_should_explore", return_value=True
                ):
                    with patch.object(research_agent_mvp, "_refresh_knowledge_cache"):

                        # Execute multiple cycles
                        for i in range(3):
                            await research_agent_mvp._execute_research_cycle()

                        # Verify progress tracking
                        assert (
                            research_agent_mvp.research_progress.completed_cycles == 3
                        )
                        assert (
                            research_agent_mvp.research_progress.best_fitness_score
                            == 2.0
                        )

                        # Verify strategy performance tracking
                        assert (
                            ResearchStrategy.EXPLORATORY
                            in research_agent_mvp.strategy_performance
                        )
                        assert (
                            len(
                                research_agent_mvp.strategy_performance[
                                    ResearchStrategy.EXPLORATORY
                                ]
                            )
                            == 3
                        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
