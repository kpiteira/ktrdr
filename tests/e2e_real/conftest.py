"""
Configuration and fixtures for real E2E tests.
"""

import pytest
import pytest_asyncio
import asyncio
import time
import httpx
from pathlib import Path
from typing import Generator

from ktrdr.ib import IbConnectionPool
from ktrdr.config.ib_config import get_ib_config


def pytest_configure(config):
    """Configure pytest for real E2E tests."""
    config.addinivalue_line(
        "markers", "real_ib: marks tests as requiring real IB Gateway connection"
    )
    config.addinivalue_line(
        "markers", "real_cli: marks tests as requiring real CLI execution with IB"
    )
    config.addinivalue_line(
        "markers", "real_api: marks tests as requiring real API calls with IB"
    )
    config.addinivalue_line(
        "markers",
        "real_pipeline: marks tests as requiring complete data pipeline with IB",
    )


def pytest_addoption(parser):
    """Add command line options for real E2E tests."""
    parser.addoption(
        "--real-ib",
        action="store_true",
        default=False,
        help="Run real E2E tests that require IB Gateway connection",
    )
    parser.addoption(
        "--ib-host",
        action="store",
        default="127.0.0.1",
        help="IB Gateway host (default: 127.0.0.1)",
    )
    parser.addoption(
        "--ib-port",
        action="store",
        default="4002",
        help="IB Gateway port (default: 4002)",
    )
    try:
        parser.addoption(
            "--api-base-url",
            action="store",
            default="http://localhost:8000",
            help="API base URL for real E2E tests (default: http://localhost:8000)",
        )
    except ValueError:
        pass  # Option already exists


def pytest_collection_modifyitems(config, items):
    """Skip real E2E tests unless explicitly requested."""
    if not config.getoption("--real-ib"):
        skip_real = pytest.mark.skip(
            reason="Real E2E tests not requested (use --real-ib to enable)"
        )
        for item in items:
            if "real_ib" in item.keywords:
                item.add_marker(skip_real)


@pytest.fixture(scope="session")
def ib_config(pytestconfig):
    """Get IB configuration for tests."""
    host = pytestconfig.getoption("--ib-host")
    port = int(pytestconfig.getoption("--ib-port"))

    # Override config for tests
    config = get_ib_config()
    config.host = host
    config.port = port
    return config


@pytest_asyncio.fixture(scope="session")
async def real_ib_connection_test(ib_config):
    """Test that we can actually connect to IB Gateway."""
    pool = IbConnectionPool(host=ib_config.host, port=ib_config.port)

    try:
        async with pool.get_connection() as connection:
            # Simple test to verify connection works
            async def get_accounts(ib):
                return await ib.reqManagedAcctsAsync()
            
            accounts = await connection.execute_request(get_accounts)
            assert accounts, "No managed accounts returned from IB"
            return True
    except Exception as e:
        pytest.fail(
            f"Cannot connect to IB Gateway at {ib_config.host}:{ib_config.port}: {e}"
        )


@pytest.fixture(scope="session")
def ib_availability_check(api_client):
    """Check if IB is available via API without failing the test."""
    try:
        response = api_client.get("/api/v1/ib/health")

        # Consider IB available only if health endpoint returns 200 AND healthy=true
        is_available = False
        if response.status_code == 200:
            data = response.json()
            if data.get("success") and data.get("data", {}).get("healthy"):
                is_available = True

        return {
            "available": is_available,
            "status_code": response.status_code,
            "response": response.json() if response.status_code in [200, 503] else None,
        }
    except Exception as e:
        return {"available": False, "status_code": None, "error": str(e)}


@pytest.fixture(scope="session")
def api_client(pytestconfig):
    """Create HTTP client for API testing."""
    base_url = pytestconfig.getoption("--api-base-url")
    return httpx.Client(base_url=base_url, timeout=30.0)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory for tests."""
    data_dir = tmp_path / "test_data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def clean_test_symbols():
    """List of symbols safe for testing."""
    return [
        "AAPL",  # Large cap stock - always available
        "MSFT",  # Large cap stock - always available
        "EURUSD",  # Major forex pair - always available
        "USDJPY",  # Major forex pair - always available
    ]


@pytest.fixture
def test_date_ranges():
    """Safe date ranges for testing."""
    return {
        "recent_days": {"start": "2024-12-01", "end": "2024-12-05"},
        "recent_hours": {"start": "2024-12-01", "end": "2024-12-01"},
    }


class RealE2ETestHelper:
    """Helper class for real E2E test operations."""

    @staticmethod
    async def wait_for_operation_completion(
        api_client, operation_id: str, timeout: int = 30
    ):
        """Wait for async operation to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            response = api_client.get(f"/api/v1/operations/{operation_id}")
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    operation_data = data.get("data", {})
                    status = operation_data.get("status")

                    if status == "completed":
                        return operation_data
                    elif status == "failed":
                        error = operation_data.get("error", "Unknown error")
                        raise Exception(f"Operation failed: {error}")

            await asyncio.sleep(1)

        raise TimeoutError(
            f"Operation {operation_id} did not complete within {timeout}s"
        )

    @staticmethod
    def verify_data_file_created(symbol: str, timeframe: str, data_dir: Path) -> bool:
        """Verify that data file was created with expected content."""
        expected_file = data_dir / f"{symbol}_{timeframe}.csv"
        if not expected_file.exists():
            return False

        # Check file has content (at least header)
        with open(expected_file, "r") as f:
            content = f.read().strip()
            return len(content) > 0 and "timestamp" in content.lower()


@pytest.fixture
def e2e_helper():
    """Provide E2E test helper instance."""
    return RealE2ETestHelper()
