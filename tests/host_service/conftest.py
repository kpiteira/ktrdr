"""
Shared fixtures for host service tests.

These fixtures provide connections to real services and should only be used
when those services are actually running and available.
"""

import asyncio
import os

import pytest
from ib_async import IB


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def real_ib_connection():
    """
    Connect to real IB Gateway/TWS.

    This fixture requires:
    - IB Gateway or TWS running
    - Paper trading account recommended
    - Environment variables or defaults for connection

    Skips test if IB connection is not available.
    """
    ib = IB()
    try:
        # Use environment variables or defaults
        host = os.environ.get("IB_HOST", "127.0.0.1")
        port = int(os.environ.get("IB_PORT", "4002"))
        client_id = int(os.environ.get("IB_CLIENT_ID", "1"))

        await ib.connectAsync(host=host, port=port, clientId=client_id, timeout=5.0)

        # Wait for connection to stabilize
        await asyncio.sleep(2.0)

        yield ib

    except Exception as e:
        pytest.skip(f"IB Gateway/TWS not available: {e}")
    finally:
        if ib.isConnected():
            ib.disconnect()


@pytest.fixture(scope="session")
def real_training_service_url():
    """
    Get real training service URL.

    Returns URL for real training service if configured and available.
    Skips test if service is not available.
    """
    url = os.environ.get("TRAINING_SERVICE_URL")
    if not url:
        pytest.skip("Training service URL not configured (set TRAINING_SERVICE_URL)")

    return url


@pytest.mark.host_service
class HostServiceTestBase:
    """Base class for host service tests."""

    def setup_method(self):
        """Setup for each test method."""
        pass

    def teardown_method(self):
        """Cleanup for each test method."""
        pass
