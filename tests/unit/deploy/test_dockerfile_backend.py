"""Tests for Dockerfile.backend configuration."""

from pathlib import Path

import pytest


class TestDockerfileBackend:
    """Tests verifying Dockerfile.backend configuration is correct."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        """Return path to Dockerfile.backend."""
        return Path("deploy/docker/Dockerfile.backend")

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        """Read Dockerfile.backend content."""
        if not dockerfile_path.exists():
            pytest.skip("Dockerfile.backend does not exist yet")
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self, dockerfile_path: Path) -> None:
        """Verify Dockerfile.backend exists."""
        assert dockerfile_path.exists(), "Dockerfile.backend should exist"

    def test_no_ml_extra(self, dockerfile_content: str) -> None:
        """Verify Dockerfile does NOT use --extra ml flag."""
        # Should NOT have --extra ml
        assert (
            "--extra ml" not in dockerfile_content
        ), "Production backend should NOT include ML extras"

    def test_uses_multi_stage_build(self, dockerfile_content: str) -> None:
        """Verify multi-stage build is used."""
        assert "AS builder" in dockerfile_content, "Should use builder stage"
        assert "AS runtime" in dockerfile_content, "Should use runtime stage"

    def test_creates_non_root_user(self, dockerfile_content: str) -> None:
        """Verify non-root user is created."""
        assert "groupadd" in dockerfile_content, "Should create group"
        assert "useradd" in dockerfile_content, "Should create user"
        assert (
            "USER ktrdr" in dockerfile_content or "USER $" in dockerfile_content
        ), "Should switch to non-root user"

    def test_user_created_before_copy(self, dockerfile_content: str) -> None:
        """Verify user is created BEFORE copying files with --chown.

        This is a key optimization from INTENT.md - creating user before
        COPY --chown prevents layer duplication.
        """
        # Find positions
        user_create_pos = dockerfile_content.find("useradd")
        copy_chown_pos = dockerfile_content.find("COPY --from=builder --chown")

        assert user_create_pos != -1, "Should have useradd command"
        assert copy_chown_pos != -1, "Should have COPY --chown command"
        assert (
            user_create_pos < copy_chown_pos
        ), "User should be created BEFORE COPY --chown commands"

    def test_has_healthcheck(self, dockerfile_content: str) -> None:
        """Verify healthcheck is configured."""
        assert "HEALTHCHECK" in dockerfile_content, "Should have healthcheck"
        assert (
            "/api/v1/health" in dockerfile_content
        ), "Healthcheck should use /api/v1/health endpoint"

    def test_uses_tini(self, dockerfile_content: str) -> None:
        """Verify tini is used for proper signal handling."""
        assert "tini" in dockerfile_content, "Should install and use tini"
        assert "ENTRYPOINT" in dockerfile_content, "Should have entrypoint"

    def test_exposes_correct_port(self, dockerfile_content: str) -> None:
        """Verify correct port is exposed."""
        assert "EXPOSE 8000" in dockerfile_content, "Should expose port 8000"

    def test_copies_required_directories(self, dockerfile_content: str) -> None:
        """Verify all required directories are copied."""
        required = ["ktrdr", "mcp", "config", "strategies", "alembic"]
        for dir_name in required:
            assert (
                f"/app/{dir_name}" in dockerfile_content
            ), f"Should copy {dir_name} directory"

    def test_uses_uv_sync_frozen(self, dockerfile_content: str) -> None:
        """Verify uv sync uses --frozen flag for reproducible builds."""
        assert (
            "uv sync --frozen" in dockerfile_content
        ), "Should use --frozen flag with uv sync"

    def test_uses_no_dev_flag(self, dockerfile_content: str) -> None:
        """Verify --no-dev flag is used to exclude dev dependencies."""
        assert (
            "--no-dev" in dockerfile_content
        ), "Should use --no-dev to exclude development dependencies"
