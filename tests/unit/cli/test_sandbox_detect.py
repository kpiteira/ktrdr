"""Tests for sandbox auto-detection module.

Tests the URL resolution logic that determines which backend to target
based on flags and current directory's .env.sandbox file.

Key design decision (from DESIGN.md Decision 10):
We read the .env.sandbox FILE directly, NOT environment variables.
This avoids "env var pollution" between terminal sessions.
"""

from pathlib import Path

import pytest

from ktrdr.cli.sandbox_detect import (
    DEFAULT_API_PORT,
    find_env_sandbox,
    get_effective_api_url,
    get_sandbox_context,
    get_url_override,
    normalize_api_url,
    parse_dotenv_file,
    resolve_api_url,
    set_url_override,
)


class TestParseDotenvFile:
    """Tests for parse_dotenv_file() function."""

    def test_parse_dotenv_file_parses_values(self, tmp_path: Path) -> None:
        """Key=value pairs are parsed correctly."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "KTRDR_API_PORT=8001\n" "SLOT_NUMBER=1\n" "INSTANCE_ID=ktrdr--feat-test\n"
        )

        result = parse_dotenv_file(env_file)

        assert result["KTRDR_API_PORT"] == "8001"
        assert result["SLOT_NUMBER"] == "1"
        assert result["INSTANCE_ID"] == "ktrdr--feat-test"

    def test_parse_dotenv_file_ignores_comments(self, tmp_path: Path) -> None:
        """Lines starting with # are ignored."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "# This is a comment\n"
            "KTRDR_API_PORT=8002\n"
            "# Another comment\n"
            "SLOT_NUMBER=2\n"
        )

        result = parse_dotenv_file(env_file)

        assert len(result) == 2
        assert result["KTRDR_API_PORT"] == "8002"
        assert "#" not in str(result)

    def test_parse_dotenv_file_ignores_empty_lines(self, tmp_path: Path) -> None:
        """Empty lines are ignored."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8003\n" "\n" "   \n" "SLOT_NUMBER=3\n")

        result = parse_dotenv_file(env_file)

        assert len(result) == 2

    def test_parse_dotenv_file_handles_values_with_equals(self, tmp_path: Path) -> None:
        """Values containing = are parsed correctly."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("DATABASE_URL=postgres://user:pass=123@host/db\n")

        result = parse_dotenv_file(env_file)

        assert result["DATABASE_URL"] == "postgres://user:pass=123@host/db"

    def test_parse_dotenv_file_returns_empty_for_missing_file(
        self, tmp_path: Path
    ) -> None:
        """Returns empty dict when file doesn't exist."""
        non_existent = tmp_path / ".env.sandbox"

        result = parse_dotenv_file(non_existent)

        assert result == {}

    def test_parse_dotenv_file_strips_whitespace(self, tmp_path: Path) -> None:
        """Whitespace around keys and values is stripped."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("  KTRDR_API_PORT  =  8004  \n")

        result = parse_dotenv_file(env_file)

        assert result["KTRDR_API_PORT"] == "8004"


class TestFindEnvSandbox:
    """Tests for find_env_sandbox() function."""

    def test_find_env_sandbox_in_current_dir(self, tmp_path: Path) -> None:
        """Found when .env.sandbox is in the current directory."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8001\n")

        result = find_env_sandbox(tmp_path)

        assert result == env_file

    def test_find_env_sandbox_in_parent_dir(self, tmp_path: Path) -> None:
        """Found when .env.sandbox is in a parent directory."""
        # Create parent/.env.sandbox
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8002\n")

        # Create nested subdirectory
        nested = tmp_path / "src" / "ktrdr" / "cli"
        nested.mkdir(parents=True)

        result = find_env_sandbox(nested)

        assert result == env_file

    def test_find_env_sandbox_not_found(self, tmp_path: Path) -> None:
        """Returns None when no .env.sandbox exists in tree."""
        # Create a directory without .env.sandbox
        subdir = tmp_path / "some" / "deep" / "path"
        subdir.mkdir(parents=True)

        result = find_env_sandbox(subdir)

        assert result is None

    def test_find_env_sandbox_uses_cwd_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uses current working directory when start_dir is None."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8003\n")
        monkeypatch.chdir(tmp_path)

        result = find_env_sandbox()

        assert result == env_file


