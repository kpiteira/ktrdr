"""Test fixtures for data acquisition tests."""

import pytest
from unittest.mock import patch

from ktrdr.api.services.operations_service import OperationsService


@pytest.fixture(autouse=True)
def mock_operations_service_for_acquisition():
    """Mock OperationsService for all data acquisition tests.

    After M1, OperationsService creates real DB connections. Unit tests should
    not hit the database. This fixture mocks get_operations_service() to return
    a service without DB connections.
    """
    # Create mock service without repository (no DB connections)
    mock_service = OperationsService(repository=None)

    with patch(
        "ktrdr.api.services.operations_service.get_operations_service",
        return_value=mock_service,
    ):
        yield mock_service
