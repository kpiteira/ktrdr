"""
Pytest configuration and fixtures for research agents tests
"""

import asyncio
import os
import pytest
import pytest_asyncio
from typing import AsyncGenerator, Generator
from uuid import uuid4

# Import test dependencies
try:
    import asyncpg
    from fastapi.testclient import TestClient
    from httpx import AsyncClient
except ImportError:
    pytest.skip("Test dependencies not available", allow_module_level=True)

from research_agents.services.database import (
    ResearchDatabaseService, 
    DatabaseConfig,
    create_database_service
)
from research_agents.services.api import create_app
from datetime import datetime


# Test database configuration
TEST_DB_CONFIG = DatabaseConfig(
    host=os.getenv("TEST_DB_HOST", "localhost"),
    port=int(os.getenv("TEST_DB_PORT", "5433")),
    database=os.getenv("TEST_DB_NAME", "research_agents_test"),
    username=os.getenv("TEST_DB_USER", "research_admin"),
    password=os.getenv("TEST_DB_PASSWORD", "research_dev_password"),
    min_connections=1,
    max_connections=5
)


@pytest_asyncio.fixture
async def test_database() -> AsyncGenerator[ResearchDatabaseService, None]:
    """
    Create a test database instance.
    
    This fixture assumes a test database is available. In real testing,
    you might want to create a temporary database or use docker-compose
    to spin up a test postgres instance.
    """
    # Try to connect to the research database for testing
    # In production tests, you'd use a separate test database
    db_service = ResearchDatabaseService(TEST_DB_CONFIG)
    
    try:
        await db_service.initialize()
        
        # Verify database connection
        health = await db_service.health_check()
        if health["status"] != "healthy":
            pytest.skip("Test database not available")
        
        yield db_service
        
    except Exception as e:
        pytest.skip(f"Test database not available: {e}")
    finally:
        await db_service.close()


@pytest_asyncio.fixture
async def clean_database(test_database: ResearchDatabaseService) -> ResearchDatabaseService:
    """
    Provide a clean database state for each test.
    
    This fixture cleans up test data after each test to ensure isolation.
    """
    # Clean up any existing test data before the test
    await _cleanup_test_data(test_database)
    
    yield test_database
    
    # Clean up test data after the test
    await _cleanup_test_data(test_database)


async def _cleanup_test_data(db: ResearchDatabaseService) -> None:
    """Clean up test data from the database."""
    try:
        # Delete test experiments
        await db.execute_query(
            "DELETE FROM research.experiments WHERE experiment_name LIKE 'TEST_%'"
        )
        
        # Delete test knowledge entries
        await db.execute_query(
            "DELETE FROM research.knowledge_base WHERE title LIKE 'TEST_%'"
        )
        
        # Delete test agent states (but keep seed data)
        await db.execute_query(
            "DELETE FROM research.agent_states WHERE agent_id LIKE 'test-%'"
        )
        
        # Delete test sessions
        await db.execute_query(
            "DELETE FROM research.sessions WHERE session_name LIKE 'TEST_%'"
        )
        
    except Exception as e:
        # If cleanup fails, it's not critical for tests
        print(f"Warning: Test cleanup failed: {e}")


