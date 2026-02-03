"""Tests for Dockerfile.dev configuration."""

from pathlib import Path

import pytest


class TestDockerfileDev:
    """Tests verifying Dockerfile.dev configuration is correct."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        """Return path to Dockerfile.dev."""
        return Path("deploy/docker/Dockerfile.dev")

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        """Read Dockerfile.dev content."""
        if not dockerfile_path.exists():
            pytest.skip("Dockerfile.dev does not exist")
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self, dockerfile_path: Path) -> None:
        """Verify Dockerfile.dev exists."""
        assert dockerfile_path.exists(), "Dockerfile.dev should exist"

    def test_has_ml_extra(self, dockerfile_content: str) -> None:
        """Verify Dockerfile uses --extra ml flag for torch/sklearn."""
        assert "--extra ml" in dockerfile_content, (
            "Dev image should include ML extras for torch"
        )

    def test_injects_cpu_pytorch_source(self, dockerfile_content: str) -> None:
        """Verify CPU-only PyTorch source is injected.

        Dev machines (Mac) don't have GPUs, so CPU torch saves ~2.8GB.
        """
        assert "pytorch-cpu" in dockerfile_content, (
            "Should inject pytorch-cpu index for smaller image"
        )
        assert "download.pytorch.org/whl/cpu" in dockerfile_content, (
            "Should use CPU wheel URL"
        )

    def test_source_injection_before_sync(self, dockerfile_content: str) -> None:
        """Verify source injection happens BEFORE uv sync --extra ml."""
        injection_pos = dockerfile_content.find("pytorch-cpu")
        sync_ml_pos = dockerfile_content.find("uv sync --frozen")

        assert injection_pos != -1, "Should have CPU source injection"
        assert sync_ml_pos != -1, "Should have uv sync command"
        assert injection_pos < sync_ml_pos, (
            "CPU source should be injected BEFORE uv sync"
        )

    def test_has_healthcheck(self, dockerfile_content: str) -> None:
        """Verify healthcheck is configured."""
        assert "HEALTHCHECK" in dockerfile_content, "Should have healthcheck"

    def test_exposes_api_port(self, dockerfile_content: str) -> None:
        """Verify dev image runs on API port."""
        # Dev runs the API server, so should be on 8000
        assert "8000" in dockerfile_content, "Should reference API port 8000"

    def test_has_reload_flag(self, dockerfile_content: str) -> None:
        """Verify dev image uses --reload for hot reloading."""
        assert "--reload" in dockerfile_content, "Dev image should enable hot reloading"

    def test_creates_non_root_user(self, dockerfile_content: str) -> None:
        """Verify non-root user is created."""
        assert "useradd" in dockerfile_content, "Should create user"
        assert "USER ktrdr" in dockerfile_content, "Should switch to non-root user"