class TestResolveApiUrl:
    """Tests for resolve_api_url() function."""

    def test_resolve_url_explicit_url_wins(self, tmp_path: Path) -> None:
        """Priority 1: Explicit --url flag always wins."""
        # Create .env.sandbox with different port
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8001\n")

        result = resolve_api_url(
            explicit_url="http://remote:9000",
            explicit_port=8002,  # Should be ignored
            cwd=tmp_path,  # Has .env.sandbox, should be ignored
        )

        assert result == "http://remote:9000"

    def test_resolve_url_explicit_url_strips_trailing_slash(self) -> None:
        """Explicit URL has trailing slash stripped."""
        result = resolve_api_url(explicit_url="http://localhost:8000/")

        assert result == "http://localhost:8000"

    def test_resolve_url_port_over_auto(self, tmp_path: Path) -> None:
        """Priority 2: --port flag overrides auto-detection."""
        # Create .env.sandbox with different port
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8001\n")

        result = resolve_api_url(
            explicit_port=8005,
            cwd=tmp_path,  # Has .env.sandbox, should be ignored
        )

        assert result == "http://localhost:8005"

    def test_resolve_url_auto_from_file(self, tmp_path: Path) -> None:
        """Priority 3: Auto-detect from .env.sandbox file."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8003\n")

        result = resolve_api_url(cwd=tmp_path)

        assert result == "http://localhost:8003"

    def test_resolve_url_auto_walks_up_tree(self, tmp_path: Path) -> None:
        """Auto-detection walks up directory tree to find .env.sandbox."""
        # Create .env.sandbox in root
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8004\n")

        # Create nested subdirectory
        nested = tmp_path / "ktrdr" / "cli"
        nested.mkdir(parents=True)

        result = resolve_api_url(cwd=nested)

        assert result == "http://localhost:8004"

    def test_resolve_url_default_fallback(self, tmp_path: Path) -> None:
        """Priority 4: Default to localhost:8000 when no other source."""
        # tmp_path has no .env.sandbox

        result = resolve_api_url(cwd=tmp_path)

        assert result == "http://localhost:8000"

    def test_resolve_url_default_with_empty_sandbox_file(self, tmp_path: Path) -> None:
        """Falls back to default if .env.sandbox exists but has no port."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("INSTANCE_ID=ktrdr--test\n")  # No KTRDR_API_PORT

        result = resolve_api_url(cwd=tmp_path)

        assert result == "http://localhost:8000"


class TestGetSandboxContext:
    """Tests for get_sandbox_context() function."""

    def test_get_sandbox_context_returns_env_vars(self, tmp_path: Path) -> None:
        """Returns dict of env vars when in sandbox directory."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text(
            "KTRDR_API_PORT=8001\n" "SLOT_NUMBER=1\n" "INSTANCE_ID=ktrdr--feat-test\n"
        )

        result = get_sandbox_context(tmp_path)

        assert result is not None
        assert result["KTRDR_API_PORT"] == "8001"
        assert result["SLOT_NUMBER"] == "1"
        assert result["INSTANCE_ID"] == "ktrdr--feat-test"

    def test_get_sandbox_context_returns_none_outside_sandbox(
        self, tmp_path: Path
    ) -> None:
        """Returns None when not in a sandbox directory."""
        result = get_sandbox_context(tmp_path)

        assert result is None

    def test_get_sandbox_context_uses_cwd_by_default(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Uses current working directory when cwd is None."""
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8002\n")
        monkeypatch.chdir(tmp_path)

        result = get_sandbox_context()

        assert result is not None
        assert result["KTRDR_API_PORT"] == "8002"


class TestDefaultApiPort:
    """Tests for DEFAULT_API_PORT constant."""

    def test_default_api_port_is_8000(self) -> None:
        """Default API port should be 8000."""
        assert DEFAULT_API_PORT == 8000


class TestUrlOverride:
    """Tests for set_url_override() and get_url_override() functions.

    These functions manage the global URL override set by the --url flag.
    """

    def test_url_override_initially_none(self) -> None:
        """URL override is None when not set."""
        # Clear any previous state
        set_url_override(None)
        assert get_url_override() is None

    def test_set_and_get_url_override(self) -> None:
        """Can set and retrieve URL override."""
        try:
            set_url_override("http://home-lab:8000/api/v1")
            assert get_url_override() == "http://home-lab:8000/api/v1"
        finally:
            set_url_override(None)

    def test_url_override_can_be_cleared(self) -> None:
        """URL override can be cleared by setting to None."""
        try:
            set_url_override("http://example.com:8000/api/v1")
            assert get_url_override() is not None

            set_url_override(None)
            assert get_url_override() is None
        finally:
            set_url_override(None)


