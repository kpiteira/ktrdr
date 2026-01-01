"""Tests for deploy commands."""

from unittest.mock import patch

from typer.testing import CliRunner

from ktrdr.cli.deploy_commands import deploy_app

runner = CliRunner()


class TestDeployCore:
    """Tests for deploy core command."""

    def test_successful_deployment_non_dry_run(self):
        """Test successful non-dry-run deployment shows success message."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
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
            mock_docker.return_value = True
            mock_ssh.return_value = "output"

            result = runner.invoke(deploy_app, ["core", "--skip-validation"])

            assert result.exit_code == 0
            assert "deployed successfully" in result.output.lower()
            # Verify docker login was called without dry_run
            assert mock_docker.call_args[1]["dry_run"] is False
            # Verify ssh was called without dry_run
            assert mock_ssh.call_args[1]["dry_run"] is False

    def test_dry_run_shows_commands(self):
        """Test dry-run mode shows commands without executing."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
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
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr"),
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env"),
        ):
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}

            result = runner.invoke(
                deploy_app, ["core", "--skip-validation", "--dry-run"]
            )

            assert result.exit_code == 0
            mock_validate.assert_not_called()

    def test_secrets_fetch_failure_aborts(self):
        """Test that secrets fetch failure aborts deployment."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.side_effect = Exception("1Password error: not signed in")

            result = runner.invoke(deploy_app, ["core"])

            assert result.exit_code != 0
            assert "1Password error" in result.output

    def test_custom_tag_used(self):
        """Test that custom tag is used in deployment."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.return_value = True
            mock_ssh.return_value = "output"

            result = runner.invoke(
                deploy_app, ["core", "--tag", "sha-abc1234", "--skip-validation"]
            )

            assert result.exit_code == 0
            assert "sha-abc1234" in result.output

    def test_docker_login_failure_aborts(self):
        """Test that Docker login failure aborts deployment."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.side_effect = Exception("Docker login failed: unauthorized")

            result = runner.invoke(deploy_app, ["core"])

            assert result.exit_code != 0
            assert "Docker login failed" in result.output

    def test_ssh_deploy_failure_aborts(self):
        """Test that SSH deploy failure aborts deployment."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.return_value = True
            mock_ssh.side_effect = Exception("SSH command failed: connection refused")

            result = runner.invoke(deploy_app, ["core"])

            assert result.exit_code != 0
            assert "SSH command failed" in result.output


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
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}

            result = runner.invoke(deploy_app, ["workers", "all", "--dry-run"])

            assert result.exit_code == 0
            # Should deploy to 3 worker hosts (workers-b, workers-c, gpu)
            assert mock_docker.call_count == 3
            assert mock_ssh.call_count == 3

    def test_deploy_single_worker(self):
        """Test deploying to a specific worker."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}

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
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.side_effect = validate_side_effect
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}

            result = runner.invoke(deploy_app, ["workers", "all", "--dry-run"])

            # Should still succeed overall (workers-b skipped, workers-c and gpu deployed)
            assert result.exit_code == 0
            # Should deploy to 2 worker hosts (skipped workers-b, deployed workers-c + gpu)
            assert mock_docker.call_count == 2
            assert mock_ssh.call_count == 2

    def test_invalid_target_aborts(self):
        """Test that invalid target aborts deployment."""
        result = runner.invoke(deploy_app, ["workers", "invalid-target"])

        assert result.exit_code != 0
        assert "Invalid target" in result.output

    def test_workers_secrets_fetch_failure_aborts(self):
        """Test that secrets fetch failure aborts worker deployment."""
        with patch(
            "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
        ) as mock_secrets:
            mock_secrets.side_effect = Exception("1Password error: not signed in")

            result = runner.invoke(deploy_app, ["workers", "workers-b"])

            assert result.exit_code != 0
            assert "1Password error" in result.output

    def test_workers_custom_tag_used(self):
        """Test that custom tag is used in worker deployment."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.return_value = True
            mock_ssh.return_value = "output"

            result = runner.invoke(
                deploy_app,
                ["workers", "workers-b", "--tag", "sha-abc1234", "--skip-validation"],
            )

            assert result.exit_code == 0
            assert "sha-abc1234" in result.output

    def test_worker_docker_login_failure_skips(self):
        """Test that Docker login failure skips that worker."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}

            # First worker docker login fails, others succeed
            def docker_side_effect(host, **kwargs):
                if "workers-b" in host:
                    raise Exception("Docker login failed")
                return True

            mock_docker.side_effect = docker_side_effect

            result = runner.invoke(deploy_app, ["workers", "all", "--dry-run"])

            # Should still succeed overall (workers-c and gpu deployed)
            assert result.exit_code == 0
            # All 3 workers attempted docker login
            assert mock_docker.call_count == 3
            # Only 2 workers got to SSH step (workers-c and gpu)
            assert mock_ssh.call_count == 2

    def test_worker_ssh_failure_skips(self):
        """Test that SSH failure skips that worker."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.return_value = True

            # First worker SSH fails, others succeed
            def ssh_side_effect(host, **kwargs):
                if "workers-b" in host:
                    raise Exception("SSH command failed")
                return "ok"

            mock_ssh.side_effect = ssh_side_effect

            result = runner.invoke(deploy_app, ["workers", "all", "--skip-validation"])

            # Should still succeed overall (workers-c and gpu deployed)
            assert result.exit_code == 0
            # All 3 workers attempted SSH
            assert mock_ssh.call_count == 3

    def test_successful_worker_deployment_non_dry_run(self):
        """Test successful non-dry-run worker deployment shows success message."""
        with (
            patch(
                "ktrdr.cli.deploy_commands.validate_deployment_prerequisites"
            ) as mock_validate,
            patch(
                "ktrdr.cli.deploy_commands.fetch_secrets_from_1password"
            ) as mock_secrets,
            patch("ktrdr.cli.deploy_commands.docker_login_ghcr") as mock_docker,
            patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh,
        ):
            mock_validate.return_value = (True, [])
            mock_secrets.return_value = {"ghcr_token": "ghp_xxx"}
            mock_docker.return_value = True
            mock_ssh.return_value = "ok"

            result = runner.invoke(
                deploy_app, ["workers", "workers-b", "--skip-validation"]
            )

            assert result.exit_code == 0
            assert "deployed successfully" in result.output.lower()


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
            # Should check core + 3 workers (workers-b, workers-c, gpu) = 4 calls
            assert mock_ssh.call_count == 4

    def test_status_workers_only(self):
        """Test checking workers status only."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            mock_ssh.return_value = "SERVICE\tSTATUS\nworker\tUp"

            result = runner.invoke(deploy_app, ["status", "workers"])

            assert result.exit_code == 0
            # Should check 2 worker hosts (workers-b, workers-c - GPU is separate target)
            assert mock_ssh.call_count == 2

    def test_status_invalid_target(self):
        """Test that invalid status target aborts."""
        result = runner.invoke(deploy_app, ["status", "invalid-target"])

        assert result.exit_code != 0
        assert "Invalid target" in result.output

    def test_status_core_ssh_failure(self):
        """Test that SSH failure in status is handled."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            mock_ssh.side_effect = Exception("SSH command failed")

            result = runner.invoke(deploy_app, ["status", "core"])

            # Status command should handle errors gracefully
            assert result.exit_code == 0
            assert "SSH command failed" in result.output

    def test_status_workers_partial_failure(self):
        """Test that partial SSH failure in worker status continues."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            # First call succeeds, second fails
            def ssh_side_effect(host, **kwargs):
                if "workers-b" in host:
                    raise Exception("SSH command failed")
                return "SERVICE\tSTATUS\nworker\tUp"

            mock_ssh.side_effect = ssh_side_effect

            result = runner.invoke(deploy_app, ["status", "workers"])

            # Should still succeed overall
            assert result.exit_code == 0
            # Should show error for failed worker
            assert "SSH command failed" in result.output

    def test_status_dry_run(self):
        """Test status command with dry-run."""
        with patch("ktrdr.cli.deploy_commands.ssh_exec_with_env") as mock_ssh:
            mock_ssh.return_value = None  # dry_run returns None

            result = runner.invoke(deploy_app, ["status", "core", "--dry-run"])

            assert result.exit_code == 0
            mock_ssh.assert_called_once()
            assert mock_ssh.call_args[1]["dry_run"] is True
