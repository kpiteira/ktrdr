"""Sandbox auto-detection and URL utilities for CLI commands.

This module provides URL resolution logic that determines which KTRDR backend
to target based on flags and current directory's .env.sandbox file.

Key design decision (from DESIGN.md Decision 10):
We read the .env.sandbox FILE directly, NOT environment variables.
This avoids "env var pollution" between terminal sessions.

Priority order (highest to lowest):
1. explicit_url: Explicit --url flag, always wins
2. explicit_port: --port flag, convenience for localhost
3. .env.sandbox file: Auto-detect from current directory tree
4. Default: http://localhost:8000
"""

from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# Default API port for KTRDR backend
DEFAULT_API_PORT = 8000

# Module-level URL override set by --url flag in CLI callback.
# This allows the URL to flow from the CLI entry point to HTTP clients
# without requiring every command to explicitly pass it.
_url_override: Optional[str] = None


def set_url_override(url: Optional[str]) -> None:
    """Set the global URL override (called by CLI callback when --url is used).

    Args:
        url: The normalized API URL, or None to clear the override.
    """
    global _url_override
    _url_override = url


def get_url_override() -> Optional[str]:
    """Get the global URL override if set via --url flag.

    Returns:
        The URL override if set, None otherwise.
    """
    return _url_override


def get_effective_api_url() -> str:
    """Get the effective API URL for display in error messages.

    Follows the same priority as URL resolution:
    1. URL override (if set via --url flag)
    2. Sandbox detection (if .env.sandbox exists)
    3. Config default

    This is useful for error messages to show users what URL is being targeted.

    Returns:
        The effective API URL being used.
    """
    # Priority 1: URL override from --url flag
    if _url_override:
        return _url_override

    # Priority 2: Sandbox detection
    if find_env_sandbox() is not None:
        sandbox_url = resolve_api_url()
        return f"{sandbox_url}/api/v1"

    # Priority 3: Config default
    from ktrdr.config.host_services import get_api_base_url

    return get_api_base_url()


def normalize_api_url(url: str) -> str:
    """Normalize an API URL by adding protocol, port, and /api/v1 if missing.

    Args:
        url: Raw URL (e.g., "backend.example.com" or "http://backend.example.com:8000")

    Returns:
        Normalized URL with protocol, port, and API path
        (e.g., "http://backend.example.com:8000/api/v1")
    """
    if not url:
        return url

    # Add http:// if no protocol specified
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"

    # Parse and add default port if missing
    parsed = urlparse(url)
    if parsed.port is None:
        # Reconstruct with default port
        netloc = f"{parsed.hostname}:{DEFAULT_API_PORT}"
        url = f"{parsed.scheme}://{netloc}{parsed.path}"

    url = url.rstrip("/")

    # Auto-append /api/v1 if no API path present
    if "/api/" not in url:
        url = f"{url}/api/v1"

    return url


def parse_dotenv_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dictionary.

    Parses a dotenv-style file into key-value pairs. Handles:
    - Lines with KEY=value format
    - Comments (lines starting with #)
    - Empty lines (ignored)
    - Whitespace around keys and values (stripped)
    - Values containing = characters (split only on first =)

    Args:
        path: Path to the .env file.

    Returns:
        Dictionary of key-value pairs from the file.
        Empty dict if file doesn't exist.
    """
    if not path.exists():
        return {}

    env: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Only process lines with = (key=value format)
            if "=" in line:
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    return env


def find_env_sandbox(start_dir: Optional[Path] = None) -> Optional[Path]:
    """Find .env.sandbox by walking up the directory tree.

    Walks up from start_dir (or cwd) looking for .env.sandbox file.
    Stops at the filesystem root or after 10 levels (safety limit).

    Args:
        start_dir: Starting directory (defaults to cwd).

    Returns:
        Path to .env.sandbox if found, None otherwise.
    """
    if start_dir is None:
        start_dir = Path.cwd()

    current = start_dir.resolve()

    # Walk up to find .env.sandbox (max 10 levels to avoid infinite loop)
    for _ in range(10):
        env_file = current / ".env.sandbox"
        if env_file.exists():
            return env_file

        parent = current.parent
        if parent == current:
            # Reached filesystem root
            break
        current = parent

    return None


def resolve_api_url(
    explicit_url: Optional[str] = None,
    explicit_port: Optional[int] = None,
    cwd: Optional[Path] = None,
) -> str:
    """Determine which KTRDR backend to target.

    Priority order (highest to lowest):
    1. explicit_url: Explicit --url flag, always wins
    2. explicit_port: --port flag, convenience for localhost
    3. .env.sandbox file: Auto-detect from current directory tree
    4. Default: http://localhost:8000

    IMPORTANT: We read the .env.sandbox FILE directly, not environment
    variables. This avoids "env var pollution" between terminal sessions.

    Args:
        explicit_url: Value from --url flag
        explicit_port: Value from --port flag
        cwd: Current working directory (defaults to actual cwd)

    Returns:
        Full API URL (e.g., "http://localhost:8001")
    """
    # Priority 1: Explicit --url flag
    if explicit_url:
        return explicit_url.rstrip("/")

    # Priority 2: Explicit --port flag
    if explicit_port:
        return f"http://localhost:{explicit_port}"

    # Priority 3: Auto-detect from .env.sandbox
    if cwd is None:
        cwd = Path.cwd()

    env_file = find_env_sandbox(cwd)
    if env_file:
        config = parse_dotenv_file(env_file)
        if port := config.get("KTRDR_API_PORT"):
            return f"http://localhost:{port}"

    # Priority 4: Default
    return "http://localhost:8000"


def get_sandbox_context(cwd: Optional[Path] = None) -> Optional[dict[str, str]]:
    """Get sandbox context if in a sandbox directory.

    Returns the parsed .env.sandbox file contents if the current (or specified)
    directory is within a sandbox directory tree.

    Args:
        cwd: Current working directory (defaults to actual cwd).

    Returns:
        Dict of env vars from .env.sandbox, or None if not in sandbox.
    """
    if cwd is None:
        cwd = Path.cwd()

    env_file = find_env_sandbox(cwd)
    if env_file:
        return parse_dotenv_file(env_file)
    return None


def get_sandbox_var(name: str, default: str | None = None) -> str | None:
    """Get a sandbox environment variable with proper fallback chain.

    Lookup priority:
    1. os.environ (explicit env var)
    2. .env.sandbox file (sandbox-specific config)
    3. default value

    This centralizes the lookup pattern so callers don't need to implement
    the fallback logic themselves.

    Args:
        name: Environment variable name (e.g., "KTRDR_JAEGER_OTLP_GRPC_PORT")
        default: Default value if not found anywhere

    Returns:
        The value from highest priority source, or default if not found.
    """
    import os

    # Priority 1: Explicit env var
    if value := os.environ.get(name):
        return value

    # Priority 2: .env.sandbox file
    if sandbox_env := get_sandbox_context():
        if value := sandbox_env.get(name):
            return value

    # Priority 3: Default
    return default
