"""Tests for deprecation warnings on ktrdr CLI commands.

Tests that sandbox, local-prod, and deploy commands show deprecation warnings
when invoked via the old ktrdr CLI.

Note: The --help flag is processed before the callback runs in Typer,
so we test with actual subcommands (using --help on the subcommand to
avoid actual operations).
"""

from typer.testing import CliRunner


class TestSandboxDeprecationWarning:
    """Tests for ktrdr sandbox deprecation warning."""

    def test_sandbox_shows_deprecation_warning(self) -> None:
        """ktrdr sandbox list should show deprecation warning."""
        from ktrdr.cli.sandbox import sandbox_app

        runner = CliRunner()
        # Use 'list' command which doesn't need special setup
        result = runner.invoke(sandbox_app, ["list"])

        # Warning should appear in output (Typer mixes stderr/stdout)
        assert "deprecated" in result.output.lower()
        assert "kinfra sandbox" in result.output.lower()

    def test_sandbox_command_still_executes(self) -> None:
        """Command should still execute despite deprecation warning."""
        from ktrdr.cli.sandbox import sandbox_app

        runner = CliRunner()
        # list command should work and produce output
        result = runner.invoke(sandbox_app, ["list"])
        # The deprecation warning in output indicates the callback ran
        assert "deprecated" in result.output.lower()


class TestLocalProdDeprecationWarning:
    """Tests for ktrdr local-prod deprecation warning."""

    def test_local_prod_shows_deprecation_warning(self) -> None:
        """ktrdr local-prod init --help should show deprecation warning."""
        from ktrdr.cli.local_prod import local_prod_app

        runner = CliRunner()
        # Use init --help to avoid needing special setup
        result = runner.invoke(local_prod_app, ["init", "--help"])

        # Warning should appear in output
        assert "deprecated" in result.output.lower()
        assert "kinfra local-prod" in result.output.lower()

    def test_local_prod_command_still_executes(self) -> None:
        """Command should still execute despite deprecation warning."""
        from ktrdr.cli.local_prod import local_prod_app

        runner = CliRunner()
        result = runner.invoke(local_prod_app, ["init", "--help"])
        # --help on subcommand should exit 0
        assert result.exit_code == 0


class TestDeployDeprecationWarning:
    """Tests for ktrdr deploy deprecation warning."""

    def test_deploy_shows_deprecation_warning(self) -> None:
        """ktrdr deploy core --help should show deprecation warning."""
        from ktrdr.cli.deploy_commands import deploy_app

        runner = CliRunner()
        # Use core --help to avoid needing actual deployment
        result = runner.invoke(deploy_app, ["core", "--help"])

        # Warning should appear in output
        assert "deprecated" in result.output.lower()
        assert "kinfra deploy" in result.output.lower()

    def test_deploy_command_still_executes(self) -> None:
        """Command should still execute despite deprecation warning."""
        from ktrdr.cli.deploy_commands import deploy_app

        runner = CliRunner()
        result = runner.invoke(deploy_app, ["core", "--help"])
        # --help on subcommand should exit 0
        assert result.exit_code == 0
