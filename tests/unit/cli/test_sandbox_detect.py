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
    find_env_sandbox,
    get_sandbox_context,
    parse_dotenv_file,
    resolve_api_url,
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
