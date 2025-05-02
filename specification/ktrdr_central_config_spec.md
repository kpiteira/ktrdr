# KTRDR Central Configuration Management Specification

## 1. Overview and Goals

This specification details a comprehensive configuration management system for KTRDR, providing a single source of truth for project metadata, versioning, and configuration across all contexts.

### 1.1 Current Challenges

- Metadata is fragmented across multiple files (`pyproject.toml`, docs_config.yaml, Dockerfile)
- Changes require updates in multiple locations, leading to inconsistencies
- Different execution contexts (tests, CLI, API, Docker) have different access patterns
- No clear source of truth for shared values

### 1.2 Design Goals

- Provide a single, authoritative source for project metadata
- Support multiple access patterns for different execution contexts
- Maintain backward compatibility with existing tooling
- Minimize overhead for developers
- Ensure consistent values across all application components

## 2. Core Architecture

### 2.1 Configuration Components

```
┌─────────────────────┐
│                     │
│  Central Metadata   │ ← Single source of truth
│  (YAML)             │
│                     │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│                     │
│  Python Metadata    │ ← Programmatic access
│  Module             │
│                     │
└────┬────────┬───────┘
     │        │
     ▼        ▼
┌────────┐  ┌────────────┐
│        │  │            │
│ Runtime│  │ Build-time │ ← Context-specific access
│ Access │  │ Generation │
│        │  │            │
└────┬───┘  └─────┬──────┘
     │            │
     ▼            ▼
┌────────┐  ┌────────────┐
│ API    │  │ Docker     │
│ CLI    │  │ CI/CD      │ ← Usage contexts
│ Tests  │  │ Packaging  │
└────────┘  └────────────┘
```

### 2.2 File Structure

```
ktrdr/
├── config/
│   ├── ktrdr_metadata.yaml       # Primary source of truth
│   ├── environment/              # Environment-specific overrides
│   │   ├── development.yaml
│   │   ├── testing.yaml
│   │   └── production.yaml
├── ktrdr/
│   ├── metadata.py               # Python access module
│   ├── config/
│   │   ├── __init__.py           # Config loader
│   │   └── settings.py           # Settings manager
├── scripts/
│   ├── update_metadata.py        # Synchronization script
```

## 3. Central Metadata File

### 3.1 Structure and Schema

```yaml
# config/ktrdr_metadata.yaml

# Project Identification
project:
  name: "KTRDR"
  full_name: "KTRDR Trading System"
  description: "Advanced trading system with fuzzy logic and machine learning capabilities"
  version: "1.0.5.5"
  license: "Proprietary"
  
# Organization Information
organization:
  name: "KTRDR"
  website: "https://ktrdr.mynerd.place"
  github: "https://github.com/kpiteira/ktrdr"
  email: "karl@mynerd.place"
  docs_url: "https://ktrdr-docs.mynerd.place"
  
# API Configuration
api:
  title: "KTRDR API"
  description: "REST API for KTRDR trading system"
  prefix: "/api/v1"
  cors_origins: ["*"]
  default_version: "v1"
  
# Docker Configuration
docker:
  labels:
    title: "KTRDR Backend"
    description: "KTRDR trading system backend API"
    licenses: "Proprietary"
    authors: "KTRDR Team"
    documentation: "https://ktrdr-docs.mynerd.place"
  
# UI Configuration  
ui:
  title: "KTRDR Dashboard"
  theme:
    primary_color: "#4CAF50"
    secondary_color: "#1a1a1a"
  logo_url: "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png"
  
# Examples for Documentation
examples:
  symbols: ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
  timeframes: ["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "1w", "1M"]
  default_symbol: "AAPL"
  default_timeframe: "1d"
```

### 3.2 Environment-Specific Overrides

```yaml
# config/environment/development.yaml
api:
  host: "127.0.0.1"
  port: 8000
  reload: true
  log_level: "DEBUG"

# config/environment/testing.yaml
api:
  port: 8001
  reload: false
  log_level: "WARNING"
```

## 4. Python Metadata Module

### 4.1 Core Module Implementation

