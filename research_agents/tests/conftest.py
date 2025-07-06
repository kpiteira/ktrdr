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
    app = create_app()
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client for API testing."""
    return TestClient(test_app)


@pytest_asyncio.fixture
async def async_test_client(test_app):
    """Create an async test client for API testing."""
    async with AsyncClient(app=test_app, base_url="http://test") as client:
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