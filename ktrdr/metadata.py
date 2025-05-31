"""
KTRDR Metadata Module - Single source of truth for project configuration.

This module reads from the central metadata file and provides programmatic
access to all project metadata and configuration.
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict

# Path to project root
PROJECT_ROOT = Path(__file__).parent.parent

# Path to metadata file
METADATA_FILE = PROJECT_ROOT / "config" / "ktrdr_metadata.yaml"

# Environment variable prefix
ENV_PREFIX = "KTRDR_"


# Load metadata from YAML
def _load_metadata() -> Dict[str, Any]:
    """Load metadata from the central metadata file."""
    with open(METADATA_FILE, "r") as f:
        return yaml.safe_load(f)


# Initial load
_metadata = _load_metadata()


# Get current environment
def get_environment() -> str:
    """Get the current environment name from environment variable or default."""
    return os.environ.get(f"{ENV_PREFIX}ENVIRONMENT", "development")


# Load environment-specific config
def _load_environment_config(env: str) -> Dict[str, Any]:
    """Load environment-specific configuration."""
    env_file = PROJECT_ROOT / "config" / "environment" / f"{env}.yaml"
    if env_file.exists():
        with open(env_file, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


# Environment config
_env_config = _load_environment_config(get_environment())


# Reload configuration (for testing or dynamic reloading)
def reload_config() -> None:
    """Reload configuration from disk."""
    global _metadata, _env_config
    _metadata = _load_metadata()
    _env_config = _load_environment_config(get_environment())


# Core metadata access functions
def get(path: str, default: Any = None) -> Any:
    """
    Get a metadata value by dot-notation path.

    Example: get("project.version") -> "1.0.6.1"
    """
    parts = path.split(".")

    # Try environment config first
    current = _env_config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            # Fall back to main metadata
            current = _metadata
            for p in parts:
                if isinstance(current, dict) and p in current:
                    current = current[p]
                else:
                    return default
            break

    # Check environment variables for override
    env_var = f"{ENV_PREFIX}{'_'.join(parts).upper()}"
    env_value = os.environ.get(env_var)
    if env_value is not None:
        # Type conversion based on the type in metadata
        if isinstance(current, bool):
            return env_value.lower() in ("true", "1", "yes")
        elif isinstance(current, int):
            return int(env_value)
        elif isinstance(current, float):
            return float(env_value)
        elif isinstance(current, list):
            return env_value.split(",")
        return env_value

    return current


# Project information
PROJECT_NAME = get("project.name")
PROJECT_DESCRIPTION = get("project.description")
VERSION = get("project.version")

# Organization information
ORG_NAME = get("organization.name")
ORG_WEBSITE = get("organization.website")
ORG_GITHUB = get("organization.github")
ORG_EMAIL = get("organization.email")
ORG_DOCS_URL = get("organization.docs_url")

# API information
API_TITLE = get("api.title")
API_DESCRIPTION = get("api.description")
API_PREFIX = get("api.prefix")


# Helper functions for specific contexts
def get_fastapi_settings() -> Dict[str, Any]:
    """Get FastAPI application settings."""
    return {
        "title": API_TITLE,
        "description": API_DESCRIPTION,
        "version": VERSION,
        "docs_url": f"{API_PREFIX}/docs",
        "redoc_url": f"{API_PREFIX}/redoc",
        "openapi_url": f"{API_PREFIX}/openapi.json",
    }


def get_docker_labels() -> Dict[str, str]:
    """Get Docker labels based on metadata."""
    return {
        "org.opencontainers.image.title": get("docker.labels.title", PROJECT_NAME),
        "org.opencontainers.image.description": get(
            "docker.labels.description", PROJECT_DESCRIPTION
        ),
        "org.opencontainers.image.version": VERSION,
        "org.opencontainers.image.licenses": get(
            "docker.labels.licenses", get("project.license")
        ),
        "org.opencontainers.image.authors": get("docker.labels.authors", ORG_NAME),
        "org.opencontainers.image.source": ORG_GITHUB,
        "org.opencontainers.image.documentation": get(
            "docker.labels.documentation", ORG_DOCS_URL
        ),
    }


def get_api_examples() -> Dict[str, Any]:
    """Get API examples for documentation."""
    return {
        "symbols": get("examples.symbols", []),
        "timeframes": get("examples.timeframes", []),
        "default_symbol": get("examples.default_symbol"),
        "default_timeframe": get("examples.default_timeframe"),
    }
