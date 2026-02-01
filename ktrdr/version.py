"""
Version management for KTRDR.

This module provides a centralized way to access the package version
from anywhere in the codebase. It reads the version from the installed
package metadata using importlib.metadata, which is the standard Python
approach for accessing package version information.

The version is sourced from pyproject.toml at package install/build time
and stored in the package metadata, making it available at runtime.
"""

from importlib.metadata import PackageNotFoundError, version


def _get_version() -> str:
    """
    Get the version string from installed package metadata.

    Uses importlib.metadata which reads from the package's installed metadata.
    This works correctly in:
    - Production (pip install from wheel/sdist)
    - Development (pip install -e / editable install)
    - Docker containers

    Returns:
        str: Version string in the format "x.y.z" or "x.y.z.build"
    """
    try:
        return version("ktrdr")
    except PackageNotFoundError:
        # Fallback for cases where the package isn't installed
        # (e.g., running directly from source without installation)
        return "0.0.0.dev"


# The package version, loaded from installed package metadata
__version__ = _get_version()


def get_version() -> str:
    """
    Get the current version of the KTRDR package.

    Returns:
        str: Current version string
    """
    return __version__


def get_version_parts() -> dict[str, int]:
    """
    Get the version parts as a dictionary.

    Returns:
        Dict with major, minor, patch, and build values
    """
    parts = __version__.split(".")
    version_parts = {
        "major": int(parts[0]) if len(parts) > 0 else 0,
        "minor": int(parts[1]) if len(parts) > 1 else 0,
        "patch": int(parts[2]) if len(parts) > 2 else 0,
        "build": int(parts[3]) if len(parts) > 3 else 0,
    }
    return version_parts
