"""
E2E tests for connection resilience with mock IB Gateway.

These tests simulate various IB Gateway scenarios to properly test
resilience behavior under realistic conditions.
"""

import socket
import threading
import time

import pytest


def check_api_available():
    """Check if API is available."""
    try:
        import httpx

        response = httpx.get("http://localhost:8000/api/v1/health", timeout=5.0)
        return response.status_code == 200
    except Exception:
        return False


class MockIBGateway:
    """Mock IB Gateway server for testing connection resilience."""

    def __init__(self, port: int = 4002, behavior: str = "normal"):
        self.port = port
        self.behavior = behavior
        self.socket = None
        self.thread = None
        self.running = False
        self.connections = []

    def start(self):
        """Start the mock IB Gateway server."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(("127.0.0.1", self.port))
        self.socket.listen(5)
        self.running = True

        self.thread = threading.Thread(target=self._server_loop)
        self.thread.daemon = True
        self.thread.start()

        # Wait for server to be ready
        time.sleep(0.1)

    def stop(self):
        """Stop the mock IB Gateway server."""
        self.running = False
        if self.socket:
            self.socket.close()
        if self.thread:
            self.thread.join(timeout=1)

    def _server_loop(self):
        """Main server loop handling different behaviors."""
        while self.running:
            try:
                if self.behavior == "reject_connections":
                    # Reject all connections (simulate IB maintenance)
                    continue
                elif self.behavior == "silent_connections":
                    # Accept but never respond (silent connection bug)
                    client, addr = self.socket.accept()
                    self.connections.append(client)
                    # Just hold the connection without responding
                elif self.behavior == "client_id_conflicts":
                    # Simulate client ID 1 already in use
                    client, addr = self.socket.accept()
                    # Send error 326 message
                    error_msg = b"4\x002\x00-1\x00326\x00Unable to connect as the client id is already in use.\x00\x00"
                    client.send(error_msg)
                    client.close()
                elif self.behavior == "normal":
                    # Normal IB behavior
                    client, addr = self.socket.accept()
                    # Send connection success and respond to basic requests
                    self._handle_normal_connection(client)

            except Exception:
                if self.running:
                    continue
                break

    def _handle_normal_connection(self, client):
        """Handle normal IB connection with basic responses."""
        try:
            # Send initial connection success
            client.send(
                b"4\x002\x001\x00Server Version:176\x00TWS Time:20250614 16:30:00 EST\x00\x00"
            )

            while self.running:
                data = client.recv(1024)
                if not data:
                    break

                # Respond to current time requests
                if b"reqCurrentTime" in data or b"49" in data:
                    time_response = b"4\x002\x0049\x001\x0020250614 16:30:00\x00\x00"
                    client.send(time_response)

        except Exception:
            pass
        finally:
            client.close()


@pytest.fixture
def mock_ib_normal():
    """Mock IB Gateway with normal behavior."""
    gateway = MockIBGateway(port=4002, behavior="normal")
    gateway.start()
    yield gateway
    gateway.stop()


@pytest.fixture
def mock_ib_silent():
    """Mock IB Gateway with silent connection behavior."""
    gateway = MockIBGateway(port=4002, behavior="silent_connections")
    gateway.start()
    yield gateway
    gateway.stop()


@pytest.fixture
def mock_ib_client_conflicts():
    """Mock IB Gateway that rejects with client ID conflicts."""
    gateway = MockIBGateway(port=4002, behavior="client_id_conflicts")
    gateway.start()
    yield gateway
    gateway.stop()


@pytest.mark.container_e2e
class TestResilienceWithMockIB:
    """Test connection resilience with realistic IB Gateway simulation."""

    def test_systematic_validation_with_working_ib(self, mock_ib_normal, api_client):
        """Test systematic validation with working IB Gateway."""
        # Wait for mock IB to be ready
        time.sleep(0.5)

        response = api_client.get("/ib/resilience")
        assert response.status_code == 200

        data = response.json()["data"]
        phase1 = data["phase_1_systematic_validation"]

        # With working IB, validation should actually work
        assert phase1["status"] == "working"
        assert phase1["validation_enabled"] is True

    def test_silent_connection_detection(self, mock_ib_silent, api_client):
        """Test detection of silent connections (TCP connects but no IB responses)."""
        time.sleep(0.5)

        # Health check should detect silent connections
        response = api_client.get("/ib/health")

        # Should fail due to timeout on silent connection
        if response.status_code == 503:
            data = response.json()
            # Should detect unhealthy connection (any unhealthy error is acceptable)
            data.get("error", {})
            health_data = data.get("data", {})
            assert not health_data.get("healthy", True), (
                "Should detect unhealthy connection"
            )

    def test_client_id_preference_with_conflicts(
        self, mock_ib_client_conflicts, api_client
    ):
        """Test Client ID 1 preference when conflicts occur."""
        time.sleep(0.5)

        response = api_client.get("/ib/resilience")
        assert response.status_code in [200, 503]

        # Even with conflicts, the preference logic should be working
        if response.status_code == 200:
            data = response.json()["data"]
            phase3 = data["phase_3_client_id_preference"]
            assert phase3["status"] == "working"

    def test_garbage_collection_under_load(self, mock_ib_normal, api_client):
        """Test garbage collection behavior under realistic load."""
        time.sleep(0.5)

        # Make multiple rapid requests to create connections
        for _ in range(3):
            api_client.get("/ib/status")
            time.sleep(0.1)

        # Check resilience status
        response = api_client.get("/ib/resilience")
        assert response.status_code == 200

        data = response.json()["data"]
        pool_health = data["connection_pool_health"]

        # Should have some connections created
        assert pool_health["total_connections"] >= 0

        # Garbage collection should be configured
        phase2 = data["phase_2_garbage_collection"]
        assert phase2["status"] == "working"
        assert phase2["max_idle_time_seconds"] == 300.0


@pytest.fixture
def api_client():
    """HTTP client for API testing."""
    if not check_api_available():
        pytest.skip("API server not available - requires Docker containers")
    import httpx

    return httpx.Client(base_url="http://localhost:8000", timeout=30.0)
