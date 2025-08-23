"""
Configuration for end-to-end tests.

This module provides shared fixtures and configuration for container-based
end-to-end testing.
"""

import subprocess
import time

import pytest
import requests


def pytest_configure(config):
    """Configure pytest for E2E tests."""
    # Add custom markers
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line(
        "markers", "container_api: marks tests as container API tests"
    )
    config.addinivalue_line(
        "markers", "container_cli: marks tests as container CLI tests"
    )
    config.addinivalue_line("markers", "slow: marks tests as slow running")


def pytest_addoption(parser):
    """Add command line options for E2E tests."""
    # Only add options that aren't already defined globally
    try:
        parser.addoption(
            "--api-base-url",
            action="store",
            default="http://localhost:8000/api/v1",
            help="Base URL for API testing",
        )
    except ValueError:
        pass  # Option already exists

    try:
        parser.addoption(
            "--container-name",
            action="store",
            default="ktrdr-backend",
            help="Name of the container to test",
        )
    except ValueError:
        pass  # Option already exists

    try:
        parser.addoption(
            "--run-container-e2e",
            action="store_true",
            default=False,
            help="Run container end-to-end tests (requires running container)",
        )
    except ValueError:
        pass  # Option already exists

    try:
        parser.addoption(
            "--run-container-cli",
            action="store_true",
            default=False,
            help="Run container CLI tests (requires running container)",
        )
    except ValueError:
        pass  # Option already exists


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on command line options."""
    # Skip container API tests unless explicitly requested
    if not config.getoption("--run-container-e2e"):
        skip_container_api = pytest.mark.skip(
            reason="Container E2E tests not requested (use --run-container-e2e)"
        )
        for item in items:
            if (
                "container_api" in item.keywords
                or "container_e2e" in item.keywords
                or ("test_container" in item.name and "api" in item.name)
                or "test_container_api" in item.name
            ):
                item.add_marker(skip_container_api)

    # Skip container CLI tests unless explicitly requested
    if not config.getoption("--run-container-cli"):
        skip_container_cli = pytest.mark.skip(
            reason="Container CLI tests not requested (use --run-container-cli)"
        )
        for item in items:
            if (
                "container_cli" in item.keywords
                or ("test_container" in item.name and "cli" in item.name)
                or "test_container_cli" in item.name
            ):
                item.add_marker(skip_container_cli)


@pytest.fixture(scope="session")
def api_base_url(request):
    """Get API base URL from command line or default."""
    return request.config.getoption("--api-base-url")


@pytest.fixture(scope="session")
def container_name(request):
    """Get container name from command line or default."""
    return request.config.getoption("--container-name")


@pytest.fixture(scope="session")
def container_running(container_name):
    """Check if the test container is running."""
    try:
        result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                f"name={container_name}",
                "--format",
                "{{.Names}}",
            ],
            capture_output=True,
            text=True,
            timeout=10.0,
        )
        running = container_name in result.stdout

        if not running:
            pytest.skip(f"Container {container_name} is not running")

        return True

    except Exception as e:
        pytest.skip(f"Could not check container status: {e}")


@pytest.fixture(scope="session")
def api_ready(api_base_url, container_running):
    """Wait for API to be ready before running tests."""
    max_attempts = 30
    attempt = 1

    while attempt <= max_attempts:
        try:
            response = requests.get(f"{api_base_url}/health", timeout=5.0)
            if response.status_code == 200:
                return True
        except requests.RequestException:
            pass

        if attempt < max_attempts:
            time.sleep(2.0)
        attempt += 1

    pytest.skip(f"API at {api_base_url} is not ready")


@pytest.fixture
def api_client(api_base_url, api_ready):
    """Create HTTP client for API testing."""
    import httpx

    return httpx.Client(base_url=api_base_url, timeout=30.0)


@pytest.fixture
async def async_api_client(api_base_url, api_ready):
    """Create async HTTP client for API testing."""
    import httpx

    async with httpx.AsyncClient(base_url=api_base_url, timeout=30.0) as client:
        yield client


@pytest.fixture
def cli_runner(container_name, container_running):
    """Create CLI runner for container testing."""
    from tests.e2e.test_container_cli_commands import ContainerCLIRunner

    return ContainerCLIRunner(container_name)