@pytest.fixture
def test_app():
    """Create a test FastAPI application."""
    from research_agents.services.api import create_app
    from unittest.mock import AsyncMock
    
    # Get the app but skip lifespan 
    import os
    os.environ["TESTING"] = "1"  # Signal to skip database initialization
    
    app = create_app()
    
    # Create a mock database service for testing
    mock_db = AsyncMock()
    mock_db.health_check.return_value = {"status": "healthy", "host": "test"}
    mock_db.get_active_agents.return_value = []
    
    # Session-related mocks
    test_session_id = "12345678-1234-5678-9012-123456789012"
    mock_db.create_session.return_value = test_session_id 
    mock_db.execute_query.return_value = []  # Default empty list for checking existing sessions
    
    # Store session data for dynamic responses
    created_sessions = {}
    session_counter = 0
    
    def mock_create_session_side_effect(session_name, description=None, strategic_goals=None, priority_areas=None):
        nonlocal session_counter
        session_counter += 1
        # Generate unique session ID for each session
        session_id = f"12345678-1234-5678-9012-12345678901{session_counter}"
        
        # Store the created session data
        created_sessions[session_id] = {
            "id": session_id,
            "session_name": session_name,
            "description": description,
            "status": "active",
            "started_at": datetime(2024, 1, 1),
            "strategic_goals": strategic_goals or [],
            "priority_areas": priority_areas or []
        }
        return session_id
    
    mock_db.create_session.side_effect = mock_create_session_side_effect
    
    # Create proper responses for session data
    def mock_execute_query_side_effect(*args, **kwargs):
        query = args[0] if args else ""
        fetch = kwargs.get("fetch", "none")
        
        if "SELECT id, session_name, description" in query and fetch == "one":
            # Extract session ID from the query for specific session lookup
            session_id_param = args[1] if len(args) > 1 else None
            
            # Convert UUID to string for consistent lookup
            if session_id_param:
                session_id_str = str(session_id_param)
                
                if session_id_str in created_sessions:
                    return created_sessions[session_id_str]
                else:
                    # Session ID requested but not found - return None for 404
                    return None
            elif created_sessions:
                # No specific ID, return the most recently created session
                return list(created_sessions.values())[-1]
            else:
                # Fallback for when no session was created yet
                return {
                    "id": test_session_id,
                    "session_name": "Test Session",
                    "description": "Test description",
                    "status": "active",
                    "started_at": datetime(2024, 1, 1),
                    "strategic_goals": [],
                    "priority_areas": []
                }
        elif "SELECT id FROM research.sessions WHERE session_name" in query and fetch == "all":
            # Check for duplicate session names
            session_name_param = args[1] if len(args) > 1 else None
            if session_name_param:
                # Check if this session name already exists
                for session in created_sessions.values():
                    if session["session_name"] == session_name_param:
                        return [{"id": session["id"]}]  # Return non-empty to indicate duplicate
            return []  # Return empty list if no duplicate found
        elif "SELECT id, session_name, description, status, started_at" in query and "ORDER BY started_at DESC" in query:
            # Return list of sessions for listing endpoint
            return list(created_sessions.values())
        elif "SELECT * FROM research.knowledge_base WHERE id = $1" in query and fetch == "one":
            # Knowledge entry retrieval by ID
            entry_id_param = args[1] if len(args) > 1 else None
            if entry_id_param:
                entry_id_str = str(entry_id_param)
                return created_knowledge.get(entry_id_str)
            return None
        elif "SELECT * FROM research.knowledge_base ORDER BY created_at DESC LIMIT" in query and fetch == "all":
            # Recent knowledge entries
            limit_param = args[0] if args else 10
            return list(created_knowledge.values())[:limit_param]
        else:
            return []
    
    mock_db.execute_query.side_effect = mock_execute_query_side_effect
    
    # Experiment-related mocks
    test_experiment_id = "87654321-4321-8765-4321-876543218765"
    created_experiments = {}
    experiment_counter = 0
    
    def mock_create_experiment_side_effect(session_id, experiment_name, hypothesis, experiment_type, configuration=None):
        nonlocal experiment_counter
        experiment_counter += 1
        # Generate unique experiment ID
        experiment_id = f"87654321-4321-8765-4321-87654321876{experiment_counter}"
        
        # Store the created experiment data
        created_experiments[experiment_id] = {
            "id": experiment_id,  # Database field name for create endpoint
            "experiment_id": experiment_id,  # Alias field name for response models
            "experiment_name": experiment_name,
            "hypothesis": hypothesis,
            "experiment_type": experiment_type,
            "status": "pending",
            "configuration": configuration or {},
            "session_id": str(session_id),
            "created_at": datetime(2024, 1, 1),
            "results": None,
            "fitness_score": None,
            "assigned_agent_name": None,
            "session_name": None,
            "started_at": None,
            "completed_at": None
        }
        return experiment_id
    
    mock_db.create_experiment.side_effect = mock_create_experiment_side_effect
    
    def mock_get_experiment_side_effect(experiment_id):
        experiment_id_str = str(experiment_id)
        return created_experiments.get(experiment_id_str)
    
    mock_db.get_experiment.side_effect = mock_get_experiment_side_effect
    
    # Add methods for experiment operations
    async def mock_update_experiment_status(experiment_id, status, results=None, fitness_score=None):
        experiment_id_str = str(experiment_id)
        if experiment_id_str in created_experiments:
            created_experiments[experiment_id_str]["status"] = status
            if results:
                created_experiments[experiment_id_str]["results"] = results
            if fitness_score:
                created_experiments[experiment_id_str]["fitness_score"] = fitness_score
            
            # Set completed_at timestamp for completed experiments
            if status == "completed":
                created_experiments[experiment_id_str]["completed_at"] = datetime(2024, 1, 2)  # Mock completion time
            elif status == "running" and not created_experiments[experiment_id_str]["started_at"]:
                created_experiments[experiment_id_str]["started_at"] = datetime(2024, 1, 1, 12, 0)  # Mock start time
    
    mock_db.update_experiment_status.side_effect = mock_update_experiment_status
    
    def mock_get_experiments_by_session_side_effect(session_id, status_filter=None):
        session_id_str = str(session_id)
        session_experiments = [
            exp for exp in created_experiments.values() 
            if exp["session_id"] == session_id_str
        ]
        if status_filter:
            session_experiments = [exp for exp in session_experiments if exp["status"] == status_filter]
        return session_experiments
    
    mock_db.get_experiments_by_session.side_effect = mock_get_experiments_by_session_side_effect
    
    # Knowledge base mocks
    created_knowledge = {}
    knowledge_counter = 0
    
    def mock_add_knowledge_entry_side_effect(content_type, title, content, summary=None, keywords=None, tags=None, quality_score=None, **kwargs):
        nonlocal knowledge_counter
        knowledge_counter += 1
        entry_id = f"11111111-2222-3333-4444-55555555555{knowledge_counter}"
        
        created_knowledge[entry_id] = {
            "id": entry_id,
            "content_type": content_type,
            "title": title,
            "content": content,
            "summary": summary,
            "keywords": keywords or [],
            "tags": tags or [],
            "quality_score": quality_score,
            "relevance_score": None,
            "created_at": datetime(2024, 1, 1)
        }
        return entry_id
    
    mock_db.add_knowledge_entry.side_effect = mock_add_knowledge_entry_side_effect
    
    def mock_search_knowledge_by_tags_side_effect(tags, content_type_filter=None, limit=10):
        results = []
        for entry in created_knowledge.values():
            if any(tag in entry["tags"] for tag in tags):
                if content_type_filter and entry["content_type"] != content_type_filter:
                    continue
                results.append(entry)
                if len(results) >= limit:
                    break
        return results
    
    mock_db.search_knowledge_by_tags.side_effect = mock_search_knowledge_by_tags_side_effect
    
    # Mock experiment statistics
    def mock_get_experiment_statistics_side_effect(session_id=None):
        if session_id:
            session_id_str = str(session_id)
            session_experiments = [
                exp for exp in created_experiments.values()
                if exp["session_id"] == session_id_str
            ]
        else:
            session_experiments = list(created_experiments.values())
        
        total = len(session_experiments)
        completed = len([exp for exp in session_experiments if exp["status"] == "completed"])
        failed = len([exp for exp in session_experiments if exp["status"] == "failed"])
        running = len([exp for exp in session_experiments if exp["status"] == "running"])
        queued = len([exp for exp in session_experiments if exp["status"] == "pending"])
        
        return {
            "total_experiments": total,
            "completed_experiments": completed,  # Full field name
            "pending_experiments": queued,  # Full field name  
            "failed": failed,
            "running": running,
            "queued": queued,
            "avg_fitness": 1.0,  # Mock value
            "max_fitness": 1.0,  # Mock value
            "high_quality_results": completed
        }
    
    mock_db.get_experiment_statistics.side_effect = mock_get_experiment_statistics_side_effect
    
    # Set the mock database on app state
    app.state.db = mock_db
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for API testing."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def async_test_client(test_app):
    """Create an async test client for API testing."""
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        yield client


