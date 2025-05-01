"""
Version management for KTRDR.

This module provides a centralized way to access the package version
from anywhere in the codebase. It reads the version from pyproject.toml,
which serves as the single source of truth.
"""
import os
import tomli
from pathlib import Path
from typing import Dict, Any

# Get the project root directory (2 levels up from this file)
# This is needed to find the pyproject.toml file
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"

def get_version_from_pyproject() -> str:
    """
    Read the version string from pyproject.toml.
    
    Returns:
        str: Version string in the format "x.y.z.build"
    
    Raises:
        FileNotFoundError: If pyproject.toml cannot be found
        KeyError: If version is not defined in pyproject.toml
    """
    try:
        with open(PYPROJECT_PATH, "rb") as f:
            pyproject_data = tomli.load(f)
        
        # Extract version from project.version
        version = pyproject_data["project"]["version"]
        return version
    except FileNotFoundError:
        # Fallback version if pyproject.toml is not found
        # This can happen in some environments like certain CI systems
        return "0.0.0.0"
    except (KeyError, tomli.TOMLDecodeError):
        # Fallback if version key is missing or TOML is invalid
        return "0.0.0.0"

# The package version, loaded from pyproject.toml
__version__ = get_version_from_pyproject()

def get_version() -> str:
    """
    Get the current version of the KTRDR package.
    
    Returns:
        str: Current version string
    """
    return __version__

def get_version_parts() -> Dict[str, int]:
    """
    Get the version parts as a dictionary.
    
    Returns:
        Dict with major, minor, patch, and build values
    """
    parts = __version__.split('.')
    version_parts = {
        "major": int(parts[0]) if len(parts) > 0 else 0,
        "minor": int(parts[1]) if len(parts) > 1 else 0,
        "patch": int(parts[2]) if len(parts) > 2 else 0,
        "build": int(parts[3]) if len(parts) > 3 else 0
    }
    return version_parts

# Additional version utilities can be added here as needed
# For example, functions to check minimum version requirements