```python
# ktrdr/metadata.py
"""
KTRDR Metadata Module - Single source of truth for project configuration.

This module reads from the central metadata file and provides programmatic
access to all project metadata and configuration.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

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
            return yaml.safe_load(f)
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
    
    Example: get("project.version") -> "1.0.5.5"
    """
    parts = path.split('.')
    
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
        "org.opencontainers.image.description": get("docker.labels.description", PROJECT_DESCRIPTION),
        "org.opencontainers.image.version": VERSION,
        "org.opencontainers.image.licenses": get("docker.labels.licenses", get("project.license")),
        "org.opencontainers.image.authors": get("docker.labels.authors", ORG_NAME),
        "org.opencontainers.image.source": ORG_GITHUB,
        "org.opencontainers.image.documentation": get("docker.labels.documentation", ORG_DOCS_URL),
    }

def get_api_examples() -> Dict[str, Any]:
    """Get API examples for documentation."""
    return {
        "symbols": get("examples.symbols", []),
        "timeframes": get("examples.timeframes", []),
        "default_symbol": get("examples.default_symbol"),
        "default_timeframe": get("examples.default_timeframe"),
    }
```

### 4.2 Settings Module for Runtime Configuration

```python
# ktrdr/config/settings.py
"""
KTRDR Settings Manager - Runtime configuration management.

This module provides access to configuration settings with environment-specific
overrides and environment variable support.
"""
from pydantic import BaseSettings, Field
from functools import lru_cache
from .. import metadata

class APISettings(BaseSettings):
    """API Server Settings."""
    title: str = Field(default=metadata.API_TITLE)
    description: str = Field(default=metadata.API_DESCRIPTION)
    version: str = Field(default=metadata.VERSION)
    host: str = Field(default=metadata.get("api.host", "127.0.0.1"))
    port: int = Field(default=metadata.get("api.port", 8000))
    reload: bool = Field(default=metadata.get("api.reload", True))
    log_level: str = Field(default=metadata.get("api.log_level", "INFO"))
    api_prefix: str = Field(default=metadata.API_PREFIX)
    cors_origins: list = Field(default=metadata.get("api.cors_origins", ["*"]))
    
    class Config:
        env_prefix = "KTRDR_API_"

class LoggingSettings(BaseSettings):
    """Logging Settings."""
    level: str = Field(default=metadata.get("logging.level", "INFO"))
    format: str = Field(default=metadata.get("logging.format", "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    
    class Config:
        env_prefix = "KTRDR_LOGGING_"

# Cache settings to avoid repeated disk/env access
@lru_cache()
def get_api_settings() -> APISettings:
    """Get API settings with caching."""
    return APISettings()

@lru_cache()
def get_logging_settings() -> LoggingSettings:
    """Get logging settings with caching."""
    return LoggingSettings()

# Clear settings cache (for testing)
def clear_settings_cache() -> None:
    """Clear settings cache."""
    get_api_settings.cache_clear()
    get_logging_settings.cache_clear()
```

## 5. Access Patterns for Different Contexts

### 5.1 API Server Context

```python
# ktrdr/api/main.py
import uvicorn
from fastapi import FastAPI
from ktrdr import metadata
from ktrdr.config.settings import get_api_settings

app = FastAPI(**metadata.get_fastapi_settings())

@app.get(f"{metadata.API_PREFIX}/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": metadata.VERSION,
        "service": metadata.PROJECT_NAME
    }

if __name__ == "__main__":
    api_settings = get_api_settings()
    uvicorn.run(
        "ktrdr.api.main:app",
        host=api_settings.host,
        port=api_settings.port,
        reload=api_settings.reload,
        log_level=api_settings.log_level.lower(),
    )
```

### 5.2 CLI Context

```python
# ktrdr/cli.py
import typer
from ktrdr import metadata
import logging

app = typer.Typer(
    name=metadata.PROJECT_NAME,
    help=metadata.PROJECT_DESCRIPTION,
)

@app.callback()
def callback(
    verbose: bool = False,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit."),
):
    """KTRDR Command Line Interface."""
    if version:
        typer.echo(f"{metadata.PROJECT_NAME} version: {metadata.VERSION}")
        raise typer.Exit()
        
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format=metadata.get("logging.format")
    )

@app.command()
def info():
    """Show project information."""
    typer.echo(f"Project: {metadata.PROJECT_NAME} v{metadata.VERSION}")
    typer.echo(f"Description: {metadata.PROJECT_DESCRIPTION}")
    typer.echo(f"Website: {metadata.ORG_WEBSITE}")
    typer.echo(f"Documentation: {metadata.ORG_DOCS_URL}")

if __name__ == "__main__":
    app()
```

