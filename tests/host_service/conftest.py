"""
Shared fixtures for host service tests.

These fixtures provide connections to real services and should only be used
when those services are actually running and available.
"""
import pytest
import asyncio
from typing import Optional
from ib_insync import IB
from ktrdr.config.config_manager import ConfigManager


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for session scope."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")  
def config_manager():
    """Load configuration for host service tests."""
    return ConfigManager.get_instance()


@pytest.fixture(scope="session")
async def real_ib_connection(config_manager):
    """
    Connect to real IB Gateway/TWS.
    
    This fixture requires:
    - IB Gateway or TWS running
    - Paper trading account recommended
    - Proper configuration in config files
    
    Skips test if IB connection is not available.
    """
    ib = IB()
    try:
        # Try to connect to IB Gateway (default port 4002) or TWS (port 7497)
        host = config_manager.get("ib.host", "127.0.0.1")
        port = config_manager.get("ib.port", 4002)
        client_id = config_manager.get("ib.client_id", 1)
        
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
def real_training_service_url(config_manager):
    """
    Get real training service URL.
    
    Returns URL for real training service if configured and available.
    Skips test if service is not available.
    """
    url = config_manager.get("training.service_url", None)
    if not url:
        pytest.skip("Training service URL not configured")
    
    # Could add a health check here if the service has a health endpoint
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