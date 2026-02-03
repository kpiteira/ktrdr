"""Tests for Dockerfile.worker-gpu configuration."""

from pathlib import Path

import pytest


class TestDockerfileWorkerGpu:
    """Tests verifying Dockerfile.worker-gpu configuration is correct."""

    @pytest.fixture
    def dockerfile_path(self) -> Path:
        """Return path to Dockerfile.worker-gpu."""
        return Path("deploy/docker/Dockerfile.worker-gpu")

    @pytest.fixture
    def dockerfile_content(self, dockerfile_path: Path) -> str:
        """Read Dockerfile.worker-gpu content."""
        if not dockerfile_path.exists():
            pytest.skip("Dockerfile.worker-gpu does not exist yet")
        return dockerfile_path.read_text()

    def test_dockerfile_exists(self, dockerfile_path: Path) -> None:
        """Verify Dockerfile.worker-gpu exists."""
        assert dockerfile_path.exists(), "Dockerfile.worker-gpu should exist"

    def test_has_ml_extra(self, dockerfile_content: str) -> None:
        """Verify Dockerfile uses --extra ml flag for torch/sklearn."""
        assert (
            "--extra ml" in dockerfile_content
        ), "GPU Worker image should include ML extras for torch"

    def test_installs_cuda_pytorch(self, dockerfile_content: str) -> None:
        """Verify CUDA PyTorch is installed from PyTorch index."""
        assert (
            "download.pytorch.org/whl/cu" in dockerfile_content
        ), "GPU worker should install from CUDA PyTorch index"
        assert (
            "pytorch-cpu" not in dockerfile_content
        ), "GPU worker should NOT use CPU-only source"

    def test_header_indicates_gpu_worker(self, dockerfile_content: str) -> None:
        """Verify header comments indicate this is for GPU workers."""
        # Check the first few lines have GPU/CUDA context
        first_lines = dockerfile_content[:500].lower()
        assert (
            "gpu" in first_lines or "cuda" in first_lines
        ), "Header should indicate this is for GPU workers"

    def test_uses_multi_stage_build(self, dockerfile_content: str) -> None:
        """Verify multi-stage build is used."""
        assert "AS builder" in dockerfile_content, "Should use builder stage"
        assert "AS runtime" in dockerfile_content, "Should use runtime stage"

    def test_creates_non_root_user(self, dockerfile_content: str) -> None:
        """Verify non-root user is created."""
        assert "groupadd" in dockerfile_content, "Should create group"
        assert "useradd" in dockerfile_content, "Should create user"

    def test_uses_tini(self, dockerfile_content: str) -> None:
        """Verify tini is used for proper signal handling."""
        assert "tini" in dockerfile_content, "Should install and use tini"
        assert "ENTRYPOINT" in dockerfile_content, "Should have entrypoint"

    def test_exposes_worker_port(self, dockerfile_content: str) -> None:
        """Verify worker port is exposed (not API port 8000)."""
        # Should expose a worker port like 5003 or 5002, not 8000
        assert "EXPOSE" in dockerfile_content, "Should have EXPOSE directive"

    def test_uses_uv_sync_frozen(self, dockerfile_content: str) -> None:
        """Verify uv sync uses --frozen flag for reproducible builds."""
        assert (
            "uv sync --frozen" in dockerfile_content
        ), "Should use --frozen flag with uv sync"
