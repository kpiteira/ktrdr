#!/usr/bin/env python
"""
KTRDR Streamlit UI Entry Point.

This script launches the KTRDR Streamlit user interface.
Run it with: python main.py
"""

import streamlit.web.cli as stcli
import sys
import os
from pathlib import Path

# Get the directory this file is in
file_dir = Path(os.path.dirname(os.path.abspath(__file__)))

def main():
    """Execute the Streamlit app."""
    # Set up command-line arguments for streamlit
    sys.argv = [
        "streamlit",
        "run",
        str(file_dir / "ktrdr" / "ui" / "main.py"),
        "--server.headless", "true",
        "--server.port", "8501",
        "--theme.base", "dark",
        "--theme.primaryColor", "#FF6D00",
    ]
    
    # Run Streamlit
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()