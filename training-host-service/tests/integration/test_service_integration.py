"""
Integration tests for the training host service.

These tests verify that the service components work together correctly
and can be run against a live service instance.
"""

import time

import pytest
import requests


@pytest.mark.integration
class TestServiceIntegration:
    """Integration tests for the full service."""

    def test_service_startup_and_health(self, integration_config):
        """Test that service starts up and reports healthy."""
        service_url = integration_config["service_url"]
        timeout = integration_config["health_check_timeout"]

        # Wait for service to be ready
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                response = requests.get(f"{service_url}/health", timeout=5)
                if response.status_code == 200:
                    break
            except requests.exceptions.RequestException:
                pass
            time.sleep(1)
        else:
            pytest.fail(f"Service did not become healthy within {timeout} seconds")

        # Test basic health check
        response = requests.get(f"{service_url}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["healthy"] is True
        assert data["service"] == "training-host"

    def test_detailed_health_check(self, integration_config):
        """Test detailed health check endpoint."""
        service_url = integration_config["service_url"]

        response = requests.get(f"{service_url}/health/detailed")
        assert response.status_code == 200
        data = response.json()

        assert data["healthy"] is True
        assert "gpu_available" in data
        assert "gpu_device_count" in data
        assert "system_memory_usage_percent" in data
        assert "gpu_manager_status" in data

    def test_root_endpoint(self, integration_config):
        """Test root service information endpoint."""
        service_url = integration_config["service_url"]

        response = requests.get(f"{service_url}/")
        assert response.status_code == 200
        data = response.json()

        assert data["service"] == "Training Host Service"
        assert data["version"] == "1.0.0"
        assert data["status"] == "running"
        assert "gpu_available" in data
        assert "gpu_device_count" in data

    def test_training_session_lifecycle(
        self, integration_config, sample_training_config
    ):
        """Test complete training session lifecycle."""
        service_url = integration_config["service_url"]
        training_timeout = integration_config["training_timeout"]

        # Start training session
        response = requests.post(
            f"{service_url}/training/start", json=sample_training_config, timeout=30
        )
        assert response.status_code == 200
        start_data = response.json()
        session_id = start_data["session_id"]
        assert start_data["status"] == "started"

        try:
            # Check session appears in listing
            response = requests.get(f"{service_url}/training/sessions")
            assert response.status_code == 200
            sessions_data = response.json()
            session_ids = [s["session_id"] for s in sessions_data["sessions"]]
            assert session_id in session_ids

            # Monitor training progress
            start_time = time.time()
            last_epoch = -1

            while time.time() - start_time < training_timeout:
                response = requests.get(f"{service_url}/training/status/{session_id}")
                assert response.status_code == 200
                status_data = response.json()

                current_epoch = status_data["progress"]["epoch"]
                if current_epoch > last_epoch:
                    print(
                        f"Training progress: Epoch {current_epoch}/{status_data['progress']['total_epochs']}"
                    )
                    last_epoch = current_epoch

                # Check if training completed
                if status_data["status"] in ["completed", "failed"]:
                    break

                # Check if training is progressing
                if status_data["status"] == "running" and current_epoch > 0:
                    # Training is progressing, we can stop it for testing
                    break

                time.sleep(2)

            # Stop training session
            stop_data = {"session_id": session_id, "save_checkpoint": False}
            response = requests.post(
                f"{service_url}/training/stop", json=stop_data, timeout=30
            )
            # Don't assert status code here as session might have completed naturally

            # Wait a bit for stop to take effect
            time.sleep(2)

            # Verify session is stopped
            response = requests.get(f"{service_url}/training/status/{session_id}")
            if response.status_code == 200:
                status_data = response.json()
                assert status_data["status"] in ["stopped", "completed", "failed"]

        finally:
            # Cleanup session
            try:
                requests.delete(
                    f"{service_url}/training/sessions/{session_id}", timeout=30
                )
            except Exception:
                pass  # Cleanup might fail if session was already cleaned up

    def test_concurrent_session_limit(self, integration_config, sample_training_config):
        """Test that concurrent session limits are enforced."""
        service_url = integration_config["service_url"]

        # Start first session
        response1 = requests.post(
            f"{service_url}/training/start", json=sample_training_config, timeout=30
        )
        assert response1.status_code == 200
        session_id1 = response1.json()["session_id"]

        try:
            # Try to start second session (should fail if limit is 1)
            response2 = requests.post(
                f"{service_url}/training/start", json=sample_training_config, timeout=30
            )

            if response2.status_code == 500:
                # Expected if concurrent session limit is 1
                assert "Maximum concurrent sessions" in response2.json()["detail"]
            else:
                # If it succeeded, we have a higher limit, clean up the second session
                session_id2 = response2.json()["session_id"]
                requests.delete(
                    f"{service_url}/training/sessions/{session_id2}", timeout=30
                )

        finally:
            # Cleanup first session
            try:
                requests.post(
                    f"{service_url}/training/stop",
                    json={"session_id": session_id1, "save_checkpoint": False},
                    timeout=30,
                )
                time.sleep(2)
                requests.delete(
                    f"{service_url}/training/sessions/{session_id1}", timeout=30
                )
            except Exception:
                pass

    def test_model_evaluation(self, integration_config):
        """Test model evaluation functionality."""
        service_url = integration_config["service_url"]

        evaluation_request = {
            "model_path": "/tmp/test_model.pth",
            "data_config": {"test_data": "sample_data", "batch_size": 32},
            "metrics": ["accuracy", "loss", "f1_score"],
        }

        response = requests.post(
            f"{service_url}/training/evaluate", json=evaluation_request, timeout=60
        )
        assert response.status_code == 200
        data = response.json()

        assert "evaluation_id" in data
        assert "results" in data
        assert "gpu_used" in data
        assert "evaluation_time_seconds" in data
        assert isinstance(data["results"], dict)

    def test_error_handling(self, integration_config):
        """Test service error handling."""
        service_url = integration_config["service_url"]

        # Test invalid training configuration
        invalid_config = {"invalid": "config"}
        response = requests.post(
            f"{service_url}/training/start", json=invalid_config, timeout=30
        )
        assert response.status_code == 422 or response.status_code == 500

        # Test getting status of non-existent session
        response = requests.get(f"{service_url}/training/status/nonexistent-session")
        assert response.status_code == 500

        # Test stopping non-existent session
        stop_data = {"session_id": "nonexistent-session", "save_checkpoint": False}
        response = requests.post(
            f"{service_url}/training/stop", json=stop_data, timeout=30
        )
        assert response.status_code == 500

    def test_service_resource_usage(self, integration_config):
        """Test that service manages resources properly."""
        service_url = integration_config["service_url"]

        # Get initial resource usage
        response = requests.get(f"{service_url}/health/detailed")
        assert response.status_code == 200
        initial_data = response.json()
        initial_data.get("gpu_memory_allocated_mb", 0)

        # Start training session to allocate resources
        training_config = {
            "model_config": {"type": "simple", "input_size": 10, "num_classes": 2},
            "training_config": {"epochs": 2, "batch_size": 16},
            "data_config": {"symbols": ["TEST"], "timeframes": ["1h"]},
            "gpu_config": {"memory_fraction": 0.2},
        }

        response = requests.post(
            f"{service_url}/training/start", json=training_config, timeout=30
        )
        if response.status_code == 200:
            session_id = response.json()["session_id"]

            try:
                # Check resource usage during training
                time.sleep(5)  # Let training start
                response = requests.get(f"{service_url}/health/detailed")
                if response.status_code == 200:
                    response.json()
                    # Resource usage might be higher during training
                    # This is mainly to verify the endpoint works during training

                # Stop training
                stop_data = {"session_id": session_id, "save_checkpoint": False}
                requests.post(
                    f"{service_url}/training/stop", json=stop_data, timeout=30
                )
                time.sleep(2)

                # Cleanup
                requests.delete(
                    f"{service_url}/training/sessions/{session_id}", timeout=30
                )

            except Exception as e:
                # If anything fails, still try to cleanup
                try:
                    requests.delete(
                        f"{service_url}/training/sessions/{session_id}", timeout=30
                    )
                except Exception:
                    pass
                raise e


@pytest.mark.integration_slow
class TestServicePerformance:
    """Performance tests for the service."""

    def test_response_times(self, integration_config, performance_config):
        """Test service response times under normal load."""
        service_url = integration_config["service_url"]
        max_response_time = performance_config["acceptable_response_time_ms"] / 1000.0

        # Test health check response time
        start_time = time.time()
        response = requests.get(f"{service_url}/health")
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < max_response_time, (
            f"Health check took {response_time:.3f}s, expected < {max_response_time:.3f}s"
        )

        # Test detailed health check response time
        start_time = time.time()
        response = requests.get(f"{service_url}/health/detailed")
        response_time = time.time() - start_time

        assert response.status_code == 200
        assert response_time < max_response_time * 2, (
            f"Detailed health check took {response_time:.3f}s"
        )

    def test_concurrent_requests(self, integration_config, performance_config):
        """Test service handling of concurrent requests."""
        service_url = integration_config["service_url"]
        num_concurrent = min(performance_config["requests_per_second"], 10)

        def make_health_request():
            try:
                response = requests.get(f"{service_url}/health", timeout=5)
                return response.status_code == 200
            except Exception:
                return False

        # Make concurrent health check requests
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_concurrent
        ) as executor:
            futures = [
                executor.submit(make_health_request) for _ in range(num_concurrent)
            ]
            results = [
                future.result() for future in concurrent.futures.as_completed(futures)
            ]

        success_rate = sum(results) / len(results)
        acceptable_success_rate = 1.0 - performance_config["acceptable_error_rate"]

        assert success_rate >= acceptable_success_rate, (
            f"Success rate {success_rate:.2%} below acceptable {acceptable_success_rate:.2%}"
        )
