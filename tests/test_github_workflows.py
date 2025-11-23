"""Tests for GitHub Actions workflow configuration.

These tests validate the structure and configuration of CI/CD workflows
to ensure they meet the requirements specified in the deployment architecture.
"""

from pathlib import Path

import pytest
import yaml


class TestBuildImagesWorkflow:
    """Test the build-images.yml GitHub Actions workflow."""

    @pytest.fixture
    def workflow_path(self) -> Path:
        """Path to the build-images workflow file."""
        return Path(".github/workflows/build-images.yml")

    @pytest.fixture
    def workflow(self, workflow_path: Path) -> dict:
        """Load and parse the workflow YAML."""
        assert workflow_path.exists(), f"Workflow file not found: {workflow_path}"
        with open(workflow_path) as f:
            return yaml.safe_load(f)

    def test_workflow_file_exists(self, workflow_path: Path):
        """Verify workflow file is created."""
        assert workflow_path.exists(), f"Workflow file must exist at {workflow_path}"

    def test_workflow_name(self, workflow: dict):
        """Verify workflow has a descriptive name."""
        assert "name" in workflow, "Workflow must have a name"
        assert (
            "Build" in workflow["name"] or "Image" in workflow["name"]
        ), "Workflow name should indicate it builds images"

    def test_triggers_on_push_to_main(self, workflow: dict):
        """Verify workflow triggers on push to main branch."""
        # YAML parses 'on:' as boolean True, so check for both
        triggers = workflow.get("on") or workflow.get(True)
        assert triggers is not None, "Workflow must have triggers"

        assert "push" in triggers, "Workflow must trigger on push"
        push_config = triggers["push"]
        assert "branches" in push_config, "Push trigger must specify branches"
        assert "main" in push_config["branches"], "Must trigger on push to main"

    def test_manual_trigger_available(self, workflow: dict):
        """Verify workflow has manual trigger (workflow_dispatch)."""
        # YAML parses 'on:' as boolean True, so check for both
        triggers = workflow.get("on") or workflow.get(True)
        assert triggers is not None, "Workflow must have triggers"
        assert (
            "workflow_dispatch" in triggers
        ), "Workflow must support manual trigger via workflow_dispatch"

    def test_uses_docker_buildx(self, workflow: dict):
        """Verify workflow uses Docker Buildx for efficient builds."""
        jobs = workflow["jobs"]
        assert len(jobs) > 0, "Workflow must have at least one job"

        # Check for Buildx setup in any job
        buildx_found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "setup-buildx-action" in uses:
                    buildx_found = True
                    break
            if buildx_found:
                break

        assert buildx_found, "Workflow must use docker/setup-buildx-action"

    def test_authenticates_to_ghcr(self, workflow: dict):
        """Verify workflow authenticates to GitHub Container Registry."""
        jobs = workflow["jobs"]

        # Check for GHCR login in any job
        login_found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "login-action" in uses:
                    with_config = step.get("with", {})
                    registry = with_config.get("registry", "")
                    if "ghcr.io" in registry or "${{ env.REGISTRY }}" in registry:
                        login_found = True
                        break
            if login_found:
                break

        assert (
            login_found
        ), "Workflow must authenticate to GHCR using docker/login-action"

    def test_tags_with_sha(self, workflow: dict):
        """Verify workflow tags images with git SHA."""
        jobs = workflow["jobs"]

        sha_tag_found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "metadata-action" in uses:
                    with_config = step.get("with", {})
                    tags = with_config.get("tags", "")
                    if "sha" in tags.lower():
                        sha_tag_found = True
                        break
            if sha_tag_found:
                break

        assert sha_tag_found, "Workflow must tag images with git SHA"

    def test_tags_with_latest(self, workflow: dict):
        """Verify workflow tags images with 'latest'."""
        jobs = workflow["jobs"]

        latest_tag_found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "metadata-action" in uses:
                    with_config = step.get("with", {})
                    tags = with_config.get("tags", "")
                    if "latest" in tags.lower():
                        latest_tag_found = True
                        break
            if latest_tag_found:
                break

        assert latest_tag_found, "Workflow must tag images with 'latest'"

    def test_uses_github_token(self, workflow: dict):
        """Verify workflow uses GITHUB_TOKEN for authentication (not a PAT)."""
        jobs = workflow["jobs"]

        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "login-action" in uses:
                    with_config = step.get("with", {})
                    password = with_config.get("password", "")
                    assert (
                        "GITHUB_TOKEN" in password
                    ), "GHCR authentication should use GITHUB_TOKEN"

    def test_has_proper_permissions(self, workflow: dict):
        """Verify job has necessary permissions for GHCR."""
        jobs = workflow["jobs"]

        for _job_name, job_config in jobs.items():
            permissions = job_config.get("permissions", {})
            assert (
                permissions.get("contents") == "read"
            ), "Job must have contents: read permission"
            assert (
                permissions.get("packages") == "write"
            ), "Job must have packages: write permission for GHCR"

    def test_uses_build_cache(self, workflow: dict):
        """Verify workflow uses GitHub Actions cache for faster builds."""
        jobs = workflow["jobs"]

        cache_found = False
        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "build-push-action" in uses:
                    with_config = step.get("with", {})
                    cache_from = with_config.get("cache-from", "")
                    cache_to = with_config.get("cache-to", "")
                    if "gha" in cache_from and "gha" in cache_to:
                        cache_found = True
                        break
            if cache_found:
                break

        assert cache_found, "Workflow must use GitHub Actions cache (type=gha)"

    def test_builds_correct_dockerfile(self, workflow: dict):
        """Verify workflow builds from the correct Dockerfile."""
        jobs = workflow["jobs"]

        for _job_name, job_config in jobs.items():
            steps = job_config.get("steps", [])
            for step in steps:
                uses = step.get("uses", "")
                if "build-push-action" in uses:
                    with_config = step.get("with", {})
                    dockerfile = with_config.get("file", "")
                    assert (
                        "docker/backend/Dockerfile" in dockerfile
                    ), "Must build from docker/backend/Dockerfile"
