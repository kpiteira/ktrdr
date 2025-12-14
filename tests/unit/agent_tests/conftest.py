"""Pytest configuration for agent tests."""

import os
import sys
from pathlib import Path

# Ensure project root is in path for imports
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# Use fast mode for stub workers in tests (500ms instead of 30s per phase)
os.environ["STUB_WORKER_FAST"] = "true"
