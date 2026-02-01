"""Pytest configuration for worker tests."""

import pytest


@pytest.fixture(autouse=True)
def clear_worker_settings_cache():
    """Clear settings cache before and after each test.

    Worker tests often modify env vars and need fresh settings.
    """
    from ktrdr.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()
