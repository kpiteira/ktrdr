"""
Unit tests for worker provisioning script.

Tests validate script structure and logic without requiring actual Proxmox execution.
"""

import os
import subprocess
from pathlib import Path


SCRIPT_PATH = Path("scripts/lxc/provision-worker.sh")


class TestProvisionScriptExists:
    """Test that the provisioning script exists and is properly configured."""

    def test_script_file_exists(self):
        """Provisioning script should exist at expected path."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """Script should have executable permissions."""
        assert os.access(SCRIPT_PATH, os.X_OK), "Script is not executable"


class TestProvisionScriptStructure:
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
            "Provision" in content or "provision" in content
        ), "Script should have documentation header"

    def test_script_syntax_is_valid(self):
        """Script should pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestProvisionScriptParameters:
    """Test that script accepts required parameters."""

    def test_accepts_worker_id_parameter(self):
        """Script should accept worker ID as parameter."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "WORKER_ID" in content or "$1" in content, "Script must accept worker ID"

    def test_accepts_worker_ip_parameter(self):
        """Script should accept worker IP as parameter."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "WORKER_IP" in content or "$2" in content, "Script must accept worker IP"

    def test_accepts_worker_type_parameter(self):
        """Script should accept worker type with default."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "WORKER_TYPE" in content or "$3" in content
        ), "Script must accept worker type parameter"

    def test_has_default_worker_type(self):
        """Script should default worker type to backtesting."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "backtesting" in content or "backtest" in content
        ), "Script should default to backtesting type"


class TestProvisionScriptContent:
    """Test that script contains required operations."""

    def test_clones_from_template(self):
        """Script should clone worker from template using pct clone."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "pct clone" in content, "Script must use 'pct clone' to create worker"

    def test_uses_template_id_999(self):
        """Script should clone from template ID 999."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "999" in content, "Script should reference template ID 999"

    def test_configures_network(self):
        """Script should configure network settings."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "pct set" in content or "net0" in content, "Script must configure network"

    def test_starts_worker_container(self):
        """Script should start the worker container."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "pct start" in content, "Script must start worker container"

    def test_creates_env_file(self):
        """Script should create .env file with configuration."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert ".env" in content, "Script must create .env file"

    def test_configures_ktrdr_api_url(self):
        """Script should configure KTRDR_API_URL."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "KTRDR_API_URL" in content, "Script must set KTRDR_API_URL"

    def test_configures_worker_endpoint_url(self):
        """Script should configure WORKER_ENDPOINT_URL."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "WORKER_ENDPOINT_URL" in content
        ), "Script must set WORKER_ENDPOINT_URL"

    def test_configures_worker_type_in_env(self):
        """Script should set WORKER_TYPE in environment."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Check if WORKER_TYPE is being written to .env
        assert "WORKER_TYPE=" in content, "Script must set WORKER_TYPE in .env"

    def test_sets_hostname(self):
        """Script should set hostname based on worker type and ID."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "hostname" in content or "--hostname" in content
        ), "Script should set hostname"


class TestProvisionScriptErrorHandling:
    """Test that script has proper error handling."""

    def test_has_set_e_for_error_handling(self):
        """Script should exit on errors (set -e)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "set -e" in content, "Script should have 'set -e' for error handling"

    def test_validates_required_parameters(self):
        """Script should validate required parameters are provided."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should check for empty parameters or usage message
        has_validation = any(
            [
                "if [ -z" in content,
                "Usage:" in content,
                "required" in content.lower(),
            ]
        )
        assert has_validation, "Script should validate required parameters"


class TestProvisionScriptDocumentation:
    """Test that script is properly documented."""

    def test_has_usage_instructions(self):
        """Script should document how to use it."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        has_docs = any(
            [
                "Usage:" in content,
                "Example:" in content,
                "Parameters:" in content,
            ]
        )
        assert has_docs, "Script should document usage"

    def test_documents_parameters(self):
        """Script should document what parameters mean."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should explain worker ID, IP, and type
        mentions_params = (
            "worker" in content.lower()
            and "IP" in content
            and ("type" in content.lower() or "backtesting" in content)
        )
        assert mentions_params, "Script should document parameters"

    def test_documents_worker_types(self):
        """Script should document available worker types."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should mention backtesting and training types
        mentions_types = "backtesting" in content and "training" in content
        assert mentions_types, "Script should document worker types"
