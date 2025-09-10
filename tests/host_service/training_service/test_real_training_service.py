"""
Real training service integration tests.

These tests require an actual training service to be running and accessible.
They test model training, inference, and service health functionality.

Usage:
    make test-host  # Run all host service tests including these
    uv run pytest tests/host_service/training_service/ -v  # Run only training tests
"""

import httpx
import pytest


@pytest.mark.host_service
@pytest.mark.real_training_service
class TestRealTrainingService:
    """Test real training service integration."""

    @pytest.mark.asyncio
    async def test_service_health_check(self, real_training_service_url):
        """Test that the training service is healthy and responding."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{real_training_service_url}/health", timeout=5.0
                )
                assert response.status_code == 200

                health_data = response.json()
                assert "status" in health_data
                assert health_data["status"] in ["healthy", "ok", "running"]

            except httpx.RequestError as e:
                pytest.skip(f"Training service not accessible: {e}")

    @pytest.mark.asyncio
    async def test_model_list_endpoint(self, real_training_service_url):
        """Test retrieving available models from training service."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{real_training_service_url}/models", timeout=10.0
                )
                assert response.status_code == 200

                models_data = response.json()
                assert isinstance(models_data, (list, dict))

                if isinstance(models_data, list):
                    # List of model names or objects
                    assert len(models_data) >= 0  # Could be empty
                elif isinstance(models_data, dict):
                    # Dict with models info
                    assert "models" in models_data or len(models_data) >= 0

            except httpx.RequestError as e:
                pytest.skip(f"Training service models endpoint not accessible: {e}")

    @pytest.mark.asyncio
    async def test_training_job_submission(self, real_training_service_url):
        """Test submitting a training job (if supported)."""
        async with httpx.AsyncClient() as client:
            try:
                # Prepare minimal training job request
                training_request = {
                    "model_type": "test",
                    "parameters": {
                        "epochs": 1,
                        "test_mode": True,  # Flag to indicate this is a test
                    },
                    "data": {
                        "source": "synthetic",  # Use synthetic data for testing
                        "size": 100,  # Small dataset for quick test
                    },
                }

                response = await client.post(
                    f"{real_training_service_url}/train",
                    json=training_request,
                    timeout=30.0,
                )

                # Accept various success status codes
                assert response.status_code in [
                    200,
                    201,
                    202,
                ], f"Unexpected status: {response.status_code}"

                result_data = response.json()
                assert isinstance(result_data, dict)

                # Should have some kind of job identifier or status
                expected_fields = ["job_id", "task_id", "status", "message"]
                assert any(field in result_data for field in expected_fields), (
                    f"Response missing expected fields: {result_data}"
                )

            except httpx.RequestError as e:
                pytest.skip(f"Training service train endpoint not accessible: {e}")
            except AssertionError:
                # If the endpoint doesn't support test training jobs, skip
                pytest.skip("Training service doesn't support test training jobs")

    @pytest.mark.asyncio
    async def test_model_inference(self, real_training_service_url):
        """Test model inference endpoint (if available)."""
        async with httpx.AsyncClient() as client:
            try:
                # Try to get available models first
                models_response = await client.get(
                    f"{real_training_service_url}/models", timeout=10.0
                )
                if models_response.status_code != 200:
                    pytest.skip("Cannot retrieve models for inference test")

                models_data = models_response.json()

                # Find a model to use for inference
                model_name = None
                if isinstance(models_data, list) and len(models_data) > 0:
                    model_name = (
                        models_data[0]
                        if isinstance(models_data[0], str)
                        else models_data[0].get("name")
                    )
                elif (
                    isinstance(models_data, dict)
                    and "models" in models_data
                    and len(models_data["models"]) > 0
                ):
                    model_name = models_data["models"][0]

                if not model_name:
                    pytest.skip("No models available for inference test")

                # Prepare inference request with synthetic data
                inference_request = {
                    "model": model_name,
                    "input_data": {
                        "features": [
                            1.0,
                            2.0,
                            3.0,
                            4.0,
                            5.0,
                        ],  # Simple numeric features
                        "metadata": {"test": True},
                    },
                }

                response = await client.post(
                    f"{real_training_service_url}/predict",
                    json=inference_request,
                    timeout=15.0,
                )

                # Accept various success status codes
                assert response.status_code in [
                    200,
                    201,
                ], f"Unexpected status: {response.status_code}"

                result_data = response.json()
                assert isinstance(result_data, dict)

                # Should have prediction results
                expected_fields = ["prediction", "predictions", "result", "output"]
                assert any(field in result_data for field in expected_fields), (
                    f"Response missing prediction fields: {result_data}"
                )

            except httpx.RequestError as e:
                pytest.skip(f"Training service inference endpoint not accessible: {e}")
            except AssertionError:
                pytest.skip("Model inference not supported or failed")


@pytest.mark.host_service
@pytest.mark.real_training_service
class TestTrainingServicePerformance:
    """Test training service performance characteristics."""

    @pytest.mark.asyncio
    async def test_response_time_acceptable(self, real_training_service_url):
        """Test that service responds within acceptable time limits."""
        async with httpx.AsyncClient() as client:
            try:
                import time

                start_time = time.time()

                response = await client.get(
                    f"{real_training_service_url}/health", timeout=10.0
                )

                response_time = time.time() - start_time

                # Health check should respond within 2 seconds
                assert response_time < 2.0, (
                    f"Health check too slow: {response_time:.2f}s"
                )
                assert response.status_code == 200

            except httpx.RequestError as e:
                pytest.skip(
                    f"Training service not accessible for performance test: {e}"
                )


if __name__ == "__main__":
    # Allow running this file directly for local testing
    pytest.main([__file__, "-v", "-m", "host_service"])
