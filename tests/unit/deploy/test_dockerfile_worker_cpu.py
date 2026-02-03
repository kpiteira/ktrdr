"""Tests for Dockerfile.worker-cpu configuration."""

from pathlib import Path

import pytest


class TestDockerfileWorkerCpu:
    """Tests verifying Dockerfile.worker-cpu configuration is correct."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        """Return path to Dockerfile.worker-cpu."""
        return Path("deploy/docker/Dockerfile.worker-cpu")

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        """Read Dockerfile.worker-cpu content."""
        if not dockerfile_path.exists():
            pytest.skip("Dockerfile.worker-cpu does not exist yet")
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self, dockerfile_path: Path) -> None:
        """Verify Dockerfile.worker-cpu exists."""
        assert dockerfile_path.exists(), "Dockerfile.worker-cpu should exist"

    def test_has_ml_extra(self, dockerfile_content: str) -> None:
        """Verify Dockerfile uses --extra ml flag for torch/sklearn."""
        assert "--extra ml" in dockerfile_content, (
            "Worker image should include ML extras for torch"
        )

    def test_injects_cpu_pytorch_source(self, dockerfile_content: str) -> None:
        """Verify CPU-only PyTorch source is injected."""
        assert "pytorch-cpu" in dockerfile_content, "Should inject pytorch-cpu index"
        assert "download.pytorch.org/whl/cpu" in dockerfile_content, (
            "Should use CPU wheel URL"
        )

    def test_source_injection_before_sync(self, dockerfile_content: str) -> None:
        """Verify source injection happens BEFORE uv sync --extra ml."""
        # Find positions
        injection_pos = dockerfile_content.find("pytorch-cpu")
        sync_ml_pos = dockerfile_content.find("uv sync --frozen")

        assert injection_pos != -1, "Should have CPU source injection"
        assert sync_ml_pos != -1, "Should have uv sync command"
        assert injection_pos < sync_ml_pos, (
            "CPU source should be injected BEFORE uv sync"
        )

    def test_uses_multi_stage_build(self, dockerfile_content: str) -> None:
        """Verify multi-stage build is used."""
        assert "AS builder" in dockerfile_content, "Should use builder stage"
        assert "AS runtime" in dockerfile_content, "Should use runtime stage"

    def test_creates_non_root_user(self, dockerfile_content: str) -> None:
        """Verify non-root user is created."""
        assert "groupadd" in dockerfile_content, "Should create group"
        assert "useradd" in dockerfile_content, "Should create user"
        assert "USER ktrdr" in dockerfile_content, "Should switch to non-root user"

    def test_uses_tini(self, dockerfile_content: str) -> None:
        """Verify tini is used for proper signal handling."""
        assert "tini" in dockerfile_content, "Should install and use tini"
        assert "ENTRYPOINT" in dockerfile_content, "Should have entrypoint"

    def test_exposes_worker_port(self, dockerfile_content: str) -> None:
        """Verify worker port is exposed."""
        assert "EXPOSE 5003" in dockerfile_content, "Should expose worker port 5003"

    def test_copies_required_directories(self, dockerfile_content: str) -> None:
        """Verify all required directories are copied."""
        required = ["ktrdr", "config", "strategies"]
        for dir_name in required:
            assert f"/app/{dir_name}" in dockerfile_content, (
                f"Should copy {dir_name} directory"
            )

    def test_uses_uv_sync_frozen(self, dockerfile_content: str) -> None:
        """Verify uv sync uses --frozen flag for reproducible builds."""
        assert "uv sync --frozen" in dockerfile_content, (
            "Should use --frozen flag with uv sync"
        )
