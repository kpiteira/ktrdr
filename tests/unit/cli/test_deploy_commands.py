"""Tests for deploy commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from ktrdr.cli.deploy_commands import deploy_app

runner = CliRunner()


class TestDeployCore:
    """Tests for deploy core command."""

    def test_dry_run_shows_commands(self):
        """Test dry-run mode shows commands without executing."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.get_latest_sha_tag") as mock_sha,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {
                "db_username": "ktrdr",
                "db_password": "secret",
                "jwt_secret": "jwt",
                "grafana_password": "grafana",
                "ghcr_token": "ghp_xxx",
            }
            mock_sha.return_value = "sha-abc1234"

            result = runner.invoke(deploy_app, ["core", "--dry-run"])

            assert result.exit_code == 0
            assert "DRY RUN" in result.output or "Dry run" in result.output
            mock_docker.assert_called_once()
            assert mock_docker.call_args[1]["dry_run"] is True
            mock_ssh.assert_called_once()
            assert mock_ssh.call_args[1]["dry_run"] is True

    def test_validation_failure_aborts(self):
        """Test that validation failures abort deployment."""
        with patch(
            "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
        ) as mock_validate:
            mock_validate.return_value = (
                False,
                ["DNS resolution failed", "SSH failed"],
            )

            result = runner.invoke(deploy_app, ["core"])

            assert result.exit_code != 0
            # Check combined output (typer combines stdout/stderr)
            assert "DNS resolution failed" in result.output

    def test_skip_validation_option(self):
        """Test --skip-validation option skips prerequisite checks."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.get_latest_sha_tag") as mock_sha,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr"),
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env"),
        ):
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_sha.return_value = "sha-abc1234"

            result = runner.invoke(
                deploy_app, ["core", "--skip-validation", "--dry-run"]
            )

            assert result.exit_code == 0
            mock_validate.assert_not_called()


class TestDeployWorkers:
    """Tests for deploy workers command."""

    def test_deploy_all_workers(self):
        """Test deploying to all workers."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.get_latest_sha_tag") as mock_sha,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_sha.return_value = "sha-abc1234"

            result = runner.invoke(deploy_app, ["workers", "all", "--dry-run"])

            assert result.exit_code == 0
            # Should deploy to 2 worker hosts (workers-b and workers-c)
            assert mock_docker.call_count == 2
            assert mock_ssh.call_count == 2

    def test_deploy_single_worker(self):
        """Test deploying to a specific worker."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.get_latest_sha_tag") as mock_sha,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_sha.return_value = "sha-abc1234"

            result = runner.invoke(deploy_app, ["workers", "workers-b", "--dry-run"])

            assert result.exit_code == 0
            # Should only deploy to 1 worker host
            assert mock_docker.call_count == 1
            assert mock_ssh.call_count == 1

    def test_worker_validation_failure_continues(self):
        """Test that worker validation failure skips that worker but continues."""

        def validate_side_effect(host):
            if "workers-b" in host:
                return (False, ["SSH failed"])
            return (True, [])

        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.get_latest_sha_tag") as mock_sha,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.side_effect = validate_side_effect
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_sha.return_value = "sha-abc1234"

            result = runner.invoke(deploy_app, ["workers", "all", "--dry-run"])

            # Should still succeed overall (workers-c deployed, workers-b skipped)
            assert result.exit_code == 0
            # Should only deploy to 1 worker host (skipped workers-b)
            assert mock_docker.call_count == 1
            assert mock_ssh.call_count == 1


class TestDeployStatus:
    """Tests for deploy status command."""

    def test_status_core(self):
        """Test checking core services status."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            mock_ssh.return_value = "SERVICE\tSTATUS\nbackend\tUp"

            result = runner.invoke(deploy_app, ["status", "core"])

            assert result.exit_code == 0
            mock_ssh.assert_called_once()

    def test_status_all(self):
        """Test checking all services status."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            mock_ssh.return_value = "SERVICE\tSTATUS\nservice\tUp"

            result = runner.invoke(deploy_app, ["status", "all"])

            assert result.exit_code == 0
            # Should check backend + 2 workers = 3 calls
            assert mock_ssh.call_count == 3
