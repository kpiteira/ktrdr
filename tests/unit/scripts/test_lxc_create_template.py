"""
Unit tests for LXC template creation script.

Tests validate script structure, documentation, and basic logic
without requiring actual Proxmox execution.
"""

import os
import subprocess
from pathlib import Path

SCRIPT_PATH = Path("scripts/lxc/create-template.sh")


class TestLXCTemplateScriptExists:
    """Test that the script exists and is properly configured."""

    def test_script_file_exists(self):
        """Script file should exist at expected path."""
        assert SCRIPT_PATH.exists(), f"Script not found at {SCRIPT_PATH}"

    def test_script_is_executable(self):
        """Script should have executable permissions."""
        assert os.access(SCRIPT_PATH, os.X_OK), "Script is not executable"


class TestLXCTemplateScriptStructure:
    """Test script structure and basic shell syntax."""

    def test_has_bash_shebang(self):
        """Script should start with bash shebang."""
        with open(SCRIPT_PATH) as f:
            first_line = f.readline().strip()
        assert first_line == "#!/bin/bash", "Script must start with #!/bin/bash"

    def test_has_documentation_header(self):
        """Script should have documentation explaining its purpose."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Check for comment block near the top
        assert (
            "# Create base LXC template" in content or "LXC template" in content
        ), "Script should have documentation header"

    def test_script_syntax_is_valid(self):
        """Script should pass bash syntax check."""
        result = subprocess.run(
            ["bash", "-n", str(SCRIPT_PATH)], capture_output=True, text=True
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestLXCTemplateScriptContent:
    """Test that script contains required operations."""

    def test_creates_container_with_pct(self):
        """Script should use pct create command."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "pct create" in content
        ), "Script must use 'pct create' to create LXC container"

    def test_installs_python_313(self):
        """Script should install Python 3.13."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "python3.13" in content, "Script must install Python 3.13"

    def test_installs_uv(self):
        """Script should install uv package manager."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "uv" in content and "install" in content, "Script must install uv"

    def test_creates_base_directories(self):
        """Script should create /opt/ktrdr directory structure."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "/opt/ktrdr" in content, "Script must create /opt/ktrdr directory"

    def test_converts_to_template(self):
        """Script should convert container to template using vzdump."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "vzdump" in content, "Script must use vzdump to create template"

    def test_cleans_up_source_container(self):
        """Script should destroy source container after template creation."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "pct destroy" in content or "pct delete" in content
        ), "Script should clean up source container"


class TestLXCTemplateScriptErrorHandling:
    """Test that script has proper error handling."""

    def test_has_set_e_for_error_handling(self):
        """Script should exit on errors (set -e)."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should have set -e or set -euo pipefail
        assert "set -e" in content, "Script should have 'set -e' for error handling"


class TestLXCTemplateScriptDocumentation:
    """Test that script is properly documented."""

    def test_has_usage_comments(self):
        """Script should document what it does."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should have comments explaining purpose
        has_docs = any(
            [
                "Create base LXC template" in content,
                "Base template" in content,
                "KTRDR worker" in content,
            ]
        )
        assert has_docs, "Script should have documentation explaining purpose"

    def test_documents_template_contents(self):
        """Script should document what's included in template."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        # Should mention key components
        mentions_components = (
            "Ubuntu" in content or "Python" in content or "dependencies" in content
        )
        assert mentions_components, "Script should document template contents"


class TestLXCTemplateScriptConfiguration:
    """Test script configuration and parameters."""

    def test_defines_template_id(self):
        """Script should use container ID 999 for template creation."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert "999" in content, "Script should use ID 999 for template container"

    def test_defines_output_template_name(self):
        """Script should define output template filename."""
        with open(SCRIPT_PATH) as f:
            content = f.read()
        assert (
            "ktrdr-worker-base" in content
        ), "Script should name template 'ktrdr-worker-base'"
