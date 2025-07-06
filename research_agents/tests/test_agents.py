"""
Unit tests for research agents base functionality
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4
from typing import Dict, Any

from research_agents.agents.base import BaseResearchAgent, AgentError
from research_agents.agents.researcher import ResearcherAgent
from research_agents.agents.assistant import AssistantAgent
from research_agents.services.database import ResearchDatabaseService, DatabaseConfig


class MockResearchAgent(BaseResearchAgent):
    """Mock agent for testing base functionality"""
    
    def __init__(self, agent_id: str, agent_type: str = "assistant"):
        super().__init__(agent_id, agent_type, max_errors=1)  # Fail fast in tests
        self.cycle_count = 0
        self.should_stop = False
        self.mock_error = None
        
    async def _start_heartbeat(self) -> None:
        """Override to prevent heartbeat in tests"""
        pass
        
    async def _initialize_agent(self) -> None:
        """Mock agent initialization"""
        # Mock initialization work
        pass
        
    async def _execute_cycle(self) -> None:
        """Mock cycle execution"""
        self.cycle_count += 1
        
        if self.mock_error:
            raise self.mock_error
            
        if self.should_stop:
            self.is_running = False
            self._stop_requested = True
            
        # Simulate some work
        await asyncio.sleep(0.01)
        
    async def _cleanup_agent(self) -> None:
        """Mock agent cleanup"""
        # Mock cleanup work
        pass


class TestBaseResearchAgent:
    """Test suite for BaseResearchAgent"""
    
    @pytest.fixture
    def mock_database_service(self):
        """Mock database service"""
        db = AsyncMock(spec=ResearchDatabaseService)
        db.create_agent_state = AsyncMock()
        db.get_agent_state = AsyncMock(return_value=None)  # Default to no existing state
        db.update_agent_state = AsyncMock()
        db.update_agent_heartbeat = AsyncMock()
        return db
    
    @pytest.fixture
    def mock_agent(self, mock_database_service):
        """Create mock agent instance"""
        agent = MockResearchAgent("test-agent-001", "assistant")
        agent.db = mock_database_service
        return agent
    
    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_agent: MockResearchAgent):
        """Test agent initialization"""
        assert mock_agent.agent_id == "test-agent-001"
        assert mock_agent.agent_type == "assistant"
        assert mock_agent.is_running is False
        assert mock_agent.current_activity == "Initializing"
        assert mock_agent.state_data == {}
        assert mock_agent.memory_context == {}
        
    @pytest.mark.asyncio
    async def test_agent_initialize_creates_state(self, mock_agent: MockResearchAgent):
        """Test that initialize() creates agent state in database"""
        await mock_agent.initialize()
        
        # Verify database state creation was called
        mock_agent.db.create_agent_state.assert_called_once_with(
            "test-agent-001",
            "assistant",
            "idle",
            "Agent registered",
            {},
            {}
        )
        
    @pytest.mark.asyncio
    async def test_agent_initialize_handles_existing_state(self, mock_agent: MockResearchAgent):
        """Test that initialize() handles existing agent state"""
        # Mock existing state
        existing_state = {
            "agent_id": "test-agent-001",
            "agent_type": "assistant",
            "status": "active",
            "current_activity": "Previous activity",
            "state_data": {"previous_key": "previous_value"},
            "memory_context": {"previous_memory": "previous_context"}
        }
        
        mock_agent.db.get_agent_state.return_value = existing_state
        
        await mock_agent.initialize()
        
        # Verify agent loaded existing state
        assert mock_agent.status == "active"
        assert mock_agent.current_activity == "Previous activity"
        assert mock_agent.state_data == {"previous_key": "previous_value"}
        assert mock_agent.memory_context == {"previous_memory": "previous_context"}
        
    @pytest.mark.asyncio
    async def test_agent_state_persistence(self, mock_agent: MockResearchAgent):
        """Test agent state persistence"""
        await mock_agent.initialize()
        
        # Update agent state
        mock_agent.status = "active"
        mock_agent.current_activity = "Testing persistence"
        mock_agent.state_data = {"test_key": "test_value"}
        
        # Persist state
        await mock_agent._persist_state()
        
        # Verify database update was called
        mock_agent.db.update_agent_state.assert_called_with(
            "test-agent-001",
            "active",
            "Testing persistence",
            {"test_key": "test_value"},
            {}
        )
        
    @pytest.mark.asyncio
    async def test_agent_heartbeat(self, mock_agent: MockResearchAgent):
        """Test agent heartbeat mechanism"""
        await mock_agent.initialize()
        
        # Send heartbeat
        await mock_agent._send_heartbeat()
        
        # Verify heartbeat was sent to database
        mock_agent.db.update_agent_heartbeat.assert_called_once_with("test-agent-001")
        
    @pytest.mark.asyncio
    async def test_agent_memory_management(self, mock_agent: MockResearchAgent):
        """Test agent memory management"""
        await mock_agent.initialize()
        
        # Add memory entries
        mock_agent.add_memory("key1", "value1")
        mock_agent.add_memory("key2", {"nested": "value2"})
        
        assert mock_agent.memory_context["key1"] == "value1"
        assert mock_agent.memory_context["key2"] == {"nested": "value2"}
        
        # Get memory
        assert mock_agent.get_memory("key1") == "value1"
        assert mock_agent.get_memory("key2") == {"nested": "value2"}
        assert mock_agent.get_memory("nonexistent") is None
        
        # Clear memory
        mock_agent.clear_memory("key1")
        assert mock_agent.get_memory("key1") is None
        assert mock_agent.get_memory("key2") is not None
        
    @pytest.mark.asyncio
    async def test_agent_activity_tracking(self, mock_agent: MockResearchAgent):
        """Test agent activity tracking"""
        await mock_agent.initialize()
        
        # Update activity
        await mock_agent.update_activity("Testing activity tracking")
        
        assert mock_agent.current_activity == "Testing activity tracking"
        
        # Verify state was persisted
        mock_agent.db.update_agent_state.assert_called()
        
    @pytest.mark.asyncio
    async def test_agent_run_cycle_execution(self, mock_agent: MockResearchAgent):
        """Test agent run cycle execution"""
        await mock_agent.initialize()
        
        # Set agent to stop after 2 cycles
        mock_agent.should_stop = True
        
        # Run agent (should stop after cycles)
        await mock_agent.run()
        
        # Verify cycles were executed
        assert mock_agent.cycle_count > 0
        assert mock_agent._stop_requested is True
        
    @pytest.mark.asyncio
    async def test_agent_error_handling(self, mock_agent: MockResearchAgent):
        """Test agent error handling"""
        await mock_agent.initialize()
        
        # Set up error condition
        test_error = ValueError("Test error")
        mock_agent.mock_error = test_error
        
        # Run agent (should handle error gracefully)
        with pytest.raises(AgentError):
            await mock_agent.run()
            
    @pytest.mark.asyncio
    async def test_agent_stop_mechanism(self, mock_agent: MockResearchAgent):
        """Test agent stop mechanism"""
        await mock_agent.initialize()
        
        # Start agent in background
        agent_task = asyncio.create_task(mock_agent.run())
        
        # Let it run for a bit
        await asyncio.sleep(0.05)
        
        # Stop agent
        await mock_agent.stop()
        
        # Wait for agent to stop
        await agent_task
        
        assert mock_agent._stop_requested is True
        
    @pytest.mark.asyncio
    async def test_agent_state_validation(self, mock_agent: MockResearchAgent):
        """Test agent state validation"""
        await mock_agent.initialize()
        
        # Test valid status updates
        valid_statuses = ["idle", "active", "busy", "error", "stopped"]
        for status in valid_statuses:
            mock_agent.status = status
            await mock_agent._persist_state()
            
        # Test invalid status (should not cause error, but might be logged)
        mock_agent.status = "invalid_status"
        await mock_agent._persist_state()
        
    @pytest.mark.asyncio
    async def test_agent_configuration_management(self, mock_agent: MockResearchAgent):
        """Test agent configuration management"""
        await mock_agent.initialize()
        
        # Set configuration
        config = {
            "max_cycles": 100,
            "heartbeat_interval": 30,
            "memory_limit": 1000
        }
        
        mock_agent.update_config(config)
        
        # Check that the new config values were set
        for key, value in config.items():
            assert mock_agent.config[key] == value
        assert mock_agent.get_config_value("max_cycles") == 100
        assert mock_agent.get_config_value("heartbeat_interval") == 30
        assert mock_agent.get_config_value("nonexistent", "default") == "default"


class TestResearcherAgent:
    """Test suite for ResearcherAgent"""
    
    @pytest.fixture
    def mock_researcher_agent(self):
        """Create mock researcher agent"""
        # Create agent without OpenAI API key to avoid real API calls
        agent = ResearcherAgent("researcher-001")
        agent.db = AsyncMock()
        agent.openai_client = AsyncMock()  # Mock the OpenAI client
        agent.llm_client = AsyncMock()  # Alias for tests
        return agent
    
    @pytest.mark.asyncio
    async def test_researcher_initialization(self, mock_researcher_agent: ResearcherAgent):
        """Test researcher agent initialization"""
        assert mock_researcher_agent.agent_id == "researcher-001"
        assert mock_researcher_agent.agent_type == "researcher"
        assert mock_researcher_agent.status == "idle"
        
    @pytest.mark.asyncio
    async def test_researcher_hypothesis_generation(self, mock_researcher_agent: ResearcherAgent):
        """Test hypothesis generation"""
        # Mock LLM response
        mock_researcher_agent.llm_client.generate_hypothesis.return_value = {
            "hypothesis": "Test hypothesis",
            "rationale": "Test rationale",
            "confidence": 0.8
        }
        
        await mock_researcher_agent.initialize()
        
        # Generate hypothesis
        hypothesis = await mock_researcher_agent.generate_hypothesis()
        
        assert hypothesis["hypothesis"] == "Test hypothesis"
        assert hypothesis["rationale"] == "Test rationale"
        assert hypothesis["confidence"] == 0.8
        
    @pytest.mark.asyncio
    async def test_researcher_knowledge_search(self, mock_researcher_agent: ResearcherAgent):
        """Test knowledge search functionality"""
        # Mock database search results
        mock_researcher_agent.db.search_knowledge_by_tags.return_value = [
            {
                "title": "Test Knowledge",
                "content": "Test content",
                "tags": ["test", "knowledge"],
                "quality_score": 0.9
            }
        ]
        
        await mock_researcher_agent.initialize()
        
        # Search knowledge
        results = await mock_researcher_agent.search_knowledge(["test", "knowledge"])
        
        assert len(results) == 1
        assert results[0]["title"] == "Test Knowledge"
        assert results[0]["quality_score"] == 0.9
        
    @pytest.mark.asyncio
    async def test_researcher_experiment_design(self, mock_researcher_agent: ResearcherAgent):
        """Test experiment design"""
        # Mock hypothesis
        hypothesis = {
            "hypothesis": "Test hypothesis",
            "rationale": "Test rationale",
            "confidence": 0.8
        }
        
        await mock_researcher_agent.initialize()
        
        # Design experiment
        experiment_design = await mock_researcher_agent.design_experiment(hypothesis)
        
        assert "experiment_name" in experiment_design
        assert "configuration" in experiment_design
        assert "expected_duration" in experiment_design
        assert experiment_design["hypothesis"] == hypothesis["hypothesis"]


class TestAssistantAgent:
    """Test suite for AssistantAgent"""
    
    @pytest.fixture
    def mock_assistant_agent(self):
        """Create mock assistant agent"""
        # Create agent without real KTRDR client
        agent = AssistantAgent("assistant-001")
        agent.db = AsyncMock()
        agent.ktrdr_client = AsyncMock()
        return agent
    
    @pytest.mark.asyncio
    async def test_assistant_initialization(self, mock_assistant_agent: AssistantAgent):
        """Test assistant agent initialization"""
        assert mock_assistant_agent.agent_id == "assistant-001"
        assert mock_assistant_agent.agent_type == "assistant"
        assert mock_assistant_agent.status == "idle"
        
    @pytest.mark.asyncio
    async def test_assistant_experiment_execution(self, mock_assistant_agent: AssistantAgent):
        """Test experiment execution"""
        # Mock KTRDR client response
        mock_assistant_agent.ktrdr_client.start_training.return_value = {
            "training_id": "test-training-001",
            "status": "started"
        }
        
        await mock_assistant_agent.initialize()
        
        # Execute experiment
        experiment_config = {
            "strategy_type": "test_strategy",
            "parameters": {"epochs": 10, "learning_rate": 0.001}
        }
        
        result = await mock_assistant_agent.execute_experiment(experiment_config)
        
        assert result["training_id"] == "test-training-001"
        assert result["status"] == "started"
        
    @pytest.mark.asyncio
    async def test_assistant_training_monitoring(self, mock_assistant_agent: AssistantAgent):
        """Test training monitoring"""
        # Mock training status
        mock_assistant_agent.ktrdr_client.get_training_status.return_value = {
            "training_id": "test-training-001",
            "status": "running",
            "progress": 0.5,
            "current_epoch": 5,
            "total_epochs": 10
        }
        
        await mock_assistant_agent.initialize()
        
        # Monitor training
        status = await mock_assistant_agent.monitor_training("test-training-001")
        
        assert status["training_id"] == "test-training-001"
        assert status["status"] == "running"
        assert status["progress"] == 0.5
        
    @pytest.mark.asyncio
    async def test_assistant_result_analysis(self, mock_assistant_agent: AssistantAgent):
        """Test result analysis"""
        # Mock training results
        training_results = {
            "fitness_score": 0.85,
            "profit_factor": 1.25,
            "sharpe_ratio": 1.8,
            "max_drawdown": 0.12,
            "total_trades": 150,
            "win_rate": 0.62
        }
        
        await mock_assistant_agent.initialize()
        
        # Analyze results
        analysis = await mock_assistant_agent.analyze_results(training_results)
        
        assert "fitness_score" in analysis
        assert "performance_metrics" in analysis
        assert "insights" in analysis
        assert analysis["fitness_score"] == 0.85
        
    @pytest.mark.asyncio
    async def test_assistant_knowledge_extraction(self, mock_assistant_agent: AssistantAgent):
        """Test knowledge extraction from results"""
        # Mock experiment results
        experiment_results = {
            "fitness_score": 0.85,
            "profit_factor": 1.25,
            "strategy_parameters": {
                "ma_period": 20,
                "rsi_threshold": 30
            },
            "performance_metrics": {
                "total_trades": 150,
                "win_rate": 0.62
            }
        }
        
        await mock_assistant_agent.initialize()
        
        # Extract knowledge
        knowledge = await mock_assistant_agent.extract_knowledge(experiment_results)
        
        assert "insights" in knowledge
        assert "patterns" in knowledge
        assert "recommendations" in knowledge
        assert knowledge["quality_score"] > 0
        
    @pytest.mark.asyncio
    async def test_assistant_error_handling(self, mock_assistant_agent: AssistantAgent):
        """Test assistant error handling"""
        # Mock KTRDR client error
        mock_assistant_agent.ktrdr_client.start_training.side_effect = Exception("Training failed")
        
        await mock_assistant_agent.initialize()
        
        # Execute experiment (should handle error)
        experiment_config = {"strategy_type": "test_strategy"}
        
        with pytest.raises(AgentError):
            await mock_assistant_agent.execute_experiment(experiment_config)
            
        # Verify error was logged and agent status updated
        assert mock_assistant_agent.status == "error"


class TestAgentIntegration:
    """Integration tests for agent interactions"""
    
    @pytest.mark.asyncio
    async def test_agent_database_integration(self, clean_database: ResearchDatabaseService):
        """Test agent integration with real database"""
        # Create agent with real database
        agent = MockResearchAgent("integration-test-001")
        agent.db = clean_database
        
        # Initialize agent
        await agent.initialize()
        
        # Verify agent state was created
        state = await clean_database.get_agent_state("integration-test-001")
        assert state is not None
        assert state["agent_id"] == "integration-test-001"
        assert state["agent_type"] == "assistant"
        
        # Update agent state
        agent.status = "active"
        agent.current_activity = "Integration testing"
        await agent._persist_state()
        
        # Verify state was updated
        updated_state = await clean_database.get_agent_state("integration-test-001")
        assert updated_state["status"] == "active"
        assert updated_state["current_activity"] == "Integration testing"
        
    @pytest.mark.asyncio
    async def test_multiple_agents_coordination(self, clean_database: ResearchDatabaseService):
        """Test coordination between multiple agents"""
        # Create multiple agents
        researcher = MockResearchAgent("researcher-integration-001", "researcher")
        assistant = MockResearchAgent("assistant-integration-001", "assistant")
        
        researcher.db = clean_database
        assistant.db = clean_database
        
        # Initialize both agents
        await researcher.initialize()
        await assistant.initialize()
        
        # Verify both agents exist
        researcher_state = await clean_database.get_agent_state("researcher-integration-001")
        assistant_state = await clean_database.get_agent_state("assistant-integration-001")
        
        assert researcher_state is not None
        assert assistant_state is not None
        assert researcher_state["agent_type"] == "researcher"
        assert assistant_state["agent_type"] == "assistant"
        
        # Test agent discovery
        active_agents = await clean_database.get_active_agents()
        agent_ids = [agent["agent_id"] for agent in active_agents]
        
        # Both agents should be discoverable
        assert "researcher-integration-001" in agent_ids
        assert "assistant-integration-001" in agent_ids