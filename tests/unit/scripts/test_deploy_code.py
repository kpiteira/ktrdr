"""
Unit tests for code deployment script.

Tests validate script structure, logic, and configuration
without requiring actual Proxmox execution.
"""

import os
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/deploy/deploy-code.sh")
SYSTEMD_BACKTEST_PATH = Path("scripts/deploy/systemd/ktrdr-backtest-worker.service")
SYSTEMD_TRAINING_PATH = Path("scripts/deploy/systemd/ktrdr-training-worker.service")


class TestDeployScriptExists:
    """Test that the deployment script exists and is properly configured."""

    def test_script_file_exists(self):
        """Deployment script should exist at expected path."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """Script should have executable permissions."""
        assert os.access(SCRIPT_PATH, os.X_OK), "Script is not executable"


class TestDeployScriptStructure:
    """Test script structure and bash syntax."""

    def test_has_bash_shebang(self):
        """Script should start with bash shebang."""
        with open(SCRIPT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/bin/bash", "Script must start with #!/bin/bash"

    def test_has_documentation_header(self):
        """Script should have documentation explaining its purpose."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "Deploy KTRDR code" in content or "deployment" in content
        ), "Script should have documentation header"

    def test_script_syntax_is_valid(self):
        """Script should pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestDeployScriptContent:
    """Test that script contains required operations."""

    def test_accepts_worker_ids_parameter(self):
        """Script should accept worker IDs as first parameter."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should have default worker IDs or parameter handling
        assert (
            "WORKER_IDS" in content or "$1" in content
        ), "Script must accept worker IDs parameter"

    def test_accepts_git_ref_parameter(self):
        """Script should accept git ref (branch/tag) as parameter."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "GIT_REF" in content or "branch" in content
        ), "Script must accept git ref parameter"

    def test_clones_or_updates_git_repo(self):
        """Script should clone git repo or update existing."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "git clone" in content or "git fetch" in content, "Script must clone/update git repo"
        assert "git checkout" in content, "Script must checkout specified ref"

    def test_installs_dependencies_with_uv(self):
        """Script should install dependencies using uv."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "uv sync" in content, "Script must run 'uv sync' to install dependencies"

    def test_restarts_worker_service(self):
        """Script should restart worker service after deployment."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "systemctl restart" in content or "restart" in content
        ), "Script must restart worker service"

    def test_uses_pct_exec_for_proxmox(self):
        """Script should use pct exec to run commands in LXC."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "pct exec" in content, "Script must use 'pct exec' for Proxmox LXC"

    def test_deploys_to_multiple_workers(self):
        """Script should support deploying to multiple workers."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "for" in content or "loop" in content, "Script should loop over workers"


class TestDeployScriptErrorHandling:
    """Test that script has proper error handling."""

    def test_has_set_e_for_error_handling(self):
        """Script should exit on errors (set -e)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "set -e" in content, "Script should have 'set -e' for error handling"


class TestSystemdServiceFiles:
    """Test systemd service file templates."""

    def test_backtest_worker_service_exists(self):
        """Backtest worker systemd service file should exist."""
        assert (
            SYSTEMD_BACKTEST_PATH.exists()
        ), f"Backtest service file not found at {SYSTEMD_BACKTEST_PATH}"

    def test_training_worker_service_exists(self):
        """Training worker systemd service file should exist."""
        assert (
            SYSTEMD_TRAINING_PATH.exists()
        ), f"Training service file not found at {SYSTEMD_TRAINING_PATH}"

    def test_backtest_service_has_unit_section(self):
        """Backtest service should have [Unit] section."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "[Unit]" in content, "Service must have [Unit] section"

    def test_backtest_service_has_service_section(self):
        """Backtest service should have [Service] section."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "[Service]" in content, "Service must have [Service] section"

    def test_backtest_service_has_install_section(self):
        """Backtest service should have [Install] section."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "[Install]" in content, "Service must have [Install] section"

    def test_backtest_service_uses_ktrdr_user(self):
        """Backtest service should run as ktrdr user."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "User=ktrdr" in content, "Service must run as ktrdr user"

    def test_backtest_service_has_working_directory(self):
        """Backtest service should set working directory."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert (
            "WorkingDirectory=/opt/ktrdr" in content
        ), "Service must set WorkingDirectory"

    def test_backtest_service_starts_backtest_worker(self):
        """Backtest service should start backtest worker."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert (
            "backtest_worker" in content or "backtesting" in content
        ), "Service must start backtest worker"

    def test_backtest_service_uses_uvicorn(self):
        """Backtest service should use uvicorn to run worker."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "uvicorn" in content, "Service must use uvicorn"

    def test_backtest_service_has_restart_policy(self):
        """Backtest service should have restart policy."""
        with open(SYSTEMD_BACKTEST_PATH) as f:
            content = f.read()
        assert "Restart=always" in content, "Service should restart automatically"

    def test_training_service_starts_training_worker(self):
        """Training service should start training worker."""
        with open(SYSTEMD_TRAINING_PATH) as f:
            content = f.read()
        assert (
            "training_worker" in content or "training" in content
        ), "Service must start training worker"


class TestDeployScriptDocumentation:
    """Test that deployment script is properly documented."""

    def test_has_usage_instructions(self):
        """Script should document how to use it."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should have usage comment or parameters documented
        has_docs = any(
            [
                "Usage:" in content,
                "Parameters:" in content,
                "WORKER_IDS" in content,
            ]
        )
        assert has_docs, "Script should document usage"

    def test_documents_parameters(self):
        """Script should document what parameters mean."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should explain worker IDs and git ref
        mentions_params = ("worker" in content.lower() and "git" in content.lower())
        assert mentions_params, "Script should document parameters"
