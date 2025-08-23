#!/usr/bin/env python3
"""
Phase 4 Integration Testing - Focused GPU Acceleration Validation

Tests the actual implementation of GPU acceleration training host service
to validate Phase 1-3 integration and functionality.
"""

import httpx
import pytest
import pytest_asyncio


class TestPhase4Integration:
    """Phase 4 integration tests for GPU acceleration implementation."""

    @pytest_asyncio.fixture
    async def training_host_client(self):
        """HTTP client for training host service."""
        async with httpx.AsyncClient(
            base_url="http://localhost:5002", timeout=30.0
        ) as client:
            # Verify service is running
            try:
                response = await client.get("/health")
                if response.status_code != 200:
                    pytest.skip("Training host service not running")
                yield client
            except httpx.ConnectError:
                pytest.skip("Training host service not available")

    @pytest_asyncio.fixture
    async def ib_host_client(self):
        """HTTP client for IB host service."""
        async with httpx.AsyncClient(
            base_url="http://localhost:5001", timeout=30.0
        ) as client:
            # Verify service is running
            try:
                response = await client.get("/health")
                if response.status_code != 200:
                    pytest.skip("IB host service not running")
                yield client
            except httpx.ConnectError:
                pytest.skip("IB host service not available")

    @pytest.mark.asyncio
    async def test_training_host_service_info(self, training_host_client):
        """Test training host service basic info endpoint."""
        response = await training_host_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "Training Host Service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "gpu_available" in data
        assert "gpu_device_count" in data

    @pytest.mark.asyncio
    async def test_training_host_health_endpoint(self, training_host_client):
        """Test training host service health endpoint."""
        response = await training_host_client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["healthy"] is True
        assert data["service"] == "training-host"
        assert data["status"] == "operational"

    @pytest.mark.asyncio
    async def test_gpu_status_via_health_detailed(self, training_host_client):
        """Test GPU status via detailed health endpoint."""
        response = await training_host_client.get("/health/detailed")
        assert response.status_code == 200

        data = response.json()
        # Should always return GPU info in detailed health
        assert "gpu_available" in data
        assert "gpu_device_count" in data

    @pytest.mark.asyncio
    async def test_training_endpoints_available(self, training_host_client):
        """Test that training endpoints are available."""
        # Test training start endpoint exists
        response = await training_host_client.post(
            "/training/start",
            json={
                "strategy_name": "invalid_test",
                "timeframes": ["1h"],
                "data_start": "2023-01-01",
                "data_end": "2023-01-02",
            },
        )
        # Should get validation error, not 404
        assert response.status_code in [400, 422, 500]  # Not 404 (not found)

    @pytest.mark.asyncio
    async def test_ib_host_service_integration(self, ib_host_client):
        """Test IB host service is running and responsive."""
        response = await ib_host_client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["service"] == "IB Connector Host Service"
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_service_coordination(self, training_host_client, ib_host_client):
        """Test that both services are running and coordinated."""
        # Test both services respond
        training_response = await training_host_client.get("/health")
        ib_response = await ib_host_client.get("/health")

        assert training_response.status_code == 200
        assert ib_response.status_code == 200

        training_data = training_response.json()
        ib_data = ib_response.json()

        assert training_data["healthy"] is True
        assert ib_data["healthy"] is True or ib_data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_gpu_acceleration_configuration(self, training_host_client):
        """Test GPU acceleration configuration is properly detected."""
        response = await training_host_client.get("/")
        assert response.status_code == 200

        data = response.json()
        # Should detect GPU availability (true if GPU present, false if not)
        assert isinstance(data["gpu_available"], bool)
        assert isinstance(data["gpu_device_count"], int)
        assert data["gpu_device_count"] >= 0

    @pytest.mark.asyncio
    async def test_training_host_error_handling(self, training_host_client):
        """Test training host service error handling."""
        # Test invalid endpoint
        response = await training_host_client.get("/invalid/endpoint")
        assert response.status_code == 404

        # Test invalid training request
        response = await training_host_client.post("/training/start", json={})
        assert response.status_code in [400, 422]  # Validation error

    @pytest.mark.asyncio
    async def test_service_performance_baseline(self, training_host_client):
        """Test service performance meets baseline requirements."""
        import time

        # Test response time for health check
        start_time = time.time()
        response = await training_host_client.get("/health")
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < 1.0  # Should respond within 1 second

        # Test response time for detailed health (includes GPU info)
        start_time = time.time()
        response = await training_host_client.get("/health/detailed")
        detailed_response_time = time.time() - start_time

        assert response.status_code == 200
        assert detailed_response_time < 2.0  # Detailed health should be < 2s
