"""Pytest configuration for agent tests."""

import os
import sys
from pathlib import Path

# Ensure project root is in path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Use minimal stub delays for tests (1ms instead of 30s per phase)
# Note: test_stub_workers.py test_has_delay tests override this with STUB_WORKER_FAST
os.environ["STUB_WORKER_DELAY"] = "0.001"

# Use fast poll interval for orchestrator tests (10ms instead of 5s)
os.environ["AGENT_POLL_INTERVAL"] = "0.01"
