"""
Integration tests for research agents API endpoints
"""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import AsyncClient


class TestResearchAPI:
    """Test suite for Research API endpoints"""

    def test_health_endpoint(self, test_client: TestClient):
        """Test health check endpoint"""
        response = test_client.get("/health")

        assert response.status_code == 200
        health_data = response.json()
        assert health_data["status"] == "healthy"
        assert "timestamp" in health_data
        assert "version" in health_data

    def test_root_endpoint(self, test_client: TestClient):
        """Test root endpoint"""
        response = test_client.get("/")

        assert response.status_code == 200
        root_data = response.json()
        assert "message" in root_data
        assert "version" in root_data
        assert root_data["message"] == "KTRDR Research Agents API"

    @pytest.mark.asyncio
    async def test_create_session_endpoint(self, async_test_client: AsyncClient):
        """Test session creation endpoint"""
        session_data = {
            "session_name": f"TEST_API_Session_{uuid4().hex[:8]}",
            "description": "Test session created via API",
        }

        response = await async_test_client.post("/sessions", json=session_data)

        assert response.status_code == 201
        response_data = response.json()
        assert "session_id" in response_data
        assert "session_name" in response_data
        assert response_data["session_name"] == session_data["session_name"]

        # Verify session_id is a valid UUID
        session_id = response_data["session_id"]
        assert UUID(session_id)  # This will raise ValueError if not valid UUID

    @pytest.mark.asyncio
    async def test_create_session_duplicate_name(self, async_test_client: AsyncClient):
        """Test creating session with duplicate name"""
        session_name = f"TEST_API_DuplicateSession_{uuid4().hex[:8]}"
        session_data = {"session_name": session_name, "description": "First session"}

        # Create first session
        response1 = await async_test_client.post("/sessions", json=session_data)
        assert response1.status_code == 201

        # Attempt to create duplicate
        response2 = await async_test_client.post("/sessions", json=session_data)
        assert response2.status_code == 409  # Conflict

        error_data = response2.json()
        assert "detail" in error_data
        assert "already exists" in error_data["detail"]

    @pytest.mark.asyncio
    async def test_get_session_endpoint(self, async_test_client: AsyncClient):
        """Test getting session by ID"""
        # Create session first
        session_data = {
            "session_name": f"TEST_API_GetSession_{uuid4().hex[:8]}",
            "description": "Test session for retrieval",
        }

        create_response = await async_test_client.post("/sessions", json=session_data)
        assert create_response.status_code == 201

        session_id = create_response.json()["session_id"]

        # Get session by ID
        get_response = await async_test_client.get(f"/sessions/{session_id}")
        assert get_response.status_code == 200

        session_info = get_response.json()
        assert session_info["session_name"] == session_data["session_name"]
        assert session_info["description"] == session_data["description"]
        assert session_info["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, async_test_client: AsyncClient):
        """Test getting non-existent session"""
        fake_session_id = str(uuid4())

        response = await async_test_client.get(f"/sessions/{fake_session_id}")
        assert response.status_code == 404

        error_data = response.json()
        assert "detail" in error_data
        assert "not found" in error_data["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_sessions_endpoint(self, async_test_client: AsyncClient):
        """Test listing sessions"""
        # Create multiple test sessions
        session_names = [
            f"TEST_API_ListSession_{i}_{uuid4().hex[:8]}" for i in range(3)
        ]

        for session_name in session_names:
            session_data = {
                "session_name": session_name,
                "description": f"Test session {session_name}",
            }
            response = await async_test_client.post("/sessions", json=session_data)
            assert response.status_code == 201

        # List sessions
        list_response = await async_test_client.get("/sessions")
        assert list_response.status_code == 200

        sessions = list_response.json()
        assert isinstance(sessions, list)

        # Verify our test sessions are in the list
        session_names_in_response = [s["session_name"] for s in sessions]
        for test_name in session_names:
            assert test_name in session_names_in_response

    @pytest.mark.asyncio
    async def test_create_experiment_endpoint(self, async_test_client: AsyncClient):
        """Test experiment creation endpoint"""
        # Create session first
        session_data = {
            "session_name": f"TEST_API_ExpSession_{uuid4().hex[:8]}",
            "description": "Test session for experiments",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        # Create experiment
        experiment_data = {
            "session_id": session_id,
            "experiment_name": f"TEST_API_Experiment_{uuid4().hex[:8]}",
            "hypothesis": "Test hypothesis via API",
            "experiment_type": "test_strategy",
            "configuration": {"test_param": "test_value", "epochs": 10},
        }

        response = await async_test_client.post("/experiments", json=experiment_data)
        assert response.status_code == 201

        response_data = response.json()
        assert "experiment_id" in response_data
        assert "experiment_name" in response_data
        assert response_data["experiment_name"] == experiment_data["experiment_name"]

        # Verify experiment_id is valid UUID
        experiment_id = response_data["experiment_id"]
        assert UUID(experiment_id)

    @pytest.mark.asyncio
    async def test_get_experiment_endpoint(self, async_test_client: AsyncClient):
        """Test getting experiment by ID"""
        # Create session and experiment
        session_data = {
            "session_name": f"TEST_API_GetExpSession_{uuid4().hex[:8]}",
            "description": "Test session for experiment retrieval",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        experiment_data = {
            "session_id": session_id,
            "experiment_name": f"TEST_API_GetExperiment_{uuid4().hex[:8]}",
            "hypothesis": "Test hypothesis for retrieval",
            "experiment_type": "test_strategy",
            "configuration": {"test_param": "test_value"},
        }

        create_response = await async_test_client.post(
            "/experiments", json=experiment_data
        )
        experiment_id = create_response.json()["experiment_id"]

        # Get experiment by ID
        get_response = await async_test_client.get(f"/experiments/{experiment_id}")
        assert get_response.status_code == 200

        experiment_info = get_response.json()
        assert experiment_info["experiment_name"] == experiment_data["experiment_name"]
        assert experiment_info["hypothesis"] == experiment_data["hypothesis"]
        assert experiment_info["status"] == "pending"

    @pytest.mark.asyncio
    async def test_update_experiment_status_endpoint(
        self, async_test_client: AsyncClient
    ):
        """Test updating experiment status"""
        # Create session and experiment
        session_data = {
            "session_name": f"TEST_API_UpdateExpSession_{uuid4().hex[:8]}",
            "description": "Test session for experiment status updates",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        experiment_data = {
            "session_id": session_id,
            "experiment_name": f"TEST_API_UpdateExperiment_{uuid4().hex[:8]}",
            "hypothesis": "Test hypothesis for status update",
            "experiment_type": "test_strategy",
            "configuration": {"test_param": "test_value"},
        }

        create_response = await async_test_client.post(
            "/experiments", json=experiment_data
        )
        experiment_id = create_response.json()["experiment_id"]

        # Update experiment status
        update_data = {"status": "running"}
        update_response = await async_test_client.patch(
            f"/experiments/{experiment_id}/status", json=update_data
        )
        assert update_response.status_code == 200

        # Verify status was updated
        get_response = await async_test_client.get(f"/experiments/{experiment_id}")
        experiment_info = get_response.json()
        assert experiment_info["status"] == "running"

    @pytest.mark.asyncio
    async def test_complete_experiment_endpoint(self, async_test_client: AsyncClient):
        """Test completing an experiment with results"""
        # Create session and experiment
        session_data = {
            "session_name": f"TEST_API_CompleteExpSession_{uuid4().hex[:8]}",
            "description": "Test session for experiment completion",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        experiment_data = {
            "session_id": session_id,
            "experiment_name": f"TEST_API_CompleteExperiment_{uuid4().hex[:8]}",
            "hypothesis": "Test hypothesis for completion",
            "experiment_type": "test_strategy",
            "configuration": {"test_param": "test_value"},
        }

        create_response = await async_test_client.post(
            "/experiments", json=experiment_data
        )
        experiment_id = create_response.json()["experiment_id"]

        # Complete experiment
        completion_data = {
            "results": {
                "fitness_score": 0.85,
                "profit_factor": 1.25,
                "total_trades": 150,
            },
            "status": "completed",
        }

        complete_response = await async_test_client.patch(
            f"/experiments/{experiment_id}/complete", json=completion_data
        )
        assert complete_response.status_code == 200

        # Verify completion
        get_response = await async_test_client.get(f"/experiments/{experiment_id}")
        experiment_info = get_response.json()
        assert experiment_info["status"] == "completed"
        assert experiment_info["results"] == completion_data["results"]
        assert experiment_info["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_list_experiments_by_session(self, async_test_client: AsyncClient):
        """Test listing experiments by session"""
        # Create session
        session_data = {
            "session_name": f"TEST_API_ListExpSession_{uuid4().hex[:8]}",
            "description": "Test session for experiment listing",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        # Create multiple experiments
        experiment_names = [
            f"TEST_API_ListExperiment_{i}_{uuid4().hex[:8]}" for i in range(3)
        ]

        for exp_name in experiment_names:
            experiment_data = {
                "session_id": session_id,
                "experiment_name": exp_name,
                "hypothesis": f"Test hypothesis for {exp_name}",
                "experiment_type": "test_strategy",
                "configuration": {"test_param": "test_value"},
            }

            response = await async_test_client.post(
                "/experiments", json=experiment_data
            )
            assert response.status_code == 201

        # List experiments by session
        list_response = await async_test_client.get(
            f"/sessions/{session_id}/experiments"
        )
        assert list_response.status_code == 200

        experiments = list_response.json()
        assert isinstance(experiments, list)
        assert len(experiments) == 3

        # Verify all experiments belong to the session
        for exp in experiments:
            assert exp["session_id"] == session_id
            assert exp["experiment_name"] in experiment_names

    @pytest.mark.asyncio
    async def test_create_knowledge_entry_endpoint(
        self, async_test_client: AsyncClient
    ):
        """Test creating knowledge base entry"""
        knowledge_data = {
            "content_type": "insight",
            "title": f"TEST_API_Knowledge_{uuid4().hex[:8]}",
            "content": "Test knowledge content via API",
            "summary": "Test summary",
            "keywords": ["test", "api", "knowledge"],
            "tags": ["test_tag", "api_test"],
            "quality_score": 0.85,
        }

        response = await async_test_client.post("/knowledge", json=knowledge_data)
        assert response.status_code == 201

        response_data = response.json()
        assert "entry_id" in response_data
        assert "title" in response_data
        assert response_data["title"] == knowledge_data["title"]

        # Verify entry_id is valid UUID
        entry_id = response_data["entry_id"]
        assert UUID(entry_id)

    @pytest.mark.asyncio
    async def test_get_knowledge_entry_endpoint(self, async_test_client: AsyncClient):
        """Test getting knowledge entry by ID"""
        # Create knowledge entry
        knowledge_data = {
            "content_type": "insight",
            "title": f"TEST_API_GetKnowledge_{uuid4().hex[:8]}",
            "content": "Test knowledge content for retrieval",
            "summary": "Test summary",
            "keywords": ["test", "retrieval"],
            "tags": ["test_tag"],
            "quality_score": 0.90,
        }

        create_response = await async_test_client.post(
            "/knowledge", json=knowledge_data
        )
        entry_id = create_response.json()["entry_id"]

        # Get knowledge entry
        get_response = await async_test_client.get(f"/knowledge/{entry_id}")
        assert get_response.status_code == 200

        entry_info = get_response.json()
        assert entry_info["title"] == knowledge_data["title"]
        assert entry_info["content"] == knowledge_data["content"]
        assert entry_info["quality_score"] == knowledge_data["quality_score"]
        assert set(entry_info["keywords"]) == set(knowledge_data["keywords"])

    @pytest.mark.asyncio
    async def test_search_knowledge_endpoint(self, async_test_client: AsyncClient):
        """Test searching knowledge entries"""
        # Create knowledge entries with different tags
        knowledge_entries = [
            {
                "content_type": "insight",
                "title": f"TEST_API_SearchKnowledge_ML_{uuid4().hex[:8]}",
                "content": "Machine learning insights",
                "summary": "ML summary",
                "keywords": ["machine_learning", "test"],
                "tags": ["ml", "test_search"],
                "quality_score": 0.85,
            },
            {
                "content_type": "strategy",
                "title": f"TEST_API_SearchKnowledge_Strategy_{uuid4().hex[:8]}",
                "content": "Trading strategy insights",
                "summary": "Strategy summary",
                "keywords": ["trading", "strategy", "test"],
                "tags": ["strategy", "test_search"],
                "quality_score": 0.90,
            },
        ]

        for entry_data in knowledge_entries:
            response = await async_test_client.post("/knowledge", json=entry_data)
            assert response.status_code == 201

        # Search by tags
        search_response = await async_test_client.get(
            "/knowledge/search?tags=test_search"
        )
        assert search_response.status_code == 200

        search_results = search_response.json()
        assert isinstance(search_results, list)
        assert len(search_results) == 2

        # Verify search results
        titles = [result["title"] for result in search_results]
        assert any("ML" in title for title in titles)
        assert any("Strategy" in title for title in titles)

    @pytest.mark.asyncio
    async def test_get_agent_status_endpoint(self, async_test_client: AsyncClient):
        """Test getting agent status"""
        response = await async_test_client.get("/agents/status")
        assert response.status_code == 200

        status_data = response.json()
        assert "active_agents" in status_data
        assert "total_agents" in status_data
        assert "agent_details" in status_data
        assert isinstance(status_data["agent_details"], list)

    @pytest.mark.asyncio
    async def test_get_experiment_statistics_endpoint(
        self, async_test_client: AsyncClient
    ):
        """Test getting experiment statistics"""
        # Create session first
        session_data = {
            "session_name": f"TEST_API_StatsSession_{uuid4().hex[:8]}",
            "description": "Test session for statistics",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        # Create and complete some experiments
        for i in range(3):
            experiment_data = {
                "session_id": session_id,
                "experiment_name": f"TEST_API_StatsExperiment_{i}_{uuid4().hex[:8]}",
                "hypothesis": f"Test hypothesis {i}",
                "experiment_type": "test_strategy",
                "configuration": {"test_param": i},
            }

            create_response = await async_test_client.post(
                "/experiments", json=experiment_data
            )
            experiment_id = create_response.json()["experiment_id"]

            # Complete some experiments
            if i < 2:
                completion_data = {
                    "results": {"fitness_score": 0.8 + i * 0.1},
                    "status": "completed",
                }
                await async_test_client.patch(
                    f"/experiments/{experiment_id}/complete", json=completion_data
                )

        # Get statistics
        stats_response = await async_test_client.get(
            f"/sessions/{session_id}/statistics"
        )
        assert stats_response.status_code == 200

        stats = stats_response.json()
        assert "total_experiments" in stats
        assert "completed_experiments" in stats
        assert "pending_experiments" in stats
        assert stats["total_experiments"] == 3
        assert stats["completed_experiments"] == 2
        assert stats["pending_experiments"] == 1

    @pytest.mark.asyncio
    async def test_api_error_handling(self, async_test_client: AsyncClient):
        """Test API error handling"""
        # Test invalid JSON
        response = await async_test_client.post("/sessions", data="invalid json")
        assert response.status_code == 422

        # Test missing required fields
        response = await async_test_client.post("/sessions", json={})
        assert response.status_code == 422

        # Test invalid UUID
        response = await async_test_client.get("/sessions/invalid-uuid")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_api_validation(self, async_test_client: AsyncClient):
        """Test API request validation"""
        # Test session creation with invalid data
        invalid_session_data = {
            "session_name": "",  # Empty string should be invalid
            "description": "Test",
        }

        response = await async_test_client.post("/sessions", json=invalid_session_data)
        assert response.status_code == 422

        # Test experiment creation with invalid experiment type
        session_data = {
            "session_name": f"TEST_API_ValidationSession_{uuid4().hex[:8]}",
            "description": "Test session for validation",
        }

        session_response = await async_test_client.post("/sessions", json=session_data)
        session_id = session_response.json()["session_id"]

        invalid_experiment_data = {
            "session_id": session_id,
            "experiment_name": "Test Experiment",
            "hypothesis": "Test hypothesis",
            "experiment_type": "invalid_type",  # Should be validated
            "configuration": {},
        }

        response = await async_test_client.post(
            "/experiments", json=invalid_experiment_data
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_api_rate_limiting(self, async_test_client: AsyncClient):
        """Test API rate limiting (if implemented)"""
        # This test depends on rate limiting being implemented
        # For now, just verify multiple requests don't cause issues

        responses = []
        for _i in range(10):
            response = await async_test_client.get("/health")
            responses.append(response)

        # All health checks should succeed
        for response in responses:
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_api_cors_headers(self, async_test_client: AsyncClient):
        """Test CORS headers if configured"""
        response = await async_test_client.get("/health")

        # Check for basic response success
        assert response.status_code == 200

        # If CORS is configured, headers should be present
        # This is optional depending on API configuration
        headers = response.headers
        assert "content-type" in headers
        assert headers["content-type"] == "application/json"
