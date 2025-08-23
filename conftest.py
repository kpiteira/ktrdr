"""
Global pytest configuration for KTRDR project.
"""

import pytest


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as an asyncio coroutine")
    config.addinivalue_line("markers", "api: mark a test as involving the API layer")
    config.addinivalue_line(
        "markers", "performance: mark tests that evaluate API performance metrics"
    )
    config.addinivalue_line(
        "markers", "endpoints: mark tests that target specific API endpoints"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests requiring IB Gateway"
    )
    config.addinivalue_line("markers", "stress: marks tests as stress tests")
    config.addinivalue_line("markers", "e2e: marks tests as end-to-end tests")
    config.addinivalue_line(
        "markers", "container_api: marks tests as container API tests"
    )
    config.addinivalue_line(
        "markers", "container_cli: marks tests as container CLI tests"
    )


def pytest_addoption(parser):
    """Add command line options for integration tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require IB Gateway",
    )
    parser.addoption(
        "--run-stress", action="store_true", default=False, help="Run stress tests"
    )
    parser.addoption(
        "--run-e2e", action="store_true", default=False, help="Run end-to-end tests"
    )
    parser.addoption(
        "--run-container-e2e",
        action="store_true",
        default=False,
        help="Run container end-to-end tests (requires running container)",
    )
    parser.addoption(
        "--run-container-cli",
        action="store_true",
        default=False,
        help="Run container CLI tests (requires running container)",
    )
