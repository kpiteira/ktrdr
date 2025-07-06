"""
Simple integration tests for research agents database
"""

import pytest
import asyncio
from uuid import uuid4
from research_agents.services.database import ResearchDatabaseService, DatabaseConfig


@pytest.mark.asyncio
async def test_database_connection_and_health():
    """Test basic database connection and health check"""
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents",
        username="research_admin",
        password="research_dev_password",
        min_connections=1,
        max_connections=5
    )
    
    db_service = ResearchDatabaseService(config)
    
    try:
        await db_service.initialize()
        
        # Test health check
        health = await db_service.health_check()
        assert health["status"] == "healthy"
        print(f"Health check passed: {health}")
        
    finally:
        await db_service.close()


@pytest.mark.asyncio
async def test_session_operations():
    """Test basic session CRUD operations"""
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents",
        username="research_admin",
        password="research_dev_password",
        min_connections=1,
        max_connections=5
    )
    
    db_service = ResearchDatabaseService(config)
    
    try:
        await db_service.initialize()
        
        # Create session
        session_name = f"TEST_Session_{uuid4().hex[:8]}"
        session_id = await db_service.create_session(
            session_name=session_name,
            description="Simple test session"
        )
        
        print(f"Created session: {session_id}")
        assert session_id is not None
        
        # Get session - use direct query since get_session method doesn't exist
        session = await db_service.execute_query(
            "SELECT * FROM research.sessions WHERE id = $1",
            session_id,
            fetch="one"
        )
        assert session is not None
        assert session["session_name"] == session_name
        print(f"Retrieved session: {session['session_name']}")
        
        # Clean up
        await db_service.execute_query(
            "DELETE FROM research.sessions WHERE id = $1", 
            session_id
        )
        
    finally:
        await db_service.close()


@pytest.mark.asyncio  
async def test_agent_state_operations():
    """Test agent state CRUD operations"""
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents",
        username="research_admin",
        password="research_dev_password",
        min_connections=1,
        max_connections=5
    )
    
    db_service = ResearchDatabaseService(config)
    
    try:
        await db_service.initialize()
        
        # Create agent state
        agent_id = f"test-agent-{uuid4().hex[:8]}"
        await db_service.create_agent_state(
            agent_id=agent_id,
            agent_type="researcher",
            status="idle",
            current_activity="Testing",
            state_data={},
            memory_context={}
        )
        
        print(f"Created agent: {agent_id}")
        
        # Get agent state
        state = await db_service.get_agent_state(agent_id)
        assert state is not None
        assert state["agent_id"] == agent_id
        assert state["agent_type"] == "researcher"
        print(f"Retrieved agent: {state['agent_id']}")
        
        # Update agent state
        await db_service.update_agent_state(
            agent_id=agent_id,
            status="active",
            current_activity="Testing update",
            state_data={},
            memory_context={}
        )
        
        # Verify update
        updated_state = await db_service.get_agent_state(agent_id)
        assert updated_state["status"] == "active"
        assert updated_state["current_activity"] == "Testing update"
        print(f"Updated agent status: {updated_state['status']}")
        
        # Clean up
        await db_service.execute_query(
            "DELETE FROM research.agent_states WHERE agent_id = $1",
            agent_id
        )
        
    finally:
        await db_service.close()


@pytest.mark.asyncio
async def test_knowledge_operations():
    """Test knowledge base operations"""
    config = DatabaseConfig(
        host="localhost",
        port=5433,
        database="research_agents",
        username="research_admin",
        password="research_dev_password",
        min_connections=1,
        max_connections=5
    )
    
    db_service = ResearchDatabaseService(config)
    
    try:
        await db_service.initialize()
        
        # Create knowledge entry
        title = f"TEST_Knowledge_{uuid4().hex[:8]}"
        entry_id = await db_service.add_knowledge_entry(
            content_type="insight",
            title=title,
            content="Test knowledge content",
            summary="Test summary",
            keywords=["test", "knowledge"],
            tags=["test_tag"],
            quality_score=0.85
        )
        
        print(f"Created knowledge entry: {entry_id}")
        assert entry_id is not None
        
        # Get knowledge entry - use direct query since get_knowledge_entry method doesn't exist
        entry = await db_service.execute_query(
            "SELECT * FROM research.knowledge_base WHERE id = $1",
            entry_id,
            fetch="one"
        )
        assert entry is not None
        assert entry["title"] == title
        assert float(entry["quality_score"]) == 0.85
        print(f"Retrieved knowledge: {entry['title']}")
        
        # Search by keywords (the method actually searches keywords, not tags)
        results = await db_service.search_knowledge_by_keywords(["test", "knowledge"])
        assert len(results) >= 1
        found_our_entry = any(r["id"] == entry_id for r in results)
        assert found_our_entry
        print(f"Found in search: {len(results)} entries")
        
        # Clean up
        await db_service.execute_query(
            "DELETE FROM research.knowledge_base WHERE id = $1",
            entry_id
        )
        
    finally:
        await db_service.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])