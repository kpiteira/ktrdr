#!/usr/bin/env python
"""
Debug script for testing the CLI directly.
"""

import sys
from ktrdr.cli.commands import cli_app

if __name__ == "__main__":
    # Print command line arguments for debugging
    print(f"Command line arguments: {sys.argv}")
    
    # Run the CLI app with the provided arguments
    sys.exit(cli_app())