@pytest.fixture
def sample_experiment_data():
    """Sample experiment data for testing."""
    return {
        "experiment_name": f"TEST_Sample_Experiment_{uuid4().hex[:8]}",
        "hypothesis": "Test hypothesis for sample experiment",
        "experiment_type": "test_strategy",
        "configuration": {
            "test_param": "test_value",
            "epochs": 10,
            "learning_rate": 0.001
        }
    }


@pytest.fixture
def sample_knowledge_data():
    """Sample knowledge base data for testing."""
    return {
        "content_type": "insight",
        "title": f"TEST_Sample_Insight_{uuid4().hex[:8]}",
        "content": "This is a test insight for validating knowledge base operations.",
        "summary": "Test insight summary",
        "keywords": ["test", "insight", "validation"],
        "tags": ["test_tag", "validation"],
        "quality_score": 0.85
    }


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing."""
    return {
        "agent_id": f"test-agent-{uuid4().hex[:8]}",
        "agent_type": "researcher",
        "status": "idle",
        "current_activity": "Testing agent functionality",
        "state_data": {"test_key": "test_value"},
        "memory_context": {"test_memory": "test_context"}
    }


# Test configuration
pytest.register_assert_rewrite("research_agents.tests.test_database")
pytest.register_assert_rewrite("research_agents.tests.test_api")
pytest.register_assert_rewrite("research_agents.tests.test_agents")