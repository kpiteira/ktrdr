"""
Unit tests for research agents database service layer
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4, UUID
from typing import Dict, Any, List, Optional

from research_agents.services.database import (
    ResearchDatabaseService,
    DatabaseConfig,
    create_database_service
)
from ktrdr.errors import DataError


class TestResearchDatabaseService:
    """Test suite for ResearchDatabaseService"""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, clean_database: ResearchDatabaseService):
        """Test successful health check"""
        health = await clean_database.health_check()
        
        assert health["status"] == "healthy"
        assert "timestamp" in health
        assert "database_url" in health
        assert "connection_pool" in health
        
    @pytest.mark.asyncio
    async def test_health_check_with_details(self, clean_database: ResearchDatabaseService):
        """Test health check with detailed information"""
        health = await clean_database.health_check()
        
        pool_info = health["connection_pool"]
        assert "size" in pool_info
        assert "max_size" in pool_info
        assert "min_size" in pool_info
        assert isinstance(pool_info["size"], int)
        assert pool_info["size"] >= 0
        
    @pytest.mark.asyncio
    async def test_create_session_success(self, clean_database: ResearchDatabaseService):
        """Test successful session creation"""
        session_name = f"TEST_Session_{uuid4().hex[:8]}"
        
        session_id = await clean_database.create_session(
            session_name=session_name,
            description="Test session for unit testing"
        )
        
        assert isinstance(session_id, UUID)
        
        # Verify session was created
        session = await clean_database.get_session(session_id)
        assert session is not None
        assert session["session_name"] == session_name
        assert session["description"] == "Test session for unit testing"
        assert session["status"] == "active"
        
    @pytest.mark.asyncio
    async def test_create_session_duplicate_name(self, clean_database: ResearchDatabaseService):
        """Test creating session with duplicate name fails"""
        session_name = f"TEST_DuplicateSession_{uuid4().hex[:8]}"
        
        # Create first session
        await clean_database.create_session(
            session_name=session_name,
            description="First session"
        )
        
        # Attempt to create duplicate should fail
        with pytest.raises(DataError, match="already exists"):
            await clean_database.create_session(
                session_name=session_name,
                description="Duplicate session"
            )
            
    @pytest.mark.asyncio
    async def test_agent_state_crud_operations(self, clean_database: ResearchDatabaseService, sample_agent_data: Dict[str, Any]):
        """Test CRUD operations for agent states"""
        agent_id = sample_agent_data["agent_id"]
        
        # Create agent state
        await clean_database.create_agent_state(
            agent_id=agent_id,
            agent_type=sample_agent_data["agent_type"],
            status=sample_agent_data["status"],
            current_activity=sample_agent_data["current_activity"],
            state_data=sample_agent_data["state_data"],
            memory_context=sample_agent_data["memory_context"]
        )
        
        # Read agent state
        state = await clean_database.get_agent_state(agent_id)
        assert state is not None
        assert state["agent_id"] == agent_id
        assert state["agent_type"] == sample_agent_data["agent_type"]
        assert state["status"] == sample_agent_data["status"]
        assert state["current_activity"] == sample_agent_data["current_activity"]
        assert state["state_data"] == sample_agent_data["state_data"]
        assert state["memory_context"] == sample_agent_data["memory_context"]
        
        # Update agent state
        new_status = "active"
        new_activity = "Running experiment"
        updated_state_data = {"updated_key": "updated_value"}
        
        await clean_database.update_agent_state(
            agent_id=agent_id,
            status=new_status,
            current_activity=new_activity,
            state_data=updated_state_data
        )
        
        # Verify update
        updated_state = await clean_database.get_agent_state(agent_id)
        assert updated_state["status"] == new_status
        assert updated_state["current_activity"] == new_activity
        assert updated_state["state_data"] == updated_state_data
        
        # Delete agent state
        await clean_database.delete_agent_state(agent_id)
        
        # Verify deletion
        deleted_state = await clean_database.get_agent_state(agent_id)
        assert deleted_state is None
        
    @pytest.mark.asyncio
    async def test_get_active_agents(self, clean_database: ResearchDatabaseService):
        """Test retrieving active agents"""
        # Create test agents with different statuses
        agents_data = [
            {"agent_id": f"test-agent-active-{i}", "agent_type": "researcher", "status": "active"}
            for i in range(3)
        ]
        agents_data.extend([
            {"agent_id": f"test-agent-idle-{i}", "agent_type": "assistant", "status": "idle"}
            for i in range(2)
        ])
        
        # Create all agents
        for agent_data in agents_data:
            await clean_database.create_agent_state(
                agent_id=agent_data["agent_id"],
                agent_type=agent_data["agent_type"],
                status=agent_data["status"],
                current_activity="Test activity"
            )
        
        # Get active agents
        active_agents = await clean_database.get_active_agents()
        
        # Verify only active agents returned
        assert len(active_agents) == 3
        for agent in active_agents:
            assert agent["status"] == "active"
            assert agent["agent_type"] == "researcher"
            
    @pytest.mark.asyncio
    async def test_experiment_lifecycle(self, clean_database: ResearchDatabaseService, sample_experiment_data: Dict[str, Any]):
        """Test complete experiment lifecycle"""
        # Create session first
        session_id = await clean_database.create_session(
            session_name=f"TEST_ExperimentSession_{uuid4().hex[:8]}",
            description="Test session for experiment lifecycle"
        )
        
        # Create experiment
        experiment_id = await clean_database.create_experiment(
            session_id=session_id,
            experiment_name=sample_experiment_data["experiment_name"],
            hypothesis=sample_experiment_data["hypothesis"],
            experiment_type=sample_experiment_data["experiment_type"],
            configuration=sample_experiment_data["configuration"]
        )
        
        assert isinstance(experiment_id, UUID)
        
        # Verify experiment creation
        experiment = await clean_database.get_experiment(experiment_id)
        assert experiment is not None
        assert experiment["experiment_name"] == sample_experiment_data["experiment_name"]
        assert experiment["hypothesis"] == sample_experiment_data["hypothesis"]
        assert experiment["status"] == "pending"
        
        # Update experiment status
        await clean_database.update_experiment_status(
            experiment_id=experiment_id,
            status="running"
        )
        
        # Verify status update
        updated_experiment = await clean_database.get_experiment(experiment_id)
        assert updated_experiment["status"] == "running"
        
        # Complete experiment with results
        results = {
            "fitness_score": 0.85,
            "profit_factor": 1.25,
            "total_trades": 150,
            "win_rate": 0.62
        }
        
        await clean_database.complete_experiment(
            experiment_id=experiment_id,
            results=results,
            status="completed"
        )
        
        # Verify completion
        completed_experiment = await clean_database.get_experiment(experiment_id)
        assert completed_experiment["status"] == "completed"
        assert completed_experiment["results"] == results
        assert completed_experiment["completed_at"] is not None
        
    @pytest.mark.asyncio
    async def test_get_experiments_by_session(self, clean_database: ResearchDatabaseService):
        """Test retrieving experiments by session"""
        # Create session
        session_id = await clean_database.create_session(
            session_name=f"TEST_SessionExperiments_{uuid4().hex[:8]}",
            description="Test session for experiment queries"
        )
        
        # Create multiple experiments
        experiment_names = [f"TEST_Experiment_{i}_{uuid4().hex[:8]}" for i in range(3)]
        experiment_ids = []
        
        for name in experiment_names:
            exp_id = await clean_database.create_experiment(
                session_id=session_id,
                experiment_name=name,
                hypothesis=f"Test hypothesis for {name}",
                experiment_type="test_strategy",
                configuration={"test_param": "test_value"}
            )
            experiment_ids.append(exp_id)
        
        # Get experiments by session
        experiments = await clean_database.get_experiments_by_session(session_id)
        
        assert len(experiments) == 3
        returned_names = [exp["experiment_name"] for exp in experiments]
        assert set(returned_names) == set(experiment_names)
        
    @pytest.mark.asyncio
    async def test_knowledge_base_operations(self, clean_database: ResearchDatabaseService, sample_knowledge_data: Dict[str, Any]):
        """Test knowledge base CRUD operations"""
        # Create knowledge entry
        entry_id = await clean_database.create_knowledge_entry(
            content_type=sample_knowledge_data["content_type"],
            title=sample_knowledge_data["title"],
            content=sample_knowledge_data["content"],
            summary=sample_knowledge_data["summary"],
            keywords=sample_knowledge_data["keywords"],
            tags=sample_knowledge_data["tags"],
            quality_score=sample_knowledge_data["quality_score"]
        )
        
        assert isinstance(entry_id, UUID)
        
        # Verify creation
        entry = await clean_database.get_knowledge_entry(entry_id)
        assert entry is not None
        assert entry["title"] == sample_knowledge_data["title"]
        assert entry["content"] == sample_knowledge_data["content"]
        assert entry["quality_score"] == sample_knowledge_data["quality_score"]
        assert set(entry["keywords"]) == set(sample_knowledge_data["keywords"])
        assert set(entry["tags"]) == set(sample_knowledge_data["tags"])
        
        # Update knowledge entry
        new_quality_score = 0.95
        await clean_database.update_knowledge_entry(
            entry_id=entry_id,
            quality_score=new_quality_score
        )
        
        # Verify update
        updated_entry = await clean_database.get_knowledge_entry(entry_id)
        assert updated_entry["quality_score"] == new_quality_score
        
    @pytest.mark.asyncio
    async def test_search_knowledge_by_tags(self, clean_database: ResearchDatabaseService):
        """Test searching knowledge by tags"""
        # Create knowledge entries with different tags
        test_entries = [
            {
                "title": f"TEST_Knowledge_ML_{uuid4().hex[:8]}",
                "content": "Machine learning insights",
                "tags": ["machine_learning", "test"],
                "quality_score": 0.8
            },
            {
                "title": f"TEST_Knowledge_Strategy_{uuid4().hex[:8]}",
                "content": "Trading strategy insights",
                "tags": ["trading_strategy", "test"],
                "quality_score": 0.9
            },
            {
                "title": f"TEST_Knowledge_Both_{uuid4().hex[:8]}",
                "content": "Combined insights",
                "tags": ["machine_learning", "trading_strategy", "test"],
                "quality_score": 0.85
            }
        ]
        
        entry_ids = []
        for entry_data in test_entries:
            entry_id = await clean_database.create_knowledge_entry(
                content_type="insight",
                title=entry_data["title"],
                content=entry_data["content"],
                summary="Test summary",
                keywords=["test"],
                tags=entry_data["tags"],
                quality_score=entry_data["quality_score"]
            )
            entry_ids.append(entry_id)
        
        # Search by single tag
        ml_results = await clean_database.search_knowledge_by_tags(["machine_learning"])
        assert len(ml_results) == 2  # Should find entries with ML tag
        
        # Search by multiple tags (AND logic)
        combined_results = await clean_database.search_knowledge_by_tags(["machine_learning", "trading_strategy"])
        assert len(combined_results) == 1  # Should find only the entry with both tags
        
        # Search by test tag
        test_results = await clean_database.search_knowledge_by_tags(["test"])
        assert len(test_results) == 3  # Should find all test entries
        
    @pytest.mark.asyncio
    async def test_get_top_quality_knowledge(self, clean_database: ResearchDatabaseService):
        """Test retrieving top quality knowledge entries"""
        # Create knowledge entries with different quality scores
        quality_scores = [0.95, 0.87, 0.92, 0.78, 0.89]
        entry_ids = []
        
        for i, score in enumerate(quality_scores):
            entry_id = await clean_database.create_knowledge_entry(
                content_type="insight",
                title=f"TEST_Quality_Knowledge_{i}_{uuid4().hex[:8]}",
                content=f"Quality content {i}",
                summary="Test summary",
                keywords=["test"],
                tags=["test"],
                quality_score=score
            )
            entry_ids.append(entry_id)
        
        # Get top 3 quality entries
        top_entries = await clean_database.get_top_quality_knowledge(limit=3)
        
        assert len(top_entries) == 3
        
        # Verify entries are ordered by quality score descending
        scores = [entry["quality_score"] for entry in top_entries]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 0.95  # Highest score
        
    @pytest.mark.asyncio
    async def test_database_error_handling(self, clean_database: ResearchDatabaseService):
        """Test database error handling"""
        # Test getting non-existent agent
        non_existent_agent = await clean_database.get_agent_state("non-existent-agent")
        assert non_existent_agent is None
        
        # Test getting non-existent experiment
        non_existent_experiment = await clean_database.get_experiment(uuid4())
        assert non_existent_experiment is None
        
        # Test updating non-existent agent
        with pytest.raises(DataError):
            await clean_database.update_agent_state(
                agent_id="non-existent-agent",
                status="active"
            )
            
    @pytest.mark.asyncio
    async def test_connection_pool_management(self, test_database: ResearchDatabaseService):
        """Test connection pool management"""
        # Verify pool is initialized
        assert test_database._pool is not None
        
        # Test multiple concurrent operations
        async def concurrent_operation(i: int):
            session_id = await test_database.create_session(
                session_name=f"TEST_Concurrent_Session_{i}_{uuid4().hex[:8]}",
                description=f"Concurrent test session {i}"
            )
            return session_id
        
        # Run multiple operations concurrently
        tasks = [concurrent_operation(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # Verify all operations completed successfully
        assert len(results) == 10
        assert all(isinstance(result, UUID) for result in results)
        
    @pytest.mark.asyncio
    async def test_agent_heartbeat_tracking(self, clean_database: ResearchDatabaseService):
        """Test agent heartbeat tracking"""
        agent_id = f"test-heartbeat-agent-{uuid4().hex[:8]}"
        
        # Create agent
        await clean_database.create_agent_state(
            agent_id=agent_id,
            agent_type="researcher",
            status="active",
            current_activity="Testing heartbeat"
        )
        
        # Get initial heartbeat
        initial_state = await clean_database.get_agent_state(agent_id)
        initial_heartbeat = initial_state["last_heartbeat"]
        
        # Wait a small amount and update heartbeat
        await asyncio.sleep(0.1)
        await clean_database.update_agent_heartbeat(agent_id)
        
        # Verify heartbeat was updated
        updated_state = await clean_database.get_agent_state(agent_id)
        updated_heartbeat = updated_state["last_heartbeat"]
        
        assert updated_heartbeat > initial_heartbeat
        
    @pytest.mark.asyncio
    async def test_experiment_statistics(self, clean_database: ResearchDatabaseService):
        """Test experiment statistics queries"""
        # Create session
        session_id = await clean_database.create_session(
            session_name=f"TEST_StatsSession_{uuid4().hex[:8]}",
            description="Test session for statistics"
        )
        
        # Create experiments with different statuses
        experiment_data = [
            {"status": "completed", "results": {"fitness_score": 0.85}},
            {"status": "completed", "results": {"fitness_score": 0.72}},
            {"status": "running", "results": None},
            {"status": "failed", "results": None}
        ]
        
        for i, data in enumerate(experiment_data):
            exp_id = await clean_database.create_experiment(
                session_id=session_id,
                experiment_name=f"TEST_StatsExperiment_{i}_{uuid4().hex[:8]}",
                hypothesis=f"Test hypothesis {i}",
                experiment_type="test_strategy",
                configuration={"test_param": i}
            )
            
            if data["status"] != "pending":
                await clean_database.update_experiment_status(exp_id, data["status"])
                
            if data["results"]:
                await clean_database.complete_experiment(
                    experiment_id=exp_id,
                    results=data["results"],
                    status=data["status"]
                )
        
        # Get experiment statistics
        stats = await clean_database.get_experiment_statistics(session_id)
        
        assert stats["total_experiments"] == 4
        assert stats["completed_experiments"] == 2
        assert stats["running_experiments"] == 1
        assert stats["failed_experiments"] == 1
        assert stats["pending_experiments"] == 0  # We updated all from pending
        
        # Check average fitness score for completed experiments
        assert "average_fitness_score" in stats
        expected_avg = (0.85 + 0.72) / 2
        assert abs(stats["average_fitness_score"] - expected_avg) < 0.01