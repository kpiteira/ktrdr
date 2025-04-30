"""
KTRDR Streamlit Application Launcher

This script launches the KTRDR Streamlit UI application.
"""
import os
import sys
from pathlib import Path

# Ensure the current directory is in the path for importing modules
current_dir = Path(__file__).parent.absolute()
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

from ktrdr.ui import run_app

if __name__ == "__main__":
    # Run the Streamlit application
    run_app()