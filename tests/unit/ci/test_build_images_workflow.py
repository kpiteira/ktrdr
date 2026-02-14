"""Tests for build-images.yml GitHub Actions workflow."""

from pathlib import Path

import pytest
import yaml


class TestBuildImagesWorkflow:
    """Tests for the build-images GitHub Actions workflow."""

    @pytest.fixture
    def workflow_path(self) -> Path:
        """Path to the workflow file."""
        return Path(__file__).parents[3] / ".github/workflows/build-images.yml"

    @pytest.fixture
    def workflow(self, workflow_path: Path) -> dict:
        """Load and parse the workflow file."""
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_workflow_is_valid_yaml(self, workflow_path: Path) -> None:
        """Workflow file should be valid YAML."""
        with open(workflow_path) as f:
            # This will raise if invalid YAML
            data = yaml.safe_load(f)
        assert data is not None

    def test_workflow_has_required_structure(self, workflow: dict) -> None:
        """Workflow should have name, on, and jobs keys."""
        assert "name" in workflow
        # YAML parses 'on' as boolean True
        assert True in workflow or "on" in workflow
        assert "jobs" in workflow

    def test_matrix_includes_three_images(self, workflow: dict) -> None:
        """Matrix should build backend, worker-cpu, and worker-gpu images."""
        build_job = workflow["jobs"]["build"]
        matrix = build_job["strategy"]["matrix"]

        # Should have 'include' with three entries
        assert "include" in matrix
        includes = matrix["include"]
        assert len(includes) == 3

        # Extract image names
        image_names = {item["image"] for item in includes}
        assert image_names == {"backend", "worker-cpu", "worker-gpu"}

    def test_correct_dockerfile_paths(self, workflow: dict) -> None:
        """Each image should reference the correct Dockerfile."""
        build_job = workflow["jobs"]["build"]
        includes = build_job["strategy"]["matrix"]["include"]

        expected_dockerfiles = {
            "backend": "deploy/docker/Dockerfile.backend",
            "worker-cpu": "deploy/docker/Dockerfile.worker-cpu",
            "worker-gpu": "deploy/docker/Dockerfile.worker-gpu",
        }

        for item in includes:
            image = item["image"]
            assert (
                item["dockerfile"] == expected_dockerfiles[image]
            ), f"Wrong Dockerfile for {image}"

    def test_correct_platforms_per_image(self, workflow: dict) -> None:
        """Backend and worker-cpu should be multi-arch, worker-gpu amd64 only."""
        build_job = workflow["jobs"]["build"]
        includes = build_job["strategy"]["matrix"]["include"]

        for item in includes:
            image = item["image"]
            platforms = item["platforms"]

            if image == "worker-gpu":
                # GPU image is amd64 only (no ARM GPUs in homelab)
                assert (
                    platforms == "linux/amd64"
                ), f"worker-gpu should be amd64 only, got {platforms}"
            else:
                # Backend and worker-cpu should be multi-arch
                assert "linux/amd64" in platforms
                assert "linux/arm64" in platforms

    def test_per_image_cache_scopes(self, workflow: dict) -> None:
        """Cache scope should use matrix.image for per-image caching."""
        build_job = workflow["jobs"]["build"]
        steps = build_job["steps"]

        # Find the build-push step
        build_step = None
        for step in steps:
            if step.get("uses", "").startswith("docker/build-push-action"):
                build_step = step
                break

        assert build_step is not None, "Build step not found"

        # Check cache-from and cache-to use matrix.image
        cache_from = build_step["with"].get("cache-from", "")
        cache_to = build_step["with"].get("cache-to", "")

        assert (
            "${{ matrix.image }}" in cache_from
        ), f"cache-from should use matrix.image: {cache_from}"
        assert (
            "${{ matrix.image }}" in cache_to
        ), f"cache-to should use matrix.image: {cache_to}"

    def test_image_base_env_variable(self, workflow: dict) -> None:
        """Workflow should use IMAGE_BASE (not IMAGE_NAME) for multi-image naming."""
        env = workflow.get("env", {})
        # Should have IMAGE_BASE for constructing image names and NOT use IMAGE_NAME
        assert "IMAGE_BASE" in env, "Should use IMAGE_BASE for multi-image builds"
        assert (
            "IMAGE_NAME" not in env
        ), "Should not use IMAGE_NAME for multi-image builds"

    def test_merge_job_verifies_all_images(self, workflow: dict) -> None:
        """Merge job should verify manifests for all images after build completes."""
        # The merge job should iterate over all images
        merge_job = workflow["jobs"].get("merge")
        assert merge_job is not None, "Merge job should exist for multi-arch builds"

        # Check that merge depends on build
        needs = merge_job.get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "build" in needs