### 5.3 Testing Context

```python
# tests/conftest.py
import pytest
from ktrdr import metadata
from ktrdr.config import settings
import os

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up the test environment."""
    # Set environment to testing
    os.environ["KTRDR_ENVIRONMENT"] = "testing"
    
    # Reload metadata with test configuration
    metadata.reload_config()
    
    # Clear settings cache to ensure test settings are used
    settings.clear_settings_cache()
    
    yield
    
    # Reset environment
    os.environ.pop("KTRDR_ENVIRONMENT", None)
    metadata.reload_config()
    settings.clear_settings_cache()

@pytest.fixture
def api_settings():
    """Get API settings for tests."""
    return settings.get_api_settings()

@pytest.fixture
def project_metadata():
    """Get project metadata for tests."""
    return {
        "name": metadata.PROJECT_NAME,
        "version": metadata.VERSION,
        "description": metadata.PROJECT_DESCRIPTION,
    }
```

### 5.4 Examples/Scripts Context

```python
# examples/api_example.py
import requests
from ktrdr import metadata

def main():
    """Example script showing API interaction."""
    # Get examples from metadata
    examples = metadata.get_api_examples()
    
    # Default values
    symbol = examples.get("default_symbol", "AAPL")
    timeframe = examples.get("default_timeframe", "1d")
    
    # API base URL from configuration
    api_host = metadata.get("api.host", "127.0.0.1")
    api_port = metadata.get("api.port", 8000)
    api_prefix = metadata.API_PREFIX
    
    base_url = f"http://{api_host}:{api_port}{api_prefix}"
    
    # Make API request
    response = requests.get(f"{base_url}/symbols")
    if response.status_code == 200:
        print(f"Available symbols: {response.json()['data']}")
    
if __name__ == "__main__":
    main()
```

## 6. Build-Time Integration

### 6.1 Dockerfile with Build Args

```dockerfile
# Dockerfile
ARG PROJECT_NAME
ARG PROJECT_VERSION
ARG ORG_WEBSITE
ARG ORG_GITHUB

FROM python:3.11-slim AS builder

# ...rest of the Dockerfile...

FROM python:3.11-slim AS runtime

# Set metadata labels from build args
LABEL org.opencontainers.image.title="${PROJECT_NAME} Backend"
LABEL org.opencontainers.image.description="${PROJECT_NAME} trading system backend API"
LABEL org.opencontainers.image.version="${PROJECT_VERSION}"
LABEL org.opencontainers.image.source="${ORG_GITHUB}"
# etc.

# ...rest of the Dockerfile...
```

### 6.2 Build Script and Hooks

