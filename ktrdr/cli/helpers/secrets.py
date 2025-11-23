"""1Password secrets integration for KTRDR deployment.

This module provides functions to fetch secrets from 1Password
using the op CLI tool. Secrets are fetched at deploy time and
injected inline - they are never stored on disk.
"""

import json
import subprocess


class OnePasswordError(Exception):
    """Raised when 1Password operations fail."""

    pass


def fetch_secrets_from_1password(item_name: str) -> dict[str, str]:
    """
    Fetch secrets from 1Password item.

    Args:
        item_name: Name of the 1Password item

    Returns:
        Dict mapping field labels to values (only CONCEALED fields)

    Raises:
        OnePasswordError: If op CLI fails
    """
    try:
        cmd = ["op", "item", "get", item_name, "--format", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        item = json.loads(result.stdout)

        secrets = {}
        for field in item.get("fields", []):
            if field.get("type") == "CONCEALED":
                secrets[field["label"]] = field["value"]

        return secrets

    except subprocess.CalledProcessError as e:
        if "not signed in" in e.stderr:
            raise OnePasswordError(
                "Not signed in to 1Password. Run: op signin"
            ) from None
        elif "not found" in e.stderr:
            raise OnePasswordError(
                f"Item '{item_name}' not found in 1Password"
            ) from None
        else:
            raise OnePasswordError(f"1Password error: {e.stderr}") from e
    except FileNotFoundError as e:
        raise OnePasswordError("1Password CLI (op) not installed") from e


def check_1password_authenticated() -> bool:
    """
    Check if 1Password CLI is authenticated.

    Returns:
        True if authenticated, False otherwise
    """
    try:
        result = subprocess.run(
            ["op", "account", "list"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
