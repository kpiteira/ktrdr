"""Pytest configuration for agent tests."""

import os
import sys
from pathlib import Path

import pytest

# Ensure project root is in path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Use minimal stub delays for tests (1ms instead of 30s per phase)
# Note: test_stub_workers.py test_has_delay tests override this with STUB_WORKER_FAST
os.environ["STUB_WORKER_DELAY"] = "0.001"

# Use fast poll interval for orchestrator tests (10ms instead of 5s)
# Note: This sets the deprecated env var which is picked up by settings
os.environ["AGENT_POLL_INTERVAL"] = "0.01"


@pytest.fixture(autouse=True)
def clear_agent_settings_cache():
    """Clear agent settings cache before and after each test.

    The agent settings are cached by lru_cache, so we need to clear them
    between tests to ensure env var changes take effect.
    """
    from ktrdr.config import clear_settings_cache

    clear_settings_cache()
    yield
    clear_settings_cache()
