#!/usr/bin/env python3
"""
Synchronization script to update version and metadata across project files.

This script ensures that derived configuration files are in sync with
the central metadata file.
"""
import yaml
import tomli
import tomli_w
import json

# import subprocess
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
        f.write(
            """#!/bin/bash

# Check if metadata files are in sync
python scripts/update_metadata.py --check
if [ $? -ne 0 ]; then
    echo "Metadata files are out of sync. Run 'python scripts/update_metadata.py' to update."
    exit 1
fi

# Continue with commit
exit 0
"""
        )

    # Make hook executable
    hook_path.chmod(0o755)
    print(f"Installed git pre-commit hook at {hook_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Update metadata across the project")
    parser.add_argument(
        "--check", action="store_true", help="Check if files are in sync"
    )
    parser.add_argument(
        "--install-hook", action="store_true", help="Install git pre-commit hook"
    )
    args = parser.parse_args()

    if args.install_hook:
        install_git_hook()
        return

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