```python
# scripts/update_metadata.py
"""
Synchronization script to update version and metadata across project files.

This script ensures that derived configuration files are in sync with
the central metadata file.
"""
import yaml
import tomli
import tomli_w
import json
import subprocess
from pathlib import Path
import sys
import argparse

# Path to project root
PROJECT_ROOT = Path(__file__).parent.parent

# Path to metadata file
METADATA_FILE = PROJECT_ROOT / "config" / "ktrdr_metadata.yaml"

def load_metadata():
    """Load metadata from the central file."""
    with open(METADATA_FILE, "r") as f:
        return yaml.safe_load(f)

def update_pyproject_toml(metadata):
    """Update pyproject.toml with metadata values."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    
    with open(pyproject_path, "rb") as f:
        pyproject = tomli.load(f)
    
    # Update version
    pyproject["project"]["version"] = metadata["project"]["version"]
    
    # Update other metadata
    pyproject["project"]["name"] = metadata["project"]["name"]
    pyproject["project"]["description"] = metadata["project"]["description"]
    
    with open(pyproject_path, "wb") as f:
        tomli_w.dump(pyproject, f)
    
    print(f"Updated pyproject.toml with version {metadata['project']['version']}")

def create_docker_env_file(metadata):
    """Create a .env file for Docker builds."""
    docker_env_path = PROJECT_ROOT / "build" / "docker.env"
    
    # Create build directory if it doesn't exist
    docker_env_path.parent.mkdir(exist_ok=True)
    
    with open(docker_env_path, "w") as f:
        f.write(f"PROJECT_NAME={metadata['project']['name']}\n")
        f.write(f"PROJECT_VERSION={metadata['project']['version']}\n")
        f.write(f"PROJECT_DESCRIPTION={metadata['project']['description']}\n")
        f.write(f"ORG_NAME={metadata['organization']['name']}\n")
        f.write(f"ORG_WEBSITE={metadata['organization']['website']}\n")
        f.write(f"ORG_GITHUB={metadata['organization']['github']}\n")
        
    print(f"Created Docker environment file at {docker_env_path}")

def create_version_file(metadata):
    """Create a version.json file for CI/CD and other tools."""
    version_path = PROJECT_ROOT / "ktrdr" / "version.json"
    
    version_info = {
        "version": metadata["project"]["version"],
        "name": metadata["project"]["name"],
        "description": metadata["project"]["description"],
    }
    
    with open(version_path, "w") as f:
        json.dump(version_info, f, indent=2)
    
    print(f"Created version.json at {version_path}")

def install_git_hook():
    """Install a git pre-commit hook to check metadata consistency."""
    hooks_dir = PROJECT_ROOT / ".git" / "hooks"
    if not hooks_dir.exists():
        print("Git hooks directory not found, skipping hook installation")
        return
    
    hook_path = hooks_dir / "pre-commit"
    
    with open(hook_path, "w") as f:
        f.write("""#!/bin/bash
        
# Check if metadata files are in sync
python scripts/update_metadata.py --check
if [ $? -ne 0 ]; then
    echo "Metadata files are out of sync. Run 'python scripts/update_metadata.py' to update."
    exit 1
fi

# Continue with commit
exit 0
""")
    
    # Make hook executable
    hook_path.chmod(0o755)
    print(f"Installed git pre-commit hook at {hook_path}")

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update metadata across the project")
    parser.add_argument("--check", action="store_true", help="Check if files are in sync")
    args = parser.parse_args()
    
    metadata = load_metadata()
    
    if args.check:
        # In check mode, verify that files are in sync
        with open(PROJECT_ROOT / "pyproject.toml", "rb") as f:
            pyproject = tomli.load(f)
        
        if pyproject["project"]["version"] != metadata["project"]["version"]:
            print("Error: pyproject.toml version doesn't match metadata")
            sys.exit(1)
        
        print("All files are in sync with metadata")
        sys.exit(0)
    
    # Update files
    update_pyproject_toml(metadata)
    create_docker_env_file(metadata)
    create_version_file(metadata)
    
    print("Metadata updated successfully across all project files")

if __name__ == "__main__":
    main()
```

## 7. Usage Guidelines

### 7.1 Running the API Server

```bash
# Method 1: Using the API module directly
python -m ktrdr.api.main

# Method 2: Using uvicorn with default values from metadata
python -m uvicorn ktrdr.api.main:app --reload

# Method 3: With environment variable overrides
KTRDR_API_PORT=8080 KTRDR_API_LOG_LEVEL=DEBUG python -m ktrdr.api.main

# Method 4: Using a different environment configuration
KTRDR_ENVIRONMENT=production python -m ktrdr.api.main
```

### 7.2 Running Tests

```bash
# Run all tests with testing environment
pytest

# Run tests with specific environment
KTRDR_ENVIRONMENT=production pytest

# Run tests with environment variable overrides
KTRDR_API_PORT=9000 pytest tests/api/
```

### 7.3 Running the CLI

```bash
# Show version
python -m ktrdr.cli --version

# Run CLI commands
python -m ktrdr.cli info

# With environment overrides
KTRDR_LOGGING_LEVEL=DEBUG python -m ktrdr.cli info
```

### 7.4 Running Examples/Scripts

```bash
# Run example scripts
python examples/api_example.py

# With environment overrides
KTRDR_API_PORT=8080 python examples/api_example.py
```

### 7.5 Docker Build Process

```bash
# Build with metadata values
docker build --build-arg PROJECT_NAME=$(python -c "from ktrdr import metadata; print(metadata.PROJECT_NAME)") \
             --build-arg PROJECT_VERSION=$(python -c "from ktrdr import metadata; print(metadata.VERSION)") \
             --build-arg ORG_WEBSITE=$(python -c "from ktrdr import metadata; print(metadata.ORG_WEBSITE)") \
             -t ktrdr-backend .

# Or using the generated environment file
docker build --env-file build/docker.env -t ktrdr-backend .
```