class TestGetEffectiveApiUrl:
    """Tests for get_effective_api_url() function.

    This function returns the URL that will appear in error messages.
    It follows the same priority as URL resolution:
    1. URL override (if set via --url flag)
    2. Sandbox detection (if .env.sandbox exists)
    3. Config default
    """

    def test_returns_url_override_when_set(self) -> None:
        """Returns URL override when set (highest priority)."""
        try:
            set_url_override("http://home-lab:8000/api/v1")
            result = get_effective_api_url()
            assert result == "http://home-lab:8000/api/v1"
        finally:
            set_url_override(None)

    def test_returns_sandbox_url_when_in_sandbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns sandbox URL when .env.sandbox exists and no override."""
        # Create a sandbox .env file with custom port
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8002\n")
        monkeypatch.chdir(tmp_path)

        # Ensure no URL override
        set_url_override(None)

        result = get_effective_api_url()

        assert "8002" in result
        assert result == "http://localhost:8002/api/v1"

    def test_url_override_beats_sandbox_detection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """URL override takes priority over sandbox detection."""
        # Create a sandbox .env file
        env_file = tmp_path / ".env.sandbox"
        env_file.write_text("KTRDR_API_PORT=8002\n")
        monkeypatch.chdir(tmp_path)

        try:
            # Set URL override - should win over sandbox
            set_url_override("http://prod-server:8000/api/v1")

            result = get_effective_api_url()

            assert result == "http://prod-server:8000/api/v1"
            assert "8002" not in result
        finally:
            set_url_override(None)

    def test_returns_config_default_when_no_override_or_sandbox(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Returns config default when no override and no sandbox."""
        # tmp_path has no .env.sandbox
        monkeypatch.chdir(tmp_path)
        set_url_override(None)

        result = get_effective_api_url()

        # Should be the config default (localhost:8000)
        assert "localhost" in result or "127.0.0.1" in result
        assert "8000" in result


class TestNormalizeApiUrl:
    """Tests for normalize_api_url() function.

    This function normalizes URLs by:
    - Adding http:// if no protocol specified
    - Adding default port (8000) if no port specified
    - Adding /api/v1 if no API path present
    - Stripping trailing slashes
    """

    def test_normalize_adds_http_protocol(self) -> None:
        """Adds http:// when no protocol specified."""
        result = normalize_api_url("localhost:8000")
        assert result.startswith("http://")

    def test_normalize_preserves_http_protocol(self) -> None:
        """Preserves existing http:// protocol."""
        result = normalize_api_url("http://localhost:8000")
        assert result.startswith("http://")
        assert "http://http://" not in result

    def test_normalize_preserves_https_protocol(self) -> None:
        """Preserves existing https:// protocol."""
        result = normalize_api_url("https://secure.example.com:8000")
        assert result.startswith("https://")

    def test_normalize_adds_default_port(self) -> None:
        """Adds default port (8000) when no port specified."""
        result = normalize_api_url("http://localhost")
        assert ":8000" in result

    def test_normalize_preserves_custom_port(self) -> None:
        """Preserves custom port when specified."""
        result = normalize_api_url("http://localhost:9000")
        assert ":9000" in result
        assert ":8000" not in result

    def test_normalize_adds_api_v1_path(self) -> None:
        """Adds /api/v1 when no API path present."""
        result = normalize_api_url("http://localhost:8000")
        assert result.endswith("/api/v1")

    def test_normalize_preserves_existing_api_path(self) -> None:
        """Preserves existing /api/ path."""
        result = normalize_api_url("http://localhost:8000/api/v2")
        assert result.endswith("/api/v2")
        assert "/api/v1" not in result

    def test_normalize_strips_trailing_slash(self) -> None:
        """Strips trailing slash before adding API path."""
        result = normalize_api_url("http://localhost:8000/")
        assert not result.endswith("/api/v1/")
        assert result.endswith("/api/v1")

    def test_normalize_handles_empty_string(self) -> None:
        """Returns empty string for empty input."""
        result = normalize_api_url("")
        assert result == ""

    def test_normalize_full_transformation(self) -> None:
        """Tests full transformation from minimal to complete URL."""
        result = normalize_api_url("backend.example.com")
        assert result == "http://backend.example.com:8000/api/v1"

    def test_normalize_already_complete_url(self) -> None:
        """Preserves already complete URL."""
        url = "http://localhost:8001/api/v1"
        result = normalize_api_url(url)
        assert result == url