## 8. Updating Metadata

### 8.1 Manual Update Process

1. Edit the central `config/ktrdr_metadata.yaml` file with new values
2. Run `python scripts/update_metadata.py` to synchronize all files
3. Commit all changed files together

### 8.2 Integration with Version Control

The project includes a Git pre-commit hook that checks metadata consistency:

1. The hook runs `update_metadata.py --check` before each commit
2. If files are out of sync, the commit fails with an error message
3. After running the update script, commit can proceed

### 8.3 CI/CD Integration

In CI/CD workflows, metadata consistency can be verified:

```yaml
# .github/workflows/ci.yml
jobs:
  metadata-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install tomli pyyaml
      - name: Check metadata consistency
        run: python scripts/update_metadata.py --check
```

## 9. Migration Plan

1. **Create Central Files**:
   - Create `config/ktrdr_metadata.yaml` with all metadata
   - Create environment-specific overrides in `config/environment/`
   - Implement `ktrdr/metadata.py` module

2. **Update Existing Code**:
   - Modify `api/main.py` to use the new metadata module
   - Update CLI to use metadata values

3. **Create Synchronization Tools**:
   - Implement `scripts/update_metadata.py`
   - Run initial synchronization to update all files
   - Install Git hook for consistency checks

4. **Documentation & Training**:
   - Document the new metadata system for developers
   - Update relevant documentation

## 10. Testing & Validation

### 10.1 Unit Tests

```python
# tests/test_metadata.py
import os
import pytest
from ktrdr import metadata

def test_metadata_module():
    """Test main metadata functions."""
    assert metadata.PROJECT_NAME == "KTRDR"
    assert isinstance(metadata.VERSION, str)
    assert metadata.ORG_WEBSITE.startswith("https://")

def test_environment_override():
    """Test environment-specific configuration override."""
    # Testing environment should have different settings
    assert metadata.get("api.port") != 8000  # Default is 8000, testing should be different

def test_env_var_override():
    """Test environment variable override."""
    test_port = 9999
    os.environ["KTRDR_API_PORT"] = str(test_port)
    
    # Force reload to pick up new environment variable
    metadata.reload_config()
    
    assert metadata.get("api.port") == test_port
    
    # Clean up
    os.environ.pop("KTRDR_API_PORT")
    metadata.reload_config()

def test_helper_functions():
    """Test metadata helper functions."""
    # FastAPI settings
    fastapi_settings = metadata.get_fastapi_settings()
    assert fastapi_settings["title"] == metadata.API_TITLE
    assert fastapi_settings["version"] == metadata.VERSION
    
    # Docker labels
    docker_labels = metadata.get_docker_labels()
    assert docker_labels["org.opencontainers.image.version"] == metadata.VERSION
```

### 10.2 Integration Tests

```python
# tests/test_integration.py
import subprocess
import json
import pytest

def test_cli_version():
    """Test CLI displays correct version from metadata."""
    result = subprocess.run(
        ["python", "-m", "ktrdr.cli", "--version"],
        capture_output=True,
        text=True,
        check=True
    )
    assert "version:" in result.stdout

def test_api_health():
    """Test API health endpoint shows correct version."""
    # This test requires the API to be running
    # In real implementation, use the testing client or start the API in the test
    import requests
    from ktrdr import metadata
    
    try:
        response = requests.get(f"http://127.0.0.1:8001/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == metadata.VERSION
    except requests.exceptions.ConnectionError:
        pytest.skip("API server not running")
```

## 11. Conclusion

The centralized configuration management system outlined in this specification provides a robust solution to the challenges of maintaining consistent metadata across the KTRDR project. By implementing a single source of truth with flexible access patterns, the project will benefit from:

1. **Consistency**: All components will use the same version, name, and other metadata
2. **Maintainability**: Updates only need to be made in one place
3. **Flexibility**: Different contexts can access the configuration in ways that make sense
4. **Extensibility**: The system can easily accommodate new components and configuration needs

This specification provides a comprehensive roadmap for implementing and using the central configuration system, ensuring that all project components remain synchronized and developers have a clear understanding of how to work with project metadata.